"""Tests del sistema de invitaciones (utils/invites.py + utils/invites_db.py).

Cubren los casos de aceptación del informe (§10), la lógica pura de atribución y
los invariantes de persistencia. No tocan discord.py ni la red: usan dobles.
"""
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from utils.invites import (
    DEFAULT_JOIN_ATTRIBUTED, ELIG_EXCLUDED, ELIG_NOT_ATTRIBUTED, ELIG_VALID, EXCLUDE_BOT,
    EXCLUDE_RECENT, SOURCE_INVITE, SOURCE_UNKNOWN, SOURCE_VANITY, STATUS_AMBIGUOUS,
    STATUS_INFERRED, STATUS_MANUAL, STATUS_UNRESOLVED, VANITY_CODE, InviteTracker,
    PendingJoin, build_snapshot, build_stay_plan, compute_increments,
    default_join_template, invite_entry, render_template, resolve_attribution,
    validate_template,
)
from utils.invites_db import InviteStore

NOW = datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc)


# ── dobles de discord.py ─────────────────────────────────────────────────────
class FakeInvite:
    def __init__(self, code, inviter_id=None, uses=0, is_vanity=False, guild=1, **kw):
        self.code = code
        self.inviter = SimpleNamespace(id=inviter_id) if inviter_id is not None else None
        self.uses = uses
        self.max_uses = kw.get("max_uses")
        self.max_age = kw.get("max_age")
        self.temporary = kw.get("temporary", False)
        self.created_at = kw.get("created_at")
        self.is_vanity = is_vanity
        self.guild = SimpleNamespace(id=guild)


class FakeGuild:
    def __init__(self, gid):
        self.id = gid


class FakeMember:
    def __init__(self, mid, guild, bot=False, created_days_ago=30.0, name=None):
        self.id = mid
        self.guild = guild
        self.bot = bot
        self.created_at = NOW - timedelta(days=created_days_ago)
        self.display_name = name or f"user{mid}"
        self.mention = f"<@{mid}>"


class World:
    """Mundo de prueba: store + tracker + invitaciones mutables."""

    def __init__(self, path, guild_ids=(1,)):
        self.store = InviteStore(path)
        self.guilds = {g: FakeGuild(g) for g in guild_ids}
        self.invites = {}   # (guild, code) -> {inviter, uses, is_vanity}
        self.vanity = {}    # guild -> uses
        self.tracker = InviteTracker(self.store, self._provider, self._resolver)
        self.tracker.DEBOUNCE_SECONDS = 0
        self.tracker.now = lambda: NOW

    def _resolver(self, gid):
        return self.guilds.get(int(gid))

    async def _provider(self, guild):
        invites = []
        vanity = None
        for (g, code), info in self.invites.items():
            if g != guild.id:
                continue
            invites.append(FakeInvite(code, info["inviter"], info["uses"],
                                      info.get("is_vanity", False)))
        van = self.vanity.get(guild.id)
        if van is not None:
            vanity = FakeInvite(VANITY_CODE, None, van, is_vanity=True)
        return build_snapshot(invites, vanity)

    def set_invite(self, guild, code, inviter, uses=0, is_vanity=False):
        self.invites[(guild, code)] = {"inviter": inviter, "uses": uses, "is_vanity": is_vanity}

    def bump(self, guild, code, delta=1):
        self.invites[(guild, code)]["uses"] += delta

    def remove_invite(self, guild, code):
        self.invites.pop((guild, code), None)

    async def baseline(self, guild):
        await self.tracker.startup_sync(self.guilds[guild])

    async def join(self, guild, mid, **kw):
        member = FakeMember(mid, self.guilds[guild], **kw)
        self.tracker.enqueue_join(member)
        results = await self.tracker.process_guild(self.guilds[guild])
        return member, results

    async def leave(self, guild, mid):
        return await self.tracker.note_leave(FakeMember(mid, self.guilds[guild]))


class TempStoreMixin:
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self._tmp.name, "invites.db")

    def tearDown(self):
        self._tmp.cleanup()


# ── lógica pura: snapshots e incrementos ─────────────────────────────────────
class TestSnapshotAndIncrements(unittest.TestCase):
    def test_invite_entry_duck_typing(self):
        entry = invite_entry(FakeInvite("abc", 42, uses=3, max_uses=10, max_age=3600,
                                        temporary=True))
        self.assertEqual(entry["code"], "abc")
        self.assertEqual(entry["inviter_id"], "42")
        self.assertEqual(entry["uses"], 3)
        self.assertTrue(entry["temporary"])

    def test_build_snapshot_includes_vanity(self):
        snap = build_snapshot([FakeInvite("a", 1, uses=2)],
                              vanity=FakeInvite("van", None, uses=5, is_vanity=True))
        self.assertIn("a", snap)
        self.assertIn("van", snap)
        self.assertTrue(snap["van"]["is_vanity"])

    def test_increment_measures_first_seen_against_zero(self):
        new = build_snapshot([FakeInvite("a", 1, uses=4)])
        inc = compute_increments(None, new)
        self.assertEqual(inc["regular"], {"a": 4})

    def test_removed_codes_kept_as_evidence_not_usage(self):
        prev = build_snapshot([FakeInvite("a", 1, uses=1), FakeInvite("b", 2, uses=0)])
        new = build_snapshot([FakeInvite("a", 1, uses=2)])
        inc = compute_increments(prev, new)
        self.assertEqual(inc["regular"], {"a": 1})
        self.assertEqual(inc["removed"], ["b"])

    def test_vanity_delta_separated_from_regular(self):
        prev = build_snapshot([], vanity=FakeInvite(VANITY_CODE, None, uses=1, is_vanity=True))
        new = build_snapshot([FakeInvite("a", 1, uses=1)],
                             vanity=FakeInvite(VANITY_CODE, None, uses=3, is_vanity=True))
        inc = compute_increments(prev, new)
        self.assertEqual(inc["vanity_delta"], 2)
        self.assertEqual(inc["regular"], {"a": 1})


# ── lógica pura: resolución conservadora ─────────────────────────────────────
class TestResolveAttribution(unittest.TestCase):
    def _p(self, *ids):
        return [PendingJoin(member_id=i) for i in ids]

    def test_baseline_never_attributes(self):
        res = resolve_attribution(None, build_snapshot([FakeInvite("a", 1, uses=1)]), self._p("m1"))
        self.assertEqual(res["m1"].attribution_status, STATUS_UNRESOLVED)
        self.assertEqual(res["m1"].attribution_reason, "baseline")

    def test_single_increment_single_join(self):
        prev = build_snapshot([FakeInvite("a", 7, uses=0)])
        new = build_snapshot([FakeInvite("a", 7, uses=1)])
        res = resolve_attribution(prev, new, self._p("m1"))
        self.assertEqual(res["m1"].attribution_status, STATUS_INFERRED)
        self.assertEqual(res["m1"].invite_code, "a")
        self.assertEqual(res["m1"].observed_inviter_id, "7")

    def test_batch_same_code(self):
        prev = build_snapshot([FakeInvite("a", 7, uses=0)])
        new = build_snapshot([FakeInvite("a", 7, uses=2)])
        res = resolve_attribution(prev, new, self._p("m1", "m2"))
        self.assertTrue(all(res[m].attribution_status == STATUS_INFERRED for m in ("m1", "m2")))

    def test_two_codes_no_arbitrary_pick(self):
        prev = build_snapshot([FakeInvite("a", 1, uses=0), FakeInvite("b", 2, uses=0)])
        new = build_snapshot([FakeInvite("a", 1, uses=1), FakeInvite("b", 2, uses=1)])
        res = resolve_attribution(prev, new, self._p("m1"))
        for m in ("m1",):
            self.assertEqual(res[m].attribution_status, STATUS_AMBIGUOUS)
            self.assertIsNone(res[m].observed_inviter_id)

    def test_count_mismatch_is_ambiguous(self):
        prev = build_snapshot([FakeInvite("a", 1, uses=0)])
        new = build_snapshot([FakeInvite("a", 1, uses=3)])
        res = resolve_attribution(prev, new, self._p("m1"))  # 3 usos, 1 entrada
        self.assertEqual(res["m1"].attribution_status, STATUS_AMBIGUOUS)

    def test_no_increment_unresolved(self):
        prev = build_snapshot([FakeInvite("a", 1, uses=5)])
        new = build_snapshot([FakeInvite("a", 1, uses=5)])
        res = resolve_attribution(prev, new, self._p("m1"))
        self.assertEqual(res["m1"].attribution_status, STATUS_UNRESOLVED)
        self.assertEqual(res["m1"].attribution_reason, "no_increment")

    def test_vanity_only_is_vanity_source(self):
        prev = build_snapshot([], vanity=FakeInvite(VANITY_CODE, None, uses=0, is_vanity=True))
        new = build_snapshot([], vanity=FakeInvite(VANITY_CODE, None, uses=1, is_vanity=True))
        res = resolve_attribution(prev, new, self._p("m1"))
        self.assertEqual(res["m1"].attribution_status, STATUS_INFERRED)
        self.assertEqual(res["m1"].source_type, SOURCE_VANITY)
        self.assertIsNone(res["m1"].observed_inviter_id)

    def test_vanity_and_invite_together_ambiguous(self):
        prev = build_snapshot([FakeInvite("a", 1, uses=0)],
                              vanity=FakeInvite(VANITY_CODE, None, uses=0, is_vanity=True))
        new = build_snapshot([FakeInvite("a", 1, uses=1)],
                             vanity=FakeInvite(VANITY_CODE, None, uses=1, is_vanity=True))
        res = resolve_attribution(prev, new, self._p("m1"))
        self.assertEqual(res["m1"].attribution_status, STATUS_AMBIGUOUS)


# ── lógica pura: plantillas ──────────────────────────────────────────────────
class TestTemplates(unittest.TestCase):
    def test_validate_rejects_unknown_vars(self):
        with self.assertRaises(ValueError):
            validate_template("{no_existe}")

    def test_validate_rejects_empty_and_long(self):
        with self.assertRaises(ValueError):
            validate_template("   ")
        with self.assertRaises(ValueError):
            validate_template("x" * 2000)

    def test_render_fills_known_and_blanks_missing(self):
        # {invite_code} es una variable VÁLIDA sin valor en el contexto → queda vacía.
        out = render_template("{member} invitado por {inviter} ({invite_code})",
                              {"member": "<@1>", "inviter": "<@2>"})
        self.assertEqual(out, "<@1> invitado por <@2> ()")

    def test_render_never_raises_on_bad_template(self):
        self.assertEqual(render_template("{member", {"member": "x"}), "{member")

    def test_default_template_selection(self):
        self.assertEqual(default_join_template(SOURCE_INVITE, STATUS_INFERRED, False),
                         DEFAULT_JOIN_ATTRIBUTED)
        self.assertIn("excluida", default_join_template(SOURCE_INVITE, STATUS_INFERRED, True))


# ── lógica pura: plan de estancia ────────────────────────────────────────────
class TestBuildStayPlan(unittest.TestCase):
    def test_rejoin_restores_prior_credit_and_ignores_new_link(self):
        pending = [PendingJoin(member_id="m1", account_created_at=NOW - timedelta(days=90))]
        resolutions = {"m1": SimpleNamespace(
            member_id="m1", invite_code="new", observed_inviter_id="999",
            source_type=SOURCE_INVITE, attribution_status=STATUS_INFERRED,
            attribution_reason="single_increment")}
        stays, restores = build_stay_plan(
            pending, resolutions, {"recent_account_days": 7, "rejoin_restores": 1},
            NOW, prior_credit_for=lambda mid: {"id": 55, "inviter_id": "1"},
            is_rejoin=lambda mid: True)
        self.assertEqual(restores, [55])
        self.assertIsNone(stays[0]["credit"])           # no concede crédito nuevo
        self.assertEqual(stays[0]["restored_credit_id"], 55)

    def test_recent_account_excluded(self):
        pending = [PendingJoin(member_id="m1", account_created_at=NOW - timedelta(hours=1))]
        resolutions = {"m1": SimpleNamespace(
            member_id="m1", invite_code="a", observed_inviter_id="1",
            source_type=SOURCE_INVITE, attribution_status=STATUS_INFERRED,
            attribution_reason="single_increment")}
        stays, _ = build_stay_plan(
            pending, resolutions, {"recent_account_days": 7, "rejoin_restores": 1},
            NOW, prior_credit_for=lambda mid: None, is_rejoin=lambda mid: False)
        self.assertEqual(stays[0]["eligibility_status"], ELIG_EXCLUDED)
        self.assertEqual(stays[0]["exclusion_reasons"], [EXCLUDE_RECENT])
        self.assertEqual(stays[0]["credit"]["eligible"], 0)

    def test_bot_excluded(self):
        pending = [PendingJoin(member_id="m1", is_bot=True)]
        resolutions = {"m1": SimpleNamespace(
            member_id="m1", invite_code=None, observed_inviter_id=None,
            source_type=SOURCE_UNKNOWN, attribution_status=STATUS_UNRESOLVED,
            attribution_reason="no_increment")}
        stays, _ = build_stay_plan(
            pending, resolutions, {"recent_account_days": 7, "rejoin_restores": 1},
            NOW, prior_credit_for=lambda mid: None, is_rejoin=lambda mid: False)
        self.assertEqual(stays[0]["eligibility_status"], ELIG_EXCLUDED)
        self.assertEqual(stays[0]["exclusion_reasons"], [EXCLUDE_BOT])

    def test_unresolved_not_attributed(self):
        pending = [PendingJoin(member_id="m1", account_created_at=NOW - timedelta(days=90))]
        resolutions = {"m1": SimpleNamespace(
            member_id="m1", invite_code=None, observed_inviter_id=None,
            source_type=SOURCE_UNKNOWN, attribution_status=STATUS_UNRESOLVED,
            attribution_reason="no_increment")}
        stays, _ = build_stay_plan(
            pending, resolutions, {"recent_account_days": 7, "rejoin_restores": 1},
            NOW, prior_credit_for=lambda mid: None, is_rejoin=lambda mid: False)
        self.assertEqual(stays[0]["eligibility_status"], ELIG_NOT_ATTRIBUTED)
        self.assertIsNone(stays[0]["credit"])


# ── persistencia ─────────────────────────────────────────────────────────────
class TestInviteStore(TempStoreMixin, unittest.TestCase):
    def test_migration_is_idempotent(self):
        store = InviteStore(self.db_path)
        store.close()
        store = InviteStore(self.db_path)  # reabrir no re-aplica
        versions = [r["version"] for r in store._query("SELECT version FROM schema_migrations")]
        self.assertEqual(versions, [1])

    def test_at_most_one_active_stay_per_member(self):
        store = InviteStore(self.db_path)
        stay = {"member_id": "m1", "joined_at": "2026-01-01T00:00:00+00:00",
                "event_id": "e1"}
        with store._tx() as conn:
            first = store.append_stay(conn, 1, stay)
        with store._tx() as conn:
            second = store.append_stay(conn, 1, {**stay, "event_id": "e2"})
        self.assertIsNotNone(first)
        self.assertIsNone(second)

    def test_replace_snapshot_keeps_removed_inactive(self):
        store = InviteStore(self.db_path)
        store.replace_snapshot(1, build_snapshot([FakeInvite("a", 1, uses=0)]))
        store.replace_snapshot(1, build_snapshot([FakeInvite("b", 2, uses=0)]))
        self.assertEqual(list(store.get_snapshot(1).keys()), ["b"])
        row = store._one("SELECT active FROM invite_snapshots WHERE guild_id = ? AND code = ?",
                         ("1", "a"))
        self.assertEqual(row["active"], 0)

    def test_score_is_credits_plus_adjustments(self):
        store = InviteStore(self.db_path)
        with store._tx() as conn:
            sid = store.append_stay(conn, 1, {"member_id": "m1", "joined_at": "t",
                                              "event_id": "e1"})
            store.add_credit(conn, 1, sid, "m1", "inviter", SOURCE_INVITE, 1)
        store.add_adjustment(1, "inviter", 5, "evento", "admin")
        self.assertEqual(store.score(1, "inviter"), 6)

    def test_reset_observations_clears_stays_and_snapshot(self):
        store = InviteStore(self.db_path)
        with store._tx() as conn:
            store.append_stay(conn, 1, {"member_id": "m1", "joined_at": "t",
                                        "event_id": "e1"})
        store.replace_snapshot(1, build_snapshot([FakeInvite("a", 1)]))
        store.reset_guild(1, "observations")
        self.assertEqual(store.list_stays(1, "m1"), [])
        self.assertEqual(store.get_snapshot(1), {})


# ── integración del tracker ──────────────────────────────────────────────────
class TestTrackerIntegration(TempStoreMixin, unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.world = World(self.db_path)

    async def test_one_join_one_increment_credited(self):
        w = self.world
        w.set_invite(1, "a", "u1", uses=0)
        await w.baseline(1)
        w.bump(1, "a")
        _, results = await w.join(1, "m1")
        self.assertEqual(results[0]["attribution_status"], STATUS_INFERRED)
        self.assertEqual(results[0]["observed_inviter_id"], "u1")
        self.assertEqual(w.store.score(1, "u1"), 1)

    async def test_double_increment_in_one_batch_no_arbitrary_choice(self):
        w = self.world
        w.set_invite(1, "a", "u1", uses=0)
        w.set_invite(1, "b", "u2", uses=0)
        await w.baseline(1)
        w.bump(1, "a")
        w.bump(1, "b")
        _, results = await w.join(1, "m1")
        self.assertEqual(results[0]["attribution_status"], STATUS_AMBIGUOUS)
        self.assertEqual(w.store.score(1, "u1"), 0)
        self.assertEqual(w.store.score(1, "u2"), 0)

    async def test_valid_member_leaves_removes_credit_once(self):
        w = self.world
        w.set_invite(1, "a", "u1", uses=0)
        await w.baseline(1)
        w.bump(1, "a")
        await w.join(1, "m1")
        self.assertEqual(w.store.score(1, "u1"), 1)
        await w.leave(1, "m1")
        self.assertEqual(w.store.score(1, "u1"), 0)
        self.assertIsNone(await w.leave(1, "m1"))  # salida duplicada no re-descuenta

    async def test_recent_account_excluded_then_leaves_no_penalty(self):
        w = self.world
        w.set_invite(1, "a", "u1", uses=0)
        await w.baseline(1)
        w.bump(1, "a")
        _, results = await w.join(1, "m1", created_days_ago=0.0)
        self.assertEqual(results[0]["eligibility_status"], ELIG_EXCLUDED)
        self.assertIn(EXCLUDE_RECENT, results[0]["exclusion_reasons"])
        self.assertEqual(w.store.score(1, "u1"), 0)
        await w.leave(1, "m1")
        self.assertEqual(w.store.score(1, "u1"), 0)

    async def test_rejoin_via_different_link_restores_original_owner(self):
        w = self.world
        w.set_invite(1, "a", "u1", uses=0)
        w.set_invite(1, "b", "u2", uses=0)
        await w.baseline(1)
        w.bump(1, "a")
        await w.join(1, "m1")
        await w.leave(1, "m1")
        w.bump(1, "b")  # vuelve por otro enlace
        _, results = await w.join(1, "m1")
        self.assertTrue(results[0]["rejoin_restored"])
        self.assertEqual(w.store.score(1, "u1"), 1)   # propietario original restaurado
        self.assertEqual(w.store.score(1, "u2"), 0)   # el enlace nuevo no transfiere

    async def test_restart_does_not_credit_historical_uses(self):
        w = self.world
        w.set_invite(1, "a", "u1", uses=5)
        await w.baseline(1)              # baseline captura uses=5
        _, results = await w.join(1, "m1")  # no hubo incremento nuevo
        self.assertEqual(results[0]["attribution_status"], STATUS_UNRESOLVED)
        self.assertEqual(w.store.score(1, "u1"), 0)

    async def test_restart_records_observation_gap(self):
        w = self.world
        w.set_invite(1, "a", "u1", uses=0)
        await w.baseline(1)
        await w.baseline(1)  # segunda línea base → hueco "restart"
        gaps = w.store._query("SELECT * FROM invite_observation_gaps WHERE guild_id = ?", ("1",))
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]["reason"], "restart")
        self.assertIsNotNone(gaps[0]["ended_at"])

    async def test_vanity_join_has_no_personal_inviter(self):
        w = self.world
        w.vanity[1] = 0
        await w.baseline(1)
        w.vanity[1] = 1
        _, results = await w.join(1, "m1")
        self.assertEqual(results[0]["source_type"], SOURCE_VANITY)
        self.assertIsNone(results[0]["observed_inviter_id"])

    async def test_deleted_invite_kept_as_evidence(self):
        w = self.world
        w.set_invite(1, "a", "u1", uses=0)
        w.set_invite(1, "b", "u2", uses=0)
        await w.baseline(1)
        # La invitación "a" desaparece de Discord (borrada) y llega el evento.
        w.remove_invite(1, "a")
        await w.tracker.note_invite_delete(FakeInvite("a", "u1", guild=1))
        _, results = await w.join(1, "m1")  # sin incremento → unresolved
        self.assertEqual(results[0]["attribution_status"], STATUS_UNRESOLVED)
        row = w.store._one("SELECT active FROM invite_snapshots WHERE guild_id = ? AND code = ?",
                           ("1", "a"))
        self.assertIsNotNone(row)      # la evidencia no se borra
        self.assertEqual(row["active"], 0)

    async def test_publish_failure_does_not_undo_registration(self):
        w = self.world
        w.set_invite(1, "a", "u1", uses=0)
        await w.baseline(1)
        w.bump(1, "a")

        async def boom(guild, results):
            raise RuntimeError("fallo al publicar")

        w.tracker.result_handler = boom
        member = FakeMember("m1", w.guilds[1])
        w.tracker.enqueue_join(member)
        await w.tracker._debounced("1")  # el handler revienta pero no debe propagar
        self.assertEqual(w.store.score(1, "u1"), 1)  # el registro persiste

    async def test_two_guilds_are_independent(self):
        w = World(self.db_path, guild_ids=(1, 2))
        w.set_invite(1, "a", "u1", uses=0)
        w.set_invite(2, "z", "u9", uses=0)
        await w.baseline(1)
        await w.baseline(2)
        w.bump(1, "a")
        await w.join(1, "m1")
        self.assertEqual(w.store.score(1, "u1"), 1)
        self.assertEqual(w.store.score(2, "u9"), 0)
        self.assertEqual(w.store.leaderboard(2), [])

    async def test_admin_correction_is_audited_and_moves_score(self):
        w = self.world
        w.set_invite(1, "a", "u1", uses=0)
        await w.baseline(1)
        w.bump(1, "a")
        await w.join(1, "m1")
        stay = w.store.get_active_stay(1, "m1")
        ok = await w.tracker.correct_stay(w.guilds[1], stay["id"], "u7", None, "prueba manual", "admin")
        self.assertTrue(ok)
        self.assertEqual(w.store.score(1, "u1"), 0)
        self.assertEqual(w.store.score(1, "u7"), 1)
        audit = w.store.list_audit(1)
        self.assertEqual(audit[0]["action"], "correct")
        self.assertEqual(w.store.get_stay(stay["id"])["attribution_status"], STATUS_MANUAL)

    async def test_rule_change_does_not_recalculate_history(self):
        w = self.world
        w.set_invite(1, "a", "u1", uses=0)
        w.store.update_settings(1, recent_account_days=7, rules_version=1)
        await w.baseline(1)
        w.bump(1, "a")
        await w.join(1, "m1", created_days_ago=0.0)  # excluida con reglas v1
        old = w.store.get_active_stay(1, "m1")
        self.assertEqual(old["eligibility_status"], ELIG_EXCLUDED)
        self.assertEqual(old["rules_version"], 1)
        w.store.update_settings(1, recent_account_days=0, rules_version=2)
        unchanged = w.store.get_active_stay(1, "m1")
        self.assertEqual(unchanged["eligibility_status"], ELIG_EXCLUDED)
        self.assertEqual(unchanged["rules_version"], 1)

    async def test_unreadable_snapshot_requeues_pending(self):
        w = self.world
        w.set_invite(1, "a", "u1", uses=0)
        await w.baseline(1)
        w.bump(1, "a")

        async def broken(guild):
            return None

        w.tracker.snapshot_provider = broken
        member = FakeMember("m1", w.guilds[1])
        w.tracker.enqueue_join(member)
        results = await w.tracker.process_guild(w.guilds[1])
        self.assertEqual(results, [])
        self.assertEqual(len(w.tracker._pending["1"]), 1)  # no se pierde

    async def test_duplicate_join_event_is_idempotent(self):
        w = self.world
        w.set_invite(1, "a", "u1", uses=0)
        await w.baseline(1)
        w.bump(1, "a")
        await w.join(1, "m1")
        # Segundo on_member_join del MISMO evento sin nueva entrada: no duplica estancia.
        w.tracker.enqueue_join(FakeMember("m1", w.guilds[1]))
        await w.tracker.process_guild(w.guilds[1])
        stays = w.store.list_stays(1, "m1")
        self.assertEqual(len(stays), 1)
        self.assertEqual(w.store.score(1, "u1"), 1)


if __name__ == "__main__":
    unittest.main()

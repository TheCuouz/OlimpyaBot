"""Persistencia del módulo de invitaciones (SQLite, stdlib — sin dependencias nuevas).

Por qué SQLite y no JSON: el módulo de invitaciones exige invariantes que un JSON
plano no puede garantizar de forma segura (una única estancia activa por miembro,
transacciones que guardan estancia + crédito + snapshot a la vez, índices por
guild_id y agregados reconstruibles). `sqlite3` es de la biblioteca estándar, así
que NO añade ninguna dependencia al bot. El fichero vive en DATA_DIR/invites.db
(gitignorado, volumen en Railway) igual que data/tickets.json.

Todo el estado de invitaciones es DERIVABLE de las tablas fuente (stays + créditos
+ ajustes): los contadores de puntuación se calculan en el momento, nunca se
guardan como verdad única.
"""
import json
import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Dict, List, Optional

from utils.logger import logger


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


# ── Esquema versionado ───────────────────────────────────────────────────────
# Cada entrada es (version, [sentencias]). Se aplican en orden y se registran en
# schema_migrations. La sentencia duplicada documental vive en migrations/*.sql.
_SCHEMA_V1 = [
    """
    CREATE TABLE IF NOT EXISTS invite_settings (
        guild_id         TEXT PRIMARY KEY,
        enabled          INTEGER NOT NULL DEFAULT 1,
        rules_version    INTEGER NOT NULL DEFAULT 1,
        recent_account_days INTEGER NOT NULL DEFAULT 7,
        count_bots       INTEGER NOT NULL DEFAULT 0,
        rejoin_restores  INTEGER NOT NULL DEFAULT 1,
        announce_channel_id TEXT,
        join_template    TEXT,
        leave_template   TEXT,
        leaderboard_visibility TEXT NOT NULL DEFAULT 'self',
        created_at       TEXT NOT NULL,
        updated_at       TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS invite_snapshots (
        guild_id    TEXT NOT NULL,
        code        TEXT NOT NULL,
        inviter_id  TEXT,
        uses        INTEGER NOT NULL DEFAULT 0,
        max_uses    INTEGER,
        max_age     INTEGER,
        temporary   INTEGER NOT NULL DEFAULT 0,
        is_vanity   INTEGER NOT NULL DEFAULT 0,
        created_at  TEXT,
        observed_at TEXT NOT NULL,
        active      INTEGER NOT NULL DEFAULT 1,
        PRIMARY KEY (guild_id, code)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS invite_observation_gaps (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id   TEXT NOT NULL,
        started_at TEXT NOT NULL,
        ended_at   TEXT,
        reason     TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS membership_stays (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id          TEXT NOT NULL,
        member_id         TEXT NOT NULL,
        joined_at         TEXT NOT NULL,
        left_at           TEXT,
        invite_code       TEXT,
        observed_inviter_id TEXT,
        source_type       TEXT NOT NULL DEFAULT 'unknown',
        attribution_status TEXT NOT NULL DEFAULT 'unresolved',
        attribution_reason TEXT,
        eligibility_status TEXT NOT NULL DEFAULT 'pending',
        exclusion_reasons TEXT,
        is_bot            INTEGER NOT NULL DEFAULT 0,
        account_created_at TEXT,
        event_id          TEXT,
        rules_version     INTEGER NOT NULL DEFAULT 1,
        created_at        TEXT NOT NULL,
        updated_at        TEXT NOT NULL
    )
    """,
    # A lo sumo UNA estancia activa por miembro y servidor (anti-duplicado).
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_stay_active "
    "ON membership_stays(guild_id, member_id) WHERE left_at IS NULL",
    # Idempotencia por identidad de evento cuando Discord la da.
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_stay_event "
    "ON membership_stays(guild_id, event_id) WHERE event_id IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS ix_stay_guild_member ON membership_stays(guild_id, member_id)",
    "CREATE INDEX IF NOT EXISTS ix_stay_guild_joined ON membership_stays(guild_id, joined_at)",
    """
    CREATE TABLE IF NOT EXISTS invite_credits (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id       TEXT NOT NULL,
        stay_id        INTEGER NOT NULL,
        member_id      TEXT NOT NULL,
        inviter_id     TEXT,
        source_type    TEXT NOT NULL,
        eligible       INTEGER NOT NULL DEFAULT 0,
        exclusion_reasons TEXT,
        is_rejoin_restore INTEGER NOT NULL DEFAULT 0,
        active         INTEGER NOT NULL DEFAULT 1,
        created_at     TEXT NOT NULL,
        updated_at     TEXT NOT NULL,
        FOREIGN KEY (stay_id) REFERENCES membership_stays(id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_credit_guild_inviter ON invite_credits(guild_id, inviter_id)",
    "CREATE INDEX IF NOT EXISTS ix_credit_stay ON invite_credits(stay_id)",
    """
    CREATE TABLE IF NOT EXISTS invite_adjustments (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id   TEXT NOT NULL,
        user_id    TEXT NOT NULL,
        amount     INTEGER NOT NULL,
        reason     TEXT NOT NULL,
        actor_id   TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_adj_guild_user ON invite_adjustments(guild_id, user_id)",
    """
    CREATE TABLE IF NOT EXISTS invite_audit_log (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id   TEXT NOT NULL,
        actor_id   TEXT,
        action     TEXT NOT NULL,
        target     TEXT,
        details    TEXT,
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS ix_audit_guild ON invite_audit_log(guild_id, created_at)",
    """
    CREATE TABLE IF NOT EXISTS invite_reward_rules (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        guild_id  TEXT NOT NULL,
        threshold INTEGER NOT NULL,
        role_id   TEXT NOT NULL,
        UNIQUE (guild_id, threshold)
    )
    """,
]

MIGRATIONS = [(1, _SCHEMA_V1)]


class InviteStore:
    """Capa de datos del módulo de invitaciones. Todas las mutaciones que tocan
    varias tablas van en una sola transacción (estancia + crédito + snapshot)."""

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.RLock()
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.isolation_level = None  # autocommit; transacciones explícitas
        self._conn.execute("PRAGMA foreign_keys = ON")
        try:
            self._conn.execute("PRAGMA journal_mode = WAL")
        except sqlite3.DatabaseError:
            pass  # p.ej. en :memory: no aplica, no es error
        self._migrate()

    # ── infra ────────────────────────────────────────────────────────────────
    @contextmanager
    def _tx(self):
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield self._conn
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def _exec(self, sql: str, params=()):
        with self._lock:
            return self._conn.execute(sql, params)

    def _query(self, sql: str, params=()) -> List[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def _one(self, sql: str, params=()) -> Optional[sqlite3.Row]:
        rows = self._query(sql, params)
        return rows[0] if rows else None

    def close(self):
        with self._lock:
            self._conn.close()

    def _migrate(self):
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        applied = {r["version"] for r in self._conn.execute("SELECT version FROM schema_migrations")}
        for version, statements in MIGRATIONS:
            if version in applied:
                continue
            with self._tx() as conn:
                for stmt in statements:
                    conn.execute(stmt)
                conn.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES(?, ?)",
                    (version, iso(utcnow())),
                )
            logger.info(f"invites: migración {version} aplicada")

    # ── settings ───────────────────────────────────────────────────────────--
    def ensure_settings(self, guild_id) -> dict:
        gid = str(guild_id)
        row = self._one("SELECT * FROM invite_settings WHERE guild_id = ?", (gid,))
        if row is None:
            now = iso(utcnow())
            self._exec(
                "INSERT INTO invite_settings(guild_id, created_at, updated_at) VALUES(?, ?, ?)",
                (gid, now, now),
            )
            row = self._one("SELECT * FROM invite_settings WHERE guild_id = ?", (gid,))
        return dict(row)

    def get_settings(self, guild_id) -> Optional[dict]:
        row = self._one("SELECT * FROM invite_settings WHERE guild_id = ?", (str(guild_id),))
        return dict(row) if row else None

    def update_settings(self, guild_id, **fields) -> dict:
        allowed = {
            "enabled", "rules_version", "recent_account_days", "count_bots",
            "rejoin_restores", "announce_channel_id", "join_template",
            "leave_template", "leaderboard_visibility",
        }
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"campos de configuración desconocidos: {sorted(unknown)}")
        self.ensure_settings(guild_id)
        if fields:
            cols = ", ".join(f"{k} = ?" for k in fields)
            params = list(fields.values()) + [iso(utcnow()), str(guild_id)]
            self._exec(
                f"UPDATE invite_settings SET {cols}, updated_at = ? WHERE guild_id = ?",
                params,
            )
        return self.get_settings(guild_id)

    # ── snapshots ──────────────────────────────────────────────────────────--
    def get_snapshot(self, guild_id) -> Dict[str, dict]:
        rows = self._query(
            "SELECT * FROM invite_snapshots WHERE guild_id = ? AND active = 1", (str(guild_id),)
        )
        snap = {}
        for r in rows:
            d = dict(r)
            d["is_vanity"] = bool(d["is_vanity"])
            d["temporary"] = bool(d["temporary"])
            snap[r["code"]] = d
        return snap

    def get_snapshot_observed_at(self, guild_id) -> Optional[str]:
        row = self._one(
            "SELECT MAX(observed_at) AS o FROM invite_snapshots WHERE guild_id = ?",
            (str(guild_id),),
        )
        return row["o"] if row and row["o"] else None

    def _apply_snapshot(self, conn, guild_id, snapshot: Dict[str, dict], observed_at: str):
        gid = str(guild_id)
        codes = list(snapshot.keys())
        if codes:
            placeholders = ",".join("?" for _ in codes)
            conn.execute(
                f"UPDATE invite_snapshots SET active = 0, observed_at = ? "
                f"WHERE guild_id = ? AND active = 1 AND code NOT IN ({placeholders})",
                [observed_at, gid, *codes],
            )
        else:
            conn.execute(
                "UPDATE invite_snapshots SET active = 0, observed_at = ? WHERE guild_id = ? AND active = 1",
                (observed_at, gid),
            )
        for code, info in snapshot.items():
            conn.execute(
                """
                INSERT INTO invite_snapshots
                    (guild_id, code, inviter_id, uses, max_uses, max_age, temporary,
                     is_vanity, created_at, observed_at, active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                ON CONFLICT(guild_id, code) DO UPDATE SET
                    inviter_id = excluded.inviter_id,
                    uses       = excluded.uses,
                    max_uses   = excluded.max_uses,
                    max_age    = excluded.max_age,
                    temporary  = excluded.temporary,
                    is_vanity  = excluded.is_vanity,
                    observed_at = excluded.observed_at,
                    active     = 1
                """,
                (
                    gid,
                    code,
                    _sid(info.get("inviter_id")),
                    int(info.get("uses") or 0),
                    info.get("max_uses"),
                    info.get("max_age"),
                    1 if info.get("temporary") else 0,
                    1 if info.get("is_vanity") else 0,
                    info.get("created_at"),
                    observed_at,
                ),
            )

    def replace_snapshot(self, guild_id, snapshot: Dict[str, dict], observed_at: Optional[str] = None):
        observed_at = observed_at or iso(utcnow())
        with self._tx() as conn:
            self._apply_snapshot(conn, guild_id, snapshot, observed_at)

    def upsert_invite(self, guild_id, code, info: dict):
        self.replace_snapshot(
            guild_id,
            {**self.get_snapshot(guild_id), code: {**info, "code": code}},
        )

    def mark_invite_deleted(self, guild_id, code):
        """La invitación borrada NO cuenta como 'usada': la conservamos como
        evidencia (active=0) y no tocamos los usos ya registrados."""
        self._exec(
            "UPDATE invite_snapshots SET active = 0, observed_at = ? "
            "WHERE guild_id = ? AND code = ?",
            (iso(utcnow()), str(guild_id), code),
        )

    # ── huecos de observación ────────────────────────────────────────────────
    def open_gap(self, guild_id, started_at: str, reason: str) -> int:
        cur = self._exec(
            "INSERT INTO invite_observation_gaps(guild_id, started_at, reason) VALUES(?, ?, ?)",
            (str(guild_id), started_at, reason),
        )
        return cur.lastrowid

    def close_gap(self, gap_id: int, ended_at: Optional[str] = None):
        self._exec(
            "UPDATE invite_observation_gaps SET ended_at = ? WHERE id = ?",
            (ended_at or iso(utcnow()), gap_id),
        )

    # ── estancias ────────────────────────────────────────────────────────────
    def get_active_stay(self, guild_id, member_id) -> Optional[dict]:
        row = self._one(
            "SELECT * FROM membership_stays "
            "WHERE guild_id = ? AND member_id = ? AND left_at IS NULL",
            (str(guild_id), _sid(member_id)),
        )
        return dict(row) if row else None

    def member_has_history(self, guild_id, member_id) -> bool:
        return self._one(
            "SELECT 1 FROM membership_stays WHERE guild_id = ? AND member_id = ? LIMIT 1",
            (str(guild_id), _sid(member_id)),
        ) is not None

    def list_stays(self, guild_id, member_id) -> List[dict]:
        rows = self._query(
            "SELECT * FROM membership_stays WHERE guild_id = ? AND member_id = ? "
            "ORDER BY joined_at",
            (str(guild_id), _sid(member_id)),
        )
        return [dict(r) for r in rows]

    def append_stay(self, conn, guild_id, stay: dict) -> Optional[int]:
        """Inserta una estancia activa. Devuelve None si ya había una activa
        (evento duplicado → idempotente)."""
        gid = str(guild_id)
        mid = _sid(stay["member_id"])
        if conn.execute(
            "SELECT 1 FROM membership_stays WHERE guild_id = ? AND member_id = ? AND left_at IS NULL",
            (gid, mid),
        ).fetchone():
            return None
        cur = conn.execute(
            """
            INSERT INTO membership_stays
                (guild_id, member_id, joined_at, left_at, invite_code, observed_inviter_id,
                 source_type, attribution_status, attribution_reason, eligibility_status,
                 exclusion_reasons, is_bot, account_created_at, event_id, rules_version,
                 created_at, updated_at)
            VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                gid, mid, stay["joined_at"], stay.get("invite_code"),
                _sid(stay.get("observed_inviter_id")), stay.get("source_type", "unknown"),
                stay.get("attribution_status", "unresolved"), stay.get("attribution_reason"),
                stay.get("eligibility_status", "pending"),
                json.dumps(stay.get("exclusion_reasons") or []),
                1 if stay.get("is_bot") else 0, stay.get("account_created_at"),
                stay.get("event_id"), int(stay.get("rules_version", 1)),
                stay.get("created_at") or iso(utcnow()),
                stay.get("updated_at") or iso(utcnow()),
            ),
        )
        return cur.lastrowid

    def get_stay(self, stay_id) -> Optional[dict]:
        row = self._one("SELECT * FROM membership_stays WHERE id = ?", (stay_id,))
        return dict(row) if row else None

    def commit_join_batch(self, guild_id, stays: List[dict], snapshot: Optional[dict] = None,
                          observed_at: Optional[str] = None, restore_credit_ids=()) -> List[int]:
        """Transacción única: estancias + créditos + restauración de créditos +
        nueva instantánea. Se persiste TODO antes de anunciar nada.

        Devuelve los ids de las estancias realmente insertadas (una entrada
        duplicada se ignora de forma idempotente)."""
        observed_at = observed_at or iso(utcnow())
        inserted: List[int] = []
        with self._tx() as conn:
            for stay in stays:
                stay_id = self.append_stay(conn, guild_id, stay)
                if stay_id is None:
                    continue
                inserted.append(stay_id)
                credit = stay.get("credit")
                if credit:
                    self.add_credit(
                        conn, guild_id, stay_id, stay["member_id"],
                        credit.get("inviter_id"), credit["source_type"],
                        credit.get("eligible", 0), credit.get("exclusion_reasons"),
                        credit.get("is_rejoin_restore", False),
                    )
            for credit_id in restore_credit_ids:
                self.restore_credit(conn, credit_id)
            if snapshot is not None:
                self._apply_snapshot(conn, guild_id, snapshot, observed_at)
        return inserted

    def close_active_stay(self, guild_id, member_id, left_at: str) -> Optional[int]:
        """Cierra la estancia activa y devuelve su id (None si no había ninguna →
        una salida duplicada no vuelve a descontar)."""
        with self._tx() as conn:
            row = conn.execute(
                "SELECT id FROM membership_stays "
                "WHERE guild_id = ? AND member_id = ? AND left_at IS NULL",
                (str(guild_id), _sid(member_id)),
            ).fetchone()
            if row is None:
                return None
            conn.execute(
                "UPDATE membership_stays SET left_at = ?, updated_at = ? WHERE id = ?",
                (left_at, iso(utcnow()), row["id"]),
            )
            return row["id"]

    def correct_stay_attribution(self, stay_id, inviter_id, code, reason, actor_id):
        stay = self.get_stay(stay_id)
        if stay is None:
            return False
        with self._tx() as conn:
            conn.execute(
                "UPDATE membership_stays SET observed_inviter_id = ?, invite_code = ?, "
                "source_type = 'invite', attribution_status = 'manual', "
                "attribution_reason = ?, updated_at = ? WHERE id = ?",
                (_sid(inviter_id), code, reason, iso(utcnow()), stay_id),
            )
            conn.execute(
                "UPDATE invite_credits SET inviter_id = ?, source_type = 'invite', "
                "updated_at = ? WHERE stay_id = ?",
                (_sid(inviter_id), iso(utcnow()), stay_id),
            )
        self.audit(stay["guild_id"], actor_id, "correct", str(stay_id),
                   {"inviter_id": _sid(inviter_id), "code": code, "reason": reason})
        return True

    # ── créditos ─────────────────────────────────────────────────────────────
    def add_credit(self, conn, guild_id, stay_id, member_id, inviter_id, source_type,
                   eligible, exclusion_reasons=None, is_rejoin_restore=False) -> int:
        now = iso(utcnow())
        cur = conn.execute(
            """
            INSERT INTO invite_credits
                (guild_id, stay_id, member_id, inviter_id, source_type, eligible,
                 exclusion_reasons, is_rejoin_restore, active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                str(guild_id), stay_id, _sid(member_id), _sid(inviter_id), source_type,
                1 if eligible else 0, json.dumps(exclusion_reasons or []),
                1 if is_rejoin_restore else 0, now, now,
            ),
        )
        return cur.lastrowid

    def get_credit_for_stay(self, stay_id) -> Optional[dict]:
        row = self._one("SELECT * FROM invite_credits WHERE stay_id = ?", (stay_id,))
        return dict(row) if row else None

    def last_prior_credit(self, guild_id, member_id, exclude_stay_id=None) -> Optional[dict]:
        """Último crédito elegible previo del miembro (para reingresos): el crédito
        original que hay que restaurar si vuelve."""
        row = self._one(
            "SELECT c.* FROM invite_credits c JOIN membership_stays s ON s.id = c.stay_id "
            "WHERE c.guild_id = ? AND c.member_id = ? AND c.eligible = 1 "
            "AND c.source_type = 'invite' AND c.inviter_id IS NOT NULL "
            "AND (? IS NULL OR c.stay_id != ?) "
            "ORDER BY c.id DESC LIMIT 1",
            (str(guild_id), _sid(member_id), exclude_stay_id, exclude_stay_id),
        )
        return dict(row) if row else None

    def deactivate_credit_for_stay(self, stay_id) -> bool:
        cur = self._exec(
            "UPDATE invite_credits SET active = 0, updated_at = ? WHERE stay_id = ? AND active = 1",
            (iso(utcnow()), stay_id),
        )
        return cur.rowcount > 0

    def restore_credit(self, conn, credit_id) -> int:
        conn.execute(
            "UPDATE invite_credits SET active = 1, updated_at = ? WHERE id = ?",
            (iso(utcnow()), credit_id),
        )
        return credit_id

    # ── puntuación ───────────────────────────────────────────────────────────
    def credited_counts(self, guild_id) -> Dict[str, int]:
        rows = self._query(
            "SELECT inviter_id AS uid, COUNT(*) AS n FROM invite_credits "
            "WHERE guild_id = ? AND active = 1 AND eligible = 1 AND inviter_id IS NOT NULL "
            "GROUP BY inviter_id",
            (str(guild_id),),
        )
        return {r["uid"]: r["n"] for r in rows}

    def adjustment_totals(self, guild_id) -> Dict[str, int]:
        rows = self._query(
            "SELECT user_id AS uid, COALESCE(SUM(amount), 0) AS n FROM invite_adjustments "
            "WHERE guild_id = ? GROUP BY user_id",
            (str(guild_id),),
        )
        return {r["uid"]: r["n"] for r in rows}

    def score(self, guild_id, user_id) -> int:
        uid = _sid(user_id)
        credited = self.credited_counts(guild_id).get(uid, 0)
        return credited + self.adjustment_totals(guild_id).get(uid, 0)

    def leaderboard(self, guild_id, limit: int = 100, offset: int = 0) -> List[dict]:
        counts = self.credited_counts(guild_id)
        adjustments = self.adjustment_totals(guild_id)
        uids = set(counts) | set(adjustments)
        rows = [
            {"user_id": u, "valid_present": counts.get(u, 0),
             "bonus": adjustments.get(u, 0), "score": counts.get(u, 0) + adjustments.get(u, 0)}
            for u in uids
        ]
        rows.sort(key=lambda r: (-r["score"], r["user_id"]))
        return rows[offset:offset + limit]

    def inviter_breakdown(self, guild_id, inviter_id) -> dict:
        uid = _sid(inviter_id)
        gid = str(guild_id)
        historical = self._one(
            "SELECT COUNT(*) AS n FROM membership_stays WHERE guild_id = ? "
            "AND observed_inviter_id = ? AND source_type = 'invite'",
            (gid, uid),
        )["n"]
        present = self._one(
            "SELECT COUNT(*) AS n FROM invite_credits WHERE guild_id = ? AND inviter_id = ? "
            "AND active = 1 AND eligible = 1",
            (gid, uid),
        )["n"]
        left = self._one(
            "SELECT COUNT(*) AS n FROM invite_credits WHERE guild_id = ? AND inviter_id = ? "
            "AND active = 0 AND eligible = 1",
            (gid, uid),
        )["n"]
        rejoins = self._one(
            "SELECT COUNT(*) AS n FROM invite_credits WHERE guild_id = ? AND inviter_id = ? "
            "AND is_rejoin_restore = 1 AND active = 1",
            (gid, uid),
        )["n"]
        excluded_rows = self._query(
            "SELECT exclusion_reasons FROM membership_stays WHERE guild_id = ? "
            "AND observed_inviter_id = ? AND eligibility_status = 'excluded'",
            (gid, uid),
        )
        excluded = {}
        for r in excluded_rows:
            for reason in _load_json_list(r["exclusion_reasons"]):
                excluded[reason] = excluded.get(reason, 0) + 1
        bonus = self.adjustment_totals(gid).get(uid, 0)
        return {
            "user_id": uid,
            "historical_attributed": historical,
            "valid_present": present,
            "attributed_left": left,
            "excluded": excluded,
            "rejoins": rejoins,
            "bonus": bonus,
            "score": present + bonus,
        }

    # ── ajustes y auditoría ──────────────────────────────────────────────────
    def add_adjustment(self, guild_id, user_id, amount, reason, actor_id) -> int:
        cur = self._exec(
            "INSERT INTO invite_adjustments(guild_id, user_id, amount, reason, actor_id, created_at) "
            "VALUES(?, ?, ?, ?, ?, ?)",
            (str(guild_id), _sid(user_id), int(amount), reason, _sid(actor_id), iso(utcnow())),
        )
        self.audit(guild_id, actor_id, "bonus", _sid(user_id),
                   {"amount": int(amount), "reason": reason})
        return cur.lastrowid

    def list_adjustments(self, guild_id, user_id=None) -> List[dict]:
        if user_id is not None:
            rows = self._query(
                "SELECT * FROM invite_adjustments WHERE guild_id = ? AND user_id = ? ORDER BY id",
                (str(guild_id), _sid(user_id)),
            )
        else:
            rows = self._query(
                "SELECT * FROM invite_adjustments WHERE guild_id = ? ORDER BY id", (str(guild_id),)
            )
        return [dict(r) for r in rows]

    def audit(self, guild_id, actor_id, action, target=None, details=None):
        self._exec(
            "INSERT INTO invite_audit_log(guild_id, actor_id, action, target, details, created_at) "
            "VALUES(?, ?, ?, ?, ?, ?)",
            (str(guild_id), _sid(actor_id), action, target,
             json.dumps(details or {}, ensure_ascii=False), iso(utcnow())),
        )

    def list_audit(self, guild_id, limit: int = 50) -> List[dict]:
        rows = self._query(
            "SELECT * FROM invite_audit_log WHERE guild_id = ? ORDER BY id DESC LIMIT ?",
            (str(guild_id), limit),
        )
        return [dict(r) for r in rows]

    # ── recompensas (fase 2: tabla lista, lógica aún no activa) ───────────────
    def set_reward_rule(self, guild_id, threshold, role_id):
        self._exec(
            "INSERT INTO invite_reward_rules(guild_id, threshold, role_id) VALUES(?, ?, ?) "
            "ON CONFLICT(guild_id, threshold) DO UPDATE SET role_id = excluded.role_id",
            (str(guild_id), int(threshold), _sid(role_id)),
        )

    def get_reward_rules(self, guild_id) -> List[dict]:
        rows = self._query(
            "SELECT * FROM invite_reward_rules WHERE guild_id = ? ORDER BY threshold",
            (str(guild_id),),
        )
        return [dict(r) for r in rows]

    # ── reset / export ───────────────────────────────────────────────────────
    def reset_guild(self, guild_id, scope: str):
        """Reinicio acotado por alcance. scope in {observations, credits, all}."""
        gid = str(guild_id)
        with self._tx() as conn:
            if scope in ("observations", "all"):
                conn.execute("DELETE FROM membership_stays WHERE guild_id = ?", (gid,))
                conn.execute("DELETE FROM invite_credits WHERE guild_id = ?", (gid,))
                conn.execute("DELETE FROM invite_snapshots WHERE guild_id = ?", (gid,))
                conn.execute("DELETE FROM invite_observation_gaps WHERE guild_id = ?", (gid,))
            if scope in ("credits", "all"):
                conn.execute("DELETE FROM invite_credits WHERE guild_id = ?", (gid,))
                conn.execute("DELETE FROM invite_adjustments WHERE guild_id = ?", (gid,))
            if scope == "all":
                conn.execute("DELETE FROM invite_reward_rules WHERE guild_id = ?", (gid,))
        self.audit(guild_id, None, "reset", scope)

    def export_guild(self, guild_id) -> dict:
        gid = str(guild_id)
        return {
            "guild_id": gid,
            "settings": self.get_settings(gid),
            "snapshot": self.get_snapshot(gid),
            "stays": [dict(r) for r in self._query(
                "SELECT * FROM membership_stays WHERE guild_id = ? ORDER BY id", (gid,))],
            "credits": [dict(r) for r in self._query(
                "SELECT * FROM invite_credits WHERE guild_id = ? ORDER BY id", (gid,))],
            "adjustments": self.list_adjustments(gid),
            "leaderboard": self.leaderboard(gid, limit=1000),
        }


# ── utilidades ───────────────────────────────────────────────────────────────
def _sid(value):
    """IDs de Discord como TEXT (sin pérdida de precisión); None se conserva."""
    if value is None:
        return None
    return str(value)


def _load_json_list(raw) -> List[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except (ValueError, TypeError):
        return []

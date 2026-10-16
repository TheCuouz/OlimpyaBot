"""Motor de atribución de invitaciones (agnóstico de discord.py, testeable).

Principio rector: **atribución conservadora**. Discord NO dice qué invitación usó
un miembro; solo expone los contadores de uso. Un incremento de usos es una
INFERENCIA, nunca una asociación explícita. Este módulo:

  · difunde instantáneas (snapshot) de invitaciones y calcula incrementos,
  · resuelve la atribución de un lote de entradas de forma conservadora
    (no elige el "primer código" a ciegas; declara ambiguous/unresolved),
  · aplica reglas de elegibilidad (bots, cuenta reciente, reingresos),
  · separa el ORIGEN de cada entrada de la PROPIEDAD del crédito.

El estado se guarda con `InviteStore` (utils/invites_db.py). El procesamiento por
servidor se serializa con un candado + una cola con debounce para agrupar entradas
próximas (un candado solo no basta si una consulta ya trae varios usos nuevos).
"""
import asyncio
import string
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, Iterable, List, Optional

from utils.invites_db import InviteStore, iso, utcnow

# ── vocabulario del contrato de datos ────────────────────────────────────────
VANITY_CODE = "__vanity__"

SOURCE_INVITE = "invite"
SOURCE_VANITY = "vanity"
SOURCE_UNKNOWN = "unknown"

STATUS_INFERRED = "inferred"
STATUS_AMBIGUOUS = "ambiguous"
STATUS_UNRESOLVED = "unresolved"
STATUS_MANUAL = "manual"

ELIG_VALID = "valid"
ELIG_EXCLUDED = "excluded"
ELIG_NOT_ATTRIBUTED = "not_attributed"

EXCLUDE_BOT = "bot"
EXCLUDE_RECENT = "recent_account"


# ── plantillas de mensajes ───────────────────────────────────────────────────
TEMPLATE_VARS = {
    "member", "member_name", "inviter", "invite_code", "score",
    "valid_present", "excluded", "left", "bonus", "source", "attribution_status",
}
MAX_TEMPLATE_LEN = 1500

DEFAULT_JOIN_ATTRIBUTED = (
    "👋 Bienvenido, {member}.\n"
    "Invitación atribuida a {inviter}.\n"
    "Ahora tiene {valid_present} miembros válidos presentes."
)
DEFAULT_JOIN_VANITY = (
    "👋 Bienvenido, {member}.\n"
    "Ha entrado por el enlace personalizado del servidor."
)
DEFAULT_JOIN_UNKNOWN = (
    "👋 Bienvenido, {member}.\n"
    "No se ha podido identificar con suficiente fiabilidad la invitación utilizada."
)
DEFAULT_JOIN_EXCLUDED = (
    "👋 Bienvenido, {member}.\n"
    "Entrada registrada pero excluida de la puntuación ({source})."
)
DEFAULT_LEAVE = (
    "👋 {member_name} ha salido del servidor.\n"
    "Se ha retirado su crédito activo de la puntuación del invitador."
)


def validate_template(template: str) -> str:
    """Valida variables y longitud de una plantilla configurable."""
    if not isinstance(template, str) or not template.strip():
        raise ValueError("la plantilla no puede estar vacía")
    if len(template) > MAX_TEMPLATE_LEN:
        raise ValueError(f"la plantilla supera {MAX_TEMPLATE_LEN} caracteres")
    names = {name for _, name, _, _ in string.Formatter().parse(template) if name}
    unknown = names - TEMPLATE_VARS
    if unknown:
        raise ValueError(f"variables desconocidas: {', '.join(sorted(unknown))}")
    return template


def render_template(template: str, ctx: Dict[str, object]) -> str:
    """Rellena una plantilla; una variable sin valor queda vacía (nunca rompe)."""
    safe = {k: ("" if ctx.get(k) is None else str(ctx.get(k))) for k in TEMPLATE_VARS}
    try:
        return template.format(**safe)
    except (KeyError, IndexError, ValueError):
        return template


def default_join_template(source_type: str, attribution_status: str, excluded: bool) -> str:
    if excluded:
        return DEFAULT_JOIN_EXCLUDED
    if source_type == SOURCE_VANITY:
        return DEFAULT_JOIN_VANITY
    if attribution_status == STATUS_INFERRED:
        return DEFAULT_JOIN_ATTRIBUTED
    return DEFAULT_JOIN_UNKNOWN


def _now() -> datetime:
    return utcnow()


# ── snapshots ────────────────────────────────────────────────────────────────
def invite_entry(inv) -> dict:
    """Convierte una Invite de discord.py en una entrada de snapshot (duck typing)."""
    inviter = getattr(inv, "inviter", None)
    created = getattr(inv, "created_at", None)
    return {
        "code": getattr(inv, "code", None),
        "inviter_id": str(inviter.id) if inviter is not None else None,
        "uses": int(getattr(inv, "uses", 0) or 0),
        "max_uses": getattr(inv, "max_uses", None),
        "max_age": getattr(inv, "max_age", None),
        "temporary": bool(getattr(inv, "temporary", False)),
        "is_vanity": bool(getattr(inv, "is_vanity", False)),
        "created_at": created.isoformat() if created is not None else None,
    }


def build_snapshot(invites: Iterable, vanity=None) -> Dict[str, dict]:
    snap: Dict[str, dict] = {}
    for inv in invites or []:
        entry = invite_entry(inv)
        if entry["code"]:
            snap[entry["code"]] = entry
    if vanity is not None:
        entry = invite_entry(vanity)
        entry["is_vanity"] = True
        snap[entry["code"] or VANITY_CODE] = entry
    return snap


def compute_increments(prev: Optional[Dict[str, dict]], new: Dict[str, dict]) -> dict:
    """Deltas de usos entre la instantánea previa y la nueva.

    Una invitación que aparece por primera vez se mide contra 0 usos (si se creó
    ya usada, ese uso es señal legítima). `removed` = códigos que desaparecen
    (borrados/agotados): se conservan como evidencia, NO cuentan como uso.
    """
    prev = prev or {}
    regular: Dict[str, int] = {}
    vanity_delta = 0
    for code, info in new.items():
        prev_uses = int(prev.get(code, {}).get("uses", 0) or 0)
        delta = int(info.get("uses", 0) or 0) - prev_uses
        if delta > 0:
            if info.get("is_vanity"):
                vanity_delta += delta
            else:
                regular[code] = delta
    removed = [c for c in prev if c not in new]
    return {"regular": regular, "vanity_delta": vanity_delta, "removed": removed}


# ── entrada pendiente y resolución ───────────────────────────────────────────
@dataclass
class PendingJoin:
    member_id: str
    is_bot: bool = False
    account_created_at: Optional[datetime] = None
    joined_at: Optional[datetime] = None
    event_id: Optional[str] = None
    display_name: str = ""

    @classmethod
    def from_member(cls, member) -> "PendingJoin":
        created = getattr(member, "created_at", None)
        return cls(
            member_id=str(member.id),
            is_bot=bool(getattr(member, "bot", False)),
            account_created_at=created,
            joined_at=_now(),
            display_name=getattr(member, "display_name", "") or "",
        )


@dataclass
class Resolution:
    member_id: str
    invite_code: Optional[str] = None
    observed_inviter_id: Optional[str] = None
    source_type: str = SOURCE_UNKNOWN
    attribution_status: str = STATUS_UNRESOLVED
    attribution_reason: str = ""


def resolve_attribution(prev: Optional[Dict[str, dict]], new: Dict[str, dict],
                        pending: List[PendingJoin]) -> Dict[str, Resolution]:
    """Atribuye cada entrada pendiente a un código o declara la incertidumbre.

    Reglas (conservadoras, nunca al azar):
      · baseline (prev=None)                  → unresolved/baseline
      · 1 código, +1 uso, 1 entrada           → inferred
      · 1 código, +n usos, n entradas         → inferred (lote del mismo código)
      · 1 código, nº usos ≠ nº entradas       → ambiguous
      · ≥2 códigos incrementados              → ambiguous (no se reparte a dedo)
      · solo vanity sube                      → vanity (sin invitador personal)
      · vanity + código suben a la vez        → ambiguous
      · nada sube                             → unresolved
    """
    out: Dict[str, Resolution] = {}
    n = len(pending)

    def assign(status, reason, code=None, inviter=None, source=SOURCE_UNKNOWN):
        for p in pending:
            out[p.member_id] = Resolution(
                member_id=p.member_id, invite_code=code, observed_inviter_id=inviter,
                source_type=source, attribution_status=status, attribution_reason=reason,
            )

    if prev is None:
        assign(STATUS_UNRESOLVED, "baseline")
        return out
    if n == 0:
        return out

    inc = compute_increments(prev, new)
    candidates = inc["regular"]
    vanity_delta = inc["vanity_delta"]
    total = sum(candidates.values())

    if not candidates and vanity_delta <= 0:
        assign(STATUS_UNRESOLVED, "no_increment")
        return out

    if candidates and vanity_delta > 0:
        assign(STATUS_AMBIGUOUS, "vanity_and_invite")
        return out

    if not candidates and vanity_delta > 0:
        assign(STATUS_INFERRED, "vanity_increment", source=SOURCE_VANITY)
        return out

    if len(candidates) == 1:
        code = next(iter(candidates))
        inviter = new.get(code, {}).get("inviter_id")
        if candidates[code] == n:
            reason = "single_increment" if n == 1 else "batch_same_code"
            assign(STATUS_INFERRED, reason, code=code, inviter=inviter, source=SOURCE_INVITE)
        else:
            assign(STATUS_AMBIGUOUS, "increment_mismatch")
        return out

    # Varios códigos incrementados, con o sin cuadre de conteo: no se reparte.
    if total != n:
        assign(STATUS_AMBIGUOUS, "increment_mismatch")
    else:
        assign(STATUS_AMBIGUOUS, "multiple_candidates")
    return out


# ── elegibilidad y plan de estancia ──────────────────────────────────────────
def _exclusions(p: PendingJoin, recent_days: int, now: datetime) -> List[str]:
    ex: List[str] = []
    if p.is_bot:
        ex.append(EXCLUDE_BOT)
    elif p.account_created_at is not None and recent_days > 0:
        created = p.account_created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if (now - created).total_seconds() < recent_days * 86400:
            ex.append(EXCLUDE_RECENT)
    return ex


def build_stay_plan(pending: List[PendingJoin], resolutions: Dict[str, Resolution], settings: dict,
                    now: datetime, prior_credit_for: Callable[[str], Optional[dict]],
                    is_rejoin: Callable[[str], bool]):
    """Traduce resoluciones + reglas a estancias y créditos.

    Un reingreso NO concede crédito nuevo: restaura el crédito original si era
    elegible (propietario original), conservando aparte el origen de la entrada
    actual. Cambiar de enlace no transfiere una recompensa ya ganada.
    """
    recent_days = int(settings.get("recent_account_days", 7) or 0)
    rejoin_restores = bool(settings.get("rejoin_restores", 1))
    rules_version = int(settings.get("rules_version", 1) or 1)
    stays = []
    restore_ids: List[int] = []

    for p in pending:
        r = resolutions.get(p.member_id) or Resolution(member_id=p.member_id)
        excluded = _exclusions(p, recent_days, now)
        rejoin = is_rejoin(p.member_id)
        credit = None
        restored = None

        if rejoin and rejoin_restores:
            prior = prior_credit_for(p.member_id)
            if prior is not None:
                restored = prior["id"]
                restore_ids.append(prior["id"])
                eligibility = ELIG_VALID
                reason = "rejoin_restore"
            else:
                eligibility = ELIG_NOT_ATTRIBUTED
                reason = "rejoin_no_prior_credit"
        elif rejoin:
            eligibility = ELIG_NOT_ATTRIBUTED
            reason = "rejoin_no_credit"
        elif excluded:
            eligibility = ELIG_EXCLUDED
            reason = r.attribution_reason
            if r.source_type in (SOURCE_INVITE, SOURCE_VANITY) and r.attribution_status == STATUS_INFERRED:
                credit = {
                    "inviter_id": r.observed_inviter_id if r.source_type == SOURCE_INVITE else None,
                    "source_type": r.source_type, "eligible": 0,
                    "exclusion_reasons": excluded, "is_rejoin_restore": False,
                }
        elif r.attribution_status == STATUS_INFERRED and r.source_type in (SOURCE_INVITE, SOURCE_VANITY):
            eligibility = ELIG_VALID
            reason = r.attribution_reason
            credit = {
                "inviter_id": r.observed_inviter_id if r.source_type == SOURCE_INVITE else None,
                "source_type": r.source_type, "eligible": 1,
                "exclusion_reasons": [], "is_rejoin_restore": False,
            }
        else:
            eligibility = ELIG_NOT_ATTRIBUTED
            reason = r.attribution_reason

        stays.append({
            "member_id": p.member_id,
            "joined_at": iso(p.joined_at or now),
            "invite_code": r.invite_code,
            "observed_inviter_id": r.observed_inviter_id,
            "source_type": r.source_type,
            "attribution_status": r.attribution_status,
            "attribution_reason": reason,
            "eligibility_status": eligibility,
            "exclusion_reasons": excluded,
            "is_bot": p.is_bot,
            "account_created_at": iso(p.account_created_at) if p.account_created_at else None,
            "event_id": p.event_id or f"join:{p.member_id}:{iso(p.joined_at or now)}",
            "rules_version": rules_version,
            "credit": credit,
            "restored_credit_id": restored,
        })

    return stays, restore_ids


# ── procesador serializado por servidor ──────────────────────────────────────
class InviteTracker:
    """Orquesta snapshot, cola de entradas y atribución, un servidor a la vez.

    `snapshot_provider(guild) -> dict` debe devolver la instantánea (dict) de
    invitaciones + vanity del servidor. El tracker es agnóstico de discord.py:
    solo usa `guild` para llamar al proveedor y a `guild_resolver`.
    """

    DEBOUNCE_SECONDS = 1.5

    def __init__(self, store: InviteStore, snapshot_provider,
                 guild_resolver=lambda gid: None, now: Callable[[], datetime] = _now):
        self.store = store
        self.snapshot_provider = snapshot_provider
        self.guild_resolver = guild_resolver
        self.now = now
        self.result_handler: Optional[Callable] = None
        self._locks: Dict[str, asyncio.Lock] = {}
        self._pending: Dict[str, List[PendingJoin]] = {}
        self._tasks: Dict[str, asyncio.Task] = {}

    def lock(self, guild_id) -> asyncio.Lock:
        return self._locks.setdefault(str(guild_id), asyncio.Lock())

    # ── arranque / sincronización ────────────────────────────────────────────
    async def startup_sync(self, guild):
        """Nueva línea base al arrancar: no adjudica usos anteriores. Si había una
        instantánea previa, registra la discontinuidad (hueco de observación)."""
        gid = str(guild.id)
        previous_at = self.store.get_snapshot_observed_at(gid)
        async with self.lock(gid):
            snapshot = await self.snapshot_provider(guild)
            if snapshot is None:
                if previous_at is not None:
                    self.store.open_gap(gid, previous_at, "unreadable")
                return
            gap_id = None
            if previous_at is not None:
                gap_id = self.store.open_gap(gid, previous_at, "restart")
            self.store.replace_snapshot(gid, snapshot)
            if gap_id is not None:
                self.store.close_gap(gap_id)

    async def sync_now(self, guild):
        """Refresca la instantánea sin inventar historial (mantiene pendientes)."""
        gid = str(guild.id)
        async with self.lock(gid):
            snapshot = await self.snapshot_provider(guild)
            if snapshot is None:
                return 0
            self.store.replace_snapshot(gid, snapshot)
            return len(snapshot)

    # ── invitaciones creadas / borradas (evidencia, nunca "uso") ─────────────
    async def note_invite_create(self, invite):
        gid = getattr(invite.guild, "id", None)
        if gid is None:
            return
        async with self.lock(gid):
            self.store.upsert_invite(gid, invite.code, invite_entry(invite))

    async def note_invite_delete(self, invite):
        gid = getattr(invite.guild, "id", None)
        if gid is None:
            return
        async with self.lock(gid):
            self.store.mark_invite_deleted(gid, invite.code)

    # ── entradas ─────────────────────────────────────────────────────────────
    def enqueue_join(self, member):
        gid = str(member.guild.id)
        queue = self._pending.setdefault(gid, [])
        if not any(p.member_id == str(member.id) for p in queue):
            queue.append(PendingJoin.from_member(member))

    async def note_join(self, member):
        gid = str(member.guild.id)
        self.enqueue_join(member)
        self._schedule(gid)

    def _schedule(self, guild_id):
        task = self._tasks.get(guild_id)
        if task is not None and not task.done():
            return
        self._tasks[guild_id] = asyncio.get_event_loop().create_task(self._debounced(guild_id))

    async def _debounced(self, guild_id):
        try:
            await asyncio.sleep(self.DEBOUNCE_SECONDS)
            guild = self.guild_resolver(guild_id)
            if guild is not None:
                results = await self.process_guild(guild)
                if results and self.result_handler is not None:
                    await self.result_handler(guild, results)
        except Exception as exc:  # nunca tumbar el bot por una atribución
            from utils.logger import logger
            logger.error(f"invites: fallo procesando {guild_id}: {exc}", exc_info=True)
        finally:
            self._tasks.pop(guild_id, None)
            if self._pending.get(guild_id):
                self._schedule(guild_id)

    async def process_guild(self, guild) -> List[dict]:
        """Procesa en bloque todas las entradas pendientes del servidor bajo el
        candado: una sola consulta de invitaciones, un diff, una transacción."""
        gid = str(guild.id)
        async with self.lock(gid):
            pending = self._pending.pop(gid, [])
            previous = self.store.get_snapshot(gid) or None
            # Sin instantánea previa NO se atribuye (es línea base).
            if not self.store.get_snapshot_observed_at(gid):
                previous = None
            new = await self.snapshot_provider(guild)
            if new is None:
                # No se pudieron leer las invitaciones: no se pierde el lote.
                self._pending.setdefault(gid, []).extend(pending)
                return []
            settings = self.store.ensure_settings(gid)
            now = self.now()
            resolutions = resolve_attribution(previous, new, pending) if pending else {}
            stays, restore_ids = build_stay_plan(
                pending, resolutions, settings, now,
                prior_credit_for=lambda mid: self.store.last_prior_credit(gid, mid),
                is_rejoin=lambda mid: self.store.member_has_history(gid, mid),
            )
            self.store.commit_join_batch(gid, stays, snapshot=new, observed_at=iso(now),
                                         restore_credit_ids=restore_ids)
            return [self._result(gid, stay, settings) for stay in stays]

    def _result(self, gid, stay, settings) -> dict:
        active = self.store.get_active_stay(gid, stay["member_id"])
        credit = self.store.get_credit_for_stay(active["id"]) if active else None
        owner = credit["inviter_id"] if credit else stay["observed_inviter_id"]
        score = self.store.score(gid, owner) if owner else None
        return {
            "type": "join",
            "member_id": stay["member_id"],
            "invite_code": stay["invite_code"],
            "source_type": stay["source_type"],
            "attribution_status": stay["attribution_status"],
            "attribution_reason": stay["attribution_reason"],
            "observed_inviter_id": owner,
            "eligibility_status": stay["eligibility_status"],
            "exclusion_reasons": stay["exclusion_reasons"],
            "is_bot": stay["is_bot"],
            "rejoin_restored": stay.get("restored_credit_id") is not None,
            "inviter_score": score,
        }

    # ── salidas ──────────────────────────────────────────────────────────────
    async def note_leave(self, member) -> Optional[dict]:
        gid = str(member.guild.id)
        async with self.lock(gid):
            stay_id = self.store.close_active_stay(gid, member.id, iso(self.now()))
            if stay_id is None:
                return None  # salida duplicada: no descuenta dos veces
            credit = self.store.get_credit_for_stay(stay_id)
            self.store.deactivate_credit_for_stay(stay_id)
            owner = credit["inviter_id"] if credit else None
            return {
                "type": "leave",
                "member_id": str(member.id),
                "inviter_id": owner,
                "deactivated": bool(credit and credit["active"]),
                "inviter_score": self.store.score(gid, owner) if owner else None,
            }

    async def correct_stay(self, guild, stay_id, inviter_id, code, reason, actor_id) -> bool:
        gid = str(guild.id)
        async with self.lock(gid):
            return self.store.correct_stay_attribution(
                stay_id, inviter_id, code, reason, actor_id)

    # ── diagnóstico ──────────────────────────────────────────────────────────
    def diagnose(self, guild) -> dict:
        gid = str(guild.id)
        settings = self.store.ensure_settings(gid)
        snap = self.store.get_snapshot(gid)
        return {
            "guild_id": gid,
            "enabled": bool(settings["enabled"]),
            "invites_seen": len(snap),
            "vanity": any(v.get("is_vanity") for v in snap.values()),
            "last_snapshot": self.store.get_snapshot_observed_at(gid),
            "pending_joins": len(self._pending.get(gid, [])),
            "queue_active": bool(self._tasks.get(gid) and not self._tasks[gid].done()),
            "leaderboard_size": len(self.store.leaderboard(gid, limit=10_000)),
        }

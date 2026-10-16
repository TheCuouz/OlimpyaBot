"""Sistema de invitaciones de OlimpyaBot.

Seguimiento conservador de invitaciones: detecta entradas/salidas, infiere qué
invitación se usó (sin inventar invitadores cuando la evidencia es ambigua),
guarda historial persistente, muestra estadísticas y ranking, aplica reglas
configurables (bots, cuentas recientes, reingresos), publica mensajes de entrada y
salida y permite ajustes administrativos auditados.

Diseño y decisiones: ver INVITES.md. Lógica pura: utils/invites.py. Persistencia:
utils/invites_db.py (SQLite stdlib, DATA_DIR/invites.db).
"""
import io
import json

import discord
from discord import app_commands
from discord.ext import commands

from config import (
    INVITE_ANNOUNCE_CHANNEL_ID, INVITE_RECENT_ACCOUNT_DAYS, INVITES_DB_FILE,
)
from utils.invites import (
    DEFAULT_LEAVE, ELIG_EXCLUDED, SOURCE_VANITY, STATUS_AMBIGUOUS, STATUS_INFERRED,
    STATUS_UNRESOLVED, TEMPLATE_VARS, InviteTracker, build_snapshot,
    default_join_template, render_template, validate_template,
)
from utils.invites_db import InviteStore
from utils.logger import logger

PAGE_SIZE = 10
BRAND_COLOR = 0xC879FF
MEDALS = ["🥇", "🥈", "🥉"]

EXCLUSION_LABELS = {
    "bot": "bot",
    "recent_account": "cuenta reciente",
}
ELIGIBILITY_LABELS = {
    "valid": "válida",
    "excluded": "excluida",
    "not_attributed": "sin atribuir",
}
SOURCE_LABELS = {
    "invite": "invitación",
    "vanity": "enlace personalizado (vanity)",
    "unknown": "origen no identificado",
}
STATUS_LABELS = {
    "inferred": "inferida",
    "ambiguous": "ambigua",
    "unresolved": "sin resolver",
    "manual": "corregida a mano",
}


def _mention(user_id) -> str:
    return f"<@{user_id}>" if user_id else "—"


class ConfirmReset(discord.ui.View):
    """Confirmación explícita antes de un reinicio acotado."""

    def __init__(self, author_id: int):
        super().__init__(timeout=60)
        self.author_id = author_id
        self.value = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.author_id

    @discord.ui.button(label="Confirmar", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, _):
        self.value = True
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, _):
        self.value = False
        self.stop()
        await interaction.response.defer()


class Invites(commands.Cog):
    """Cog del sistema de invitaciones."""

    invites = app_commands.Group(
        name="invites", description="Estadísticas y ranking de invitaciones")
    admin = app_commands.Group(
        name="invites-admin", description="Administración del sistema de invitaciones",
        default_permissions=discord.Permissions(administrator=True))

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.store = InviteStore(INVITES_DB_FILE)
        self.tracker = InviteTracker(
            self.store,
            snapshot_provider=self._snapshot,
            guild_resolver=lambda gid: self.bot.get_guild(int(gid)),
        )
        self.tracker.result_handler = self._announce_results
        self._bootstrapped = False

    # ── snapshot desde discord ────────────────────────────────────────────────
    async def _snapshot(self, guild):
        """Instantánea de invitaciones + vanity. None si no se pueden leer (falta
        'Gestionar servidor'): mejor no observar que observar mal."""
        try:
            invites = await guild.invites()
        except discord.Forbidden:
            logger.warning("invites: sin permiso para leer invitaciones en %s", guild.id)
            return None
        except discord.HTTPException as exc:
            logger.warning("invites: fallo de API leyendo invitaciones: %s", exc)
            return None
        vanity = None
        try:
            vanity = await guild.vanity_invite()
        except (discord.Forbidden, discord.HTTPException):
            vanity = None
        return build_snapshot(invites, vanity)

    def _settings(self, guild_id) -> dict:
        return self.store.ensure_settings(guild_id)

    def _announce_channel_id(self, settings) -> int:
        return int(settings.get("announce_channel_id") or INVITE_ANNOUNCE_CHANNEL_ID or 0)

    # ── eventos ───────────────────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_ready(self):
        if self._bootstrapped:
            return
        self._bootstrapped = True
        for guild in self.bot.guilds:
            try:
                self.store.ensure_settings(guild.id)
                await self.tracker.startup_sync(guild)
            except Exception as exc:  # nunca tumbar el bot
                logger.error("invites: fallo en el arranque de %s: %s", guild.id, exc,
                             exc_info=True)

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        try:
            self.store.ensure_settings(guild.id)
            await self.tracker.startup_sync(guild)
        except Exception as exc:
            logger.error("invites: fallo al unirse a %s: %s", guild.id, exc, exc_info=True)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        try:
            if not self._settings(member.guild.id)["enabled"]:
                return
            await self.tracker.note_join(member)
        except Exception as exc:
            logger.error("invites: fallo registrando entrada de %s: %s", member.id, exc,
                         exc_info=True)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        try:
            if not self._settings(member.guild.id)["enabled"]:
                return
            result = await self.tracker.note_leave(member)
            if result:
                await self._announce_leave(member, result)
        except Exception as exc:
            logger.error("invites: fallo registrando salida de %s: %s", member.id, exc,
                         exc_info=True)

    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        try:
            await self.tracker.note_invite_create(invite)
        except Exception as exc:
            logger.error("invites: fallo registrando creación de invitación: %s", exc)

    @commands.Cog.listener()
    async def on_invite_delete(self, invite):
        try:
            await self.tracker.note_invite_delete(invite)
        except Exception as exc:
            logger.error("invites: fallo registrando borrado de invitación: %s", exc)

    # ── mensajes de entrada / salida ──────────────────────────────────────────
    async def _announce_results(self, guild, results):
        settings = self._settings(guild.id)
        channel = guild.get_channel(self._announce_channel_id(settings))
        for res in results:
            ctx = self._template_ctx(guild, res)
            template = settings.get("join_template") or default_join_template(
                res["source_type"], res["attribution_status"], res["eligibility_status"] == ELIG_EXCLUDED)
            text = render_template(template, ctx)
            logger.info("invites: entrada %s → %s (score %s)",
                        res["member_id"], res["attribution_status"], res["inviter_score"])
            if channel is not None:
                try:
                    await channel.send(text, allowed_mentions=discord.AllowedMentions(
                        users=True, roles=False, everyone=False))
                except discord.HTTPException as exc:
                    # Un fallo al publicar NO deshace el registro ya persistido.
                    logger.error("invites: no se pudo publicar la entrada: %s", exc)

    async def _announce_leave(self, member, result):
        settings = self._settings(member.guild.id)
        channel = member.guild.get_channel(self._announce_channel_id(settings))
        if channel is None:
            return
        ctx = {
            "member": member.mention, "member_name": member.display_name,
            "inviter": _mention(result.get("inviter_id")), "score": result.get("inviter_score"),
        }
        template = settings.get("leave_template") or DEFAULT_LEAVE
        try:
            await channel.send(render_template(template, ctx),
                               allowed_mentions=discord.AllowedMentions(
                                   users=True, roles=False, everyone=False))
        except discord.HTTPException as exc:
            logger.error("invites: no se pudo publicar la salida: %s", exc)

    def _template_ctx(self, guild, res) -> dict:
        inviter_id = res.get("observed_inviter_id")
        breakdown = self.store.inviter_breakdown(guild.id, inviter_id) if inviter_id else {}
        member = guild.get_member(int(res["member_id"]))
        return {
            "member": _mention(res["member_id"]),
            "member_name": getattr(member, "display_name", res["member_id"]),
            "inviter": _mention(inviter_id),
            "invite_code": res.get("invite_code"),
            "score": res.get("inviter_score"),
            "valid_present": breakdown.get("valid_present", 0),
            "excluded": ", ".join(EXCLUSION_LABELS.get(r, r) for r in res.get("exclusion_reasons", [])),
            "source": SOURCE_LABELS.get(res["source_type"], res["source_type"]),
            "attribution_status": STATUS_LABELS.get(res["attribution_status"], res["attribution_status"]),
        }

    # ── helpers de permisos / settings ────────────────────────────────────────
    @staticmethod
    def _is_moderator(interaction: discord.Interaction) -> bool:
        perms = interaction.user.guild_permissions
        return bool(perms.administrator or perms.manage_guild)

    async def _guild_guard(self, interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            await interaction.response.send_message(
                "Este comando solo funciona dentro de un servidor.", ephemeral=True)
            return False
        return True

    # ══════════════════════════════════════════════════════════════════════════
    #  COMANDOS DE MIEMBROS
    # ══════════════════════════════════════════════════════════════════════════
    @invites.command(name="stats", description="Consulta tu puntuación de invitaciones y su desglose")
    @app_commands.describe(usuario="Consultar a otro usuario (moderadores)")
    async def stats(self, interaction: discord.Interaction, usuario: discord.Member = None):
        if not await self._guild_guard(interaction):
            return
        target = usuario or interaction.user
        if target.id != interaction.user.id and not self._is_moderator(interaction):
            await interaction.response.send_message(
                "Solo puedes consultar tus propias estadísticas.", ephemeral=True)
            return
        data = self.store.inviter_breakdown(interaction.guild.id, target.id)
        embed = discord.Embed(title=f"🌸 Invitaciones de {target.display_name}", color=BRAND_COLOR)
        embed.add_field(name="Puntuación", value=str(data["score"]), inline=True)
        embed.add_field(name="Válidos presentes", value=str(data["valid_present"]), inline=True)
        embed.add_field(name="Atribuidas (histórico)", value=str(data["historical_attributed"]), inline=True)
        embed.add_field(name="Salidos", value=str(data["attributed_left"]), inline=True)
        embed.add_field(name="Reingresos", value=str(data["rejoins"]), inline=True)
        embed.add_field(name="Bonus / ajustes", value=str(data["bonus"]), inline=True)
        if data["excluded"]:
            excluded = "\n".join(
                f"{EXCLUSION_LABELS.get(k, k)}: {v}" for k, v in data["excluded"].items())
            embed.add_field(name="Excluidas", value=excluded, inline=False)
        embed.set_footer(text="Puntuación = miembros válidos presentes atribuidos + ajustes manuales")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @invites.command(name="leaderboard", description="Ranking de invitaciones del servidor")
    @app_commands.describe(pagina="Página del ranking (1 = primera)")
    async def leaderboard(self, interaction: discord.Interaction, pagina: int = 1):
        if not await self._guild_guard(interaction):
            return
        pagina = max(1, pagina)
        rows = self.store.leaderboard(interaction.guild.id, limit=PAGE_SIZE + 1,
                                      offset=(pagina - 1) * PAGE_SIZE)
        has_next = len(rows) > PAGE_SIZE
        rows = rows[:PAGE_SIZE]
        visible = [r for r in rows if interaction.guild.get_member(int(r["user_id"]))]
        embed = discord.Embed(title="🌸 Ranking de invitaciones", color=BRAND_COLOR)
        if not visible:
            embed.description = "Aún no hay datos en esta página."
        lines = []
        for i, row in enumerate(visible):
            pos = (pagina - 1) * PAGE_SIZE + i + 1
            medal = MEDALS[i] if pagina == 1 and i < len(MEDALS) else f"`#{pos}`"
            lines.append(f"{medal} {_mention(row['user_id'])} — **{row['score']}** "
                         f"(válidos {row['valid_present']}, bonus {row['bonus']})")
        embed.description = "\n".join(lines) if lines else embed.description
        embed.set_footer(text=f"Página {pagina}" + (" · hay más" if has_next else ""))
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @invites.command(name="invited", description="Miembros atribuidos a un usuario")
    @app_commands.describe(usuario="De quién ver los invitados", pagina="Página")
    async def invited(self, interaction: discord.Interaction, usuario: discord.Member = None,
                      pagina: int = 1):
        if not await self._guild_guard(interaction):
            return
        target = usuario or interaction.user
        visibility = self._settings(interaction.guild.id)["leaderboard_visibility"]
        if target.id != interaction.user.id and not self._is_moderator(interaction) \
                and visibility != "public":
            await interaction.response.send_message(
                "La lista de invitados es privada. Solo tú o los moderadores pueden verla.",
                ephemeral=True)
            return
        stays = self.store._query(
            "SELECT * FROM membership_stays WHERE guild_id = ? AND observed_inviter_id = ? "
            "ORDER BY joined_at DESC", (str(interaction.guild.id), str(target.id)))
        joined = [dict(s) for s in stays]
        pagina = max(1, pagina)
        page_items = joined[(pagina - 1) * PAGE_SIZE: pagina * PAGE_SIZE]
        embed = discord.Embed(title=f"🌸 Invitados por {target.display_name}", color=BRAND_COLOR)
        if not page_items:
            embed.description = "Sin miembros atribuidos en esta página."
        for s in page_items:
            member = interaction.guild.get_member(int(s["member_id"]))
            who = member.mention if member else f"`{s['member_id']}` (fuera)"
            state = "presente" if s["left_at"] is None and member else "salió"
            embed.add_field(
                name=f"{who} · {state}",
                value=f"origen: {SOURCE_LABELS.get(s['source_type'], s['source_type'])} · "
                      f"{STATUS_LABELS.get(s['attribution_status'], s['attribution_status'])}",
                inline=False)
        embed.set_footer(text=f"Página {pagina} · visible: {visibility}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @invites.command(name="help", description="Cómo funciona el sistema de invitaciones")
    async def help_cmd(self, interaction: discord.Interaction):
        embed = discord.Embed(title="🌸 Sistema de invitaciones — ayuda", color=BRAND_COLOR)
        embed.description = (
            "Seguimos quién invita a quién comparando los contadores de las invitaciones "
            "del servidor. Es una **inferencia**, no una certeza: cuando la evidencia no "
            "basta marcamos la entrada como ambigua o desconocida en lugar de inventar un "
            "invitador.")
        embed.add_field(
            name="Puntuación",
            value="miembros válidos presentes atribuidos + ajustes manuales.\n"
                  "- Un miembro = un crédito activo.\n"
                  "- Si sale, se retira ese crédito (una vez).\n"
                  "- Bots y cuentas recientes entran al registro pero no puntúan.",
            inline=False)
        embed.add_field(
            name="Reingresos",
            value="Quien vuelve no genera un crédito nuevo: se restaura el crédito original "
                  "si era válido. Cambiar de enlace no transfiere una recompensa ya ganada.",
            inline=False)
        embed.add_field(
            name="Limitaciones",
            value="No detectamos multicuentas por IP o dispositivo. Durante una parada del "
                  "bot no podemos reconstruir con certeza quién entró: se abre una nueva "
                  "línea base y se registra la discontinuidad.",
            inline=False)
        embed.add_field(
            name="Comandos",
            value="`/invites stats` · `/invites leaderboard` · `/invites invited` · `/invites help`",
            inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ══════════════════════════════════════════════════════════════════════════
    #  COMANDOS DE ADMINISTRACIÓN
    # ══════════════════════════════════════════════════════════════════════════
    @admin.command(name="setup", description="Configuración inicial del módulo de invitaciones")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(canal="Canal para los mensajes de entrada/salida (opcional)")
    async def admin_setup(self, interaction: discord.Interaction, canal: discord.TextChannel = None):
        if not await self._guild_guard(interaction):
            return
        settings = self.store.ensure_settings(interaction.guild.id)
        fields = {"enabled": 1, "recent_account_days": settings["recent_account_days"] or INVITE_RECENT_ACCOUNT_DAYS}
        if canal is not None:
            fields["announce_channel_id"] = str(canal.id)
        settings = self.store.update_settings(interaction.guild.id, **fields)
        self.store.audit(interaction.guild.id, interaction.user.id, "setup", None, fields)
        snap = await self._snapshot(interaction.guild)
        embed = discord.Embed(title="✅ Módulo de invitaciones listo", color=BRAND_COLOR)
        embed.add_field(name="Estado", value="activado", inline=True)
        embed.add_field(name="Canal de avisos", value=canal.mention if canal else "—", inline=True)
        embed.add_field(name="Cuenta reciente", value=f"{settings['recent_account_days']} días", inline=True)
        embed.add_field(name="Invitaciones leídas", value=str(len(snap or {})), inline=True)
        embed.add_field(
            name="Requiere",
            value="intents GUILDS + GUILD_MEMBERS + GUILD_INVITES (privilegiado) y el permiso "
                  "**Gestionar servidor** para leer invitaciones; **Gestionar canales** para "
                  "recibir eventos de invitación.",
            inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @admin.command(name="config", description="Consulta o cambia las reglas del módulo")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        activado="Activar/desactivar el módulo",
        cuenta_reciente_dias="Días mínimos de antigüedad de cuenta para puntuar",
        canal_avisos="Canal de mensajes de entrada/salida",
        restaurar_reingreso="Restaurar el crédito original en reingresos",
        visible="Visibilidad de la lista de invitados",
        plantilla_entrada="Plantilla del mensaje de entrada",
        plantilla_salida="Plantilla del mensaje de salida")
    @app_commands.choices(visible=[
        app_commands.Choice(name="privada (solo tú/mods)", value="self"),
        app_commands.Choice(name="pública", value="public"),
    ])
    async def admin_config(self, interaction: discord.Interaction, activado: bool = None,
                           cuenta_reciente_dias: int = None, canal_avisos: discord.TextChannel = None,
                           restaurar_reingreso: bool = None, visible: app_commands.Choice[str] = None,
                           plantilla_entrada: str = None, plantilla_salida: str = None):
        if not await self._guild_guard(interaction):
            return
        fields = {}
        try:
            if activado is not None:
                fields["enabled"] = 1 if activado else 0
            if cuenta_reciente_dias is not None:
                if cuenta_reciente_dias < 0:
                    raise ValueError("los días no pueden ser negativos")
                fields["recent_account_days"] = cuenta_reciente_dias
            if canal_avisos is not None:
                fields["announce_channel_id"] = str(canal_avisos.id)
            if restaurar_reingreso is not None:
                fields["rejoin_restores"] = 1 if restaurar_reingreso else 0
            if visible is not None:
                fields["leaderboard_visibility"] = visible.value
            if plantilla_entrada is not None:
                fields["join_template"] = validate_template(plantilla_entrada)
            if plantilla_salida is not None:
                fields["leave_template"] = validate_template(plantilla_salida)
        except ValueError as exc:
            await interaction.response.send_message(f"❌ {exc}", ephemeral=True)
            return
        if fields:
            fields["rules_version"] = (self.store.ensure_settings(interaction.guild.id)["rules_version"] or 1) + 1
            settings = self.store.update_settings(interaction.guild.id, **fields)
            self.store.audit(interaction.guild.id, interaction.user.id, "config", None, fields)
            note = ("⚠️ Las reglas nuevas solo afectan a las entradas futuras; el historial "
                    "no se recalcula solo.")
        else:
            settings = self.store.ensure_settings(interaction.guild.id)
            note = "Configuración actual (no has cambiado nada)."
        embed = discord.Embed(title="⚙️ Configuración de invitaciones", color=BRAND_COLOR)
        embed.add_field(name="Activo", value="sí" if settings["enabled"] else "no", inline=True)
        embed.add_field(name="Reglas v.", value=str(settings["rules_version"]), inline=True)
        embed.add_field(name="Cuenta reciente", value=f"{settings['recent_account_days']} días", inline=True)
        embed.add_field(name="Restaurar reingreso", value="sí" if settings["rejoin_restores"] else "no", inline=True)
        embed.add_field(name="Canal avisos", value=f"<#{settings['announce_channel_id']}>" if settings["announce_channel_id"] else "—", inline=True)
        embed.add_field(name="Visibilidad", value=settings["leaderboard_visibility"], inline=True)
        embed.add_field(name="Variables", value=", ".join(f"`{{{v}}}`" for v in sorted(TEMPLATE_VARS)), inline=False)
        embed.set_footer(text=note)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @admin.command(name="bonus", description="Aplica un ajuste firmado (+/-) a la puntuación de un usuario")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(usuario="A quién ajustar", cantidad="Positivo o negativo (≠ 0)",
                           motivo="Motivo (queda auditado)")
    async def admin_bonus(self, interaction: discord.Interaction, usuario: discord.User,
                          cantidad: int, motivo: str):
        if not await self._guild_guard(interaction):
            return
        if cantidad == 0:
            await interaction.response.send_message("❌ La cantidad no puede ser 0.", ephemeral=True)
            return
        self.store.add_adjustment(interaction.guild.id, usuario.id, cantidad, motivo, interaction.user.id)
        total = self.store.score(interaction.guild.id, usuario.id)
        await interaction.response.send_message(
            f"✅ Ajuste de {cantidad:+d} a {usuario.mention}. Puntuación total: **{total}**.",
            ephemeral=True)

    @admin.command(name="inspect", description="Consulta evidencia y estancias de un usuario")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(usuario="Usuario a inspeccionar")
    async def admin_inspect(self, interaction: discord.Interaction, usuario: discord.User):
        if not await self._guild_guard(interaction):
            return
        stays = self.store.list_stays(interaction.guild.id, usuario.id)
        embed = discord.Embed(title=f"🔎 Evidencia de {usuario}", color=BRAND_COLOR)
        if not stays:
            embed.description = "Sin estancias registradas."
        for s in stays[-15:]:
            left = s["left_at"][:19].replace("T", " ") if s["left_at"] else "presente"
            embed.add_field(
                name=f"#{s['id']} · {s['joined_at'][:19].replace('T', ' ')} → {left}",
                value=(f"origen: {SOURCE_LABELS.get(s['source_type'], s['source_type'])} · "
                       f"{STATUS_LABELS.get(s['attribution_status'], s['attribution_status'])} "
                       f"({s['attribution_reason']})\n"
                       f"invitador: {_mention(s['observed_inviter_id'])} · "
                       f"elegibilidad: {ELIGIBILITY_LABELS.get(s['eligibility_status'], s['eligibility_status'])}"),
                inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @admin.command(name="correct", description="Corrige la atribución de una estancia (queda auditado)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(estancia="ID de estancia (ver /invites-admin inspect)", invitador="Invitador correcto",
                           motivo="Motivo de la corrección")
    async def admin_correct(self, interaction: discord.Interaction, estancia: int,
                            invitador: discord.Member, motivo: str):
        if not await self._guild_guard(interaction):
            return
        ok = await self.tracker.correct_stay(interaction.guild, estancia, invitador.id,
                                             None, motivo, interaction.user.id)
        if ok:
            await interaction.response.send_message(
                f"✅ Estancia #{estancia} corregida → {invitador.mention}.", ephemeral=True)
        else:
            await interaction.response.send_message(
                f"❌ No existe la estancia #{estancia} en este servidor.", ephemeral=True)

    @admin.command(name="sync", description="Refresca la instantánea de invitaciones sin inventar historial")
    @app_commands.default_permissions(administrator=True)
    async def admin_sync(self, interaction: discord.Interaction):
        if not await self._guild_guard(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        count = await self.tracker.sync_now(interaction.guild)
        await interaction.followup.send(
            f"✅ Instantánea actualizada: {count} invitaciones observadas.", ephemeral=True)

    @admin.command(name="diagnose", description="Comprueba intents, permisos y estado del módulo")
    @app_commands.default_permissions(administrator=True)
    async def admin_diagnose(self, interaction: discord.Interaction):
        if not await self._guild_guard(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        intents = self.bot.intents
        me = interaction.guild.me
        perms = me.guild_permissions
        diag = self.tracker.diagnose(interaction.guild)
        snap = await self._snapshot(interaction.guild)

        def tick(ok):
            return "✅" if ok else "❌"

        embed = discord.Embed(title="🩺 Diagnóstico de invitaciones", color=BRAND_COLOR)
        embed.add_field(name="Intent GUILDS", value=tick(intents.guilds), inline=True)
        embed.add_field(name="Intent GUILD_MEMBERS", value=tick(intents.members), inline=True)
        embed.add_field(name="Intent GUILD_INVITES", value=tick(intents.invites), inline=True)
        embed.add_field(name="Gestionar servidor", value=tick(perms.manage_guild), inline=True)
        embed.add_field(name="Gestionar canales", value=tick(perms.manage_channels), inline=True)
        embed.add_field(name="Leer invitaciones", value=tick(snap is not None), inline=True)
        embed.add_field(name="Invitaciones observadas", value=str(len(snap or {})), inline=True)
        embed.add_field(name="Vanity detectada", value=tick(diag["vanity"]), inline=True)
        embed.add_field(name="Última instantánea", value=diag["last_snapshot"] or "—", inline=True)
        embed.add_field(name="Entradas en cola", value=str(diag["pending_joins"]), inline=True)
        embed.add_field(name="Usuarios en ranking", value=str(diag["leaderboard_size"]), inline=True)
        if not intents.members:
            embed.set_footer(text="Falta el intent privilegiado GUILD_MEMBERS (Developer Portal).")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @admin.command(name="export", description="Exporta las estadísticas del módulo a JSON")
    @app_commands.default_permissions(administrator=True)
    async def admin_export(self, interaction: discord.Interaction):
        if not await self._guild_guard(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        data = self.store.export_guild(interaction.guild.id)
        self.store.audit(interaction.guild.id, interaction.user.id, "export", None)
        payload = json.dumps(data, indent=2, ensure_ascii=False)
        file = discord.File(io.BytesIO(payload.encode("utf-8")),
                            filename=f"invites-{interaction.guild.id}.json")
        await interaction.followup.send("📤 Exportación lista.", file=file, ephemeral=True)

    @admin.command(name="reset", description="Reinicia los datos del módulo (con confirmación)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(alcance="Qué reiniciar")
    @app_commands.choices(alcance=[
        app_commands.Choice(name="observaciones (estancias + instantáneas)", value="observations"),
        app_commands.Choice(name="créditos y ajustes", value="credits"),
        app_commands.Choice(name="todo", value="all"),
    ])
    async def admin_reset(self, interaction: discord.Interaction, alcance: app_commands.Choice[str]):
        if not await self._guild_guard(interaction):
            return
        view = ConfirmReset(interaction.user.id)
        await interaction.response.send_message(
            f"⚠️ Vas a reiniciar **{alcance.name}**. Es irreversible. ¿Confirmas?",
            view=view, ephemeral=True)
        await view.wait()
        if view.value:
            self.store.reset_guild(interaction.guild.id, alcance.value)
            await interaction.followup.send(
                f"🗑️ Reiniciado: {alcance.name}. Se abrirá una nueva línea base en la próxima "
                f"instantánea.", ephemeral=True)
        elif view.value is False:
            await interaction.followup.send("Cancelado.", ephemeral=True)

    def cog_unload(self):
        try:
            self.store.close()
        except Exception:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(Invites(bot))
    logger.info("InvitesCog loaded")

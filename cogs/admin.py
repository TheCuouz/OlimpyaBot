"""Admin commands cog for moderation and server management."""

import discord
from discord import app_commands
from discord.ext import commands
from utils.logger import logger


class AdminCog(commands.Cog):
    """Comandos de administración del servidor."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _send_error(self, interaction: discord.Interaction, error: str):
        await interaction.response.send_message(f"❌ {error}", ephemeral=True)
        logger.warning(f"Admin error: {error}")

    async def _send_success(self, interaction: discord.Interaction, message: str):
        await interaction.response.send_message(f"✅ {message}", ephemeral=True)

    # ── PURGE ──────────────────────────────────────────────────────────────────
    @app_commands.command(name="purge", description="Elimina un número de mensajes del canal")
    @app_commands.describe(cantidad="Número de mensajes a eliminar (1-100)")
    @app_commands.default_permissions(administrator=True)
    async def purge(self, interaction: discord.Interaction, cantidad: int):
        if cantidad < 1 or cantidad > 100:
            await self._send_error(interaction, "La cantidad debe estar entre 1 y 100")
            return
        await interaction.response.defer(ephemeral=True)
        try:
            deleted = await interaction.channel.purge(limit=cantidad)
            await interaction.followup.send(f"✅ Eliminados {len(deleted)} mensajes", ephemeral=True)
            logger.info(f"Purge {len(deleted)} mensajes por {interaction.user}")
        except Exception as e:
            await interaction.followup.send(f"❌ {str(e)}", ephemeral=True)

    # ── NUKE ───────────────────────────────────────────────────────────────────
    @app_commands.command(name="nuke", description="Vacía el canal por completo clonándolo y eliminando el original")
    @app_commands.default_permissions(administrator=True)
    async def nuke(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        canal = interaction.channel
        try:
            nuevo = await canal.clone(reason=f"Nuke por {interaction.user}")
            await nuevo.move(beginning=True, offset=canal.position)
            await canal.delete(reason=f"Nuke por {interaction.user}")
            await nuevo.send("💥 Canal limpiado.", delete_after=5)
            logger.info(f"Nuke canal #{canal.name} por {interaction.user}")
        except Exception as e:
            await interaction.followup.send(f"❌ {str(e)}", ephemeral=True)

    # ── KICK ───────────────────────────────────────────────────────────────────
    @app_commands.command(name="kick", description="Expulsa a un usuario del servidor")
    @app_commands.describe(usuario="Usuario a expulsar", razon="Motivo de la expulsión")
    @app_commands.default_permissions(administrator=True)
    async def kick(self, interaction: discord.Interaction, usuario: discord.Member, razon: str = "Sin motivo"):
        try:
            await interaction.guild.kick(usuario, reason=razon)
            await self._send_success(interaction, f"{usuario.mention} expulsado — {razon}")
            logger.info(f"Kick {usuario} por {interaction.user}: {razon}")
        except Exception as e:
            await self._send_error(interaction, str(e))

    # ── BAN ────────────────────────────────────────────────────────────────────
    @app_commands.command(name="ban", description="Banea a un usuario del servidor")
    @app_commands.describe(usuario="Usuario a banear", razon="Motivo del ban")
    @app_commands.default_permissions(administrator=True)
    async def ban(self, interaction: discord.Interaction, usuario: discord.Member, razon: str = "Sin motivo"):
        try:
            await interaction.guild.ban(usuario, reason=razon)
            await self._send_success(interaction, f"{usuario.mention} baneado — {razon}")
            logger.info(f"Ban {usuario} por {interaction.user}: {razon}")
        except Exception as e:
            await self._send_error(interaction, str(e))

    # ── SOFTBAN ────────────────────────────────────────────────────────────────
    @app_commands.command(name="softban", description="Banea y desbanea a un usuario eliminando sus mensajes recientes")
    @app_commands.describe(usuario="Usuario a softbanear", razon="Motivo")
    @app_commands.default_permissions(administrator=True)
    async def softban(self, interaction: discord.Interaction, usuario: discord.Member, razon: str = "Sin motivo"):
        try:
            await interaction.guild.ban(usuario, delete_message_days=7, reason=razon)
            await interaction.guild.unban(usuario, reason="Softban")
            await self._send_success(interaction, f"{usuario.mention} softbaneado — {razon}")
            logger.info(f"Softban {usuario} por {interaction.user}")
        except Exception as e:
            await self._send_error(interaction, str(e))

    # ── MUTE ───────────────────────────────────────────────────────────────────
    @app_commands.command(name="mute", description="Silencia a un usuario durante un tiempo (ej: 10m, 2h, 1d)")
    @app_commands.describe(usuario="Usuario a silenciar", duracion="Duración: 10m, 2h, 1d...")
    @app_commands.default_permissions(administrator=True)
    async def mute(self, interaction: discord.Interaction, usuario: discord.Member, duracion: str):
        import re
        from datetime import timedelta
        match = re.match(r"(\d+)([hmd])", duracion.lower())
        if not match:
            await self._send_error(interaction, "Formato incorrecto. Usa: 10m, 2h, 1d")
            return
        try:
            amount, unit = match.groups()
            segundos = int(amount) * (3600 if unit == "h" else 60 if unit == "m" else 86400)
            await usuario.timeout(timedelta(seconds=segundos), reason=f"Mute por {interaction.user}")
            await self._send_success(interaction, f"{usuario.mention} silenciado por {duracion}")
            logger.info(f"Mute {usuario} {duracion} por {interaction.user}")
        except Exception as e:
            await self._send_error(interaction, str(e))

    # ── WARN ───────────────────────────────────────────────────────────────────
    @app_commands.command(name="warn", description="Advierte a un usuario con un motivo")
    @app_commands.describe(usuario="Usuario a advertir", motivo="Motivo de la advertencia")
    @app_commands.default_permissions(administrator=True)
    async def warn(self, interaction: discord.Interaction, usuario: discord.Member, motivo: str):
        try:
            await self._send_success(interaction, f"{usuario.mention} advertido: {motivo}")
            logger.warning(f"Warn {usuario}: {motivo} por {interaction.user}")
        except Exception as e:
            await self._send_error(interaction, str(e))

    # ── CLEAR (por tipo) ───────────────────────────────────────────────────────
    @app_commands.command(name="clear", description="Elimina mensajes del canal según su tipo")
    @app_commands.describe(tipo="Tipo de mensajes: embeds, archivos, links, menciones")
    @app_commands.default_permissions(administrator=True)
    async def clear(self, interaction: discord.Interaction, tipo: str):
        opciones = ["embeds", "archivos", "links", "menciones"]
        if tipo not in opciones:
            await self._send_error(interaction, f"Tipo inválido. Opciones: {', '.join(opciones)}")
            return
        await interaction.response.defer(ephemeral=True)
        try:
            count = 0
            async for msg in interaction.channel.history(limit=100):
                borrar = False
                if tipo == "embeds" and msg.embeds:
                    borrar = True
                elif tipo == "archivos" and msg.attachments:
                    borrar = True
                elif tipo == "links" and "http" in msg.content:
                    borrar = True
                elif tipo == "menciones" and msg.mentions:
                    borrar = True
                if borrar:
                    await msg.delete()
                    count += 1
            await interaction.followup.send(f"✅ Eliminados {count} mensajes de tipo '{tipo}'", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ {str(e)}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
    logger.info("AdminCog loaded")

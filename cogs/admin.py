"""Admin commands cog for moderation and server management."""

import discord
from discord import app_commands
from discord.ext import commands
from utils.logger import logger


class AdminCog(commands.Cog):
    """Admin commands for server management."""

    def __init__(self, bot: commands.Bot):
        """Initialize the admin cog."""
        self.bot = bot

    def _is_admin(self, interaction: discord.Interaction) -> bool:
        return interaction.user.guild_permissions.administrator

    async def _send_error(self, interaction: discord.Interaction, error: str):
        await interaction.response.send_message(f"❌ {error}", ephemeral=True)
        logger.warning(f"Admin error: {error}")

    async def _send_success(self, interaction: discord.Interaction, message: str):
        await interaction.response.send_message(f"✅ {message}", ephemeral=True)

    @commands.command(name="ping")
    @commands.is_owner()
    async def ping(self, ctx: commands.Context):
        """Check bot latency."""
        latency = round(self.bot.latency * 1000)
        await ctx.send(f"Pong! {latency}ms")
        logger.info(f"Ping command executed by {ctx.author}")

    @app_commands.command(name="purge")
    @app_commands.describe(count="Number of messages to delete (1-100)")
    async def purge(self, interaction: discord.Interaction, count: int):
        if not self._is_admin(interaction):
            await self._send_error(interaction, "No tienes permisos")
            return
        if count < 1 or count > 100:
            await self._send_error(interaction, "Cuenta debe ser 1-100")
            return
        await interaction.response.defer(ephemeral=True)
        try:
            deleted = await interaction.channel.purge(limit=count)
            await interaction.followup.send(f"✅ Eliminados {len(deleted)} mensajes")
            logger.info(f"Purge {len(deleted)} by {interaction.user}")
        except Exception as e:
            await interaction.followup.send(f"❌ {str(e)}", ephemeral=True)

    @app_commands.command(name="kick")
    async def kick(self, interaction: discord.Interaction, user: discord.User):
        if not self._is_admin(interaction):
            await self._send_error(interaction, "No tienes permisos")
            return
        try:
            await interaction.guild.kick(user)
            await self._send_success(interaction, f"{user.mention} expulsado")
            logger.info(f"Kick {user} by {interaction.user}")
        except Exception as e:
            await self._send_error(interaction, str(e))

    @app_commands.command(name="ban")
    async def ban(self, interaction: discord.Interaction, user: discord.User):
        if not self._is_admin(interaction):
            await self._send_error(interaction, "No tienes permisos")
            return
        try:
            await interaction.guild.ban(user)
            await self._send_success(interaction, f"{user.mention} baneado")
            logger.info(f"Ban {user} by {interaction.user}")
        except Exception as e:
            await self._send_error(interaction, str(e))

    @app_commands.command(name="softban")
    async def softban(self, interaction: discord.Interaction, user: discord.User):
        if not self._is_admin(interaction):
            await self._send_error(interaction, "No tienes permisos")
            return
        try:
            await interaction.guild.ban(user, delete_message_days=7)
            await interaction.guild.unban(user)
            await self._send_success(interaction, f"{user.mention} softbaneado")
            logger.info(f"Softban {user} by {interaction.user}")
        except Exception as e:
            await self._send_error(interaction, str(e))

    @app_commands.command(name="mute")
    async def mute(self, interaction: discord.Interaction, user: discord.User, duration: str):
        if not self._is_admin(interaction):
            await self._send_error(interaction, "No tienes permisos")
            return
        try:
            import re
            match = re.match(r"(\d+)([hmd])", duration.lower())
            if not match:
                await self._send_error(interaction, "Formato: 1h, 30m, 7d")
                return
            amount, unit = match.groups()
            from datetime import timedelta
            seconds = int(amount) * (3600 if unit == "h" else 60 if unit == "m" else 86400)
            member = await interaction.guild.fetch_member(user.id)
            await member.timeout(timedelta(seconds=seconds))
            await self._send_success(interaction, f"{user.mention} muteado por {duration}")
            logger.info(f"Mute {user} {duration} by {interaction.user}")
        except Exception as e:
            await self._send_error(interaction, str(e))

    @app_commands.command(name="warn")
    async def warn(self, interaction: discord.Interaction, user: discord.User, reason: str):
        if not self._is_admin(interaction):
            await self._send_error(interaction, "No tienes permisos")
            return
        try:
            await self._send_success(interaction, f"{user.mention} advertido: {reason}")
            logger.warning(f"Warn {user}: {reason} by {interaction.user}")
        except Exception as e:
            await self._send_error(interaction, str(e))

    @app_commands.command(name="clear")
    async def clear(self, interaction: discord.Interaction, type: str):
        if not self._is_admin(interaction):
            await self._send_error(interaction, "No tienes permisos")
            return
        if type not in ["embeds", "files", "links", "mentions"]:
            await self._send_error(interaction, "Tipo: embeds, files, links, mentions")
            return
        await interaction.response.defer(ephemeral=True)
        try:
            count = 0
            async for msg in interaction.channel.history(limit=100):
                should_del = False
                if type == "embeds" and msg.embeds:
                    should_del = True
                elif type == "files" and msg.attachments:
                    should_del = True
                elif type == "links" and ("http" in msg.content):
                    should_del = True
                elif type == "mentions" and msg.mentions:
                    should_del = True
                if should_del:
                    await msg.delete()
                    count += 1
            await interaction.followup.send(f"✅ Eliminados {count} mensajes")
        except Exception as e:
            await interaction.followup.send(f"❌ {str(e)}")


async def setup(bot: commands.Bot):
    """Load the admin cog."""
    await bot.add_cog(AdminCog(bot))
    logger.info("AdminCog loaded")

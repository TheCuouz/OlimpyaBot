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


async def setup(bot: commands.Bot):
    """Load the admin cog."""
    await bot.add_cog(AdminCog(bot))
    logger.info("AdminCog loaded")

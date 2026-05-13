"""Admin commands cog for moderation and server management."""

import discord
from discord.ext import commands
from utils.logger import logger


class AdminCog(commands.Cog):
    """Admin commands for server management."""

    def __init__(self, bot: commands.Bot):
        """Initialize the admin cog."""
        self.bot = bot

    @commands.command(name="ping")
    @commands.is_owner()
    async def ping(self, ctx: commands.Context):
        """Check bot latency."""
        latency = round(self.bot.latency * 1000)
        await ctx.send(f"Pong! {latency}ms")
        logger.info(f"Ping command executed by {ctx.author}")


async def setup(bot: commands.Bot):
    """Load the admin cog."""
    await bot.add_cog(AdminCog(bot))
    logger.info("AdminCog loaded")

"""Embed builder cog for creating custom Discord embeds."""

import discord
from discord.ext import commands
from utils.logger import logger
from utils.embed_utils import create_embed, validate_embed, create_error_embed


class EmbedBuilderCog(commands.Cog):
    """Cog for building and managing custom embeds."""

    def __init__(self, bot: commands.Bot):
        """Initialize the embed builder cog."""
        self.bot = bot

    @commands.command(name="create_embed")
    @commands.is_owner()
    async def create_embed_command(self, ctx: commands.Context, title: str, *, description: str):
        """Create a custom embed."""
        # TODO: Implement embed creation logic
        await ctx.send("Embed creation not yet implemented")
        logger.info(f"Embed creation requested by {ctx.author}")

    @commands.command(name="list_colors")
    async def list_colors(self, ctx: commands.Context):
        """List available embed colors."""
        from config import EMBED_CONFIG
        
        colors = EMBED_CONFIG["colors"]
        color_list = ", ".join(colors.keys())
        
        embed = create_embed(
            title="Available Colors",
            description=f"Colors: {color_list}",
            color="azul"
        )
        
        await ctx.send(embed=embed)
        logger.info(f"Color list requested by {ctx.author}")


async def setup(bot: commands.Bot):
    """Load the embed builder cog."""
    await bot.add_cog(EmbedBuilderCog(bot))
    logger.info("EmbedBuilderCog loaded")

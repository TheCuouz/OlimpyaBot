import discord
from discord.ext import commands
from utils.logger import logger


class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info(f"El bot está listo y online como {self.bot.user}")
        logger.info(f"Conectado a {len(self.bot.guilds)} servidor(es)")
        await self.bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching, name="a los usuarios"
            )
        )

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        logger.info(f"Bot unido al servidor: {guild.name} (ID: {guild.id})")

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        logger.info(f"Bot removido del servidor: {guild.name} (ID: {guild.id})")


async def setup(bot):
    await bot.add_cog(Events(bot))

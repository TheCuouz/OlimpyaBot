import discord
from discord.ext import commands
from utils.logger import logger
from config import AUTOROLE_ID


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

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Asigna el rol de autorol (config.AUTOROLE_ID) a cada nuevo miembro."""
        logger.info(f"Nuevo miembro: {member} ({member.id}) en {member.guild.name}")
        if member.bot or not AUTOROLE_ID:
            return
        role = member.guild.get_role(AUTOROLE_ID)
        if role is None:
            logger.warning(
                f"Autorol: rol {AUTOROLE_ID} no existe en {member.guild.name}"
            )
            return
        try:
            await member.add_roles(role, reason="Autorol al entrar")
            logger.info(f"Autorol: '{role.name}' asignado a {member}")
        except discord.Forbidden:
            logger.error(
                "Autorol FALLÓ (Forbidden): el bot necesita permiso 'Gestionar roles' "
                f"y su rol debe estar POR ENCIMA de '{role.name}' en la jerarquía."
            )
        except Exception as e:
            logger.error(f"Autorol: error asignando rol a {member}: {e}")


async def setup(bot):
    await bot.add_cog(Events(bot))

import discord
from discord.ext import commands
from utils.logger import logger
from config import (
    AUTOROLE_ID, WELCOME_CHANNEL_ID, CHAT_CHANNEL_ID, PRESENTACIONES_CHANNEL_ID,
    COMIENZA_AQUI_CHANNEL_ID, LOG_CHANNEL_ID, GUILD_ID, DATA_DIR,
)
from utils.tiamat_welcome import TIAMAT_GUILD_ID, TiamatWelcomer

# Presence is global (one per bot), so it names something valid for every brand.
PRESENCE = "tiamatmc.net"


class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tiamat = TiamatWelcomer(bot, DATA_DIR)

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info(f"El bot está listo y online como {self.bot.user}")
        logger.info(f"Conectado a {len(self.bot.guilds)} servidor(es)")
        await self.bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching, name=PRESENCE
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
        """Each guild has its own welcome: Tiamat gets the card; TTS Dev SL autorole, log and welcome."""
        logger.info(f"Nuevo miembro: {member} ({member.id}) en {member.guild.name}")
        if member.guild.id == TIAMAT_GUILD_ID:
            await self.tiamat.join(member)
            return
        if member.guild.id != GUILD_ID:
            return
        await self._log(member.guild, f"📥 {member.mention} joined · account created <t:{int(member.created_at.timestamp())}:R>")
        if member.bot:
            return
        await self._assign_autorole(member)
        await self._send_welcome(member)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if member.guild.id == TIAMAT_GUILD_ID:
            await self.tiamat.leave(member)
            return
        if member.guild.id != GUILD_ID:
            return
        await self._log(member.guild, f"📤 {member.mention} ({member}) left")

    async def _log(self, guild, text):
        channel = guild.get_channel(LOG_CHANNEL_ID) if LOG_CHANNEL_ID else None
        if channel:
            try:
                await channel.send(text, allowed_mentions=discord.AllowedMentions.none())
            except discord.HTTPException:
                pass

    async def _assign_autorole(self, member):
        if not AUTOROLE_ID:
            return
        role = member.guild.get_role(AUTOROLE_ID)
        if role is None:
            logger.warning(f"Autorol: rol {AUTOROLE_ID} no existe en {member.guild.name}")
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

    async def _send_welcome(self, member):
        if not WELCOME_CHANNEL_ID:
            return
        channel = member.guild.get_channel(WELCOME_CHANNEL_ID)
        if channel is None:
            logger.warning(f"Bienvenida: canal {WELCOME_CHANNEL_ID} no encontrado")
            return
        comienza = f"<#{COMIENZA_AQUI_CHANNEL_ID}>" if COMIENZA_AQUI_CHANNEL_ID else "#comienza-aquí"
        presentaciones = f"<#{PRESENTACIONES_CHANNEL_ID}>" if PRESENTACIONES_CHANNEL_ID else "#presentaciones"
        chat = f"<#{CHAT_CHANNEL_ID}>" if CHAT_CHANNEL_ID else "el chat"
        embed = discord.Embed(
            title="👋 Welcome to TTS Dev SL",
            description=(
                f"Hi {member.mention}! Start in {comienza}: our plugins, the docs and how support works.\n"
                f"Questions go in {chat}."
            ),
            color=0xC879FF,
        )
        try:
            embed.set_thumbnail(url=member.display_avatar.url)
        except Exception:
            pass
        embed.set_footer(text="TTS Dev SL")
        try:
            await channel.send(content=member.mention, embed=embed)
            logger.info(f"Bienvenida enviada a {member} en #{channel}")
        except discord.Forbidden:
            logger.error(
                "Bienvenida FALLÓ (Forbidden): el bot necesita 'Enviar mensajes' "
                f"e 'Insertar enlaces' en el canal {WELCOME_CHANNEL_ID}."
            )
        except Exception as e:
            logger.error(f"Bienvenida: error enviando a {member}: {e}")


async def setup(bot):
    await bot.add_cog(Events(bot))

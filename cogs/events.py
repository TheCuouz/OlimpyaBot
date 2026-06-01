import discord
from discord.ext import commands
from utils.logger import logger
from config import AUTOROLE_ID, WELCOME_CHANNEL_ID


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
        """Al entrar un nuevo miembro: le asigna el autorol y le da la bienvenida."""
        logger.info(f"Nuevo miembro: {member} ({member.id}) en {member.guild.name}")
        if member.bot:
            return
        await self._assign_autorole(member)
        await self._send_welcome(member)

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
        embed = discord.Embed(
            title="🌸 ¡Bienvenido/a a la familia!",
            description=(
                f"¡Hola {member.mention}! Qué ilusión tenerte por aquí ✨\n\n"
                "Esto es **JournalByTTS**, la comunidad de **The Trader's Stop** 💛 "
                "Traders que van en serio… pero sin agobios. Aquí venimos a mejorar **juntos** 📈\n\n"
                "🧭 Pásate por **#presentaciones** y cuéntanos tu par favorito y en qué cuenta operas.\n"
                "🤝 Haz **amigos traders** — aquí se forman muy buenas migas.\n"
                "🎥 No te pierdas los **directos**, se aprende un montón y se pasa genial.\n\n"
                "Cualquier cosa que necesites, estoy por aquí para ayudarte. ¡Un abrazo enorme! 🫶"
            ),
            color=0xE8552B,
        )
        try:
            embed.set_thumbnail(url=member.display_avatar.url)
        except Exception:
            pass
        embed.set_footer(text="Olimpya · tu anfitriona 🌸")
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

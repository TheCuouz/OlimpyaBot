"""
Ejemplo de Cog con comandos.
Descomentar para usar, o usarlo como plantilla para crear más comandos.
"""

import discord
from discord.ext import commands
from discord import app_commands
from utils.logger import logger


class CommandsExample(commands.Cog):
    """Ejemplo de comandos - desactivado por defecto"""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="hola",
        description="El bot te saluda"
    )
    async def slash_hello(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"¡Hola {interaction.user.name}! 👋"
        )
        logger.info(f"Comando /hola ejecutado por {interaction.user}")

    @app_commands.command(
        name="ping",
        description="Muestra la latencia del bot"
    )
    async def slash_ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(
            f"Pong! 🏓 Latencia: {latency}ms"
        )

    @app_commands.command(
        name="info",
        description="Muestra información del bot"
    )
    async def slash_info(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="OlimpyaBot - Información",
            description="Bot profesional convertido de Java a Python",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Servidores",
            value=len(self.bot.guilds),
            inline=True
        )
        embed.add_field(
            name="Usuarios",
            value=sum(g.member_count for g in self.bot.guilds),
            inline=True
        )
        embed.set_footer(text=f"Bot por Desidia")

        await interaction.response.send_message(embed=embed)

    @commands.command(name="ayuda")
    async def prefix_help(self, ctx):
        """Comando con prefijo tradicional"""
        message = """
        **Comandos Disponibles:**
        
        Slash Commands (/)
        - `/hola` - El bot te saluda
        - `/ping` - Latencia del bot
        - `/info` - Información del bot
        
        Respuestas Automáticas
        - `Desidia` → "Que pasa perro?"
        """
        await ctx.send(message)


# Descomenta la siguiente línea para usar este cog
# async def setup(bot):
#     await bot.add_cog(CommandsExample(bot))

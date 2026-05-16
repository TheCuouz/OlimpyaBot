import asyncio
import discord
from discord.ext import commands
import os
import traceback
from config import DISCORD_TOKEN
from utils.logger import logger


class OlimpyaBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guild_messages = True
        intents.dm_messages = True

        super().__init__(command_prefix="!", intents=intents)
        self.synced = False

    async def setup_hook(self):
        await self.load_cogs()
        await self.tree.sync()
        logger.info("Cogs cargados y slash commands sincronizados")

    async def load_cogs(self):
        cogs_dir = "cogs"
        for filename in os.listdir(cogs_dir):
            if filename.endswith(".py") and not filename.startswith("__"):
                cog_name = filename[:-3]
                try:
                    await self.load_extension(f"cogs.{cog_name}")
                    logger.info(f"Cog '{cog_name}' cargado")
                except Exception as e:
                    logger.error(f"Error cargando cog '{cog_name}': {e}")


async def main():
    bot = OlimpyaBot()

    try:
        await bot.start(DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("Bot detenido por el usuario")
        await bot.close()
    except Exception as e:
        logger.error(f"Error fatal: {e}", exc_info=True)
        await bot.close()


if __name__ == "__main__":
    asyncio.run(main())

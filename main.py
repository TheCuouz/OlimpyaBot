import asyncio
import discord
from discord.ext import commands
import os
import traceback
from config import DISCORD_TOKEN, SYNC_GUILD_IDS
from utils.logger import logger


class OlimpyaBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guild_messages = True
        intents.dm_messages = True
        intents.members = True  # necesario para on_member_join (autorol al entrar)
        intents.invites = True  # GUILD_INVITES: eventos de invitaciones (sistema de invitaciones)

        super().__init__(command_prefix="!", intents=intents)
        self.synced = False

    async def setup_hook(self):
        await self.load_cogs()
        # Register the slash commands in every guild the bot is in (guild commands
        # show up at once). SYNC_GUILD_IDS can pin an explicit list; empty = all.
        targets = list(SYNC_GUILD_IDS)
        if not targets:
            targets = [guild.id async for guild in self.fetch_guilds()]
        for guild_id in targets:
            guild = discord.Object(id=guild_id)
            self.tree.copy_global_to(guild=guild)
            try:
                await self.tree.sync(guild=guild)
                logger.info(f"Slash commands sincronizados en el servidor {guild_id}")
            except discord.HTTPException as exc:
                logger.warning(f"No pude sincronizar comandos en {guild_id}: {exc}")
        # Clear the global scope so the commands don't duplicate across guilds.
        self.tree.clear_commands(guild=None)
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

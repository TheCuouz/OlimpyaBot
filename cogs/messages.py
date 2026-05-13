import discord
from discord.ext import commands
from utils.logger import logger
from config import RESPONSES


class MessageHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return

        self._log_message(message)

        content = message.content.lower().strip()
        for trigger, response in RESPONSES.items():
            if content == trigger:
                await message.channel.send(response)
                logger.info(
                    f"Respuesta enviada a {message.author}: {response}"
                )
                break

        await self.bot.process_commands(message)

    def _log_message(self, message):
        if isinstance(message.channel, discord.DMChannel):
            logger.info(f"[PM] {message.author.name}: {message.content}")
        else:
            guild_name = message.guild.name if message.guild else "Unknown"
            channel_name = message.channel.name if hasattr(
                message.channel, "name"
            ) else "Unknown"
            user_name = (
                message.author.display_name
                if message.guild
                else message.author.name
            )
            logger.info(
                f"[{guild_name}][{channel_name}] {user_name}: {message.content}"
            )


async def setup(bot):
    await bot.add_cog(MessageHandler(bot))

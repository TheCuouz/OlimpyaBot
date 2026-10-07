import os
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from config import CUSTOMER_ROLE, VOUCH_CHANNEL_ID, VOUCHES_FILE
from utils.logger import logger
from utils.vouches import RATING_LABELS, VouchStore, all_plugins, stars, vouch_embed

MAX_IMAGE_BYTES = 8 * 1024 * 1024
IMAGE_TYPES = ("image/png", "image/jpeg", "image/gif", "image/webp")
CONFIRMATION_SECONDS = 20


class VouchModal(discord.ui.Modal, title="Leave a vouch"):
    """Everything in one window: plugin, stars, review, server and an optional image."""

    plugin = discord.ui.Label(
        text="Plugin",
        description="Which one are you reviewing?",
        component=discord.ui.Select(
            placeholder="Choose a plugin",
            options=[discord.SelectOption(label=p, value=p) for p in all_plugins()],
        ),
    )
    rating = discord.ui.Label(
        text="Rating",
        component=discord.ui.Select(
            placeholder="How many stars?",
            options=[discord.SelectOption(label=f"{stars(n)}  {RATING_LABELS[n]}", value=str(n))
                     for n in range(5, 0, -1)],
        ),
    )
    review = discord.ui.Label(
        text="Your review",
        component=discord.ui.TextInput(
            style=discord.TextStyle.paragraph,
            placeholder="What you use it for, what you liked, what could be better",
            min_length=20,
            max_length=1000,
        ),
    )
    server = discord.ui.Label(
        text="Your server",
        description="Optional: a name or IP if you want it on the card",
        component=discord.ui.TextInput(style=discord.TextStyle.short, required=False, max_length=60),
    )
    image = discord.ui.Label(
        text="Image",
        description="Optional: show something you built with it (PNG, JPG, GIF or WEBP, up to 8 MB)",
        component=discord.ui.FileUpload(required=False, max_values=1),
    )

    def __init__(self, cog: "Vouches"):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        plugin = self.plugin.component.values[0]
        rating = int(self.rating.component.values[0])
        files = self.image.component.values
        await self.cog.publish(interaction, plugin, rating, self.review.component.value,
                               self.server.component.value.strip() or None, files[0] if files else None)


class Vouches(commands.Cog):
    """/vouch: a review card in the vouches channel, one per person and plugin."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.store = VouchStore(VOUCHES_FILE)

    @app_commands.command(name="vouch", description="Review one of our plugins")
    @app_commands.guild_only()
    async def vouch(self, interaction: discord.Interaction):
        await interaction.response.send_modal(VouchModal(self))

    async def _reply(self, interaction: discord.Interaction, text: str):
        """Only the author sees it, and it goes away so the channel stays clean."""
        message = await interaction.followup.send(text, ephemeral=True, wait=True)
        try:
            await message.delete(delay=CONFIRMATION_SECONDS)
        except discord.HTTPException:
            pass

    async def publish(self, interaction: discord.Interaction, plugin: str, rating: int,
                      review: str, server: Optional[str], image: Optional[discord.Attachment]):
        await interaction.response.defer(ephemeral=True, thinking=True)
        channel = interaction.guild.get_channel(VOUCH_CHANNEL_ID) if interaction.guild else None
        if channel is None:
            await self._reply(interaction, "❌ The vouches channel isn't set up.")
            return
        if image is not None:
            kind = (image.content_type or "").split(";")[0]
            if kind not in IMAGE_TYPES:
                await self._reply(interaction, "❌ The image must be a PNG, JPG, GIF or WEBP. Nothing was posted.")
                return
            if image.size > MAX_IMAGE_BYTES:
                await self._reply(interaction, "❌ The image must be under 8 MB. Nothing was posted.")
                return

        member = interaction.user
        previous = self.store.get(member.id, plugin)
        verified = any(r.name == CUSTOMER_ROLE for r in getattr(member, "roles", []))
        number = previous["number"] if previous else self.store.next_number()
        icon = interaction.guild.icon.url if interaction.guild.icon else None
        embed = vouch_embed(member, plugin, rating, review, verified, number, server, icon)

        # The upload is copied into the vouch itself: interaction attachment links expire.
        file = None
        if image is not None:
            try:
                ext = os.path.splitext(image.filename)[1].lower() or ".png"
                file = await image.to_file(filename=f"vouch-{number}{ext}")
                embed.set_image(url=f"attachment://{file.filename}")
            except discord.HTTPException:
                file = None

        message = None
        if previous:
            try:
                message = await channel.fetch_message(previous["message_id"])
                if file:
                    await message.edit(embed=embed, attachments=[file])
                else:
                    if message.attachments:  # keep the picture from last time
                        embed.set_image(url=f"attachment://{message.attachments[0].filename}")
                    await message.edit(embed=embed)
            except discord.HTTPException:
                message = None
        if message is None:
            if file:
                file.reset()
                message = await channel.send(embed=embed, file=file)
            else:
                message = await channel.send(embed=embed)
            try:
                await message.add_reaction("⭐")
            except discord.HTTPException:
                pass
        self.store.save(member.id, plugin, rating, message.id, number)

        await self._reply(
            interaction,
            ("✏️ Your review is updated: " if previous else "⭐ Thank you! Your review is up: ")
            + message.jump_url
            + "\nGot it on BuiltByBit or SpigotMC? A review there helps us a lot too.")
        logger.info(f"/vouch: {member} -> {plugin} {rating}★ ({'updated' if previous else 'new'})")


async def setup(bot: commands.Bot):
    await bot.add_cog(Vouches(bot))

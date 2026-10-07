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


class VouchModal(discord.ui.Modal):
    review = discord.ui.TextInput(
        label="Your review",
        style=discord.TextStyle.paragraph,
        placeholder="What you use it for, what you liked, what could be better",
        min_length=20,
        max_length=1000,
    )
    server = discord.ui.TextInput(
        label="Your server (optional)",
        style=discord.TextStyle.short,
        placeholder="Name or IP, if you want it shown",
        required=False,
        max_length=60,
    )

    def __init__(self, cog: "Vouches", plugin: str, rating: int, previous: dict = None,
                 image: Optional[discord.Attachment] = None):
        super().__init__(title=f"Review {plugin}"[:45])
        self.cog = cog
        self.plugin = plugin
        self.rating = rating
        self.previous = previous
        self.image = image

    async def on_submit(self, interaction: discord.Interaction):
        await self.cog.publish(interaction, self.plugin, self.rating, self.review.value,
                               self.server.value.strip() or None, self.previous, self.image)


class Vouches(commands.Cog):
    """/vouch: a review card in the vouches channel, one per person and plugin."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.store = VouchStore(VOUCHES_FILE)

    @app_commands.command(name="vouch", description="Review one of our plugins")
    @app_commands.describe(plugin="The plugin you're reviewing", rating="How many stars",
                           image="Optional: a screenshot of what you built with it")
    @app_commands.choices(rating=[
        app_commands.Choice(name=f"{stars(n)}  {RATING_LABELS[n]}", value=n) for n in range(5, 0, -1)])
    async def vouch(self, interaction: discord.Interaction, plugin: str, rating: app_commands.Choice[int],
                    image: Optional[discord.Attachment] = None):
        if plugin not in all_plugins():
            await interaction.response.send_message("❌ Pick a plugin from the list.", ephemeral=True)
            return
        if image is not None:
            kind = (image.content_type or "").split(";")[0]
            if kind not in IMAGE_TYPES:
                await interaction.response.send_message(
                    "❌ The image must be a PNG, JPG, GIF or WEBP.", ephemeral=True)
                return
            if image.size > MAX_IMAGE_BYTES:
                await interaction.response.send_message("❌ The image must be under 8 MB.", ephemeral=True)
                return
        previous = self.store.get(interaction.user.id, plugin)
        await interaction.response.send_modal(VouchModal(self, plugin, rating.value, previous, image))

    @vouch.autocomplete("plugin")
    async def plugin_autocomplete(self, interaction: discord.Interaction, current: str):
        c = current.lower()
        return [app_commands.Choice(name=n, value=n) for n in all_plugins() if c in n.lower()][:25]

    async def publish(self, interaction: discord.Interaction, plugin: str, rating: int,
                      review: str, server, previous, image: Optional[discord.Attachment] = None):
        await interaction.response.defer(ephemeral=True)
        channel = interaction.guild.get_channel(VOUCH_CHANNEL_ID) if interaction.guild else None
        if channel is None:
            await interaction.followup.send("❌ The vouches channel isn't set up.", ephemeral=True)
            return

        member = interaction.user
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
                file.fp.seek(0)
                message = await channel.send(embed=embed, file=file)
            else:
                message = await channel.send(embed=embed)
            try:
                await message.add_reaction("⭐")
            except discord.HTTPException:
                pass
        self.store.save(member.id, plugin, rating, message.id, number)

        await interaction.followup.send(
            ("✏️ Your review is updated: " if previous else "⭐ Thank you! Your review is up: ")
            + message.jump_url
            + "\nGot it on BuiltByBit or SpigotMC? A review there helps us a lot too.",
            ephemeral=True)
        logger.info(f"/vouch: {member} -> {plugin} {rating}★ ({'updated' if previous else 'new'})")


async def setup(bot: commands.Bot):
    await bot.add_cog(Vouches(bot))

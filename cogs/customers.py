import time

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from config import CLAIMED_KEYS_FILE, LICENSE_API, LOG_CHANNEL_ID
from utils.customers import (
    ClaimedKeys, customer_roles, normalize_key, product_choices, slugs, valid_key,
)
from utils.logger import logger

COOLDOWN_SECONDS = 30


class Customers(commands.Cog):
    """/verify for buyers with a licence key, /customer for the team."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.claimed = ClaimedKeys(CLAIMED_KEYS_FILE)
        self.last_try = {}

    async def _log(self, guild: discord.Guild, text: str):
        channel = guild.get_channel(LOG_CHANNEL_ID) if LOG_CHANNEL_ID else None
        if channel:
            try:
                await channel.send(text, allowed_mentions=discord.AllowedMentions.none())
            except discord.HTTPException:
                pass

    async def _find_product(self, key: str):
        """Returns the product the key is an active licence for, or None."""
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as http:
            for product, slug in slugs():
                url = f"{LICENSE_API}/{slug}/{key}?server=discord-verify"
                async with http.get(url) as r:
                    if r.status != 200:
                        raise RuntimeError(f"licence API {r.status}")
                    body = await r.json()
                    if body.get("data", {}).get("active"):
                        return product
        return None

    async def _grant(self, member: discord.Member, product: str, reason: str) -> list:
        roles = [r for r in customer_roles(member.guild, product) if r not in member.roles]
        if roles:
            await member.add_roles(*roles, reason=reason)
        return roles

    @app_commands.command(name="verify", description="Unlock your plugin's channels with your licence key")
    @app_commands.describe(key="Your licence key, TTS-XXXXX-XXXXX-XXXXX-XXXXX")
    async def verify(self, interaction: discord.Interaction, key: str):
        await interaction.response.defer(ephemeral=True)
        member = interaction.user
        now = time.monotonic()
        if now - self.last_try.get(member.id, 0) < COOLDOWN_SECONDS:
            await interaction.followup.send("⏳ Wait a few seconds and try again.", ephemeral=True)
            return
        self.last_try[member.id] = now

        key = normalize_key(key)
        if not valid_key(key):
            await interaction.followup.send(
                "❌ That doesn't look like a licence key. It is `TTS-` followed by four groups of five "
                "letters and digits, and it's in your purchase email.\n"
                "Bought on BuiltByBit? Open a ticket in the support channel with your BuiltByBit username "
                "and the team will give you the role.", ephemeral=True)
            return

        owner = self.claimed.owner(key)
        if owner and owner != member.id:
            await interaction.followup.send(
                "❌ This key is already linked to another Discord account. If it's yours, open a ticket "
                "and we'll sort it out.", ephemeral=True)
            await self._log(interaction.guild, f"⚠️ {member.mention} tried a key already linked to <@{owner}>.")
            return

        try:
            product = await self._find_product(key)
        except Exception as e:
            logger.error(f"/verify: licence check failed: {e}")
            await interaction.followup.send(
                "❌ The licence server didn't answer. Try again in a minute.", ephemeral=True)
            return

        if not product:
            await interaction.followup.send(
                "❌ That key isn't active. Check you copied it whole; if it's right, open a ticket.",
                ephemeral=True)
            return

        try:
            added = await self._grant(member, product, "Licence verified with /verify")
        except discord.Forbidden:
            logger.error("/verify: missing Manage Roles or the bot's role is too low")
            await interaction.followup.send("❌ I couldn't give you the role. The team has been told.",
                                            ephemeral=True)
            await self._log(interaction.guild, f"❌ Could not give {member.mention} the {product} role (permissions).")
            return

        self.claimed.claim(key, member.id, product)
        await interaction.followup.send(
            f"✅ Licence for **{product}** verified. Your download channel and customer support are "
            "unlocked. Thanks for your purchase!", ephemeral=True)
        await self._log(interaction.guild, f"🔑 {member.mention} verified **{product}** "
                                           f"({len(added)} role(s) added).")
        logger.info(f"/verify: {member} -> {product}")

    @app_commands.command(name="customer", description="Give someone the customer roles for a plugin")
    @app_commands.describe(member="Who bought it", plugin="Which plugin")
    @app_commands.default_permissions(manage_roles=True)
    async def customer(self, interaction: discord.Interaction, member: discord.Member, plugin: str):
        await interaction.response.defer(ephemeral=True)
        if plugin not in product_choices():
            await interaction.followup.send("❌ Pick a plugin from the list.", ephemeral=True)
            return
        try:
            added = await self._grant(member, plugin, f"Customer role given by {interaction.user}")
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ I can't give that role: I need Manage Roles and my role above it.", ephemeral=True)
            return
        await interaction.followup.send(
            f"✅ {member.mention}: **{plugin}** + Customer ({len(added)} role(s) added).", ephemeral=True)
        await self._log(interaction.guild,
                        f"🧾 {interaction.user.mention} gave {member.mention} **{plugin}** + Customer.")

    @customer.autocomplete("plugin")
    async def plugin_autocomplete(self, interaction: discord.Interaction, current: str):
        return [app_commands.Choice(name=n, value=n) for n in product_choices(current)][:25]


async def setup(bot: commands.Bot):
    await bot.add_cog(Customers(bot))

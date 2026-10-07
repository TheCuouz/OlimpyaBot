"""Vouch storage and the card that goes into the vouches channel."""
import json
import os
from datetime import datetime, timezone
from typing import Optional

import discord

from config import FREE_PRODUCTS, PRODUCTS

DOCS = "https://docs.journalbytts.xyz"
# Plugins with a page and a cover on the docs site, by display name -> docs slug.
DOCS_SLUG = {
    "AfkGuard": "afkguard", "AtlasForge": "atlasforge", "BetterDeathMessages": "betterdeathmessages",
    "ChattyChannels": "chattychannels", "ClaimsForge": "claimsforge", "CombatLogger": "combatlogger",
    "CrateForge": "crateforge", "DominionForge": "dominionforge", "EnchantsForge": "enchantsforge",
    "EnchantsForge V2": "enchantsforge", "HudForge": "hudforge", "ItemForge": "itemforge",
    "ParticleForge": "particleforge", "QuestForge": "questforge", "SafeRTP": "safertp",
    "ShopForge": "shopforge", "SkillsRPG": "skillsrpg", "SmartHomes": "smarthomes",
    "TradeForge": "tradeforge", "TTSCore": "ttscore",
}
RATING_LABELS = {5: "Excellent", 4: "Good", 3: "Okay", 2: "Poor", 1: "Bad"}
RATING_COLORS = {5: 0xF5C542, 4: 0xF5C542, 3: 0xE8A33D, 2: 0x99AAB5, 1: 0x99AAB5}


def all_plugins() -> list:
    return sorted(list(PRODUCTS) + FREE_PRODUCTS, key=str.lower)


def stars(n: int) -> str:
    return "★" * n + "☆" * (5 - n)


def quote(text: str) -> str:
    return "\n".join("> " + line if line.strip() else ">" for line in text.strip().splitlines())


def vouch_embed(member: discord.abc.User, plugin: str, rating: int, review: str, verified: bool,
                number: int, server: Optional[str] = None,
                guild_icon: Optional[str] = None) -> discord.Embed:
    slug = DOCS_SLUG.get(plugin)
    embed = discord.Embed(
        title=plugin,
        url=f"{DOCS}/{slug}/" if slug else None,
        description=f"**{stars(rating)}**  ·  {RATING_LABELS[rating]}\n\n{quote(review)}",
        color=RATING_COLORS[rating],
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
    if slug:
        embed.set_thumbnail(url=f"{DOCS}/portadas/{slug}.png")
    embed.add_field(name="Reviewer", value="✔ Verified customer" if verified else "Community member", inline=True)
    if server:
        embed.add_field(name="Server", value=server[:100], inline=True)
    embed.set_footer(text=f"Vouch #{number}  ·  TTS Dev SL", icon_url=guild_icon)
    return embed


class VouchStore:
    """One vouch per person per plugin: posting again updates the same card."""

    def __init__(self, path: str):
        self.path = path
        self.data = {"counter": 0, "vouches": {}}
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict) and "vouches" in loaded:
                    self.data = loaded
            except (OSError, ValueError):
                pass

    @staticmethod
    def _key(user_id: int, plugin: str) -> str:
        return f"{user_id}:{plugin.lower()}"

    def get(self, user_id: int, plugin: str) -> Optional[dict]:
        return self.data["vouches"].get(self._key(user_id, plugin))

    def next_number(self) -> int:
        return self.data["counter"] + 1

    def save(self, user_id: int, plugin: str, rating: int, message_id: int, number: int):
        self.data["counter"] = max(self.data["counter"], number)
        self.data["vouches"][self._key(user_id, plugin)] = {
            "rating": rating, "message_id": message_id, "number": number}
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)
        os.replace(tmp, self.path)

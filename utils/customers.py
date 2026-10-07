"""Customer roles: which roles a buyer gets and who already used which licence key."""
import json
import os
import re
from typing import Iterable, Optional

import discord

from config import CUSTOMER_DIVIDERS, CUSTOMER_ROLE, PRODUCT_ROLE_PREFIX, PRODUCTS

LICENSE_KEY = re.compile(r"^TTS-[0-9A-HJKMNP-TV-Z]{5}(-[0-9A-HJKMNP-TV-Z]{5}){3}$")


def normalize_key(raw: str) -> str:
    return raw.strip().upper()


def valid_key(key: str) -> bool:
    return bool(LICENSE_KEY.match(key))


def customer_roles(guild: discord.Guild, product: str) -> list:
    """Product role + Customer + the group dividers. Missing roles are skipped."""
    wanted = [PRODUCT_ROLE_PREFIX + product, CUSTOMER_ROLE]
    roles = [discord.utils.get(guild.roles, name=n) for n in wanted]
    for divider in CUSTOMER_DIVIDERS:
        roles.append(next((r for r in guild.roles if r.name.startswith("▬") and divider in r.name), None))
    return [r for r in roles if r is not None]


def product_choices(prefix: str = "") -> list:
    p = prefix.lower()
    return [name for name in PRODUCTS if name.lower().startswith(p)]


class ClaimedKeys:
    """One licence key unlocks roles for one Discord account."""

    def __init__(self, path: str):
        self.path = path
        self.data = {}
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    self.data = json.load(f)
            except (OSError, ValueError):
                self.data = {}

    def owner(self, key: str) -> Optional[int]:
        entry = self.data.get(key)
        return int(entry["user_id"]) if entry else None

    def claim(self, key: str, user_id: int, product: str):
        self.data[key] = {"user_id": user_id, "product": product}
        self._save()

    def _save(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)
        os.replace(tmp, self.path)


def slugs() -> Iterable:
    return PRODUCTS.items()

"""Utilities for creating and managing Discord embeds."""

from typing import Dict, Any, Optional, Tuple
import discord
from config import EMBED_CONFIG


async def is_valid_image_url(url: str) -> bool:
    """Check if URL looks like a valid image URL."""
    if not url:
        return False
    if not url.startswith(("http://", "https://")):
        return False
    valid_ext = (".png", ".jpg", ".jpeg", ".gif", ".webp")
    return any(url.lower().endswith(ext) for ext in valid_ext)


def get_color_from_string(color_name: str) -> Optional[int]:
    """Convert color name to Discord int color."""
    color_map = EMBED_CONFIG["colors"]
    return color_map.get(color_name.lower() if color_name else "")


def validate_embed_data(data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validate embed data against Discord limits."""
    if "title" in data and data["title"]:
        if len(data["title"]) > EMBED_CONFIG["limits"]["title"]:
            return False, f"Title exceeds {EMBED_CONFIG['limits']['title']} chars"

    if "description" in data and data["description"]:
        if len(data["description"]) > EMBED_CONFIG["limits"]["description"]:
            return False, f"Description exceeds {EMBED_CONFIG['limits']['description']} chars"

    if "fields" in data and data["fields"]:
        if len(data["fields"]) > EMBED_CONFIG["limits"]["max_fields"]:
            return False, f"Max {EMBED_CONFIG['limits']['max_fields']} fields allowed"
        for field in data["fields"]:
            if len(field.get("name", "")) > EMBED_CONFIG["limits"]["field_name"]:
                return False, f"Field name too long"
            if len(field.get("value", "")) > EMBED_CONFIG["limits"]["field_value"]:
                return False, f"Field value too long"

    if "color" in data and data["color"]:
        if not get_color_from_string(data["color"]):
            return False, f"Invalid color: {data['color']}"

    return True, None


def validate_embed(title: str, description: str, fields: list = None) -> bool:
    """Validate embed content against Discord limits."""
    limits = EMBED_CONFIG["limits"]
    
    # Check title length
    if title and len(title) > limits["title"]:
        return False
    
    # Check description length
    if description and len(description) > limits["description"]:
        return False
    
    # Check fields
    if fields:
        if len(fields) > limits["max_fields"]:
            return False
        
        for field in fields:
            if len(field.get("name", "")) > limits["field_name"]:
                return False
            if len(field.get("value", "")) > limits["field_value"]:
                return False
    
    return True


def create_embed(title: str, description: str, color: str = "azul", fields: list = None) -> discord.Embed:
    """Create a styled embed with predefined colors."""
    colors = EMBED_CONFIG["colors"]
    color_value = colors.get(color, colors["azul"])
    
    embed = discord.Embed(
        title=title,
        description=description,
        color=color_value
    )
    
    if fields:
        for field in fields:
            embed.add_field(
                name=field.get("name", ""),
                value=field.get("value", ""),
                inline=field.get("inline", False)
            )
    
    return embed


def create_error_embed(message: str) -> discord.Embed:
    """Create an error embed."""
    return create_embed(
        title="Error",
        description=message,
        color="rojo"
    )


def create_success_embed(message: str) -> discord.Embed:
    """Create a success embed."""
    return create_embed(
        title="Success",
        description=message,
        color="verde"
    )

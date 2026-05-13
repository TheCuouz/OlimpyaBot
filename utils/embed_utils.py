"""Utilities for creating and managing Discord embeds."""

import discord
from config import EMBED_CONFIG


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

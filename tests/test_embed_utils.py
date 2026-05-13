"""Tests for embed_utils module."""

import pytest
import discord
from utils.embed_utils import validate_embed_data, get_color_from_string, is_valid_image_url, create_embed_from_data


def test_validate_embed_data_valid():
    """Valid embed data passes validation."""
    data = {"title": "Test", "description": "Desc"}
    is_valid, error = validate_embed_data(data)
    assert is_valid is True
    assert error is None


def test_get_color_from_string():
    """Test color name conversion to Discord int color."""
    assert get_color_from_string("rojo") == 0xFF0000
    assert get_color_from_string("azul") == 0x0000FF
    assert get_color_from_string("invalid") is None


@pytest.mark.asyncio
async def test_is_valid_image_url():
    """Test image URL validation."""
    assert await is_valid_image_url("https://example.com/image.png") is True
    assert await is_valid_image_url("invalid") is False


def test_create_embed_from_data():
    """Test create_embed_from_data creates proper Discord embeds."""
    data = {"title": "Test", "description": "Desc", "color": "rojo"}
    embed = create_embed_from_data(data)
    assert isinstance(embed, discord.Embed)
    assert embed.title == "Test"
    assert embed.color == discord.Color(0xFF0000)

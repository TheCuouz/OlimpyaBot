"""Tests for EmbedBuilderCog."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from cogs.embed_builder import EmbedBuilderCog


@pytest.mark.asyncio
async def test_embed_builder_requires_admin():
    bot = MagicMock()
    bot.embed_builders = {}
    cog = EmbedBuilderCog(bot)
    interaction = AsyncMock()
    interaction.user.guild_permissions.administrator = False

    await cog.embed_builder.callback(cog, interaction, channel=None)

    interaction.response.send_message.assert_called()
    call_args = interaction.response.send_message.call_args
    assert "No permisos" in call_args[0][0]

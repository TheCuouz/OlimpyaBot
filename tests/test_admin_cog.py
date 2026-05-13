"""Tests for AdminCog."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from cogs.admin import AdminCog


@pytest.mark.asyncio
async def test_purge_requires_admin():
    bot = MagicMock()
    cog = AdminCog(bot)
    interaction = AsyncMock()
    interaction.user.guild_permissions.administrator = False
    await cog.purge.callback(cog, interaction, 5)
    interaction.response.send_message.assert_called()

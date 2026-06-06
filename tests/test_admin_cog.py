"""Tests for AdminCog."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from cogs.admin import AdminCog


@pytest.mark.asyncio
async def test_purge_rejects_out_of_range():
    # El control de admin es declarativo (@app_commands.default_permissions),
    # lo aplica Discord server-side. La invariante propia del código es el rango 1-100.
    bot = MagicMock()
    cog = AdminCog(bot)
    interaction = AsyncMock()
    await cog.purge.callback(cog, interaction, 0)
    interaction.response.send_message.assert_called()
    # Con 0 mensajes no debe llegar a purgar el canal.
    interaction.channel.purge.assert_not_called()


@pytest.mark.asyncio
async def test_purge_valid_range_executes():
    bot = MagicMock()
    cog = AdminCog(bot)
    interaction = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.channel.purge = AsyncMock(return_value=[1, 2, 3])
    await cog.purge.callback(cog, interaction, 3)
    interaction.response.defer.assert_called_once()
    interaction.channel.purge.assert_called_once_with(limit=3)


@pytest.mark.asyncio
async def test_kick_requires_admin():
    bot = MagicMock()
    cog = AdminCog(bot)
    interaction = AsyncMock()
    user = MagicMock()
    interaction.user.guild_permissions.administrator = False
    await cog.kick.callback(cog, interaction, user)
    interaction.response.send_message.assert_called()


@pytest.mark.asyncio
async def test_kick_success():
    bot = MagicMock()
    cog = AdminCog(bot)
    interaction = AsyncMock()
    user = MagicMock()
    user.mention = "@TestUser"
    interaction.user.guild_permissions.administrator = True
    interaction.guild = AsyncMock()
    interaction.guild.kick = AsyncMock()
    await cog.kick.callback(cog, interaction, user)
    # El código pasa un reason (por defecto "Sin motivo") a la API de Discord.
    interaction.guild.kick.assert_called_once_with(user, reason="Sin motivo")
    interaction.response.send_message.assert_called()


@pytest.mark.asyncio
async def test_ban_requires_admin():
    bot = MagicMock()
    cog = AdminCog(bot)
    interaction = AsyncMock()
    user = MagicMock()
    interaction.user.guild_permissions.administrator = False
    await cog.ban.callback(cog, interaction, user)
    interaction.response.send_message.assert_called()


@pytest.mark.asyncio
async def test_ban_success():
    bot = MagicMock()
    cog = AdminCog(bot)
    interaction = AsyncMock()
    user = MagicMock()
    user.mention = "@TestUser"
    interaction.user.guild_permissions.administrator = True
    interaction.guild = AsyncMock()
    interaction.guild.ban = AsyncMock()
    await cog.ban.callback(cog, interaction, user)
    interaction.guild.ban.assert_called_once_with(user, reason="Sin motivo")
    interaction.response.send_message.assert_called()


@pytest.mark.asyncio
async def test_softban_requires_admin():
    bot = MagicMock()
    cog = AdminCog(bot)
    interaction = AsyncMock()
    user = MagicMock()
    interaction.user.guild_permissions.administrator = False
    await cog.softban.callback(cog, interaction, user)
    interaction.response.send_message.assert_called()


@pytest.mark.asyncio
async def test_softban_success():
    bot = MagicMock()
    cog = AdminCog(bot)
    interaction = AsyncMock()
    user = MagicMock()
    user.mention = "@TestUser"
    interaction.user.guild_permissions.administrator = True
    interaction.guild = AsyncMock()
    interaction.guild.ban = AsyncMock()
    interaction.guild.unban = AsyncMock()
    await cog.softban.callback(cog, interaction, user)
    interaction.guild.ban.assert_called_once_with(user, delete_message_days=7, reason="Sin motivo")
    interaction.guild.unban.assert_called_once_with(user, reason="Softban")
    interaction.response.send_message.assert_called()


@pytest.mark.asyncio
async def test_mute_requires_admin():
    bot = MagicMock()
    cog = AdminCog(bot)
    interaction = AsyncMock()
    user = MagicMock()
    interaction.user.guild_permissions.administrator = False
    await cog.mute.callback(cog, interaction, user, "1h")
    interaction.response.send_message.assert_called()


@pytest.mark.asyncio
async def test_mute_invalid_format():
    bot = MagicMock()
    cog = AdminCog(bot)
    interaction = AsyncMock()
    user = MagicMock()
    interaction.user.guild_permissions.administrator = True
    await cog.mute.callback(cog, interaction, user, "invalid")
    interaction.response.send_message.assert_called()


@pytest.mark.asyncio
async def test_mute_success():
    bot = MagicMock()
    cog = AdminCog(bot)
    interaction = AsyncMock()
    # El código aplica el timeout directamente sobre el Member recibido (no hace fetch).
    user = AsyncMock()
    user.id = 123
    user.mention = "@TestUser"
    user.timeout = AsyncMock()
    interaction.user.guild_permissions.administrator = True
    await cog.mute.callback(cog, interaction, user, "1h")
    user.timeout.assert_called_once()
    interaction.response.send_message.assert_called()


@pytest.mark.asyncio
async def test_warn_requires_admin():
    bot = MagicMock()
    cog = AdminCog(bot)
    interaction = AsyncMock()
    user = MagicMock()
    interaction.user.guild_permissions.administrator = False
    await cog.warn.callback(cog, interaction, user, "spam")
    interaction.response.send_message.assert_called()


@pytest.mark.asyncio
async def test_warn_success():
    bot = MagicMock()
    cog = AdminCog(bot)
    interaction = AsyncMock()
    user = MagicMock()
    user.mention = "@TestUser"
    interaction.user.guild_permissions.administrator = True
    await cog.warn.callback(cog, interaction, user, "spam")
    interaction.response.send_message.assert_called()


@pytest.mark.asyncio
async def test_clear_rejects_unknown_type():
    # El control de admin es declarativo (lo aplica Discord). La invariante propia
    # del código es la allowlist de tipos: un tipo fuera de ella se rechaza sin defer.
    bot = MagicMock()
    cog = AdminCog(bot)
    interaction = AsyncMock()
    await cog.clear.callback(cog, interaction, "no-existe")
    interaction.response.send_message.assert_called()
    interaction.response.defer.assert_not_called()


@pytest.mark.asyncio
async def test_clear_invalid_type():
    bot = MagicMock()
    cog = AdminCog(bot)
    interaction = AsyncMock()
    interaction.user.guild_permissions.administrator = True
    await cog.clear.callback(cog, interaction, "invalid")
    interaction.response.send_message.assert_called()


@pytest.mark.asyncio
async def test_clear_success():
    bot = MagicMock()
    cog = AdminCog(bot)
    interaction = AsyncMock()
    interaction.user.guild_permissions.administrator = True
    interaction.response.defer = AsyncMock()
    
    # Mock message history
    msg1 = AsyncMock()
    msg1.embeds = [AsyncMock()]
    msg1.delete = AsyncMock()
    msg2 = AsyncMock()
    msg2.embeds = []
    msg2.delete = AsyncMock()
    
    async def mock_history(*args, **kwargs):
        for msg in [msg1, msg2]:
            yield msg
    
    interaction.channel.history = mock_history
    interaction.followup = AsyncMock()
    
    await cog.clear.callback(cog, interaction, "embeds")
    interaction.response.defer.assert_called_once()
    msg1.delete.assert_called_once()
    msg2.delete.assert_not_called()
    interaction.followup.send.assert_called_once()

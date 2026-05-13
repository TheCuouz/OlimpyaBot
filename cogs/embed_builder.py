"""Interactive embed builder with button UI."""
import discord
from discord.ext import commands
from discord import app_commands
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class TitleModal(discord.ui.Modal):
    title = "Edit Title"
    title_input = discord.ui.TextInput(label="Title", max_length=256)

    def __init__(self, cog, user_id):
        super().__init__()
        self.cog, self.user_id = cog, user_id

    async def on_submit(self, interaction):
        if self.user_id not in self.cog.bot.embed_builders:
            self.cog.bot.embed_builders[self.user_id] = {}
        self.cog.bot.embed_builders[self.user_id]["title"] = self.title_input.value
        await interaction.response.defer()


class DescriptionModal(discord.ui.Modal):
    title = "Edit Description"
    desc_input = discord.ui.TextInput(label="Description", max_length=4096, style=discord.TextStyle.long)

    def __init__(self, cog, user_id):
        super().__init__()
        self.cog, self.user_id = cog, user_id

    async def on_submit(self, interaction):
        if self.user_id not in self.cog.bot.embed_builders:
            self.cog.bot.embed_builders[self.user_id] = {}
        self.cog.bot.embed_builders[self.user_id]["description"] = self.desc_input.value
        await interaction.response.defer()


class ColorModal(discord.ui.Modal):
    title = "Select Color"
    color_input = discord.ui.TextInput(label="Color (rojo, azul, verde...)", max_length=50)

    def __init__(self, cog, user_id):
        super().__init__()
        self.cog, self.user_id = cog, user_id

    async def on_submit(self, interaction):
        if self.user_id not in self.cog.bot.embed_builders:
            self.cog.bot.embed_builders[self.user_id] = {}
        self.cog.bot.embed_builders[self.user_id]["color"] = self.color_input.value
        await interaction.response.defer()


class BuilderView(discord.ui.View):
    def __init__(self, cog, user_id, channel):
        super().__init__(timeout=1800)
        self.cog, self.user_id, self.channel = cog, user_id, channel

    @discord.ui.button(label="Título", style=discord.ButtonStyle.gray)
    async def title_btn(self, interaction, button):
        if interaction.user.id != self.user_id:
            return
        await interaction.response.show_modal(TitleModal(self.cog, self.user_id))

    @discord.ui.button(label="Descripción", style=discord.ButtonStyle.gray)
    async def desc_btn(self, interaction, button):
        if interaction.user.id != self.user_id:
            return
        await interaction.response.show_modal(DescriptionModal(self.cog, self.user_id))

    @discord.ui.button(label="Color", style=discord.ButtonStyle.gray)
    async def color_btn(self, interaction, button):
        if interaction.user.id != self.user_id:
            return
        await interaction.response.show_modal(ColorModal(self.cog, self.user_id))

    @discord.ui.button(label="Preview", style=discord.ButtonStyle.primary)
    async def preview_btn(self, interaction, button):
        if interaction.user.id != self.user_id:
            return
        from utils.embed_utils import create_embed_from_data
        try:
            state = self.cog.bot.embed_builders.get(self.user_id, {})
            embed = create_embed_from_data(state)
            await interaction.response.send_message("📋 Preview:", embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error: {str(e)}", ephemeral=True)

    @discord.ui.button(label="Enviar", style=discord.ButtonStyle.success)
    async def send_btn(self, interaction, button):
        if interaction.user.id != self.user_id:
            return
        from utils.embed_utils import create_embed_from_data, validate_embed_data
        state = self.cog.bot.embed_builders.get(self.user_id, {})
        is_valid, error = validate_embed_data(state)
        if not is_valid:
            await interaction.response.send_message(f"❌ {error}", ephemeral=True)
            return
        try:
            channel = state.get("channel")
            embed = create_embed_from_data(state)
            await channel.send(embed=embed)
            await interaction.response.send_message(f"✅ Enviado a {channel.mention}", ephemeral=True)
            if self.user_id in self.cog.bot.embed_builders:
                del self.cog.bot.embed_builders[self.user_id]
            logger.info(f"Embed sent by {interaction.user}")
        except Exception as e:
            await interaction.response.send_message(f"❌ {str(e)}", ephemeral=True)


class EmbedBuilderCog(commands.Cog):
    """Interactive embed builder with button-driven interface."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        if not hasattr(bot, "embed_builders"):
            bot.embed_builders = {}

    @app_commands.command(name="embed_builder")
    @app_commands.describe(channel="Target channel (optional)")
    async def embed_builder(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        """Start interactive embed builder."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ No permisos", ephemeral=True)
            return

        if not channel:
            select = discord.ui.ChannelSelect(channel_types=[discord.ChannelType.text])

            async def select_cb(sel_int):
                ch = sel_int.values[0]
                self.bot.embed_builders[interaction.user.id] = {"channel": ch}
                await sel_int.response.send_message(
                    f"🎨 Canal: {ch.mention}\n\nElige un campo:",
                    view=BuilderView(self, interaction.user.id, ch),
                    ephemeral=True
                )

            select.callback = select_cb
            view = discord.ui.View()
            view.add_item(select)
            await interaction.response.send_message("Selecciona canal:", view=view, ephemeral=True)
        else:
            self.bot.embed_builders[interaction.user.id] = {"channel": channel}
            await interaction.response.send_message(
                f"🎨 Canal: {channel.mention}\n\nElige un campo:",
                view=BuilderView(self, interaction.user.id, channel),
                ephemeral=True
            )
            logger.info(f"Embed builder started by {interaction.user}")


async def setup(bot: commands.Bot):
    await bot.add_cog(EmbedBuilderCog(bot))

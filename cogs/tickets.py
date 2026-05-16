import discord
from discord.ext import commands
from discord import app_commands
from utils.logger import logger
from utils.ticket_manager import TicketManager
from utils.ticket_utils import (
    create_ticket_embed, create_setup_embed, create_action_embed,
    create_ticket_channel, archive_channel, get_staff_role, user_is_staff
)
from config import TICKET_CONFIG


class TicketModal(discord.ui.Modal, title="Crear ticket de soporte"):
    descripcion = discord.ui.TextInput(
        label="Descripción",
        placeholder="Describe tu problema en detalle",
        style=discord.TextStyle.paragraph,
        required=True,
        min_length=10,
        max_length=1000
    )

    def __init__(self, ticket_cog: 'Tickets'):
        super().__init__()
        self.ticket_cog = ticket_cog
        self.selected_category = None
        self.selected_priority = None

    async def on_submit(self, interaction: discord.Interaction):
        if not self.selected_category:
            self.selected_category = TICKET_CONFIG["categories"][0]
        if not self.selected_priority:
            self.selected_priority = TICKET_CONFIG["priorities"][0]

        await interaction.response.defer(ephemeral=True)

        try:
            ticket_id = self.ticket_cog.ticket_manager.create_ticket(
                creator_id=interaction.user.id,
                creator_name=interaction.user.name,
                category=self.selected_category,
                priority=self.selected_priority,
                title=self.descripcion.value[:50] if self.descripcion.value else "Sin título",
                description=self.descripcion.value
            )

            staff_role = get_staff_role(interaction.guild, TICKET_CONFIG["staff_role_name"])
            channel = await create_ticket_channel(
                interaction.guild,
                ticket_id,
                self.descripcion.value[:30],
                interaction.user,
                staff_role
            )

            if not channel:
                await interaction.followup.send(
                    "❌ No se pudo crear el canal del ticket. Inténtalo de nuevo.",
                    ephemeral=True
                )
                return

            self.ticket_cog.ticket_manager.update_ticket(ticket_id, {"channel_id": channel.id})

            ticket = self.ticket_cog.ticket_manager.get_ticket(ticket_id)
            embed = create_ticket_embed(ticket)
            view = self.ticket_cog.create_ticket_buttons(ticket_id)

            await channel.send(embed=embed, view=view)
            await interaction.followup.send(
                f"✅ Ticket creado. Canal: {channel.mention}",
                ephemeral=True
            )
            logger.info(f"Ticket {ticket_id} creado por {interaction.user.name}")

        except Exception as e:
            logger.error(f"Error al crear ticket: {e}")
            await interaction.followup.send(
                "❌ Ocurrió un error al crear el ticket. Inténtalo de nuevo.",
                ephemeral=True
            )


class TicketButtonView(discord.ui.View):
    def __init__(self, ticket_cog: 'Tickets', ticket_id: str):
        super().__init__(timeout=None)
        self.ticket_cog = ticket_cog
        self.ticket_id = ticket_id

    @discord.ui.button(label="Cerrar", style=discord.ButtonStyle.danger, emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.ticket_cog.close_ticket(interaction, self.ticket_id)

    @discord.ui.button(label="Reabrir", style=discord.ButtonStyle.primary, emoji="🔓")
    async def reopen_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.ticket_cog.reopen_ticket(interaction, self.ticket_id)

    @discord.ui.button(label="Asignar", style=discord.ButtonStyle.success, emoji="👤")
    async def assign_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.ticket_cog.assign_ticket(interaction, self.ticket_id)


class CreateTicketView(discord.ui.View):
    def __init__(self, ticket_cog: 'Tickets'):
        super().__init__(timeout=None)
        self.ticket_cog = ticket_cog

    @discord.ui.button(label="Crear Ticket", style=discord.ButtonStyle.primary, emoji="📝")
    async def create_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TicketModal(self.ticket_cog))


class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ticket_manager = TicketManager(TICKET_CONFIG["data_file"])
        logger.info("Tickets cog initialized")

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("Tickets cog ready")

    @app_commands.command(name="setup-tickets", description="Configura el sistema de tickets en este canal")
    @app_commands.default_permissions(administrator=True)
    async def setup_tickets(self, interaction: discord.Interaction):
        try:
            embed = create_setup_embed()
            view = CreateTicketView(self)
            await interaction.response.send_message(embed=embed, view=view)
            logger.info(f"Sistema de tickets configurado en {interaction.guild.name} por {interaction.user.name}")
        except Exception as e:
            logger.error(f"Error al configurar tickets: {e}")
            await interaction.response.send_message(
                "❌ No se pudo configurar el sistema de tickets.",
                ephemeral=True
            )

    def create_ticket_buttons(self, ticket_id: str) -> TicketButtonView:
        return TicketButtonView(self, ticket_id)

    async def close_ticket(self, interaction: discord.Interaction, ticket_id: str):
        await interaction.response.defer(ephemeral=True)
        try:
            ticket = self.ticket_manager.get_ticket(ticket_id)
            if not ticket:
                await interaction.followup.send("❌ Ticket no encontrado.", ephemeral=True)
                return

            staff_role = get_staff_role(interaction.guild, TICKET_CONFIG["staff_role_name"])
            is_creator = interaction.user.id == ticket["creator_id"]
            is_staff = user_is_staff(interaction.user, staff_role)

            if not (is_creator or is_staff):
                await interaction.followup.send("❌ No tienes permiso para cerrar este ticket.", ephemeral=True)
                return

            self.ticket_manager.close_ticket(ticket_id)
            channel = interaction.guild.get_channel(ticket["channel_id"])
            if channel:
                await archive_channel(channel)

            action_embed = create_action_embed("Cerrado", interaction.user.name)
            await interaction.followup.send(embed=action_embed, ephemeral=True)
            logger.info(f"Ticket {ticket_id} cerrado por {interaction.user.name}")

        except Exception as e:
            logger.error(f"Error al cerrar ticket {ticket_id}: {e}")
            await interaction.followup.send("❌ Error al cerrar el ticket.", ephemeral=True)

    async def reopen_ticket(self, interaction: discord.Interaction, ticket_id: str):
        await interaction.response.defer(ephemeral=True)
        try:
            ticket = self.ticket_manager.get_ticket(ticket_id)
            if not ticket:
                await interaction.followup.send("❌ Ticket no encontrado.", ephemeral=True)
                return

            staff_role = get_staff_role(interaction.guild, TICKET_CONFIG["staff_role_name"])
            is_creator = interaction.user.id == ticket["creator_id"]
            is_staff = user_is_staff(interaction.user, staff_role)

            if not (is_creator or is_staff):
                await interaction.followup.send("❌ No tienes permiso para reabrir este ticket.", ephemeral=True)
                return

            self.ticket_manager.reopen_ticket(ticket_id)
            channel = interaction.guild.get_channel(ticket["channel_id"])
            if channel:
                new_name = channel.name.replace("✅-", "", 1)
                try:
                    await channel.edit(name=new_name)
                except Exception:
                    pass

            action_embed = create_action_embed("Reabierto", interaction.user.name)
            await interaction.followup.send(embed=action_embed, ephemeral=True)
            logger.info(f"Ticket {ticket_id} reabierto por {interaction.user.name}")

        except Exception as e:
            logger.error(f"Error al reabrir ticket {ticket_id}: {e}")
            await interaction.followup.send("❌ Error al reabrir el ticket.", ephemeral=True)

    async def assign_ticket(self, interaction: discord.Interaction, ticket_id: str):
        await interaction.response.defer(ephemeral=True)
        try:
            ticket = self.ticket_manager.get_ticket(ticket_id)
            if not ticket:
                await interaction.followup.send("❌ Ticket no encontrado.", ephemeral=True)
                return

            staff_role = get_staff_role(interaction.guild, TICKET_CONFIG["staff_role_name"])
            if not user_is_staff(interaction.user, staff_role):
                await interaction.followup.send("❌ Necesitas ser staff para asignar tickets.", ephemeral=True)
                return

            self.ticket_manager.assign_ticket(ticket_id, interaction.user.id, interaction.user.name)
            action_embed = create_action_embed(f"Asignado a {interaction.user.name}", interaction.user.name)
            await interaction.followup.send(embed=action_embed, ephemeral=True)
            logger.info(f"Ticket {ticket_id} asignado a {interaction.user.name}")

        except Exception as e:
            logger.error(f"Error al asignar ticket {ticket_id}: {e}")
            await interaction.followup.send("❌ Error al asignar el ticket.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
    logger.info("Tickets cog loaded")

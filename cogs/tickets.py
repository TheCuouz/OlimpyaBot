from typing import Optional

import discord
from discord.ext import commands
from discord import app_commands
from utils.logger import logger
from utils.ticket_manager import TicketManager
from utils.ticket_utils import (
    create_ticket_embed, create_setup_embed, create_action_embed,
    create_welcome_message, create_ticket_channel, archive_channel,
    get_staff_role, user_is_staff,
)
from config import TICKET_CONFIG


class TicketModal(discord.ui.Modal, title="Crear ticket de soporte"):
    motivo = discord.ui.TextInput(
        label="Motivo",
        placeholder="Resumen breve del ticket",
        style=discord.TextStyle.short,
        required=True,
        min_length=3,
        max_length=100,
    )
    descripcion = discord.ui.TextInput(
        label="Descripción",
        placeholder="Describe tu problema en detalle",
        style=discord.TextStyle.paragraph,
        required=True,
        min_length=10,
        max_length=1000,
    )

    def __init__(self, ticket_cog: 'Tickets', categoria: str, prioridad: str):
        super().__init__()
        self.ticket_cog = ticket_cog
        self.categoria = categoria
        self.prioridad = prioridad

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            ticket_id = self.ticket_cog.ticket_manager.create_ticket(
                creator_id=interaction.user.id,
                creator_name=interaction.user.name,
                category=self.categoria,
                priority=self.prioridad,
                title=self.motivo.value,
                description=self.descripcion.value,
            )

            staff_role = get_staff_role(interaction.guild)
            channel = await create_ticket_channel(
                interaction.guild,
                ticket_id,
                self.motivo.value,
                interaction.user,
                staff_role,
            )

            if not channel:
                await interaction.followup.send(
                    "❌ No se pudo crear el canal del ticket. Inténtalo de nuevo.",
                    ephemeral=True,
                )
                return

            self.ticket_cog.ticket_manager.update_ticket(ticket_id, {"channel_id": channel.id})

            ticket = self.ticket_cog.ticket_manager.get_ticket(ticket_id)
            embed = create_ticket_embed(ticket)
            view = self.ticket_cog.create_ticket_buttons(ticket_id)
            welcome = create_welcome_message(interaction.user, ticket, staff_role)

            await channel.send(
                content=welcome,
                embed=embed,
                view=view,
                allowed_mentions=discord.AllowedMentions(users=True, roles=True),
            )
            await interaction.followup.send(
                f"✅ Ticket creado. Canal: {channel.mention}",
                ephemeral=True,
            )
            logger.info(f"Ticket {ticket_id} creado por {interaction.user.name}")

        except Exception as e:
            logger.error(f"Error al crear ticket: {e}", exc_info=True)
            await interaction.followup.send(
                "❌ Ocurrió un error al crear el ticket. Inténtalo de nuevo.",
                ephemeral=True,
            )


def _get_tickets_cog(interaction: discord.Interaction) -> Optional['Tickets']:
    cog = interaction.client.get_cog("Tickets")
    return cog  # type: ignore[return-value]


class TicketButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def _resolve_ticket_id(self, interaction: discord.Interaction) -> Optional[str]:
        cog = _get_tickets_cog(interaction)
        if not cog:
            await interaction.response.send_message("❌ Sistema de tickets no disponible.", ephemeral=True)
            return None
        ticket = cog.ticket_manager.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("❌ Este canal no es un ticket válido.", ephemeral=True)
            return None
        return ticket["ticket_id"]

    @discord.ui.button(label="Cerrar", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="olimpya:ticket:close")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket_id = await self._resolve_ticket_id(interaction)
        if ticket_id:
            await _get_tickets_cog(interaction).close_ticket(interaction, ticket_id)

    @discord.ui.button(label="Reabrir", style=discord.ButtonStyle.primary, emoji="🔓", custom_id="olimpya:ticket:reopen")
    async def reopen_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket_id = await self._resolve_ticket_id(interaction)
        if ticket_id:
            await _get_tickets_cog(interaction).reopen_ticket(interaction, ticket_id)

    @discord.ui.button(label="Asignar", style=discord.ButtonStyle.success, emoji="👤", custom_id="olimpya:ticket:assign")
    async def assign_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket_id = await self._resolve_ticket_id(interaction)
        if ticket_id:
            await _get_tickets_cog(interaction).assign_ticket(interaction, ticket_id)

    @discord.ui.button(label="Eliminar", style=discord.ButtonStyle.danger, emoji="🗑️", custom_id="olimpya:ticket:delete")
    async def delete_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket_id = await self._resolve_ticket_id(interaction)
        if ticket_id:
            await _get_tickets_cog(interaction).delete_ticket(interaction, ticket_id)


def build_ticket_view(status: str = "open") -> TicketButtonView:
    """Vista de botones del ticket con Cerrar/Reabrir activados según el estado:
    si está cerrado, Cerrar se desactiva y Reabrir se activa (y viceversa)."""
    view = TicketButtonView()
    is_closed = status == "closed"
    for child in view.children:
        cid = getattr(child, "custom_id", "")
        if cid == "olimpya:ticket:close":
            child.disabled = is_closed
        elif cid == "olimpya:ticket:reopen":
            child.disabled = not is_closed
    return view


class ConfirmDeleteView(discord.ui.View):
    """Confirmación efímera antes de borrar el canal del ticket (acción irreversible)."""

    def __init__(self, cog: 'Tickets', ticket_id: str):
        super().__init__(timeout=60)
        self.cog = cog
        self.ticket_id = ticket_id

    @discord.ui.button(label="Sí, eliminar", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket = self.cog.ticket_manager.get_ticket(self.ticket_id)
        await interaction.response.edit_message(content="🗑️ Eliminando el ticket…", view=None)
        self.cog.ticket_manager.delete_ticket(self.ticket_id)
        if ticket and ticket.get("channel_id"):
            channel = interaction.guild.get_channel(ticket["channel_id"])
            if channel:
                try:
                    await channel.delete(
                        reason=f"Ticket {self.ticket_id} eliminado por {interaction.user.name}"
                    )
                except Exception as e:
                    logger.error(f"No se pudo borrar el canal del ticket {self.ticket_id}: {e}")
        logger.info(f"Ticket {self.ticket_id} eliminado por {interaction.user.name}")

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Operación cancelada.", view=None)


class TicketSetupView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.categoria: Optional[str] = None
        self.prioridad: Optional[str] = None

        cat_options = [discord.SelectOption(label=c, value=c) for c in TICKET_CONFIG["categories"]]
        self.cat_select = discord.ui.Select(
            placeholder="Elige una categoría...",
            options=cat_options,
            row=0,
            min_values=1,
            max_values=1,
        )
        self.cat_select.callback = self._on_cat
        self.add_item(self.cat_select)

        pri_options = [discord.SelectOption(label=p, value=p) for p in TICKET_CONFIG["priorities"]]
        self.pri_select = discord.ui.Select(
            placeholder="Elige una prioridad...",
            options=pri_options,
            row=1,
            min_values=1,
            max_values=1,
        )
        self.pri_select.callback = self._on_pri
        self.add_item(self.pri_select)

        self.continue_btn = discord.ui.Button(
            label="Continuar",
            style=discord.ButtonStyle.success,
            emoji="➡️",
            disabled=True,
            row=2,
        )
        self.continue_btn.callback = self._on_continue
        self.add_item(self.continue_btn)

    def _refresh_continue(self):
        self.continue_btn.disabled = not (self.categoria and self.prioridad)

    def _mark_selected(self, select: discord.ui.Select, value: str):
        for opt in select.options:
            opt.default = (opt.value == value)

    async def _on_cat(self, interaction: discord.Interaction):
        self.categoria = self.cat_select.values[0]
        self._mark_selected(self.cat_select, self.categoria)
        self._refresh_continue()
        await interaction.response.edit_message(view=self)

    async def _on_pri(self, interaction: discord.Interaction):
        self.prioridad = self.pri_select.values[0]
        self._mark_selected(self.pri_select, self.prioridad)
        self._refresh_continue()
        await interaction.response.edit_message(view=self)

    async def _on_continue(self, interaction: discord.Interaction):
        cog = _get_tickets_cog(interaction)
        if not cog:
            await interaction.response.send_message("❌ Sistema de tickets no disponible.", ephemeral=True)
            return
        if not (self.categoria and self.prioridad):
            await interaction.response.send_message("❌ Selecciona categoría y prioridad primero.", ephemeral=True)
            return
        await interaction.response.send_modal(TicketModal(cog, self.categoria, self.prioridad))


class CreateTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Crear Ticket", style=discord.ButtonStyle.primary, emoji="📝", custom_id="olimpya:ticket:create")
    async def create_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "**Configura tu ticket**\nElige categoría y prioridad y pulsa Continuar para rellenar el motivo.",
            view=TicketSetupView(),
            ephemeral=True,
        )


class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ticket_manager = TicketManager(TICKET_CONFIG["data_file"])
        self._views_registered = False
        logger.info("Tickets cog initialized")

    async def cog_load(self):
        if not self._views_registered:
            self.bot.add_view(CreateTicketView())
            self.bot.add_view(TicketButtonView())
            self._views_registered = True
            logger.info("Vistas persistentes de tickets registradas")

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("Tickets cog ready")

    @app_commands.command(name="setup-tickets", description="Configura el sistema de tickets en este canal")
    @app_commands.default_permissions(administrator=True)
    async def setup_tickets(self, interaction: discord.Interaction):
        try:
            embed = create_setup_embed()
            view = CreateTicketView()
            await interaction.response.send_message(embed=embed, view=view)
            logger.info(f"Sistema de tickets configurado en {interaction.guild.name} por {interaction.user.name}")
        except Exception as e:
            logger.error(f"Error al configurar tickets: {e}")
            await interaction.response.send_message(
                "❌ No se pudo configurar el sistema de tickets.",
                ephemeral=True
            )

    def create_ticket_buttons(self, ticket_id: str) -> TicketButtonView:
        return build_ticket_view("open")

    async def _refresh_ticket_message(self, interaction: discord.Interaction, ticket_id: str):
        """Reescribe el mensaje del ticket con su embed y botones al estado actual."""
        ticket = self.ticket_manager.get_ticket(ticket_id)
        if not ticket or interaction.message is None:
            return
        try:
            await interaction.message.edit(
                embed=create_ticket_embed(ticket),
                view=build_ticket_view(ticket["status"]),
            )
        except Exception as e:
            logger.error(f"No se pudo refrescar el mensaje del ticket {ticket_id}: {e}")

    async def close_ticket(self, interaction: discord.Interaction, ticket_id: str):
        await interaction.response.defer(ephemeral=True)
        try:
            ticket = self.ticket_manager.get_ticket(ticket_id)
            if not ticket:
                await interaction.followup.send("❌ Ticket no encontrado.", ephemeral=True)
                return

            if ticket["status"] == "closed":
                await interaction.followup.send("ℹ️ Este ticket ya está cerrado.", ephemeral=True)
                return

            staff_role = get_staff_role(interaction.guild)
            is_creator = interaction.user.id == ticket["creator_id"]
            is_staff = user_is_staff(interaction.user, staff_role)

            if not (is_creator or is_staff):
                await interaction.followup.send("❌ No tienes permiso para cerrar este ticket.", ephemeral=True)
                return

            self.ticket_manager.close_ticket(ticket_id)
            channel = interaction.guild.get_channel(ticket["channel_id"])
            if channel:
                await archive_channel(channel)

            await self._refresh_ticket_message(interaction, ticket_id)
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

            if ticket["status"] != "closed":
                await interaction.followup.send("ℹ️ Este ticket no está cerrado.", ephemeral=True)
                return

            staff_role = get_staff_role(interaction.guild)
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
                # Devuelve la escritura al creador (al cerrar se le había quitado).
                creator = interaction.guild.get_member(ticket["creator_id"])
                if creator:
                    try:
                        await channel.set_permissions(
                            creator, read_messages=True, send_messages=True
                        )
                    except Exception:
                        pass

            await self._refresh_ticket_message(interaction, ticket_id)
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

            staff_role = get_staff_role(interaction.guild)
            if not user_is_staff(interaction.user, staff_role):
                await interaction.followup.send("❌ Necesitas ser staff para asignar tickets.", ephemeral=True)
                return

            self.ticket_manager.assign_ticket(ticket_id, interaction.user.id, interaction.user.name)
            await self._refresh_ticket_message(interaction, ticket_id)
            action_embed = create_action_embed(f"Asignado a {interaction.user.name}", interaction.user.name)
            await interaction.followup.send(embed=action_embed, ephemeral=True)
            logger.info(f"Ticket {ticket_id} asignado a {interaction.user.name}")

        except Exception as e:
            logger.error(f"Error al asignar ticket {ticket_id}: {e}")
            await interaction.followup.send("❌ Error al asignar el ticket.", ephemeral=True)

    async def delete_ticket(self, interaction: discord.Interaction, ticket_id: str):
        ticket = self.ticket_manager.get_ticket(ticket_id)
        if not ticket:
            await interaction.response.send_message("❌ Ticket no encontrado.", ephemeral=True)
            return

        staff_role = get_staff_role(interaction.guild)
        if not user_is_staff(interaction.user, staff_role):
            await interaction.response.send_message(
                "❌ Solo el staff puede eliminar tickets.", ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"⚠️ ¿Seguro que quieres **eliminar** el ticket **#{ticket_id}**?\n"
            "Se borrará el canal por completo y **no se puede deshacer**.",
            view=ConfirmDeleteView(self, ticket_id),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))
    logger.info("Tickets cog loaded")

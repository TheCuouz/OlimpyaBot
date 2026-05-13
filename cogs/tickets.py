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


class TicketModal(discord.ui.Modal, title="Create Support Ticket"):
    """Modal form for ticket creation with description, category, and priority."""
    
    description = discord.ui.TextInput(
        label="Description",
        placeholder="Describe your issue in detail",
        style=discord.TextStyle.paragraph,
        required=True,
        min_length=10,
        max_length=1000
    )
    
    def __init__(self, ticket_cog: 'Tickets'):
        super().__init__()
        self.ticket_cog = ticket_cog
        
        # Add category select
        self.category_select = discord.ui.Select(
            placeholder="Select category",
            options=[
                discord.SelectOption(label=cat, value=cat)
                for cat in TICKET_CONFIG["categories"]
            ]
        )
        self.category_select.callback = self.on_category_select
        
        # Add priority select
        self.priority_select = discord.ui.Select(
            placeholder="Select priority",
            options=[
                discord.SelectOption(label=pri, value=pri)
                for pri in TICKET_CONFIG["priorities"]
            ]
        )
        self.priority_select.callback = self.on_priority_select
        
        # Store selections
        self.selected_category = None
        self.selected_priority = None
    
    async def on_category_select(self, interaction: discord.Interaction):
        """Handle category selection."""
        self.selected_category = self.category_select.values[0]
        await interaction.response.defer()
    
    async def on_priority_select(self, interaction: discord.Interaction):
        """Handle priority selection."""
        self.selected_priority = self.priority_select.values[0]
        await interaction.response.defer()
    
    async def on_submit(self, interaction: discord.Interaction):
        """Process modal submission and create ticket."""
        # Validate selections
        if not self.selected_category:
            self.selected_category = TICKET_CONFIG["categories"][0]
        if not self.selected_priority:
            self.selected_priority = TICKET_CONFIG["priorities"][0]
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Create ticket in database
            ticket_id = self.ticket_cog.ticket_manager.create_ticket(
                creator_id=interaction.user.id,
                creator_name=interaction.user.name,
                category=self.selected_category,
                priority=self.selected_priority,
                title=self.description.value[:50] if self.description.value else "No Title",
                description=self.description.value
            )
            
            # Get staff role for channel permissions
            staff_role = get_staff_role(interaction.guild, TICKET_CONFIG["staff_role_name"])
            
            # Create private channel
            channel = await create_ticket_channel(
                interaction.guild,
                ticket_id,
                self.description.value[:30],
                interaction.user,
                staff_role
            )
            
            if not channel:
                await interaction.followup.send(
                    "❌ Failed to create ticket channel. Please try again.",
                    ephemeral=True
                )
                logger.error(f"Failed to create channel for ticket {ticket_id}")
                return
            
            # Update ticket with channel ID
            self.ticket_cog.ticket_manager.update_ticket(
                ticket_id,
                {"channel_id": channel.id}
            )
            
            # Get ticket and send initial message with buttons
            ticket = self.ticket_cog.ticket_manager.get_ticket(ticket_id)
            embed = create_ticket_embed(ticket)
            view = self.ticket_cog.create_ticket_buttons(ticket_id)
            
            await channel.send(embed=embed, view=view)
            
            # Respond to user
            await interaction.followup.send(
                f"✅ Ticket created! Channel: {channel.mention}",
                ephemeral=True
            )
            
            logger.info(f"Ticket {ticket_id} created by {interaction.user.name} in channel {channel.id}")
            
        except Exception as e:
            logger.error(f"Error creating ticket: {e}")
            await interaction.followup.send(
                "❌ An error occurred while creating your ticket. Please try again.",
                ephemeral=True
            )


class TicketButtonView(discord.ui.View):
    """View containing action buttons for ticket management."""
    
    def __init__(self, ticket_cog: 'Tickets', ticket_id: str):
        super().__init__(timeout=None)
        self.ticket_cog = ticket_cog
        self.ticket_id = ticket_id
    
    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Close the ticket."""
        await self.ticket_cog.close_ticket(interaction, self.ticket_id)
    
    @discord.ui.button(label="Reopen", style=discord.ButtonStyle.primary, emoji="🔓")
    async def reopen_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Reopen the ticket."""
        await self.ticket_cog.reopen_ticket(interaction, self.ticket_id)
    
    @discord.ui.button(label="Assign", style=discord.ButtonStyle.success, emoji="👤")
    async def assign_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Assign the ticket to staff."""
        await self.ticket_cog.assign_ticket(interaction, self.ticket_id)


class CreateTicketView(discord.ui.View):
    """View for the setup message with create ticket button."""
    
    def __init__(self, ticket_cog: 'Tickets'):
        super().__init__(timeout=None)
        self.ticket_cog = ticket_cog
    
    @discord.ui.button(label="Create Ticket", style=discord.ButtonStyle.primary, emoji="📝")
    async def create_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show ticket creation modal."""
        await interaction.response.send_modal(TicketModal(self.ticket_cog))


class Tickets(commands.Cog):
    """Main cog for Discord ticket system."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ticket_manager = TicketManager(TICKET_CONFIG["data_file"])
        logger.info("Tickets cog initialized")
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Called when bot is ready."""
        logger.info("Tickets cog ready")
    
    @app_commands.command(name="setup-tickets")
    @app_commands.default_permissions(administrator=True)
    async def setup_tickets(self, interaction: discord.Interaction):
        """
        Admin command to set up the ticket system.
        Sends a message with a button to create tickets.
        """
        # Check permissions
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ You need administrator permissions to use this command.",
                ephemeral=True
            )
            return
        
        try:
            embed = create_setup_embed()
            view = CreateTicketView(self)
            
            await interaction.response.send_message(
                embed=embed,
                view=view
            )
            
            logger.info(f"Ticket system set up in {interaction.guild.name} by {interaction.user.name}")
            
        except Exception as e:
            logger.error(f"Error setting up tickets: {e}")
            await interaction.response.send_message(
                "❌ Failed to set up ticket system. Please try again.",
                ephemeral=True
            )
    
    def create_ticket_buttons(self, ticket_id: str) -> TicketButtonView:
        """Create view with ticket action buttons."""
        return TicketButtonView(self, ticket_id)
    
    async def close_ticket(self, interaction: discord.Interaction, ticket_id: str):
        """Close a ticket and archive the channel."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            ticket = self.ticket_manager.get_ticket(ticket_id)
            
            if not ticket:
                await interaction.followup.send(
                    "❌ Ticket not found.",
                    ephemeral=True
                )
                return
            
            # Check permissions: creator or staff
            staff_role = get_staff_role(interaction.guild, TICKET_CONFIG["staff_role_name"])
            is_creator = interaction.user.id == ticket["creator_id"]
            is_staff = user_is_staff(interaction.user, staff_role)
            
            if not (is_creator or is_staff):
                await interaction.followup.send(
                    "❌ You don't have permission to close this ticket.",
                    ephemeral=True
                )
                return
            
            # Update ticket status
            self.ticket_manager.close_ticket(ticket_id)
            
            # Archive channel
            channel = interaction.guild.get_channel(ticket["channel_id"])
            if channel:
                await archive_channel(channel)
            
            # Send notification
            action_embed = create_action_embed("Closed", interaction.user.name)
            await interaction.followup.send(embed=action_embed, ephemeral=True)
            
            logger.info(f"Ticket {ticket_id} closed by {interaction.user.name}")
            
        except Exception as e:
            logger.error(f"Error closing ticket {ticket_id}: {e}")
            await interaction.followup.send(
                "❌ An error occurred while closing the ticket.",
                ephemeral=True
            )
    
    async def reopen_ticket(self, interaction: discord.Interaction, ticket_id: str):
        """Reopen a closed ticket."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            ticket = self.ticket_manager.get_ticket(ticket_id)
            
            if not ticket:
                await interaction.followup.send(
                    "❌ Ticket not found.",
                    ephemeral=True
                )
                return
            
            # Check permissions: creator or staff
            staff_role = get_staff_role(interaction.guild, TICKET_CONFIG["staff_role_name"])
            is_creator = interaction.user.id == ticket["creator_id"]
            is_staff = user_is_staff(interaction.user, staff_role)
            
            if not (is_creator or is_staff):
                await interaction.followup.send(
                    "❌ You don't have permission to reopen this ticket.",
                    ephemeral=True
                )
                return
            
            # Update ticket status
            self.ticket_manager.reopen_ticket(ticket_id)
            
            # Restore channel name if archived
            channel = interaction.guild.get_channel(ticket["channel_id"])
            if channel:
                new_name = channel.name.replace("✅-", "", 1)
                try:
                    await channel.edit(name=new_name)
                except Exception:
                    pass
            
            # Send notification
            action_embed = create_action_embed("Reopened", interaction.user.name)
            await interaction.followup.send(embed=action_embed, ephemeral=True)
            
            logger.info(f"Ticket {ticket_id} reopened by {interaction.user.name}")
            
        except Exception as e:
            logger.error(f"Error reopening ticket {ticket_id}: {e}")
            await interaction.followup.send(
                "❌ An error occurred while reopening the ticket.",
                ephemeral=True
            )
    
    async def assign_ticket(self, interaction: discord.Interaction, ticket_id: str):
        """Assign ticket to a staff member."""
        await interaction.response.defer(ephemeral=True)
        
        try:
            ticket = self.ticket_manager.get_ticket(ticket_id)
            
            if not ticket:
                await interaction.followup.send(
                    "❌ Ticket not found.",
                    ephemeral=True
                )
                return
            
            # Check permissions: staff only
            staff_role = get_staff_role(interaction.guild, TICKET_CONFIG["staff_role_name"])
            
            if not user_is_staff(interaction.user, staff_role):
                await interaction.followup.send(
                    "❌ You need staff permissions to assign tickets.",
                    ephemeral=True
                )
                return
            
            # Assign to the user who clicked the button
            self.ticket_manager.assign_ticket(
                ticket_id,
                interaction.user.id,
                interaction.user.name
            )
            
            # Send notification
            action_embed = create_action_embed(
                f"Assigned to {interaction.user.name}",
                interaction.user.name
            )
            await interaction.followup.send(embed=action_embed, ephemeral=True)
            
            logger.info(f"Ticket {ticket_id} assigned to {interaction.user.name}")
            
        except Exception as e:
            logger.error(f"Error assigning ticket {ticket_id}: {e}")
            await interaction.followup.send(
                "❌ An error occurred while assigning the ticket.",
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    """Required function to load the cog."""
    await bot.add_cog(Tickets(bot))
    logger.info("Tickets cog loaded")

import discord
from datetime import datetime
from typing import Optional

def create_ticket_embed(ticket: dict) -> discord.Embed:
    embed = discord.Embed(
        title=f"Ticket #{ticket['ticket_id']} - {ticket['title']}",
        description=ticket['description'],
        color=discord.Color.blue()
    )
    embed.add_field(name="Creator", value=f"<@{ticket['creator_id']}>", inline=True)
    embed.add_field(name="Category", value=ticket['category'], inline=True)
    embed.add_field(name="Priority", value=ticket['priority'], inline=True)
    status_color = {"open": "🟢 Open", "closed": "🔴 Closed", "reopened": "🟡 Reopened"}
    embed.add_field(name="Status", value=status_color.get(ticket['status'], ticket['status']), inline=True)
    assigned = ticket.get('assigned_to_name') or "Unassigned"
    embed.add_field(name="Assigned To", value=assigned, inline=True)
    created_at = datetime.fromisoformat(ticket['created_at']).strftime("%Y-%m-%d %H:%M UTC")
    embed.add_field(name="Created", value=created_at, inline=False)
    if ticket['notes']:
        notes_text = f"{len(ticket['notes'])} note(s)"
        embed.add_field(name="Notes", value=notes_text, inline=False)
    embed.set_footer(text="Use buttons below to manage this ticket")
    return embed

def create_setup_embed() -> discord.Embed:
    embed = discord.Embed(
        title="📋 Create a Support Ticket",
        description="Click the button below to create a new support ticket. You'll be asked for a description, category, and priority level.",
        color=discord.Color.blue()
    )
    embed.set_footer(text="OlimpyaBot Ticket System")
    return embed

def create_action_embed(action: str, performed_by: str) -> discord.Embed:
    embed = discord.Embed(
        title="✅ Ticket Updated",
        description=f"Action: {action} by {performed_by}",
        color=discord.Color.green()
    )
    embed.timestamp = datetime.utcnow()
    return embed

def get_channel_name(ticket_id: str, title: str) -> str:
    sanitized = "".join(c if c.isalnum() or c == "-" else "" for c in title.lower().replace(" ", "-"))
    sanitized = sanitized[:20] if sanitized else "ticket"
    return f"ticket-{ticket_id}-{sanitized}"

async def create_ticket_channel(guild: discord.Guild, ticket_id: str, 
                               title: str, creator: discord.Member, 
                               staff_role: Optional[discord.Role] = None) -> Optional[discord.TextChannel]:
    channel_name = get_channel_name(ticket_id, title)
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        creator: discord.PermissionOverwrite(read_messages=True, send_messages=True),
    }
    if staff_role:
        overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
    try:
        channel = await guild.create_text_channel(
            channel_name,
            overwrites=overwrites,
            topic=f"Ticket {ticket_id} - Created by {creator.name}"
        )
        return channel
    except Exception as e:
        return None

async def archive_channel(channel: discord.TextChannel):
    try:
        new_name = f"✅-{channel.name}"
        if len(new_name) > 100:
            new_name = f"✅-{channel.name[-95:]}"
        await channel.edit(name=new_name)
    except Exception as e:
        pass

def get_staff_role(guild: discord.Guild, staff_role_name: str) -> Optional[discord.Role]:
    for role in guild.roles:
        if role.name.lower() == staff_role_name.lower():
            return role
    return None

def user_is_staff(member: discord.Member, staff_role: Optional[discord.Role]) -> bool:
    if not staff_role:
        return member.guild_permissions.administrator
    return staff_role in member.roles or member.guild_permissions.administrator

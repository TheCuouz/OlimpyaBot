import discord
from datetime import datetime
from typing import Optional

def create_ticket_embed(ticket: dict) -> discord.Embed:
    embed = discord.Embed(
        title=f"Ticket #{ticket['ticket_id']} — {ticket['title']}",
        description=ticket['description'],
        color=discord.Color.blue()
    )
    embed.add_field(name="Creado por", value=f"<@{ticket['creator_id']}>", inline=True)
    embed.add_field(name="Categoría", value=ticket['category'], inline=True)
    embed.add_field(name="Prioridad", value=ticket['priority'], inline=True)
    estados = {"open": "🟢 Abierto", "closed": "🔴 Cerrado", "reopened": "🟡 Reabierto"}
    embed.add_field(name="Estado", value=estados.get(ticket['status'], ticket['status']), inline=True)
    asignado = ticket.get('assigned_to_name') or "Sin asignar"
    embed.add_field(name="Asignado a", value=asignado, inline=True)
    creado = datetime.fromisoformat(ticket['created_at']).strftime("%d/%m/%Y %H:%M UTC")
    embed.add_field(name="Creado", value=creado, inline=False)
    if ticket['notes']:
        embed.add_field(name="Notas", value=f"{len(ticket['notes'])} nota(s)", inline=False)
    embed.set_footer(text="Usa los botones para gestionar este ticket")
    return embed

def create_setup_embed() -> discord.Embed:
    embed = discord.Embed(
        title="📋 Crear un ticket de soporte",
        description="Pulsa el botón para abrir un nuevo ticket. Se te pedirá una descripción, categoría y prioridad.",
        color=discord.Color.blue()
    )
    embed.set_footer(text="Sistema de tickets — OlimpyaBot")
    return embed

def create_action_embed(action: str, performed_by: str) -> discord.Embed:
    embed = discord.Embed(
        title="✅ Ticket actualizado",
        description=f"Acción: {action} por {performed_by}",
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
            topic=f"Ticket {ticket_id} — Creado por {creator.name}"
        )
        return channel
    except Exception:
        return None

async def archive_channel(channel: discord.TextChannel):
    try:
        new_name = f"✅-{channel.name}"
        if len(new_name) > 100:
            new_name = f"✅-{channel.name[-95:]}"
        await channel.edit(name=new_name)
    except Exception:
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

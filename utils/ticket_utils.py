import discord
from datetime import datetime, timezone
from typing import Optional


PRIORITY_COLORS = {
    "Low": 0x57F287,
    "Normal": 0x5865F2,
    "High": 0xFEE75C,
    "Urgent": 0xED4245,
}

PRIORITY_EMOJI = {
    "Low": "🟢",
    "Normal": "🔵",
    "High": "🟠",
    "Urgent": "🔴",
}

CATEGORY_EMOJI = {
    "Bug": "🐞",
    "Help": "💬",
    "Licence": "🔑",
}

STATUS_BADGE = {
    "open": ("🟢", "Open", 0x57F287),
    "closed": ("⚫", "Closed", 0x747F8D),
    "reopened": ("🟡", "Reopened", 0xFEE75C),
}


def _divider() -> str:
    return "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"


def create_ticket_embed(ticket: dict) -> discord.Embed:
    status_emoji, status_label, status_color = STATUS_BADGE.get(
        ticket["status"], ("⚪", ticket["status"], 0x99AAB5)
    )
    priority = ticket["priority"]
    color = status_color if ticket["status"] != "open" else PRIORITY_COLORS.get(priority, 0x5865F2)

    cat_emoji = CATEGORY_EMOJI.get(ticket["category"], "📁")
    pri_emoji = PRIORITY_EMOJI.get(priority, "⚪")

    embed = discord.Embed(
        title=f"Ticket #{ticket['ticket_id']}",
        description=(
            f"**{ticket['title']}**\n"
            f"{_divider()}\n"
            f"{ticket['description']}"
        ),
        color=color,
    )

    embed.add_field(name="👤 Opened by", value=f"<@{ticket['creator_id']}>", inline=True)
    embed.add_field(name=f"{cat_emoji} Category", value=f"`{ticket['category']}`", inline=True)
    embed.add_field(name=f"{pri_emoji} Priority", value=f"`{priority}`", inline=True)

    embed.add_field(name=f"{status_emoji} Status", value=f"`{status_label}`", inline=True)
    asignado = (
        f"<@{ticket['assigned_to']}>"
        if ticket.get("assigned_to")
        else "*Unassigned*"
    )
    embed.add_field(name="🛠️ Assigned to", value=asignado, inline=True)

    if ticket.get("notes"):
        embed.add_field(name="📝 Notes", value=f"{len(ticket['notes'])}", inline=True)
    else:
        embed.add_field(name="​", value="​", inline=True)

    created_dt = datetime.fromisoformat(ticket["created_at"]).replace(tzinfo=timezone.utc)
    embed.timestamp = created_dt
    embed.set_footer(text=f"ID {ticket['ticket_id']} • Opened")
    return embed


def create_setup_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🎫  Private support",
        description=(
            "Need help with a plugin you bought? Open a private ticket: only you and the team "
            "can see it.\n"
            "¿Necesitas ayuda con un plugin que compraste? Abre un ticket privado: solo tú y el "
            "equipo lo veréis.\n"
            f"{_divider()}"
        ),
        color=0x5865F2,
    )
    embed.add_field(
        name="📋  What it's for",
        value=(
            "🐞 **Bug** — something doesn't work as it should\n"
            "💬 **Help** — setup, configuration, how do I...\n"
            "🔑 **Licence** — keys, transfers, extra servers, invoices"
        ),
        inline=False,
    )
    embed.add_field(
        name="🐞  For a bug, include",
        value=(
            "Plugin and version · server software and Minecraft version · what you did · "
            "what happened · the full console error"
        ),
        inline=False,
    )
    embed.add_field(
        name="🚀  How",
        value=(
            "Press **Open ticket**, pick a category and a priority, and describe the problem. "
            "A private channel is created for your case."
        ),
        inline=False,
    )
    embed.set_footer(text="TTS Dev SL · Support")
    return embed


def create_action_embed(action: str, performed_by: str) -> discord.Embed:
    embed = discord.Embed(
        description=f"✅  **{action}** by **{performed_by}**",
        color=0x57F287,
    )
    embed.timestamp = datetime.now(timezone.utc)
    return embed


def create_welcome_message(user: discord.Member, ticket: dict, staff_role: Optional[discord.Role]) -> str:
    cat_emoji = CATEGORY_EMOJI.get(ticket["category"], "📁")
    pri_emoji = PRIORITY_EMOJI.get(ticket["priority"], "⚪")
    parts = [
        f"👋  Hi {user.mention}!",
        "",
        f"Your ticket **#{ticket['ticket_id']}** is open.",
        f"{cat_emoji} `{ticket['category']}`  ·  {pri_emoji} `{ticket['priority']}`",
        "",
        "Add any detail, screenshot or log here. ",
    ]
    if staff_role:
        parts[-1] += f"{staff_role.mention} has been notified."
    else:
        parts[-1] += "The team will answer as soon as possible."
    parts.append("When it's solved, press **🔒 Close**.")
    return "\n".join(parts)

def get_channel_name(ticket_id: str, title: str) -> str:
    sanitized = "".join(c if c.isalnum() or c == "-" else "" for c in title.lower().replace(" ", "-"))
    sanitized = sanitized[:20] if sanitized else "ticket"
    return f"ticket-{ticket_id}-{sanitized}"

async def create_ticket_channel(guild: discord.Guild, ticket_id: str,
                               title: str, creator: discord.Member,
                               staff_role: Optional[discord.Role] = None,
                               category: Optional[discord.CategoryChannel] = None) -> Optional[discord.TextChannel]:
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
            category=category,
            topic=f"Ticket {ticket_id} — opened by {creator.name}"
        )
        return channel
    except Exception:
        return None

async def archive_channel(channel: discord.TextChannel):
    """Al cerrar: renombra con ✅ y quita la escritura a los miembros (el creador
    sigue viendo el historial pero ya no puede escribir). El staff conserva acceso."""
    try:
        new_name = f"✅-{channel.name}"
        if len(new_name) > 100:
            new_name = f"✅-{channel.name[-95:]}"
        await channel.edit(name=new_name)
    except Exception:
        pass
    # Revoca la escritura de los overwrites de tipo miembro (el creador del ticket).
    for target, overwrite in list(channel.overwrites.items()):
        if isinstance(target, discord.Member):
            try:
                overwrite.update(send_messages=False)
                await channel.set_permissions(target, overwrite=overwrite)
            except Exception:
                pass

def get_staff_role(guild: discord.Guild) -> Optional[discord.Role]:
    """Resuelve el rol de staff: primero por ID (fiable), luego por nombre."""
    from config import TICKET_CONFIG
    role_id = TICKET_CONFIG.get("staff_role_id") or 0
    if role_id:
        role = guild.get_role(role_id)
        if role:
            return role
    name = TICKET_CONFIG.get("staff_role_name")
    if name:
        for role in guild.roles:
            if role.name.lower() == name.lower():
                return role
    return None

def user_is_staff(member: discord.Member, staff_role: Optional[discord.Role]) -> bool:
    if not staff_role:
        return member.guild_permissions.administrator
    return staff_role in member.roles or member.guild_permissions.administrator

import discord
from datetime import datetime, timezone
from typing import Optional


PRIORITY_COLORS = {
    "Baja": 0x57F287,      # verde
    "Media": 0x5865F2,     # blurple
    "Alta": 0xFEE75C,      # amarillo
    "Crítica": 0xED4245,   # rojo
}

PRIORITY_EMOJI = {
    "Baja": "🟢",
    "Media": "🔵",
    "Alta": "🟠",
    "Crítica": "🔴",
}

CATEGORY_EMOJI = {
    "Bug": "🐞",
    "Soporte": "💬",
    "Sugerencia": "💡",
}

STATUS_BADGE = {
    "open": ("🟢", "Abierto", 0x57F287),
    "closed": ("⚫", "Cerrado", 0x747F8D),
    "reopened": ("🟡", "Reabierto", 0xFEE75C),
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

    embed.add_field(name="👤 Creado por", value=f"<@{ticket['creator_id']}>", inline=True)
    embed.add_field(name=f"{cat_emoji} Categoría", value=f"`{ticket['category']}`", inline=True)
    embed.add_field(name=f"{pri_emoji} Prioridad", value=f"`{priority}`", inline=True)

    embed.add_field(name=f"{status_emoji} Estado", value=f"`{status_label}`", inline=True)
    asignado = (
        f"<@{ticket['assigned_to']}>"
        if ticket.get("assigned_to")
        else "*Sin asignar*"
    )
    embed.add_field(name="🛠️ Asignado a", value=asignado, inline=True)

    if ticket.get("notes"):
        embed.add_field(name="📝 Notas", value=f"{len(ticket['notes'])}", inline=True)
    else:
        embed.add_field(name="​", value="​", inline=True)

    created_dt = datetime.fromisoformat(ticket["created_at"]).replace(tzinfo=timezone.utc)
    embed.timestamp = created_dt
    embed.set_footer(text=f"ID {ticket['ticket_id']} • Creado")
    return embed


def create_setup_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🎫  Sistema de Tickets",
        description=(
            "¿Necesitas ayuda? Abre un ticket privado con el equipo.\n"
            "Solo tú y el staff podréis ver la conversación.\n"
            f"{_divider()}"
        ),
        color=0x5865F2,
    )
    embed.add_field(
        name="📋  ¿Qué puedes reportar?",
        value=(
            "🐞 **Bug** — algo no funciona como debería\n"
            "💬 **Soporte** — necesitas ayuda con algo\n"
            "💡 **Sugerencia** — propones una mejora"
        ),
        inline=False,
    )
    embed.add_field(
        name="⚡  Prioridades",
        value=(
            "🟢 `Baja`  ·  🔵 `Media`  ·  🟠 `Alta`  ·  🔴 `Crítica`"
        ),
        inline=False,
    )
    embed.add_field(
        name="🚀  Cómo abrir uno",
        value=(
            "**1.** Pulsa el botón **Crear Ticket** de abajo\n"
            "**2.** Elige categoría y prioridad\n"
            "**3.** Rellena motivo y descripción\n"
            "**4.** Se creará un canal privado para tu caso"
        ),
        inline=False,
    )
    embed.set_footer(text="OlimpyaBot · Sistema de Tickets")
    return embed


def create_action_embed(action: str, performed_by: str) -> discord.Embed:
    embed = discord.Embed(
        description=f"✅  **{action}** por **{performed_by}**",
        color=0x57F287,
    )
    embed.timestamp = datetime.now(timezone.utc)
    return embed


def create_welcome_message(user: discord.Member, ticket: dict, staff_role: Optional[discord.Role]) -> str:
    cat_emoji = CATEGORY_EMOJI.get(ticket["category"], "📁")
    pri_emoji = PRIORITY_EMOJI.get(ticket["priority"], "⚪")
    parts = [
        f"👋  ¡Hola {user.mention}!",
        "",
        f"Tu ticket **#{ticket['ticket_id']}** ha sido creado correctamente.",
        f"{cat_emoji} `{ticket['category']}`  ·  {pri_emoji} `{ticket['priority']}`",
        "",
        "Describe cualquier detalle adicional aquí. ",
    ]
    if staff_role:
        parts[-1] += f"El equipo {staff_role.mention} ha sido notificado."
    else:
        parts[-1] += "El equipo de staff responderá lo antes posible."
    parts.append("Cuando esté resuelto, pulsa **🔒 Cerrar**.")
    return "\n".join(parts)

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

def get_staff_role(guild: discord.Guild, staff_role_name: str) -> Optional[discord.Role]:
    for role in guild.roles:
        if role.name.lower() == staff_role_name.lower():
            return role
    return None

def user_is_staff(member: discord.Member, staff_role: Optional[discord.Role]) -> bool:
    if not staff_role:
        return member.guild_permissions.administrator
    return staff_role in member.roles or member.guild_permissions.administrator

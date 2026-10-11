"""Welcome of Tiamat Network: a card + a short message in #bienvenida for each new member.

Only the Tiamat guild uses this; TTS Dev SL keeps its own (off) welcome in cogs/events.py.
- join-and-leave within 15 min deletes the card; a rejoin within 24 h gets no second card
- more than 4 joins within 2 s (raid, big wave) -> one grouped message without cards

    python -m utils.tiamat_welcome --prueba [user_id]   test card to #staff-chat, no mentions
"""
import asyncio
import datetime as dt
import io
import json
import os

import discord

from config import TIAMAT_FOUNDER_ROLE_ID, TIAMAT_FOUNDER_UNTIL
from utils import tiamat_card
from utils.logger import logger

TIAMAT_GUILD_ID = 1557892821099348100
CHANNEL_ID = 1557893268883374140     # #bienvenida (read-only; members can still react)
STAFF_CHANNEL_ID = 1557893376362156132
RULES_ID = 1557893272473571520       # #normas
LINKS_ID = 1557893275577352192       # #enlaces
HELP_ID = 1557893332997374002        # #preguntas
CRISTIAN_ID = 229431355845509122
BURST = 4
BURST_WINDOW = 2.0
DELETE_IF_LEFT = dt.timedelta(minutes=15)
NO_REPEAT = dt.timedelta(hours=24)
KEEP = dt.timedelta(days=30)
OPENING_TS = int(tiamat_card.OPENING.timestamp())
FOUNDER_UNTIL = dt.datetime.fromisoformat(TIAMAT_FOUNDER_UNTIL)
FOUNDER_LINE = "-# Has entrado antes de la apertura: eres Fundador 🐉"


def now_utc():
    return dt.datetime.now(dt.timezone.utc)


def is_founder_time(now=None):
    return (now or now_utc()) < FOUNDER_UNTIL


def welcome_text(uid, number, now=None):
    now = now or now_utc()
    when = (f"🎃 Abrimos el **31 de octubre a las 19:30** (hora de México). En tu zona horaria: <t:{OPENING_TS}:f>."
            if now < tiamat_card.OPENING else "🟢 Los servidores ya están abiertos. Entra cuando quieras.")
    return (f"<@{uid}>, te damos la bienvenida a Tiamat Network 🐉 Eres el miembro número **{number}** "
            "y nos alegra tenerte por aquí.\n\n"
            f"📜 Antes de nada, lee las <#{RULES_ID}>. Son cortas.\n"
            "⛏️ Se entra con Minecraft Java, de la 1.8 a la 1.21, en `play.tiamatmc.net`.\n"
            f"{when}\n"
            f"❓ Si te atascas, pregunta en <#{HELP_ID}> y te echamos una mano."
            + (f"\n{FOUNDER_LINE}" if is_founder_time(now) else ""))


def group_text(uids, number):
    names = ", ".join(f"<@{u}>" for u in uids)
    return (f"🐉 Damos la bienvenida a Tiamat Network a {names}. Ya somos **{number}** en el Discord.\n\n"
            f"📜 Las normas están en <#{RULES_ID}> y se entra con Minecraft Java en `play.tiamatmc.net`."
            + ("\n-# Por entrar antes de la apertura, cada uno recibe el rol Fundador 🐉" if is_founder_time() else ""))


def card_name(display, username):
    """Name for the card; falls back to the username when the card fonts can't draw most of it."""
    display = " ".join((display or "").split())
    return display if display and tiamat_card.coverage(display) >= 0.5 else username


def buttons():
    v = discord.ui.View(timeout=None)
    v.add_item(discord.ui.Button(style=discord.ButtonStyle.link, label="Leer las normas", emoji="📜",
                                 url=f"https://discord.com/channels/{TIAMAT_GUILD_ID}/{RULES_ID}"))
    v.add_item(discord.ui.Button(style=discord.ButtonStyle.link, label="Cómo entrar", emoji="⛏️",
                                 url=f"https://discord.com/channels/{TIAMAT_GUILD_ID}/{LINKS_ID}"))
    return v


class WelcomeStore:
    """Who got a card and when (JSON in DATA_DIR), to skip quick rejoins and clean quick leaves."""

    def __init__(self, path):
        self.path = path
        try:
            with open(path, encoding="utf-8") as f:
                self.data = json.load(f)
        except (OSError, ValueError):
            self.data = {}

    def _save(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=1)
        os.replace(tmp, self.path)

    def _age(self, uid, now):
        e = self.data.get(str(uid))
        return (now - dt.datetime.fromisoformat(e["at"])) if e else None

    def recently_welcomed(self, uid, now=None):
        age = self._age(uid, now or now_utc())
        return age is not None and age < NO_REPEAT

    def card_to_delete(self, uid, now=None):
        age = self._age(uid, now or now_utc())
        return self.data[str(uid)]["msg"] if age is not None and age < DELETE_IF_LEFT else None

    def record(self, uids, msg_id, now=None):
        now = now or now_utc()
        for uid in uids:
            self.data[str(uid)] = {"msg": msg_id, "at": now.isoformat()}
        for k in [k for k, v in self.data.items() if now - dt.datetime.fromisoformat(v["at"]) > KEEP]:
            del self.data[k]
        self._save()


async def render(member, number):
    try:
        raw = await member.display_avatar.replace(format="png", size=512).read()
    except Exception as e:
        logger.warning(f"Tiamat: sin avatar de {member} ({e}); va el dragón")
        raw = None
    name = card_name(member.display_name, member.name)
    png = await asyncio.to_thread(tiamat_card.card, name, number, raw)
    return discord.File(io.BytesIO(png), filename="bienvenida.png")


async def send_card(channel, member, number, test=False):
    content = welcome_text(member.id, number)
    if test:
        content = "🧪 **Prueba de la bienvenida** (sin mención; así lo verá cada persona nueva en #bienvenida)\n\n" + content
    msg = await channel.send(content=content, file=await render(member, number), view=buttons(),
                             allowed_mentions=discord.AllowedMentions.none() if test
                             else discord.AllowedMentions(everyone=False, roles=False, users=[member]))
    try:
        await msg.add_reaction("👋")
    except discord.HTTPException:
        pass
    return msg


async def give_founder(member, now=None):
    """Fundador role for anyone who joins before the opening (rejoins included)."""
    if not TIAMAT_FOUNDER_ROLE_ID or not is_founder_time(now):
        return False
    role = member.guild.get_role(TIAMAT_FOUNDER_ROLE_ID)
    if role is None:
        logger.warning(f"Tiamat: el rol Fundador {TIAMAT_FOUNDER_ROLE_ID} no existe")
        return False
    try:
        await member.add_roles(role, reason="Entró antes de la apertura")
        logger.info(f"Tiamat: Fundador para {member}")
        return True
    except Exception as e:
        logger.error(f"Tiamat: no pude dar Fundador a {member}: {e}")
        return False


class TiamatWelcomer:
    def __init__(self, bot, data_dir):
        self.bot = bot
        self.store = WelcomeStore(os.path.join(data_dir, "tiamat_welcome.json"))
        self.pending = []
        self.flusher = None

    async def join(self, member):
        if member.bot:
            return
        await give_founder(member)
        if self.store.recently_welcomed(member.id):
            logger.info(f"Tiamat: {member} vuelve a entrar en menos de 24 h, sin tarjeta")
            return
        self.pending.append(member)
        if self.flusher is None or self.flusher.done():
            self.flusher = asyncio.create_task(self._flush())

    async def _flush(self):
        await asyncio.sleep(BURST_WINDOW)
        batch, self.pending = self.pending, []
        channel = self.bot.get_channel(CHANNEL_ID)
        if channel is None or not batch:
            logger.warning("Tiamat: canal de bienvenida no encontrado")
            return
        try:
            if len(batch) > BURST:
                count = batch[0].guild.member_count or 0
                msg = await channel.send(content=group_text([m.id for m in batch], count), view=buttons(),
                                         allowed_mentions=discord.AllowedMentions(everyone=False, roles=False,
                                                                                  users=batch[:100]))
                self.store.record([m.id for m in batch], msg.id)
                logger.info(f"Tiamat: oleada de {len(batch)} entradas, un solo mensaje ({msg.id})")
                return
            for m in batch:
                msg = await send_card(channel, m, m.guild.member_count or 0)
                self.store.record([m.id], msg.id)
                logger.info(f"Tiamat: bienvenida a {m} ({m.id}) -> {msg.id}")
        except Exception as e:
            logger.error(f"Tiamat: error dando la bienvenida: {e}", exc_info=True)

    async def leave(self, member):
        mid = self.store.card_to_delete(member.id)
        if not mid:
            return
        channel = self.bot.get_channel(CHANNEL_ID)
        try:
            await channel.get_partial_message(mid).delete()
            logger.info(f"Tiamat: {member} se fue a los pocos minutos, tarjeta borrada")
        except Exception as e:
            logger.warning(f"Tiamat: no pude borrar la tarjeta de {member}: {e}")


async def _test(uid):
    from config import DISCORD_TOKEN
    client = discord.Client(intents=discord.Intents.none())
    await client.login(DISCORD_TOKEN)
    try:
        guild = await client.fetch_guild(TIAMAT_GUILD_ID, with_counts=True)
        member = await guild.fetch_member(uid)
        channel = await client.fetch_channel(STAFF_CHANNEL_ID)
        msg = await send_card(channel, member, guild.approximate_member_count or 0, test=True)
        print("prueba enviada:", msg.jump_url)
    finally:
        await client.close()


if __name__ == "__main__":
    import sys
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--prueba" in sys.argv:
        asyncio.run(_test(int(args[0]) if args else CRISTIAN_ID))

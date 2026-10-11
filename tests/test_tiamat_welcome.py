import datetime as dt
import io
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock

from PIL import Image

from config import GUILD_ID
from utils import tiamat_card
from utils.tiamat_welcome import (
    TIAMAT_GUILD_ID, WelcomeStore, card_name, group_text, welcome_text,
)

UTC = dt.timezone.utc


class TestText(unittest.TestCase):
    def test_before_opening_has_date_and_local_time(self):
        t = welcome_text(42, 7, dt.datetime(2026, 10, 20, tzinfo=UTC))
        self.assertTrue(t.startswith("<@42>"))
        self.assertIn("miembro número **7**", t)
        self.assertIn("19:30", t)
        self.assertIn(f"<t:{int(tiamat_card.OPENING.timestamp())}:f>", t)
        self.assertIn("play.tiamatmc.net", t)

    def test_after_opening_drops_the_date(self):
        t = welcome_text(42, 7, dt.datetime(2026, 11, 2, tzinfo=UTC))
        self.assertNotIn("🎃", t)
        self.assertIn("ya están abiertos", t)

    def test_opening_is_mexico_1930(self):
        from zoneinfo import ZoneInfo
        mx = tiamat_card.OPENING.astimezone(ZoneInfo("America/Mexico_City"))
        self.assertEqual((mx.month, mx.day, mx.hour, mx.minute), (10, 31, 19, 30))

    def test_group_mentions_everyone_in_the_wave(self):
        self.assertIn("<@1>, <@2>", group_text([1, 2], 9))


class TestCardName(unittest.TestCase):
    def test_keeps_drawable_names(self):
        self.assertEqual(card_name("José 🔥", "jose"), "José 🔥")

    def test_folds_fancy_letters(self):
        self.assertEqual("".join(c for _, c in tiamat_card.runs("𝓜𝓪𝓽𝓮𝓸")), "Mateo")

    def test_falls_back_to_username(self):
        self.assertEqual(card_name("   ", "mateo"), "mateo")
        self.assertEqual(card_name("​​", "mateo"), "mateo")


class TestCard(unittest.TestCase):
    def check(self, name, avatar=None):
        im = Image.open(io.BytesIO(tiamat_card.card(name, 1234, avatar)))
        self.assertEqual(im.size, (tiamat_card.W, tiamat_card.H))

    def test_tricky_names_render(self):
        for n in ("Memox", "xX_DarkKnightSlayerOfTheEndlessVoid_Xx", "José María de la Fuente Martínez",
                  "👨‍👩‍👧 🇲🇽 🏳️‍🌈", "★ Ñoño ♥"):
            self.check(n)

    def test_broken_avatar_uses_the_dragon(self):
        self.check("Memox", b"not an image")


class TestStore(unittest.TestCase):
    def test_rejoin_and_quick_leave_windows(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "w.json")
            t0 = dt.datetime(2026, 10, 20, 12, tzinfo=UTC)
            WelcomeStore(path).record([5], 99, t0)
            s = WelcomeStore(path)
            self.assertTrue(s.recently_welcomed(5, t0 + dt.timedelta(hours=23)))
            self.assertFalse(s.recently_welcomed(5, t0 + dt.timedelta(hours=25)))
            self.assertEqual(s.card_to_delete(5, t0 + dt.timedelta(minutes=10)), 99)
            self.assertIsNone(s.card_to_delete(5, t0 + dt.timedelta(minutes=20)))
            self.assertIsNone(s.card_to_delete(6, t0))


class TestRouting(unittest.IsolatedAsyncioTestCase):
    def cog(self):
        from cogs.events import Events
        c = Events(MagicMock())
        c.tiamat = MagicMock(join=AsyncMock(), leave=AsyncMock())
        c._log, c._assign_autorole, c._send_welcome = AsyncMock(), AsyncMock(), AsyncMock()
        return c

    def member(self, guild_id):
        m = MagicMock(bot=False)
        m.guild.id = guild_id
        return m

    async def test_tiamat_gets_only_the_card(self):
        c = self.cog()
        m = self.member(TIAMAT_GUILD_ID)
        await c.on_member_join(m)
        await c.on_member_remove(m)
        c.tiamat.join.assert_awaited_once_with(m)
        c.tiamat.leave.assert_awaited_once_with(m)
        c._log.assert_not_awaited()
        c._assign_autorole.assert_not_awaited()
        c._send_welcome.assert_not_awaited()

    async def test_tts_dev_keeps_its_flow(self):
        c = self.cog()
        m = self.member(GUILD_ID)
        await c.on_member_join(m)
        await c.on_member_remove(m)
        self.assertEqual(c._log.await_count, 2)
        c._assign_autorole.assert_awaited_once_with(m)
        c._send_welcome.assert_awaited_once_with(m)
        c.tiamat.join.assert_not_awaited()

    async def test_other_guilds_are_ignored(self):
        c = self.cog()
        await c.on_member_join(self.member(123))
        c._log.assert_not_awaited()
        c.tiamat.join.assert_not_awaited()


class TestFlush(unittest.IsolatedAsyncioTestCase):
    def welcomer(self, d):
        from utils import tiamat_welcome as tw
        bot = MagicMock()
        channel = MagicMock()
        channel.send = AsyncMock(return_value=MagicMock(id=777))
        bot.get_channel.return_value = channel
        w = tw.TiamatWelcomer(bot, d)
        return tw, w, channel

    def member(self, uid):
        m = MagicMock(bot=False, id=uid)
        m.guild.member_count = 40
        return m

    async def test_single_join_gets_a_card(self):
        with tempfile.TemporaryDirectory() as d:
            tw, w, channel = self.welcomer(d)
            orig, tw.BURST_WINDOW = tw.BURST_WINDOW, 0
            tw.send_card = AsyncMock(return_value=MagicMock(id=555))
            try:
                await w.join(self.member(1))
                await w.flusher
            finally:
                tw.BURST_WINDOW = orig
            tw.send_card.assert_awaited_once()
            self.assertEqual(tw.send_card.await_args.args[2], 40)
            self.assertTrue(w.store.recently_welcomed(1))
            await w.join(self.member(1))          # rejoin: nothing queued
            self.assertEqual(w.pending, [])

    async def test_wave_becomes_one_message(self):
        with tempfile.TemporaryDirectory() as d:
            tw, w, channel = self.welcomer(d)
            orig, tw.BURST_WINDOW = tw.BURST_WINDOW, 0.05
            tw.send_card = AsyncMock()
            try:
                for i in range(6):
                    await w.join(self.member(100 + i))
                await w.flusher
            finally:
                tw.BURST_WINDOW = orig
            tw.send_card.assert_not_awaited()
            channel.send.assert_awaited_once()
            self.assertIn("<@100>", channel.send.await_args.kwargs["content"])


class TestChannel(unittest.TestCase):
    def test_cards_go_to_bienvenida(self):
        from utils import tiamat_welcome as tw
        self.assertEqual(tw.CHANNEL_ID, 1557893268883374140)

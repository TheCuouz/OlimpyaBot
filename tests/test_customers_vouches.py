import os
import tempfile
import unittest
from unittest.mock import MagicMock

from utils.customers import ClaimedKeys, normalize_key, product_choices, valid_key
from utils.vouches import VouchStore, all_plugins, quote, stars, vouch_embed


class TestCustomers(unittest.TestCase):
    def test_key_format(self):
        self.assertTrue(valid_key(normalize_key(" tts-abcde-fghjk-mnpqr-stvwx ")))
        self.assertFalse(valid_key("TTS-ABCDE-FGHJK-MNPQR"))
        self.assertFalse(valid_key("TTS-ABCDE-FGHJK-MNPQR-STVWI"))  # I is not in the alphabet

    def test_claimed_keys_persist(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "sub", "claimed.json")
            ClaimedKeys(path).claim("TTS-K", 42, "DominionForge")
            self.assertEqual(ClaimedKeys(path).owner("TTS-K"), 42)
            self.assertIsNone(ClaimedKeys(path).owner("TTS-OTHER"))

    def test_product_choices(self):
        self.assertIn("EnchantsForge V2", product_choices("ench"))
        self.assertEqual(product_choices("zzz"), [])


class TestVouches(unittest.TestCase):
    def test_store_numbers_and_updates(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "vouches.json")
            s = VouchStore(path)
            self.assertEqual(s.next_number(), 1)
            s.save(1, "ParticleForge", 5, 100, 1)
            s.save(2, "ParticleForge", 4, 101, 2)
            s.save(1, "ParticleForge", 3, 100, 1)  # same person, same plugin: same card
            again = VouchStore(path)
            self.assertEqual(again.next_number(), 3)
            self.assertEqual(again.get(1, "particleforge")["rating"], 3)

    def test_card(self):
        member = MagicMock()
        member.display_name = "Steve"
        member.display_avatar.url = "https://cdn/x.png"
        e = vouch_embed(member, "ParticleForge", 5, "Great\n\nplugin", True, 7, "play.example.net")
        self.assertEqual(e.title, "ParticleForge")
        self.assertIn("★★★★★", e.description)
        self.assertIn("> Great", e.description)
        self.assertEqual(e.footer.text, "Vouch #7  ·  TTS Dev SL")
        self.assertIn("particleforge", e.thumbnail.url)
        self.assertEqual(e.fields[0].value, "✔ Verified customer")

    def test_helpers(self):
        self.assertEqual(stars(3), "★★★☆☆")
        self.assertEqual(quote("a\n\nb"), "> a\n>\n> b")
        self.assertIn("ParticleForge", all_plugins())
        self.assertIn("DominionForge", all_plugins())


if __name__ == "__main__":
    unittest.main()

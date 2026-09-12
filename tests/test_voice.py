"""Tests for offline voice control: intent parsing + intent->key routing.

Pure logic — no mic, no audio device, no pygame window, and NO save writes.
The VoiceController mic thread is never started here; we exercise the parser
directly and the router with a fake pygame module, so this stays green headless
(and in CI where vosk/sounddevice/a mic may be absent).
"""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import voice_intents as vi  # noqa: E402
import voice  # noqa: E402


class TestIntentParser(unittest.TestCase):
    def setUp(self):
        self.p = vi.IntentParser()  # no wake word

    def _feed(self, s):
        return self.p.feed(s, now=1.0)

    # --- numbered battle commands (spoken 1-based -> engine 0-based) ---
    def test_attack_class_plus_number(self):
        i = self._feed("sniper three")
        self.assertEqual(i.kind, "attack")
        self.assertEqual(i.payload, {"cls": "sniper", "building": 2})

    def test_attack_each_class(self):
        self.assertEqual(self._feed("enforcer one").payload,
                         {"cls": "enforcer", "building": 0})
        self.assertEqual(self._feed("assassin two").payload,
                         {"cls": "assassin", "building": 1})
        # "demo" is the spoken alias for demolitionist (not in the small model)
        self.assertEqual(self._feed("demo five").payload,
                         {"cls": "demolitionist", "building": 4})

    def test_class_word_alone_just_selects(self):
        self.assertEqual(self._feed("sniper").kind, "select_class")
        self.assertEqual(self._feed("sniper").payload, {"cls": "sniper"})

    def test_heal_number(self):
        self.assertEqual(self._feed("heal three").kind, "heal")
        self.assertEqual(self._feed("heal three").payload, {"building": 2})

    def test_heal_bare(self):
        self.assertEqual(self._feed("heal").kind, "heal")
        self.assertEqual(self._feed("heal").payload, {})

    def test_nuke_number(self):
        self.assertEqual(self._feed("nuke five").payload, {"building": 4})

    def test_nuke_bare(self):
        self.assertEqual(self._feed("nuke").payload, {})

    # --- plain 1:1 keystroke commands ---
    def test_plain_commands(self):
        cases = {
            "mode": ("mode", {}),
            "auto": ("ai_assist", {"on": True}),
            "manual": ("ai_assist", {"on": False}),
            "speed up": ("speed", {"direction": "up"}),
            "speed down": ("speed", {"direction": "down"}),
            "forfeit": ("forfeit", {}),
            "sound": ("sound", {}),
            "map": ("goto", {"screen": "map"}),
            "layout": ("goto", {"screen": "layout"}),
            "quit": ("quit", {}),
            "back": ("back", {}),
            "menu": ("back", {}),
            "next tab": ("next_tab", {}),
            "zoom in": ("zoom", {"direction": "in"}),
            "zoom out": ("zoom", {"direction": "out"}),
            "pan left": ("pan", {"direction": "left"}),
            "reset": ("reset_view", {}),
            "next page": ("page", {"direction": "next"}),
            "previous page": ("page", {"direction": "previous"}),
            "yes": ("confirm", {"value": True}),
            "no": ("confirm", {"value": False}),
        }
        for phrase, (kind, payload) in cases.items():
            i = self._feed(phrase)
            self.assertIsNotNone(i, phrase)
            self.assertEqual(i.kind, kind, phrase)
            self.assertEqual(i.payload, payload, phrase)

    def test_unknown(self):
        self.assertEqual(self._feed("florble wizzle").kind, "unknown")

    def test_vocab_has_no_wake_word(self):
        self.assertNotIn("eve", vi.VOCAB)
        self.assertNotIn("commander", vi.VOCAB)


class TestWakeWordGating(unittest.TestCase):
    def test_wake_word_required_when_set(self):
        p = vi.IntentParser(wake_word="eve", window=4.0)
        self.assertIsNone(p.feed("sniper", now=1.0))          # no wake -> ignored
        i = p.feed("eve sniper", now=2.0)                     # same-utterance
        self.assertEqual(i.kind, "select_class")

    def test_wake_then_command_within_window(self):
        p = vi.IntentParser(wake_word="eve", window=4.0)
        self.assertEqual(p.feed("eve", now=10.0).kind, "wake")
        self.assertEqual(p.feed("heal three", now=11.0).kind, "heal")

    def test_command_after_window_ignored(self):
        p = vi.IntentParser(wake_word="eve", window=4.0)
        p.feed("eve", now=10.0)
        self.assertIsNone(p.feed("heal three", now=20.0))     # window expired


class _FakeKey:
    """Fake pygame key constants + Event/event.post capture for router tests."""
    K_e = 101; K_a = 97; K_s = 115; K_d = 100
    K_h = 104; K_n = 110; K_t = 116; K_q = 113; K_m = 109
    K_TAB = 9; K_EQUALS = 61; K_MINUS = 45; K_ESCAPE = 27; K_r = 114
    K_LEFT = 1; K_RIGHT = 2; K_UP = 3; K_DOWN = 4; K_y = 121
    KEYDOWN = 2; MOUSEBUTTONDOWN = 5


class TestRouterKeyMapping(unittest.TestCase):
    """_key_for_intent should map every keystroke intent, and return None for
    numbered battle commands (which are routed to the session, not a key)."""

    def _key(self, kind, **payload):
        return voice._key_for_intent(vi.Intent(kind, payload), _FakeKey)

    def test_keystroke_intents_map(self):
        self.assertEqual(self._key("select_class", cls="sniper"), _FakeKey.K_s)
        self.assertEqual(self._key("select_class", cls="demolitionist"), _FakeKey.K_d)
        self.assertEqual(self._key("heal"), _FakeKey.K_h)          # bare heal
        self.assertEqual(self._key("nuke"), _FakeKey.K_n)          # bare nuke
        self.assertEqual(self._key("mode"), _FakeKey.K_t)
        self.assertEqual(self._key("ai_assist", on=True), _FakeKey.K_TAB)
        self.assertEqual(self._key("next_tab"), _FakeKey.K_TAB)
        self.assertEqual(self._key("speed", direction="up"), _FakeKey.K_EQUALS)
        self.assertEqual(self._key("speed", direction="down"), _FakeKey.K_MINUS)
        self.assertEqual(self._key("forfeit"), _FakeKey.K_q)
        self.assertEqual(self._key("sound"), _FakeKey.K_m)
        self.assertEqual(self._key("back"), _FakeKey.K_ESCAPE)
        self.assertEqual(self._key("quit"), _FakeKey.K_q)
        self.assertEqual(self._key("zoom", direction="in"), _FakeKey.K_EQUALS)
        self.assertEqual(self._key("pan", direction="left"), _FakeKey.K_LEFT)
        self.assertEqual(self._key("reset_view"), _FakeKey.K_r)
        self.assertEqual(self._key("page", direction="next"), _FakeKey.K_RIGHT)
        self.assertEqual(self._key("confirm", value=True), _FakeKey.K_y)

    def test_numbered_battle_commands_have_no_key(self):
        self.assertIsNone(self._key("attack", cls="sniper", building=2))
        self.assertIsNone(self._key("heal", building=2))
        self.assertIsNone(self._key("nuke", building=4))


class TestModuleNoopFallback(unittest.TestCase):
    """With no controller started, every module call is a safe no-op."""

    def test_calls_before_start_are_safe(self):
        # A fresh module state: no controller started in this process path.
        voice._controller = None
        voice.pump()                                  # must not raise
        self.assertFalse(voice.is_available())
        self.assertEqual(voice.poll_battle_intents(), [])
        voice.set_context("battle")
        voice.stop()                                  # safe before start


if __name__ == "__main__":
    unittest.main()

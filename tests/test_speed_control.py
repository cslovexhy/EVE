"""Tests for battle war-speed control via both the +/- keys and the mouse wheel.

Scroll forward (wheel y>0) speeds up, scroll back (y<0) slows down, over the
same 1x/2x/4x/8x ladder as +/-; both clamp at the ends, and the wheel is
ignored once the battle is over.

Runs under the dummy SDL video/audio driver (no display) and builds throwaway
Empire objects — never calls GameState.save(), so the live saves are untouched.
"""
import os
import sys
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pygame  # noqa: E402
import config  # noqa: E402
import buildings  # noqa: E402
from models import Empire, Member, MemberClass, Rarity, BuildingType  # noqa: E402
from battle_session import BattleSession  # noqa: E402


def _side(name, is_player):
    e = Empire(name=name, is_player=is_player)
    e.setup_buildings()
    layout = [BuildingType.HEADQUARTERS] + [BuildingType.WAREHOUSE] * 8
    e.apply_building_layout(layout)
    e.building_order = buildings.building_order_from_layout(layout)
    e.members = [Member(name=f"{name}{i}", member_class=MemberClass.SNIPER,
                        level=3, rarity=Rarity.COMMON) for i in range(2)]
    for m in e.members:
        m.assigned_building = 0
    e.member_assignments = [[0, 1]] + [[] for _ in range(8)]
    return e


class TestSpeedControl(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        config.SCREEN_WIDTH, config.SCREEN_HEIGHT = 1280, 800
        config.BATTLEFIELD_WIDTH = config.SCREEN_WIDTH - 80
        config.BATTLEFIELD_HEIGHT = (config.SCREEN_HEIGHT - config.BATTLEFIELD_Y
                                     - config.ORDER_PANEL_HEIGHT)
        cls.screen = pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _session(self):
        return BattleSession(self.screen, _side("P", True), _side("E", False))

    def _wheel(self, sess, y):
        pygame.event.post(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=y,
                                             flipped=False, which=0))
        sess._handle_events()

    def test_starts_at_1x(self):
        sess = self._session()
        self.assertEqual(sess.speed, 1)

    def test_scroll_forward_speeds_up_and_clamps(self):
        sess = self._session()
        self._wheel(sess, 1); self.assertEqual(sess.speed, 2)
        self._wheel(sess, 1); self.assertEqual(sess.speed, 4)
        self._wheel(sess, 1); self.assertEqual(sess.speed, 8)
        self._wheel(sess, 1); self.assertEqual(sess.speed, 8)  # clamp at top

    def test_scroll_back_slows_down_and_clamps(self):
        sess = self._session()
        for _ in range(3):
            self._wheel(sess, 1)
        self.assertEqual(sess.speed, 8)
        self._wheel(sess, -1); self.assertEqual(sess.speed, 4)
        self._wheel(sess, -1); self.assertEqual(sess.speed, 2)
        self._wheel(sess, -1); self.assertEqual(sess.speed, 1)
        self._wheel(sess, -1); self.assertEqual(sess.speed, 1)  # clamp at bottom

    def test_plus_minus_keys_still_work(self):
        sess = self._session()
        sess._handle_keydown(pygame.K_EQUALS)
        self.assertEqual(sess.speed, 2)
        sess._handle_keydown(pygame.K_KP_PLUS)
        self.assertEqual(sess.speed, 4)
        sess._handle_keydown(pygame.K_MINUS)
        self.assertEqual(sess.speed, 2)

    def test_wheel_ignored_when_battle_over(self):
        sess = self._session()
        sess.engine.battle_over = True
        self._wheel(sess, 1)
        self.assertEqual(sess.speed, 1)


class TestBattleOverDismiss(unittest.TestCase):
    """The battle-over (victory/defeat) screen proceeds to loot on a left-click
    as well as a key press; right-click there is a no-op, and a left-click
    during a live battle must not end it."""

    @classmethod
    def setUpClass(cls):
        pygame.init()
        config.SCREEN_WIDTH, config.SCREEN_HEIGHT = 1280, 800
        config.BATTLEFIELD_WIDTH = config.SCREEN_WIDTH - 80
        config.BATTLEFIELD_HEIGHT = (config.SCREEN_HEIGHT - config.BATTLEFIELD_Y
                                     - config.ORDER_PANEL_HEIGHT)
        cls.screen = pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _session(self):
        return BattleSession(self.screen, _side("P", True), _side("E", False))

    def _click(self, sess, button):
        pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=button,
                                             pos=(config.SCREEN_WIDTH // 2,
                                                  config.SCREEN_HEIGHT // 2)))
        sess._handle_events()

    def _key(self, sess, key):
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key, mod=0,
                                             unicode="", scancode=0))
        sess._handle_events()

    def test_left_click_dismisses_battle_over(self):
        sess = self._session()
        sess.engine.battle_over = True
        self._click(sess, 1)
        self.assertTrue(sess.finished)

    def test_right_click_does_not_dismiss(self):
        sess = self._session()
        sess.engine.battle_over = True
        self._click(sess, 3)
        self.assertFalse(sess.finished)

    def test_enter_still_dismisses(self):
        sess = self._session()
        sess.engine.battle_over = True
        self._key(sess, pygame.K_RETURN)
        self.assertTrue(sess.finished)

    def test_left_click_during_live_battle_does_not_finish(self):
        sess = self._session()
        self._click(sess, 1)
        self.assertFalse(sess.finished)


if __name__ == "__main__":
    unittest.main()

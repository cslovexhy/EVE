"""Tests for the revamped attack-control scheme:

  * A/S/D/F attack modes -> 1/4, 1/2, Full, Auto (config.ATTACK_MODE_FRACTION)
  * engine.volley_size: how many members a volley fires at each mode (ceil,
    >=1, full/auto = everyone)
  * engine.group_rounds_remaining: ammo expressed as "rounds" that scale by
    1/frac with the mode (the user's example: 2 full demo rounds -> 8 on 1/4)
  * engine.execute_order honours the fractional modes + 'auto' sustained flag
  * orders.OrderSystem.handle_click button routing: left enemy = ESA group,
    right enemy = Demo group, left own = heal, mode-bar click cycles

Builds throwaway Empire/BattleEngine objects — never calls GameState.save(),
so the live saves are untouched.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import config  # noqa: E402
import buildings  # noqa: E402
from models import (Empire, Member, MemberClass, Rarity, BuildingType,  # noqa: E402
                    MemberState, Order, OrderAction)
from engine import BattleEngine  # noqa: E402


def make_member(name, cls, building, level=1, ammo=None):
    m = Member(name=name, member_class=cls, level=level, rarity=Rarity.COMMON)
    m.assigned_building = building
    if ammo is not None:
        m.ammo = ammo
    return m


def build_engine(player_members, player_assign=None):
    """A minimal engine with the given player members all in building 0 and a
    trivial enemy. Enough to exercise ammo/mode math and ordering."""
    player = Empire(name="P", is_player=True)
    player.setup_buildings()
    layout = [BuildingType.HEADQUARTERS] + [BuildingType.WAREHOUSE] * 8
    player.apply_building_layout(layout)
    player.building_order = buildings.building_order_from_layout(layout)
    player.members = player_members
    player.member_assignments = player_assign or (
        [[i for i in range(len(player_members))]] + [[] for _ in range(8)])

    enemy = Empire(name="E", is_player=False)
    enemy.setup_buildings()
    enemy.apply_building_layout(layout)
    enemy.building_order = buildings.building_order_from_layout(layout)
    enemy.members = [make_member("E1", MemberClass.SNIPER, 0)]
    enemy.member_assignments = [[0]] + [[] for _ in range(8)]
    return BattleEngine(player, enemy)


class TestVolleySize(unittest.TestCase):
    def test_fractions_round_up_and_floor_at_one(self):
        self.assertEqual(BattleEngine.volley_size("quarter", 10), 3)   # ceil(2.5)
        self.assertEqual(BattleEngine.volley_size("half", 10), 5)
        self.assertEqual(BattleEngine.volley_size("quarter", 1), 1)    # >=1
        self.assertEqual(BattleEngine.volley_size("half", 1), 1)

    def test_full_auto_once_fire_everyone(self):
        for mode in ("full", "auto", "once"):
            self.assertEqual(BattleEngine.volley_size(mode, 7), 7)

    def test_zero_available(self):
        self.assertEqual(BattleEngine.volley_size("quarter", 0), 0)
        self.assertEqual(BattleEngine.volley_size("full", 0), 0)


class TestGroupRounds(unittest.TestCase):
    def test_demo_example_two_full_rounds_shows_eight_on_quarter(self):
        """The user's spec example: 2 full rounds of demo -> 8 on 1/4 mode."""
        # 10 demos x 2 ammo = 20 ammo. Full round = 10 members, so 2 full rounds.
        demos = [make_member(f"D{i}", MemberClass.DEMOLITIONIST, 0, ammo=2)
                 for i in range(10)]
        eng = build_engine(demos)
        self.assertAlmostEqual(
            eng.group_rounds_remaining(eng.player, [MemberClass.DEMOLITIONIST], "full"),
            2.0)
        self.assertAlmostEqual(
            eng.group_rounds_remaining(eng.player, [MemberClass.DEMOLITIONIST], "quarter"),
            8.0)
        self.assertAlmostEqual(
            eng.group_rounds_remaining(eng.player, [MemberClass.DEMOLITIONIST], "half"),
            4.0)

    def test_esa_group_sums_across_classes(self):
        members = (
            [make_member(f"E{i}", MemberClass.ENFORCER, 0, ammo=4) for i in range(2)]
            + [make_member(f"S{i}", MemberClass.SNIPER, 0, ammo=4) for i in range(2)]
            + [make_member(f"A{i}", MemberClass.ASSASSIN, 0, ammo=4) for i in range(2)]
        )
        eng = build_engine(members)
        esa = [MemberClass.ENFORCER, MemberClass.SNIPER, MemberClass.ASSASSIN]
        # 6 members x 4 ammo = 24 ammo; full round = 6 members -> 4 rounds.
        self.assertAlmostEqual(eng.group_rounds_remaining(eng.player, esa, "full"), 4.0)
        # Quarter: divisor 6*0.25 = 1.5 -> 24/1.5 = 16 rounds.
        self.assertAlmostEqual(eng.group_rounds_remaining(eng.player, esa, "quarter"), 16.0)

    def test_dead_members_do_not_count(self):
        demos = [make_member(f"D{i}", MemberClass.DEMOLITIONIST, 0, ammo=3)
                 for i in range(4)]
        demos[0].state = MemberState.DEAD
        demos[1].state = MemberState.DEAD
        eng = build_engine(demos)
        # Only 2 alive x 3 ammo = 6; full round = 2 -> 3 rounds.
        self.assertAlmostEqual(
            eng.group_rounds_remaining(eng.player, [MemberClass.DEMOLITIONIST], "full"),
            3.0)

    def test_no_members_or_no_ammo_is_zero(self):
        eng = build_engine([make_member("D", MemberClass.DEMOLITIONIST, 0, ammo=0)])
        self.assertEqual(
            eng.group_rounds_remaining(eng.player, [MemberClass.DEMOLITIONIST], "full"),
            0.0)
        self.assertEqual(
            eng.group_rounds_remaining(eng.player, [MemberClass.SNIPER], "full"),
            0.0)


class TestExecuteOrderModes(unittest.TestCase):
    def _attacking(self, eng, cls):
        return [m for m in eng.player.members
                if m.member_class == cls and m.state == MemberState.ATTACKING]

    def test_quarter_orders_ceil_quarter_and_fires_once(self):
        demos = [make_member(f"D{i}", MemberClass.DEMOLITIONIST, 0) for i in range(10)]
        eng = build_engine(demos)
        order = Order(member_class=MemberClass.DEMOLITIONIST, target_building=0,
                      action=OrderAction.ATTACK)
        eng.execute_order(order, eng.player, eng.enemy, attack_mode="quarter")
        att = self._attacking(eng, MemberClass.DEMOLITIONIST)
        self.assertEqual(len(att), 3)                      # ceil(10*0.25)
        self.assertTrue(all(m.attack_once for m in att))   # single volley

    def test_auto_orders_all_and_sustains(self):
        demos = [make_member(f"D{i}", MemberClass.DEMOLITIONIST, 0) for i in range(10)]
        eng = build_engine(demos)
        order = Order(member_class=MemberClass.DEMOLITIONIST, target_building=0,
                      action=OrderAction.ATTACK)
        eng.execute_order(order, eng.player, eng.enemy, attack_mode="auto")
        att = self._attacking(eng, MemberClass.DEMOLITIONIST)
        self.assertEqual(len(att), 10)
        self.assertTrue(all(not m.attack_once for m in att))  # sustained

    def test_full_orders_all_but_single_volley(self):
        demos = [make_member(f"D{i}", MemberClass.DEMOLITIONIST, 0) for i in range(10)]
        eng = build_engine(demos)
        order = Order(member_class=MemberClass.DEMOLITIONIST, target_building=0,
                      action=OrderAction.ATTACK)
        eng.execute_order(order, eng.player, eng.enemy, attack_mode="full")
        att = self._attacking(eng, MemberClass.DEMOLITIONIST)
        self.assertEqual(len(att), 10)
        self.assertTrue(all(m.attack_once for m in att))


class TestClickRouting(unittest.TestCase):
    """OrderSystem.handle_click button + side routing (no pygame display needed
    beyond rects; buildings carry x/y so _building_rect works)."""

    def setUp(self):
        import pygame
        pygame.init()
        from orders import OrderSystem, ESA_CLASSES, DEMO_CLASSES
        self.OrderSystem = OrderSystem
        self.ESA = ESA_CLASSES
        self.DEMO = DEMO_CLASSES

    def _placed(self, side):
        """Two trivial buildings at known positions for a side."""
        from models import Building
        bs = [Building(index=i) for i in range(2)]
        for i, b in enumerate(bs):
            b.x = 100 + i * 300
            b.y = 400
        return bs

    def test_left_click_enemy_returns_esa_group(self):
        os_ = self.OrderSystem()
        enemy = self._placed("enemy")
        res = os_.handle_click((100, 400), [], enemy, button=1)
        self.assertEqual(res[0], "attack_group")
        self.assertEqual(res[1], self.ESA)
        self.assertEqual(res[2], 0)

    def test_right_click_enemy_returns_demo_group(self):
        os_ = self.OrderSystem()
        enemy = self._placed("enemy")
        res = os_.handle_click((400, 400), [], enemy, button=3)
        self.assertEqual(res[0], "attack_group")
        self.assertEqual(res[1], self.DEMO)
        self.assertEqual(res[2], 1)

    def test_left_click_own_returns_heal(self):
        os_ = self.OrderSystem()
        player = self._placed("player")
        res = os_.handle_click((100, 400), player, [], button=1)
        self.assertEqual(res, ("heal_building", 0))

    def test_right_click_own_does_nothing(self):
        os_ = self.OrderSystem()
        player = self._placed("player")
        self.assertIsNone(os_.handle_click((100, 400), player, [], button=3))

    def test_mode_bar_left_click_cycles(self):
        from orders import ATTACK_MODE_BUTTON
        os_ = self.OrderSystem()
        start = ATTACK_MODE_BUTTON.mode_index
        center = ATTACK_MODE_BUTTON.rect.center
        res = os_.handle_click(center, [], [], button=1)
        self.assertIsNone(res)
        self.assertEqual(ATTACK_MODE_BUTTON.mode_index,
                         (start + 1) % len(ATTACK_MODE_BUTTON.MODES))

    def test_set_mode_index(self):
        os_ = self.OrderSystem()
        os_.set_mode_index(0)
        self.assertEqual(os_.attack_mode, "quarter")
        os_.set_mode_index(3)
        self.assertEqual(os_.attack_mode, "auto")


if __name__ == "__main__":
    unittest.main()

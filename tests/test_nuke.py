"""Tests for the reworked nuke mechanics:
  1. Minimum charge to fire (NUKE_MIN_CHARGE = 30%).
  2. One-shot: after firing the silo never recharges that battle.
  3. Distance-based blast falloff (center 100%, orthogonal 70%, diagonal 50%)
     applied to both buildings and members.

Builds throwaway Empire/BattleEngine objects only — never calls
GameState.save(), so the live profile is never touched.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import config  # noqa: E402
from models import Empire, Member, MemberClass, Rarity, BuildingType  # noqa: E402
from engine import BattleEngine  # noqa: E402


def _empire(name="x"):
    e = Empire(name=name)
    e.setup_buildings()
    return e


def _set_building(empire, slot, btype, level=1):
    b = empire.buildings[slot]
    b.building_type = btype
    b.level = level
    b.apply_type_hp()


def _silo_engine(charge_frac):
    """A player with a Lv1 Nuclear Silo charged to `charge_frac`, vs a fresh
    enemy. Returns (engine, player, enemy)."""
    player = _empire("P")
    _set_building(player, 4, BuildingType.NUCLEAR_SILO, level=1)  # center slot
    enemy = _empire("E")
    eng = BattleEngine(player, enemy)
    eng._nuke_charge["player"] = config.BATTLE_DURATION * charge_frac
    return eng, player, enemy


class TestMinCharge(unittest.TestCase):
    def test_below_min_cannot_fire(self):
        eng, player, enemy = _silo_engine(0.29)
        self.assertFalse(eng.nuke_ready(player))
        self.assertFalse(eng.launch_nuke(player, 4))

    def test_at_min_can_fire(self):
        eng, player, enemy = _silo_engine(0.30)
        self.assertTrue(eng.nuke_ready(player))
        self.assertTrue(eng.launch_nuke(player, 4))


class TestOneShot(unittest.TestCase):
    def test_no_recharge_after_firing(self):
        eng, player, enemy = _silo_engine(1.0)
        self.assertTrue(eng.launch_nuke(player, 4))
        # Spent: fraction is None, cannot fire again.
        self.assertIsNone(eng.nuke_charge_fraction(player))
        self.assertFalse(eng.nuke_ready(player))
        self.assertFalse(eng.launch_nuke(player, 4))
        # Charging more time does NOT bring it back.
        eng._update_powers(config.BATTLE_DURATION)
        self.assertIsNone(eng.nuke_charge_fraction(player))

    def test_second_launch_deals_no_damage(self):
        eng, player, enemy = _silo_engine(1.0)
        center = 4
        eng.launch_nuke(player, center)
        hp_after_first = enemy.buildings[center].hp
        eng.launch_nuke(player, center)  # should be a no-op (spent)
        self.assertEqual(enemy.buildings[center].hp, hp_after_first)


class TestBlastFalloff(unittest.TestCase):
    def _fresh_targets(self, eng, enemy):
        # Give every enemy building ample HP so the full nuke damage lands
        # without being clamped by a low max HP (Warehouse is only 500).
        for b in enemy.buildings:
            b.max_hp = 5000
            b.hp = 5000
        return [b.hp for b in enemy.buildings]

    def test_building_falloff_center_ortho_diagonal(self):
        eng, player, enemy = _silo_engine(1.0)  # full charge, no frac scaling
        before = self._fresh_targets(eng, enemy)
        eng.launch_nuke(player, 4)  # center slot 4; 3x3 covers all 9
        dmg = [before[i] - enemy.buildings[i].hp for i in range(9)]
        full = config.NUKE_BUILDING_DAMAGE
        # Center (4): 100%
        self.assertAlmostEqual(dmg[4], full * config.NUKE_SPLASH_CENTER, places=3)
        # Orthogonal neighbours of center = slots 1,3,5,7: 70%
        for i in (1, 3, 5, 7):
            self.assertAlmostEqual(dmg[i], full * config.NUKE_SPLASH_ORTHOGONAL,
                                   places=3)
        # Diagonal neighbours = slots 0,2,6,8: 50%
        for i in (0, 2, 6, 8):
            self.assertAlmostEqual(dmg[i], full * config.NUKE_SPLASH_DIAGONAL,
                                   places=3)

    def test_member_falloff_matches_building_rings(self):
        eng, player, enemy = _silo_engine(1.0)
        # Put a high-HP member in center (4), an orthogonal (1), a diagonal (0).
        # Members apply mitigation uniformly, so compare the RING RATIOS (which
        # cancel mitigation) rather than absolute damage.
        def put(slot):
            m = Member(name=f"m{slot}", member_class=MemberClass.ENFORCER,
                       level=80, rarity=Rarity.SUPER_RARE)
            m.hp = m.max_hp = 100000  # survive the blast so we can read damage
            m.assigned_building = slot
            enemy.members.append(m)
            return m
        c, o, d = put(4), put(1), put(0)
        base_c, base_o, base_d = c.hp, o.hp, d.hp
        eng.launch_nuke(player, 4)
        dmg_c = base_c - c.hp
        dmg_o = base_o - o.hp
        dmg_d = base_d - d.hp
        self.assertGreater(dmg_c, 0)
        # Ratios equal the falloff ratios (mitigation cancels).
        self.assertAlmostEqual(dmg_o / dmg_c,
                               config.NUKE_SPLASH_ORTHOGONAL / config.NUKE_SPLASH_CENTER,
                               places=3)
        self.assertAlmostEqual(dmg_d / dmg_c,
                               config.NUKE_SPLASH_DIAGONAL / config.NUKE_SPLASH_CENTER,
                               places=3)

    def test_charge_fraction_scales_on_top_of_falloff(self):
        eng, player, enemy = _silo_engine(0.50)  # half charge
        for b in enemy.buildings:
            b.max_hp = 5000
            b.hp = 5000
        before = enemy.buildings[4].hp
        eng.launch_nuke(player, 4)
        # Center building damage = full * 0.50 * 1.0
        got = before - enemy.buildings[4].hp
        self.assertAlmostEqual(got, config.NUKE_BUILDING_DAMAGE * 0.50
                               * config.NUKE_SPLASH_CENTER, places=3)

    def test_corner_target_only_hits_four_cells(self):
        eng, player, enemy = _silo_engine(1.0)
        for b in enemy.buildings:
            b.max_hp = 5000
            b.hp = 5000
        before = [b.hp for b in enemy.buildings]
        eng.launch_nuke(player, 0)  # top-left corner
        dmg = [before[i] - enemy.buildings[i].hp for i in range(9)]
        hit = [i for i, d in enumerate(dmg) if d > 0]
        # Corner 0's 3x3-clamped block is slots {0,1,3,4}.
        self.assertEqual(sorted(hit), [0, 1, 3, 4])


class TestFalloffHelper(unittest.TestCase):
    def test_multipliers(self):
        eng, _, _ = _silo_engine(1.0)
        self.assertEqual(eng._nuke_falloff(0, 0), config.NUKE_SPLASH_CENTER)
        self.assertEqual(eng._nuke_falloff(0, 1), config.NUKE_SPLASH_ORTHOGONAL)
        self.assertEqual(eng._nuke_falloff(1, 0), config.NUKE_SPLASH_ORTHOGONAL)
        self.assertEqual(eng._nuke_falloff(1, 1), config.NUKE_SPLASH_DIAGONAL)


class TestNukeStatus(unittest.TestCase):
    def test_no_silo(self):
        p = _empire("P")
        eng = BattleEngine(p, _empire("E"))
        self.assertEqual(eng.nuke_status(p), ("none", None))

    def test_charging_below_min(self):
        eng, player, _ = _silo_engine(0.10)
        state, frac = eng.nuke_status(player)
        self.assertEqual(state, "charging")
        self.assertAlmostEqual(frac, 0.10, places=2)

    def test_ready_at_or_above_min(self):
        eng, player, _ = _silo_engine(0.50)
        state, frac = eng.nuke_status(player)
        self.assertEqual(state, "ready")
        self.assertAlmostEqual(frac, 0.50, places=2)

    def test_spent_after_firing(self):
        eng, player, _ = _silo_engine(1.0)
        eng.launch_nuke(player, 4)
        self.assertEqual(eng.nuke_status(player), ("spent", None))


if __name__ == "__main__":
    unittest.main()

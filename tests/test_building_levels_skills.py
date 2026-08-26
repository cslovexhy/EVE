"""Unit tests for per-building level effects on building POWERS in battle.

Covers the two skills that scale with building level under the agreed design:
  - Hospital: grants +bonus_packs health packs at battle start (0/2/4/6 by level)
  - Nuclear Silo: charges faster at higher level (charge time 100/85/70/55% of
    the battle duration), so nuke_charge_fraction reaches 1.0 sooner.

Builds throwaway Empire/BattleEngine objects only — never calls
GameState.save(), so the live profile is never touched. Building types/levels
are set directly on the empire's buildings (no building_order), so the engine
does not overwrite them at construction.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import config  # noqa: E402
from models import Empire, BuildingType  # noqa: E402
from engine import BattleEngine  # noqa: E402


def _empire():
    e = Empire(name="x")
    e.setup_buildings()
    return e


def _set_building(empire, slot, btype, level=1):
    b = empire.buildings[slot]
    b.building_type = btype
    b.level = level
    b.apply_type_hp()  # clamps level to type max and refreshes HP


class TestHospitalBonusPacks(unittest.TestCase):
    def _packs_with_hospital(self, level):
        player = _empire()
        base = player.health_packs
        _set_building(player, 0, BuildingType.HOSPITAL, level=level)
        BattleEngine(player, _empire())  # __init__ grants the bonus once
        return player.health_packs - base

    def test_no_hospital_no_bonus(self):
        player = _empire()
        base = player.health_packs
        BattleEngine(player, _empire())
        self.assertEqual(player.health_packs, base)

    def test_bonus_scales_with_level(self):
        self.assertEqual(self._packs_with_hospital(1), 0)
        self.assertEqual(self._packs_with_hospital(2), 2)
        self.assertEqual(self._packs_with_hospital(3), 4)
        self.assertEqual(self._packs_with_hospital(4), 6)


class TestSiloChargeScaling(unittest.TestCase):
    def _charge_time(self, level):
        player = _empire()
        _set_building(player, 0, BuildingType.NUCLEAR_SILO, level=level)
        eng = BattleEngine(player, _empire())
        return eng._silo_charge_time(player)

    def test_charge_time_decreases_with_level(self):
        t1 = self._charge_time(1)
        t2 = self._charge_time(2)
        t3 = self._charge_time(3)
        t4 = self._charge_time(4)
        self.assertAlmostEqual(t1, config.BATTLE_DURATION * 1.00)
        self.assertAlmostEqual(t2, config.BATTLE_DURATION * 0.85)
        self.assertAlmostEqual(t3, config.BATTLE_DURATION * 0.70)
        self.assertAlmostEqual(t4, config.BATTLE_DURATION * 0.55)
        self.assertTrue(t1 > t2 > t3 > t4)

    def test_higher_level_charges_to_full_faster(self):
        # After simulating the Lv1 charge time worth of dt, a Lv4 silo (charge
        # time 55% of that) is already fully charged, while a Lv1 silo is not.
        elapsed = config.BATTLE_DURATION * 0.60  # between Lv4 (0.55) and Lv1 (1.0)

        p1 = _empire()
        _set_building(p1, 0, BuildingType.NUCLEAR_SILO, level=1)
        eng1 = BattleEngine(p1, _empire())
        eng1._nuke_charge["player"] = elapsed
        self.assertLess(eng1.nuke_charge_fraction(p1), 1.0)
        self.assertFalse(eng1.nuke_ready(p1))

        p4 = _empire()
        _set_building(p4, 0, BuildingType.NUCLEAR_SILO, level=4)
        eng4 = BattleEngine(p4, _empire())
        eng4._nuke_charge["player"] = elapsed
        self.assertGreaterEqual(eng4.nuke_charge_fraction(p4), 1.0)
        self.assertTrue(eng4.nuke_ready(p4))

    def test_no_silo_fraction_is_none(self):
        player = _empire()
        eng = BattleEngine(player, _empire())
        self.assertIsNone(eng.nuke_charge_fraction(player))


if __name__ == "__main__":
    unittest.main()

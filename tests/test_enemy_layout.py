"""Tests for the per-city enemy base-arrangement permutation (enemy_gen).

The build ladder assigns fixed LOGICAL slot roles; build_enemy then remaps those
onto PHYSICAL grid slots per city so bases are not all identical. These tests
pin the invariants that make the remap safe:

  * deterministic per city (same city -> same arrangement every build)
  * different cities generally differ (diversity restored)
  * the front-row ban holds (HQ/Armory/Hospital/Research Lab/Nuclear Silo never
    land on physical front-row slots 0/3/6)
  * the building+level MULTISET is unchanged (pure repositioning: same roster of
    buildings/levels, so difficulty/net worth are unaffected)

Builds throwaway Empire objects via enemy_gen only — never calls
GameState.save(), so the live saves are untouched.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import config  # noqa: E402
import enemy_gen  # noqa: E402
from models import BuildingType  # noqa: E402

# High power so a fully-built base exists (every specialist present).
_POWER = 500_000
_FRONT = {0, 3, 6}
_BANNED_FRONT = {
    BuildingType.HEADQUARTERS, BuildingType.ARMORY, BuildingType.HOSPITAL,
    BuildingType.RESEARCH_LAB, BuildingType.NUCLEAR_SILO,
}
_NAME_BY_INDEX = {spec["name_index"]: BuildingType(v)
                  for v, spec in config.BUILDING_TYPES.items()}


def _layout(city_id):
    """(layout[9] BuildingType, levels[9]) for a city's enemy base."""
    e = enemy_gen.build_enemy(_POWER, name="X", profile_seed=city_id)
    layout = [_NAME_BY_INDEX[ni] for ni in e.building_order]
    return layout, e.building_levels


_CITIES = [
    "United States/Virginia/Fairfax County/Reston",
    "United States/Virginia/Arlington County/Arlington",
    "United States/California/Los Angeles County/Los Angeles",
    "United States/Texas/Harris County/Houston",
    "United States/New York/Kings County/Brooklyn",
    "United States/Illinois/Cook County/Chicago",
]


class TestSlotPermutation(unittest.TestCase):
    def test_front_row_ban_preserved(self):
        for c in _CITIES:
            layout, _ = _layout(c)
            for slot in _FRONT:
                self.assertNotIn(layout[slot], _BANNED_FRONT,
                                 f"{c}: {layout[slot]} on front slot {slot}")

    def test_front_slots_hold_only_front_roles(self):
        # Front physical slots must always be Sniper Tower, Bunker, Safehouse,
        # or Warehouse (the front-row role category + base fillers).
        allowed = {BuildingType.SNIPER_TOWER, BuildingType.BUNKER,
                   BuildingType.SAFEHOUSE, BuildingType.WAREHOUSE}
        for c in _CITIES:
            layout, _ = _layout(c)
            for slot in _FRONT:
                self.assertIn(layout[slot], allowed, f"{c} slot {slot}")

    def test_deterministic_per_city(self):
        for c in _CITIES:
            a_layout, a_levels = _layout(c)
            b_layout, b_levels = _layout(c)
            self.assertEqual(a_layout, b_layout)
            self.assertEqual(a_levels, b_levels)

    def test_multiset_invariant_vs_ladder(self):
        base_layout, base_levels = enemy_gen._make_layout_and_levels(_POWER)
        base_ms = sorted((bt.value, lv) for bt, lv in zip(base_layout, base_levels))
        for c in _CITIES:
            layout, levels = _layout(c)
            ms = sorted((bt.value, lv) for bt, lv in zip(layout, levels))
            self.assertEqual(ms, base_ms, f"{c} changed the building/level multiset")

    def test_cities_are_diverse(self):
        # Not every city need differ, but the set should not collapse to one
        # arrangement (the bug being fixed). Expect several distinct layouts.
        arrangements = {tuple(bt.value for bt in _layout(c)[0]) for c in _CITIES}
        self.assertGreaterEqual(len(arrangements), 3)

    def test_hq_assignment_follows_permuted_slot(self):
        # The attacker stack (non-enforcers) must be assigned to wherever the HQ
        # actually landed after permutation, not a hardcoded slot.
        for c in _CITIES:
            e = enemy_gen.build_enemy(_POWER, name="X", profile_seed=c)
            layout = [_NAME_BY_INDEX[ni] for ni in e.building_order]
            hq_slot = layout.index(BuildingType.HEADQUARTERS)
            # The HQ slot should hold the most members (the attacker stack).
            counts = [len(a) for a in e.member_assignments]
            self.assertEqual(max(range(9), key=lambda i: counts[i]), hq_slot,
                             f"{c}: attacker stack not on the permuted HQ slot")

    def test_permutation_is_a_valid_bijection(self):
        mapping = enemy_gen.slot_permutation("some/city/id")
        self.assertEqual(sorted(mapping), list(range(9)))
        # Front logical roles map to front physical slots; backline to backline.
        for logical in enemy_gen._FRONT_LOGICAL:
            self.assertIn(mapping[logical], enemy_gen._FRONT_PHYSICAL)
        for logical in enemy_gen._BACKLINE_LOGICAL:
            self.assertIn(mapping[logical], enemy_gen._BACKLINE_PHYSICAL)


if __name__ == "__main__":
    unittest.main()

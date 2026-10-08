"""Tests for the unified-power scaling model and the repeatable 'Challenge
Police' raid-boss feature.

Under the unified model there is no POLICE_LEVEL / flat police override: a
police boss is tougher purely because a city's police_power is much larger than
its underworld_power, so it lands in a higher decade tier (higher member levels
and a deeper build-ladder row). These tests cover the tier math, the skewed
per-member level roll, the build ladder + row/tier mapping, and the police boss.

Builds throwaway Empire objects via enemy_gen only — never calls
GameState.save(), so the live player_profile.json is untouched.
"""
import os
import random
import statistics
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import config  # noqa: E402
import enemy_gen  # noqa: E402
from models import Member, MemberClass, Rarity, BuildingType  # noqa: E402


class TestPowerTier(unittest.TestCase):
    def test_tier_is_clamped_decade(self):
        cases = [(1, 0), (5, 0), (9, 0), (10, 1), (99, 1), (100, 2),
                 (999, 2), (1000, 3), (1_060_611, 6), (36_000_000, 7),
                 (10 ** 9, 7)]
        for power, tier in cases:
            self.assertEqual(enemy_gen.power_tier(power), tier, power)

    def test_tier_floor_for_zero_or_negative(self):
        self.assertEqual(enemy_gen.power_tier(0), 0)
        self.assertEqual(enemy_gen.power_tier(-5), 0)
        self.assertEqual(enemy_gen.power_tier(None), 0)

    def test_level_band_contiguous(self):
        self.assertEqual(enemy_gen.tier_level_band(0), (1, 10))
        self.assertEqual(enemy_gen.tier_level_band(1), (11, 20))
        self.assertEqual(enemy_gen.tier_level_band(7), (71, 80))
        self.assertEqual(enemy_gen.MAX_LEVEL, 80)

    def test_tier_frac_endpoints(self):
        self.assertAlmostEqual(enemy_gen.tier_frac(100), 0.0, places=6)   # floor
        self.assertAlmostEqual(enemy_gen.tier_frac(1000 - 1e-6), 1.0, places=3)


class TestLevelRoll(unittest.TestCase):
    def test_floor_power_all_min_level(self):
        rng = random.Random(0)
        lv = [enemy_gen.roll_member_level(100, rng) for _ in range(300)]
        self.assertEqual(set(lv), {21})  # tier 2 L_min

    def test_ceiling_power_all_max_level(self):
        rng = random.Random(0)
        lv = [enemy_gen.roll_member_level(999.9999, rng) for _ in range(300)]
        self.assertEqual(set(lv), {30})  # tier 2 L_max

    def test_levels_stay_in_band(self):
        rng = random.Random(0)
        for _ in range(500):
            lv = enemy_gen.roll_member_level(5000, rng)  # tier 3 -> 31..40
            self.assertGreaterEqual(lv, 31)
            self.assertLessEqual(lv, 40)

    def test_expected_level_monotonic_within_decade(self):
        def avg(power, n=5000):
            r = random.Random(1)
            return statistics.mean(enemy_gen.roll_member_level(power, r)
                                   for _ in range(n))
        seq = [avg(p) for p in (100, 200, 400, 700, 999)]
        for a, b in zip(seq, seq[1:]):
            self.assertLessEqual(a, b + 0.05)

    def test_skew_front_loads_the_climb(self):
        # At the decade midpoint the skewed average should sit ABOVE the linear
        # midpoint (25.5 for the 21..30 band), proving the skew.
        r = random.Random(2)
        mid = statistics.mean(enemy_gen.roll_member_level(316, r)  # 10**2.5
                              for _ in range(8000))
        self.assertGreater(mid, 25.5)


class TestBuildLadder(unittest.TestCase):
    def test_row0_is_all_warehouse_base(self):
        layout, levels = enemy_gen.ladder_state(0)
        self.assertTrue(all(bt == BuildingType.WAREHOUSE for bt in layout))
        self.assertTrue(all(v == 1 for v in levels))

    def test_row41_is_fully_maxed_base(self):
        layout, levels = enemy_gen.ladder_state(enemy_gen.LADDER_LEN)
        kinds = sorted(bt.value for bt in layout)
        self.assertEqual(kinds, sorted([
            "sniper_tower", "research_lab", "hospital", "bunker",
            "headquarters", "nuclear_silo", "bunker", "armory", "safehouse"]))
        # Everything at its max level (safehouse caps at 3, rest at 4).
        for bt, lvl in zip(layout, levels):
            self.assertEqual(lvl, enemy_gen.buildings.building_max_level(bt))

    def test_research_lab_gated_after_hq_l3(self):
        # Research Lab must not exist until HQ reaches L3 (row 15); it is built
        # at row 16.
        before = enemy_gen.ladder_state(15)[0]
        after = enemy_gen.ladder_state(16)[0]
        self.assertNotIn(BuildingType.RESEARCH_LAB, before)
        self.assertIn(BuildingType.RESEARCH_LAB, after)
        # HQ is L3 by row 15.
        hq_slot = enemy_gen._SLOT["HQ"]
        self.assertEqual(enemy_gen.ladder_state(15)[1][hq_slot], 3)

    def test_nuclear_silo_gated_after_hq_l4(self):
        before = enemy_gen.ladder_state(26)[0]
        after = enemy_gen.ladder_state(27)[0]
        self.assertNotIn(BuildingType.NUCLEAR_SILO, before)
        self.assertIn(BuildingType.NUCLEAR_SILO, after)
        hq_slot = enemy_gen._SLOT["HQ"]
        self.assertEqual(enemy_gen.ladder_state(26)[1][hq_slot], 4)

    def test_slot9_safehouse_gated_after_hq_l4(self):
        s9 = enemy_gen._SLOT["Sf9"]
        self.assertEqual(enemy_gen.ladder_state(27)[0][s9], BuildingType.WAREHOUSE)
        self.assertEqual(enemy_gen.ladder_state(28)[0][s9], BuildingType.SAFEHOUSE)


class TestRowTierMapping(unittest.TestCase):
    def test_tier0_is_base_only(self):
        self.assertEqual(enemy_gen.ladder_row_for_power(5), 0)

    def test_tier_row_spans(self):
        # tier n (1..6) = [1+6(n-1), 6n]; tier 7 = [37, 41].
        self.assertEqual(enemy_gen.tier_row_span(0), (0, 0))
        self.assertEqual(enemy_gen.tier_row_span(1), (1, 6))
        self.assertEqual(enemy_gen.tier_row_span(6), (31, 36))
        self.assertEqual(enemy_gen.tier_row_span(7), (37, enemy_gen.LADDER_LEN))

    def test_within_tier_interpolation(self):
        # Bottom of tier 1 decade -> first row of block; top -> last row.
        self.assertEqual(enemy_gen.ladder_row_for_power(10), 1)
        self.assertEqual(enemy_gen.ladder_row_for_power(99.99), 6)

    def test_top_tier_absorbs_overflow_to_row41(self):
        # A maxed top-tier power reaches the end of the ladder.
        self.assertEqual(enemy_gen.ladder_row_for_power(10 ** 8 - 1),
                         enemy_gen.LADDER_LEN)

    def test_row_monotonic_in_power(self):
        powers = [1, 10, 100, 1000, 10_000, 100_000, 1_000_000,
                  10_000_000, 36_000_000]
        rows = [enemy_gen.ladder_row_for_power(p) for p in powers]
        for a, b in zip(rows, rows[1:]):
            self.assertLessEqual(a, b)


class TestBuildEnemyUnified(unittest.TestCase):
    def test_police_outlevels_gang_because_power_is_larger(self):
        # Same seed; police_power >> underworld_power -> higher tier -> higher
        # member levels. No special override involved.
        gang = enemy_gen.build_enemy(3000, name="G", seed=5)          # tier 3
        police = enemy_gen.build_enemy(900_000, name="P", police=True, seed=5)  # tier 5
        self.assertGreater(max(m.level for m in police.members),
                           max(m.level for m in gang.members))

    def test_stronger_city_builds_further_up_ladder(self):
        weak = enemy_gen.build_enemy(50, seed=1)       # tier 1, low row
        strong = enemy_gen.build_enemy(500_000, seed=1)  # tier 5, high row
        weak_nonwh = sum(1 for b in weak.building_order
                         if b != BuildingType.WAREHOUSE.spec["name_index"])
        strong_nonwh = sum(1 for b in strong.building_order
                           if b != BuildingType.WAREHOUSE.spec["name_index"])
        self.assertGreater(strong_nonwh, weak_nonwh)

    def test_prebuilt_so_engine_wont_randomize(self):
        e = enemy_gen.build_enemy(150000, police=True)
        self.assertTrue(e.building_order)
        self.assertEqual(len(e.member_assignments), 9)
        flat = [i for slot in e.member_assignments for i in slot]
        self.assertEqual(sorted(flat), list(range(len(e.members))))

    def test_member_stats_scale_with_level_unbounded(self):
        low = Member(name="a", member_class=MemberClass.SNIPER, level=15,
                     rarity=Rarity.COMMON).get_stats()["hp"]
        high = Member(name="b", member_class=MemberClass.SNIPER, level=80,
                      rarity=Rarity.COMMON).get_stats()["hp"]
        self.assertGreater(high, low)


class TestDescribe(unittest.TestCase):
    def test_describe_reports_tier_level_band_row(self):
        info = enemy_gen.describe(5000)  # tier 3
        self.assertEqual(info["tier"], 3)
        self.assertEqual(info["level_band"], (31, 40))
        self.assertEqual(info["level"], 40)  # band max (back-compat key)
        self.assertIn("row", info)
        self.assertIn("members", info)

    def test_describe_level_monotonic_and_capped(self):
        weak = enemy_gen.describe(10)["level"]
        strong = enemy_gen.describe(10_000_000)["level"]
        self.assertLessEqual(weak, strong)
        self.assertLessEqual(strong, enemy_gen.MAX_LEVEL)


class TestPoliceReward(unittest.TestCase):
    def test_reward_multiplier_configured(self):
        self.assertGreaterEqual(config.POLICE_REWARD_MULT, 1.0)

    def test_police_reward_scales_with_difficulty(self):
        weak = enemy_gen.police_net_worth(3000)
        strong = enemy_gen.police_net_worth(5_000_000)
        self.assertGreater(strong, weak)

    def test_reward_preview_matches_actual(self):
        """police_net_worth (UI preview) must equal the real built boss's net
        worth even when the real build also passes per_capita_income — levels
        use a separate RNG stream, so income never perturbs them."""
        import game_state
        power = 150000
        preview = enemy_gen.police_net_worth(power)
        boss = enemy_gen.build_enemy(power, police=True,
                                     per_capita_income=120_000)
        self.assertEqual(preview, game_state.empire_net_worth(boss))


if __name__ == "__main__":
    unittest.main()

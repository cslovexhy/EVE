"""Tests for city per-capita-income -> enemy member rarity.

Pure-logic tests: they build throwaway enemy_gen Empire objects and roll
rarities with a seeded RNG only. They never call GameState.save(), so the live
player_profile.json and the profiles/ dir are untouched.
"""
import os
import random
import sys
import unittest
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import config  # noqa: E402
import enemy_gen  # noqa: E402
from models import Rarity  # noqa: E402


class TestPerCapitaIncome(unittest.TestCase):
    def test_income_from_city(self):
        self.assertEqual(
            enemy_gen.per_capita_income({"population": 1000, "gdp_thousands": 50_000}),
            50_000.0)

    def test_income_missing_or_zero_is_zero(self):
        self.assertEqual(enemy_gen.per_capita_income(None), 0.0)
        self.assertEqual(enemy_gen.per_capita_income({}), 0.0)
        self.assertEqual(
            enemy_gen.per_capita_income({"population": 0, "gdp_thousands": 50_000}),
            0.0)
        self.assertEqual(
            enemy_gen.per_capita_income({"population": 1000}), 0.0)  # no gdp


class TestIncomeRarityWeights(unittest.TestCase):
    def test_anchors(self):
        # Lowest bracket and highest bracket are the agreed anchors.
        self.assertEqual(enemy_gen.income_rarity_weights(0), [95, 5, 0, 0])
        self.assertEqual(enemy_gen.income_rarity_weights(10_000), [95, 5, 0, 0])
        self.assertEqual(enemy_gen.income_rarity_weights(1e12), [0, 0, 0, 100])

    def test_bracket_boundaries(self):
        # Bracket rule is income < upper, so a value exactly on a lower edge
        # falls into the next bracket up.
        self.assertEqual(enemy_gen.income_rarity_weights(19_999), [95, 5, 0, 0])
        self.assertEqual(enemy_gen.income_rarity_weights(20_000), [65, 33, 2, 0])
        self.assertEqual(enemy_gen.income_rarity_weights(50_000), [56, 40, 4, 0])
        self.assertEqual(enemy_gen.income_rarity_weights(130_000), [21, 57, 21, 1])

    def test_every_row_sums_to_100(self):
        for upper, weights in config.RARITY_INCOME_BRACKETS:
            self.assertEqual(sum(weights), 100, f"bracket upper={upper}")

    def test_mass_sweeps_rightward(self):
        # As income rises, the expected rarity index (0..3 weighted) is monotone
        # non-decreasing — the distribution's center of mass moves toward rarer.
        incomes = [10_000, 30_000, 50_000, 70_000, 90_000, 110_000, 130_000,
                   150_000, 190_000, 275_000, 450_000, 2_000_000, 1e12]
        prev = -1.0
        for inc in incomes:
            w = enemy_gen.income_rarity_weights(inc)
            center = sum(i * wi for i, wi in enumerate(w)) / sum(w)
            self.assertGreaterEqual(center + 1e-9, prev,
                                    f"center regressed at income {inc}")
            prev = center


class TestRarityRoll(unittest.TestCase):
    def _dist(self, income, n=20000):
        rng = random.Random(42)
        c = Counter()
        for _ in range(n):
            c[enemy_gen._pick_rarity_by_income(income, rng)] += 1
        return c

    def test_low_income_mostly_common_never_super_rare(self):
        c = self._dist(10_000)
        self.assertGreater(c[Rarity.COMMON], 0.85 * sum(c.values()))
        self.assertEqual(c[Rarity.SUPER_RARE], 0)
        self.assertEqual(c[Rarity.RARE], 0)

    def test_top_bracket_all_super_rare(self):
        c = self._dist(50_000_000)
        self.assertEqual(c[Rarity.SUPER_RARE], sum(c.values()))

    def test_mid_income_is_a_mix(self):
        c = self._dist(130_000)
        # All four appear-ish: uncommon dominant, rare meaningful.
        self.assertGreater(c[Rarity.UNCOMMON], c[Rarity.COMMON])
        self.assertGreater(c[Rarity.RARE], 0)


class TestBuildEnemyThreadsIncome(unittest.TestCase):
    def test_high_income_gang_outclasses_low_income_gang(self):
        """Same power, different per-capita income -> the richer city fields a
        strictly rarer-skewed roster."""
        def rare_frac(income):
            e = enemy_gen.build_enemy(5000, per_capita_income=income, seed=7)
            n = len(e.members)
            rare_plus = sum(1 for m in e.members
                            if m.rarity in (Rarity.RARE, Rarity.SUPER_RARE))
            return rare_plus / n
        self.assertLess(rare_frac(30_000), rare_frac(450_000))

    def test_no_income_falls_back_to_legacy_and_is_valid(self):
        e = enemy_gen.build_enemy(5000, seed=7)  # no per_capita_income
        self.assertTrue(all(isinstance(m.rarity, Rarity) for m in e.members))
        self.assertGreater(len(e.members), 0)

    def test_income_rarity_is_deterministic_for_seed(self):
        a = enemy_gen.build_enemy(5000, per_capita_income=120_000, seed=11)
        b = enemy_gen.build_enemy(5000, per_capita_income=120_000, seed=11)
        self.assertEqual([m.rarity for m in a.members],
                         [m.rarity for m in b.members])


if __name__ == "__main__":
    unittest.main()

"""Tests for the Magic-Find-biased loot distribution (models.loot_recruits).

The distribution is Gaussian over member *level* (formulation (A)):
    mu    = lo + (mf/100) * (hi - lo)   peak slides lo -> hi with Magic Find
    sigma = (hi - lo) / 6               fixed, so at MF=0 the +3 sigma edge
                                        sits at the crew midpoint
Each of up to `count` draws is WITHOUT replacement, so recruits are distinct.
The axis is level only (rarity is ignored), and recruits are fresh copies.
"""
import os
import random
import sys
import unittest
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from models import Member, MemberClass, Rarity, Empire, loot_recruits  # noqa: E402


def _crew(levels, rarities=None):
    """Build an Empire whose members have the given levels (one member each).
    Names are unique so distinctness is checkable by name."""
    rarities = rarities or [Rarity.COMMON] * len(levels)
    classes = list(MemberClass)
    members = [
        Member(name=f"M{i}", member_class=classes[i % len(classes)],
               level=lv, rarity=rarities[i])
        for i, lv in enumerate(levels)
    ]
    return Empire(name="crew", members=members)


class TestDistinctAndCopies(unittest.TestCase):
    def test_three_distinct(self):
        crew = _crew(list(range(1, 21)))  # levels 1..20
        rng = random.Random(0)
        picks = loot_recruits(crew, magic_find=50, rng=rng)
        self.assertEqual(len(picks), 3)
        names = [p.name for p in picks]
        self.assertEqual(len(names), len(set(names)))

    def test_fewer_members_than_count(self):
        crew = _crew([5, 9])
        picks = loot_recruits(crew, magic_find=50, count=3,
                              rng=random.Random(1))
        self.assertEqual(len(picks), 2)

    def test_empty(self):
        self.assertEqual(loot_recruits(Empire(name="x", members=[])), [])

    def test_recruits_are_copies(self):
        crew = _crew([5, 10, 15])
        picks = loot_recruits(crew, magic_find=50, rng=random.Random(2))
        picks[0].level = -1
        self.assertTrue(all(m.level >= 0 for m in crew.members))


class TestMagicFindShiftsPeak(unittest.TestCase):
    """Over many samples the *average drawn level* should rise monotonically
    with Magic Find, and MF=0 should keep draws in the lower half."""

    def _avg_level(self, mf, trials=4000):
        # Single-member draws so each trial reflects one sample of the curve.
        levels = list(range(1, 101))  # lo=1, hi=100
        crew = _crew(levels)
        rng = random.Random(12345 + mf)
        total = 0
        for _ in range(trials):
            picks = loot_recruits(crew, magic_find=mf, count=1, rng=rng)
            total += picks[0].level
        return total / trials

    def test_average_rises_with_mf(self):
        a0 = self._avg_level(0)
        a50 = self._avg_level(50)
        a100 = self._avg_level(100)
        self.assertLess(a0, a50)
        self.assertLess(a50, a100)

    def test_mf0_stays_in_lower_half(self):
        # lo=1, hi=100, midpoint ~50.5. At MF=0 the peak is at lo and +3 sigma
        # reaches the midpoint, so the average must sit well below the midpoint.
        self.assertLess(self._avg_level(0), 40)

    def test_mf100_peaks_high(self):
        # Peak at hi=100, so the average must sit well into the upper half.
        self.assertGreater(self._avg_level(100), 60)

    def test_mf0_rarely_exceeds_midpoint(self):
        # Everything above +3 sigma (the midpoint at MF=0) is deep tail:
        # fewer than ~2% of draws should land above the midpoint.
        levels = list(range(1, 101))
        crew = _crew(levels)
        rng = random.Random(999)
        above = 0
        trials = 4000
        for _ in range(trials):
            if loot_recruits(crew, magic_find=0, count=1, rng=rng)[0].level > 50:
                above += 1
        self.assertLess(above / trials, 0.03)


class TestEdgeCases(unittest.TestCase):
    def test_all_same_level_uniform(self):
        # sigma == 0: fall back to uniform; just confirm it returns distinct
        # members without error.
        crew = _crew([7, 7, 7, 7, 7])
        picks = loot_recruits(crew, magic_find=0, count=3, rng=random.Random(3))
        self.assertEqual(len(picks), 3)
        self.assertEqual(len({p.name for p in picks}), 3)

    def test_mf_clamped(self):
        # Out-of-range MF should not raise; clamps to [0, 100].
        crew = _crew(list(range(1, 21)))
        self.assertEqual(len(loot_recruits(crew, magic_find=-20,
                                           rng=random.Random(4))), 3)
        self.assertEqual(len(loot_recruits(crew, magic_find=250,
                                           rng=random.Random(5))), 3)

    def test_level_axis_ignores_rarity(self):
        # A low-level Super Rare should still be drawable at MF=0 (level-only).
        levels = [2, 40, 41, 42, 43, 44, 45, 46, 47, 48]
        rarities = [Rarity.SUPER_RARE] + [Rarity.COMMON] * 9
        crew = _crew(levels, rarities)
        rng = random.Random(7)
        drew_super_rare = False
        for _ in range(2000):
            picks = loot_recruits(crew, magic_find=0, count=1, rng=rng)
            if picks[0].rarity == Rarity.SUPER_RARE:
                drew_super_rare = True
                break
        self.assertTrue(drew_super_rare)


if __name__ == "__main__":
    unittest.main()

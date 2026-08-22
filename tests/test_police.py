"""Tests for the repeatable 'Challenge Police' raid-boss feature.

Builds throwaway Empire objects via enemy_gen only — never calls
GameState.save(), so the live player_profile.json is untouched.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import config  # noqa: E402
import enemy_gen  # noqa: E402
from models import Member, MemberClass, Rarity, BuildingType  # noqa: E402


class TestLevelScaling(unittest.TestCase):
    def test_max_level_raised_above_old_placeholder(self):
        # The old arbitrary cap was 15; the gang curve now has real headroom.
        self.assertGreater(enemy_gen.MAX_LEVEL, 15)

    def test_gang_level_monotonic_and_capped(self):
        weak = enemy_gen.describe(10)["level"]
        strong = enemy_gen.describe(enemy_gen.REFERENCE_MAX_POWER)["level"]
        self.assertLessEqual(weak, strong)
        self.assertLessEqual(strong, enemy_gen.MAX_LEVEL)

    def test_member_stats_scale_with_level_unbounded(self):
        low = Member(name="a", member_class=MemberClass.SNIPER, level=15,
                     rarity=Rarity.COMMON).get_stats()["hp"]
        high = Member(name="b", member_class=MemberClass.SNIPER, level=40,
                      rarity=Rarity.COMMON).get_stats()["hp"]
        self.assertGreater(high, low)


class TestPoliceBoss(unittest.TestCase):
    def test_police_is_elite(self):
        """A police boss out-classes the strongest gang: max roster, elite
        level, and a top-level HQ."""
        police = enemy_gen.build_enemy(200000, name="X Police", police=True)
        self.assertEqual(len(police.members), enemy_gen.MAX_MEMBERS)
        self.assertTrue(all(m.level == enemy_gen.POLICE_LEVEL
                            for m in police.members))
        # HQ is levelled to the max.
        hq_slot = police.building_order.index(
            BuildingType.HEADQUARTERS.spec["name_index"])
        self.assertEqual(police.building_levels[hq_slot], config.HQ_MAX_LEVEL)

    def test_police_outlevels_any_gang(self):
        gang = enemy_gen.build_enemy(enemy_gen.REFERENCE_MAX_POWER, name="G")
        police = enemy_gen.build_enemy(enemy_gen.REFERENCE_MAX_POWER,
                                       name="P", police=True)
        self.assertGreater(max(m.level for m in police.members),
                           max(m.level for m in gang.members))

    def test_police_prebuilt_so_engine_wont_randomize(self):
        police = enemy_gen.build_enemy(150000, police=True)
        self.assertTrue(police.building_order)
        self.assertEqual(len(police.member_assignments), 9)
        # Every member is assigned exactly once.
        flat = [i for slot in police.member_assignments for i in slot]
        self.assertEqual(sorted(flat), list(range(len(police.members))))

    def test_reward_multiplier_configured(self):
        self.assertGreaterEqual(config.POLICE_REWARD_MULT, 1.0)


if __name__ == "__main__":
    unittest.main()

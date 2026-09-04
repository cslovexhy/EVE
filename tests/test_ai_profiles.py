"""Tests for AI targeting personalities (ai_profiles) + their deterministic,
per-city / per-side assignment.

Pure-logic tests: they build throwaway Member/Building objects and enemy_gen
Empire objects only, and never call GameState.save(), so the live
player_profile.json and the profiles/ dir are untouched.
"""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import config  # noqa: E402
import ai_profiles  # noqa: E402
import enemy_gen  # noqa: E402
from models import Building, Member, MemberClass, BuildingType, Rarity  # noqa: E402


def _bldg(bt):
    return Building(index=0, building_type=bt)


def _members(*classes):
    return [Member(name=f"m{i}", member_class=c, level=1, rarity=Rarity.COMMON)
            for i, c in enumerate(classes)]


ARMORY = _bldg(BuildingType.ARMORY)
HOSPITAL = _bldg(BuildingType.HOSPITAL)
WAREHOUSE = _bldg(BuildingType.WAREHOUSE)
RNG = random.Random(0)


class TestBaseValueProfile(unittest.TestCase):
    """The default 'value' profile must reproduce the legacy score exactly:
    building-type value + summed defender values (enforcer weighted)."""

    def test_value_matches_legacy_formula(self):
        prof = ai_profiles.get_profile("value")
        defenders = _members(MemberClass.SNIPER, MemberClass.ENFORCER)
        # armory(20) + sniper(2) + enforcer(1) = 23
        expected = (config.AI_TARGET_SCORE_BUILDING["armory"]
                    + config.AI_TARGET_SCORE_DEFENDER
                    + config.AI_TARGET_SCORE_ENFORCER)
        self.assertEqual(prof.score(ARMORY, defenders, RNG), expected)
        self.assertEqual(expected, 23)

    def test_value_warehouse_default(self):
        prof = ai_profiles.get_profile("value")
        self.assertEqual(prof.score(WAREHOUSE, [], RNG),
                         config.AI_TARGET_SCORE_BUILDING_DEFAULT)

    def test_unknown_name_falls_back_to_default(self):
        self.assertEqual(ai_profiles.get_profile("nope").name,
                         config.AI_PROFILE_DEFAULT)
        self.assertEqual(ai_profiles.get_profile(None).name,
                         config.AI_PROFILE_DEFAULT)


class TestDestroyerProfiles(unittest.TestCase):
    def test_hospital_destroyer_prefers_hospital(self):
        prof = ai_profiles.get_profile("hospital_destroyer")
        hosp = prof.score(HOSPITAL, [], RNG)
        arm = prof.score(ARMORY, [], RNG)
        ware = prof.score(WAREHOUSE, [], RNG)
        self.assertGreater(hosp, arm)
        self.assertGreater(hosp, ware)

    def test_armory_destroyer_prefers_armory(self):
        prof = ai_profiles.get_profile("armory_destroyer")
        self.assertGreater(prof.score(ARMORY, [], RNG),
                           prof.score(HOSPITAL, [], RNG))

    def test_destroyer_degrades_to_value_when_target_absent(self):
        # With the target type gone, scoring is exactly the value model, so a
        # hospital-destroyer facing only warehouse+armory prefers the armory
        # (higher base value) — same as 'value'.
        prof = ai_profiles.get_profile("hospital_destroyer")
        val = ai_profiles.get_profile("value")
        self.assertEqual(prof.score(ARMORY, [], RNG), val.score(ARMORY, [], RNG))
        self.assertEqual(prof.score(WAREHOUSE, [], RNG),
                         val.score(WAREHOUSE, [], RNG))


class TestPathProfiles(unittest.TestCase):
    def _score(self, name, defenders):
        return ai_profiles.get_profile(name).score(WAREHOUSE, defenders, RNG)

    def test_hard_path_prefers_more_defended(self):
        light = self._score("hard_path", _members(MemberClass.SNIPER))
        heavy = self._score("hard_path",
                            _members(MemberClass.SNIPER, MemberClass.ASSASSIN,
                                     MemberClass.DEMOLITIONIST))
        self.assertGreater(heavy, light)

    def test_easy_path_prefers_less_defended(self):
        light = self._score("easy_path", _members(MemberClass.SNIPER))
        heavy = self._score("easy_path",
                            _members(MemberClass.SNIPER, MemberClass.ASSASSIN,
                                     MemberClass.DEMOLITIONIST))
        # easy path: fewer defenders => higher (less negative) score
        self.assertGreater(light, heavy)

    def test_easy_and_hard_are_opposite(self):
        d = _members(MemberClass.SNIPER, MemberClass.ASSASSIN)
        self.assertAlmostEqual(self._score("hard_path", d),
                               -self._score("easy_path", d))


class TestRandomProfile(unittest.TestCase):
    def test_random_in_unit_interval(self):
        prof = ai_profiles.get_profile("random_path")
        rng = random.Random(123)
        for _ in range(20):
            s = prof.score(WAREHOUSE, [], rng)
            self.assertGreaterEqual(s, 0.0)
            self.assertLess(s, 1.0)


class TestDeterministicAssignment(unittest.TestCase):
    def test_same_seed_same_profile(self):
        a = ai_profiles.profile_name_for("va|fairfax|reston")
        b = ai_profiles.profile_name_for("va|fairfax|reston")
        self.assertEqual(a, b)

    def test_stable_across_calls_hash_not_salted(self):
        # md5-based, so it must be identical every call (not PYTHONHASHSEED-salted).
        self.assertEqual(ai_profiles.profile_name_for("stable|city|key"),
                         ai_profiles.profile_name_for("stable|city|key"))

    def test_gang_and_police_independent(self):
        # Police is always the fixed police profile; gang is drawn from the pool.
        police = ai_profiles.profile_name_for("x|y|z", police=True)
        self.assertEqual(police, config.AI_PROFILE_POLICE)

    def test_police_always_hard(self):
        for key in ["a|b|c", "d|e|f", "g|h|i"]:
            self.assertEqual(
                ai_profiles.profile_name_for(key, police=True),
                config.AI_PROFILE_POLICE)

    def test_gang_from_pool(self):
        for key in ["a|b|c", "d|e|f", "g|h|i", "j|k|l"]:
            name = ai_profiles.profile_name_for(key, police=False)
            self.assertIn(name, config.AI_PROFILE_GANG_POOL)

    def test_distribution_covers_multiple_profiles(self):
        # Over many distinct city keys we should see more than one gang profile.
        seen = {ai_profiles.profile_name_for(f"s|c|{i}") for i in range(200)}
        self.assertGreater(len(seen), 1)


class TestEnemyGenIntegration(unittest.TestCase):
    def test_build_enemy_sets_profile_name(self):
        gang = enemy_gen.build_enemy(5000, name="G", profile_seed="va|x|town")
        self.assertTrue(hasattr(gang, "ai_profile_name"))
        self.assertIn(gang.ai_profile_name, config.AI_PROFILE_GANG_POOL)

    def test_police_enemy_gets_police_profile(self):
        boss = enemy_gen.build_enemy(500000, name="P", police=True,
                                     profile_seed="va|x|town")
        self.assertEqual(boss.ai_profile_name, config.AI_PROFILE_POLICE)

    def test_gang_and_police_same_city_may_differ(self):
        seed = "va|arlington|arlington"
        gang = enemy_gen.build_enemy(5000, profile_seed=seed).ai_profile_name
        police = enemy_gen.build_enemy(500000, police=True,
                                       profile_seed=seed).ai_profile_name
        # Police is fixed hard_path; assert it is independent of the gang pick.
        self.assertEqual(police, config.AI_PROFILE_POLICE)
        self.assertIn(gang, config.AI_PROFILE_GANG_POOL)

    def test_build_enemy_deterministic_profile(self):
        seed = "va|loudoun|leesburg"
        a = enemy_gen.build_enemy(3000, profile_seed=seed).ai_profile_name
        b = enemy_gen.build_enemy(3000, profile_seed=seed).ai_profile_name
        self.assertEqual(a, b)

    def test_city_strategies_labels(self):
        s = enemy_gen.city_strategies("va|fairfax|reston")
        self.assertIn("gang", s)
        self.assertIn("police", s)
        # Labels are the human-readable display names.
        self.assertEqual(s["police"],
                         ai_profiles.display_name(config.AI_PROFILE_POLICE))

    def test_describe_includes_strategies_when_seeded(self):
        info = enemy_gen.describe(5000, profile_seed="va|x|town")
        self.assertIn("gang_strategy", info)
        self.assertIn("police_strategy", info)
        info2 = enemy_gen.describe(5000)
        self.assertNotIn("gang_strategy", info2)


if __name__ == "__main__":
    unittest.main()

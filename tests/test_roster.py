"""Tests for the persisted roster, backup force, recruit acquisition, roster
management moves, and war-start cap gating.

All persistence is directed at a temp file — the live player_profile.json is
never touched.
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import config  # noqa: E402
import game_state as gs  # noqa: E402
from models import (Member, MemberClass, Rarity, BuildingType,  # noqa: E402
                    create_starting_roster, top_rarity_recruit,
                    default_player_members)


def _valid(state):
    return gs._valid_assignments(state.member_assignments, len(state.roster))


class TestRosterPersistence(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.remove(self.path)  # start with no file
        self._orig = gs.PROFILE_PATH
        gs.PROFILE_PATH = self.path

    def tearDown(self):
        gs.PROFILE_PATH = self._orig
        if os.path.exists(self.path):
            os.remove(self.path)

    def test_fresh_state_seeds_default_roster(self):
        st = gs.GameState.load()  # no file
        emp = st.build_player_empire()
        self.assertEqual(len(st.roster), 40)
        self.assertEqual(len(emp.members), 40)
        self.assertTrue(_valid(st))

    def test_legacy_save_without_roster_migrates(self):
        # Simulate an old save: 40-member assignments, no roster/backup keys.
        import json
        old = {
            "money": 1000,
            "building_layout": ["headquarters"] + ["warehouse"] * 8,
            "building_levels": [1] * 9,
            "conquered": [],
            "member_assignments": gs.default_member_assignments(default_player_members()),
            "home_city": None,
        }
        with open(self.path, "w") as f:
            json.dump(old, f)
        st = gs.GameState.load()
        self.assertEqual(len(st.roster), 40)
        self.assertEqual(len(st.backup), 0)
        self.assertTrue(_valid(st))

    def test_recruit_roundtrip_persists(self):
        st = gs.GameState.load()
        st.build_player_empire()
        rec = Member(name="Ghost", member_class=MemberClass.ASSASSIN,
                     level=8, rarity=Rarity.SUPER_RARE)
        self.assertTrue(st.add_recruit(rec))
        st.save()
        st2 = gs.GameState.load()
        self.assertEqual([m.name for m in st2.backup], ["Ghost"])
        self.assertEqual(st2.backup[0].rarity, Rarity.SUPER_RARE)
        self.assertEqual(st2.backup[0].level, 8)


class TestAcquisition(unittest.TestCase):
    def test_top_rarity_recruit_picks_best_and_copies(self):
        enemy = create_starting_roster("E", is_player=False)
        # Make one clear best: super rare, high level.
        enemy.members[5].rarity = Rarity.SUPER_RARE
        enemy.members[5].level = 12
        rec = top_rarity_recruit(enemy)
        self.assertEqual(rec.rarity, Rarity.SUPER_RARE)
        self.assertEqual(rec.level, 12)
        # It's a COPY — mutating the recruit must not change the enemy member.
        rec.level = 1
        self.assertEqual(enemy.members[5].level, 12)

    def test_top_rarity_recruit_none_for_empty(self):
        from models import Empire
        self.assertIsNone(top_rarity_recruit(Empire(name="x", members=[])))


class TestRosterMoves(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.remove(self.path)
        self._orig = gs.PROFILE_PATH
        gs.PROFILE_PATH = self.path
        self.st = gs.GameState.load()
        self.st.build_player_empire()

    def tearDown(self):
        gs.PROFILE_PATH = self._orig
        if os.path.exists(self.path):
            os.remove(self.path)

    def test_bench_reindexes_and_keeps_assignments_valid(self):
        st = self.st
        # Bench a middle member; assignments must remain a valid cover of 0..38.
        self.assertTrue(st.move_to_backup(10))
        self.assertEqual(len(st.roster), 39)
        self.assertEqual(len(st.backup), 1)
        self.assertTrue(_valid(st))

    def test_activate_adds_and_assigns(self):
        st = self.st
        st.add_recruit(Member(name="R", member_class=MemberClass.SNIPER,
                              level=5, rarity=Rarity.RARE))
        self.assertTrue(st.move_to_roster(0))
        self.assertEqual(len(st.roster), 41)
        self.assertEqual(len(st.backup), 0)
        self.assertTrue(_valid(st))
        # The new member (last index) must be assigned to some slot.
        new_idx = len(st.roster) - 1
        self.assertTrue(any(new_idx in slot for slot in st.member_assignments))

    def test_kick_removes_from_backup_only(self):
        st = self.st
        st.add_recruit(Member(name="K", member_class=MemberClass.ENFORCER,
                              level=1, rarity=Rarity.COMMON))
        before = len(st.roster)
        self.assertTrue(st.kick_backup(0))
        self.assertEqual(len(st.backup), 0)
        self.assertEqual(len(st.roster), before)
        self.assertTrue(_valid(st))

    def test_backup_cap_enforced(self):
        st = self.st
        for i in range(config.BACKUP_FORCE_CAP):
            self.assertTrue(st.add_recruit(
                Member(name=f"B{i}", member_class=MemberClass.SNIPER,
                       level=1, rarity=Rarity.COMMON)))
        # One over the cap must be rejected.
        self.assertFalse(st.add_recruit(
            Member(name="overflow", member_class=MemberClass.SNIPER,
                   level=1, rarity=Rarity.COMMON)))
        self.assertEqual(len(st.backup), config.BACKUP_FORCE_CAP)


class TestCapGating(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        os.remove(self.path)
        self._orig = gs.PROFILE_PATH
        gs.PROFILE_PATH = self.path

    def tearDown(self):
        gs.PROFILE_PATH = self._orig
        if os.path.exists(self.path):
            os.remove(self.path)

    def test_roster_over_cap_blocks(self):
        st = gs.GameState.load()
        # No HQ -> base cap 40, default roster is exactly 40 -> not over.
        st.building_layout = [BuildingType.WAREHOUSE] * 9
        st.building_levels = [1] * 9
        st.build_player_empire()
        self.assertEqual(st.member_cap(), config.BASE_MEMBER_CAP)
        self.assertFalse(st.roster_over_cap())
        # Activate a recruit -> 41 > 40 -> now over cap (war start must block).
        st.add_recruit(Member(name="X", member_class=MemberClass.SNIPER,
                              level=1, rarity=Rarity.COMMON))
        st.move_to_roster(0)
        self.assertEqual(len(st.roster), 41)
        self.assertTrue(st.roster_over_cap())

    def test_hq_level_raises_cap(self):
        st = gs.GameState.load()
        st.building_layout = [BuildingType.HEADQUARTERS] + [BuildingType.WAREHOUSE] * 8
        st.building_levels = [4] + [1] * 8
        self.assertEqual(st.member_cap(),
                         config.BASE_MEMBER_CAP + config.HQ_MEMBERS_PER_LEVEL * 4)


if __name__ == "__main__":
    unittest.main()

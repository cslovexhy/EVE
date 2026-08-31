"""EVE - Tests for the multi-profile save system (src/profiles.py).

All filesystem work is directed at a temp sandbox — the live player_profile.json
and any real profiles/ directory are never touched.
"""
import json
import os
import sys
import tempfile
import shutil
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import game_state as gs  # noqa: E402
import profiles  # noqa: E402


class TestProfiles(unittest.TestCase):
    def setUp(self):
        self.sandbox = tempfile.mkdtemp()
        self._orig_dir = profiles.PROFILES_DIR
        self._orig_legacy = profiles.LEGACY_PATH
        profiles.PROFILES_DIR = os.path.join(self.sandbox, "profiles")
        profiles.LEGACY_PATH = os.path.join(self.sandbox, "player_profile.json")

    def tearDown(self):
        profiles.PROFILES_DIR = self._orig_dir
        profiles.LEGACY_PATH = self._orig_legacy
        shutil.rmtree(self.sandbox, ignore_errors=True)

    def test_empty_list(self):
        self.assertEqual(profiles.list_profiles(), [])

    def test_create_and_list(self):
        st = profiles.create_profile("My Hero")
        self.assertIsNotNone(st)
        self.assertEqual(st.profile_name, "My Hero")
        self.assertTrue(os.path.basename(st.path), "my_hero.json")
        self.assertEqual(profiles.list_profiles(), ["my_hero"])

    def test_slugify(self):
        self.assertEqual(profiles._slugify("My Hero"), "my_hero")
        self.assertEqual(profiles._slugify("  Spaces  "), "spaces")
        self.assertEqual(profiles._slugify("weird!@#chars"), "weirdchars")
        self.assertEqual(profiles._slugify(""), "profile")
        self.assertEqual(profiles._slugify("!!!"), "profile")

    def test_duplicate_rejected(self):
        profiles.create_profile("Dup")
        self.assertIsNone(profiles.create_profile("Dup"))
        # slug collision (different case / spacing maps to same slug)
        self.assertIsNone(profiles.create_profile("dup"))

    def test_blank_rejected(self):
        self.assertIsNone(profiles.create_profile("   "))
        self.assertIsNone(profiles.create_profile(""))

    def test_save_load_roundtrip(self):
        st = profiles.create_profile("Save Test")
        st.money = 4242
        st.home_city = "United States/Virginia/Richmond city/Richmond city"
        st.save()
        loaded = profiles.load_profile("save_test")
        self.assertEqual(loaded.money, 4242)
        self.assertEqual(loaded.profile_name, "Save Test")
        self.assertEqual(loaded.path, st.path)

    def test_summarize(self):
        st = profiles.create_profile("Summ")
        st.money = 900
        st.conquered = {"a", "b", "c"}
        st.home_city = "United States/Virginia/Richmond city/Richmond city"
        st.save()
        s = profiles.summarize("summ")
        self.assertEqual(s["name"], "Summ")
        self.assertEqual(s["money"], 900)
        self.assertEqual(s["conquered"], 3)
        self.assertIsNotNone(s["home"])

    def test_delete(self):
        profiles.create_profile("Gone")
        self.assertTrue(profiles.delete_profile("gone"))
        self.assertEqual(profiles.list_profiles(), [])
        self.assertFalse(profiles.delete_profile("gone"))  # already gone

    def test_profile_exists(self):
        profiles.create_profile("Exists")
        self.assertTrue(profiles.profile_exists("Exists"))
        self.assertTrue(profiles.profile_exists("exists"))  # slug match
        self.assertFalse(profiles.profile_exists("Nope"))

    def test_migrate_legacy(self):
        # A legacy save exists, no profiles yet -> migrated to 'default'.
        json.dump({"money": 555, "conquered": ["x", "y"], "home_city": "c"},
                  open(profiles.LEGACY_PATH, "w"))
        profiles.migrate_legacy()
        self.assertEqual(profiles.list_profiles(), ["default"])
        s = profiles.summarize("default")
        self.assertEqual(s["money"], 555)
        self.assertEqual(s["conquered"], 2)

    def test_migrate_is_idempotent(self):
        json.dump({"money": 1}, open(profiles.LEGACY_PATH, "w"))
        profiles.migrate_legacy()
        # A second call must not overwrite or duplicate.
        profiles.create_profile("Other")
        profiles.migrate_legacy()  # profiles already exist -> no-op
        self.assertIn("default", profiles.list_profiles())
        self.assertIn("other", profiles.list_profiles())
        self.assertEqual(len(profiles.list_profiles()), 2)

    def test_migrate_no_legacy_noop(self):
        # No legacy file -> nothing created.
        profiles.migrate_legacy()
        self.assertEqual(profiles.list_profiles(), [])


if __name__ == "__main__":
    unittest.main()

"""Unit tests for fog-of-war visibility (flood-fill + Research Lab reveal).

Builds throwaway Empire/BattleEngine objects only — never calls
GameState.save(), so the live player_profile.json is untouched.

Grid indices (labelled building N == index N-1):
    slots: 0 1 2 / 3 4 5 / 6 7 8
    adjacency is 4-neighbour (no diagonals).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from models import Empire, BuildingType  # noqa: E402
from engine import BattleEngine  # noqa: E402
import config  # noqa: E402


def _empire():
    e = Empire(name="x")
    e.setup_buildings()
    return e


class TestVisibility(unittest.TestCase):
    def _engine(self, player_lab=False):
        player, enemy = _empire(), _empire()
        if player_lab:
            player.buildings[7].building_type = BuildingType.RESEARCH_LAB
        return BattleEngine(player, enemy), player, enemy

    def test_entry_point_floodfill_without_lab(self):
        # Destroying an entry-point building (index 0) reveals its neighbours
        # (indices 1 and 3).
        eng, player, enemy = self._engine()
        enemy.buildings[0].destroyed = True
        vis = eng._compute_visibility(enemy, assassin_entry=False)
        self.assertIn(1, vis)
        self.assertIn(3, vis)

    def test_lab_reveals_expected_set(self):
        eng, player, enemy = self._engine(player_lab=True)
        vis = eng._compute_visibility(enemy, assassin_entry=False)
        for idx in config.RESEARCH_LAB_REVEAL:  # (3, 4, 6, 7, 8)
            self.assertIn(idx, vis)

    def test_destroying_lab_revealed_building_propagates(self):
        # The reported bug: with a Research Lab, building 5 (index 4) is
        # directly visible. Destroying it must reveal its neighbours —
        # notably building 2 (index 1), which is NOT otherwise visible.
        eng, player, enemy = self._engine(player_lab=True)

        before = eng._compute_visibility(enemy, assassin_entry=False)
        self.assertIn(4, before)      # bldg 5 visible via lab
        self.assertNotIn(1, before)   # bldg 2 hidden

        enemy.buildings[4].destroyed = True
        after = eng._compute_visibility(enemy, assassin_entry=False)
        self.assertIn(1, after)       # bldg 2 now revealed (index 4 neighbour)
        # index 4's other neighbours: 3 (already visible), 5, 7 (already visible)
        self.assertIn(5, after)

    def test_chained_reveal_through_multiple_destroyed(self):
        # Destroy building 5 (index 4) then building 2 (index 1): visibility
        # should chain up to building 1/3 (indices 0/2) via the flood-fill.
        eng, player, enemy = self._engine(player_lab=True)
        enemy.buildings[4].destroyed = True
        enemy.buildings[1].destroyed = True
        vis = eng._compute_visibility(enemy, assassin_entry=False)
        # index 1's neighbours are 0, 2, 4 → 0 and 2 revealed.
        self.assertIn(0, vis)
        self.assertIn(2, vis)

    def test_isolated_destroyed_building_reveals_neighbours(self):
        # Rule: ANY building adjacent to a destroyed building is visible — even
        # if that destroyed building is NOT connected to an entry point through
        # other destroyed buildings (e.g. a nuked backline building). No lab.
        eng, player, enemy = self._engine(player_lab=False)
        # Index 8 (building 9) is only an entry point for assassins; disable
        # the assassin entry so index 8 is otherwise hidden, then destroy the
        # isolated index 5 (building 6) in the back-right.
        enemy.buildings[5].destroyed = True
        vis = eng._compute_visibility(enemy, assassin_entry=False)
        # index 5's neighbours are 2, 4, 8 → all revealed by the destroyed bldg,
        # none of which are entry points.
        self.assertIn(2, vis)
        self.assertIn(4, vis)
        self.assertIn(8, vis)
        # The destroyed building itself is visible.
        self.assertIn(5, vis)


if __name__ == "__main__":
    unittest.main()

"""Tests for the visual US map: adjacency-based state unlocking, color buckets,
and the point-in-polygon hit test. Pure logic — no pygame, no save writes.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import config  # noqa: E402
import world_map as wm  # noqa: E402


class TestAdjacencyUnlock(unittest.TestCase):
    def test_map_data_loaded(self):
        self.assertGreaterEqual(len(wm.US_MAP["states"]), 48)
        self.assertIn("VA", wm.US_MAP["states"])
        self.assertIn("VA", wm.US_MAP["adjacency"])

    def test_home_state_always_unlocked(self):
        self.assertTrue(
            wm.state_unlocked("United States", "Virginia", set(),
                              home_state="Virginia"))

    def test_neighbor_locked_with_nothing_conquered(self):
        self.assertFalse(
            wm.state_unlocked("United States", "North Carolina", set(),
                              home_state="Virginia"))

    def test_neighbor_unlocks_when_home_hits_threshold(self):
        va = wm.state_city_ids("United States", "Virginia")
        # Conquer enough VA cities to clear a 1% threshold.
        n = max(1, int(len(va) * 0.02))
        conquered = set(va[:n])
        # NC borders VA -> unlocked; Montana does not -> still locked.
        self.assertTrue(
            wm.state_unlocked("United States", "North Carolina", conquered,
                              home_state="Virginia", threshold=0.01))
        self.assertFalse(
            wm.state_unlocked("United States", "Montana", conquered,
                              home_state="Virginia", threshold=0.01))

    def test_adjacency_is_symmetric(self):
        adj = wm.US_MAP["adjacency"]
        for a, nbrs in adj.items():
            for b in nbrs:
                self.assertIn(a, adj.get(b, []),
                              f"{a}->{b} not mirrored by {b}->{a}")

    def test_threshold_respected(self):
        va = wm.state_city_ids("United States", "Virginia")
        conquered = set(va[:1])  # ~0.4% of 241 cities
        # Below a 50% bar the neighbour stays locked...
        self.assertFalse(
            wm.state_unlocked("United States", "North Carolina", conquered,
                              home_state="Virginia", threshold=0.50))
        # ...but clears a 0.1% bar.
        self.assertTrue(
            wm.state_unlocked("United States", "North Carolina", conquered,
                              home_state="Virginia", threshold=0.001))


class TestColorBucket(unittest.TestCase):
    def test_locked_bucket(self):
        self.assertEqual(wm.state_color_bucket(0.9, unlocked=False), "locked")

    def test_buckets_relative_to_threshold(self):
        X = 0.10
        self.assertEqual(wm.state_color_bucket(0.0, True, X), "red")       # 0
        self.assertEqual(wm.state_color_bucket(0.005, True, X), "red")     # 5% of X
        self.assertEqual(wm.state_color_bucket(0.02, True, X), "orange")   # 20% of X
        self.assertEqual(wm.state_color_bucket(0.05, True, X), "yellow")   # 50% of X
        self.assertEqual(wm.state_color_bucket(0.10, True, X), "green")    # == X
        self.assertEqual(wm.state_color_bucket(0.30, True, X), "green")    # > X

    def test_monotonic_ordering(self):
        order = ["red", "orange", "yellow", "green"]
        X = 0.5
        prev = -1
        for frac in [0.0, 0.1 * X, 0.3 * X, 0.99 * X, X]:
            b = wm.state_color_bucket(frac, True, X)
            self.assertGreaterEqual(order.index(b), prev)
            prev = order.index(b)


class TestPointInPolygon(unittest.TestCase):
    def setUp(self):
        # Import the screen's static hit test without constructing a screen.
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        import pygame
        pygame.init()
        from screens import USMapScreen
        self.pip = USMapScreen._point_in_poly

    def test_inside_square(self):
        sq = [(0, 0), (10, 0), (10, 10), (0, 10)]
        self.assertTrue(self.pip(5, 5, sq))

    def test_outside_square(self):
        sq = [(0, 0), (10, 0), (10, 10), (0, 10)]
        self.assertFalse(self.pip(15, 5, sq))
        self.assertFalse(self.pip(-1, -1, sq))

    def test_concave_polygon(self):
        # An L-shape: the notch is outside.
        ell = [(0, 0), (10, 0), (10, 4), (4, 4), (4, 10), (0, 10)]
        self.assertTrue(self.pip(2, 2, ell))    # in the tall arm
        self.assertFalse(self.pip(7, 7, ell))   # in the notch


if __name__ == "__main__":
    unittest.main()

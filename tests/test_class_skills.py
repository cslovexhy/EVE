"""Tests for the sniper/assassin rebalance:
  - swapped base damage (both player + building damage)
  - sniper CRIT (rarity chance, 1.5x)
  - assassin DECAPITATE (rarity chance, instakill target < 20% HP)

Builds throwaway Empire/BattleEngine objects — never calls GameState.save().
"""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import config  # noqa: E402
from models import (Empire, Member, MemberClass, Rarity, BuildingType,  # noqa: E402
                    Projectile, ProjectileType, MemberState)
from engine import BattleEngine  # noqa: E402


def mk(name, cls, building, level=1, rarity=Rarity.COMMON):
    m = Member(name=name, member_class=cls, level=level, rarity=rarity)
    m.assigned_building = building
    return m


def _engine(victim):
    player = Empire(name="Target", is_player=True)
    player.setup_buildings()
    layout = [BuildingType.WAREHOUSE] * 9
    player.apply_building_layout(layout)
    player.building_order = None
    player.members = [victim]
    player.member_assignments = [[0]] + [[] for _ in range(8)]
    enemy = Empire(name="Atk", is_player=False)
    enemy.setup_buildings()
    enemy.members = [mk("S", MemberClass.SNIPER, 0)]
    enemy.member_assignments = [[0]] + [[] for _ in range(8)]
    enemy.building_order = None
    return BattleEngine(player, enemy)


def _proj(eng, ptype, victim, rarity, dmg=10):
    b = eng.player.buildings[0]
    return Projectile(x=b.x, y=b.y, target_x=b.x, target_y=b.y, speed=99999,
                      damage=dmg, projectile_type=ptype, target_member=victim,
                      target_building=b, building_damage=dmg,
                      shooter_rarity=rarity)


class TestSwappedStats(unittest.TestCase):
    def test_damage_swapped_both_axes(self):
        # Sniper now heavier vs members; assassin heavier vs buildings.
        self.assertEqual(config.BASE_STATS["sniper"]["damage_player"], 20)
        self.assertEqual(config.BASE_STATS["sniper"]["damage_building"], 6)
        self.assertEqual(config.BASE_STATS["assassin"]["damage_player"], 15)
        self.assertEqual(config.BASE_STATS["assassin"]["damage_building"], 8)

    def test_no_class_dominates_both_axes(self):
        s = config.BASE_STATS["sniper"]
        a = config.BASE_STATS["assassin"]
        # Neither beats the other on BOTH member and building damage.
        self.assertFalse(s["damage_player"] > a["damage_player"]
                         and s["damage_building"] > a["damage_building"])
        self.assertFalse(a["damage_player"] > s["damage_player"]
                         and a["damage_building"] > s["damage_building"])

    def test_attack_intervals_untouched(self):
        # Assassin still unloads faster than the sniper.
        self.assertLess(config.BASE_STATS["assassin"]["attack_interval"],
                        config.BASE_STATS["sniper"]["attack_interval"])


class TestSniperCrit(unittest.TestCase):
    def test_crit_multiplies_damage(self):
        v = mk("V", MemberClass.ENFORCER, 0)
        v.state = MemberState.DEFENDING
        eng = _engine(v)
        proj = _proj(eng, ProjectileType.SNIPER, v, "super_rare", dmg=100)
        orig = random.random
        random.random = lambda: 0.0   # force crit
        try:
            dmg, skill = eng._apply_class_skill(proj, v, 100)
        finally:
            random.random = orig
        self.assertEqual(skill, "CRIT")
        self.assertAlmostEqual(dmg, 100 * config.SNIPER_CRIT_MULT)

    def test_no_crit_when_roll_fails(self):
        v = mk("V", MemberClass.ENFORCER, 0)
        v.state = MemberState.DEFENDING
        eng = _engine(v)
        proj = _proj(eng, ProjectileType.SNIPER, v, "common", dmg=100)
        orig = random.random
        random.random = lambda: 0.99   # above any crit chance
        try:
            dmg, skill = eng._apply_class_skill(proj, v, 100)
        finally:
            random.random = orig
        self.assertEqual(skill, "")
        self.assertEqual(dmg, 100)

    def test_crit_chance_scales_with_rarity(self):
        self.assertEqual(config.SNIPER_CRIT_CHANCE["common"], 0.05)
        self.assertEqual(config.SNIPER_CRIT_CHANCE["super_rare"], 0.20)
        vals = [config.SNIPER_CRIT_CHANCE[r]
                for r in ("common", "uncommon", "rare", "super_rare")]
        self.assertEqual(vals, sorted(vals))


class TestAssassinDecapitate(unittest.TestCase):
    def test_decap_instakills_low_hp_target(self):
        v = mk("V", MemberClass.SNIPER, 0)
        v.state = MemberState.DEFENDING
        eng = _engine(v)
        v.hp = v.max_hp * 0.1   # below 20% threshold
        proj = _proj(eng, ProjectileType.ASSASSIN, v, "super_rare", dmg=5)
        orig = random.random
        random.random = lambda: 0.0   # force decap
        try:
            dmg, skill = eng._apply_class_skill(proj, v, 5)
        finally:
            random.random = orig
        self.assertEqual(skill, "DECAPITATE")
        v.take_damage(dmg)
        self.assertFalse(v.is_alive)

    def test_no_decap_above_threshold(self):
        v = mk("V", MemberClass.SNIPER, 0)
        v.state = MemberState.DEFENDING
        eng = _engine(v)
        v.hp = v.max_hp * 0.5   # above 20% threshold -> never executable
        proj = _proj(eng, ProjectileType.ASSASSIN, v, "super_rare", dmg=5)
        orig = random.random
        random.random = lambda: 0.0   # would fire, but target too healthy
        try:
            dmg, skill = eng._apply_class_skill(proj, v, 5)
        finally:
            random.random = orig
        self.assertEqual(skill, "")
        self.assertEqual(dmg, 5)

    def test_no_decap_when_roll_fails(self):
        v = mk("V", MemberClass.SNIPER, 0)
        v.state = MemberState.DEFENDING
        eng = _engine(v)
        v.hp = v.max_hp * 0.1
        proj = _proj(eng, ProjectileType.ASSASSIN, v, "common", dmg=5)
        orig = random.random
        random.random = lambda: 0.99   # above decap chance
        try:
            dmg, skill = eng._apply_class_skill(proj, v, 5)
        finally:
            random.random = orig
        self.assertEqual(skill, "")

    def test_decap_chance_scales_with_rarity(self):
        self.assertEqual(config.ASSASSIN_DECAP_CHANCE["common"], 0.10)
        self.assertEqual(config.ASSASSIN_DECAP_CHANCE["super_rare"], 0.40)
        self.assertEqual(config.ASSASSIN_DECAP_HP_THRESHOLD, 0.20)

    def test_sniper_does_not_decapitate(self):
        v = mk("V", MemberClass.SNIPER, 0)
        v.state = MemberState.DEFENDING
        eng = _engine(v)
        v.hp = v.max_hp * 0.1
        proj = _proj(eng, ProjectileType.SNIPER, v, "super_rare", dmg=5)
        orig = random.random
        random.random = lambda: 0.0
        try:
            dmg, skill = eng._apply_class_skill(proj, v, 5)
        finally:
            random.random = orig
        self.assertIn(skill, ("CRIT", ""))   # sniper crits, never decapitates
        self.assertNotEqual(skill, "DECAPITATE")


if __name__ == "__main__":
    unittest.main()

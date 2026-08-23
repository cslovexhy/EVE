"""Tests for the unified projectile damage model:

Building + its defenders are one damage sink, resolved at impact. A shot in
flight is never cancelled by the targeted defender dying or being healed away:
 - defender dead at impact  -> damage rolls onto the building
 - live defender at impact   -> defender takes the hit, building spared
 - double-bunker shield up   -> building damage reduced to 0

Builds throwaway Empire/BattleEngine objects — never calls GameState.save(),
so the live player_profile.json is untouched.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import buildings  # noqa: E402
from models import (Empire, Member, MemberClass, Rarity, BuildingType,  # noqa: E402
                    Projectile, ProjectileType, MemberState)
from engine import BattleEngine  # noqa: E402


def make_member(name, cls, building, level=1):
    m = Member(name=name, member_class=cls, level=level, rarity=Rarity.COMMON)
    m.assigned_building = building
    return m


class _Base(unittest.TestCase):
    def _engine(self, target_layout, target_members, target_assign):
        """target = player side (the side being shot at)."""
        player = Empire(name="Target", is_player=True)
        player.setup_buildings()
        player.apply_building_layout(target_layout)
        player.building_order = buildings.building_order_from_layout(target_layout)
        player.members = target_members
        player.member_assignments = target_assign

        enemy = Empire(name="Attacker", is_player=False)
        enemy.setup_buildings()
        elayout = [BuildingType.HEADQUARTERS] + [BuildingType.WAREHOUSE] * 8
        enemy.apply_building_layout(elayout)
        enemy.building_order = buildings.building_order_from_layout(elayout)
        enemy.members = [make_member("S1", MemberClass.SNIPER, 0)]
        enemy.member_assignments = [[0]] + [[] for _ in range(8)]
        return BattleEngine(player, enemy)

    def _landed_proj(self, bldg, member, dmg_member, dmg_building):
        """A projectile positioned exactly on its target so the next update
        tick resolves it as an impact. If a live member is targeted the update
        steers to the member's position, so start there; otherwise the building."""
        if member is not None and member.is_alive:
            sx, sy = member.x, member.y
        else:
            sx, sy = bldg.x, bldg.y
        return Projectile(
            x=sx, y=sy, target_x=sx, target_y=sy,
            speed=100000.0, damage=dmg_member,
            projectile_type=ProjectileType.SNIPER,
            target_member=member, target_building=bldg,
            building_damage=dmg_building,
        )


class TestNoCancel(_Base):
    def test_dead_defender_rolls_damage_onto_building(self):
        """The heal/kill exploit: a shot aimed at a defender that is gone by
        impact now damages the building instead of being cancelled."""
        layout = [BuildingType.WAREHOUSE] * 9
        guard = make_member("Guard", MemberClass.ENFORCER, 0)
        eng = self._engine(layout, [guard], [[0]] + [[] for _ in range(8)])
        bldg = eng.player.buildings[0]
        hp0 = bldg.hp

        # Defender is already dead when the shot lands.
        guard.hp = 0
        guard.state = MemberState.DEAD
        proj = self._landed_proj(bldg, guard, dmg_member=50, dmg_building=8)
        eng.projectiles = [proj]
        eng._update_projectiles(0.1)

        self.assertFalse(proj.alive)
        self.assertAlmostEqual(bldg.hp, hp0 - 8, places=3)  # building took the roll-over

    def test_live_defender_absorbs_hit_building_spared(self):
        """Legitimate defence still works: a live defender at impact takes the
        member-damage and the building is untouched."""
        layout = [BuildingType.WAREHOUSE] * 9
        guard = make_member("Guard", MemberClass.ENFORCER, 0)
        guard.state = MemberState.DEFENDING
        eng = self._engine(layout, [guard], [[0]] + [[] for _ in range(8)])
        bldg = eng.player.buildings[0]
        hp0 = bldg.hp
        ghp0 = guard.hp

        proj = self._landed_proj(bldg, guard, dmg_member=20, dmg_building=8)
        eng.projectiles = [proj]
        eng._update_projectiles(0.1)

        self.assertAlmostEqual(bldg.hp, hp0, places=3)      # building untouched
        self.assertLess(guard.hp, ghp0)                     # defender took damage

    def test_defender_dies_this_tick_second_shot_hits_building(self):
        """A second shot after the last defender falls lands on the building."""
        layout = [BuildingType.WAREHOUSE] * 9
        guard = make_member("Guard", MemberClass.ENFORCER, 0)
        guard.state = MemberState.DEFENDING
        eng = self._engine(layout, [guard], [[0]] + [[] for _ in range(8)])
        bldg = eng.player.buildings[0]
        hp0 = bldg.hp

        # Two shots land the same tick; the first kills the guard (999 dmg),
        # the second finds no defenders and rolls onto the building.
        p1 = self._landed_proj(bldg, guard, dmg_member=999, dmg_building=8)
        p2 = self._landed_proj(bldg, guard, dmg_member=999, dmg_building=8)
        eng.projectiles = [p1, p2]
        eng._update_projectiles(0.1)

        self.assertFalse(guard.is_alive)
        # First shot killed the guard; second rolled onto the building.
        self.assertAlmostEqual(bldg.hp, hp0 - 8, places=3)


class TestBunkerShield(_Base):
    def test_shielded_bunker_takes_zero_building_damage(self):
        """Double bunker: while another bunker holds a live defender, a
        defenderless bunker takes 0 structural damage."""
        layout = [BuildingType.WAREHOUSE] * 9
        layout[3] = BuildingType.BUNKER   # holds a defender
        layout[6] = BuildingType.BUNKER   # empty -> target
        guard = make_member("Guard", MemberClass.ENFORCER, 3)
        guard.state = MemberState.DEFENDING
        assign = [[] for _ in range(9)]
        assign[3] = [0]
        eng = self._engine(layout, [guard], assign)
        empty_bunker = eng.player.buildings[6]
        hp0 = empty_bunker.hp

        proj = self._landed_proj(empty_bunker, None, dmg_member=50, dmg_building=50)
        eng.projectiles = [proj]
        eng._update_projectiles(0.1)

        self.assertAlmostEqual(empty_bunker.hp, hp0, places=3)  # shield: 0 damage

    def test_unshielded_bunker_takes_damage_after_defenders_gone(self):
        """Once the other bunker's defender is dead, the empty bunker is
        damageable — the shield rule is the only zeroing condition."""
        layout = [BuildingType.WAREHOUSE] * 9
        layout[3] = BuildingType.BUNKER
        layout[6] = BuildingType.BUNKER
        guard = make_member("Guard", MemberClass.ENFORCER, 3)
        guard.hp = 0
        guard.state = MemberState.DEAD
        assign = [[] for _ in range(9)]
        assign[3] = [0]
        eng = self._engine(layout, [guard], assign)
        # The engine's constructor re-seeds defender state, so kill the guard
        # AFTER construction to model "the other bunker's defender is down".
        guard.hp = 0
        guard.state = MemberState.DEAD
        empty_bunker = eng.player.buildings[6]
        hp0 = empty_bunker.hp

        proj = self._landed_proj(empty_bunker, None, dmg_member=50, dmg_building=40)
        eng.projectiles = [proj]
        eng._update_projectiles(0.1)

        self.assertAlmostEqual(empty_bunker.hp, hp0 - 40, places=3)


class TestOrphanedMemberTargeting(_Base):
    def test_live_member_in_destroyed_slot_is_targetable(self):
        """A living member left in a destroyed slot (e.g. by a nuke) stays a
        valid target instead of becoming untargetable."""
        layout = [BuildingType.WAREHOUSE] * 9
        guard = make_member("Orphan", MemberClass.ENFORCER, 0)
        eng = self._engine(layout, [guard], [[0]] + [[] for _ in range(8)])
        bldg = eng.player.buildings[0]
        bldg.destroyed = True  # rubble, but guard is still alive & assigned here

        self.assertTrue(eng.slot_has_live_member(eng.player, 0))
        self.assertTrue(eng.is_slot_targetable(eng.player, 0))

    def test_projectile_hits_orphaned_member_in_rubble(self):
        """A shot into a destroyed slot damages the live member there."""
        layout = [BuildingType.WAREHOUSE] * 9
        guard = make_member("Orphan", MemberClass.ENFORCER, 0)
        guard.state = MemberState.DEFENDING
        eng = self._engine(layout, [guard], [[0]] + [[] for _ in range(8)])
        bldg = eng.player.buildings[0]
        bldg.destroyed = True
        ghp0 = guard.hp

        proj = self._landed_proj(bldg, guard, dmg_member=20, dmg_building=8)
        eng.projectiles = [proj]
        eng._update_projectiles(0.1)

        self.assertLess(guard.hp, ghp0)  # orphan took the hit

    def test_dead_empty_destroyed_slot_not_targetable(self):
        """A destroyed slot with no living members is a dead slot."""
        layout = [BuildingType.WAREHOUSE] * 9
        eng = self._engine(layout, [], [[] for _ in range(9)])
        eng.player.buildings[0].destroyed = True
        self.assertFalse(eng.is_slot_targetable(eng.player, 0))
        self.assertFalse(
            eng.worthwhile_target(0, MemberClass.SNIPER, is_player=False))

    def test_standing_empty_building_is_targetable(self):
        """An intact building with no defenders is still targetable (to damage
        the building)."""
        layout = [BuildingType.WAREHOUSE] * 9
        eng = self._engine(layout, [], [[] for _ in range(9)])
        self.assertTrue(eng.is_slot_targetable(eng.player, 0))


if __name__ == "__main__":
    unittest.main()

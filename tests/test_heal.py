"""Unit tests for the per-building health-pack revive.

Locks in the fix: using a health pack on a building must ONLY revive a dead
member already ASSIGNED to that building. It must never pull a dead member in
from another building (which used to silently rewrite the layout).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from models import (  # noqa: E402
    Empire, Building, Member, MemberClass, MemberState, Rarity,
)
from battle_session import BattleSession  # noqa: E402


class _StubOrderSystem:
    """Captures feedback without pygame."""
    def __init__(self):
        self.feedback_msg = ""
        self.feedback_timer = 0.0


def _member(name, cls, building_index, level=1, rarity=Rarity.COMMON):
    m = Member(name=name, member_class=cls, level=level, rarity=rarity)
    m.assigned_building = building_index
    return m


def _make_session(members, health_packs=5):
    """Build a BattleSession without running its pygame __init__."""
    session = BattleSession.__new__(BattleSession)
    empire = Empire(name="Player", is_player=True)
    empire.health_packs = health_packs
    empire.buildings = [Building(index=i) for i in range(9)]
    # x/y are positioned by the engine at battle start; set them for the test
    # since the revive places the member near its building.
    for b in empire.buildings:
        b.x = 100.0 + b.index * 10
        b.y = 100.0 + b.index * 10
    empire.members = members
    # Wire members into their assigned building's defender list.
    for m in members:
        if m.assigned_building is not None:
            empire.buildings[m.assigned_building].defenders.append(m)
    session.player_empire = empire
    session.order_system = _StubOrderSystem()
    return session


class TestPerBuildingHeal(unittest.TestCase):
    def test_revives_only_member_assigned_to_that_building(self):
        # A dead demolitionist in building 0, a dead sniper in building 4.
        demo = _member("Demo", MemberClass.DEMOLITIONIST, 0)
        sniper = _member("Sniper", MemberClass.SNIPER, 4)
        demo.state = MemberState.DEAD
        sniper.state = MemberState.DEAD
        session = _make_session([demo, sniper])

        session._use_health_pack_on_building(0)

        # The building-0 member revived; the building-4 member untouched.
        self.assertEqual(demo.state, MemberState.DEFENDING)
        self.assertEqual(demo.hp, demo.max_hp)
        self.assertEqual(sniper.state, MemberState.DEAD)
        self.assertEqual(session.player_empire.health_packs, 4)

    def test_does_not_pull_in_member_from_another_building(self):
        # Only building 4 has a dead member; building 0 has a live one.
        live = _member("Live", MemberClass.ENFORCER, 0)
        live.state = MemberState.DEFENDING
        elsewhere = _member("Elsewhere", MemberClass.SNIPER, 4)
        elsewhere.state = MemberState.DEAD
        session = _make_session([elsewhere, live])

        session._use_health_pack_on_building(0)

        # Nothing revived, no pack spent, and the stray member did NOT move.
        self.assertEqual(elsewhere.state, MemberState.DEAD)
        self.assertEqual(elsewhere.assigned_building, 4)
        self.assertNotIn(elsewhere, session.player_empire.buildings[0].defenders)
        self.assertEqual(session.player_empire.health_packs, 5)
        self.assertEqual(session.order_system.feedback_msg,
                         "No more dead members to heal here")

    def test_layout_unchanged_for_healed_member(self):
        demo = _member("Demo", MemberClass.DEMOLITIONIST, 6)
        demo.state = MemberState.DEAD
        session = _make_session([demo])

        session._use_health_pack_on_building(6)

        # assigned_building preserved; member stays in the same building list.
        self.assertEqual(demo.assigned_building, 6)
        self.assertIn(demo, session.player_empire.buildings[6].defenders)
        # No duplicate append.
        self.assertEqual(
            session.player_empire.buildings[6].defenders.count(demo), 1)

    def test_no_packs_left(self):
        demo = _member("Demo", MemberClass.DEMOLITIONIST, 0)
        demo.state = MemberState.DEAD
        session = _make_session([demo], health_packs=0)

        session._use_health_pack_on_building(0)

        self.assertEqual(demo.state, MemberState.DEAD)
        self.assertEqual(session.order_system.feedback_msg, "No health packs left")

    def test_revives_a_dead_member_of_that_building(self):
        # Two dead members in the same building — a random one is revived,
        # and it must be one of THIS building's dead (never relocate/pull-in).
        weak = _member("Weak", MemberClass.ASSASSIN, 0, level=1)
        strong = _member("Strong", MemberClass.ENFORCER, 0, level=10)
        weak.state = MemberState.DEAD
        strong.state = MemberState.DEAD
        session = _make_session([weak, strong])

        session._use_health_pack_on_building(0)

        revived = [m for m in (weak, strong) if m.state == MemberState.DEFENDING]
        still_dead = [m for m in (weak, strong) if m.state == MemberState.DEAD]
        # Exactly one revived, and it stayed in building 0.
        self.assertEqual(len(revived), 1)
        self.assertEqual(len(still_dead), 1)
        self.assertEqual(revived[0].assigned_building, 0)
        self.assertEqual(session.player_empire.health_packs, 4)


class TestEmpireHealBuilding(unittest.TestCase):
    """Empire.heal_building is the SINGLE shared heal used by both the player
    (H -> click building) and the AI: revive a random dead defender assigned to
    the given building, in place, never relocating them."""

    def _empire(self):
        e = Empire(name="P", is_player=True)
        e.buildings = [Building(index=i) for i in range(9)]
        for b in e.buildings:
            b.x = 100.0 + b.index
            b.y = 100.0 + b.index
        return e

    def test_revives_in_place_in_that_building(self):
        e = self._empire()
        # A dead enforcer assigned to the silo (slot 8).
        titan = Member(name="Titan", member_class=MemberClass.ENFORCER,
                       level=3, rarity=Rarity.COMMON)
        titan.assigned_building = 8
        titan.state = MemberState.DEAD
        e.members = [titan]
        packs_before = e.health_packs

        revived = e.heal_building(8)

        self.assertIs(revived, titan)
        self.assertEqual(titan.assigned_building, 8)       # never relocated
        self.assertIn(titan, e.buildings[8].defenders)
        self.assertNotIn(titan, e.buildings[2].defenders)  # not the hospital
        self.assertEqual(titan.state, MemberState.DEFENDING)
        self.assertEqual(e.health_packs, packs_before - 1)

    def test_only_revives_dead_in_that_building(self):
        e = self._empire()
        here = Member(name="Here", member_class=MemberClass.SNIPER,
                      level=1, rarity=Rarity.COMMON)
        here.assigned_building = 3
        here.state = MemberState.DEAD
        elsewhere = Member(name="Elsewhere", member_class=MemberClass.SNIPER,
                           level=1, rarity=Rarity.COMMON)
        elsewhere.assigned_building = 5
        elsewhere.state = MemberState.DEAD
        e.members = [here, elsewhere]

        # Healing building 3 must not touch the dead defender in building 5.
        revived = e.heal_building(3)
        self.assertIs(revived, here)
        self.assertEqual(elsewhere.state, MemberState.DEAD)
        self.assertEqual(elsewhere.assigned_building, 5)

    def test_no_dead_in_building_returns_none(self):
        e = self._empire()
        m = Member(name="Dead", member_class=MemberClass.SNIPER,
                   level=1, rarity=Rarity.COMMON)
        m.assigned_building = 5
        m.state = MemberState.DEAD
        e.members = [m]
        packs_before = e.health_packs

        # Building 0 has no dead defenders → no-op, no pack spent.
        self.assertIsNone(e.heal_building(0))
        self.assertEqual(e.health_packs, packs_before)

    def test_no_packs_returns_none(self):
        e = self._empire()
        e.health_packs = 0
        m = Member(name="Dead", member_class=MemberClass.SNIPER,
                   level=1, rarity=Rarity.COMMON)
        m.assigned_building = 0
        m.state = MemberState.DEAD
        e.members = [m]

        self.assertIsNone(e.heal_building(0))
        self.assertEqual(m.state, MemberState.DEAD)

    def test_destroyed_building_returns_none(self):
        e = self._empire()
        e.buildings[0].destroyed = True
        m = Member(name="Dead", member_class=MemberClass.SNIPER,
                   level=1, rarity=Rarity.COMMON)
        m.assigned_building = 0
        m.state = MemberState.DEAD
        e.members = [m]

        self.assertIsNone(e.heal_building(0))

    def test_player_path_delegates_to_shared_logic(self):
        # The player's H -> building path must produce the same result as a
        # direct heal_building call (single source of truth).
        demo = _member("Demo", MemberClass.DEMOLITIONIST, 6)
        demo.state = MemberState.DEAD
        session = _make_session([demo])

        session._use_health_pack_on_building(6)

        self.assertEqual(demo.state, MemberState.DEFENDING)
        self.assertEqual(demo.assigned_building, 6)
        self.assertIn(demo, session.player_empire.buildings[6].defenders)

    def test_healing_three_times_revives_only_the_one_defender(self):
        # Reproduces the reported bug: a bunker (slot 0) with exactly ONE
        # defender (Grizzly) and members belonging to another building
        # (research lab, slot 7). Healing slot 0 three times must revive only
        # Grizzly once, then report "no more dead" — never pull in slot-7
        # members.
        grizzly = _member("Grizzly", MemberClass.ENFORCER, 0)
        rocco = _member("Rocco", MemberClass.ENFORCER, 7)
        hammer = _member("Hammer", MemberClass.ENFORCER, 7)
        grizzly.state = MemberState.DEAD
        # rocco/hammer are alive in the research lab and must never move.
        rocco.state = MemberState.DEFENDING
        hammer.state = MemberState.DEFENDING
        session = _make_session([grizzly, rocco, hammer])

        session._use_health_pack_on_building(0)   # revives Grizzly
        self.assertEqual(grizzly.state, MemberState.DEFENDING)

        session._use_health_pack_on_building(0)   # nobody dead in slot 0
        self.assertEqual(session.order_system.feedback_msg,
                         "No more dead members to heal here")
        session._use_health_pack_on_building(0)   # still nobody
        self.assertEqual(session.order_system.feedback_msg,
                         "No more dead members to heal here")

        # Rocco and Hammer never touched: still in the research lab (slot 7).
        bunker = session.player_empire.buildings[0]
        lab = session.player_empire.buildings[7]
        self.assertNotIn(rocco, bunker.defenders)
        self.assertNotIn(hammer, bunker.defenders)
        self.assertEqual(rocco.assigned_building, 7)
        self.assertEqual(hammer.assigned_building, 7)
        self.assertIn(rocco, lab.defenders)
        self.assertIn(hammer, lab.defenders)
        # Only one pack spent (the successful revive).
        self.assertEqual(session.player_empire.health_packs, 4)


if __name__ == "__main__":
    unittest.main()

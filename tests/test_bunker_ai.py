"""Scenario tests: AI must not waste ammo on a shielded, defenderless bunker.

Builds throwaway Empire/BattleEngine objects only — never calls GameState.save(),
so the live player_profile.json is untouched.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from models import Empire, Member, MemberClass, Rarity, BuildingType  # noqa: E402
from engine import BattleEngine  # noqa: E402
from ai import BattleAI  # noqa: E402
import buildings  # noqa: E402


def make_member(name, cls, building):
    m = Member(name=name, member_class=cls, level=1, rarity=Rarity.COMMON)
    m.assigned_building = building
    return m


class TestBunkerAITargeting(unittest.TestCase):
    def _make(self):
        # Target side: bunker WITH defender in front slot 0's neighbor, bunker
        # WITHOUT defender in a front entry slot so it is always reachable.
        player = Empire(name="Target", is_player=True)
        player.setup_buildings()
        layout = [BuildingType.WAREHOUSE] * 9
        layout[3] = BuildingType.BUNKER   # front entry slot (index 3) -> reachable, HAS defender
        layout[6] = BuildingType.BUNKER   # front entry slot (index 6) -> reachable, NO defender
        player.apply_building_layout(layout)
        player.members = [make_member("Guard", MemberClass.ENFORCER, 3)]
        # Pin the guard into the slot-3 bunker; slot 6 stays empty.
        player.member_assignments = [[] for _ in range(9)]
        player.member_assignments[3] = [0]

        # Attacker side (the AI): a handful of each attacking class in HQ slot 0.
        enemy = Empire(name="Attacker", is_player=False)
        enemy.setup_buildings()
        enemy_layout = [BuildingType.HEADQUARTERS] + [BuildingType.WAREHOUSE] * 8
        enemy.apply_building_layout(enemy_layout)
        # Set building_order so the engine skips enemy randomization (which would
        # otherwise clobber member_assignments below).
        enemy.building_order = buildings.building_order_from_layout(enemy_layout)
        enemy.members = [
            make_member("A1", MemberClass.ASSASSIN, 0),
            make_member("A2", MemberClass.ASSASSIN, 0),
            make_member("D1", MemberClass.DEMOLITIONIST, 0),
            make_member("S1", MemberClass.SNIPER, 0),
        ]
        # Pin attackers in HQ (slot 0).
        enemy.member_assignments = [list(range(len(enemy.members)))] + [[] for _ in range(8)]
        engine = BattleEngine(player, enemy)
        return engine, player, enemy

    def test_shielded_defenderless_bunker_not_worthwhile(self):
        engine, player, enemy = self._make()
        # Both bunkers reachable (front entry slots)
        self.assertTrue(engine.is_attackable_by_class(3, MemberClass.ASSASSIN, is_player=False))
        self.assertTrue(engine.is_attackable_by_class(6, MemberClass.ASSASSIN, is_player=False))

        # Bunker with a defender (slot 3): worthwhile (kill its defenders).
        self.assertIsNone(engine.attack_block_reason(3, is_player=False))
        self.assertTrue(engine.worthwhile_target(3, MemberClass.ASSASSIN, is_player=False))

        # Bunker with NO defender (slot 6): shielded dead end -> NOT worthwhile.
        self.assertIsNotNone(engine.attack_block_reason(6, is_player=False))
        self.assertFalse(engine.worthwhile_target(6, MemberClass.ASSASSIN, is_player=False))
        self.assertFalse(engine.worthwhile_target(6, MemberClass.DEMOLITIONIST, is_player=False))

    def test_ai_never_targets_shielded_defenderless_bunker(self):
        engine, player, enemy = self._make()
        ai = BattleAI(enemy, player, is_player=False)

        # Drive many planning cycles; the AI must never queue an order at slot 6.
        for _ in range(200):
            ai._plan_attack(engine)
            for order in ai.order_queue:
                self.assertNotEqual(
                    order.target_building, 6,
                    "AI queued an attack on the shielded, defenderless bunker (slot 6)",
                )
            ai.order_queue.clear()
            # rotate phases so we exercise opening/assault/push/cleanup
            if ai.current_target is None:
                ai.phase = "opening"

    def test_bunker_becomes_attackable_once_all_defenders_dead(self):
        engine, player, enemy = self._make()
        # Kill the lone defender -> no bunker holds a live defender -> unshielded.
        from models import MemberState
        player.members[0].state = MemberState.DEAD

        self.assertIsNone(engine.attack_block_reason(6, is_player=False))
        self.assertTrue(engine.worthwhile_target(6, MemberClass.DEMOLITIONIST, is_player=False))
        self.assertIsNone(engine.attack_block_reason(3, is_player=False))
        self.assertTrue(engine.worthwhile_target(3, MemberClass.DEMOLITIONIST, is_player=False))

    def _make_two_defended_bunkers(self):
        """Player has bunkers in front slots 3 and 6, each with its own live
        enforcer. Enemy has one assassin who will be ordered onto slot 3."""
        from models import MemberState  # noqa: F401
        player = Empire(name="Target", is_player=True)
        player.setup_buildings()
        layout = [BuildingType.WAREHOUSE] * 9
        layout[3] = BuildingType.BUNKER
        layout[6] = BuildingType.BUNKER
        player.apply_building_layout(layout)
        player.members = [
            make_member("G3", MemberClass.ENFORCER, 3),
            make_member("G6", MemberClass.ENFORCER, 6),
        ]
        player.member_assignments = [[] for _ in range(9)]
        player.member_assignments[3] = [0]
        player.member_assignments[6] = [1]

        enemy = Empire(name="Attacker", is_player=False)
        enemy.setup_buildings()
        enemy_layout = [BuildingType.HEADQUARTERS] + [BuildingType.WAREHOUSE] * 8
        enemy.apply_building_layout(enemy_layout)
        enemy.building_order = buildings.building_order_from_layout(enemy_layout)
        enemy.members = [make_member("A1", MemberClass.ASSASSIN, 0)]
        enemy.member_assignments = [[0]] + [[] for _ in range(8)]
        engine = BattleEngine(player, enemy)
        return engine, player, enemy

    def test_attacker_stops_firing_when_bunker_becomes_shielded_deadend(self):
        """The core bug: a member already ordered onto a bunker keeps firing
        after its defender dies while the OTHER bunker still shields it."""
        from models import MemberState, OrderAction, Order
        engine, player, enemy = self._make_two_defended_bunkers()
        attacker = enemy.members[0]

        # Order the attacker onto the slot-3 bunker (which has a defender).
        engine.execute_order(
            Order(member_class=MemberClass.ASSASSIN, target_building=3,
                  action=OrderAction.ATTACK),
            enemy, player, attack_mode="auto",
        )
        self.assertEqual(attacker.target_building, 3)
        self.assertEqual(attacker.state, MemberState.ATTACKING)

        # While the slot-3 defender lives, the attacker keeps firing (ammo drops).
        attacker.attack_cooldown = 0.0
        start_ammo = attacker.ammo
        engine._update_attacker(attacker, 0.016)
        self.assertLess(attacker.ammo, start_ammo, "should fire while defenders present")

        # Kill slot-3's defender. Slot 6's bunker still holds a defender, so the
        # slot-3 bunker is now shielded AND defenderless -> a dead end.
        player.members[0].state = MemberState.DEAD
        self.assertIsNotNone(engine.bunker_block_reason(player, 3))

        # Now the attacker must STOP: it drops the target and burns no more ammo.
        ammo_before = attacker.ammo
        for _ in range(10):
            attacker.attack_cooldown = 0.0
            engine._update_attacker(attacker, 0.016)
        self.assertIsNone(attacker.target_building,
                          "attacker should drop the shielded, empty bunker target")
        self.assertEqual(attacker.ammo, ammo_before,
                         "attacker must not waste ammo on a shielded, empty bunker")


if __name__ == "__main__":
    unittest.main()

"""Unit tests for the building upgrade system (chain, limits, costs, HP)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import config  # noqa: E402
import buildings  # noqa: E402
from models import Empire, Building, BuildingType  # noqa: E402


def make_empire(money=None):
    e = Empire(name="Test")
    e.setup_buildings()
    if money is not None:
        e.money = money
    return e


class TestBuildingHP(unittest.TestCase):
    def test_warehouse_uses_base_hp(self):
        b = Building(index=0)
        self.assertEqual(b.building_type, BuildingType.WAREHOUSE)
        self.assertEqual(b.hp, config.BUILDING_BASE_HP)
        self.assertEqual(b.max_hp, config.BUILDING_BASE_HP)
        self.assertEqual(b.max_hp, 500)

    def test_type_driven_hp_on_construction(self):
        b = Building(index=0, building_type=BuildingType.HEADQUARTERS)
        self.assertEqual(b.max_hp, 1300)
        self.assertEqual(b.hp, 1300)

    def test_hq_and_bunker_are_highest(self):
        hps = {bt: buildings.building_hp(bt) for bt in BuildingType}
        top = max(hps.values())
        self.assertEqual(hps[BuildingType.HEADQUARTERS], top)
        self.assertEqual(hps[BuildingType.BUNKER], top)
        # Warehouse is the base / lowest.
        self.assertEqual(hps[BuildingType.WAREHOUSE], min(hps.values()))

    def test_apply_type_hp_refreshes(self):
        b = Building(index=0)
        b.take_damage(200)
        self.assertLess(b.hp, b.max_hp)
        b.building_type = BuildingType.BUNKER
        b.apply_type_hp()
        self.assertEqual(b.max_hp, 1300)
        self.assertEqual(b.hp, 1300)
        self.assertFalse(b.destroyed)


class TestUpgradeChain(unittest.TestCase):
    def test_warehouse_can_upgrade_to_tier1(self):
        e = make_empire(money=100000)
        for target in (BuildingType.HEADQUARTERS, BuildingType.ARMORY,
                       BuildingType.HOSPITAL, BuildingType.SAFEHOUSE,
                       BuildingType.SNIPER_TOWER, BuildingType.RESEARCH_LAB,
                       BuildingType.NUCLEAR_SILO):
            ok, reason = buildings.can_upgrade(e, 0, target)
            self.assertTrue(ok, f"{target} should be upgradable from warehouse ({reason})")

    def test_warehouse_cannot_go_straight_to_bunker(self):
        e = make_empire(money=100000)
        ok, reason = buildings.can_upgrade(e, 0, BuildingType.BUNKER)
        self.assertFalse(ok)
        self.assertEqual(reason, "invalid_chain")

    def test_safehouse_upgrades_to_bunker(self):
        e = make_empire(money=100000)
        buildings.upgrade_building(e, 0, BuildingType.SAFEHOUSE)
        ok, reason = buildings.can_upgrade(e, 0, BuildingType.BUNKER)
        self.assertTrue(ok, reason)
        ok2, _ = buildings.upgrade_building(e, 0, BuildingType.BUNKER)
        self.assertTrue(ok2)
        self.assertEqual(e.buildings[0].building_type, BuildingType.BUNKER)
        self.assertEqual(e.buildings[0].max_hp, 1300)

    def test_safehouse_cannot_go_to_hq(self):
        e = make_empire(money=100000)
        buildings.upgrade_building(e, 0, BuildingType.SAFEHOUSE)
        ok, reason = buildings.can_upgrade(e, 0, BuildingType.HEADQUARTERS)
        self.assertFalse(ok)
        self.assertEqual(reason, "invalid_chain")

    def test_already_this_type(self):
        e = make_empire(money=100000)
        ok, reason = buildings.can_upgrade(e, 0, BuildingType.WAREHOUSE)
        self.assertFalse(ok)
        self.assertEqual(reason, "already_this_type")

    def test_invalid_slot(self):
        e = make_empire(money=100000)
        ok, reason = buildings.can_upgrade(e, 99, BuildingType.HEADQUARTERS)
        self.assertFalse(ok)
        self.assertEqual(reason, "invalid_slot")


class TestUpgradeLimits(unittest.TestCase):
    def test_hq_is_unique(self):
        e = make_empire(money=100000)
        self.assertTrue(buildings.upgrade_building(e, 0, BuildingType.HEADQUARTERS)[0])
        ok, reason = buildings.can_upgrade(e, 1, BuildingType.HEADQUARTERS)
        self.assertFalse(ok)
        self.assertEqual(reason, "max_count_reached")

    def test_safehouse_limit_two(self):
        e = make_empire(money=100000)
        self.assertTrue(buildings.upgrade_building(e, 0, BuildingType.SAFEHOUSE)[0])
        self.assertTrue(buildings.upgrade_building(e, 1, BuildingType.SAFEHOUSE)[0])
        ok, reason = buildings.can_upgrade(e, 2, BuildingType.SAFEHOUSE)
        self.assertFalse(ok)
        self.assertEqual(reason, "max_count_reached")

    def test_bunker_limit_two(self):
        e = make_empire(money=1000000)
        # Only 2 safehouses can exist at once, so build 2 and convert to bunkers.
        buildings.upgrade_building(e, 0, BuildingType.SAFEHOUSE)
        buildings.upgrade_building(e, 1, BuildingType.SAFEHOUSE)
        self.assertTrue(buildings.upgrade_building(e, 0, BuildingType.BUNKER)[0])
        self.assertTrue(buildings.upgrade_building(e, 1, BuildingType.BUNKER)[0])
        self.assertEqual(e.count_building_type(BuildingType.BUNKER), 2)
        # Safehouse slots are free again; build 2 more safehouses.
        self.assertTrue(buildings.upgrade_building(e, 2, BuildingType.SAFEHOUSE)[0])
        self.assertTrue(buildings.upgrade_building(e, 3, BuildingType.SAFEHOUSE)[0])
        # A 3rd bunker must be blocked by the bunker cap.
        ok, reason = buildings.can_upgrade(e, 2, BuildingType.BUNKER)
        self.assertFalse(ok)
        self.assertEqual(reason, "max_count_reached")


class TestUpgradeCosts(unittest.TestCase):
    def test_cost_is_deducted(self):
        e = make_empire(money=5000)
        cost = buildings.upgrade_cost(BuildingType.ARMORY)
        ok, _ = buildings.upgrade_building(e, 0, BuildingType.ARMORY)
        self.assertTrue(ok)
        self.assertEqual(e.money, 5000 - cost)

    def test_insufficient_funds_blocks_and_preserves_state(self):
        e = make_empire(money=100)
        ok, reason = buildings.can_upgrade(e, 0, BuildingType.NUCLEAR_SILO)
        self.assertFalse(ok)
        self.assertEqual(reason, "insufficient_funds")
        ok2, reason2 = buildings.upgrade_building(e, 0, BuildingType.NUCLEAR_SILO)
        self.assertFalse(ok2)
        self.assertEqual(reason2, "insufficient_funds")
        self.assertEqual(e.money, 100)  # unchanged
        self.assertEqual(e.buildings[0].building_type, BuildingType.WAREHOUSE)

    def test_costs_match_config(self):
        self.assertEqual(buildings.upgrade_cost(BuildingType.SAFEHOUSE), 1500)
        self.assertEqual(buildings.upgrade_cost(BuildingType.NUCLEAR_SILO), 10000)
        self.assertEqual(buildings.upgrade_cost(BuildingType.BUNKER), 5000)


class TestBuildingOrderInterop(unittest.TestCase):
    def test_apply_building_order_sets_types_and_hp(self):
        e = make_empire()
        # Identity building_order: slot i -> name_index i.
        # name_index: 0=HQ,1=armory,2=hospital,3=warehouse,4=bunker,
        #             5=silo,6=sniper_tower,7=research_lab,8=safehouse
        order = list(range(9))
        buildings.apply_building_order(e, order)
        self.assertEqual(e.buildings[0].building_type, BuildingType.HEADQUARTERS)
        self.assertEqual(e.buildings[0].max_hp, 1300)
        self.assertEqual(e.buildings[3].building_type, BuildingType.WAREHOUSE)
        self.assertEqual(e.buildings[3].max_hp, 500)
        self.assertEqual(e.buildings[4].building_type, BuildingType.BUNKER)
        self.assertEqual(e.buildings[4].max_hp, 1300)


if __name__ == "__main__":
    unittest.main()

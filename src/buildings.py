"""EVE - Building upgrade system.

Pure logic for validating and applying building upgrades along the chain
defined in config.BUILDING_TYPES:

    warehouse -> headquarters | armory | hospital | safehouse
               | sniper_tower | research_lab | nuclear_silo
    safehouse -> bunker

Upgrades cost money and are gated by per-type maximum counts (e.g. HQ is
unique, Safehouses are limited to 2). Building HP is determined by type.
"""
from typing import List, Optional, Tuple

import config
from models import BuildingType, Empire


def building_hp(building_type: BuildingType) -> int:
    """Max HP for a building type."""
    return building_type.spec["hp"]


def upgrade_cost(building_type: BuildingType) -> int:
    """Money cost to upgrade INTO this building type."""
    return building_type.spec["upgrade_cost"]


def max_count(building_type: BuildingType) -> Optional[int]:
    """Max number of this type allowed per empire (None = unlimited)."""
    return building_type.spec["max_count"]


def upgrade_source(building_type: BuildingType) -> Optional[BuildingType]:
    """The type that upgrades INTO this one (None for the base warehouse)."""
    src = building_type.spec["upgrades_from"]
    return BuildingType(src) if src is not None else None


def available_upgrade_targets(current_type: BuildingType) -> List[BuildingType]:
    """Building types the given current type can be upgraded into."""
    targets = []
    for name, spec in config.BUILDING_TYPES.items():
        if spec["upgrades_from"] == current_type.value:
            targets.append(BuildingType(name))
    return targets


def can_upgrade(empire: Empire, slot: int,
                target_type: BuildingType) -> Tuple[bool, str]:
    """Check whether `empire` may upgrade the building at `slot` into
    `target_type`. Returns (ok, reason). `reason` is "" when ok is True."""
    if slot < 0 or slot >= len(empire.buildings):
        return False, "invalid_slot"

    building = empire.buildings[slot]
    current = building.building_type

    # Must be a real upgrade edge in the chain.
    if target_type == current:
        return False, "already_this_type"
    if upgrade_source(target_type) != current:
        return False, "invalid_chain"

    # Per-type maximum count (uniqueness / limits).
    limit = max_count(target_type)
    if limit is not None and empire.count_building_type(target_type) >= limit:
        return False, "max_count_reached"

    # Money.
    if empire.money < upgrade_cost(target_type):
        return False, "insufficient_funds"

    return True, ""


def upgrade_building(empire: Empire, slot: int,
                     target_type: BuildingType) -> Tuple[bool, str]:
    """Validate and apply an upgrade. On success, deducts the cost, sets the
    building's type, and refreshes its HP. Returns (ok, reason)."""
    ok, reason = can_upgrade(empire, slot, target_type)
    if not ok:
        return False, reason

    empire.money -= upgrade_cost(target_type)
    building = empire.buildings[slot]
    building.building_type = target_type
    building.level = 1
    building.apply_type_hp()
    return True, ""


# --- HQ leveling ---------------------------------------------------------
def hq_next_level_cost(current_level: int) -> Optional[int]:
    """Money to level an HQ from current_level to current_level+1 (None if maxed)."""
    return config.HQ_LEVEL_UP_COST.get(current_level + 1)


def can_level_hq(empire: Empire, slot: int) -> Tuple[bool, str]:
    if slot < 0 or slot >= len(empire.buildings):
        return False, "invalid_slot"
    b = empire.buildings[slot]
    if b.building_type != BuildingType.HEADQUARTERS:
        return False, "not_hq"
    if b.level >= config.HQ_MAX_LEVEL:
        return False, "max_level"
    cost = hq_next_level_cost(b.level)
    if cost is None:
        return False, "max_level"
    if empire.money < cost:
        return False, "insufficient_funds"
    return True, ""


def level_up_hq(empire: Empire, slot: int) -> Tuple[bool, str]:
    """Raise an HQ one level: deduct escalating cost, bump level, refresh HP
    (which also raises the empire's member cap)."""
    ok, reason = can_level_hq(empire, slot)
    if not ok:
        return False, reason
    b = empire.buildings[slot]
    empire.money -= hq_next_level_cost(b.level)
    b.level += 1
    b.apply_type_hp()
    return True, ""


def apply_building_levels(empire: Empire, levels: List[int]) -> None:
    """Set each building's level (e.g. HQ level) and refresh HP."""
    for i, b in enumerate(empire.buildings):
        if i < len(levels) and levels[i]:
            b.level = max(1, int(levels[i]))
            b.apply_type_hp()


# --- building_order (name-index) interop ---------------------------------
# building_order (used by the renderer and setup UI) is a list of "name
# indices" per slot. Map those indices back to BuildingType so battle HP
# reflects each slot's building type.
NAME_INDEX_TO_TYPE = {
    spec["name_index"]: BuildingType(name)
    for name, spec in config.BUILDING_TYPES.items()
}


def type_for_name_index(name_index: int) -> BuildingType:
    """BuildingType for a renderer/building_order name index (fallback warehouse)."""
    return NAME_INDEX_TO_TYPE.get(name_index, BuildingType.WAREHOUSE)


# Inverse: BuildingType -> renderer name index.
TYPE_TO_NAME_INDEX = {bt: bt.spec["name_index"] for bt in BuildingType}


def building_order_from_layout(layout: List[BuildingType]) -> List[int]:
    """Convert a building-type layout (9 BuildingType) into a building_order
    name-index list for the renderer/setup UI. Duplicates are allowed."""
    return [TYPE_TO_NAME_INDEX[bt] for bt in layout]


def apply_building_order(empire: Empire, building_order: List[int],
                         levels: List[int] = None) -> None:
    """Set an empire's building types + HP from a building_order name-index
    list. If `levels` is given, apply per-slot building levels (e.g. HQ level)."""
    layout = [type_for_name_index(ni) for ni in building_order]
    empire.apply_building_layout(layout)
    if levels is not None:
        apply_building_levels(empire, levels)


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

    # Bunker requires its source Safehouse to be fully leveled first.
    if target_type == BuildingType.BUNKER and building.level < config.SAFEHOUSE_BUNKER_MIN_LEVEL:
        return False, "safehouse_level_required"

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


# --- generic building leveling (all types) -------------------------------
def building_max_level(building_type: BuildingType) -> int:
    """Highest level this building type can reach."""
    return building_type.spec.get("max_level", 1)


def level_hp(building_type: BuildingType, level: int) -> int:
    """Max HP for a building type at a given (clamped) level."""
    ladder = building_type.spec["levels"]
    lvl = max(1, min(level, len(ladder)))
    return ladder[lvl - 1]["hp"]


def next_level_cost(building_type: BuildingType, current_level: int) -> Optional[int]:
    """Money to level a building of this type from current_level to
    current_level+1, or None if already at max level."""
    ladder = building_type.spec["levels"]
    nxt = current_level + 1
    if nxt < 1 or nxt > len(ladder):
        return None
    return ladder[nxt - 1]["cost"]


def level_field(building_type: BuildingType, level: int, field: str, default=None):
    """Read a per-level field (e.g. 'bonus_packs', 'charge_time') from a
    building type's level ladder at a clamped level, or `default` if absent."""
    ladder = building_type.spec["levels"]
    lvl = max(1, min(level, len(ladder)))
    return ladder[lvl - 1].get(field, default)


def effect_line(building_type: BuildingType, level: int) -> Optional[str]:
    """A short human description of what a building of this type does at the
    given level, beyond HP. Returns None for types whose only effect is HP
    (Warehouse, Armory, Sniper Tower, Research Lab, Safehouse).

    Surfaces the real, engine-backed mechanics so the upgrade screen tells you
    what leveling actually buys:
      * Hospital     -> bonus health packs granted at battle start (scales)
      * Nuclear Silo -> nuke charge time in seconds (lower = faster; scales)
      * Bunker       -> structural-damage shield while a bunker is defended
      * HQ           -> roster cap (+HQ_MEMBERS_PER_LEVEL per level)
    """
    t = building_type
    if t == BuildingType.HOSPITAL:
        packs = level_field(t, level, "bonus_packs", 0) or 0
        return (f"+{packs} health packs at battle start" if packs
                else "No bonus packs at Lv1 (level up for +packs)")
    if t == BuildingType.NUCLEAR_SILO:
        secs = level_field(t, level, "charge_time", None)
        if secs is not None:
            return f"Enables nuke · charges in {secs:.0f}s (lower is faster)"
        return "Enables the nuke"
    if t == BuildingType.BUNKER:
        return "Shields structure while any bunker is defended"
    if t == BuildingType.HEADQUARTERS:
        cap = config.BASE_MEMBER_CAP + config.HQ_MEMBERS_PER_LEVEL * max(1, level)
        return f"Roster cap {cap}"
    return None  # Warehouse / Armory / Sniper Tower / Research Lab / Safehouse


def can_level_building(empire: Empire, slot: int) -> Tuple[bool, str]:
    """Whether the building at `slot` can be leveled up one step. Applies to
    every level-able type (Warehouse is single-level and always returns
    'max_level')."""
    if slot < 0 or slot >= len(empire.buildings):
        return False, "invalid_slot"
    b = empire.buildings[slot]
    if b.level >= building_max_level(b.building_type):
        return False, "max_level"
    cost = next_level_cost(b.building_type, b.level)
    if cost is None:
        return False, "max_level"
    if empire.money < cost:
        return False, "insufficient_funds"
    return True, ""


def level_up_building(empire: Empire, slot: int) -> Tuple[bool, str]:
    """Raise a building one level: deduct its level cost, bump level, refresh
    HP. For an HQ this also raises the empire's member cap (via HP/level)."""
    ok, reason = can_level_building(empire, slot)
    if not ok:
        return False, reason
    b = empire.buildings[slot]
    empire.money -= next_level_cost(b.building_type, b.level)
    b.level += 1
    b.apply_type_hp()
    return True, ""


# --- HQ leveling (thin wrappers over the generic path) -------------------
def can_level_hq(empire: Empire, slot: int) -> Tuple[bool, str]:
    if slot < 0 or slot >= len(empire.buildings):
        return False, "invalid_slot"
    if empire.buildings[slot].building_type != BuildingType.HEADQUARTERS:
        return False, "not_hq"
    return can_level_building(empire, slot)


def level_up_hq(empire: Empire, slot: int) -> Tuple[bool, str]:
    """Raise an HQ one level: deduct escalating cost, bump level, refresh HP
    (which also raises the empire's member cap)."""
    if slot < 0 or slot >= len(empire.buildings):
        return False, "invalid_slot"
    if empire.buildings[slot].building_type != BuildingType.HEADQUARTERS:
        return False, "not_hq"
    return level_up_building(empire, slot)


def apply_building_levels(empire: Empire, levels: List[int]) -> None:
    """Set each building's level and refresh HP (clamped per type)."""
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


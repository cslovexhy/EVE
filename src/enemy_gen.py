"""EVE - Enemy roster generation from a region's underworld power.

Translates a single scalar (underworld_power, ~ crime volume) into a concrete
enemy empire: member count (up to the 80 cap), member level, rarity mix, and a
fortified building layout. Uses absolute log-scaling against a reference max,
so a city's difficulty is fixed by its real power (tuned on Virginia, whose
underworld powers span ~1..77,700).
"""
import math
import random
from typing import List

import config
import buildings
from models import Empire, Member, MemberClass, Rarity, BuildingType

MAX_MEMBERS = 80              # roster cap (docs/questions.md)
MIN_MEMBERS = 4
MAX_LEVEL = 15
REFERENCE_MAX_POWER = 80000  # ~ Virginia's strongest underworld (recalibrate for other states)

# Fortification build order as a city grows stronger. Each entry is one stage;
# 'add' places a new building, 'upgrade' converts an existing Safehouse into a
# Bunker (mirroring the player's upgrade chain). More power => more stages applied.
FORT_STAGES = [
    ("add", BuildingType.HEADQUARTERS),
    ("add", BuildingType.SAFEHOUSE),      # Safehouse 1
    ("add", BuildingType.SAFEHOUSE),      # Safehouse 2
    ("add", BuildingType.ARMORY),
    ("add", BuildingType.HOSPITAL),
    ("add", BuildingType.SNIPER_TOWER),
    ("add", BuildingType.RESEARCH_LAB),
    ("upgrade", BuildingType.BUNKER),     # Safehouse 1 -> Bunker 1
    ("upgrade", BuildingType.BUNKER),     # Safehouse 2 -> Bunker 2
    ("add", BuildingType.NUCLEAR_SILO),
]

CLASS_ORDER = [MemberClass.ENFORCER, MemberClass.SNIPER,
               MemberClass.ASSASSIN, MemberClass.DEMOLITIONIST]

_NAME_POOLS = {
    MemberClass.ENFORCER: ["Gustavo", "Salvatore", "Brutus", "Goliath", "Mammoth",
                           "Ox", "Rhino", "Grizzly", "Boulder", "Colossus"],
    MemberClass.SNIPER: ["Gunslinger", "Razor", "Crosshair", "Marksman", "Eagle",
                         "Sharpshot", "Glint", "Reticle", "Archer", "Pierce"],
    MemberClass.ASSASSIN: ["Ghost", "Lotus", "Cobra", "Raven", "Scorpion",
                           "Shade", "Fang", "Mamba", "Eclipse", "Null"],
    MemberClass.DEMOLITIONIST: ["Diablo", "Caine", "Arson", "Pyro", "Napalm",
                                "Havoc", "Crater", "Mortar", "Shrapnel", "Landmine"],
}


def power_norm(underworld_power: float) -> float:
    """Map raw underworld power to 0..1 via log-scale against the reference max."""
    if underworld_power <= 0:
        return 0.0
    return min(1.0, math.log10(underworld_power + 1) / math.log10(REFERENCE_MAX_POWER + 1))


def _member_count(norm: float) -> int:
    return max(MIN_MEMBERS, round(MIN_MEMBERS + (MAX_MEMBERS - MIN_MEMBERS) * norm))


def _member_level(norm: float) -> int:
    return max(1, round(1 + (MAX_LEVEL - 1) * norm))


def _pick_rarity(norm: float, rng: random.Random) -> Rarity:
    """Rarity distribution shifts toward rare/super-rare as power rises."""
    if norm < 0.25:
        return Rarity.COMMON
    if norm < 0.5:
        return Rarity.UNCOMMON if rng.random() < (norm - 0.25) / 0.25 else Rarity.COMMON
    if norm < 0.75:
        return rng.choices([Rarity.COMMON, Rarity.UNCOMMON, Rarity.RARE],
                           weights=[1, 2, 2])[0]
    return rng.choices([Rarity.UNCOMMON, Rarity.RARE, Rarity.SUPER_RARE],
                       weights=[1, 2, 3])[0]


def _name(cls: MemberClass, k: int) -> str:
    pool = _NAME_POOLS[cls]
    base = pool[(k // len(CLASS_ORDER)) % len(pool)]
    cycle = (k // len(CLASS_ORDER)) // len(pool)
    return base if cycle == 0 else f"{base} {cycle + 1}"


def _make_members(count: int, level: int, norm: float, rng: random.Random) -> List[Member]:
    members = []
    for k in range(count):
        cls = CLASS_ORDER[k % len(CLASS_ORDER)]
        members.append(Member(name=_name(cls, k), member_class=cls,
                              level=level, rarity=_pick_rarity(norm, rng)))
    return members


def _fort_types(norm: float) -> List[BuildingType]:
    """Specialist building types for a fortification level (more stages as power
    rises). Safehouses are upgraded into Bunkers by the 'upgrade' stages."""
    k = max(0, min(len(FORT_STAGES), round(len(FORT_STAGES) * norm)))
    types: List[BuildingType] = []
    for op, t in FORT_STAGES[:k]:
        if op == "add":
            types.append(t)
        else:  # upgrade a Safehouse into a Bunker
            if BuildingType.SAFEHOUSE in types:
                types[types.index(BuildingType.SAFEHOUSE)] = BuildingType.BUNKER
            else:
                types.append(t)
    return types[:9]


# Slot placement bans (slot == index in the 9-length layout list).
# Front slots are 1/4/7 (indices 0/3/6). Mirrors engine._assign_initial_defenders'
# intent: keep the HQ (which the attacker stack sits on) and the Armory/Hospital
# off the exposed front row so the enemy's attackers aren't dumped on the frontline.
FRONT_SLOTS = {0, 3, 6}                 # slots 1/4/7
HQ_BANNED_SLOTS = {0, 3, 6, 4, 8}       # slots 1/4/7/5/9
ARMORY_HOSPITAL_BANNED_SLOTS = {0, 3, 6}  # slots 1/4/7


def _place_layout(types: List[BuildingType], rng: random.Random) -> List[BuildingType]:
    """Place a list of building types into 9 slots, honoring the front-slot bans
    for HQ / Armory / Hospital. The remaining types fill the leftover slots
    randomly. Returns a 9-length layout indexed by slot."""
    layout: List[BuildingType] = [None] * 9
    all_slots = set(range(9))

    def place(bt: BuildingType, banned: set) -> None:
        free = list(all_slots - {s for s, v in enumerate(layout) if v is not None})
        valid = [s for s in free if s not in banned] or free  # fall back if over-constrained
        slot = rng.choice(valid)
        layout[slot] = bt

    # Place the restricted types first (most-constrained first).
    restricted = [
        (BuildingType.HEADQUARTERS, HQ_BANNED_SLOTS),
        (BuildingType.ARMORY, ARMORY_HOSPITAL_BANNED_SLOTS),
        (BuildingType.HOSPITAL, ARMORY_HOSPITAL_BANNED_SLOTS),
    ]
    remaining = list(types)
    for bt, banned in restricted:
        if bt in remaining:
            remaining.remove(bt)
            place(bt, banned)

    # Fill the rest into the open slots at random.
    open_slots = [s for s, v in enumerate(layout) if v is None]
    rng.shuffle(open_slots)
    for slot, bt in zip(open_slots, remaining):
        layout[slot] = bt
    return layout


def _make_layout(norm: float, rng: random.Random) -> List[BuildingType]:
    types = _fort_types(norm)
    types = types + [BuildingType.WAREHOUSE] * (9 - len(types))
    return _place_layout(types, rng)


def _assign_members(members: List[Member], building_order: List[int],
                    rng: random.Random) -> List[List[int]]:
    """Attackers stack in the HQ slot; enforcers spread across all buildings."""
    assignments = [[] for _ in range(9)]
    try:
        hq = building_order.index(BuildingType.HEADQUARTERS.spec["name_index"])
    except ValueError:
        hq = rng.randrange(9)
    enforcers = [i for i, m in enumerate(members)
                 if m.member_class == MemberClass.ENFORCER]
    others = [i for i, m in enumerate(members)
              if m.member_class != MemberClass.ENFORCER]
    assignments[hq].extend(others)
    for k, i in enumerate(enforcers):
        assignments[k % 9].append(i)
    return assignments


def build_enemy(underworld_power: float, name: str = "Rival Gang",
                seed: int = None) -> Empire:
    """Build a scaled enemy Empire for the given underworld power. The returned
    empire has members, building_order, and member_assignments pre-set, so the
    battle engine will not randomize it."""
    rng = random.Random(seed if seed is not None else int(underworld_power))
    norm = power_norm(underworld_power)

    members = _make_members(_member_count(norm), _member_level(norm), norm, rng)
    layout = _make_layout(norm, rng)
    order = buildings.building_order_from_layout(layout)

    # HQ level matches the empire's member count (base 40, +10 per level).
    count = len(members)
    hq_level = max(1, min(config.HQ_MAX_LEVEL,
                          math.ceil((count - config.BASE_MEMBER_CAP)
                                    / config.HQ_MEMBERS_PER_LEVEL)))
    levels = [1] * 9
    if BuildingType.HEADQUARTERS in layout:
        levels[layout.index(BuildingType.HEADQUARTERS)] = hq_level

    empire = Empire(name=name, members=members, is_player=False)
    empire.setup_buildings()
    empire.building_order = order
    empire.building_levels = levels
    empire.member_assignments = _assign_members(members, order, rng)
    return empire


def describe(underworld_power: float) -> dict:
    """Preview the scaled parameters (for UI/tests) without building the empire."""
    norm = power_norm(underworld_power)
    return {
        "norm": round(norm, 3),
        "members": _member_count(norm),
        "level": _member_level(norm),
        "forts": len(_fort_types(norm)),
    }

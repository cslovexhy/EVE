"""EVE - Enemy roster generation from a region's power.

Translates a single scalar ("power" — underworld_power for a gang, police_power
for the police boss; they are the SAME axis, police is just larger) into a
concrete enemy empire: member count, per-member level, rarity mix, and a
fortified building layout.

Scaling is **decade-tiered**: tier n = floor(log10(power)) clamped to [0,7]
(8 tiers). Member level is rolled per member within the tier's level band
[n*10+1, (n+1)*10], skewed by where power sits inside its decade. Buildings
follow an explicit 41-row build ladder (docs/building_progression.md) mapped to
tiers (tier 0 = all-warehouse base; tiers 1..6 = 6 ladder rows each; tier 7
absorbs the remaining rows 37..41), interpolated within a tier by the same
fraction. There is no gang/police special-casing of strength any more — the
only difference is which power scalar feeds in.
"""
import math
import random
from typing import List, Tuple

import config
import buildings
import ai_profiles
from models import Empire, Member, MemberClass, Rarity, BuildingType

MAX_MEMBERS = 80              # roster cap (docs/questions.md)
MIN_MEMBERS = 4

# --- Decade power tiers -----------------------------------------------------
# tier n = floor(log10(power)), clamped to [TIER_MIN, TIER_MAX] => 8 tiers.
# Each tier's member-level band is [n*10 + 1, (n+1)*10]: tier 0 -> 1..10,
# tier 1 -> 11..20, ..., tier 7 -> 71..80. Contiguous, no gaps.
TIER_MIN = 0
TIER_MAX = 7
LEVELS_PER_TIER = 10
MAX_LEVEL = (TIER_MAX + 1) * LEVELS_PER_TIER   # 80 (hard level ceiling)
# Skew exponent on the within-tier level center (frac**SKEW): <1 front-loads
# the climb so levels rise faster early in a decade (compensates for the data
# clustering at the low end of every decade). Owner chose skewed over symmetric.
LEVEL_SKEW = 0.7

REFERENCE_MAX_POWER = 1_060_611  # real underworld max (tier 6); kept for legacy
                                 # power_norm callers (member COUNT still uses it)


def power_tier(power: float) -> int:
    """Decade tier n = floor(log10(power)), clamped to [0, 7]."""
    if power is None or power <= 1:
        return TIER_MIN
    return max(TIER_MIN, min(TIER_MAX, int(math.floor(math.log10(power)))))


def tier_frac(power: float) -> float:
    """Where `power` sits inside its decade: frac = log10(power) - n, in [0, 1].
    0 at the tier floor (power = 10^n), ->1 at the ceiling (power -> 10^(n+1)).
    Clamped at the top tier so overflow powers read as frac = 1 (fully maxed)."""
    if power is None or power <= 1:
        return 0.0
    n = power_tier(power)
    if n >= TIER_MAX:
        # Top tier: interpolate across the whole last decade, clamp beyond it.
        return min(1.0, max(0.0, math.log10(power) - TIER_MAX))
    return max(0.0, min(1.0, math.log10(power) - n))


def tier_level_band(n: int) -> Tuple[int, int]:
    """(L_min, L_max) member-level band for tier n."""
    return n * LEVELS_PER_TIER + 1, (n + 1) * LEVELS_PER_TIER


def roll_member_level(power: float, rng: random.Random) -> int:
    """Roll ONE member's level for a city of the given power (skewed within the
    tier). Guarantees: power at a tier floor (frac=0) -> L_min for every member;
    at the ceiling (frac=1) -> L_max for every member; higher power -> higher
    expected level AND higher chance of rolling the max."""
    n = power_tier(power)
    l_min, l_max = tier_level_band(n)
    frac = tier_frac(power)
    span = l_max - l_min
    center = l_min + (frac ** LEVEL_SKEW) * span
    spread = span * frac * (1.0 - frac)        # 0 at both ends, peaks mid-tier
    level = round(center + rng.uniform(-1.0, 1.0) * spread)
    return int(max(l_min, min(l_max, level)))


def power_norm(power: float) -> float:
    """Map raw power to 0..1 via log-scale against the reference max. Retained
    only for member COUNT (which still uses the old smooth curve); level and
    buildings now use the decade-tier model above."""
    if power <= 0:
        return 0.0
    return min(1.0, math.log10(power + 1) / math.log10(REFERENCE_MAX_POWER + 1))


def _member_count(norm: float) -> int:
    return max(MIN_MEMBERS, round(MIN_MEMBERS + (MAX_MEMBERS - MIN_MEMBERS) * norm))


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


def _pick_rarity(norm: float, rng: random.Random) -> Rarity:
    """Rarity distribution shifts toward rare/super-rare as power rises.

    Legacy power-based model, kept as the fallback when a city's per-capita
    income is unknown (e.g. older callers / tests that pass only a power)."""
    if norm < 0.25:
        return Rarity.COMMON
    if norm < 0.5:
        return Rarity.UNCOMMON if rng.random() < (norm - 0.25) / 0.25 else Rarity.COMMON
    if norm < 0.75:
        return rng.choices([Rarity.COMMON, Rarity.UNCOMMON, Rarity.RARE],
                           weights=[1, 2, 2])[0]
    return rng.choices([Rarity.UNCOMMON, Rarity.RARE, Rarity.SUPER_RARE],
                       weights=[1, 2, 3])[0]


# Rarity enums in the same column order as config.RARITY_INCOME_BRACKETS weights.
_RARITY_BY_COLUMN = [Rarity.COMMON, Rarity.UNCOMMON, Rarity.RARE, Rarity.SUPER_RARE]


def per_capita_income(city: dict) -> float:
    """City GDP-per-capita in dollars (gdp_thousands * 1000 / population), or
    0.0 if the city lacks usable population/GDP. Safe on None / missing keys."""
    if not city:
        return 0.0
    pop = city.get("population") or 0
    gdp_k = city.get("gdp_thousands")
    if pop > 0 and gdp_k:
        return gdp_k * 1000.0 / pop
    return 0.0


def income_rarity_weights(income: float) -> List[int]:
    """The [common, uncommon, rare, super_rare] weight row for a per-capita
    income, from config.RARITY_INCOME_BRACKETS (first bracket whose upper bound
    exceeds the income)."""
    for upper, weights in config.RARITY_INCOME_BRACKETS:
        if income < upper:
            return weights
    return config.RARITY_INCOME_BRACKETS[-1][1]


def _pick_rarity_by_income(income: float, rng: random.Random) -> Rarity:
    """Roll one member's rarity from the city's per-capita income bracket."""
    weights = income_rarity_weights(income)
    return rng.choices(_RARITY_BY_COLUMN, weights=weights)[0]


def _name(cls: MemberClass, k: int) -> str:
    pool = _NAME_POOLS[cls]
    base = pool[(k // len(CLASS_ORDER)) % len(pool)]
    cycle = (k // len(CLASS_ORDER)) // len(pool)
    return base if cycle == 0 else f"{base} {cycle + 1}"


def _make_members(count: int, power: float, norm: float, rng: random.Random,
                  income: float = None) -> List[Member]:
    """Build `count` members. Each member's LEVEL is rolled independently from
    the city's `power` tier (skewed within the decade — see roll_member_level),
    so a roster has a believable spread that collapses to all-min at a tier
    floor and all-max at a tier ceiling. Applies to BOTH gang and police (the
    only difference is the magnitude of `power`). Rarity comes from the city's
    per-capita `income` bracket when provided; otherwise it falls back to the
    legacy power-based `norm` model.

    Levels use a SEPARATE RNG stream (derived from `rng`) so the per-member
    level sequence is independent of how many draws the rarity path consumes.
    That keeps a city's levels — and thus its net worth — stable regardless of
    whether income-based or power-based rarity is used, so police_net_worth's
    preview (built without income) matches the real fight's net worth exactly."""
    level_rng = random.Random(rng.random())
    members = []
    for k in range(count):
        cls = CLASS_ORDER[k % len(CLASS_ORDER)]
        if income is not None:
            rarity = _pick_rarity_by_income(income, rng)
        else:
            rarity = _pick_rarity(norm, rng)
        members.append(Member(name=_name(cls, k), member_class=cls,
                              level=roll_member_level(power, level_rng),
                              rarity=rarity))
    return members


# --- Build progression ladder (docs/building_progression.md) ----------------
# Fixed slot roles (0-indexed). The ladder builds into these specific slots so
# HQ/Armory/Hospital stay off the exposed front row (slots 0/3/6) exactly as the
# old placement bans intended, and the two Bunkers sit on the front corners.
#   S1=0 Sniper Tower, S2=1 Research Lab, S3=2 Hospital, S4=3 Bunker,
#   S5=4 HQ, S6=5 Nuclear Silo, S7=6 Bunker, S8=7 Armory, S9=8 Safehouse(late)
_SLOT = {"St": 0, "Rl": 1, "Ho": 2, "Bu4": 3, "HQ": 4, "Nu": 5,
         "Bu7": 6, "Ar": 7, "Sf9": 8}

# Each ladder action is (slot_index, BuildingType, level). Applying actions 1..k
# in order, starting from the all-Warehouse base (row 0), yields the build state
# at row k. Gates are baked into the ORDER: Research Lab is first built only
# after HQ L3 (row 15 -> row 16), Nuclear Silo only after HQ L4 (row 26 -> 27),
# and slot-9 Warehouse->Safehouse only after HQ L4 (row 28). See the doc.
WH = BuildingType.WAREHOUSE
_LADDER_ACTIONS = [
    # row 1-6: establish HQ, 2 safehouses, armory, hospital, sniper tower (L1)
    (_SLOT["HQ"],  BuildingType.HEADQUARTERS, 1),
    (_SLOT["Bu4"], BuildingType.SAFEHOUSE,    1),
    (_SLOT["Bu7"], BuildingType.SAFEHOUSE,    1),
    (_SLOT["Ar"],  BuildingType.ARMORY,       1),
    (_SLOT["Ho"],  BuildingType.HOSPITAL,     1),
    (_SLOT["St"],  BuildingType.SNIPER_TOWER, 1),
    # row 7-10: HQ L2, Armory L2, Hospital L2, Sniper Tower L2
    (_SLOT["HQ"],  BuildingType.HEADQUARTERS, 2),
    (_SLOT["Ar"],  BuildingType.ARMORY,       2),
    (_SLOT["Ho"],  BuildingType.HOSPITAL,     2),
    (_SLOT["St"],  BuildingType.SNIPER_TOWER, 2),
    # row 11-14: safehouses L2, L2, L3, L3
    (_SLOT["Bu4"], BuildingType.SAFEHOUSE,    2),
    (_SLOT["Bu7"], BuildingType.SAFEHOUSE,    2),
    (_SLOT["Bu4"], BuildingType.SAFEHOUSE,    3),
    (_SLOT["Bu7"], BuildingType.SAFEHOUSE,    3),
    # row 15: HQ L3  (gate: Research Lab may now be built)
    (_SLOT["HQ"],  BuildingType.HEADQUARTERS, 3),
    # row 16: BUILD Research Lab (L1)  [gated after HQ3]
    (_SLOT["Rl"],  BuildingType.RESEARCH_LAB, 1),
    # row 17-21: Armory L3, Hospital L3, Sniper Tower L3, Research Lab L2, L3
    (_SLOT["Ar"],  BuildingType.ARMORY,       3),
    (_SLOT["Ho"],  BuildingType.HOSPITAL,     3),
    (_SLOT["St"],  BuildingType.SNIPER_TOWER, 3),
    (_SLOT["Rl"],  BuildingType.RESEARCH_LAB, 2),
    (_SLOT["Rl"],  BuildingType.RESEARCH_LAB, 3),
    # row 22-25: safehouses -> Bunker (L1), then Bunkers L2
    (_SLOT["Bu4"], BuildingType.BUNKER,       1),
    (_SLOT["Bu7"], BuildingType.BUNKER,       1),
    (_SLOT["Bu4"], BuildingType.BUNKER,       2),
    (_SLOT["Bu7"], BuildingType.BUNKER,       2),
    # row 26: HQ L4  (gate: Nuclear Silo + slot-9 Safehouse may now be built)
    (_SLOT["HQ"],  BuildingType.HEADQUARTERS, 4),
    # row 27: BUILD Nuclear Silo (L1)  [gated after HQ4]
    (_SLOT["Nu"],  BuildingType.NUCLEAR_SILO, 1),
    # row 28: BUILD slot-9 Safehouse (Warehouse->Safehouse)  [gated after HQ4]
    (_SLOT["Sf9"], BuildingType.SAFEHOUSE,    1),
    # row 29-33: Armory L4, Hospital L4, Sniper Tower L4, Research Lab L4, Silo L2
    (_SLOT["Ar"],  BuildingType.ARMORY,       4),
    (_SLOT["Ho"],  BuildingType.HOSPITAL,     4),
    (_SLOT["St"],  BuildingType.SNIPER_TOWER, 4),
    (_SLOT["Rl"],  BuildingType.RESEARCH_LAB, 4),
    (_SLOT["Nu"],  BuildingType.NUCLEAR_SILO, 2),
    # row 34-37: Silo L3, Bunkers L3, Silo L4
    (_SLOT["Nu"],  BuildingType.NUCLEAR_SILO, 3),
    (_SLOT["Bu4"], BuildingType.BUNKER,       3),
    (_SLOT["Bu7"], BuildingType.BUNKER,       3),
    (_SLOT["Nu"],  BuildingType.NUCLEAR_SILO, 4),
    # row 38-39: Bunkers L4
    (_SLOT["Bu4"], BuildingType.BUNKER,       4),
    (_SLOT["Bu7"], BuildingType.BUNKER,       4),
    # row 40-41: slot-9 Safehouse L2, L3
    (_SLOT["Sf9"], BuildingType.SAFEHOUSE,    2),
    (_SLOT["Sf9"], BuildingType.SAFEHOUSE,    3),
]
LADDER_LEN = len(_LADDER_ACTIONS)   # 41


def ladder_state(row: int) -> Tuple[List[BuildingType], List[int]]:
    """Build state after applying ladder rows 1..row to the all-Warehouse base.
    row 0 => all Warehouses L1. Returns (layout[9] types, levels[9])."""
    layout = [WH] * 9
    levels = [1] * 9
    for i in range(max(0, min(row, LADDER_LEN))):
        slot, bt, lvl = _LADDER_ACTIONS[i]
        layout[slot] = bt
        levels[slot] = lvl
    return layout, levels


# --- Row <-> tier mapping ---------------------------------------------------
# tier 0 = base (row 0, no upgrades); tier n (1..6) = rows [1+6*(n-1), 6*n];
# the final tier n=7 absorbs the remaining rows [37, 41]. Within a tier the row
# is chosen by interpolating `frac` across the tier's row span.
ROWS_PER_TIER = 6


def tier_row_span(n: int) -> Tuple[int, int]:
    """(first_row, last_row) ladder rows for tier n. Tier 0 is the base-only
    row 0; the top tier runs to the end of the ladder."""
    if n <= 0:
        return 0, 0
    first = 1 + ROWS_PER_TIER * (n - 1)
    if n >= TIER_MAX:
        return first, LADDER_LEN          # top tier absorbs overflow (37..41)
    return first, ROWS_PER_TIER * n


def ladder_row_for_power(power: float) -> int:
    """The ladder row (0..41) a city of this power builds to, interpolating
    within its tier by `frac`."""
    n = power_tier(power)
    first, last = tier_row_span(n)
    if n <= 0:
        # Tier 0: interpolate from the base (row 0) up to row... still 0 (no
        # upgrade rows belong to tier 0), so a tier-0 city is always the base.
        return 0
    frac = tier_frac(power)
    # Interpolate across the tier's upgrade rows. frac=0 -> first row of the
    # block (the first upgrade), frac=1 -> last row of the block.
    span = last - first
    return int(round(first + frac * span))


def _make_layout_and_levels(power: float) -> Tuple[List[BuildingType], List[int]]:
    """The 9-slot (layout, levels) for a city of the given power, straight from
    the build ladder (no randomness — slot roles are fixed)."""
    return ladder_state(ladder_row_for_power(power))


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
                seed: int = None, police: bool = False,
                profile_seed: str = None,
                per_capita_income: float = None) -> Empire:
    """Build a scaled enemy Empire for the given power. The returned empire has
    members, building_order, member_assignments, and ai_profile_name pre-set, so
    the battle engine will not randomize it.

    police=True no longer forces any special maxing. Under the unified-power
    model it only affects the NAME and the AI profile (always the toughest,
    `hard_path`); the roster level and buildings fall out of the same tier math
    as a gang, just driven by the city's (much larger) police_power. So a police
    boss is harder purely because its power is higher — the hardest, repeatable
    end-of-city fight — not via overrides.

    profile_seed is a stable string (the city id) used to deterministically pick
    the AI targeting personality. Folded with the side (gang/police) so a city's
    gang and police get independent but individually stable strategies. Falls
    back to `name` when not supplied.

    per_capita_income (city GDP-per-capita, $) drives member rarity via
    config.RARITY_INCOME_BRACKETS when supplied; richer cities field
    higher-rarity gangs. When None, rarity falls back to the legacy power-based
    model (keeps older callers/tests stable).
    """
    rng = random.Random(seed if seed is not None else int(underworld_power))
    power = underworld_power
    norm = power_norm(power)

    # Per-member level is rolled from the power tier (skewed within the decade),
    # for BOTH gang and police — police is simply a larger `power`, so its
    # members naturally roll higher. No flat POLICE_LEVEL override any more.
    members = _make_members(_member_count(norm), power, norm, rng,
                            income=per_capita_income)

    # Buildings come straight from the tier-mapped build ladder (fixed slot
    # roles, deterministic — no random placement, no police max-override).
    layout, levels = _make_layout_and_levels(power)
    order = buildings.building_order_from_layout(layout)

    empire = Empire(name=name, members=members, is_player=False)
    empire.setup_buildings()
    empire.building_order = order
    empire.building_levels = levels
    empire.member_assignments = _assign_members(members, order, rng)
    empire.ai_profile_name = ai_profiles.profile_name_for(
        profile_seed if profile_seed is not None else name, police=police)
    return empire


def describe(underworld_power: float, profile_seed: str = None) -> dict:
    """Preview the scaled parameters (for UI/tests) without building the empire.
    When profile_seed is given, also reports the deterministic gang/police AI
    strategy labels for that city.

    `level` is the tier's MAX level (the ceiling a top-of-decade city reaches);
    `level_band` is the full (min, max) band; `tier` is the decade tier; `row`
    is the build-ladder row the power maps to."""
    power = underworld_power
    norm = power_norm(power)
    n = power_tier(power)
    l_min, l_max = tier_level_band(n)
    info = {
        "norm": round(norm, 3),
        "members": _member_count(norm),
        "tier": n,
        "level": l_max,                 # tier ceiling (back-compat with old key)
        "level_band": (l_min, l_max),
        "row": ladder_row_for_power(power),
    }
    if profile_seed is not None:
        info["gang_strategy"] = city_strategies(profile_seed)["gang"]
        info["police_strategy"] = city_strategies(profile_seed)["police"]
    return info


def city_strategies(profile_seed: str) -> dict:
    """Deterministic AI strategy display labels for a city, without building the
    empire. Returns {'gang': <label>, 'police': <label>} for the city detail UI.
    Mirrors exactly what build_enemy assigns for each side."""
    gang = ai_profiles.profile_name_for(profile_seed, police=False)
    police = ai_profiles.profile_name_for(profile_seed, police=True)
    return {
        "gang": ai_profiles.display_name(gang),
        "police": ai_profiles.display_name(police),
    }


def police_net_worth(police_power: float) -> int:
    """Net worth (100 x sum of member levels) of the police boss for a city,
    without needing the caller to build it. Member levels are now rolled per
    member from the power tier, so this builds the roster deterministically with
    the SAME default seed build_enemy uses (int(power)) and sums real levels —
    guaranteeing the UI preview equals exactly what _run_police pays. (Net worth
    depends only on levels, so rarity/income are irrelevant here.)"""
    boss = build_enemy(police_power, police=True)
    return 100 * sum(m.level for m in boss.members)

"""EVE - Data Models for Members, Buildings, and Empires"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
import config


class MemberClass(Enum):
    ENFORCER = "enforcer"
    SNIPER = "sniper"
    ASSASSIN = "assassin"
    DEMOLITIONIST = "demolitionist"


class Rarity(Enum):
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    SUPER_RARE = "super_rare"


class MemberState(Enum):
    IDLE = "idle"               # In building, no orders
    DEFENDING = "defending"     # Actively defending a building
    ATTACKING = "attacking"     # Moving to/fighting at enemy building
    MOVING = "moving"           # In transit
    DEAD = "dead"               # Knocked out this battle


class OrderAction(Enum):
    ATTACK = "attack"
    DEFEND = "defend"


class ProjectileType(Enum):
    SNIPER = "sniper"
    DEMO = "demo"
    ENFORCER = "enforcer"
    ASSASSIN = "assassin"


class BuildingType(Enum):
    """The 9 building types. Every building starts as WAREHOUSE and can be
    upgraded along the chain defined in config.BUILDING_TYPES."""
    WAREHOUSE = "warehouse"
    SAFEHOUSE = "safehouse"
    ARMORY = "armory"
    HOSPITAL = "hospital"
    RESEARCH_LAB = "research_lab"
    SNIPER_TOWER = "sniper_tower"
    NUCLEAR_SILO = "nuclear_silo"
    HEADQUARTERS = "headquarters"
    BUNKER = "bunker"

    @property
    def spec(self) -> dict:
        """Config entry for this building type."""
        return config.BUILDING_TYPES[self.value]


@dataclass
class Projectile:
    """A visible projectile traveling from attacker to target."""
    x: float
    y: float
    target_x: float
    target_y: float
    speed: float              # Pixels per second
    damage: float             # Damage to deal on impact
    projectile_type: ProjectileType
    target_member: Optional['Member'] = None    # If targeting a member
    target_building: Optional['Building'] = None  # If targeting a building
    hit_building_directly: bool = False  # True = damage building, False = damage member
    missed: bool = False      # If this shot will miss (pre-determined)
    alive: bool = True        # Set to False when it hits or target dies


@dataclass
class Member:
    """A single empire member (fighter)."""
    name: str
    member_class: MemberClass
    level: int
    rarity: Rarity
    
    # Runtime state (reset each battle)
    hp: float = 0
    max_hp: float = 0
    state: MemberState = MemberState.IDLE
    x: float = 0.0
    y: float = 0.0
    target_x: float = 0.0
    target_y: float = 0.0
    assigned_building: Optional[int] = None  # Building index (0-8)
    target_building: Optional[int] = None    # Attack/defend target
    attack_cooldown: float = 0.0
    # Ammo
    ammo: int = config.AMMO_MAX
    ammo_regen_timer: float = 0.0
    # Attack mode
    attack_once: bool = False  # If True, return to defending after one shot
    
    def __post_init__(self):
        self.reset_for_battle()
    
    def reset_for_battle(self):
        """Reset HP and state for a new battle."""
        stats = self.get_stats()
        self.max_hp = stats["hp"]
        self.hp = self.max_hp
        self.state = MemberState.IDLE
        self.attack_cooldown = 0.0
        self.target_building = None
        self.ammo = config.AMMO_MAX
        self.ammo_regen_timer = 0.0
    
    def get_stats(self) -> dict:
        """Calculate stats based on level and rarity."""
        base = config.BASE_STATS[self.member_class.value]
        mult = config.RARITY_MULTIPLIERS[self.rarity.value]
        level_mult = 1.0 + (self.level - 1) * 0.15  # 15% per level
        
        return {
            "hp": base["hp"] * mult * level_mult,
            "damage_player": base["damage_player"] * mult * level_mult,
            "damage_building": base["damage_building"] * mult * level_mult,
            "mitigation": base["mitigation"],  # Doesn't scale with level
            "speed": base["speed"],
            "attack_interval": base["attack_interval"],  # Doesn't scale
        }
    
    @property
    def is_alive(self) -> bool:
        return self.state != MemberState.DEAD
    
    @property
    def is_available(self) -> bool:
        """Can this member respond to a new order?"""
        return self.state in (MemberState.IDLE, MemberState.DEFENDING, MemberState.ATTACKING, MemberState.MOVING)
    
    def take_damage(self, raw_damage: float):
        """Apply damage after mitigation."""
        stats = self.get_stats()
        actual = raw_damage * (1.0 - stats["mitigation"])
        self.hp -= actual
        if self.hp <= 0:
            self.hp = 0
            self.state = MemberState.DEAD

    # --- persistence (roster / backup force) -----------------------------
    def to_dict(self) -> dict:
        """Serialize the persistent identity of this member (not battle state)."""
        return {
            "name": self.name,
            "member_class": self.member_class.value,
            "level": self.level,
            "rarity": self.rarity.value,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Member":
        return cls(
            name=data["name"],
            member_class=MemberClass(data["member_class"]),
            level=int(data.get("level", 1)),
            rarity=Rarity(data.get("rarity", Rarity.COMMON.value)),
        )

    def copy_identity(self) -> "Member":
        """A fresh Member with the same identity (used when recruiting)."""
        return Member(name=self.name, member_class=self.member_class,
                      level=self.level, rarity=self.rarity)


@dataclass
class Building:
    """A building on the 3x3 grid."""
    index: int              # 0-8 position on grid
    building_type: BuildingType = BuildingType.WAREHOUSE
    hp: float = config.BUILDING_BASE_HP
    max_hp: float = config.BUILDING_BASE_HP
    level: int = 1
    defenders: list = field(default_factory=list)  # List of Member refs
    destroyed: bool = False

    def __post_init__(self):
        # HP is driven by building type. Warehouse keeps BUILDING_BASE_HP.
        self.apply_type_hp()

    def apply_type_hp(self):
        """Set max_hp/hp from the current building type (HQ scales with level)."""
        if self.building_type == BuildingType.HEADQUARTERS:
            lvl = max(1, min(self.level, config.HQ_MAX_LEVEL))
            self.max_hp = config.HQ_LEVEL_HP.get(lvl, config.HQ_LEVEL_HP[1])
        else:
            self.max_hp = self.building_type.spec["hp"]
        self.hp = self.max_hp
        self.destroyed = False

    @property
    def type_name(self) -> str:
        """Human-readable building type name."""
        return self.building_type.spec["display_name"]

    def take_damage(self, damage: float):
        """Apply damage to building."""
        self.hp -= damage
        if self.hp <= 0:
            self.hp = 0
            self.destroyed = True

    @property
    def is_front_row(self) -> bool:
        """Buildings 0, 3, 6 are front row (leftmost column)."""
        return self.index % 3 == 0


@dataclass
class Order:
    """A player order: class → target → action."""
    member_class: MemberClass
    target_building: int  # 0-8 index on ENEMY grid (for attack) or OWN grid (for defend)
    action: OrderAction
    issued_at: float = 0.0  # Battle time when issued


@dataclass
class Empire:
    """One side of the battle."""
    name: str
    members: list = field(default_factory=list)       # List of Member
    buildings: list = field(default_factory=list)      # List of Building (9)
    points: int = 0
    is_player: bool = True
    health_packs: int = config.HEALTH_PACKS_START
    money: int = config.STARTING_MONEY

    def setup_buildings(self):
        """Initialize 9 buildings for battle (all Warehouses by default)."""
        self.buildings = [Building(index=i) for i in range(9)]

    def apply_building_layout(self, type_layout):
        """Set building types from a layout list of 9 BuildingType (or type-name
        strings), refreshing each building's HP to match its type. Slots default
        to WAREHOUSE where the layout entry is missing/None."""
        if not self.buildings:
            self.setup_buildings()
        for i, building in enumerate(self.buildings):
            entry = type_layout[i] if i < len(type_layout) else None
            if entry is None:
                bt = BuildingType.WAREHOUSE
            elif isinstance(entry, BuildingType):
                bt = entry
            else:
                bt = BuildingType(entry)
            building.building_type = bt
            building.apply_type_hp()

    def count_building_type(self, building_type: BuildingType) -> int:
        """How many buildings of the given type this empire currently has."""
        return sum(1 for b in self.buildings if b.building_type == building_type)

    def hq_level(self) -> int:
        """Highest active HQ level, or 0 if the empire has no standing HQ."""
        levels = [b.level for b in self.buildings
                  if b.building_type == BuildingType.HEADQUARTERS and not b.destroyed]
        return max(levels) if levels else 0

    def member_cap(self) -> int:
        """Max roster size: base cap, +HQ_MEMBERS_PER_LEVEL per HQ level."""
        return config.BASE_MEMBER_CAP + config.HQ_MEMBERS_PER_LEVEL * self.hq_level()
    
    def get_members_by_class(self, member_class: MemberClass) -> list:
        """Get all living members of a given class."""
        return [m for m in self.members 
                if m.member_class == member_class and m.is_alive]
    
    def get_available_by_class(self, member_class: MemberClass) -> list:
        """Get available (can respond to orders) members of a class."""
        return [m for m in self.members 
                if m.member_class == member_class and m.is_available]
    
    def get_alive_members(self) -> list:
        return [m for m in self.members if m.is_alive]
    
    def get_dead_by_class(self, member_class: MemberClass) -> list:
        """Get all dead members of a given class."""
        return [m for m in self.members
                if m.member_class == member_class and m.state == MemberState.DEAD]
    
    def heal_building(self, building_index: int):
        """Use a health pack to revive one random dead defender ASSIGNED to the
        given building, reviving them IN PLACE. Shared by the player (H → click
        building) and the AI so both sides heal identically. Does not relocate
        the member or change the base layout. Returns the revived member, or
        None if no pack is available or no dead defender is assigned there."""
        import random
        if self.health_packs <= 0:
            return None
        if not (0 <= building_index < len(self.buildings)):
            return None
        building = self.buildings[building_index]
        if building.destroyed:
            return None

        dead_here = [m for m in self.members
                     if m.state == MemberState.DEAD
                     and m.assigned_building == building_index]
        if not dead_here:
            return None

        member = random.choice(dead_here)
        member.hp = member.max_hp
        member.state = MemberState.DEFENDING
        member.attack_cooldown = 0.0
        member.target_building = None
        # assigned_building is already building_index — keep it as-is.
        member.x = building.x + random.uniform(-15, 15)
        member.y = building.y + random.uniform(-15, 15)
        if member not in building.defenders:
            building.defenders.append(member)

        self.health_packs -= 1
        return member
    
    @property
    def total_building_hp(self) -> float:
        return sum(b.hp for b in self.buildings)
    
    @property
    def buildings_destroyed(self) -> int:
        return sum(1 for b in self.buildings if b.destroyed)


def create_starting_roster(empire_name: str, is_player: bool = True) -> Empire:
    """Create an empire with 40 starting members (10 per class)."""
    members = default_player_members() if is_player else default_enemy_members()
    empire = Empire(name=empire_name, members=members, is_player=is_player)
    empire.setup_buildings()
    return empire


# Rarity strength order (weakest -> strongest), for picking the best recruit.
RARITY_ORDER = {
    Rarity.COMMON: 0,
    Rarity.UNCOMMON: 1,
    Rarity.RARE: 2,
    Rarity.SUPER_RARE: 3,
}


def _PLAYER_NAMES_BY_CLASS():
    return {
        MemberClass.ENFORCER: [
            "Hammer", "Duke", "Tank", "Brick", "Ironside",
            "Magnus", "Bulwark", "Titan", "Rocco", "Slab",
        ],
        MemberClass.SNIPER: [
            "Fox", "Kate", "Hawkeye", "Scope", "Viper",
            "Longshot", "Whisper", "Deadshot", "Iris", "Bolt",
        ],
        MemberClass.ASSASSIN: [
            "Phantom", "Nightshade", "Shadow", "Wraith", "Stiletto",
            "Venom", "Specter", "Mirage", "Silhouette", "Dagger",
        ],
        MemberClass.DEMOLITIONIST: [
            "Hotwire", "Blade", "Fuse", "Bomber", "Sparks",
            "Inferno", "Nitro", "Torch", "Kaboom", "Blast",
        ],
    }


def _ENEMY_NAMES_BY_CLASS():
    return {
        MemberClass.ENFORCER: [
            "Gustavo", "Salvatore", "Brutus", "Goliath", "Mammoth",
            "Ox", "Rhino", "Grizzly", "Boulder", "Colossus",
        ],
        MemberClass.SNIPER: [
            "Gunslinger", "Razor", "Crosshair", "Marksman", "Eagle",
            "Sharpshot", "Glint", "Reticle", "Archer", "Pierce",
        ],
        MemberClass.ASSASSIN: [
            "Ghost", "Lotus", "Cobra", "Raven", "Scorpion",
            "Shade", "Fang", "Mamba", "Eclipse", "Null",
        ],
        MemberClass.DEMOLITIONIST: [
            "Diablo", "Caine", "Arson", "Pyro", "Napalm",
            "Havoc", "Crater", "Mortar", "Shrapnel", "Landmine",
        ],
    }


def _members_from_names(names_by_class) -> list:
    members = []
    for cls in MemberClass:
        for name in names_by_class[cls]:
            members.append(Member(name=name, member_class=cls,
                                  level=3, rarity=Rarity.COMMON))
    return members


def default_player_members() -> list:
    """The default 40 player members (10 per class), used to seed a new roster."""
    return _members_from_names(_PLAYER_NAMES_BY_CLASS())


def default_enemy_members() -> list:
    return _members_from_names(_ENEMY_NAMES_BY_CLASS())


def top_rarity_recruit(empire: "Empire", rng=None) -> Optional["Member"]:
    """Pick a recruit from a (defeated) empire: the highest-rarity member,
    breaking ties randomly, then by highest level. Returns a fresh Member with
    the same identity, or None if the empire has no members."""
    import random as _random
    rng = rng or _random
    if not empire.members:
        return None
    best_rarity = max(RARITY_ORDER[m.rarity] for m in empire.members)
    pool = [m for m in empire.members if RARITY_ORDER[m.rarity] == best_rarity]
    top_level = max(m.level for m in pool)
    pool = [m for m in pool if m.level == top_level]
    return rng.choice(pool).copy_identity()

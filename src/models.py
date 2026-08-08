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
    # Stealth (assassins only)
    stealthed: bool = False
    time_since_combat: float = 0.0
    
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
        self.stealthed = False
        self.time_since_combat = 0.0
    
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
        # Break stealth on being hit
        self.stealthed = False
        self.time_since_combat = 0.0
        if self.hp <= 0:
            self.hp = 0
            self.state = MemberState.DEAD


@dataclass
class Building:
    """A building on the 3x3 grid."""
    index: int              # 0-8 position on grid
    hp: float = config.BUILDING_BASE_HP
    max_hp: float = config.BUILDING_BASE_HP
    level: int = 1
    defenders: list = field(default_factory=list)  # List of Member refs
    destroyed: bool = False
    
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
    
    def setup_buildings(self):
        """Initialize 9 buildings for battle."""
        self.buildings = [Building(index=i) for i in range(9)]
    
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
    
    @property
    def total_building_hp(self) -> float:
        return sum(b.hp for b in self.buildings)
    
    @property
    def buildings_destroyed(self) -> int:
        return sum(1 for b in self.buildings if b.destroyed)


def create_starting_roster(empire_name: str, is_player: bool = True) -> Empire:
    """Create an empire with 40 starting members (10 per class)."""
    names_by_class = {
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

    enemy_names = {
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

    chosen_names = names_by_class if is_player else enemy_names

    members = []
    for cls in MemberClass:
        for name in chosen_names[cls]:
            member = Member(
                name=name,
                member_class=cls,
                level=3,
                rarity=Rarity.COMMON,
            )
            members.append(member)

    empire = Empire(name=empire_name, members=members, is_player=is_player)
    empire.setup_buildings()
    return empire

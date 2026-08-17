"""EVE - Persistent player profile / game state.

Holds progression that survives across screens and battles:
  - money (primary currency)
  - building_layout: the 9-slot EvE base as BuildingType (upgraded in EVE Layout)
  - conquered: set of city ids the player has taken on the map

Persisted to player_profile.json next to the project root.
"""
import json
import os
from dataclasses import dataclass, field
from typing import List, Optional, Set

import config
import world_map as wm
from models import (
    BuildingType, Empire, MemberClass, Member,
    default_player_members,
)

PROFILE_PATH = os.path.join(os.path.dirname(__file__), "..", "player_profile.json")


def default_member_assignments(members) -> List[List[int]]:
    """Default distribution: non-enforcers in slot 3 (index 2), enforcers spread
    across the other slots. Returns 9 lists of member indices."""
    assignments = [[] for _ in range(9)]
    enforcers = [i for i, m in enumerate(members)
                 if m.member_class == MemberClass.ENFORCER]
    others = [i for i, m in enumerate(members)
              if m.member_class != MemberClass.ENFORCER]
    assignments[2] = list(others)
    other_slots = [0, 1, 3, 4, 5, 6, 7, 8]
    for i, ei in enumerate(enforcers):
        assignments[other_slots[i % len(other_slots)]].append(ei)
    return assignments


@dataclass
class GameState:
    money: int = config.STARTING_MONEY
    # 9 building slots; everyone starts as a Warehouse.
    building_layout: List[BuildingType] = field(
        default_factory=lambda: [BuildingType.WAREHOUSE for _ in range(9)]
    )
    # Per-slot building levels (mainly HQ level 1..4). Defaults to all level 1.
    building_levels: List[int] = field(default_factory=lambda: [1] * 9)
    conquered: Set[str] = field(default_factory=set)
    # 9 lists of member indices (into the active roster). None until set.
    member_assignments: Optional[List[List[int]]] = None
    # The player's active fighting roster (persisted; grows via recruits). Empty
    # until seeded with the default 40 on first load.
    roster: List[Member] = field(default_factory=list)
    # The backup force / bench: recruits won from defeated empires wait here
    # until moved into the active roster. Capped at config.BACKUP_FORCE_CAP.
    backup: List[Member] = field(default_factory=list)
    # The player's birthplace city id ("Country/State/City"). None until chosen
    # on first run; determines the home state/country for map gating.
    home_city: Optional[str] = None

    # --- persistence -----------------------------------------------------
    @classmethod
    def load(cls) -> "GameState":
        """Load profile from disk, or return a fresh default profile."""
        if not os.path.exists(PROFILE_PATH):
            return cls()
        try:
            with open(PROFILE_PATH, "r") as f:
                data = json.load(f)
            layout = [BuildingType(v) for v in data.get("building_layout", [])]
            if len(layout) != 9:
                layout = [BuildingType.WAREHOUSE for _ in range(9)]
            levels = data.get("building_levels") or []
            if len(levels) != 9:
                levels = [1] * 9

            # Roster / backup force. Seed the default 40 for legacy saves that
            # predate persisted rosters (or an empty roster).
            roster = [Member.from_dict(d) for d in data.get("roster", [])]
            if not roster:
                roster = default_player_members()
            backup = [Member.from_dict(d) for d in data.get("backup", [])]
            backup = backup[:config.BACKUP_FORCE_CAP]

            member_assignments = data.get("member_assignments")
            if not _valid_assignments(member_assignments, len(roster)):
                member_assignments = None
            state = cls(
                money=int(data.get("money", config.STARTING_MONEY)),
                building_layout=layout,
                building_levels=[max(1, int(x)) for x in levels],
                conquered=set(data.get("conquered", [])),
                member_assignments=member_assignments,
                roster=roster,
                backup=backup,
                home_city=data.get("home_city"),
            )
            # Self-heal: if the saved home city no longer exists in the world
            # data (e.g. the map changed), reset birthplace + territory so the
            # player re-picks a valid starting city.
            if state.home_city and wm.get_city(state.home_city) is None:
                state.home_city = None
                state.conquered = set()
            return state
        except (json.JSONDecodeError, ValueError, TypeError, KeyError):
            return cls()

    def save(self) -> None:
        data = {
            "money": self.money,
            "building_layout": [bt.value for bt in self.building_layout],
            "building_levels": self.building_levels,
            "conquered": sorted(self.conquered),
            "member_assignments": self.member_assignments,
            "roster": [m.to_dict() for m in self.roster],
            "backup": [m.to_dict() for m in self.backup],
            "home_city": self.home_city,
        }
        with open(PROFILE_PATH, "w") as f:
            json.dump(data, f, indent=2)

    # --- helpers ---------------------------------------------------------
    def is_conquered(self, city_id: str) -> bool:
        return city_id in self.conquered

    def mark_conquered(self, city_id: str) -> None:
        self.conquered.add(city_id)

    # --- birthplace / map-scope gating -----------------------------------
    def set_birthplace(self, city_id: str) -> None:
        """Choose the starting city: becomes home and the first conquered city."""
        self.home_city = city_id
        self.mark_conquered(city_id)

    def home_location(self):
        """(country, state, county, city) of the home city, or None if unset."""
        if not self.home_city:
            return None
        return wm.split_city_id(self.home_city)

    def owns_entire_county(self, country: str, state: str, county: str) -> bool:
        ids = wm.county_city_ids(country, state, county)
        return bool(ids) and set(ids) <= self.conquered

    def owns_entire_state(self, country: str, state: str) -> bool:
        ids = wm.state_city_ids(country, state)
        return bool(ids) and set(ids) <= self.conquered

    def owns_entire_country(self, country: str) -> bool:
        ids = wm.country_city_ids(country)
        return bool(ids) and set(ids) <= self.conquered

    def scope(self) -> str:
        """Current map-visibility scope, expanding as you conquer:
            'none'    - no birthplace chosen yet
            'county'  - only your home county's cities are visible/challengeable
            'state'   - own the whole home county -> all counties in the state
            'country' - own the whole home state -> all states in the country
            'world'   - own the whole home country -> all countries
        """
        loc = self.home_location()
        if loc is None:
            return "none"
        country, state, county, _ = loc
        if self.owns_entire_country(country):
            return "world"
        if self.owns_entire_state(country, state):
            return "country"
        if self.owns_entire_county(country, state, county):
            return "state"
        return "county"

    def ensure_member_assignments(self, members) -> List[List[int]]:
        """Return member assignments, initializing to the default distribution
        (for the given roster) if not set or inconsistent with the roster size."""
        if not _valid_assignments(self.member_assignments, len(members)):
            self.member_assignments = default_member_assignments(members)
        return self.member_assignments

    # --- roster / backup force -------------------------------------------
    def ensure_roster(self) -> List[Member]:
        """Guarantee the active roster is seeded (default 40 for a fresh game)."""
        if not self.roster:
            self.roster = default_player_members()
        return self.roster

    def build_player_empire(self, name: str = "Your Empire") -> Empire:
        """Build a battle-ready player Empire from the persisted roster. Uses
        fresh Member copies so battle state never mutates the saved roster."""
        self.ensure_roster()
        members = [m.copy_identity() for m in self.roster]
        empire = Empire(name=name, members=members, is_player=True)
        empire.setup_buildings()
        self.apply_to_empire(empire)
        return empire

    def apply_to_empire(self, empire: Empire) -> None:
        """Push the persistent money + building layout (+ levels + member
        assignments) onto a battle empire whose members are the active roster."""
        import buildings
        empire.money = self.money
        empire.apply_building_layout(list(self.building_layout))
        buildings.apply_building_levels(empire, list(self.building_levels))
        assignments = self.ensure_member_assignments(empire.members)
        empire.member_assignments = [list(s) for s in assignments]

    def roster_over_cap(self) -> bool:
        """True if the active roster exceeds the HQ-gated cap (blocks war start)."""
        return len(self.roster) > self.member_cap()

    def add_recruit(self, member: Member) -> bool:
        """Add a won recruit to the backup force. Returns False if it's full."""
        if len(self.backup) >= config.BACKUP_FORCE_CAP:
            return False
        self.backup.append(member)
        return True

    def _default_assign_slot(self) -> int:
        """Building slot to drop a newly-activated member into: the standing HQ
        if there is one, else the slot currently holding the fewest members."""
        self.ensure_member_assignments(self.roster)
        for i, bt in enumerate(self.building_layout):
            if bt == BuildingType.HEADQUARTERS:
                return i
        counts = [len(s) for s in self.member_assignments]
        return counts.index(min(counts))

    def _reindex_after_removal(self, removed: int) -> None:
        """After removing roster[removed], drop it from assignments and shift
        every higher stored index down by one."""
        if self.member_assignments is None:
            return
        new_assign = []
        for slot in self.member_assignments:
            s = [(mi - 1 if mi > removed else mi) for mi in slot if mi != removed]
            new_assign.append(s)
        self.member_assignments = new_assign

    def move_to_backup(self, roster_idx: int) -> bool:
        """Bench an active-roster member (remove from buildings, add to backup)."""
        if not (0 <= roster_idx < len(self.roster)):
            return False
        if len(self.backup) >= config.BACKUP_FORCE_CAP:
            return False
        m = self.roster.pop(roster_idx)
        self._reindex_after_removal(roster_idx)
        self.backup.append(m)
        return True

    def move_to_roster(self, backup_idx: int) -> bool:
        """Activate a backup member into the roster and assign to a building."""
        if not (0 <= backup_idx < len(self.backup)):
            return False
        self.ensure_roster()
        self.ensure_member_assignments(self.roster)
        m = self.backup.pop(backup_idx)
        self.roster.append(m)
        new_idx = len(self.roster) - 1
        self.member_assignments[self._default_assign_slot()].append(new_idx)
        return True

    def kick_backup(self, backup_idx: int) -> bool:
        """Permanently remove a backup member from the game."""
        if not (0 <= backup_idx < len(self.backup)):
            return False
        self.backup.pop(backup_idx)
        return True

    def member_cap(self) -> int:
        """Roster cap from the persistent HQ level (base + 10 per HQ level)."""
        cap = config.BASE_MEMBER_CAP
        for bt, lvl in zip(self.building_layout, self.building_levels):
            if bt == BuildingType.HEADQUARTERS:
                cap = config.BASE_MEMBER_CAP + config.HQ_MEMBERS_PER_LEVEL * max(1, lvl)
                break
        return cap


def _valid_assignments(assignments, size: int = 40) -> bool:
    """Valid == 9 lists of ints covering exactly range(size) (each roster member
    assigned to exactly one building slot)."""
    if not isinstance(assignments, list) or len(assignments) != 9:
        return False
    flat = []
    for slot in assignments:
        if not isinstance(slot, list):
            return False
        flat.extend(slot)
    return len(flat) == size and sorted(flat) == list(range(size))


def empire_net_worth(empire: Empire) -> int:
    """Economy doc: net worth = 100 x sum of all member levels."""
    return 100 * sum(m.level for m in empire.members)


def war_reward(enemy: Empire) -> int:
    """Win reward = 30% of enemy empire net worth (economy doc)."""
    return int(0.30 * empire_net_worth(enemy))

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
from models import BuildingType, Empire, MemberClass

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
    # 9 lists of member indices (into a deterministic roster). None until set.
    member_assignments: Optional[List[List[int]]] = None
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
            member_assignments = data.get("member_assignments")
            if not _valid_assignments(member_assignments):
                member_assignments = None
            state = cls(
                money=int(data.get("money", config.STARTING_MONEY)),
                building_layout=layout,
                building_levels=[max(1, int(x)) for x in levels],
                conquered=set(data.get("conquered", [])),
                member_assignments=member_assignments,
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
        (for the given roster) if not set yet."""
        if not _valid_assignments(self.member_assignments):
            self.member_assignments = default_member_assignments(members)
        return self.member_assignments

    def apply_to_empire(self, empire: Empire) -> None:
        """Push the persistent money + building layout (+ levels + member
        assignments) onto a battle empire."""
        import buildings
        empire.money = self.money
        empire.apply_building_layout(list(self.building_layout))
        buildings.apply_building_levels(empire, list(self.building_levels))
        assignments = self.ensure_member_assignments(empire.members)
        empire.member_assignments = [list(s) for s in assignments]

    def member_cap(self) -> int:
        """Roster cap from the persistent HQ level (base + 10 per HQ level)."""
        cap = config.BASE_MEMBER_CAP
        for bt, lvl in zip(self.building_layout, self.building_levels):
            if bt == BuildingType.HEADQUARTERS:
                cap = config.BASE_MEMBER_CAP + config.HQ_MEMBERS_PER_LEVEL * max(1, lvl)
                break
        return cap


def _valid_assignments(assignments) -> bool:
    """A valid assignment is 9 lists of ints covering all 40 members exactly."""
    if not isinstance(assignments, list) or len(assignments) != 9:
        return False
    flat = []
    for slot in assignments:
        if not isinstance(slot, list):
            return False
        flat.extend(slot)
    return len(flat) == 40 and sorted(flat) == list(range(40))


def empire_net_worth(empire: Empire) -> int:
    """Economy doc: net worth = 100 x sum of all member levels."""
    return 100 * sum(m.level for m in empire.members)


def war_reward(enemy: Empire) -> int:
    """Win reward = 30% of enemy empire net worth (economy doc)."""
    return int(0.30 * empire_net_worth(enemy))

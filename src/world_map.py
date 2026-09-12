"""EVE - World map data + helpers.

Loads the generated datasets in data/world/*.json (produced by
tools/build_world_data.py) into a Country > State > County > City hierarchy.
Each city leaf carries real-derived metrics: population, gdp_thousands,
crime_rate, reward, difficulty, underworld_power, police_power.

Kept free of pygame/game imports so both screens and game_state can share it.

City ids are "Country/State/County/City" (4 parts). Names never contain '/'.
"""
import glob
import json
import os
from typing import List, Optional, Tuple

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "world")


def _load():
    """WORLD[country][state] = {county_name: county_obj} where county_obj has
    keys: fips, gdp_thousands, population, homicide_rate, difficulty,
    gdp_estimated, cities{city_name: metrics}."""
    world = {}
    for path in sorted(glob.glob(os.path.join(DATA_DIR, "*.json"))):
        with open(path) as f:
            d = json.load(f)
        world.setdefault(d["country"], {})[d["state"]] = d["counties"]
    return world


WORLD = _load()


# --- id helpers ------------------------------------------------------------
def city_id(country: str, state: str, county: str, city: str) -> str:
    return f"{country}/{state}/{county}/{city}"


def split_city_id(cid: str) -> Tuple[str, str, str, str]:
    country, state, county, city = cid.split("/")
    return country, state, county, city


# --- navigation ------------------------------------------------------------
def countries() -> List[str]:
    return sorted(WORLD.keys())


def states(country: str) -> List[str]:
    return sorted(WORLD.get(country, {}).keys())


def _county_power(county_obj) -> int:
    return sum(c.get("underworld_power", 0) for c in county_obj["cities"].values())


def counties(country: str, state: str) -> List[str]:
    """Counties ordered by total underworld power (weakest first = natural roadmap)."""
    st = WORLD.get(country, {}).get(state, {})
    return sorted(st.keys(), key=lambda n: _county_power(st[n]))


def cities(country: str, state: str, county: str) -> List[str]:
    """Cities ordered by underworld power (weakest first)."""
    cs = WORLD[country][state][county]["cities"]
    return sorted(cs.keys(), key=lambda n: cs[n].get("underworld_power", 0))


# --- lookups ---------------------------------------------------------------
def get_county(country: str, state: str, county: str) -> Optional[dict]:
    return WORLD.get(country, {}).get(state, {}).get(county)


def get_city(cid: str) -> Optional[dict]:
    """Return the metrics dict for a city id, or None."""
    try:
        country, state, county, city = split_city_id(cid)
    except ValueError:
        return None
    county_obj = get_county(country, state, county)
    if not county_obj:
        return None
    return county_obj["cities"].get(city)


# --- id collections (for scope gating) -------------------------------------
def county_city_ids(country: str, state: str, county: str) -> List[str]:
    obj = get_county(country, state, county)
    if not obj:
        return []
    return [city_id(country, state, county, c) for c in obj["cities"]]


def state_city_ids(country: str, state: str) -> List[str]:
    ids = []
    for county in WORLD.get(country, {}).get(state, {}):
        ids.extend(county_city_ids(country, state, county))
    return ids


def country_city_ids(country: str) -> List[str]:
    ids = []
    for state in WORLD.get(country, {}):
        ids.extend(state_city_ids(country, state))
    return ids


# --- control rollup (depends on the player's conquered set) ----------------
def control(ids, conquered) -> Tuple[int, int, float]:
    """(#owned, #total, fraction) of the given city ids that are conquered."""
    total = len(ids)
    owned = sum(1 for i in ids if i in conquered)
    return owned, total, (owned / total if total else 0.0)


def county_control(country, state, county, conquered):
    return control(county_city_ids(country, state, county), conquered)


def state_control(country, state, conquered):
    return control(state_city_ids(country, state), conquered)


def country_control(country, conquered):
    return control(country_city_ids(country), conquered)


# --- Visual US map data + adjacency-based unlocking ------------------------
import config  # noqa: E402  (config has no pygame/game deps)

_MAP_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "us_states_map.json")


def _load_us_map():
    try:
        with open(_MAP_PATH) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"states": {}, "adjacency": {}, "aspect": 2.4}


US_MAP = _load_us_map()

# Full state name <-> two-letter abbreviation (drives map <-> WORLD linking).
STATE_ABBREV = {
    "Alabama": "AL", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
    "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "District of Columbia": "DC", "Florida": "FL", "Georgia": "GA",
    "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA",
    "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME",
    "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN",
    "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE",
    "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ",
    "New Mexico": "NM", "New York": "NY", "North Carolina": "NC",
    "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR",
    "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
    "Vermont": "VT", "Virginia": "VA", "Washington": "WA",
    "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
}
ABBREV_STATE = {v: k for k, v in STATE_ABBREV.items()}


def state_abbrev(state_name: str) -> Optional[str]:
    return STATE_ABBREV.get(state_name)


def state_adjacency(abbrev: str) -> List[str]:
    """Neighbouring state abbreviations for a state abbreviation."""
    return US_MAP.get("adjacency", {}).get(abbrev, [])


def state_unlocked(country: str, state_name: str, conquered,
                   home_state: Optional[str] = None,
                   threshold: Optional[float] = None) -> bool:
    """Is this state challengeable on the visual US map?

    True if:
      * it is the player's home state (always open), OR
      * any bordering state's control fraction is >= threshold
        (config.STATE_UNLOCK_THRESHOLD by default).
    """
    if threshold is None:
        threshold = config.STATE_UNLOCK_THRESHOLD
    if home_state is not None and state_name == home_state:
        return True
    abbrev = state_abbrev(state_name)
    if abbrev is None:
        return False
    for nb in state_adjacency(abbrev):
        nb_name = ABBREV_STATE.get(nb)
        if nb_name is None:
            continue
        _, _, frac = state_control(country, nb_name, conquered)
        if frac >= threshold:
            return True
    return False


def state_color_bucket(control_frac: float, unlocked: bool,
                       threshold: Optional[float] = None) -> str:
    """Map a state's control fraction to a color bucket for the map.

    Absolute control-percentage bands (independent of the unlock threshold —
    that gate only decides whether a state is challengeable, not its color):

        locked  -> not yet challengeable (gray)
        red     ->   0% .. 1%
        orange  ->   1% .. 10%
        yellow  ->  10% .. 30%
        green   ->  30% .. 70%
        blue    ->  70% and up

    Bands are lower-inclusive: exactly 1% is orange, 10% yellow, 30% green,
    70% blue. `threshold` is accepted for signature compatibility but unused.
    """
    if not unlocked:
        return "locked"
    pct = control_frac * 100.0
    if pct >= 70.0:
        return "blue"
    if pct >= 30.0:
        return "green"
    if pct >= 10.0:
        return "yellow"
    if pct >= 1.0:
        return "orange"
    return "red"

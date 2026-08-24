#!/usr/bin/env python3
"""EVE - Generate placeholder world data for every US state.

Until real ETL data exists for all states, this seeds each state (except those
that already have a real file, e.g. Virginia) with a single dummy county + city
so the state is enterable and the visual US map / adjacency-unlock flow can be
tested end to end. Powers are small and beatable.

Idempotent: never overwrites an existing data/world/<state>.json.

Usage: python3 tools/gen_dummy_states.py
"""
import json
import os

HERE = os.path.dirname(__file__)
MAP = os.path.join(HERE, "..", "data", "us_states_map.json")
WORLD_DIR = os.path.join(HERE, "..", "data", "world")

ABBREV_TO_NAME = {
    "AL": "Alabama", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia",
    "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa",
    "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine",
    "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska",
    "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
    "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon",
    "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming",
}


def dummy_state(name):
    city = {
        "population": 50000,
        "gdp_thousands": 2000000,
        "crime_rate": 20.0,
        "reward": 1500,
        "difficulty": 0.2,
        "underworld_power": 200,   # small -> beatable for testing
        "police_power": 8000,
    }
    county = {
        "fips": "00000",
        "gdp_thousands": 2000000,
        "gdp_estimated": True,
        "population": 50000,
        "homicide_rate": 20.0,
        "difficulty": 0.2,
        "cities": {f"{name} City": city},
    }
    return {
        "country": "United States",
        "state": name,
        "state_fips": "00",
        "counties": {f"{name} County": county},
    }


def main():
    with open(MAP) as f:
        states = json.load(f)["states"]
    os.makedirs(WORLD_DIR, exist_ok=True)
    created, skipped = 0, 0
    for abbrev in states:
        name = ABBREV_TO_NAME[abbrev]
        fname = os.path.join(WORLD_DIR, f"{name.lower().replace(' ', '_')}.json")
        if os.path.exists(fname):
            skipped += 1
            continue
        with open(fname, "w") as f:
            json.dump(dummy_state(name), f, indent=2)
        created += 1
    print(f"Created {created} dummy state files, skipped {skipped} existing.")


if __name__ == "__main__":
    main()

"""EVE - AI targeting personalities (profiles).

A "profile" changes only HOW the AI scores a candidate building; the wave/phase
machinery in ai.py (reachability, class batching, health packs) is shared by all
profiles. Each enemy is assigned a profile deterministically from a seed made of
the city id + the side ("gang" or "police"), so:

  * a city's gang and its police boss can behave differently, and
  * the same fight always plays out with the same personality on replay.

Scoring contract
----------------
`AIProfile.score(building, defenders, rng)` returns a number; the AI picks the
highest-scoring REACHABLE building each wave (ties broken randomly upstream).
`building` is a models.Building; `defenders` is the list of that building's live
Member defenders; `rng` is the AI's seeded random.Random (only random_path uses
it). All profiles share `base_value` so the "destroyer" profiles degrade to the
value model once their target type is gone.
"""

import hashlib

import config
from models import MemberClass


def _building_type_value(building) -> int:
    return config.AI_TARGET_SCORE_BUILDING.get(
        building.building_type.value, config.AI_TARGET_SCORE_BUILDING_DEFAULT)


def _defender_value(defenders) -> int:
    """Summed value of live defenders (enforcers weighted differently)."""
    total = 0
    for m in defenders:
        total += (config.AI_TARGET_SCORE_ENFORCER
                  if m.member_class == MemberClass.ENFORCER
                  else config.AI_TARGET_SCORE_DEFENDER)
    return total


def base_value(building, defenders) -> int:
    """The baseline value model: building-type value + live-defender value.
    Shared by the `value` profile and used as the fallback term elsewhere."""
    return _building_type_value(building) + _defender_value(defenders)


class AIProfile:
    """A named targeting personality. `score` ranks candidate buildings."""

    def __init__(self, name: str, display_name: str, score_fn):
        self.name = name
        self.display_name = display_name
        self._score_fn = score_fn

    def score(self, building, defenders, rng) -> float:
        return self._score_fn(building, defenders, rng)

    def __repr__(self):
        return f"AIProfile({self.name!r})"


# --- scoring functions ----------------------------------------------------

def _score_value(building, defenders, rng):
    return base_value(building, defenders)


def _score_random(building, defenders, rng):
    # Uniform over reachable candidates: every building is effectively a tie.
    return rng.random()


def _path_scorer(sign):
    """Score by how contested a building is: weighted live-defender count plus a
    small building-type-value tiebreak. sign=+1 => hard path (most defended),
    sign=-1 => easy path (least defended)."""
    def _fn(building, defenders, rng):
        contest = _defender_value(defenders) + 0.001 * _building_type_value(building)
        return sign * contest
    return _fn


def _destroyer_scorer(target_type, bonus):
    """Beeline one building type: base value plus a big bonus when the building
    matches. Falls back to the value model once that type is gone/unreachable."""
    def _fn(building, defenders, rng):
        score = base_value(building, defenders)
        if building.building_type.value == target_type:
            score += bonus
        return score
    return _fn


def _build_profiles():
    p = config.AI_PROFILE_PARAMS
    return {
        "value": AIProfile("value", "Balanced (value)", _score_value),
        "random_path": AIProfile("random_path", "Erratic (random)", _score_random),
        "easy_path": AIProfile("easy_path", "Opportunist (easy path)",
                               _path_scorer(p["easy_path"]["sign"])),
        "hard_path": AIProfile("hard_path", "Juggernaut (hard path)",
                               _path_scorer(p["hard_path"]["sign"])),
        "hospital_destroyer": AIProfile(
            "hospital_destroyer", "Hospital Destroyer",
            _destroyer_scorer(p["hospital_destroyer"]["target_type"],
                              p["hospital_destroyer"]["bonus"])),
        "armory_destroyer": AIProfile(
            "armory_destroyer", "Armory Destroyer",
            _destroyer_scorer(p["armory_destroyer"]["target_type"],
                              p["armory_destroyer"]["bonus"])),
    }


_PROFILES = _build_profiles()


def get_profile(name: str) -> AIProfile:
    """Look up a profile by name; unknown/None names fall back to the default."""
    return _PROFILES.get(name) or _PROFILES[config.AI_PROFILE_DEFAULT]


def display_name(name: str) -> str:
    """Human-readable strategy label for a profile name (for the city popup)."""
    return get_profile(name).display_name


def _seed_index(seed_str: str, modulo: int) -> int:
    """Stable, cross-run hash of a string into [0, modulo). Uses md5 rather than
    the builtin hash() because hash() is salted per-process (PYTHONHASHSEED)."""
    digest = hashlib.md5(seed_str.encode("utf-8")).hexdigest()
    return int(digest, 16) % modulo


def profile_name_for(seed_key: str, police: bool = False) -> str:
    """Deterministically pick a profile NAME for an enemy.

    seed_key is a stable identifier for the opponent (we use the full city id).
    The side is folded in so a city's gang and police get independent — but each
    individually stable — strategies. The police boss is always the fixed police
    profile (the hardest personality); gangs draw from the weighted gang pool.
    """
    if police:
        return config.AI_PROFILE_POLICE
    pool = config.AI_PROFILE_GANG_POOL
    idx = _seed_index(f"{seed_key}|gang", len(pool))
    return pool[idx]

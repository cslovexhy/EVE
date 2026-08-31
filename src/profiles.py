"""EVE - Multiple save profiles.

Each profile is one JSON file under data/../profiles/<slug>.json, in the exact
same format GameState reads/writes. This module owns the directory, name <->
path mapping, listing, creation, deletion, and one-time migration of the legacy
single-file save (player_profile.json) into profiles/default.json.

A profile's on-disk filename is a filesystem-safe *slug* of its display name;
the display name itself is stored inside the JSON as "profile_name" so it can
contain spaces/case the slug can't. Listing prefers that stored name.
"""
import json
import os
import re
from typing import List, Optional

import game_state
from game_state import GameState

# profiles/ lives next to the legacy save (project root).
PROFILES_DIR = os.path.join(os.path.dirname(__file__), "..", "profiles")
LEGACY_PATH = game_state.PROFILE_PATH


def _slugify(name: str) -> str:
    """Filesystem-safe slug: keep alnum, dash, underscore, space->underscore,
    lowercased. Collapses runs and trims. Empty -> 'profile'."""
    s = name.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)       # drop punctuation except _ - and space
    s = re.sub(r"[\s]+", "_", s)          # spaces -> underscore
    s = re.sub(r"_+", "_", s).strip("_")  # collapse/trim underscores
    return s or "profile"


def path_for_slug(slug: str) -> str:
    return os.path.join(PROFILES_DIR, slug + ".json")


def ensure_dir() -> None:
    os.makedirs(PROFILES_DIR, exist_ok=True)


def migrate_legacy() -> None:
    """If a legacy player_profile.json exists and no profiles/ has been created
    yet, move it in as 'default' so existing progress carries over. Idempotent:
    does nothing once profiles/ has any file, or if there's no legacy save."""
    ensure_dir()
    if list_profiles():          # already have profiles -> nothing to do
        return
    if not os.path.exists(LEGACY_PATH):
        return
    try:
        with open(LEGACY_PATH, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return
    data.setdefault("profile_name", "default")
    dest = path_for_slug("default")
    with open(dest, "w") as f:
        json.dump(data, f, indent=2)


def _display_name(slug: str) -> str:
    """Stored display name for a slug, falling back to the slug itself."""
    try:
        with open(path_for_slug(slug), "r") as f:
            data = json.load(f)
        name = data.get("profile_name")
        if isinstance(name, str) and name.strip():
            return name
    except (json.JSONDecodeError, OSError):
        pass
    return slug


def list_profiles() -> List[str]:
    """Slugs of all existing profiles, sorted by display name (case-insensitive)."""
    if not os.path.isdir(PROFILES_DIR):
        return []
    slugs = [fn[:-5] for fn in os.listdir(PROFILES_DIR) if fn.endswith(".json")]
    return sorted(slugs, key=lambda s: _display_name(s).lower())


def profile_exists(name: str) -> bool:
    return os.path.exists(path_for_slug(_slugify(name)))


def summarize(slug: str) -> dict:
    """A light summary for the selection screen without a full GameState load."""
    info = {"slug": slug, "name": _display_name(slug),
            "money": 0, "conquered": 0, "home": None}
    try:
        with open(path_for_slug(slug), "r") as f:
            data = json.load(f)
        info["money"] = int(data.get("money", 0))
        info["conquered"] = len(data.get("conquered", []))
        info["home"] = data.get("home_city")
    except (json.JSONDecodeError, OSError, ValueError, TypeError):
        pass
    return info


def create_profile(name: str) -> Optional[GameState]:
    """Create a fresh profile with the given display name. Returns a new
    GameState bound to its file (already saved), or None if the name collides
    or is blank."""
    display = name.strip()
    if not display:
        return None
    slug = _slugify(display)
    ensure_dir()
    if os.path.exists(path_for_slug(slug)):
        return None
    state = GameState(path=path_for_slug(slug))
    state.profile_name = display
    state.save()
    return state


def load_profile(slug: str) -> GameState:
    """Load an existing profile by slug (bound to its file)."""
    return GameState.load(path_for_slug(slug))


def delete_profile(slug: str) -> bool:
    """Delete a profile file. Returns True if a file was removed."""
    p = path_for_slug(slug)
    if os.path.exists(p):
        os.remove(p)
        return True
    return False

"""EVE - Sound effects manager.

A tiny wrapper over pygame.mixer that is safe to use everywhere, including
headless environments (unit tests, CI): if the mixer can't be initialized or a
file is missing, every call becomes a no-op instead of raising. This keeps the
engine free of audio-availability checks and keeps tests silent and green.

Usage:
    import sound
    sound.init(muted=False)          # once, at game start (battle/session)
    sound.play("fire_sniper")        # fire-and-forget SFX by logical name
    sound.play_for_class(member_class)   # per-class fire sound
    sound.set_muted(True)            # toggle mute at runtime

Logical names map to files in assets/sounds/<name>.ogg.
"""
import os
from typing import Dict, Optional

# MemberClass is an enum in models; import lazily inside the mapping helper to
# avoid a hard import cycle (models does not import sound, but keep it clean).

_SOUNDS_DIR = os.path.join(os.path.dirname(__file__), "..", "assets", "sounds")

# Logical event name -> filename in assets/sounds/.
_FILES: Dict[str, str] = {
    "fire_assassin": "fire_assassin.ogg",
    "fire_sniper": "fire_sniper.ogg",
    "fire_enforcer": "fire_enforcer.ogg",
    "fire_demolitionist": "fire_demolitionist.ogg",
    "member_death": "member_death.ogg",
    "building_hit_explosion": "building_hit_explosion.ogg",
    "building_destroyed": "building_destroyed.ogg",
    "nuke": "nuke.ogg",
}

# Per-event volume trim (0..1) so loud/long clips sit under the fire SFX.
_VOLUMES: Dict[str, float] = {
    "fire_assassin": 0.6,
    "fire_sniper": 0.7,
    "fire_enforcer": 0.7,
    "fire_demolitionist": 0.8,
    "member_death": 0.7,
    "building_hit_explosion": 0.9,
    "building_destroyed": 1.0,
    "nuke": 1.0,
}

_available = False          # True once the mixer initialized successfully
_muted = False
_master_volume = 1.0
_cache: Dict[str, object] = {}   # name -> pygame.mixer.Sound
_pygame = None


def init(muted: bool = False, master_volume: float = 1.0) -> bool:
    """Initialize the audio mixer and preload the sound bank. Safe to call more
    than once. Returns True if audio is available, False if running silent
    (headless / no audio device / pygame missing)."""
    global _available, _muted, _master_volume, _pygame
    _muted = muted
    _master_volume = max(0.0, min(1.0, master_volume))
    try:
        import pygame  # noqa: WPS433 (local import keeps module importable headless)
        _pygame = pygame
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        # Plenty of channels so overlapping shots don't cut each other off.
        pygame.mixer.set_num_channels(32)
        _available = True
    except Exception:
        # No audio device, dummy driver, or mixer failure -> run silent.
        _available = False
        return False

    _preload()
    return True


def _preload() -> None:
    if not _available:
        return
    for name, fname in _FILES.items():
        path = os.path.join(_SOUNDS_DIR, fname)
        try:
            snd = _pygame.mixer.Sound(path)
            snd.set_volume(_VOLUMES.get(name, 1.0))
            _cache[name] = snd
        except Exception:
            # Missing/corrupt file -> that one sound is simply silent.
            continue


def set_muted(muted: bool) -> None:
    global _muted
    _muted = muted


def is_muted() -> bool:
    return _muted


def toggle_muted() -> bool:
    global _muted
    _muted = not _muted
    return _muted


def set_master_volume(vol: float) -> None:
    global _master_volume
    _master_volume = max(0.0, min(1.0, vol))
    for name, snd in _cache.items():
        try:
            snd.set_volume(_VOLUMES.get(name, 1.0) * _master_volume)
        except Exception:
            pass


def play(name: str) -> None:
    """Play a logical sound by name. No-op when muted, unavailable, or unknown."""
    if not _available or _muted:
        return
    snd = _cache.get(name)
    if snd is None:
        return
    try:
        snd.set_volume(_VOLUMES.get(name, 1.0) * _master_volume)
        snd.play()
    except Exception:
        pass


# --- per-class fire sound -------------------------------------------------
_CLASS_FIRE = {
    "enforcer": "fire_enforcer",
    "sniper": "fire_sniper",
    "assassin": "fire_assassin",
    "demolitionist": "fire_demolitionist",
}


def play_for_class(member_class) -> None:
    """Play the fire sound for a MemberClass (or its .value string)."""
    key = getattr(member_class, "value", member_class)
    name = _CLASS_FIRE.get(key)
    if name:
        play(name)

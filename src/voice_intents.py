"""Voice intent parser for EVE — game-agnostic, no pygame / mic dependency.

Turns a recognized speech transcript into a structured Intent. This is the
text->intent half of voice control; `voice.py` owns the mic/STT half and maps
Intents onto the game's existing keyboard/mouse actions (1:1, never superseding
them). Kept dependency-free so it is unit-testable from plain strings.

Command grammar (fully offline, closed vocabulary):

  Battle — numbered (target a building by its on-screen number, 1-based):
    "{class} {n}"      select that class AND attack enemy building n
                       classes: enforcer | assassin | sniper | demo
    "heal {n}"         heal your building n
    "nuke {n}"         arm + launch the nuke at enemy building n

  Battle — plain (1:1 with a single key):
    "mode"             cycle attack mode  (T)
    "auto" / "manual"  toggle AI-assist   (Tab)
    "speed up" / "speed down"             (+ / -)
    "forfeit"          leave the battle   (Q)
    "sound"            toggle mute         (M)

  Menu / map / layout (1:1 with a single key):
    "map" "layout" "quit" "back" / "menu" "next tab"
    "zoom in" / "zoom out"  "pan left/right/up/down"  "reset"
    "next page" / "previous page"  "yes" / "no"

Building numbers are spoken 1-based (matching the number drawn on each building)
and returned 0-based to match the engine's building indices.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# --- number words -> int (Vosk emits spoken digits as words) ----------------
_NUM_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}


def word_to_int(token: str) -> Optional[int]:
    token = token.strip().lower()
    if token.isdigit():
        return int(token)
    return _NUM_WORDS.get(token)


# canonical class words + spoken aliases. "demolitionist" is NOT in the small
# Vosk model's vocabulary, so "demo" is the reliable spoken form.
CLASS_WORDS = ["enforcer", "assassin", "sniper", "demolitionist"]
CLASS_ALIASES = {"demo": "demolitionist"}
NUMBER_WORDS = list(_NUM_WORDS.keys())

# The closed vocabulary handed to Vosk as a restricted grammar (accuracy win).
VOCAB = sorted(set(
    ["enforcer", "assassin", "sniper", "demo"]   # class words the model knows
    + NUMBER_WORDS
    + [
        "heal", "nuke", "mode", "auto", "manual", "speed", "up", "down",
        "forfeit", "sound",
        "map", "layout", "quit", "back", "menu", "tab", "next", "previous",
        "page", "zoom", "in", "out", "pan", "left", "right", "reset",
        "yes", "no",
    ]
))


@dataclass
class Intent:
    """A parsed command. `kind` is a stable action id; `payload` carries args."""
    kind: str
    payload: dict = field(default_factory=dict)
    raw: str = ""

    def __repr__(self):
        p = f" {self.payload}" if self.payload else ""
        return f"<Intent {self.kind}{p}>"


class IntentParser:
    """Turns a transcript into an Intent. No wake word (always accept commands).

    A wake word can be re-enabled by passing wake_word="...": then a command
    must share the utterance with the wake word, or arrive within `window`
    seconds of hearing it alone. Default is off per product decision.
    """

    def __init__(self, wake_word: str = "", window: float = 4.0):
        self.wake_word = wake_word.lower().strip()
        self.window = window
        self._armed_until = float("-inf")

    def feed(self, transcript: str, now: float = 0.0) -> Optional[Intent]:
        text = _normalize(transcript)
        if not text:
            return None

        if self.wake_word:
            armed = now <= self._armed_until
            if text.split()[0] == self.wake_word:
                rest = text[len(self.wake_word):].strip()
                self._armed_until = now + self.window
                if not rest:
                    return Intent("wake", raw=transcript)
                self._armed_until = float("-inf")
                return self._parse_command(rest, transcript)
            if not armed:
                return None
            self._armed_until = float("-inf")
            return self._parse_command(text, transcript)

        return self._parse_command(text, transcript)

    def _parse_command(self, text: str, raw: str) -> Optional[Intent]:
        t = text.split()

        def I(kind, **payload):
            return Intent(kind, payload, raw=raw)

        # --- numbered battle commands -----------------------------------
        # "{class} {n}" -> select class + attack enemy building n
        cls = _resolve_class(t[0]) if t else None
        if cls:
            idx = _trailing_building_index(t)
            if idx is not None:
                return I("attack", cls=cls, building=idx)
            return I("select_class", cls=cls)   # class word alone: just select

        # "heal {n}"
        if t[0] == "heal":
            idx = _trailing_building_index(t)
            if idx is not None:
                return I("heal", building=idx)
            return I("heal")                    # bare "heal": toggle heal mode

        # "nuke {n}"
        if t[0] == "nuke":
            idx = _trailing_building_index(t)
            if idx is not None:
                return I("nuke", building=idx)
            return I("nuke")                    # bare "nuke": just arm

        # --- plain battle keys ------------------------------------------
        if text == "mode":
            return I("mode")
        if text == "auto":
            return I("ai_assist", on=True)
        if text == "manual":
            return I("ai_assist", on=False)
        if text == "speed up":
            return I("speed", direction="up")
        if text == "speed down":
            return I("speed", direction="down")
        if text == "forfeit":
            return I("forfeit")
        if text == "sound":
            return I("sound")

        # --- menu / map / layout ----------------------------------------
        if text == "map":
            return I("goto", screen="map")
        if text == "layout":
            return I("goto", screen="layout")
        if text == "quit":
            return I("quit")
        if text in ("back", "menu"):
            return I("back")
        if text in ("next tab", "tab"):
            return I("next_tab")
        if text == "zoom in":
            return I("zoom", direction="in")
        if text == "zoom out":
            return I("zoom", direction="out")
        if t[0] == "pan" and len(t) > 1 and t[1] in ("left", "right", "up", "down"):
            return I("pan", direction=t[1])
        if text == "reset":
            return I("reset_view")
        if text == "next page":
            return I("page", direction="next")
        if text == "previous page":
            return I("page", direction="previous")
        if text == "yes":
            return I("confirm", value=True)
        if text == "no":
            return I("confirm", value=False)

        return I("unknown", text=text)


# --- helpers ----------------------------------------------------------------
def _resolve_class(word: str) -> Optional[str]:
    if word in CLASS_WORDS:
        return word
    return CLASS_ALIASES.get(word)


def _normalize(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _trailing_building_index(tokens) -> Optional[int]:
    """Find a spoken building number in the tokens and return it 0-based.
    Spoken numbers are 1-based (match the on-screen label); engine indices are
    0-based. Returns None if no number is present."""
    for tok in reversed(tokens):
        n = word_to_int(tok)
        if n is not None:
            return n - 1 if n >= 1 else 0
    return None

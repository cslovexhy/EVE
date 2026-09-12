"""EVE - Voice control (offline, always-listening) as a PARALLEL input path.

Design goals (see README worklog):
  * Fully offline: Vosk small model + a closed-vocabulary grammar. No network.
  * Always-on while the game runs; stopped when it ends (main.py lifecycle).
  * 1:1 with existing keyboard/mouse — voice never supersedes them. It only
    *adds* input by posting the same synthetic pygame events the game already
    handles, or by handing numbered battle commands to the battle session's own
    order logic. Real key/mouse events are untouched.
  * Safe no-op fallback (like sound.py): if vosk/sounddevice/model/mic are
    unavailable (headless, CI, denied mic permission), every call is a no-op and
    the game behaves exactly as before.

Architecture:
    mic thread (Vosk) --transcripts--> IntentParser --Intents--> Queue
    main loop each frame: voice.pump()  drains the queue and either
        - posts a synthetic pygame KEYDOWN for 1:1 keystroke commands, or
        - buffers a numbered battle command (attack/heal/nuke {n}) for the
          active BattleSession to consume via poll_battle_intents().

The two integration touch-points in existing code are one-liners:
    screens._Screen.run():        voice.pump() before pygame.event.get()
    battle_session._handle_events: voice.pump() + poll_battle_intents()
"""
from __future__ import annotations

import json
import os
import queue
import threading
from typing import List, Optional

from voice_intents import IntentParser, VOCAB, Intent

_MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "models",
                          "vosk-model-small-en-us-0.15")

# --- module state (mirrors sound.py's simple, safe-by-default style) --------
_controller: "Optional[VoiceController]" = None
_context = "menu"          # menu | map | layout | battle  (set by main.py)


# Intents that map 1:1 to a single keystroke, resolved per context to a pygame
# key. Filled lazily in pump() so pygame is only imported when actually used.
def _key_for_intent(intent: Intent, pygame):
    """Return a pygame key constant for a keystroke-style intent, or None if the
    intent is not a simple keystroke (numbered battle commands return None and
    are routed to the battle session instead)."""
    k = intent.kind
    p = intent.payload

    if k == "select_class":
        return {
            "enforcer": pygame.K_e, "assassin": pygame.K_a,
            "sniper": pygame.K_s, "demolitionist": pygame.K_d,
        }.get(p.get("cls"))
    if k == "heal" and "building" not in p:
        return pygame.K_h
    if k == "nuke" and "building" not in p:
        return pygame.K_n
    if k == "mode":
        return pygame.K_t
    if k == "ai_assist":
        return pygame.K_TAB
    if k == "next_tab":
        return pygame.K_TAB
    if k == "speed":
        return pygame.K_EQUALS if p.get("direction") == "up" else pygame.K_MINUS
    if k == "forfeit":
        return pygame.K_q
    if k == "sound":
        return pygame.K_m
    if k == "quit":
        return pygame.K_q
    if k == "back":
        return pygame.K_ESCAPE
    if k == "goto":
        # main menu buttons are click-only; but map/layout also respond to no
        # key. We post a KEYDOWN the MainMenu ignores -> instead handled via a
        # dedicated mapping below. Return None so pump() uses the click path.
        return None
    if k == "zoom":
        return pygame.K_EQUALS if p.get("direction") == "in" else pygame.K_MINUS
    if k == "pan":
        return {"left": pygame.K_LEFT, "right": pygame.K_RIGHT,
                "up": pygame.K_UP, "down": pygame.K_DOWN}.get(p.get("direction"))
    if k == "reset_view":
        return pygame.K_r
    if k == "page":
        return pygame.K_RIGHT if p.get("direction") == "next" else pygame.K_LEFT
    if k == "confirm":
        return pygame.K_y if p.get("value") else pygame.K_n
    return None


class VoiceController:
    """Owns the mic stream + Vosk recognizer on a daemon thread and produces
    Intents onto a thread-safe queue. Safe no-op if anything is unavailable."""

    def __init__(self, model_dir: str = _MODEL_DIR, wake_word: str = ""):
        self.model_dir = model_dir
        self.parser = IntentParser(wake_word=wake_word)
        self.available = False
        self._q: "queue.Queue[Intent]" = queue.Queue()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._sd = None
        self._stream = None

    # --- lifecycle ------------------------------------------------------
    def start(self) -> bool:
        """Try to start listening. Returns True if the mic thread started, False
        if running silent (deps/model/mic unavailable). Never raises."""
        try:
            import sounddevice as sd
            from vosk import Model, KaldiRecognizer, SetLogLevel
        except Exception:
            return False
        if not os.path.isdir(self.model_dir):
            return False
        try:
            SetLogLevel(-1)
            self._model = Model(self.model_dir)
            info = sd.query_devices(kind="input")
            self._samplerate = int(info["default_samplerate"])
            grammar = json.dumps(list(VOCAB) + ["[unk]"])
            self._rec = KaldiRecognizer(self._model, self._samplerate, grammar)
            self._sd = sd
        except Exception:
            return False

        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="voice", daemon=True)
        self._thread.start()
        self.available = True
        return True

    def stop(self) -> None:
        """Stop listening and tear down the stream. Safe to call repeatedly."""
        self._stop.set()
        try:
            if self._stream is not None:
                self._stream.stop()
                self._stream.close()
        except Exception:
            pass
        self._stream = None
        self.available = False

    # --- mic thread -----------------------------------------------------
    def _run(self) -> None:
        import time
        audio_q: "queue.Queue[bytes]" = queue.Queue()

        def cb(indata, frames, time_info, status):  # noqa: ANN001
            audio_q.put(bytes(indata))

        try:
            self._stream = self._sd.RawInputStream(
                samplerate=self._samplerate, blocksize=8000, dtype="int16",
                channels=1, callback=cb)
            self._stream.start()
        except Exception:
            # e.g. PortAudio -9986 (mic permission denied): run silent.
            self.available = False
            return

        while not self._stop.is_set():
            try:
                data = audio_q.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                if self._rec.AcceptWaveform(data):
                    text = json.loads(self._rec.Result()).get("text", "").strip()
                    if not text:
                        continue
                    intent = self.parser.feed(text, now=time.monotonic())
                    if intent is not None and intent.kind not in ("unknown", "wake"):
                        self._q.put(intent)
            except Exception:
                continue

    # --- consumption ----------------------------------------------------
    def drain(self) -> List[Intent]:
        out = []
        while True:
            try:
                out.append(self._q.get_nowait())
            except queue.Empty:
                break
        return out


# --- module-level API used by the game --------------------------------------
def start(wake_word: str = "") -> bool:
    """Start the always-listening controller. No-op-safe; returns availability."""
    global _controller
    if _controller is None:
        _controller = VoiceController(wake_word=wake_word)
    return _controller.start()


def stop() -> None:
    if _controller is not None:
        _controller.stop()


def is_available() -> bool:
    return _controller is not None and _controller.available


def set_context(name: str) -> None:
    """Tell voice which screen is active so battle-only numbered commands are
    ignored elsewhere. One of: menu | map | layout | battle."""
    global _context
    _context = name


# Numbered battle commands (attack/heal/nuke {n}) that the BattleSession polls.
_battle_buffer: "List[Intent]" = []


def pump() -> None:
    """Drain recognized intents. Post synthetic pygame events for 1:1 keystroke
    commands; buffer numbered battle commands for the battle session. Called
    once per frame from the active event loop. No-op if voice is unavailable."""
    if _controller is None or not _controller.available:
        return
    try:
        import pygame
    except Exception:
        return

    for intent in _controller.drain():
        # Numbered battle commands need the session's order logic -> buffer them
        # (only while in battle; ignore stray numbers elsewhere).
        if intent.kind in ("attack", "heal", "nuke") and "building" in intent.payload:
            if _context == "battle":
                _battle_buffer.append(intent)
            continue

        # 'goto' (map/layout) has no keyboard equivalent on the main menu (the
        # buttons are click-only), so post a synthetic click on the button.
        if intent.kind == "goto":
            _post_menu_click(pygame, intent.payload.get("screen"))
            continue

        key = _key_for_intent(intent, pygame)
        if key is not None:
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key,
                                                 mod=0, unicode="", scancode=0))


def poll_battle_intents() -> List[Intent]:
    """Return and clear buffered numbered battle commands (attack/heal/nuke n).
    Consumed by BattleSession, which resolves them through its own order logic
    (same validity/visibility checks as a mouse click)."""
    global _battle_buffer
    out = _battle_buffer
    _battle_buffer = []
    return out


def _post_menu_click(pygame, screen_name: str) -> None:
    """Post a synthetic left-click at the MainMenu button for map/layout. The
    button rects are recomputed here from config to avoid importing screens
    (which would create an import cycle)."""
    import config
    cx = config.SCREEN_WIDTH // 2
    w, h, gap = 320, 64, 24
    y0 = config.SCREEN_HEIGHT // 2 - 60
    order = {"map": 0, "layout": 1, "quit": 2}
    if screen_name not in order:
        return
    i = order[screen_name]
    rect_center = (cx, y0 + i * (h + gap) + h // 2)
    pygame.event.post(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, button=1, pos=rect_center))

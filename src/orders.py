"""EVE - Order System (click-driven).

New control scheme:
  * A / S / D / F         -> attack mode = 1/4 | 1/2 | Full | Auto
  * Left-click enemy bldg  -> attack with the ESA group (Enforcer+Sniper+Assassin)
  * Right-click enemy bldg -> attack with the Demolitionist group
  * Left-click OWN bldg    -> heal the strongest dead member in that building

There is no class-selection step and no separate heal mode anymore: the mouse
button + which side you clicked fully determine the action. Each class in an
attack group is ordered independently so per-class visibility (e.g. the
assassin backdoor) still applies.
"""

import pygame
from models import MemberClass, OrderAction, Order
import config


# Which MemberClass each attack group fires, derived from the config string
# lists (config must not import models, so the mapping lives here).
_CLASS_BY_VALUE = {c.value: c for c in MemberClass}
ESA_CLASSES = [_CLASS_BY_VALUE[v] for v in config.ATTACK_GROUP_ESA]
DEMO_CLASSES = [_CLASS_BY_VALUE[v] for v in config.ATTACK_GROUP_DEMO]


class AttackModeButton:
    """The attack-mode selector: 1/4 -> 1/2 -> Full -> Auto.

    Driven by the A/S/D/F keys (set in battle_session), and also clickable:
    clicking the bar cycles to the next mode. `set_mode_index` lets the keys
    jump straight to a specific mode.
    """

    MODES = config.ATTACK_MODES  # ["quarter", "half", "full", "auto"]

    def __init__(self):
        self.rect = pygame.Rect(0, 0, 320, 50)
        self.hovered = False
        self.mode_index = 1  # default: 1/2 (half)

    @property
    def mode(self) -> str:
        return self.MODES[self.mode_index]

    @property
    def label(self) -> str:
        return config.ATTACK_MODE_LABELS.get(self.mode, self.mode)

    def set_mode_index(self, index: int):
        if 0 <= index < len(self.MODES):
            self.mode_index = index

    def toggle(self):
        self.mode_index = (self.mode_index + 1) % len(self.MODES)

    def update_rect(self):
        """Centered mode selector bar in the order panel."""
        w, h = 360, 50
        self.rect = pygame.Rect(
            (config.SCREEN_WIDTH - w) // 2,
            config.SCREEN_HEIGHT - 90,
            w, h,
        )


ATTACK_MODE_BUTTON = AttackModeButton()


class OrderSystem:
    """Click-driven order flow. No class selection; the mouse button + the
    clicked side decide the action."""

    def __init__(self):
        self.order_history = []
        self.hovered_building = None   # ("player"|"enemy", index)
        self.feedback_msg = ""
        self.feedback_timer = 0.0
        ATTACK_MODE_BUTTON.update_rect()

    def update(self, dt: float):
        if self.feedback_timer > 0:
            self.feedback_timer -= dt
            if self.feedback_timer <= 0:
                self.feedback_msg = ""

    @property
    def attack_mode(self) -> str:
        return ATTACK_MODE_BUTTON.mode

    def set_mode_index(self, index: int):
        ATTACK_MODE_BUTTON.set_mode_index(index)

    # --- hover ----------------------------------------------------------
    def handle_mouse_move(self, mouse_pos, player_buildings, enemy_buildings):
        """Highlight whatever building is under the cursor (either side)."""
        mx, my = mouse_pos
        ATTACK_MODE_BUTTON.hovered = ATTACK_MODE_BUTTON.rect.collidepoint(mx, my)

        self.hovered_building = None
        for b in enemy_buildings:
            if self._building_rect(b).collidepoint(mx, my):
                self.hovered_building = ("enemy", b.index)
                return
        for b in player_buildings:
            if self._building_rect(b).collidepoint(mx, my):
                self.hovered_building = ("player", b.index)
                return

    # --- click ----------------------------------------------------------
    def handle_click(self, mouse_pos, player_buildings, enemy_buildings,
                     engine=None, button: int = 1):
        """Resolve a mouse click into an action.

        button: 1 = left, 3 = right.
          * Left-click a mode-selector hit  -> cycle mode (returns None)
          * Left-click an OWN building       -> ("heal_building", index)
          * Left-click an ENEMY building     -> ("attack_group", ESA_CLASSES, index)
          * Right-click an ENEMY building    -> ("attack_group", DEMO_CLASSES, index)
        Returns None if the click hit nothing actionable. Attack results list the
        classes to order; the battle session applies per-class visibility checks
        (the same ones a reach check would) and orders each that can reach.
        """
        mx, my = mouse_pos

        # Left-click on the mode bar cycles the attack mode.
        if button == 1 and ATTACK_MODE_BUTTON.rect.collidepoint(mx, my):
            ATTACK_MODE_BUTTON.toggle()
            return None

        # Own buildings: left-click heals the strongest dead member there.
        # (Right-clicking your own building does nothing.)
        if button == 1:
            for b in player_buildings:
                if self._building_rect(b).collidepoint(mx, my):
                    return ("heal_building", b.index)

        # Enemy buildings: left = ESA group, right = Demo group.
        for b in enemy_buildings:
            if self._building_rect(b).collidepoint(mx, my):
                classes = ESA_CLASSES if button == 1 else DEMO_CLASSES
                return ("attack_group", classes, b.index)

        return None

    # --- helpers --------------------------------------------------------
    def _create_order(self, member_class, building_index: int) -> Order:
        order = Order(member_class=member_class,
                      target_building=building_index,
                      action=OrderAction.ATTACK)
        self.order_history.append(order)
        return order

    def _building_rect(self, building) -> pygame.Rect:
        size = config.BUILDING_SIZE
        return pygame.Rect(
            int(building.x) - size // 2,
            int(building.y) - size // 2,
            size, size,
        )

    def get_prompt(self) -> str:
        if self.feedback_msg:
            return self.feedback_msg
        mode = ATTACK_MODE_BUTTON.label
        return (f"[{mode}]  L-click enemy: Enf+Sni+Assassin   "
                f"R-click enemy: Demo   L-click own: heal   "
                f"(A/S/D/F = 1/4 1/2 Full Auto)")

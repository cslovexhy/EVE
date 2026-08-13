"""EVE - Order System: Click class button, then click building."""

import pygame
from models import MemberClass, OrderAction, Order
import config


# Button layout at bottom of screen (positions calculated at init)
BUTTON_HEIGHT = 50
BUTTON_WIDTH = 120
BUTTON_GAP = 12


class ClassButton:
    """A clickable class selection button."""
    
    def __init__(self, index: int, label: str, member_class: MemberClass = None):
        """member_class=None means 'All' (all classes)."""
        self.label = label
        self.member_class = member_class
        self.index = index
        self.rect = pygame.Rect(0, 0, BUTTON_WIDTH, BUTTON_HEIGHT)
        self.hovered = False
        self.selected = False
    
    def update_rect(self):
        """Recalculate button position based on current screen size."""
        start_x = (config.SCREEN_WIDTH - (4 * BUTTON_WIDTH + 3 * BUTTON_GAP)) // 2
        button_y = config.SCREEN_HEIGHT - 90
        self.rect = pygame.Rect(
            start_x + self.index * (BUTTON_WIDTH + BUTTON_GAP),
            button_y,
            BUTTON_WIDTH,
            BUTTON_HEIGHT,
        )
    
    @property
    def color(self):
        if self.member_class is None:
            return config.WHITE
        return {
            MemberClass.ENFORCER: config.ENFORCER_COLOR,
            MemberClass.SNIPER: config.SNIPER_COLOR,
            MemberClass.ASSASSIN: config.ASSASSIN_COLOR,
            MemberClass.DEMOLITIONIST: config.DEMO_COLOR,
        }[self.member_class]


# Build the 4 buttons
CLASS_BUTTONS = [
    ClassButton(0, "[E] Enf", MemberClass.ENFORCER),
    ClassButton(1, "[A] Ass", MemberClass.ASSASSIN),
    ClassButton(2, "[S] Sni", MemberClass.SNIPER),
    ClassButton(3, "[D] Dem", MemberClass.DEMOLITIONIST),
]


class HealButton:
    """The Heal button — uses a health pack on selected class."""
    
    def __init__(self):
        self.rect = pygame.Rect(0, 0, BUTTON_WIDTH, BUTTON_HEIGHT)
        self.hovered = False
        self.label = "[H] Heal"
        self.color = (200, 50, 50)  # Red cross color
    
    def update_rect(self):
        """Position to the right of class buttons."""
        start_x = (config.SCREEN_WIDTH - (4 * BUTTON_WIDTH + 3 * BUTTON_GAP)) // 2
        button_y = config.SCREEN_HEIGHT - 90
        # Place after the 4 class buttons with a larger gap
        self.rect = pygame.Rect(
            start_x + 4 * (BUTTON_WIDTH + BUTTON_GAP) + BUTTON_GAP,
            button_y,
            BUTTON_WIDTH,
            BUTTON_HEIGHT,
        )


HEAL_BUTTON = HealButton()


class AttackModeButton:
    """Toggle between Half, Once, and Auto attack modes.
    
    Rotation: Half -> Once -> Auto -> Half
    Half = fire only half of the selected class (reduces ammo waste)
    Once = single volley from all, then stop
    Auto = sustained fire from all
    """
    
    # Mode cycle order
    MODES = ["half", "once", "auto"]
    
    def __init__(self):
        self.rect = pygame.Rect(0, 0, BUTTON_WIDTH, BUTTON_HEIGHT)
        self.hovered = False
        self.mode_index = 0  # Start on "half" (default)
    
    @property
    def mode(self) -> str:
        return self.MODES[self.mode_index]
    
    @property
    def label(self):
        return f"[T] {self.mode.capitalize()}"
    
    @property
    def color(self):
        if self.mode == "half":
            return (50, 140, 180)   # Blue-teal for half
        elif self.mode == "once":
            return (180, 180, 50)   # Yellow for once
        else:
            return (50, 180, 50)    # Green for auto
    
    def toggle(self):
        """Cycle to next mode: Half -> Once -> Auto -> Half."""
        self.mode_index = (self.mode_index + 1) % len(self.MODES)
    
    def update_rect(self):
        """Position to the left of class buttons."""
        start_x = (config.SCREEN_WIDTH - (4 * BUTTON_WIDTH + 3 * BUTTON_GAP)) // 2
        button_y = config.SCREEN_HEIGHT - 90
        self.rect = pygame.Rect(
            start_x - BUTTON_WIDTH - BUTTON_GAP * 2,
            button_y,
            BUTTON_WIDTH,
            BUTTON_HEIGHT,
        )


ATTACK_MODE_BUTTON = AttackModeButton()


class OrderSystem:
    """Mouse-click order flow: select class → click building."""
    
    def __init__(self):
        self.selected_class = None
        self.selected_button = None
        self.order_history = []
        self.hovered_building = None
        self.feedback_msg = ""
        self.feedback_timer = 0.0
        self.heal_mode = False  # True when player presses H, waiting for building click
        # Update button positions based on screen size
        for btn in CLASS_BUTTONS:
            btn.update_rect()
        HEAL_BUTTON.update_rect()
        ATTACK_MODE_BUTTON.update_rect()
    
    def update(self, dt: float):
        """Update feedback timer."""
        if self.feedback_timer > 0:
            self.feedback_timer -= dt
            if self.feedback_timer <= 0:
                self.feedback_msg = ""
    
    @property
    def can_issue_order(self) -> bool:
        return True
    
    @property
    def attack_mode(self) -> str:
        """Current attack mode from the toggle button."""
        return ATTACK_MODE_BUTTON.mode
    
    @property
    def has_class_selected(self) -> bool:
        return self.selected_button is not None
    
    def handle_mouse_move(self, mouse_pos: tuple, player_buildings: list, enemy_buildings: list):
        """Update hover state for buttons and buildings."""
        mx, my = mouse_pos
        
        # Update button hover
        for btn in CLASS_BUTTONS:
            btn.hovered = btn.rect.collidepoint(mx, my)
        HEAL_BUTTON.hovered = HEAL_BUTTON.rect.collidepoint(mx, my)
        ATTACK_MODE_BUTTON.hovered = ATTACK_MODE_BUTTON.rect.collidepoint(mx, my)
        
        # Update building hover (only if a class is selected or in heal mode)
        self.hovered_building = None
        if self.has_class_selected or self.heal_mode:
            for b in player_buildings:
                if not b.destroyed and self._building_rect(b).collidepoint(mx, my):
                    self.hovered_building = ("player", b.index)
                    return
            if not self.heal_mode:
                for b in enemy_buildings:
                    if not b.destroyed and self._building_rect(b).collidepoint(mx, my):
                        self.hovered_building = ("enemy", b.index)
                        return
    
    def handle_click(self, mouse_pos: tuple, player_buildings: list, enemy_buildings: list, engine=None) -> Order:
        """Handle a mouse click. Returns an Order if one was completed, else None.
        Returns ('heal_building', index) tuple if heal was applied to a building."""
        mx, my = mouse_pos
        
        # Check heal button — toggles heal mode
        if HEAL_BUTTON.rect.collidepoint(mx, my):
            self.heal_mode = not self.heal_mode
            return None
        
        # Check attack mode toggle
        if ATTACK_MODE_BUTTON.rect.collidepoint(mx, my):
            ATTACK_MODE_BUTTON.toggle()
            return None
        
        # Check class buttons
        for btn in CLASS_BUTTONS:
            if btn.rect.collidepoint(mx, my):
                self._select_button(btn)
                self.heal_mode = False  # Exit heal mode on class select
                return None
        
        # If in heal mode, clicking a player building triggers heal
        if self.heal_mode:
            for b in player_buildings:
                if not b.destroyed and self._building_rect(b).collidepoint(mx, my):
                    self.heal_mode = False
                    return ("heal_building", b.index)
            return None
        
        # Check building click (only if class is selected)
        if not self.has_class_selected:
            return None
        
        # Check enemy buildings → attack (with visibility check)
        for b in enemy_buildings:
            if not b.destroyed and self._building_rect(b).collidepoint(mx, my):
                # Check if selected class can reach this building
                if engine and self.selected_class is not None:
                    if not engine.is_attackable_by_class(b.index, self.selected_class, is_player=True):
                        self.feedback_msg = "No visibility"
                        self.feedback_timer = 1.5
                        return None
                
                return self._create_order(b.index, OrderAction.ATTACK)
        
        return None
    
    def _select_button(self, btn: ClassButton):
        """Select a class button (no deselect on repeat click)."""
        if self.selected_button == btn:
            return  # Already selected, do nothing
        
        # Deselect old
        if self.selected_button:
            self.selected_button.selected = False
        
        # Select new
        btn.selected = True
        self.selected_button = btn
        self.selected_class = btn.member_class  # None = "all"
    
    def select_button_by_index(self, index: int):
        """Select a class button by index (for keyboard shortcuts)."""
        if 0 <= index < len(CLASS_BUTTONS):
            self._select_button(CLASS_BUTTONS[index])
    
    def _create_order(self, building_index: int, action: OrderAction) -> Order:
        """Create and return an order."""
        order = Order(
            member_class=self.selected_class,  # None means all classes
            target_building=building_index,
            action=action,
        )
        self.order_history.append(order)
        return order
    
    def _building_rect(self, building) -> pygame.Rect:
        """Get the clickable rect for a building."""
        size = config.BUILDING_SIZE
        return pygame.Rect(
            int(building.x) - size // 2,
            int(building.y) - size // 2,
            size,
            size,
        )
    
    def get_prompt(self) -> str:
        """Get the current prompt/status text."""
        if self.feedback_msg:
            return self.feedback_msg
        if self.heal_mode:
            return "HEAL MODE — click a building to revive a defender"
        if not self.has_class_selected:
            return "Select a class, then click a building"
        
        class_name = self.selected_button.label
        mode = ATTACK_MODE_BUTTON.mode.capitalize()
        return f"{class_name} selected [{mode}] — click enemy building to attack"

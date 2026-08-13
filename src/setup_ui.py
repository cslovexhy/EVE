"""EVE - Pre-battle Setup UI: Building arrangement + Member assignment."""

import json
import os
import pygame
import config
from models import Empire, MemberClass, MemberState, Building


# Save file path
SETUP_SAVE_PATH = os.path.join(os.path.dirname(__file__), "..", "player_setup.json")

# Building names in default order (index 0-8)
BUILDING_NAMES = [
    "Headquarters", "Armory", "Hospital",
    "Warehouse", "Bunker", "Nuclear Silo",
    "Sniper Tower", "Research Lab", "Safehouse",
]

# Short names for compact display
BUILDING_SHORT = [
    "HQ", "Armory", "Hosp",
    "Warehs", "Bunker", "Nuke",
    "Sniper", "ResLab", "Safe",
]


def _save_setup(building_order: list, member_assignments: list):
    """Save player's setup configuration to disk."""
    data = {
        "building_order": building_order,
        "member_assignments": member_assignments,
    }
    with open(SETUP_SAVE_PATH, "w") as f:
        json.dump(data, f, indent=2)


def _load_setup() -> tuple:
    """Load saved setup from disk. Returns (building_order, member_assignments) or (None, None)."""
    if not os.path.exists(SETUP_SAVE_PATH):
        return None, None
    try:
        with open(SETUP_SAVE_PATH, "r") as f:
            data = json.load(f)
        building_order = data["building_order"]
        member_assignments = data["member_assignments"]
        # Validate
        if len(building_order) != 9 or sorted(building_order) != list(range(9)):
            return None, None
        if len(member_assignments) != 9:
            return None, None
        total = sum(len(s) for s in member_assignments)
        if total != 40:
            return None, None
        return building_order, member_assignments
    except (json.JSONDecodeError, KeyError, TypeError):
        return None, None


class SetupUI:
    """Pre-battle setup screen with two tabs:
    1. Building Arrangement: drag buildings to grid slots
    2. Member Assignment: assign members to buildings
    
    Controls:
    - TAB: switch between arrangement / assignment tabs
    - Click: select/swap buildings or assign members
    - ENTER/SPACE: start battle
    """
    
    def __init__(self, screen: pygame.Surface, empire: Empire):
        self.screen = screen
        self.empire = empire
        self.done = False  # Set True when player starts battle
        
        # Tab state
        self.tab = "buildings"  # "buildings" or "members"
        
        # Try loading saved configuration
        saved_order, saved_assignments = _load_setup()
        
        if saved_order is not None:
            self.building_order = saved_order
            self.member_assignments = saved_assignments
        else:
            # Default: building i in slot i
            self.building_order = list(range(9))
            self._init_default_assignments()
        
        self.selected_slot = None  # For swap-based arrangement
        self.selected_member_class = None
        self.selected_member_idx = None
        
        # UI
        self.font_title = pygame.font.SysFont("Arial", 36, bold=True)
        self.font_medium = pygame.font.SysFont("Arial", 22)
        self.font_small = pygame.font.SysFont("Arial", 16)
        self.font_btn = pygame.font.SysFont("Arial", 18, bold=True)
        
        # Grid layout for building slots
        self.slot_rects = {}
        self.slot_size = 120
        self._compute_layout()
    
    def _init_default_assignments(self):
        """Set up default member assignments matching the engine's logic."""
        self.member_assignments = [[] for _ in range(9)]
        
        enforcers = [i for i, m in enumerate(self.empire.members)
                     if m.member_class == MemberClass.ENFORCER]
        others = [i for i, m in enumerate(self.empire.members)
                  if m.member_class != MemberClass.ENFORCER]
        
        # Others all in slot 2 (building 3)
        self.member_assignments[2] = list(others)
        
        # Enforcers spread across other slots
        other_slots = [0, 1, 3, 4, 5, 6, 7, 8]
        for i, enf_idx in enumerate(enforcers):
            slot = other_slots[i % len(other_slots)]
            self.member_assignments[slot].append(enf_idx)
    
    def _compute_layout(self):
        """Compute grid slot positions for building arrangement.
        
        Layout matches the blue side of the battlefield:
        Columns are reversed (right-to-left on battlefield = left-to-right in setup)
          3 2 1
          6 5 4
          9 8 7
        Slot numbers are 1-based.
        """
        self.slot_rects = {}  # slot_index -> Rect
        grid_start_x = config.SCREEN_WIDTH // 2 - (3 * self.slot_size + 2 * 20) // 2
        grid_start_y = 160
        
        for row in range(3):
            for col in range(3):
                # Columns reversed: col 0 in display = col 2 in game (index 2,5,8)
                game_col = 2 - col
                slot_idx = row * 3 + game_col
                x = grid_start_x + col * (self.slot_size + 20)
                y = grid_start_y + row * (self.slot_size + 20)
                self.slot_rects[slot_idx] = pygame.Rect(x, y, self.slot_size, self.slot_size)
    
    def run(self) -> list:
        """Run the setup UI loop. Returns building_order when done.
        
        Returns:
            building_order: list where building_order[slot] = building_name_index
        """
        clock = pygame.time.Clock()
        
        while not self.done:
            dt = clock.tick(config.FPS) / 1000.0
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    import sys
                    sys.exit()
                elif event.type == pygame.KEYDOWN:
                    self._handle_key(event.key)
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self._handle_click(event.pos)
            
            self._render()
            pygame.display.flip()
        
        # Save configuration to disk for next time
        _save_setup(self.building_order, self.member_assignments)
        
        return self.building_order, self.member_assignments
    
    def _handle_key(self, key):
        """Handle keyboard input."""
        if key == pygame.K_TAB:
            self.tab = "members" if self.tab == "buildings" else "buildings"
            self.selected_slot = None
            self.selected_member_idx = None
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            self.done = True
        elif key in (pygame.K_q, pygame.K_ESCAPE):
            pygame.quit()
            import sys
            sys.exit()
    
    def _handle_click(self, pos):
        """Handle mouse click."""
        mx, my = pos
        
        # Check start button
        start_rect = self._get_start_button_rect()
        if start_rect.collidepoint(mx, my):
            self.done = True
            return
        
        # Check tab buttons
        tab_b_rect, tab_m_rect = self._get_tab_rects()
        if tab_b_rect.collidepoint(mx, my):
            self.tab = "buildings"
            self.selected_slot = None
            return
        if tab_m_rect.collidepoint(mx, my):
            self.tab = "members"
            self.selected_slot = None
            return
        
        if self.tab == "buildings":
            self._handle_building_click(pos)
        else:
            self._handle_member_click(pos)
    
    def _handle_building_click(self, pos):
        """Handle click in buildings arrangement tab — swap two slots."""
        mx, my = pos
        
        for i, rect in self.slot_rects.items():
            if rect.collidepoint(mx, my):
                if self.selected_slot is None:
                    self.selected_slot = i
                elif self.selected_slot == i:
                    self.selected_slot = None  # Deselect
                else:
                    # Swap buildings between slots
                    a, b = self.selected_slot, i
                    self.building_order[a], self.building_order[b] = \
                        self.building_order[b], self.building_order[a]
                    # Also swap member assignments
                    self.member_assignments[a], self.member_assignments[b] = \
                        self.member_assignments[b], self.member_assignments[a]
                    self.selected_slot = None
                return
    
    def _handle_member_click(self, pos):
        """Handle click in member assignment tab.
        
        Click a member in the roster → click a building slot to assign them there.
        """
        mx, my = pos
        
        # Check if clicking a building slot (to assign selected member)
        if self.selected_member_idx is not None:
            for i, rect in self.slot_rects.items():
                if rect.collidepoint(mx, my):
                    # Move member from current slot to clicked slot
                    self._move_member(self.selected_member_idx, i)
                    self.selected_member_idx = None
                    return
        
        # Check if clicking a member in the roster panel
        member_idx = self._get_member_at_pos(pos)
        if member_idx is not None:
            if self.selected_member_idx == member_idx:
                self.selected_member_idx = None  # Deselect
            else:
                self.selected_member_idx = member_idx
            return
        
        # Check if clicking a building slot to see its members
        for i, rect in self.slot_rects.items():
            if rect.collidepoint(mx, my):
                self.selected_slot = i if self.selected_slot != i else None
                return
    
    def _move_member(self, member_idx: int, target_slot: int):
        """Move a member from their current slot to target slot."""
        # Remove from current slot
        for slot_members in self.member_assignments:
            if member_idx in slot_members:
                slot_members.remove(member_idx)
                break
        # Add to target slot
        self.member_assignments[target_slot].append(member_idx)
    
    def _get_member_at_pos(self, pos) -> int:
        """Get member index at mouse position in the roster panel, or None."""
        mx, my = pos
        roster_x = config.SCREEN_WIDTH // 2 + 250
        roster_y = 170
        row_height = 20
        
        # Check each class section
        y_offset = roster_y
        for cls in MemberClass:
            members_of_class = [(i, m) for i, m in enumerate(self.empire.members)
                                if m.member_class == cls]
            y_offset += 25  # Class header
            for idx, (member_idx, member) in enumerate(members_of_class):
                rect = pygame.Rect(roster_x, y_offset, 200, row_height)
                if rect.collidepoint(mx, my):
                    return member_idx
                y_offset += row_height
            y_offset += 10  # Gap between classes
        
        return None
    
    def _render(self):
        """Render the setup screen."""
        self.screen.fill((20, 20, 30))
        
        # Title
        title = self.font_title.render("BATTLE SETUP", True, config.GOLD)
        title_rect = title.get_rect(centerx=config.SCREEN_WIDTH // 2, y=20)
        self.screen.blit(title, title_rect)
        
        # Tab buttons
        self._draw_tabs()
        
        # Content
        if self.tab == "buildings":
            self._render_buildings_tab()
        else:
            self._render_members_tab()
        
        # Start button
        self._draw_start_button()
        
        # Instructions
        self._draw_instructions()
    
    def _draw_tabs(self):
        """Draw tab selector buttons."""
        tab_b_rect, tab_m_rect = self._get_tab_rects()
        
        # Buildings tab
        active = self.tab == "buildings"
        color = config.GOLD if active else config.GRAY
        pygame.draw.rect(self.screen, color, tab_b_rect, 0 if active else 2, border_radius=4)
        text_color = config.BLACK if active else config.WHITE
        text = self.font_btn.render("Buildings", True, text_color)
        text_rect = text.get_rect(center=tab_b_rect.center)
        self.screen.blit(text, text_rect)
        
        # Members tab
        active = self.tab == "members"
        color = config.GOLD if active else config.GRAY
        pygame.draw.rect(self.screen, color, tab_m_rect, 0 if active else 2, border_radius=4)
        text_color = config.BLACK if active else config.WHITE
        text = self.font_btn.render("Members", True, text_color)
        text_rect = text.get_rect(center=tab_m_rect.center)
        self.screen.blit(text, text_rect)
    
    def _get_tab_rects(self):
        """Get tab button rectangles."""
        cx = config.SCREEN_WIDTH // 2
        tab_b = pygame.Rect(cx - 160, 70, 150, 35)
        tab_m = pygame.Rect(cx + 10, 70, 150, 35)
        return tab_b, tab_m
    
    def _render_buildings_tab(self):
        """Render the building arrangement grid."""
        # Instructions
        inst = self.font_medium.render("Click two slots to swap buildings", True, config.LIGHT_GRAY)
        inst_rect = inst.get_rect(centerx=config.SCREEN_WIDTH // 2, y=120)
        self.screen.blit(inst, inst_rect)
        
        # Draw grid with slot labels
        # Grid is flipped vertically: front row (7/8/9) at top, back row (1/2/3) at bottom
        for i, rect in self.slot_rects.items():
            building_name_idx = self.building_order[i]
            
            # Highlight selected
            if i == self.selected_slot:
                pygame.draw.rect(self.screen, config.GOLD, rect.inflate(6, 6), 3, border_radius=6)
            
            # Slot background
            bg_color = (40, 40, 55)
            pygame.draw.rect(self.screen, bg_color, rect, border_radius=6)
            pygame.draw.rect(self.screen, config.GRAY, rect, 2, border_radius=6)
            
            # Slot number (top-left)
            slot_text = self.font_small.render(f"Slot {i+1}", True, config.GRAY)
            self.screen.blit(slot_text, (rect.x + 5, rect.y + 3))
            
            # Building name (center)
            name = BUILDING_NAMES[building_name_idx]
            name_text = self.font_btn.render(name, True, config.WHITE)
            name_rect = name_text.get_rect(center=rect.center)
            self.screen.blit(name_text, name_rect)
            
            # Member count at this slot (bottom)
            count = len(self.member_assignments[i])
            count_text = self.font_small.render(f"{count} members", True, config.LIGHT_GRAY)
            count_rect = count_text.get_rect(centerx=rect.centerx, y=rect.bottom - 20)
            self.screen.blit(count_text, count_rect)
    
    def _render_members_tab(self):
        """Render the member assignment view."""
        # Instructions
        if self.selected_member_idx is not None:
            member = self.empire.members[self.selected_member_idx]
            inst_text = f"Click a building slot to assign {member.name}"
            inst_color = config.GOLD
        elif self.selected_slot is not None:
            inst_text = f"Slot {self.selected_slot+1}: {BUILDING_NAMES[self.building_order[self.selected_slot]]}"
            inst_color = config.LIGHT_GRAY
        else:
            inst_text = "Click a member, then click a building slot to assign"
            inst_color = config.LIGHT_GRAY
        
        inst = self.font_medium.render(inst_text, True, inst_color)
        inst_rect = inst.get_rect(centerx=config.SCREEN_WIDTH // 2, y=120)
        self.screen.blit(inst, inst_rect)
        
        # Draw building grid (left side) - smaller
        for i, rect in self.slot_rects.items():
            building_name_idx = self.building_order[i]
            
            # Highlight if selected
            if i == self.selected_slot:
                pygame.draw.rect(self.screen, config.GOLD, rect.inflate(6, 6), 3, border_radius=6)
            
            bg_color = (40, 40, 55)
            pygame.draw.rect(self.screen, bg_color, rect, border_radius=6)
            pygame.draw.rect(self.screen, config.GRAY, rect, 2, border_radius=6)
            
            # Building name
            short_name = BUILDING_SHORT[building_name_idx]
            name_text = self.font_btn.render(short_name, True, config.WHITE)
            name_rect = name_text.get_rect(centerx=rect.centerx, y=rect.y + 5)
            self.screen.blit(name_text, name_rect)
            
            # Members assigned here (compact)
            members_here = self.member_assignments[i]
            y_off = rect.y + 28
            for mi in members_here[:config.BUILDING_DEFENDER_SLOTS]:
                m = self.empire.members[mi]
                cls_color = self._class_color(m.member_class)
                # Highlight if this member is selected
                if mi == self.selected_member_idx:
                    pygame.draw.rect(self.screen, config.GOLD, 
                                     pygame.Rect(rect.x + 3, y_off - 1, rect.width - 6, 16), 1)
                mtext = self.font_small.render(f"{m.name[:8]}", True, cls_color)
                self.screen.blit(mtext, (rect.x + 8, y_off))
                y_off += 16
            
            # Overflow indicator
            if len(members_here) > config.BUILDING_DEFENDER_SLOTS:
                extra = len(members_here) - config.BUILDING_DEFENDER_SLOTS
                more_text = self.font_small.render(f"+{extra} more", True, config.GRAY)
                self.screen.blit(more_text, (rect.x + 8, y_off))
        
        # Draw member roster (right side)
        self._draw_member_roster()
    
    def _draw_member_roster(self):
        """Draw the full member roster on the right side."""
        roster_x = config.SCREEN_WIDTH // 2 + 250
        roster_y = 170
        row_height = 20
        
        y_offset = roster_y
        for cls in MemberClass:
            # Class header
            cls_color = self._class_color(cls)
            header = self.font_btn.render(f"— {cls.value.capitalize()} —", True, cls_color)
            self.screen.blit(header, (roster_x, y_offset))
            y_offset += 25
            
            members_of_class = [(i, m) for i, m in enumerate(self.empire.members)
                                if m.member_class == cls]
            
            for member_idx, member in members_of_class:
                # Find which slot this member is in
                slot = None
                for s, members_in_slot in enumerate(self.member_assignments):
                    if member_idx in members_in_slot:
                        slot = s
                        break
                
                # Highlight selected
                if member_idx == self.selected_member_idx:
                    highlight_rect = pygame.Rect(roster_x - 3, y_offset - 1, 210, row_height)
                    pygame.draw.rect(self.screen, config.GOLD, highlight_rect, 1)
                
                slot_str = f"[S{slot+1}]" if slot is not None else "[--]"
                text = self.font_small.render(f"{member.name:12s} {slot_str}", True, config.WHITE)
                self.screen.blit(text, (roster_x, y_offset))
                y_offset += row_height
            
            y_offset += 10
    
    def _draw_start_button(self):
        """Draw the Start Battle button."""
        rect = self._get_start_button_rect()
        pygame.draw.rect(self.screen, config.GREEN, rect, border_radius=8)
        pygame.draw.rect(self.screen, config.WHITE, rect, 2, border_radius=8)
        text = self.font_title.render("START BATTLE", True, config.BLACK)
        text_rect = text.get_rect(center=rect.center)
        self.screen.blit(text, text_rect)
    
    def _get_start_button_rect(self) -> pygame.Rect:
        return pygame.Rect(
            config.SCREEN_WIDTH // 2 - 150,
            config.SCREEN_HEIGHT - 80,
            300, 55
        )
    
    def _draw_instructions(self):
        """Draw keyboard shortcut hints."""
        hints = [
            "TAB: Switch tab  |  ENTER/SPACE: Start Battle  |  Q/ESC: Quit",
            "Buildings tab: click two slots to swap  |  Members tab: click member then slot",
        ]
        y = config.SCREEN_HEIGHT - 130
        for hint in hints:
            text = self.font_small.render(hint, True, config.GRAY)
            text_rect = text.get_rect(centerx=config.SCREEN_WIDTH // 2, y=y)
            self.screen.blit(text, text_rect)
            y += 20
    
    def _class_color(self, cls: MemberClass):
        return {
            MemberClass.ENFORCER: config.ENFORCER_COLOR,
            MemberClass.SNIPER: config.SNIPER_COLOR,
            MemberClass.ASSASSIN: config.ASSASSIN_COLOR,
            MemberClass.DEMOLITIONIST: config.DEMO_COLOR,
        }[cls]

"""EVE - Navigable screens: Main Menu, EVE Layout (base management), Map.

Each screen exposes a blocking run() that returns a navigation result:
  MainMenu.run()  -> "map" | "layout" | "quit"
  EveLayout.run() -> "menu"
  MapScreen.run() -> ("battle", city_id) | "menu"

EVE Layout is the single base-management screen: Upgrade buildings, Arrange
(swap) their positions, and assign Members. All changes persist to the profile,
so wars launch straight into battle with no pre-battle setup step.

NOTE: the Map's country/state/city structure is a first-pass placeholder.
docs/questions.md section 4 (map structure, rival empires per city, etc.) is
still open, so MAP_DATA below is provisional and meant to be iterated on.
"""
import sys

import pygame

import config
import buildings
import game_state
import world_map as wm
from models import Empire, BuildingType, MemberClass


class Button:
    """A simple clickable button."""

    def __init__(self, rect, label, font, enabled=True, base_color=None):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.font = font
        self.enabled = enabled
        self.base_color = base_color or config.GREEN

    def draw(self, screen, mouse_pos=None):
        hover = self.enabled and mouse_pos is not None and self.rect.collidepoint(mouse_pos)
        if not self.enabled:
            color = config.DARK_GRAY
        elif hover:
            color = tuple(min(255, c + 40) for c in self.base_color)
        else:
            color = self.base_color
        pygame.draw.rect(screen, color, self.rect, border_radius=8)
        pygame.draw.rect(screen, config.WHITE, self.rect, 2, border_radius=8)
        text_color = config.BLACK if self.enabled else config.GRAY
        txt = self.font.render(self.label, True, text_color)
        screen.blit(txt, txt.get_rect(center=self.rect.center))

    def hit(self, pos) -> bool:
        return self.enabled and self.rect.collidepoint(pos)


class _Screen:
    """Base class with a blocking loop and font setup."""

    def __init__(self, screen):
        self.screen = screen
        self.result = None
        self.done = False
        self.clock = pygame.time.Clock()
        self.font_title = pygame.font.SysFont("Arial", 48, bold=True)
        self.font_h = pygame.font.SysFont("Arial", 28, bold=True)
        self.font_btn = pygame.font.SysFont("Arial", 22, bold=True)
        self.font_med = pygame.font.SysFont("Arial", 20)
        self.font_small = pygame.font.SysFont("Arial", 16)

    def run(self):
        while not self.done:
            self.clock.tick(config.FPS)
            mouse_pos = pygame.mouse.get_pos()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                elif event.type == pygame.KEYDOWN:
                    self.handle_key(event.key)
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self.handle_click(event.pos)
                elif event.type == pygame.MOUSEWHEEL:
                    self.handle_scroll(event.y, pygame.mouse.get_pos())
            self.render(mouse_pos)
            pygame.display.flip()
        return self.result

    # Overridable hooks
    def handle_key(self, key):
        pass

    def handle_click(self, pos):
        pass

    def handle_scroll(self, dy, pos):
        pass

    def render(self, mouse_pos):
        pass


# ---------------------------------------------------------------------------
# Main Menu
# ---------------------------------------------------------------------------
class MainMenu(_Screen):
    def __init__(self, screen):
        super().__init__(screen)
        cx = config.SCREEN_WIDTH // 2
        w, h, gap = 320, 64, 24
        y0 = config.SCREEN_HEIGHT // 2 - 60
        self.buttons = {
            "map": Button((cx - w // 2, y0, w, h), "Map", self.font_btn),
            "layout": Button((cx - w // 2, y0 + (h + gap), w, h), "EVE Layout", self.font_btn),
            "quit": Button((cx - w // 2, y0 + 2 * (h + gap), w, h), "Quit", self.font_btn,
                           base_color=config.RED),
        }

    def handle_key(self, key):
        if key in (pygame.K_q, pygame.K_ESCAPE):
            self.result = "quit"
            self.done = True

    def handle_click(self, pos):
        for name, btn in self.buttons.items():
            if btn.hit(pos):
                self.result = name
                self.done = True
                return

    def render(self, mouse_pos):
        self.screen.fill((18, 18, 28))
        title = self.font_title.render("EVE", True, config.GOLD)
        self.screen.blit(title, title.get_rect(centerx=config.SCREEN_WIDTH // 2, y=120))
        sub = self.font_h.render("Empire vs Empire", True, config.LIGHT_GRAY)
        self.screen.blit(sub, sub.get_rect(centerx=config.SCREEN_WIDTH // 2, y=185))
        for btn in self.buttons.values():
            btn.draw(self.screen, mouse_pos)


# ---------------------------------------------------------------------------
# EVE Layout: single base-management screen (Upgrade / Arrange / Members)
# ---------------------------------------------------------------------------
class EveLayout(_Screen):
    """Manages the persistent base. Three tabs:
      - Upgrade : click a slot, buy an upgrade (money-gated by the chain)
      - Arrange : click two slots to swap their buildings (and defenders)
      - Members : click a member, click a slot to assign them there
    Every change syncs to the GameState and saves immediately."""

    TABS = ("upgrade", "arrange", "members", "force")
    TAB_LABELS = {"upgrade": "Upgrade", "arrange": "Arrange",
                  "members": "Assign", "force": "Force"}

    def __init__(self, screen, state):
        super().__init__(screen)
        self.state = state

        # The active roster is persisted on the profile; build a working empire
        # from it (fresh copies) so this screen mirrors money + layout + roster.
        self.empire = self.state.build_player_empire("Your Empire")
        # Local working copy of assignments (list of 9 lists of member indices).
        self.member_assignments = [list(s) for s in self.empire.member_assignments]

        self.tab = "upgrade"
        self.selected_slot = None      # Upgrade tab
        self.swap_slot = None          # Arrange tab
        self.selected_member = None    # Assign tab
        self.force_sel = None          # Force tab: ("active"|"backup", idx)
        self.feedback = ""

        # Scroll offsets (pixels) for the scrollable lists.
        self.assign_scroll = 0
        self.active_scroll = 0
        self.backup_scroll = 0

        self.slot_size = 150
        self.gap = 18
        self.grid_x = 70
        self.grid_y = 170
        self._compute_slot_rects()

        self.back_btn = Button(
            (40, config.SCREEN_HEIGHT - 80, 200, 52), "Back", self.font_btn,
            base_color=config.GRAY)
        self.tab_rects = {}
        self.upgrade_rows = []   # (rect, target_type, ok)
        self.roster_rows = []    # (rect, member_idx)   [Assign tab]
        self.active_rows = []    # (rect, roster_idx)   [Force tab]
        self.backup_rows = []    # (rect, backup_idx)   [Force tab]
        self.force_action_rects = {}  # name -> rect  [Force tab bottom bar]

    def _compute_slot_rects(self):
        self.slot_rects = {}
        for row in range(3):
            for col in range(3):
                game_col = 2 - col  # mirror battlefield orientation (3 2 1 / ...)
                slot_idx = row * 3 + game_col
                x = self.grid_x + col * (self.slot_size + self.gap)
                y = self.grid_y + row * (self.slot_size + self.gap)
                self.slot_rects[slot_idx] = pygame.Rect(x, y, self.slot_size, self.slot_size)

    def _sync_to_state(self):
        self.state.money = self.empire.money
        self.state.building_layout = [b.building_type for b in self.empire.buildings]
        self.state.building_levels = [b.level for b in self.empire.buildings]
        self.state.member_assignments = [list(s) for s in self.member_assignments]
        self.state.save()

    def _rebuild_from_state(self):
        """Rebuild the working empire + assignments from the persisted state
        (after a Force-tab move that changed the roster and its indices)."""
        self.empire = self.state.build_player_empire("Your Empire")
        self.member_assignments = [list(s) for s in self.empire.member_assignments]

    # --- input -----------------------------------------------------------
    def handle_key(self, key):
        if key in (pygame.K_q, pygame.K_ESCAPE):
            self.result = "menu"
            self.done = True
        elif key == pygame.K_TAB:
            i = self.TABS.index(self.tab)
            self.tab = self.TABS[(i + 1) % len(self.TABS)]
            self._reset_selection()

    def _reset_selection(self):
        self.selected_slot = None
        self.swap_slot = None
        self.selected_member = None
        self.force_sel = None
        self.feedback = ""

    def handle_click(self, pos):
        if self.back_btn.hit(pos):
            self.result = "menu"
            self.done = True
            return
        # Tab switching.
        for name, rect in self.tab_rects.items():
            if rect.collidepoint(pos):
                if self.tab != name:
                    self.tab = name
                    self._reset_selection()
                return

        if self.tab == "upgrade":
            self._click_upgrade(pos)
        elif self.tab == "arrange":
            self._click_arrange(pos)
        elif self.tab == "members":
            self._click_members(pos)
        else:
            self._click_force(pos)

    def handle_scroll(self, dy, pos):
        step = 40 * dy
        if self.tab == "members":
            self.assign_scroll = max(0, self.assign_scroll - step)
        elif self.tab == "force":
            # Scroll whichever column the cursor is over.
            mid = self._force_column_split()
            if pos[0] < mid:
                self.active_scroll = max(0, self.active_scroll - step)
            else:
                self.backup_scroll = max(0, self.backup_scroll - step)

    def _click_upgrade(self, pos):
        for rect, target, ok in self.upgrade_rows:
            if rect.collidepoint(pos):
                if ok and target == "LEVEL_HQ":
                    success, reason = buildings.level_up_hq(self.empire, self.selected_slot)
                    if success:
                        self._sync_to_state()
                        lvl = self.empire.buildings[self.selected_slot].level
                        self.feedback = f"HQ upgraded to Lv{lvl} (roster cap {self.empire.member_cap()})"
                    else:
                        self.feedback = self._reason_text(reason, None)
                elif ok:
                    success, reason = buildings.upgrade_building(
                        self.empire, self.selected_slot, target)
                    if success:
                        self._sync_to_state()
                        self.feedback = (f"Upgraded slot {self.selected_slot + 1} "
                                         f"to {target.spec['display_name']}")
                    else:
                        self.feedback = self._reason_text(reason, target)
                return
        for idx, rect in self.slot_rects.items():
            if rect.collidepoint(pos):
                self.selected_slot = idx if self.selected_slot != idx else None
                self.feedback = ""
                return

    def _click_arrange(self, pos):
        for idx, rect in self.slot_rects.items():
            if rect.collidepoint(pos):
                if self.swap_slot is None:
                    self.swap_slot = idx
                elif self.swap_slot == idx:
                    self.swap_slot = None
                else:
                    self._swap_slots(self.swap_slot, idx)
                    self.swap_slot = None
                return

    def _swap_slots(self, a, b):
        ba, bb = self.empire.buildings[a], self.empire.buildings[b]
        ba.building_type, bb.building_type = bb.building_type, ba.building_type
        ba.level, bb.level = bb.level, ba.level
        ba.apply_type_hp()
        bb.apply_type_hp()
        self.member_assignments[a], self.member_assignments[b] = \
            self.member_assignments[b], self.member_assignments[a]
        self._sync_to_state()
        self.feedback = f"Swapped slots {a + 1} and {b + 1}"

    def _click_members(self, pos):
        # Assign a selected member to a clicked slot.
        if self.selected_member is not None:
            for idx, rect in self.slot_rects.items():
                if rect.collidepoint(pos):
                    self._move_member(self.selected_member, idx)
                    self.selected_member = None
                    self._sync_to_state()
                    return
        # Select a member from the roster.
        for rect, midx in self.roster_rows:
            if rect.collidepoint(pos):
                self.selected_member = None if self.selected_member == midx else midx
                return

    def _move_member(self, member_idx, target_slot):
        for slot in self.member_assignments:
            if member_idx in slot:
                slot.remove(member_idx)
                break
        self.member_assignments[target_slot].append(member_idx)

    # --- Force tab (active roster <-> backup force) -----------------------
    def _force_column_split(self):
        """X coordinate separating the Active (left) and Backup (right) columns,
        used to route scroll events to the column under the cursor."""
        left_x, right_x, col_w, *_ = self._force_layout()
        return (left_x + col_w + right_x) // 2

    def _click_force(self, pos):
        # Bottom action bar first (Bench / Activate / Kick).
        for name, rect in self.force_action_rects.items():
            if rect.collidepoint(pos):
                self._do_force_action(name)
                return
        # Select a row in either column.
        for rect, ridx in self.active_rows:
            if rect.collidepoint(pos):
                self.force_sel = None if self.force_sel == ("active", ridx) else ("active", ridx)
                self.feedback = ""
                return
        for rect, bidx in self.backup_rows:
            if rect.collidepoint(pos):
                self.force_sel = None if self.force_sel == ("backup", bidx) else ("backup", bidx)
                self.feedback = ""
                return

    def _do_force_action(self, name):
        if self.force_sel is None:
            return
        col, idx = self.force_sel
        if name == "bench" and col == "active":
            if len(self.empire.members) <= 1:
                self.feedback = "You must keep at least one member in the roster."
                return
            if self.state.move_to_backup(idx):
                self._rebuild_from_state()
                self.state.save()
                self.force_sel = None
                self.feedback = "Moved to backup force."
            else:
                self.feedback = f"Backup force is full (max {config.BACKUP_FORCE_CAP})."
        elif name == "activate" and col == "backup":
            if self.state.move_to_roster(idx):
                self._rebuild_from_state()
                self.state.save()
                self.force_sel = None
                over = self.state.roster_over_cap()
                self.feedback = ("Activated. Roster is OVER the HQ cap — bench "
                                 "someone before you can start a war."
                                 if over else "Activated into the roster.")
            else:
                self.feedback = "Could not activate."
        elif name == "kick" and col == "backup":
            if self.state.kick_backup(idx):
                self.state.save()
                self.force_sel = None
                self.feedback = "Recruit kicked out."

    def _reason_text(self, reason, target):
        if reason == "insufficient_funds":
            if target is None:
                return "Not enough money"
            return f"Not enough money (need ${buildings.upgrade_cost(target):,})"
        if reason == "max_count_reached":
            return f"Max {target.spec['display_name']} reached"
        return {
            "invalid_chain": "Cannot upgrade along that path",
            "already_this_type": "Already this type",
            "invalid_slot": "Invalid slot",
            "max_level": "HQ at max level",
            "not_hq": "Not an HQ",
        }.get(reason, reason)

    # --- render ----------------------------------------------------------
    def render(self, mouse_pos):
        self.screen.fill((22, 24, 34))
        title = self.font_title.render("EVE Layout", True, config.GOLD)
        self.screen.blit(title, (40, 24))
        self._draw_money_chip()

        self._draw_tabs(mouse_pos)
        if self.tab != "force":
            self._draw_grid(mouse_pos)

        if self.tab == "upgrade":
            self._render_upgrade_panel(mouse_pos)
        elif self.tab == "arrange":
            self._render_arrange_panel()
        elif self.tab == "members":
            self._render_members_panel(mouse_pos)
        else:
            self._render_force_panel(mouse_pos)

        if self.feedback:
            fb = self.font_med.render(self.feedback, True, config.GOLD)
            self.screen.blit(fb, (self.grid_x, self.grid_y + 3 * (self.slot_size + self.gap) + 8))

        self.back_btn.draw(self.screen, mouse_pos)
        self.screen.blit(
            self.font_small.render(self._hint(), True, config.GRAY),
            (self.grid_x, config.SCREEN_HEIGHT - 100))
    def _draw_money_chip(self):
        """Prominent, labeled money readout in the top-right."""
        surf = self.font_h.render(f"Money: ${self.state.money:,}", True, config.GOLD)
        pad = 14
        chip = pygame.Rect(0, 0, surf.get_width() + pad * 2, surf.get_height() + pad)
        chip.topright = (config.SCREEN_WIDTH - 30, 28)
        pygame.draw.rect(self.screen, (34, 60, 40), chip, border_radius=8)
        pygame.draw.rect(self.screen, config.GREEN, chip, 2, border_radius=8)
        self.screen.blit(surf, surf.get_rect(center=chip.center))

        # Roster cap (from HQ level) just below the money chip.
        hq_lvl = self.empire.hq_level()
        cap = self.state.member_cap()
        cap_txt = f"Roster cap: {cap}" + (f"  (HQ Lv{hq_lvl})" if hq_lvl else "  (no HQ)")
        cs = self.font_small.render(cap_txt, True, config.LIGHT_GRAY)
        self.screen.blit(cs, cs.get_rect(topright=(config.SCREEN_WIDTH - 32, chip.bottom + 6)))


    def _hint(self):
        return {
            "upgrade": "Click a slot, then click an upgrade to buy it.",
            "arrange": "Click two slots to swap their buildings.",
            "members": "Click a member, then click a slot to assign them.  (scroll to see more)",
            "force": "Move recruits between your Active Roster and Backup Force.  (scroll each list)",
        }[self.tab] + "   TAB: switch tab   Q/ESC: back"

    def _draw_tabs(self, mouse_pos):
        self.tab_rects = {}
        x, y, w, h, gap = 40, 90, 160, 40, 12
        for name in self.TABS:
            rect = pygame.Rect(x, y, w, h)
            active = self.tab == name
            color = config.GOLD if active else config.GRAY
            pygame.draw.rect(self.screen, color, rect, 0 if active else 2, border_radius=6)
            tcol = config.BLACK if active else config.WHITE
            txt = self.font_btn.render(self.TAB_LABELS[name], True, tcol)
            self.screen.blit(txt, txt.get_rect(center=rect.center))
            self.tab_rects[name] = rect
            x += w + gap

    def _draw_grid(self, mouse_pos):
        for idx, rect in self.slot_rects.items():
            b = self.empire.buildings[idx]
            highlight = (idx == self.selected_slot) or (idx == self.swap_slot)
            if highlight:
                pygame.draw.rect(self.screen, config.GOLD, rect.inflate(6, 6), 3, border_radius=8)
            pygame.draw.rect(self.screen, (42, 44, 60), rect, border_radius=8)
            pygame.draw.rect(self.screen, config.GRAY, rect, 2, border_radius=8)

            self.screen.blit(self.font_small.render(f"Slot {idx + 1}", True, config.GRAY),
                             (rect.x + 8, rect.y + 6))

            if self.tab == "members":
                self._draw_slot_members(rect, idx)
            else:
                name = self.font_btn.render(b.type_name, True, config.WHITE)
                self.screen.blit(name, name.get_rect(center=(rect.centerx, rect.centery - 8)))
                hp = self.font_small.render(f"HP {int(b.max_hp)}", True, config.LIGHT_GRAY)
                self.screen.blit(hp, hp.get_rect(centerx=rect.centerx, y=rect.bottom - 26))

    def _draw_slot_members(self, rect, idx):
        b = self.empire.buildings[idx]
        short = self.font_small.render(b.type_name, True, config.WHITE)
        self.screen.blit(short, (rect.x + 8, rect.y + 26))
        assigned = self.member_assignments[idx]
        y = rect.y + 48
        for mi in assigned[:config.BUILDING_DEFENDER_SLOTS]:
            m = self.empire.members[mi]
            col = self._class_color(m.member_class)
            if mi == self.selected_member:
                pygame.draw.rect(self.screen, config.GOLD,
                                 pygame.Rect(rect.x + 4, y - 1, rect.width - 8, 16), 1)
            self.screen.blit(self.font_small.render(m.name[:12], True, col), (rect.x + 10, y))
            y += 16
        if len(assigned) > config.BUILDING_DEFENDER_SLOTS:
            extra = len(assigned) - config.BUILDING_DEFENDER_SLOTS
            self.screen.blit(self.font_small.render(f"+{extra} more", True, config.GRAY),
                             (rect.x + 10, y))
        cnt = self.font_small.render(f"{len(assigned)} members", True, config.LIGHT_GRAY)
        self.screen.blit(cnt, cnt.get_rect(centerx=rect.centerx, y=rect.bottom - 20))

    def _panel_x(self):
        return self.grid_x + 3 * (self.slot_size + self.gap) + 50

    def _render_upgrade_panel(self, mouse_pos):
        self.upgrade_rows = []
        px, py = self._panel_x(), self.grid_y
        panel_w = 460
        self.screen.blit(self.font_h.render(f"Upgrades  (${self.state.money:,})", True, config.WHITE),
                         (px, py - 46))

        if self.selected_slot is None:
            self.screen.blit(self.font_med.render("Select a building slot on the left.",
                                                  True, config.LIGHT_GRAY), (px, py))
            return

        b = self.empire.buildings[self.selected_slot]
        self.screen.blit(self.font_med.render(
            f"Slot {self.selected_slot + 1}: {b.type_name} (HP {int(b.max_hp)})",
            True, config.GOLD), (px, py))

        targets = buildings.available_upgrade_targets(b.building_type)
        y = py + 44

        # HQ is leveled up (raises member cap + HP), not type-upgraded.
        if b.building_type == BuildingType.HEADQUARTERS:
            self._render_hq_levelup(px, y, panel_w, mouse_pos, b)
            return

        if not targets:
            self.screen.blit(self.font_med.render("No further upgrades available.",
                                                  True, config.LIGHT_GRAY), (px, y))
            return
        for target in targets:
            ok, reason = buildings.can_upgrade(self.empire, self.selected_slot, target)
            rect = pygame.Rect(px, y, panel_w, 56)
            hover = rect.collidepoint(mouse_pos)
            bg = ((64, 96, 64) if hover else (48, 70, 48)) if ok else (54, 40, 40)
            pygame.draw.rect(self.screen, bg, rect, border_radius=6)
            pygame.draw.rect(self.screen, config.GRAY, rect, 1, border_radius=6)
            spec = target.spec
            self.screen.blit(self.font_btn.render(spec["display_name"], True, config.WHITE),
                             (rect.x + 12, rect.y + 6))
            self.screen.blit(self.font_small.render(
                f"HP {spec['hp']}   Cost ${spec['upgrade_cost']:,}", True, config.LIGHT_GRAY),
                (rect.x + 12, rect.y + 32))
            if not ok:
                tag = self.font_small.render(self._reason_text(reason, target), True, config.RED)
                self.screen.blit(tag, tag.get_rect(right=rect.right - 12, centery=rect.centery))
            self.upgrade_rows.append((rect, target, ok))
            y += 66

    def _render_hq_levelup(self, px, y, panel_w, mouse_pos, b):
        cur_cap = config.BASE_MEMBER_CAP + config.HQ_MEMBERS_PER_LEVEL * b.level
        self.screen.blit(self.font_small.render(
            f"HQ Lv{b.level}  ·  roster cap {cur_cap}", True, config.LIGHT_GRAY), (px, y))
        y += 26
        if b.level >= config.HQ_MAX_LEVEL:
            self.screen.blit(self.font_med.render("HQ at max level (Lv4).",
                                                  True, config.LIGHT_GRAY), (px, y))
            return
        ok, reason = buildings.can_level_hq(self.empire, self.selected_slot)
        nxt = b.level + 1
        cost = buildings.hq_next_level_cost(b.level)
        new_hp = config.HQ_LEVEL_HP[nxt]
        new_cap = config.BASE_MEMBER_CAP + config.HQ_MEMBERS_PER_LEVEL * nxt
        rect = pygame.Rect(px, y, panel_w, 56)
        hover = rect.collidepoint(mouse_pos)
        bg = ((64, 96, 64) if hover else (48, 70, 48)) if ok else (54, 40, 40)
        pygame.draw.rect(self.screen, bg, rect, border_radius=6)
        pygame.draw.rect(self.screen, config.GRAY, rect, 1, border_radius=6)
        self.screen.blit(self.font_btn.render(f"Upgrade HQ to Lv{nxt}", True, config.WHITE),
                         (rect.x + 12, rect.y + 6))
        self.screen.blit(self.font_small.render(
            f"HP {new_hp}   Roster cap {new_cap}   Cost ${cost:,}", True, config.LIGHT_GRAY),
            (rect.x + 12, rect.y + 32))
        if not ok:
            tag = self.font_small.render(self._reason_text(reason, None), True, config.RED)
            self.screen.blit(tag, tag.get_rect(right=rect.right - 12, centery=rect.centery))
        self.upgrade_rows.append((rect, "LEVEL_HQ", ok))

    def _render_arrange_panel(self):
        px, py = self._panel_x(), self.grid_y
        self.screen.blit(self.font_h.render("Arrange", True, config.WHITE), (px, py - 46))
        lines = [
            "Click a building slot to pick it up,",
            "then click another slot to swap them.",
            "",
            "Front-row slots (1 / 4 / 7) are exposed",
            "first in battle — put your tankiest",
            "buildings (HQ, Bunker) up front.",
        ]
        if self.swap_slot is not None:
            b = self.empire.buildings[self.swap_slot]
            lines.append("")
            lines.append(f"Holding: Slot {self.swap_slot + 1} ({b.type_name})")
        y = py
        for ln in lines:
            self.screen.blit(self.font_med.render(ln, True, config.LIGHT_GRAY), (px, y))
            y += 30

    def _list_viewport(self):
        """(top, bottom, height) of the scrollable list area on the right."""
        top = self.grid_y
        bottom = self.grid_y + 3 * (self.slot_size + self.gap) - 24
        return top, bottom, bottom - top

    def _render_members_panel(self, mouse_pos):
        self.roster_rows = []
        px, py = self._panel_x(), self.grid_y
        n = len(self.empire.members)
        self.screen.blit(self.font_h.render(f"Assign to buildings  ({n})",
                                            True, config.WHITE), (px, py - 46))
        view_top, view_bottom, view_h = self._list_viewport()
        row_h = 20
        panel_w = 320

        # Lay out content in content-space, then cull to the viewport.
        items = []  # (kind, payload)  kind: 'header'|'member'
        for cls in MemberClass:
            items.append(("header", cls))
            for midx, m in enumerate(self.empire.members):
                if m.member_class == cls:
                    items.append(("member", (midx, m)))
            items.append(("gap", None))

        content_h = 0
        for kind, _ in items:
            content_h += 26 if kind == "header" else (8 if kind == "gap" else row_h)
        max_scroll = max(0, content_h - view_h)
        self.assign_scroll = min(self.assign_scroll, max_scroll)

        clip = pygame.Rect(px - 4, view_top - 2, panel_w + 20, view_h + 4)
        self.screen.set_clip(clip)
        cy = view_top - self.assign_scroll
        for kind, payload in items:
            if kind == "header":
                if cy + 26 > view_top and cy < view_bottom:
                    self.screen.blit(self.font_btn.render(
                        f"— {payload.value.capitalize()} —", True,
                        self._class_color(payload)), (px, cy))
                cy += 26
            elif kind == "gap":
                cy += 8
            else:
                midx, m = payload
                if cy + row_h > view_top and cy < view_bottom:
                    rect = pygame.Rect(px, cy, panel_w, row_h)
                    if midx == self.selected_member:
                        pygame.draw.rect(self.screen, config.GOLD, rect, 1)
                    slot = self._slot_of(midx)
                    slot_str = f"[S{slot + 1}]" if slot is not None else "[--]"
                    tag = f"L{m.level} {self._rarity_short(m.rarity)}"
                    self.screen.blit(self.font_small.render(
                        f"{m.name:12s} {slot_str} {tag}", True,
                        self._class_color(m.member_class)), (px + 2, cy))
                    self.roster_rows.append((rect, midx))
                cy += row_h
        self.screen.set_clip(None)
        self._draw_scrollbar(clip, content_h, self.assign_scroll)

    def _force_layout(self):
        """Full-width two-column layout for the Force tab (the building grid is
        hidden on this tab, so we use the whole screen width). Returns
        (left_x, right_x, col_w, view_top, view_bottom, view_h)."""
        left_x = self.grid_x
        gap = 90
        total_w = config.SCREEN_WIDTH - left_x - 40
        col_w = (total_w - gap) // 2
        right_x = left_x + col_w + gap
        view_top = self.grid_y + 60          # push lists (and headers) down below the tabs
        view_bottom = self.grid_y + 3 * (self.slot_size + self.gap) - 40
        return left_x, right_x, col_w, view_top, view_bottom, view_bottom - view_top

    def _render_force_panel(self, mouse_pos):
        self.active_rows = []
        self.backup_rows = []
        self.force_action_rects = {}
        left_x, right_x, col_w, view_top, view_bottom, view_h = self._force_layout()
        hdr_y = view_top - 38

        cap = self.state.member_cap()
        n_active = len(self.empire.members)
        over = n_active > cap
        active_hdr_col = config.RED if over else config.WHITE
        self.screen.blit(self.font_h.render(
            f"Active Roster  {n_active}/{cap}", True, active_hdr_col), (left_x, hdr_y))
        self.screen.blit(self.font_h.render(
            f"Backup Force  {len(self.state.backup)}/{config.BACKUP_FORCE_CAP}",
            True, config.WHITE), (right_x, hdr_y))

        # Active column — grouped by class (indices are roster indices).
        active_entries = list(enumerate(self.empire.members))
        ch, self.active_scroll = self._draw_force_column(
            active_entries, left_x, col_w, view_top, view_bottom,
            self.active_scroll, "active")
        self._draw_scrollbar(pygame.Rect(left_x, view_top, col_w, view_h),
                             ch, self.active_scroll)

        # Backup column — grouped by class (indices are backup indices).
        if not self.state.backup:
            self.screen.blit(self.font_small.render(
                "No recruits yet — win wars to recruit.", True, config.GRAY),
                (right_x + 4, view_top + 4))
        else:
            backup_entries = list(enumerate(self.state.backup))
            ch, self.backup_scroll = self._draw_force_column(
                backup_entries, right_x, col_w, view_top, view_bottom,
                self.backup_scroll, "backup")
            self._draw_scrollbar(pygame.Rect(right_x, view_top, col_w, view_h),
                                 ch, self.backup_scroll)

        self._draw_force_actions(mouse_pos, view_bottom + 16, left_x)

        # Detail card for the currently-selected member (either column).
        sel_m = self._force_selected_member()
        if sel_m is not None:
            self._draw_force_detail(sel_m, right_x, view_bottom + 16, col_w)

    def _force_selected_member(self):
        if self.force_sel is None:
            return None
        col, idx = self.force_sel
        if col == "active" and 0 <= idx < len(self.empire.members):
            return self.empire.members[idx]
        if col == "backup" and 0 <= idx < len(self.state.backup):
            return self.state.backup[idx]
        return None

    def _draw_force_detail(self, m, x, y, w):
        """A stat card for the selected member: HP, damage, mitigation, speed."""
        s = m.get_stats()
        h = 132
        card = pygame.Rect(x, y, w, h)
        pygame.draw.rect(self.screen, (30, 32, 46), card, border_radius=8)
        pygame.draw.rect(self.screen, self._rarity_color(m.rarity), card, 2, border_radius=8)

        title = f"{m.name}"
        self.screen.blit(self.font_h.render(title, True, config.WHITE),
                         (x + 14, y + 8))
        sub = f"{self._rarity_label(m.rarity)} {m.member_class.value.title()}  ·  Level {m.level}"
        self.screen.blit(self.font_small.render(sub, True, self._rarity_color(m.rarity)),
                         (x + 14, y + 40))

        # Two columns of stat label/value pairs.
        stats = [
            ("Health", f"{int(s['hp'])}"),
            ("Damage (vs members)", f"{int(s['damage_player'])}"),
            ("Damage (vs buildings)", f"{int(s['damage_building'])}"),
            ("Mitigation", f"{int(s['mitigation'] * 100)}%"),
            ("Attack interval", f"{s['attack_interval']:.1f}s"),
            ("Move speed", f"{int(s['speed'])}"),
        ]
        col_x = [x + 14, x + w // 2 + 10]
        row_y = y + 66
        for i, (label, val) in enumerate(stats):
            cx = col_x[i % 2]
            cyy = row_y + (i // 2) * 22
            lbl = self.font_small.render(label + ":", True, config.LIGHT_GRAY)
            self.screen.blit(lbl, (cx, cyy))
            vv = self.font_small.render(val, True, config.GOLD)
            self.screen.blit(vv, (cx + 190, cyy))

    def _draw_force_column(self, entries, x, col_w, view_top, view_bottom,
                           scroll, col_key):
        """Draw one Force column grouped by class (headers like the Assign tab),
        culling to the viewport. Registers clickable rows into active_rows /
        backup_rows keyed by the entry's original index. Returns (content_h,
        clamped_scroll)."""
        hdr_h, row_h, gap_h = 24, 22, 8
        rows_out = self.active_rows if col_key == "active" else self.backup_rows

        # Lay out in content-space, grouped by class (skip empty classes).
        items = []  # ('header', cls) | ('member', (idx, m)) | ('gap', None)
        for cls in MemberClass:
            cls_entries = [(i, m) for (i, m) in entries if m.member_class == cls]
            if not cls_entries:
                continue
            items.append(("header", cls))
            for e in cls_entries:
                items.append(("member", e))
            items.append(("gap", None))

        content_h = sum(hdr_h if k == "header" else (gap_h if k == "gap" else row_h)
                        for k, _ in items)
        view_h = view_bottom - view_top
        scroll = min(scroll, max(0, content_h - view_h))

        clip = pygame.Rect(x - 4, view_top - 2, col_w + 8, view_h + 4)
        self.screen.set_clip(clip)
        cy = view_top - scroll
        for kind, payload in items:
            if kind == "header":
                if cy + hdr_h > view_top and cy < view_bottom:
                    self.screen.blit(self.font_btn.render(
                        f"— {payload.value.capitalize()} —", True,
                        self._class_color(payload)), (x + 2, cy))
                cy += hdr_h
            elif kind == "gap":
                cy += gap_h
            else:
                idx, m = payload
                if cy + row_h > view_top and cy < view_bottom:
                    rect = pygame.Rect(x, cy, col_w, row_h)
                    if self.force_sel == (col_key, idx):
                        pygame.draw.rect(self.screen, config.GOLD, rect, 2, border_radius=4)
                    self._draw_member_row(m, x, cy, col_w)
                    rows_out.append((rect, idx))
                cy += row_h
        self.screen.set_clip(None)
        return content_h, scroll

    def _draw_force_actions(self, mouse_pos, y, x):
        """Bottom action bar; buttons depend on the current selection."""
        self.force_action_rects = {}
        actions = []
        if self.force_sel is not None:
            col, _ = self.force_sel
            if col == "active":
                actions = [("bench", "Move to Backup ▶", config.GRAY)]
            else:
                actions = [("activate", "◀ Activate", config.GREEN),
                           ("kick", "Kick Out", config.RED)]
        bx = x
        for name, label, color in actions:
            w = self.font_btn.size(label)[0] + 28
            rect = pygame.Rect(bx, y, w, 44)
            hover = rect.collidepoint(mouse_pos)
            c = tuple(min(255, ch + 40) for ch in color) if hover else color
            pygame.draw.rect(self.screen, c, rect, border_radius=8)
            pygame.draw.rect(self.screen, config.WHITE, rect, 2, border_radius=8)
            txt = self.font_btn.render(label, True, config.BLACK)
            self.screen.blit(txt, txt.get_rect(center=rect.center))
            self.force_action_rects[name] = rect
            bx += w + 14
        if self.force_sel is None:
            self.screen.blit(self.font_small.render(
                "Select a member on either side to move them.", True, config.GRAY),
                (x, y + 12))

    def _draw_member_row(self, m, x, y, w):
        """A single-line row (same spirit as the Assign tab): the name + level in
        the class color on the left, and the full rarity word — in its rarity
        color — on the right so rarity stands out."""
        name = self.font_small.render(f"{m.name}   L{m.level}",
                                      True, self._class_color(m.member_class))
        self.screen.blit(name, (x + 6, y + 4))
        rlabel = self._rarity_label(m.rarity)
        rt = self.font_small.render(rlabel, True, self._rarity_color(m.rarity))
        self.screen.blit(rt, rt.get_rect(right=x + w - 16, y=y + 4))

    def _draw_scrollbar(self, view_rect, content_h, scroll):
        if content_h <= view_rect.height:
            return
        track = pygame.Rect(view_rect.right - 8, view_rect.y, 5, view_rect.height)
        pygame.draw.rect(self.screen, (50, 52, 66), track, border_radius=3)
        frac = view_rect.height / content_h
        knob_h = max(24, int(view_rect.height * frac))
        max_scroll = content_h - view_rect.height
        t = (scroll / max_scroll) if max_scroll > 0 else 0
        knob_y = view_rect.y + int((view_rect.height - knob_h) * t)
        pygame.draw.rect(self.screen, config.GRAY,
                         pygame.Rect(track.x, knob_y, 5, knob_h), border_radius=3)

    def _panel_x_left(self):
        return self._panel_x()

    def _rarity_label(self, rarity):
        return {"common": "Common", "uncommon": "Uncommon", "rare": "Rare",
                "super_rare": "Super Rare"}.get(rarity.value, "?")

    def _rarity_short(self, rarity):
        return {"common": "C", "uncommon": "U", "rare": "R",
                "super_rare": "SR"}.get(rarity.value, "?")

    def _rarity_color(self, rarity):
        return {
            "common": config.LIGHT_GRAY,
            "uncommon": (120, 200, 120),
            "rare": (110, 170, 255),
            "super_rare": config.GOLD,
        }.get(rarity.value, config.LIGHT_GRAY)

    def _slot_of(self, member_idx):
        for s, members in enumerate(self.member_assignments):
            if member_idx in members:
                return s
        return None

    def _class_color(self, cls):
        return {
            MemberClass.ENFORCER: config.ENFORCER_COLOR,
            MemberClass.SNIPER: config.SNIPER_COLOR,
            MemberClass.ASSASSIN: config.ASSASSIN_COLOR,
            MemberClass.DEMOLITIONIST: config.DEMO_COLOR,
        }[cls]


# ---------------------------------------------------------------------------
# Map (country -> state -> city) with wage-war popup
# ---------------------------------------------------------------------------
class MapScreen(_Screen):
    """Country -> State -> City map.

    mode="war"       : browse within the unlocked scope and wage war on cities.
    mode="birthplace": full map; pick any city as your starting home.
    """

    def __init__(self, screen, state, mode="war"):
        super().__init__(screen)
        self.state = state
        self.mode = mode
        self.popup_city = None      # city_id awaiting confirmation
        self.item_rects = []        # (rect, value) for current level
        self.back_btn = Button(
            (40, config.SCREEN_HEIGHT - 80, 200, 52), "Back", self.font_btn,
            base_color=config.GRAY)
        self.popup_yes = None
        self.popup_no = None

        # Navigation levels: country -> state -> county -> city.
        # Scope fixes the higher levels and sets the lowest level you can back to.
        fixed_country = fixed_state = fixed_county = None
        if mode == "birthplace":
            self.scope = "world"
            self.min_level = "country"
        else:
            self.scope = state.scope()
            loc = state.home_location()
            hc, hs, hco = (loc[0], loc[1], loc[2]) if loc else (None, None, None)
            if self.scope == "county":
                self.min_level = "city"
                fixed_country, fixed_state, fixed_county = hc, hs, hco
            elif self.scope == "state":
                self.min_level = "county"
                fixed_country, fixed_state = hc, hs
            elif self.scope == "country":
                self.min_level = "state"
                fixed_country = hc
            else:  # world
                self.min_level = "country"

        self.level = self.min_level
        self.sel_country = fixed_country
        self.sel_state = fixed_state
        self.sel_county = fixed_county
        self.page = 0
        self.total_pages = 1
        self.prev_btn = None
        self.next_btn = None
        self.sort_mode = "underworld"   # county-list sort: alpha | underworld | gdp
        self.sort_desc = False          # True = large->small, False = small->large
        self.sort_button_rects = {}
        self.sort_dir_rect = None

    # --- navigation ------------------------------------------------------
    _UP = {"city": "county", "county": "state", "state": "country"}

    def _go_back(self):
        if self.level == self.min_level:
            self.result = "menu"
            self.done = True
            return
        if self.level == "city":
            self.sel_county = None
        elif self.level == "county":
            self.sel_state = None
        elif self.level == "state":
            self.sel_country = None
        self.level = self._UP[self.level]
        self.page = 0

    def handle_key(self, key):
        if key in (pygame.K_q, pygame.K_ESCAPE):
            if self.popup_city is not None:
                self.popup_city = None
            else:
                self._go_back()
        elif key in (pygame.K_LEFT, pygame.K_PAGEUP):
            self.page = max(0, self.page - 1)
        elif key in (pygame.K_RIGHT, pygame.K_PAGEDOWN):
            self.page = min(self.total_pages - 1, self.page + 1)

    def handle_click(self, pos):
        if self.popup_city is not None:
            if self.popup_yes and self.popup_yes.hit(pos):
                kind = "birthplace" if self.mode == "birthplace" else "battle"
                self.result = (kind, self.popup_city)
                self.done = True
            elif self.popup_no and self.popup_no.hit(pos):
                self.popup_city = None
            return

        if self.back_btn.hit(pos):
            self._go_back()
            return
        if self.prev_btn and self.prev_btn.hit(pos):
            self.page = max(0, self.page - 1)
            return
        if self.next_btn and self.next_btn.hit(pos):
            self.page = min(self.total_pages - 1, self.page + 1)
            return

        for mode, rect in self.sort_button_rects.items():
            if rect.collidepoint(pos):
                self.sort_mode = mode
                self.page = 0
                return
        if self.sort_dir_rect and self.sort_dir_rect.collidepoint(pos):
            self.sort_desc = not self.sort_desc
            self.page = 0
            return

        for rect, value in self.item_rects:
            if rect.collidepoint(pos):
                self._select(value)
                return

    def _select(self, value):
        if self.level == "country":
            self.sel_country = value
            self.level = "state"
        elif self.level == "state":
            self.sel_state = value
            self.level = "county"
        elif self.level == "county":
            self.sel_county = value
            self.level = "city"
        elif self.level == "city":
            cid = wm.city_id(self.sel_country, self.sel_state, self.sel_county, value)
            if self.mode == "war" and self.state.is_conquered(cid):
                return  # already ours
            self.popup_city = cid
            return
        self.page = 0

    def _current_items(self):
        if self.level == "country":
            return wm.countries()
        if self.level == "state":
            return wm.states(self.sel_country)
        if self.level == "county":
            return self._sorted_counties()
        return wm.cities(self.sel_country, self.sel_state, self.sel_county)

    def _sorted_counties(self):
        st = wm.WORLD[self.sel_country][self.sel_state]
        names = list(st.keys())
        if self.sort_mode == "alpha":
            key = lambda n: n.lower()
        elif self.sort_mode == "gdp":
            key = lambda n: (st[n].get("gdp_thousands") or 0)
        else:  # combined underworld strength
            key = lambda n: sum(c["underworld_power"] for c in st[n]["cities"].values())
        names.sort(key=key, reverse=self.sort_desc)
        return names

    def _breadcrumb(self):
        root = "Birthplace" if self.mode == "birthplace" else "Map"
        parts = [root]
        for p in (self.sel_country, self.sel_state, self.sel_county):
            if p:
                parts.append(p)
        return "  >  ".join(parts)

    def _region_control_summary(self, conquered):
        """Rolled-up control of the region whose children are being viewed."""
        if self.level == "state":
            o, t, pct = wm.country_control(self.sel_country, conquered)
            return f"{self.sel_country}: {pct * 100:.0f}% controlled ({o}/{t})"
        if self.level == "county":
            o, t, pct = wm.state_control(self.sel_country, self.sel_state, conquered)
            return f"{self.sel_state}: {pct * 100:.0f}% controlled ({o}/{t})"
        if self.level == "city":
            o, t, pct = wm.county_control(self.sel_country, self.sel_state,
                                          self.sel_county, conquered)
            return f"{self.sel_county}: {pct * 100:.0f}% controlled ({o}/{t})"
        return ""

    def _status_banner(self):
        """Explain the current visibility scope in war mode."""
        if self.mode != "war":
            return "Choose the city where your empire begins."
        loc = self.state.home_location()
        if loc is None:
            return ""
        country, state, county, _ = loc
        if self.scope == "county":
            return f"Locked to {county}. Conquer the whole county to expand across {state}."
        if self.scope == "state":
            return f"{state} unlocked. Conquer the whole state to unlock all of {country}."
        if self.scope == "country":
            return f"{country} unlocked. Conquer the whole country to reach the wider world."
        return "All regions unlocked."

    # --- render ----------------------------------------------------------
    def render(self, mouse_pos):
        self.screen.fill((16, 26, 22))
        heading = "Choose Your Birthplace" if self.mode == "birthplace" else "Map"
        title = self.font_title.render(heading, True, config.GOLD)
        self.screen.blit(title, (40, 30))
        crumb = self.font_med.render(self._breadcrumb(), True, config.LIGHT_GRAY)
        self.screen.blit(crumb, (40, 100))
        conquered = self.state.conquered
        summary = self._region_control_summary(conquered)
        if summary:
            self.screen.blit(self.font_med.render(summary, True, config.GREEN),
                             (40 + crumb.get_width() + 30, 100))
        banner = self._status_banner()
        if banner:
            self.screen.blit(self.font_small.render(banner, True, config.GOLD), (40, 128))

        # Sort controls (county level only).
        self.sort_button_rects = {}
        self.sort_dir_rect = None
        top_y = 155
        if self.level == "county":
            self.screen.blit(self.font_small.render("Sort by:", True, config.LIGHT_GRAY),
                             (60, 152))
            sx = 140
            for mode, label in (("alpha", "A-Z"), ("underworld", "Underworld"), ("gdp", "GDP")):
                rect = pygame.Rect(sx, 146, 150, 34)
                active = self.sort_mode == mode
                pygame.draw.rect(self.screen, config.GOLD if active else config.GRAY,
                                 rect, 0 if active else 2, border_radius=6)
                lbl = self.font_small.render(label, True,
                                             config.BLACK if active else config.WHITE)
                self.screen.blit(lbl, lbl.get_rect(center=rect.center))
                self.sort_button_rects[mode] = rect
                sx += 160
            # Direction toggle.
            self.sort_dir_rect = pygame.Rect(sx + 20, 146, 190, 34)
            pygame.draw.rect(self.screen, (60, 70, 90), self.sort_dir_rect, border_radius=6)
            pygame.draw.rect(self.screen, config.GRAY, self.sort_dir_rect, 2, border_radius=6)
            dir_label = "Large \u2192 Small" if self.sort_desc else "Small \u2192 Large"
            dl = self.font_small.render(dir_label, True, config.WHITE)
            self.screen.blit(dl, dl.get_rect(center=self.sort_dir_rect.center))
            top_y = 194

        self.item_rects = []
        items = self._current_items()
        w, h, gap = 420, 76, 12
        col_x = [60, 60 + w + 40, 60 + 2 * (w + 40)]
        per_col = max(1, (config.SCREEN_HEIGHT - top_y - 110) // (h + gap))
        ipp = per_col * len(col_x)
        self.total_pages = max(1, (len(items) + ipp - 1) // ipp)
        self.page = min(self.page, self.total_pages - 1)
        page_items = items[self.page * ipp:(self.page + 1) * ipp]

        for i, value in enumerate(page_items):
            col = i // per_col
            rowi = i % per_col
            rect = pygame.Rect(col_x[col], top_y + rowi * (h + gap), w, h)
            hover = rect.collidepoint(mouse_pos)

            owned = False
            info1 = info2 = None
            if self.level == "city":
                cid = wm.city_id(self.sel_country, self.sel_state, self.sel_county, value)
                owned = self.state.is_conquered(cid)
                city = wm.get_city(cid)
                if city:
                    pop = city["population"]
                    gdp_pc = int(city["gdp_thousands"] * 1000 / pop) if pop else 0
                    info1 = f"Pop {pop:,}    ${gdp_pc:,}/capita    crime {city['crime_rate']}"
                    info2 = f"Gang {city['underworld_power']:,}    Police {city['police_power']:,}"
                    if self.mode == "war":
                        info2 += f"    Reward ${city['reward']:,}"
            else:
                if self.level == "country":
                    o, t, pct = wm.country_control(value, conquered)
                elif self.level == "state":
                    o, t, pct = wm.state_control(self.sel_country, value, conquered)
                else:
                    o, t, pct = wm.county_control(self.sel_country, self.sel_state, value, conquered)
                owned = t > 0 and o == t
                info1 = f"{o}/{t} cities    {pct * 100:.0f}% controlled"

            bg = (40, 80, 48) if owned else ((50, 70, 60) if hover else (34, 50, 44))
            pygame.draw.rect(self.screen, bg, rect, border_radius=8)
            pygame.draw.rect(self.screen, config.GRAY, rect, 2, border_radius=8)

            label = value + ("   \u2713 owned" if owned else "")
            txt = self.font_btn.render(label, True, config.WHITE)
            if info1 is not None:
                self.screen.blit(txt, (rect.x + 14, rect.y + 6))
                self.screen.blit(self.font_small.render(info1, True, config.LIGHT_GRAY),
                                 (rect.x + 14, rect.y + 34))
                if info2 is not None:
                    self.screen.blit(self.font_small.render(info2, True, config.GOLD),
                                     (rect.x + 14, rect.y + 54))
            else:
                self.screen.blit(txt, txt.get_rect(midleft=(rect.x + 14, rect.centery)))
            self.item_rects.append((rect, value))

        # Pagination controls.
        self.prev_btn = self.next_btn = None
        if self.total_pages > 1:
            by = config.SCREEN_HEIGHT - 80
            self.prev_btn = Button((config.SCREEN_WIDTH - 540, by, 150, 52), "< Prev",
                                   self.font_btn, enabled=self.page > 0, base_color=config.GRAY)
            self.next_btn = Button((config.SCREEN_WIDTH - 200, by, 150, 52), "Next >",
                                   self.font_btn, enabled=self.page < self.total_pages - 1,
                                   base_color=config.GRAY)
            self.prev_btn.draw(self.screen, mouse_pos)
            self.next_btn.draw(self.screen, mouse_pos)
            pind = self.font_med.render(f"Page {self.page + 1}/{self.total_pages}",
                                        True, config.LIGHT_GRAY)
            self.screen.blit(pind, pind.get_rect(center=(config.SCREEN_WIDTH - 295, by + 26)))

        self.back_btn.draw(self.screen, mouse_pos)
        if self.level == "city":
            hint_txt = ("Click a city to settle there." if self.mode == "birthplace"
                        else "Click a city to wage war.")
        else:
            hint_txt = "Click to drill down."
        extra = "    \u2190/\u2192 page" if self.total_pages > 1 else ""
        self.screen.blit(self.font_small.render(hint_txt + "   Q/ESC: back" + extra, True, config.GRAY),
                         (60, config.SCREEN_HEIGHT - 100))

        if self.popup_city is not None:
            self._render_popup(mouse_pos)

    def _render_popup(self, mouse_pos):
        overlay = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        self.screen.blit(overlay, (0, 0))

        pw, ph = 620, 340
        px = config.SCREEN_WIDTH // 2 - pw // 2
        py = config.SCREEN_HEIGHT // 2 - ph // 2
        panel = pygame.Rect(px, py, pw, ph)
        pygame.draw.rect(self.screen, (30, 32, 44), panel, border_radius=12)
        pygame.draw.rect(self.screen, config.GOLD, panel, 3, border_radius=12)

        _, _, _, city_name = wm.split_city_id(self.popup_city)
        city = wm.get_city(self.popup_city)
        if self.mode == "birthplace":
            line1 = "Rise as a new force in"
            yes_label = "Challenge the Gang"
        else:
            line1 = "Wage war on"
            yes_label = "Wage War"
        q1 = self.font_h.render(line1, True, config.WHITE)
        q2 = self.font_h.render(f"{city_name}?", True, config.GOLD)
        self.screen.blit(q1, q1.get_rect(centerx=panel.centerx, y=py + 24))
        self.screen.blit(q2, q2.get_rect(centerx=panel.centerx, y=py + 60))

        # Region stats so the player knows what they're committing to.
        if city:
            pop = city["population"]
            gdp_pc = int(city["gdp_thousands"] * 1000 / pop) if pop else 0
            stats = [
                f"Population {pop:,}      GDP/capita ${gdp_pc:,}      Crime {city['crime_rate']}/100k",
                f"Gang power (underworld): {city['underworld_power']:,}",
                f"Police power (raid boss): {city['police_power']:,}",
            ]
            if self.mode == "war":
                stats.append(f"Reward on victory: ${city['reward']:,}")
            sy = py + 108
            for i, s in enumerate(stats):
                col = config.GOLD if i == 1 else config.LIGHT_GRAY
                self.screen.blit(self.font_small.render(s, True, col),
                                 (panel.x + 40, sy))
                sy += 24
        if self.mode == "birthplace":
            warn = self.font_small.render(
                "Lose and your path ends here — you start over.", True, config.RED)
            self.screen.blit(warn, warn.get_rect(centerx=panel.centerx, y=py + ph - 116))

        bw, bh = 220, 56
        self.popup_yes = Button((panel.centerx - bw - 20, py + ph - 76, bw, bh),
                                yes_label, self.font_btn, base_color=config.RED)
        self.popup_no = Button((panel.centerx + 20, py + ph - 76, bw, bh),
                               "Cancel", self.font_btn, base_color=config.GRAY)
        self.popup_yes.draw(self.screen, mouse_pos)
        self.popup_no.draw(self.screen, mouse_pos)


class GameOverScreen(_Screen):
    """Shown when the player loses their birthplace challenge (no territory)."""

    def __init__(self, screen, city_id):
        super().__init__(screen)
        _, state, _, city = wm.split_city_id(city_id)
        self.city = city
        self.state_name = state
        self.btn = Button(
            (config.SCREEN_WIDTH // 2 - 160, config.SCREEN_HEIGHT // 2 + 60, 320, 60),
            "Try Again", self.font_btn, base_color=config.RED)

    def handle_key(self, key):
        if key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE, pygame.K_q):
            self.done = True

    def handle_click(self, pos):
        if self.btn.hit(pos):
            self.done = True

    def render(self, mouse_pos):
        self.screen.fill((10, 8, 10))
        t = self.font_title.render("Your empire dies before it begins.", True, config.RED)
        self.screen.blit(t, t.get_rect(centerx=config.SCREEN_WIDTH // 2,
                                       y=config.SCREEN_HEIGHT // 2 - 120))
        msg = self.font_h.render(
            f"Your path to Godfather ends in {self.city}, {self.state_name}.",
            True, config.LIGHT_GRAY)
        self.screen.blit(msg, msg.get_rect(centerx=config.SCREEN_WIDTH // 2,
                                           y=config.SCREEN_HEIGHT // 2 - 40))
        self.btn.draw(self.screen, mouse_pos)


class VictoryScreen(_Screen):
    """Shown after winning the birthplace challenge — you now control the city.
    No retry here (the fight is already won); only Continue."""

    def __init__(self, screen, city_id):
        super().__init__(screen)
        _, state, _, city = wm.split_city_id(city_id)
        self.city = city
        self.state_name = state
        self.btn = Button(
            (config.SCREEN_WIDTH // 2 - 160, config.SCREEN_HEIGHT // 2 + 60, 320, 60),
            "Continue", self.font_btn, base_color=config.GREEN)

    def handle_key(self, key):
        if key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE, pygame.K_q):
            self.done = True

    def handle_click(self, pos):
        if self.btn.hit(pos):
            self.done = True

    def render(self, mouse_pos):
        self.screen.fill((12, 20, 14))
        t = self.font_title.render("Congratulations!", True, config.GOLD)
        self.screen.blit(t, t.get_rect(centerx=config.SCREEN_WIDTH // 2,
                                       y=config.SCREEN_HEIGHT // 2 - 120))
        msg = self.font_h.render(
            f"You are now in control of {self.city}, {self.state_name}.",
            True, config.GREEN)
        self.screen.blit(msg, msg.get_rect(centerx=config.SCREEN_WIDTH // 2,
                                           y=config.SCREEN_HEIGHT // 2 - 40))
        self.btn.draw(self.screen, mouse_pos)


class RecruitPopup(_Screen):
    """Shown after winning a war: reveals the recruit acquired from the
    defeated empire and confirms they've joined the Backup Force."""

    def __init__(self, screen, member, backup_full=False):
        super().__init__(screen)
        self.member = member
        self.backup_full = backup_full
        self.btn = Button(
            (config.SCREEN_WIDTH // 2 - 160, config.SCREEN_HEIGHT // 2 + 110, 320, 60),
            "Continue", self.font_btn, base_color=config.GREEN)

    def handle_key(self, key):
        if key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE, pygame.K_q):
            self.done = True

    def handle_click(self, pos):
        if self.btn.hit(pos):
            self.done = True

    def _rarity_color(self, rarity):
        return {
            "common": config.LIGHT_GRAY,
            "uncommon": (120, 200, 120),
            "rare": (110, 170, 255),
            "super_rare": config.GOLD,
        }.get(rarity.value, config.LIGHT_GRAY)

    def render(self, mouse_pos):
        self.screen.fill((14, 16, 26))
        cx = config.SCREEN_WIDTH // 2
        cy = config.SCREEN_HEIGHT // 2

        t = self.font_title.render("New Recruit!", True, config.GOLD)
        self.screen.blit(t, t.get_rect(centerx=cx, y=cy - 200))

        m = self.member
        rc = self._rarity_color(m.rarity)
        name = self.font_h.render(m.name, True, config.WHITE)
        self.screen.blit(name, name.get_rect(centerx=cx, y=cy - 110))
        rarity_name = m.rarity.value.replace("_", " ").title()
        detail = self.font_med.render(
            f"{rarity_name} {m.member_class.value.title()}   ·   Level {m.level}",
            True, rc)
        self.screen.blit(detail, detail.get_rect(centerx=cx, y=cy - 66))

        if self.backup_full:
            msg = self.font_med.render(
                f"Backup Force is full (max {config.BACKUP_FORCE_CAP}) — recruit not kept.",
                True, config.RED)
        else:
            msg = self.font_med.render(
                "Joined your Backup Force. Move them into the roster in EVE Layout ▸ Force.",
                True, config.LIGHT_GRAY)
        self.screen.blit(msg, msg.get_rect(centerx=cx, y=cy - 10))

        self.btn.draw(self.screen, mouse_pos)


class CapBlockedPopup(_Screen):
    """Blocks starting a war while the active roster exceeds the HQ cap."""

    def __init__(self, screen, roster_size, cap):
        super().__init__(screen)
        self.roster_size = roster_size
        self.cap = cap
        self.btn = Button(
            (config.SCREEN_WIDTH // 2 - 160, config.SCREEN_HEIGHT // 2 + 80, 320, 60),
            "OK", self.font_btn, base_color=config.GRAY)

    def handle_key(self, key):
        if key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE, pygame.K_q):
            self.done = True

    def handle_click(self, pos):
        if self.btn.hit(pos):
            self.done = True

    def render(self, mouse_pos):
        self.screen.fill((22, 12, 12))
        cx = config.SCREEN_WIDTH // 2
        cy = config.SCREEN_HEIGHT // 2
        t = self.font_title.render("Roster over HQ cap", True, config.RED)
        self.screen.blit(t, t.get_rect(centerx=cx, y=cy - 140))
        lines = [
            f"Your active roster is {self.roster_size}, but your HQ only supports {self.cap}.",
            "Open EVE Layout ▸ Force and move members to the Backup Force",
            "(or level up your HQ) before you can start a war.",
        ]
        y = cy - 60
        for ln in lines:
            s = self.font_med.render(ln, True, config.LIGHT_GRAY)
            self.screen.blit(s, s.get_rect(centerx=cx, y=y))
            y += 34
        self.btn.draw(self.screen, mouse_pos)

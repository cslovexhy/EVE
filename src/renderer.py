"""EVE - Renderer: Pygame display of battlefield, buildings, members, HUD."""

import os
import pygame
from models import Empire, Member, Building, MemberClass, MemberState, Rarity
from engine import BattleEngine
from orders import OrderSystem, CLASS_BUTTONS
import config

# Portrait and icon directories
PORTRAIT_DIR = os.path.join(os.path.dirname(__file__), "..", "assets", "portraits")
ICON_DIR = os.path.join(os.path.dirname(__file__), "..", "assets", "icons")

# Mini card dimensions
CARD_WIDTH = 24
CARD_HEIGHT = 30
CARD_BORDER = 2


class Renderer:
    """Handles all Pygame rendering."""
    
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.font_large = pygame.font.Font(None, 42)
        self.font_medium = pygame.font.Font(None, 28)
        self.font_small = pygame.font.Font(None, 20)
        self.font_tiny = pygame.font.Font(None, 16)
        self.font_btn = pygame.font.Font(None, 28)
        
        # Class colors mapping
        self.class_colors = {
            MemberClass.ENFORCER: config.ENFORCER_COLOR,
            MemberClass.SNIPER: config.SNIPER_COLOR,
            MemberClass.ASSASSIN: config.ASSASSIN_COLOR,
            MemberClass.DEMOLITIONIST: config.DEMO_COLOR,
        }
        
        # Class short labels
        self.class_labels = {
            MemberClass.ENFORCER: "E",
            MemberClass.SNIPER: "S",
            MemberClass.ASSASSIN: "A",
            MemberClass.DEMOLITIONIST: "D",
        }
        
        # Load portrait images (scaled to card size)
        self.portraits = {}
        self._load_portraits()
        
        # Load class icons
        self.class_icons = {}
        self._load_class_icons()
    
    def _load_portraits(self):
        """Load portraits, crop to face area (top portion), and scale to card size."""
        portrait_w = CARD_WIDTH - CARD_BORDER * 2
        portrait_h = CARD_HEIGHT - CARD_BORDER * 2 - 8  # Leave room for level bar
        
        if not os.path.isdir(PORTRAIT_DIR):
            return
        
        for filename in os.listdir(PORTRAIT_DIR):
            if filename.endswith(".png"):
                name = filename[:-4]  # Strip .png
                path = os.path.join(PORTRAIT_DIR, filename)
                try:
                    img = pygame.image.load(path).convert_alpha()
                    w, h = img.get_width(), img.get_height()
                    
                    # Crop to face area: top 45% of image, centered horizontally
                    # Most UE portraits have the face in the upper portion
                    crop_h = int(h * 0.45)
                    crop_w = int(w * 0.7)  # Slightly narrower to focus on face
                    crop_x = (w - crop_w) // 2
                    crop_y = int(h * 0.05)  # Start slightly below top edge
                    
                    face_rect = pygame.Rect(crop_x, crop_y, crop_w, crop_h)
                    face_img = img.subsurface(face_rect).copy()
                    
                    # Scale to card portrait area
                    face_img = pygame.transform.smoothscale(face_img, (portrait_w, portrait_h))
                    self.portraits[name] = face_img
                except (pygame.error, FileNotFoundError, ValueError):
                    pass
    
    def _load_class_icons(self):
        """Load class icon images scaled to member icon size."""
        icon_size = (config.MEMBER_ICON_SIZE, config.MEMBER_ICON_SIZE)
        
        if not os.path.isdir(ICON_DIR):
            return
        
        for cls in MemberClass:
            path = os.path.join(ICON_DIR, f"{cls.value}.png")
            try:
                img = pygame.image.load(path).convert_alpha()
                img = pygame.transform.smoothscale(img, icon_size)
                self.class_icons[cls] = img
            except (pygame.error, FileNotFoundError):
                pass
    
    def render(self, engine: BattleEngine, order_system: OrderSystem):
        """Render the full battle scene."""
        self.screen.fill(config.BLACK)
        
        # Draw battlefield background
        self._draw_battlefield_bg()
        
        # Draw buildings (with hover highlights)
        self._draw_buildings(engine.player, is_player=True, order_system=order_system)
        self._draw_buildings(engine.enemy, is_player=False, engine=engine, order_system=order_system)
        
        # Draw members as mini cards
        self._draw_members(engine.player.members, is_player=True)
        self._draw_members(engine.enemy.members, is_player=False, engine=engine)
        
        # Draw sniper range circles for defending player snipers
        self._draw_sniper_ranges(engine.player.members)
        
        # Draw HUD (top)
        self._draw_hud(engine)
        
        # Draw class stats (left side)
        self._draw_class_stats(engine)
        
        # Draw class buttons
        self._draw_class_buttons(order_system)
        
        # Draw order prompt
        self._draw_order_prompt(order_system.get_prompt())
        
        # Draw battle over screen
        if engine.battle_over:
            self._draw_battle_over(engine)
    
    def _draw_battlefield_bg(self):
        """Draw the battlefield background area."""
        rect = pygame.Rect(config.BATTLEFIELD_X, config.BATTLEFIELD_Y,
                          config.BATTLEFIELD_WIDTH, config.BATTLEFIELD_HEIGHT)
        pygame.draw.rect(self.screen, (20, 20, 30), rect)
    
    def _draw_buildings(self, empire: Empire, is_player: bool,
                       engine: BattleEngine = None, order_system: OrderSystem = None):
        """Draw buildings as rectangles with HP bars."""
        for building in empire.buildings:
            x, y = int(building.x), int(building.y)
            size = config.BUILDING_SIZE
            
            # Fog of war for enemy buildings
            if not is_player and engine:
                visible = engine.is_visible_to_player(building.index)
            else:
                visible = True
            
            # Check if this building is hovered
            is_hovered = False
            if order_system and order_system.hovered_building:
                side, idx = order_system.hovered_building
                if idx == building.index:
                    if (side == "player" and is_player) or (side == "enemy" and not is_player):
                        is_hovered = True
            
            # Building rect
            if building.destroyed:
                color = config.DARK_GRAY
            elif is_player:
                color = (40, 80, 40)
            else:
                color = (80, 40, 40) if visible else (40, 40, 40)
            
            rect = pygame.Rect(x - size // 2, y - size // 2, size, size)
            pygame.draw.rect(self.screen, color, rect)
            
            # Hover highlight
            if is_hovered and not building.destroyed:
                highlight_color = config.GREEN if is_player else config.RED
                pygame.draw.rect(self.screen, highlight_color, rect, 3)
            else:
                pygame.draw.rect(self.screen, config.GRAY, rect, 1)
            
            # Building number
            num_text = self.font_small.render(str(building.index + 1), True, config.WHITE)
            self.screen.blit(num_text, (x - 4, y - 6))
            
            # HP bar
            if visible and not building.destroyed:
                hp_pct = building.hp / building.max_hp
                bar_width = size
                bar_height = 4
                bar_x = x - size // 2
                bar_y = y + size // 2 + 2
                
                pygame.draw.rect(self.screen, config.DARK_GRAY,
                               (bar_x, bar_y, bar_width, bar_height))
                bar_color = config.GREEN if hp_pct > 0.5 else config.GOLD if hp_pct > 0.25 else config.RED
                pygame.draw.rect(self.screen, bar_color,
                               (bar_x, bar_y, int(bar_width * hp_pct), bar_height))
            
            # Defender count bubble (top-right of building)
            if visible and not building.destroyed:
                defender_count = len([m for m in empire.members
                                     if m.is_alive and m.assigned_building == building.index])
                if defender_count > 0:
                    bubble_x = x + size // 2 - 2
                    bubble_y = y - size // 2 - 2
                    bubble_r = 8
                    pygame.draw.circle(self.screen, (50, 50, 50), (bubble_x, bubble_y), bubble_r)
                    pygame.draw.circle(self.screen, config.WHITE, (bubble_x, bubble_y), bubble_r, 1)
                    count_text = self.font_tiny.render(str(defender_count), True, config.WHITE)
                    count_rect = count_text.get_rect(center=(bubble_x, bubble_y))
                    self.screen.blit(count_text, count_rect)
            
            # Fog overlay
            if not is_player and not visible and not building.destroyed:
                fog = pygame.Surface((size, size), pygame.SRCALPHA)
                fog.fill((0, 0, 0, 150))
                self.screen.blit(fog, (x - size // 2, y - size // 2))
                q_text = self.font_medium.render("?", True, config.GRAY)
                self.screen.blit(q_text, (x - 4, y - 8))
    
    def _draw_members(self, members: list, is_player: bool, engine: BattleEngine = None):
        """Draw members as mini cards with class icon, rarity border, and level."""
        for member in members:
            if not member.is_alive:
                continue
            
            # Visibility check for enemy members
            if not is_player and engine:
                # Stealthed enemies are completely invisible
                if member.stealthed:
                    continue
                if member.state in (MemberState.DEFENDING, MemberState.IDLE):
                    if member.assigned_building is not None:
                        if not engine.is_visible_to_player(member.assigned_building):
                            continue
            
            x, y = int(member.x), int(member.y)
            
            # Player's own stealthed members drawn semi-transparent
            if is_player and member.stealthed:
                # Draw to a temp surface with alpha
                self._draw_member_card_alpha(member, x, y, alpha=100)
            else:
                self._draw_member_card(member, x, y)
    
    def _draw_sniper_ranges(self, members: list):
        """Draw subtle range circles around defending player snipers."""
        for member in members:
            if (member.is_alive and 
                member.member_class == MemberClass.SNIPER and
                member.state in (MemberState.DEFENDING, MemberState.IDLE)):
                
                x, y = int(member.x), int(member.y)
                # Draw just the circle outline, very subtle
                range_surface = pygame.Surface(
                    (config.SNIPER_RANGE * 2 + 2, config.SNIPER_RANGE * 2 + 2), pygame.SRCALPHA)
                pygame.draw.circle(
                    range_surface, (34, 139, 34, 35),
                    (config.SNIPER_RANGE + 1, config.SNIPER_RANGE + 1),
                    config.SNIPER_RANGE, 1)
                self.screen.blit(range_surface, 
                               (x - config.SNIPER_RANGE - 1, y - config.SNIPER_RANGE - 1))
    
    def _draw_member_card(self, member: Member, cx: int, cy: int):
        """Draw a single member as their class icon with rarity border and level."""
        icon_size = config.MEMBER_ICON_SIZE
        card_size = icon_size + CARD_BORDER * 2
        
        card_x = cx - card_size // 2
        card_y = cy - card_size // 2
        card_rect = pygame.Rect(card_x, card_y, card_size, card_size)
        
        # Rarity border color
        rarity_color = config.RARITY_COLORS[member.rarity.value]
        
        # State-based glow
        if member.state == MemberState.ATTACKING:
            glow_rect = pygame.Rect(card_x - 1, card_y - 1, card_size + 2, card_size + 2)
            pygame.draw.rect(self.screen, config.RED, glow_rect, 1)
        elif member.state == MemberState.MOVING:
            glow_rect = pygame.Rect(card_x - 1, card_y - 1, card_size + 2, card_size + 2)
            pygame.draw.rect(self.screen, config.GOLD, glow_rect, 1)
        
        # Draw background
        pygame.draw.rect(self.screen, (30, 30, 30), card_rect)
        
        # Draw rarity-colored border
        pygame.draw.rect(self.screen, rarity_color, card_rect, CARD_BORDER)
        
        # Draw class icon (centered in card)
        if member.member_class in self.class_icons:
            icon = self.class_icons[member.member_class]
            self.screen.blit(icon, (card_x + CARD_BORDER, card_y + CARD_BORDER))
        else:
            # Fallback: colored square with class letter
            class_color = self.class_colors[member.member_class]
            inner = pygame.Rect(card_x + CARD_BORDER, card_y + CARD_BORDER, icon_size, icon_size)
            pygame.draw.rect(self.screen, class_color, inner)
            label = self.font_tiny.render(
                self.class_labels[member.member_class], True, config.WHITE)
            label_rect = label.get_rect(center=inner.center)
            self.screen.blit(label, label_rect)
        
        # Draw level number (below icon)
        level_text = self.font_tiny.render(str(member.level), True, config.WHITE)
        level_rect = level_text.get_rect(centerx=cx, top=card_y + card_size + 1)
        self.screen.blit(level_text, level_rect)
        
        # HP bar (below level, only if damaged)
        if member.hp < member.max_hp:
            hp_pct = member.hp / member.max_hp
            bar_w = card_size
            bar_h = 3
            bar_x = card_x
            bar_y = card_y + card_size + 11
            pygame.draw.rect(self.screen, config.DARK_GRAY,
                           (bar_x, bar_y, bar_w, bar_h))
            bar_color = config.GREEN if hp_pct > 0.5 else config.RED
            pygame.draw.rect(self.screen, bar_color,
                           (bar_x, bar_y, int(bar_w * hp_pct), bar_h))
    
    def _draw_member_card_alpha(self, member: Member, cx: int, cy: int, alpha: int = 100):
        """Draw a member card with transparency (for stealthed own units)."""
        icon_size = config.MEMBER_ICON_SIZE
        card_size = icon_size + CARD_BORDER * 2
        # Render to a temp surface with per-surface alpha
        temp = pygame.Surface((card_size + 4, card_size + 20), pygame.SRCALPHA)
        # Offset drawing to temp surface
        offset_x = 2
        offset_y = 2
        
        card_rect = pygame.Rect(offset_x, offset_y, card_size, card_size)
        rarity_color = config.RARITY_COLORS[member.rarity.value]
        
        pygame.draw.rect(temp, (30, 30, 30, alpha), card_rect)
        pygame.draw.rect(temp, (*rarity_color, alpha), card_rect, CARD_BORDER)
        
        if member.member_class in self.class_icons:
            icon = self.class_icons[member.member_class]
            scaled = pygame.transform.smoothscale(icon, (icon_size, icon_size))
            scaled.set_alpha(alpha)
            temp.blit(scaled, (offset_x + CARD_BORDER, offset_y + CARD_BORDER))
        
        # Blit temp surface centered on position
        blit_x = cx - (card_size + 4) // 2
        blit_y = cy - (card_size + 4) // 2
        self.screen.blit(temp, (blit_x, blit_y))
    
    def _draw_class_stats(self, engine: BattleEngine):
        """Draw class member count stats in the stats bar area."""
        # Background
        stats_rect = pygame.Rect(0, config.STATS_Y, config.SCREEN_WIDTH, config.STATS_HEIGHT)
        pygame.draw.rect(self.screen, (12, 12, 18), stats_rect)
        
        # Player stats (left side, horizontal)
        x = 15
        y = config.STATS_Y + 5
        
        player_label = self.font_small.render("YOUR FORCES", True, config.GREEN)
        self.screen.blit(player_label, (x, y))
        y += 16
        
        for cls in MemberClass:
            alive = len([m for m in engine.player.members 
                        if m.member_class == cls and m.is_alive])
            total = len([m for m in engine.player.members 
                        if m.member_class == cls])
            
            color = self.class_colors[cls]
            label = cls.value.title()[:3]
            
            pygame.draw.circle(self.screen, color, (x + 6, y + 6), 5)
            text = self.font_small.render(f"{label}: {alive}/{total}", True, color)
            self.screen.blit(text, (x + 15, y))
            y += 16
        
        # Enemy stats (right side, horizontal)
        x_end = config.SCREEN_WIDTH - 15
        y = config.STATS_Y + 5
        
        enemy_label = self.font_small.render("ENEMY FORCES", True, config.RED)
        enemy_label_rect = enemy_label.get_rect(right=x_end, y=y)
        self.screen.blit(enemy_label, enemy_label_rect)
        y += 16
        
        for cls in MemberClass:
            alive = len([m for m in engine.enemy.members 
                        if m.member_class == cls and m.is_alive])
            total = len([m for m in engine.enemy.members 
                        if m.member_class == cls])
            
            color = self.class_colors[cls]
            label = cls.value.title()[:3]
            
            text = self.font_small.render(f"{alive}/{total} :{label}", True, color)
            text_rect = text.get_rect(right=x_end - 15, y=y)
            self.screen.blit(text, text_rect)
            pygame.draw.circle(self.screen, color, (x_end - 6, y + 6), 5)
            y += 16
    
    def _draw_class_buttons(self, order_system: OrderSystem):
        """Draw the class selection buttons."""
        for btn in CLASS_BUTTONS:
            if btn.selected:
                bg_color = btn.color
                text_color = config.BLACK
            elif btn.hovered:
                r, g, b = btn.color
                bg_color = (min(255, r + 40), min(255, g + 40), min(255, b + 40))
                text_color = config.BLACK
            else:
                bg_color = config.DARK_GRAY
                text_color = btn.color
            
            pygame.draw.rect(self.screen, bg_color, btn.rect, border_radius=6)
            pygame.draw.rect(self.screen, btn.color, btn.rect, 2, border_radius=6)
            
            label = self.font_btn.render(btn.label, True, text_color)
            label_rect = label.get_rect(center=btn.rect.center)
            self.screen.blit(label, label_rect)
    
    def _draw_hud(self, engine: BattleEngine):
        """Draw top HUD bar with timer, scores, building counts."""
        # Background bar
        bar_rect = pygame.Rect(0, 0, config.SCREEN_WIDTH, config.HUD_HEIGHT)
        pygame.draw.rect(self.screen, (15, 15, 20), bar_rect)
        pygame.draw.line(self.screen, config.DARK_GRAY, (0, config.HUD_HEIGHT), (config.SCREEN_WIDTH, config.HUD_HEIGHT))
        
        # Timer (center)
        remaining = max(0, config.BATTLE_DURATION - engine.battle_time)
        minutes = int(remaining) // 60
        seconds = int(remaining) % 60
        timer_text = self.font_large.render(f"{minutes}:{seconds:02d}", True, config.WHITE)
        timer_rect = timer_text.get_rect(centerx=config.SCREEN_WIDTH // 2, centery=config.HUD_HEIGHT // 2)
        self.screen.blit(timer_text, timer_rect)
        
        # Player score + buildings (left)
        p_score = self.font_medium.render(
            f"You: {engine.player.points} pts  |  Buildings: {9 - engine.player.buildings_destroyed}/9",
            True, config.GREEN)
        self.screen.blit(p_score, (15, config.HUD_HEIGHT // 2 - 8))
        
        # Enemy score + buildings (right)
        e_score = self.font_medium.render(
            f"Buildings: {9 - engine.enemy.buildings_destroyed}/9  |  Enemy: {engine.enemy.points} pts",
            True, config.RED)
        e_rect = e_score.get_rect(right=config.SCREEN_WIDTH - 15, centery=config.HUD_HEIGHT // 2)
        self.screen.blit(e_score, e_rect)
    
    def _draw_order_prompt(self, prompt: str):
        """Draw the order prompt above the buttons."""
        y = config.SCREEN_HEIGHT - 120
        prompt_text = self.font_medium.render(prompt, True, config.LIGHT_GRAY)
        prompt_rect = prompt_text.get_rect(centerx=config.SCREEN_WIDTH // 2, y=y)
        self.screen.blit(prompt_text, prompt_rect)
        
        # ESC hint (right of buttons, same vertical level)
        esc_text = self.font_small.render("[ESC] Quit", True, config.GRAY)
        esc_rect = esc_text.get_rect(right=config.SCREEN_WIDTH - 30, centery=config.SCREEN_HEIGHT - 65)
        self.screen.blit(esc_text, esc_rect)
    
    def _draw_battle_over(self, engine: BattleEngine):
        """Draw battle over overlay."""
        overlay = pygame.Surface((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))
        
        if engine.winner == engine.player:
            text = "VICTORY!"
            color = config.GREEN
        else:
            text = "DEFEAT"
            color = config.RED
        
        win_text = self.font_large.render(text, True, color)
        win_rect = win_text.get_rect(center=(config.SCREEN_WIDTH // 2,
                                             config.SCREEN_HEIGHT // 2 - 40))
        self.screen.blit(win_text, win_rect)
        
        score_text = self.font_medium.render(
            f"Final Score — You: {engine.player.points}  vs  Enemy: {engine.enemy.points}",
            True, config.WHITE)
        score_rect = score_text.get_rect(center=(config.SCREEN_WIDTH // 2,
                                                 config.SCREEN_HEIGHT // 2 + 10))
        self.screen.blit(score_text, score_rect)
        
        hint_text = self.font_medium.render("Press R to restart or Q to quit", True, config.GRAY)
        hint_rect = hint_text.get_rect(center=(config.SCREEN_WIDTH // 2,
                                               config.SCREEN_HEIGHT // 2 + 50))
        self.screen.blit(hint_text, hint_rect)

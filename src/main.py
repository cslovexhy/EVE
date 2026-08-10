"""EVE - Empire vs Empire: Main game loop."""

import sys
import pygame

import config
from models import MemberClass, OrderAction, create_starting_roster
from engine import BattleEngine
from orders import OrderSystem
from ai import BattleAI
from renderer import Renderer


class Game:
    """Main game class — manages the game loop and ties systems together."""
    
    def __init__(self):
        pygame.init()
        
        # Get display size for fullscreen
        display_info = pygame.display.Info()
        config.SCREEN_WIDTH = display_info.current_w
        config.SCREEN_HEIGHT = display_info.current_h
        
        self.screen = pygame.display.set_mode(
            (config.SCREEN_WIDTH, config.SCREEN_HEIGHT),
            pygame.FULLSCREEN
        )
        pygame.display.set_caption(config.TITLE)
        self.clock = pygame.time.Clock()
        self.running = True
        
        # Recalculate layout based on actual screen size
        config.BATTLEFIELD_WIDTH = config.SCREEN_WIDTH - 80
        config.BATTLEFIELD_HEIGHT = config.SCREEN_HEIGHT - config.BATTLEFIELD_Y - config.ORDER_PANEL_HEIGHT
        
        self._start_battle()
    
    def _start_battle(self):
        """Initialize a new battle."""
        self.player_empire = create_starting_roster("Your Empire", is_player=True)
        self.enemy_empire = create_starting_roster("Enemy Empire", is_player=False)
        
        self.engine = BattleEngine(self.player_empire, self.enemy_empire)
        self.order_system = OrderSystem()
        self.ai = BattleAI(self.enemy_empire, self.player_empire)
        self.renderer = Renderer(self.screen)
    
    def run(self):
        """Main game loop."""
        while self.running:
            dt = self.clock.tick(config.FPS) / 1000.0
            
            self._handle_events()
            self._update(dt)
            self._render()
            
            pygame.display.flip()
        
        pygame.quit()
        sys.exit()
    
    def _handle_events(self):
        """Process input events."""
        # Update mouse hover every frame
        mouse_pos = pygame.mouse.get_pos()
        if not self.engine.battle_over:
            self.order_system.handle_mouse_move(
                mouse_pos,
                self.player_empire.buildings,
                self.enemy_empire.buildings,
            )
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q or event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_r and self.engine.battle_over:
                    self._start_battle()
                elif not self.engine.battle_over:
                    self._handle_keydown(event.key)
            
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if not self.engine.battle_over:
                    self._handle_click(event.pos)
    
    def _handle_click(self, pos: tuple):
        """Handle a left mouse click."""
        order = self.order_system.handle_click(
            pos,
            self.player_empire.buildings,
            self.enemy_empire.buildings,
            engine=self.engine,
        )
        
        if order == "heal":
            self._use_health_pack()
        elif order:
            self._execute_player_order(order)
    
    def _use_health_pack(self):
        """Use a health pack on the currently selected class."""
        if not self.order_system.has_class_selected:
            self.order_system.feedback_msg = "Select a class first"
            self.order_system.feedback_timer = 1.5
            return
        
        cls = self.order_system.selected_class
        if self.player_empire.health_packs <= 0:
            self.order_system.feedback_msg = "No health packs left"
            self.order_system.feedback_timer = 1.5
            return
        
        if not self.player_empire.get_dead_by_class(cls):
            self.order_system.feedback_msg = f"No dead {cls.value}s to revive"
            self.order_system.feedback_timer = 1.5
            return
        
        if self.player_empire.heal_member(cls):
            self.order_system.feedback_msg = f"Revived a {cls.value}! ({self.player_empire.health_packs} packs left)"
            self.order_system.feedback_timer = 2.0
    
    def _handle_keydown(self, key):
        """Handle keyboard shortcuts for class selection."""
        from orders import CLASS_BUTTONS
        
        key_map = {
            pygame.K_e: 0,      # Enforcer
            pygame.K_a: 1,      # Assassin
            pygame.K_s: 2,      # Sniper
            pygame.K_d: 3,      # Demolitionist
        }
        
        if key in key_map:
            btn_index = key_map[key]
            self.order_system.select_button_by_index(btn_index)
        elif key == pygame.K_h:
            self._use_health_pack()
    
    def _execute_player_order(self, order):
        """Execute a player order."""
        if order.action == OrderAction.ATTACK:
            self.engine.execute_order(order, self.player_empire, self.enemy_empire)
        else:
            self.engine.execute_order(order, self.player_empire, self.player_empire)
    
    def _update(self, dt: float):
        """Update game state."""
        if self.engine.battle_over:
            return
        
        # Update battle engine
        self.engine.update(dt)
        
        # Update order cooldown
        self.order_system.update(dt)
        
        # Update AI
        ai_order = self.ai.update(dt, self.engine)
        if ai_order:
            if ai_order.action == OrderAction.ATTACK:
                self.engine.execute_order(ai_order, self.enemy_empire, self.player_empire)
            else:
                self.engine.execute_order(ai_order, self.enemy_empire, self.enemy_empire)
    
    def _render(self):
        """Render the current frame."""
        self.renderer.render(self.engine, self.order_system)


if __name__ == "__main__":
    game = Game()
    game.run()

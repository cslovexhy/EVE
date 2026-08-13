"""EVE - Empire vs Empire: Main game loop."""

import sys
import pygame

import config
from models import MemberClass, MemberState, OrderAction, create_starting_roster
from engine import BattleEngine
from orders import OrderSystem
from ai import BattleAI
from renderer import Renderer
from setup_ui import SetupUI, BUILDING_NAMES


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
        """Initialize a new battle with pre-battle setup phase."""
        self.player_empire = create_starting_roster("Your Empire", is_player=True)
        self.enemy_empire = create_starting_roster("Enemy Empire", is_player=False)
        
        # Pre-battle setup UI (building arrangement + member assignment)
        setup = SetupUI(self.screen, self.player_empire)
        building_order, member_assignments = setup.run()
        
        # Apply player's building arrangement and member assignments
        self.player_empire.building_order = building_order
        self.player_empire.member_assignments = member_assignments
        
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
        
        if isinstance(order, tuple) and order[0] == "heal_building":
            self._use_health_pack_on_building(order[1])
        elif order:
            self._execute_player_order(order)
    
    def _use_health_pack_on_building(self, building_index: int):
        """Use a health pack to revive the highest-HP dead defender at the specified building."""
        if self.player_empire.health_packs <= 0:
            self.order_system.feedback_msg = "No health packs left"
            self.order_system.feedback_timer = 1.5
            return
        
        building = self.player_empire.buildings[building_index]
        if building.destroyed:
            self.order_system.feedback_msg = "Building is destroyed"
            self.order_system.feedback_timer = 1.5
            return
        
        # Find dead members that were assigned to this building
        dead_at_building = [
            m for m in self.player_empire.members
            if m.state == MemberState.DEAD and m.assigned_building == building_index
        ]
        
        if not dead_at_building:
            # Fallback: any dead member (if none were assigned here)
            dead_at_building = [m for m in self.player_empire.members if m.state == MemberState.DEAD]
        
        if not dead_at_building:
            self.order_system.feedback_msg = "No dead members to revive"
            self.order_system.feedback_timer = 1.5
            return
        
        # Prioritize highest max_hp (tankiest member first)
        dead_at_building.sort(key=lambda m: m.max_hp, reverse=True)
        member = dead_at_building[0]
        
        # Revive at the clicked building
        import random
        member.hp = member.max_hp
        member.state = MemberState.DEFENDING
        member.stealthed = False
        member.time_since_combat = 0.0
        member.attack_cooldown = 0.0
        member.target_building = None
        member.assigned_building = building_index
        member.x = building.x + random.uniform(-15, 15)
        member.y = building.y + random.uniform(-15, 15)
        building.defenders.append(member)
        
        self.player_empire.health_packs -= 1
        self.order_system.feedback_msg = f"Revived {member.member_class.value} '{member.name}' at bldg {building_index+1} ({self.player_empire.health_packs} packs left)"
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
            self.order_system.heal_mode = False  # Exit heal mode on class select
        elif key == pygame.K_h:
            self.order_system.heal_mode = not self.order_system.heal_mode
        elif key == pygame.K_t:
            from orders import ATTACK_MODE_BUTTON
            ATTACK_MODE_BUTTON.toggle()
    
    def _execute_player_order(self, order):
        """Execute a player order."""
        if order.action == OrderAction.ATTACK:
            self.engine.execute_order(order, self.player_empire, self.enemy_empire, 
                                     attack_mode=self.order_system.attack_mode)
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
                self.engine.execute_order(ai_order, self.enemy_empire, self.player_empire, attack_mode="auto")
            else:
                self.engine.execute_order(ai_order, self.enemy_empire, self.enemy_empire, attack_mode="auto")
    
    def _render(self):
        """Render the current frame."""
        self.renderer.render(self.engine, self.order_system)


if __name__ == "__main__":
    game = Game()
    game.run()

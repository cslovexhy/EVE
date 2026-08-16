"""EVE - Battle session: runs one EvE battle (setup -> real-time battle).

Extracted from the old monolithic main loop so the battle can be launched as a
self-contained, blocking step from the map. run() returns the winner
("player" / "enemy") or None if the player exited/forfeited before a result.
"""
import sys
import random

import pygame

import config
from models import MemberClass, MemberState, OrderAction
from engine import BattleEngine
from orders import OrderSystem
from ai import BattleAI
from renderer import Renderer


class BattleSession:
    """One EvE battle. The player's base layout and member assignments are set
    up ahead of time on the EVE Layout screen, so this launches straight into
    the fight — there is no pre-battle setup step."""

    def __init__(self, screen, player_empire, enemy_empire,
                 building_order=None, member_assignments=None):
        self.screen = screen
        self.player_empire = player_empire
        self.enemy_empire = enemy_empire

        # Apply the persistent base config onto the player empire.
        if building_order is not None:
            self.player_empire.building_order = building_order
        if member_assignments is not None:
            self.player_empire.member_assignments = member_assignments

        self.engine = BattleEngine(player_empire, enemy_empire)
        self.order_system = OrderSystem()
        self.ai = BattleAI(enemy_empire, player_empire)
        self.renderer = Renderer(screen)

        self.clock = pygame.time.Clock()
        self.finished = False

    def run(self):
        """Blocking battle loop. Returns the winning Empire object or None."""
        while not self.finished:
            dt = self.clock.tick(config.FPS) / 1000.0
            self._handle_events()
            self._update(dt)
            self._render()
            pygame.display.flip()
        return self.engine.winner

    # --- events ----------------------------------------------------------
    def _handle_events(self):
        mouse_pos = pygame.mouse.get_pos()
        if not self.engine.battle_over:
            self.order_system.handle_mouse_move(
                mouse_pos,
                self.player_empire.buildings,
                self.enemy_empire.buildings,
            )

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            elif event.type == pygame.KEYDOWN:
                if self.engine.battle_over:
                    # Any of these acknowledge the result and return to the map.
                    if event.key in (pygame.K_RETURN, pygame.K_SPACE,
                                     pygame.K_ESCAPE, pygame.K_q):
                        self.finished = True
                else:
                    if event.key in (pygame.K_q, pygame.K_ESCAPE):
                        # Forfeit / leave the battle (no winner recorded).
                        self.finished = True
                    else:
                        self._handle_keydown(event.key)

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if not self.engine.battle_over:
                    self._handle_click(event.pos)

    def _handle_click(self, pos):
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
        if self.player_empire.health_packs <= 0:
            self.order_system.feedback_msg = "No health packs left"
            self.order_system.feedback_timer = 1.5
            return

        building = self.player_empire.buildings[building_index]
        if building.destroyed:
            self.order_system.feedback_msg = "Building is destroyed"
            self.order_system.feedback_timer = 1.5
            return

        dead_at_building = [
            m for m in self.player_empire.members
            if m.state == MemberState.DEAD and m.assigned_building == building_index
        ]
        if not dead_at_building:
            dead_at_building = [m for m in self.player_empire.members
                                if m.state == MemberState.DEAD]
        if not dead_at_building:
            self.order_system.feedback_msg = "No dead members to revive"
            self.order_system.feedback_timer = 1.5
            return

        dead_at_building.sort(key=lambda m: m.max_hp, reverse=True)
        member = dead_at_building[0]

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
        self.order_system.feedback_msg = (
            f"Revived {member.member_class.value} '{member.name}' at bldg "
            f"{building_index+1} ({self.player_empire.health_packs} packs left)"
        )
        self.order_system.feedback_timer = 2.0

    def _handle_keydown(self, key):
        from orders import CLASS_BUTTONS  # noqa: F401 (kept for parity)

        key_map = {
            pygame.K_e: 0,      # Enforcer
            pygame.K_a: 1,      # Assassin
            pygame.K_s: 2,      # Sniper
            pygame.K_d: 3,      # Demolitionist
        }
        if key in key_map:
            self.order_system.select_button_by_index(key_map[key])
            self.order_system.heal_mode = False
        elif key == pygame.K_h:
            self.order_system.heal_mode = not self.order_system.heal_mode
        elif key == pygame.K_t:
            from orders import ATTACK_MODE_BUTTON
            ATTACK_MODE_BUTTON.toggle()

    def _execute_player_order(self, order):
        if order.action == OrderAction.ATTACK:
            self.engine.execute_order(order, self.player_empire, self.enemy_empire,
                                      attack_mode=self.order_system.attack_mode)
        else:
            self.engine.execute_order(order, self.player_empire, self.player_empire)

    # --- update / render -------------------------------------------------
    def _update(self, dt: float):
        if self.engine.battle_over:
            return
        self.engine.update(dt)
        self.order_system.update(dt)
        ai_order = self.ai.update(dt, self.engine)
        if ai_order:
            if ai_order.action == OrderAction.ATTACK:
                self.engine.execute_order(ai_order, self.enemy_empire,
                                          self.player_empire, attack_mode="auto")
            else:
                self.engine.execute_order(ai_order, self.enemy_empire,
                                          self.enemy_empire, attack_mode="auto")

    def _render(self):
        self.renderer.render(self.engine, self.order_system)

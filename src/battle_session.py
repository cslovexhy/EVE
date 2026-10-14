"""EVE - Battle session: runs one EvE battle (setup -> real-time battle).

Extracted from the old monolithic main loop so the battle can be launched as a
self-contained, blocking step from the map. run() returns the winner
("player" / "enemy") or None if the player exited/forfeited before a result.
"""
import sys

import pygame

import config
from models import OrderAction, Order
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
        # The enemy fights with its assigned targeting personality (set on the
        # empire by enemy_gen; falls back to the default when absent).
        self.ai = BattleAI(enemy_empire, player_empire, is_player=False,
                           profile=getattr(enemy_empire, "ai_profile_name", None))
        # Same AI class drives the player's side when AI-assist is toggled on
        # (default targeting personality).
        self.player_ai = BattleAI(player_empire, enemy_empire, is_player=True)
        self.ai_mode = False
        self.nuke_armed = False   # player has armed the nuke and is picking a target
        self.renderer = Renderer(screen)

        self.clock = pygame.time.Clock()
        self.finished = False

        # War speed: +/- cycles 1x/2x/4x/8x (implemented by sub-stepping the sim).
        self.SPEEDS = [1, 2, 4, 8]
        self.speed_idx = 0
        self._speed_font = pygame.font.SysFont("Arial", 22, bold=True)

    @property
    def speed(self) -> int:
        return self.SPEEDS[self.speed_idx]

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
        import voice  # parallel voice input; no-op if unavailable
        voice.pump()  # 1:1 keystroke commands arrive as synthetic KEYDOWN below
        mouse_pos = pygame.mouse.get_pos()
        if not self.engine.battle_over:
            self.order_system.handle_mouse_move(
                mouse_pos,
                self.player_empire.buildings,
                self.enemy_empire.buildings,
            )
            # Numbered voice commands (attack/heal/nuke {n}) resolve through the
            # same order logic a mouse click uses (visibility/validity checks).
            for intent in voice.poll_battle_intents():
                self._handle_voice_battle_intent(intent)

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

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button in (1, 3):
                if self.engine.battle_over:
                    # On the battle-over (victory/defeat) screen, a left-click
                    # acknowledges the result and proceeds — same as pressing
                    # ENTER — so the player can continue to the loot/recruit
                    # reveal with either the keyboard or the mouse.
                    if event.button == 1:
                        self.finished = True
                else:
                    self._handle_click(event.pos, button=event.button)

            elif event.type == pygame.MOUSEWHEEL:
                # Scroll forward (up) speeds up, scroll back (down) slows down —
                # same 1x/2x/4x/8x ladder as the +/- keys.
                if not self.engine.battle_over:
                    if event.y > 0:
                        self._speed_up()
                    elif event.y < 0:
                        self._speed_down()

    def _handle_voice_battle_intent(self, intent):
        """Resolve a numbered voice command (attack/heal/nuke {n}) through the
        same logic a mouse click uses. Voice never bypasses the game's checks:
        attacks honor visibility/attack-block, nuke uses launch_nuke, heal uses
        the health-pack path. Ignored while AI-assist is driving your side."""
        from models import MemberClass, OrderAction, Order

        p = intent.payload
        idx = p.get("building")
        if idx is None:
            return

        if intent.kind == "heal":
            self._use_health_pack_on_building(idx)
            return

        if intent.kind == "nuke":
            frac = self.engine.nuke_charge_fraction(self.player_empire)
            if frac is None:
                self.order_system.feedback_msg = "No Nuclear Silo"
                self.order_system.feedback_timer = 1.5
                return
            if frac < config.NUKE_MIN_CHARGE:
                pct = int(config.NUKE_MIN_CHARGE * 100)
                self.order_system.feedback_msg = (
                    f"Nuke needs {pct}% charge ({int(frac * 100)}% now)")
                self.order_system.feedback_timer = 1.5
                return
            if self.engine.launch_nuke(self.player_empire, idx):
                self.order_system.feedback_msg = f"NUKE launched on building {idx + 1}!"
                self.order_system.feedback_timer = 2.0
                self.nuke_armed = False
            return

        if intent.kind == "attack":
            if self.ai_mode:
                return  # AI is driving your side; manual orders are ignored
            cls_map = {
                "enforcer": MemberClass.ENFORCER, "assassin": MemberClass.ASSASSIN,
                "sniper": MemberClass.SNIPER, "demolitionist": MemberClass.DEMOLITIONIST,
            }
            member_class = cls_map.get(p.get("cls"))
            if member_class is None:
                return
            # Route through the same group-order path a click uses (single-class
            # group), so visibility / attack-block / availability checks all apply.
            self._order_attack_group([member_class], idx)

    def _handle_click(self, pos, button: int = 1):
        # Nuke targeting is a left-click on an enemy building while armed.
        if self.nuke_armed and button == 1:
            idx = self._enemy_building_at(pos)
            if idx is not None and self.engine.launch_nuke(self.player_empire, idx):
                self.order_system.feedback_msg = f"NUKE launched on building {idx + 1}!"
                self.order_system.feedback_timer = 2.0
                self.nuke_armed = False
            return
        if self.ai_mode:
            return  # AI is driving your side; manual orders are ignored
        result = self.order_system.handle_click(
            pos,
            self.player_empire.buildings,
            self.enemy_empire.buildings,
            engine=self.engine,
            button=button,
        )
        if not result:
            return
        if result[0] == "heal_building":
            self._use_health_pack_on_building(result[1])
        elif result[0] == "attack_group":
            _, classes, idx = result
            self._order_attack_group(classes, idx)

    def _order_attack_group(self, classes, building_index: int):
        """Order each class in a group to attack a building, applying the same
        per-class visibility / attack-block checks a single click used to.
        Classes that can't reach the target are skipped; if NONE can reach it,
        a single feedback message explains why (shared across the group)."""
        ordered_any = False
        last_reason = None
        for member_class in classes:
            if not self.engine.is_attackable_by_class(building_index, member_class,
                                                      is_player=True):
                last_reason = "No visibility"
                continue
            reason = self.engine.attack_block_reason(building_index, is_player=True)
            if reason:
                last_reason = reason
                continue
            if not self.player_empire.get_available_by_class(member_class):
                continue  # none of this class alive/available — silently skip
            order = Order(member_class=member_class, target_building=building_index,
                          action=OrderAction.ATTACK)
            self._execute_player_order(order)
            ordered_any = True
        if not ordered_any and last_reason:
            self.order_system.feedback_msg = last_reason
            self.order_system.feedback_timer = 2.0

    def _use_health_pack_on_building(self, building_index: int):
        if self.player_empire.health_packs <= 0:
            self.order_system.feedback_msg = "No health packs left"
            self.order_system.feedback_timer = 1.5
            return

        # Note: a destroyed building can still hold dead members orphaned in the
        # rubble (e.g. a nuke that flattened the building without killing its
        # occupants). heal_building revives them in place; only a truly empty
        # slot returns None below.
        member = self.player_empire.heal_building(building_index)
        if member is None:
            self.order_system.feedback_msg = "No more dead members to heal here"
            self.order_system.feedback_timer = 1.5
            return

        self.order_system.feedback_msg = (
            f"Revived {member.member_class.value} '{member.name}' at bldg "
            f"{building_index+1} ({self.player_empire.health_packs} packs left)"
        )
        self.order_system.feedback_timer = 2.0

    def _handle_keydown(self, key):
        # A/S/D/F select the attack mode: 1/4, 1/2, Full, Auto.
        mode_keys = {
            pygame.K_a: 0,   # 1/4
            pygame.K_s: 1,   # 1/2
            pygame.K_d: 2,   # Full
            pygame.K_f: 3,   # Auto
        }
        if key in mode_keys:
            self.order_system.set_mode_index(mode_keys[key])
            from orders import ATTACK_MODE_BUTTON
            self.order_system.feedback_msg = f"Mode: {ATTACK_MODE_BUTTON.label}"
            self.order_system.feedback_timer = 1.0
        elif key == pygame.K_TAB:
            self.ai_mode = not self.ai_mode
        elif key == pygame.K_n:
            frac = self.engine.nuke_charge_fraction(self.player_empire)
            if frac is None:
                self.order_system.feedback_msg = "No Nuclear Silo"
                self.order_system.feedback_timer = 1.5
            elif frac < config.NUKE_MIN_CHARGE:
                pct = int(config.NUKE_MIN_CHARGE * 100)
                self.order_system.feedback_msg = (
                    f"Nuke needs {pct}% charge ({int(frac * 100)}% now)")
                self.order_system.feedback_timer = 1.5
            else:
                # Armed; the nuke is one-shot, charge scales the damage.
                self.nuke_armed = not self.nuke_armed
        elif key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
            self._speed_up()
        elif key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self._speed_down()
        elif key == pygame.K_m:
            # Sound effects are disabled game-wide; keep the mixer muted so M
            # cannot re-enable SFX (and so the choice is never persisted on).
            import sound
            sound.set_muted(True)
            self.order_system.feedback_msg = "Sound disabled"
            self.order_system.feedback_timer = 1.2

    def _speed_up(self):
        """Step war speed up one notch (1x/2x/4x/8x). Shared by +/- keys and
        mouse-wheel-forward."""
        self.speed_idx = min(len(self.SPEEDS) - 1, self.speed_idx + 1)

    def _speed_down(self):
        """Step war speed down one notch. Shared by +/- keys and
        mouse-wheel-back."""
        self.speed_idx = max(0, self.speed_idx - 1)

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
        # Sub-step the simulation `speed` times per frame for stable fast-forward.
        for _ in range(self.speed):
            self.engine.update(dt)
            self.order_system.update(dt)
            # Player-side AI (only when AI-assist is toggled on).
            if self.ai_mode:
                p_order = self.player_ai.update(dt, self.engine)
                if p_order:
                    if p_order.action == OrderAction.ATTACK:
                        self.engine.execute_order(p_order, self.player_empire,
                                                  self.enemy_empire, attack_mode="auto")
                    else:
                        self.engine.execute_order(p_order, self.player_empire,
                                                  self.player_empire, attack_mode="auto")
            ai_order = self.ai.update(dt, self.engine)
            if ai_order:
                if ai_order.action == OrderAction.ATTACK:
                    self.engine.execute_order(ai_order, self.enemy_empire,
                                              self.player_empire, attack_mode="auto")
                else:
                    self.engine.execute_order(ai_order, self.enemy_empire,
                                              self.enemy_empire, attack_mode="auto")
            if self.engine.battle_over:
                break

        # Enemy auto-launches its (one-shot) nuke as soon as it reaches the
        # minimum charge, aimed at its CURRENT attack target so the blast
        # supports its offense. Falls back to your bloodiest building if the AI
        # has no current target (e.g. nothing reachable yet).
        enemy_frac = self.engine.nuke_charge_fraction(self.enemy_empire)
        if (not self.engine.battle_over and enemy_frac is not None
                and enemy_frac >= config.ENEMY_NUKE_THRESHOLD):
            target_idx = self.ai.current_target
            if target_idx is None or not self.engine.is_slot_targetable(
                    self.player_empire, target_idx):
                targets = [b for b in self.player_empire.buildings
                           if self.engine.is_slot_targetable(
                               self.player_empire, b.index)]
                if targets:
                    best = max(targets, key=lambda b: sum(
                        1 for m in self.player_empire.members
                        if m.is_alive and m.assigned_building == b.index))
                    target_idx = best.index
                else:
                    target_idx = None
            if target_idx is not None:
                self.engine.launch_nuke(self.enemy_empire, target_idx)

    def _enemy_building_at(self, pos):
        size = config.BUILDING_SIZE
        for b in self.enemy_empire.buildings:
            # Rubble slots that still hold a live member remain targetable, so a
            # nuke can finish off members orphaned by an earlier blast.
            if not self.engine.is_slot_targetable(self.enemy_empire, b.index):
                continue
            rect = pygame.Rect(int(b.x) - size // 2, int(b.y) - size // 2, size, size)
            if rect.collidepoint(pos):
                return b.index
        return None

    def _render(self):
        self.renderer.render(self.engine, self.order_system)
        if not self.engine.battle_over:
            # Right-edge status stack, placed BELOW the HUD bar (0-40) and the
            # class-stats bar (42-112) so it never overlaps the enemy
            # score/forces readouts drawn there by the renderer.
            x_right = config.SCREEN_WIDTH - 20
            y = config.STATS_Y + config.STATS_HEIGHT + 12   # just below stats bar
            line_h = 26

            def _blit_right(text, color):
                nonlocal y
                surf = self._speed_font.render(text, True, color)
                self.screen.blit(surf, (x_right - surf.get_width(), y))
                y += line_h

            _blit_right(f"Speed {self.speed}x  (+/- or scroll)", config.GOLD)
            mode_txt = "AI: ON  (Tab)" if self.ai_mode else "Manual  (Tab)"
            _blit_right(mode_txt, config.GREEN if self.ai_mode else config.LIGHT_GRAY)

            state, frac = self.engine.nuke_status(self.player_empire)
            if state == "spent":
                _blit_right("Nuke: SPENT", config.DARK_GRAY)
            elif state == "charging":
                pct = int(config.NUKE_MIN_CHARGE * 100)
                _blit_right(f"Nuke {int(frac*100)}%  (needs {pct}% to launch)",
                            config.LIGHT_GRAY)
            elif state == "ready":
                if self.nuke_armed:
                    _blit_right(f"NUKE {int(frac*100)}%: click enemy building",
                                config.RED)
                else:
                    _blit_right(f"Nuke {int(frac*100)}% READY  (N to launch)",
                                config.RED)
            # state == "none": no silo, draw nothing.

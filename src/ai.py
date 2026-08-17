"""EVE - AI Opponent: coordinated multi-class attack strategies."""

import random
import time
from models import Empire, MemberClass, MemberState, OrderAction, Order
from engine import BattleEngine
import config


class BattleAI:
    """AI that coordinates classes into organized attack waves.
    
    Strategy:
    - Enforcers stay home to defend (only sent to attack as last resort)
    - Assassins + Snipers assault together (assassins engage, snipers support from range)
    - Demos charge in after defenders are weakened to destroy buildings
    - Picks a focus target with weighted randomness:
      - Building 3, 6, 9 (front row from AI's perspective): 30% each
      - Building 7 (backdoor via assassins): 10%
    """
    
    def __init__(self, empire: Empire, enemy_empire: Empire, is_player: bool = False):
        self.empire = empire
        self.enemy = enemy_empire
        self.is_player = is_player  # True when this AI drives the player's side
        self.time_since_last_order = 0.0
        self.first_order_issued = False
        self.orders_issued = 0
        self.order_queue = []  # Queue of orders to issue in sequence
        self.queue_delay = 0.0
        self.current_target = None  # The building we're focusing on
        self.phase = "opening"  # opening, assault, push, cleanup
        
        # Seed RNG based on current time for varied behavior each game
        self.rng = random.Random(int(time.time() * 1000))
    
    def update(self, dt: float, engine: BattleEngine) -> Order:
        """Update AI timer and return next order from queue or plan new attack."""
        self.time_since_last_order += dt
        
        # If we have queued orders, issue them with slight delay
        if self.order_queue:
            self.queue_delay += dt
            if self.queue_delay >= 0.5:  # 0.5s between queued orders
                self.queue_delay = 0.0
                return self.order_queue.pop(0)
            return None
        
        # Wait before first order
        if not self.first_order_issued:
            if self.time_since_last_order >= config.AI_FIRST_ORDER_DELAY:
                self.first_order_issued = True
                self.time_since_last_order = 0.0
                self._plan_attack(engine)
                return self.order_queue.pop(0) if self.order_queue else None
            return None
        
        # Plan new attack wave on interval
        if self.time_since_last_order >= config.AI_ORDER_INTERVAL:
            self.time_since_last_order = 0.0
            self._plan_attack(engine)
            return self.order_queue.pop(0) if self.order_queue else None
        
        return None
    
    def _plan_attack(self, engine: BattleEngine):
        """Plan a coordinated attack wave based on current battle state."""
        self.order_queue = []
        
        # Use health packs if needed
        self._use_health_packs()
        
        # Plan the attack based on phase
        if self.phase == "opening":
            self._plan_opening(engine)
        elif self.phase == "assault":
            self._plan_assault(engine)
        elif self.phase == "push":
            self._plan_push(engine)
        else:
            self._plan_cleanup(engine)
    
    def _use_health_packs(self):
        """AI uses health packs when an attack class is depleted."""
        if self.empire.health_packs <= 0:
            return
        
        # Priority: revive attack classes that are fully dead
        for cls in [MemberClass.ASSASSIN, MemberClass.DEMOLITIONIST, MemberClass.SNIPER]:
            alive = len([m for m in self.empire.members
                        if m.member_class == cls and m.is_alive])
            dead = self.empire.get_dead_by_class(cls)
            
            # Use health packs if class has fewer than 3 alive and has dead members
            if alive < 3 and dead and self.empire.health_packs > 0:
                revived = self.empire.heal_member(cls)
                if revived:
                    print(f"  [AI] Healed {cls.value} '{revived.name}' (packs left: {self.empire.health_packs})")
                # Use up to 2 packs per wave on the same class if badly depleted
                if alive < 1 and self.empire.health_packs > 0 and self.empire.get_dead_by_class(cls):
                    revived = self.empire.heal_member(cls)
                    if revived:
                        print(f"  [AI] Healed {cls.value} '{revived.name}' (packs left: {self.empire.health_packs})")
    
    def _plan_opening(self, engine: BattleEngine):
        """Opening phase: pick a target with weighted randomness, send assassins + snipers.
        
        Target weights (player building indices):
        - Building 1 (index 0): 30% — front row
        - Building 4 (index 3): 30% — front row
        - Building 7 (index 6): 30% — front row
        - Building 9 (index 8): 10% — backdoor (assassins only)
        """
        # Weighted target selection
        targets_weights = [
            (0, 30),   # Building 1
            (3, 30),   # Building 4
            (6, 30),   # Building 7
            (8, 10),   # Building 9 (backdoor)
        ]
        
        # Filter to only undestroyed and reachable targets
        valid_weighted = []
        for target_idx, weight in targets_weights:
            if self.enemy.buildings[target_idx].destroyed:
                continue
            # Backdoor (building 9) only reachable by assassins
            if target_idx == 8:
                if engine.worthwhile_target(target_idx, MemberClass.ASSASSIN, is_player=self.is_player):
                    valid_weighted.append((target_idx, weight))
            else:
                if engine.worthwhile_target(target_idx, MemberClass.ASSASSIN, is_player=self.is_player):
                    valid_weighted.append((target_idx, weight))
        
        if not valid_weighted:
            # Fallback: any reachable building
            valid_targets = [
                b.index for b in self.enemy.buildings
                if not b.destroyed and engine.worthwhile_target(b.index, MemberClass.ASSASSIN, is_player=self.is_player)
            ]
            if not valid_targets:
                self.phase = "cleanup"
                return
            self.current_target = self.rng.choice(valid_targets)
        else:
            # Weighted random choice
            indices = [t[0] for t in valid_weighted]
            weights = [t[1] for t in valid_weighted]
            self.current_target = self.rng.choices(indices, weights=weights, k=1)[0]
        
        # Send assassins to engage defenders
        if self.empire.get_available_by_class(MemberClass.ASSASSIN):
            self.order_queue.append(Order(
                member_class=MemberClass.ASSASSIN,
                target_building=self.current_target,
                action=OrderAction.ATTACK,
            ))
        
        # Send snipers to support (only if they can reach the target)
        if self.empire.get_available_by_class(MemberClass.SNIPER):
            if engine.worthwhile_target(self.current_target, MemberClass.SNIPER, is_player=self.is_player):
                self.order_queue.append(Order(
                    member_class=MemberClass.SNIPER,
                    target_building=self.current_target,
                    action=OrderAction.ATTACK,
                ))
        
        self.phase = "assault"
        self.orders_issued += 1
    
    def _plan_assault(self, engine: BattleEngine):
        """Assault phase: check if defenders are down, send demos to destroy building."""
        if self.current_target is None:
            self.phase = "opening"
            return
        
        target_bldg = self.enemy.buildings[self.current_target]
        
        # If target is already destroyed, move to next phase
        if target_bldg.destroyed:
            self.phase = "push"
            return

        # If the target is no longer worth attacking — e.g. a shielded bunker
        # whose own defenders are all dead but which is still protected by the
        # OTHER bunker — abandon it and go find a new target instead of dumping
        # ammo into an invulnerable, empty building. This check is class-
        # independent (the shield does not depend on who is attacking), so it
        # will not wrongly abandon an assassin-only backdoor target.
        if engine.attack_block_reason(self.current_target, is_player=self.is_player) is not None:
            self.current_target = None
            self.phase = "push"
            return
        
        # Check if defenders at target are weakened
        defenders = [
            m for m in self.enemy.members
            if m.is_alive and m.assigned_building == self.current_target
        ]
        
        if len(defenders) <= 2:
            # Defenders weakened — send demos to finish the building
            if self.empire.get_available_by_class(MemberClass.DEMOLITIONIST):
                if engine.worthwhile_target(self.current_target, MemberClass.DEMOLITIONIST, is_player=self.is_player):
                    self.order_queue.append(Order(
                        member_class=MemberClass.DEMOLITIONIST,
                        target_building=self.current_target,
                        action=OrderAction.ATTACK,
                    ))
        else:
            # Still has defenders — send more assassins if available
            if self.empire.get_available_by_class(MemberClass.ASSASSIN):
                self.order_queue.append(Order(
                    member_class=MemberClass.ASSASSIN,
                    target_building=self.current_target,
                    action=OrderAction.ATTACK,
                ))
        
        # Also keep snipers firing
        if self.empire.get_available_by_class(MemberClass.SNIPER):
            # Snipers target same building or a nearby one
            valid_sniper_targets = [
                b.index for b in self.enemy.buildings
                if not b.destroyed and engine.worthwhile_target(b.index, MemberClass.SNIPER, is_player=self.is_player)
            ]
            if valid_sniper_targets:
                sniper_target = self.current_target if self.current_target in valid_sniper_targets else self.rng.choice(valid_sniper_targets)
                self.order_queue.append(Order(
                    member_class=MemberClass.SNIPER,
                    target_building=sniper_target,
                    action=OrderAction.ATTACK,
                ))
        
        self.orders_issued += 1
    
    def _plan_push(self, engine: BattleEngine):
        """Push phase: building destroyed, pick next target deeper in."""
        # Find newly reachable targets
        valid_targets = [
            b.index for b in self.enemy.buildings
            if not b.destroyed and engine.worthwhile_target(b.index, MemberClass.DEMOLITIONIST, is_player=self.is_player)
        ]
        
        if not valid_targets:
            self.phase = "cleanup"
            return
        
        # Pick the next target (prefer ones we couldn't reach before)
        self.current_target = self.rng.choice(valid_targets)
        
        # Coordinated wave on new target
        if self.empire.get_available_by_class(MemberClass.ASSASSIN):
            self.order_queue.append(Order(
                member_class=MemberClass.ASSASSIN,
                target_building=self.current_target,
                action=OrderAction.ATTACK,
            ))
        
        if self.empire.get_available_by_class(MemberClass.SNIPER):
            if engine.worthwhile_target(self.current_target, MemberClass.SNIPER, is_player=self.is_player):
                self.order_queue.append(Order(
                    member_class=MemberClass.SNIPER,
                    target_building=self.current_target,
                    action=OrderAction.ATTACK,
                ))
        
        if self.empire.get_available_by_class(MemberClass.DEMOLITIONIST):
            if engine.worthwhile_target(self.current_target, MemberClass.DEMOLITIONIST, is_player=self.is_player):
                self.order_queue.append(Order(
                    member_class=MemberClass.DEMOLITIONIST,
                    target_building=self.current_target,
                    action=OrderAction.ATTACK,
                ))
        
        self.phase = "assault"
        self.orders_issued += 1
    
    def _plan_cleanup(self, engine: BattleEngine):
        """Cleanup: send everything at remaining buildings."""
        valid_targets = [
            b.index for b in self.enemy.buildings
            if not b.destroyed
        ]
        if not valid_targets:
            return
        
        target = self.rng.choice(valid_targets)
        
        for cls in [MemberClass.ASSASSIN, MemberClass.SNIPER, MemberClass.DEMOLITIONIST]:
            if self.empire.get_available_by_class(cls):
                if engine.worthwhile_target(target, cls, is_player=self.is_player):
                    self.order_queue.append(Order(
                        member_class=cls,
                        target_building=target,
                        action=OrderAction.ATTACK,
                    ))
        
        # Even send enforcers in cleanup
        if self.empire.get_available_by_class(MemberClass.ENFORCER):
            if engine.worthwhile_target(target, MemberClass.ENFORCER, is_player=self.is_player):
                self.order_queue.append(Order(
                    member_class=MemberClass.ENFORCER,
                    target_building=target,
                    action=OrderAction.ATTACK,
                ))
    


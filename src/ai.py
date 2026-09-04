"""EVE - AI Opponent: coordinated multi-class attack strategies."""

import random
import time
from models import Empire, MemberClass, MemberState, OrderAction, Order
from engine import BattleEngine
import ai_profiles
import config


class BattleAI:
    """AI that coordinates classes into organized attack waves.
    
    Strategy:
    - All attack classes (enforcers, assassins, snipers, demolitionists) are
      batched into each coordinated wave — combat is all-ranged, so enforcers
      fire alongside everyone else rather than idling on defense.
    - Assassins + Snipers open the assault (assassins engage, snipers support
      from range); demos charge in after defenders are weakened to destroy
      buildings; enforcers add sustained ranged damage on the focus target.
    - Focus target is chosen by a VALUE-scoring model (see the target-scoring
      section below and config.AI_TARGET_SCORE_*): each wave the AI picks the
      highest-scoring building it can currently see/reach, ties broken randomly.
      Score = building-type value + the summed value of the building's live
      defenders.
    """
    
    def __init__(self, empire: Empire, enemy_empire: Empire, is_player: bool = False,
                 profile=None):
        self.empire = empire
        self.enemy = enemy_empire
        self.is_player = is_player  # True when this AI drives the player's side
        # Targeting personality (see ai_profiles). Accepts an AIProfile, a
        # profile name, or None (-> the default "value" profile).
        if isinstance(profile, str) or profile is None:
            self.profile = ai_profiles.get_profile(profile)
        else:
            self.profile = profile
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

    # --- target scoring ---------------------------------------------------
    # The active PROFILE (ai_profiles) decides how a candidate building is
    # scored; the AI focuses the highest-scoring building it can currently
    # see/reach. Only reachable targets are ever scored (filtered by callers).
    def _target_score(self, building_index: int) -> float:
        """Value of attacking this building, per the active targeting profile.
        Passes the building plus its live defenders to the profile's scorer."""
        b = self.enemy.buildings[building_index]
        defenders = [m for m in self.enemy.members
                     if m.is_alive and m.assigned_building == building_index]
        return self.profile.score(b, defenders, self.rng)

    def _best_target(self, candidate_indices) -> int:
        """Pick the highest-scoring building among candidates (ties broken
        randomly to keep behavior varied). Returns None if no candidates."""
        candidates = list(candidate_indices)
        if not candidates:
            return None
        scores = {i: self._target_score(i) for i in candidates}
        best = max(scores.values())
        top = [i for i, s in scores.items() if s == best]
        return self.rng.choice(top)

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
        """AI uses health packs when its attack force is depleted. Uses the
        SAME per-building heal logic as the player (Empire.heal_building):
        revive the strongest dead defender in place, in the chosen building."""
        if self.empire.health_packs <= 0:
            return

        attack_classes = {MemberClass.ASSASSIN, MemberClass.DEMOLITIONIST,
                          MemberClass.SNIPER}

        # Heal while the attack force is thin and packs remain. Cap the number
        # of packs spent per wave so the AI doesn't dump them all at once.
        packs_this_wave = 0
        while self.empire.health_packs > 0 and packs_this_wave < 2:
            alive_attackers = len([m for m in self.empire.members
                                   if m.member_class in attack_classes and m.is_alive])
            if alive_attackers >= 3:
                break

            # Choose the building holding the most dead attack-class defenders;
            # fall back to any building with a dead defender.
            best_slot, best_attack_dead, best_any_dead = None, 0, 0
            for slot, b in enumerate(self.empire.buildings):
                dead_here = [m for m in self.empire.members
                             if m.state == MemberState.DEAD
                             and m.assigned_building == slot]
                if not dead_here:
                    continue
                attack_dead = sum(1 for m in dead_here
                                  if m.member_class in attack_classes)
                # Prefer buildings with dead attackers; break ties on total dead.
                key = (attack_dead, len(dead_here))
                if key > (best_attack_dead, best_any_dead):
                    best_slot, best_attack_dead, best_any_dead = slot, attack_dead, len(dead_here)

            if best_slot is None:
                break  # nothing left to revive

            revived = self.empire.heal_building(best_slot)
            if revived is None:
                break
            packs_this_wave += 1
            print(f"  [AI] Healed {revived.member_class.value} '{revived.name}' "
                  f"at bldg {best_slot + 1} (packs left: {self.empire.health_packs})")
    
    def _plan_opening(self, engine: BattleEngine):
        """Opening phase: focus the highest-VALUE building the AI can currently
        reach (see target-score model above), then send the assault classes.

        Reachability uses assassin visibility (the widest: front doors 1/4/7 plus
        the backdoor 9), so the AI only ever scores buildings it can actually hit.
        """
        # Candidate = every building this side can reach right now (assassin has
        # the widest reach, so it defines "what the AI can see").
        reachable = [
            b.index for b in self.enemy.buildings
            if engine.worthwhile_target(b.index, MemberClass.ASSASSIN, is_player=self.is_player)
        ]
        self.current_target = self._best_target(reachable)
        if self.current_target is None:
            self.phase = "cleanup"
            return

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

        # Send enforcers too — combat is all-ranged now, so enforcers fire like
        # any other class. Batch them into the wave (front-door reachability).
        if self.empire.get_available_by_class(MemberClass.ENFORCER):
            if engine.worthwhile_target(self.current_target, MemberClass.ENFORCER, is_player=self.is_player):
                self.order_queue.append(Order(
                    member_class=MemberClass.ENFORCER,
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
                if engine.worthwhile_target(b.index, MemberClass.SNIPER, is_player=self.is_player)
            ]
            if valid_sniper_targets:
                sniper_target = self.current_target if self.current_target in valid_sniper_targets else self.rng.choice(valid_sniper_targets)
                self.order_queue.append(Order(
                    member_class=MemberClass.SNIPER,
                    target_building=sniper_target,
                    action=OrderAction.ATTACK,
                ))

        # Keep enforcers firing on the target too (all-ranged: they contribute
        # sustained damage like any class rather than idling on defense).
        if self.empire.get_available_by_class(MemberClass.ENFORCER):
            if engine.worthwhile_target(self.current_target, MemberClass.ENFORCER, is_player=self.is_player):
                self.order_queue.append(Order(
                    member_class=MemberClass.ENFORCER,
                    target_building=self.current_target,
                    action=OrderAction.ATTACK,
                ))

        self.orders_issued += 1
    
    def _plan_push(self, engine: BattleEngine):
        """Push phase: building destroyed, pick next target deeper in."""
        # Find newly reachable targets
        valid_targets = [
            b.index for b in self.enemy.buildings
            if engine.worthwhile_target(b.index, MemberClass.DEMOLITIONIST, is_player=self.is_player)
        ]
        
        if not valid_targets:
            self.phase = "cleanup"
            return
        
        # Pick the highest-value reachable building (deeper buildings are now
        # visible after the front row fell).
        self.current_target = self._best_target(valid_targets)
        
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

        if self.empire.get_available_by_class(MemberClass.ENFORCER):
            if engine.worthwhile_target(self.current_target, MemberClass.ENFORCER, is_player=self.is_player):
                self.order_queue.append(Order(
                    member_class=MemberClass.ENFORCER,
                    target_building=self.current_target,
                    action=OrderAction.ATTACK,
                ))

        self.phase = "assault"
        self.orders_issued += 1
    
    def _plan_cleanup(self, engine: BattleEngine):
        """Cleanup: send everything at remaining buildings."""
        valid_targets = [
            b.index for b in self.enemy.buildings
            if engine.is_slot_targetable(self.enemy, b.index)
        ]
        if not valid_targets:
            return
        
        target = self._best_target(valid_targets)
        
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
    


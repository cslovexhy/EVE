"""EVE - AI Opponent: scripted decision-making for the enemy empire."""

import random
from models import Empire, MemberClass, OrderAction, Order
from engine import BattleEngine
import config


class BattleAI:
    """Simple scripted AI that makes attack/defend decisions on a timer."""
    
    def __init__(self, empire: Empire, enemy_empire: Empire):
        self.empire = empire
        self.enemy = enemy_empire
        self.time_since_last_order = 0.0
        self.first_order_issued = False
        self.orders_issued = 0
    
    def update(self, dt: float, engine: BattleEngine) -> Order:
        """Update AI timer and possibly return an order."""
        self.time_since_last_order += dt
        
        # Wait before first order
        if not self.first_order_issued:
            if self.time_since_last_order >= config.AI_FIRST_ORDER_DELAY:
                self.first_order_issued = True
                self.time_since_last_order = 0.0
                return self._decide_order(engine)
            return None
        
        # Issue orders on interval
        if self.time_since_last_order >= config.AI_ORDER_INTERVAL:
            self.time_since_last_order = 0.0
            return self._decide_order(engine)
        
        return None
    
    def _decide_order(self, engine: BattleEngine) -> Order:
        """AI decision logic: attack or defend based on battle state."""
        # Evaluate threats to own buildings
        threatened_buildings = self._find_threatened_buildings(engine)
        
        # If buildings are under attack, 40% chance to defend
        if threatened_buildings and random.random() < 0.4:
            return self._make_defend_order(threatened_buildings)
        
        # Otherwise, attack
        return self._make_attack_order(engine)
    
    def _find_threatened_buildings(self, engine: BattleEngine) -> list:
        """Find own buildings that are being attacked by enemy."""
        threatened = []
        for building in self.empire.buildings:
            if building.destroyed:
                continue
            # Check if any player members are attacking this building
            for member in self.enemy.members:
                if (member.is_alive and 
                    member.state.value == "attacking" and
                    member.target_building == building.index):
                    threatened.append(building.index)
                    break
        return threatened
    
    def _make_defend_order(self, threatened_buildings: list) -> Order:
        """Issue a defend order to reinforce a threatened building."""
        target = random.choice(threatened_buildings)
        
        # Pick a class that has available members
        available_classes = self._get_classes_with_available()
        if not available_classes:
            return None
        
        # Prefer enforcers for defense
        if MemberClass.ENFORCER in available_classes:
            chosen_class = MemberClass.ENFORCER
        else:
            chosen_class = random.choice(available_classes)
        
        return Order(
            member_class=chosen_class,
            target_building=target,
            action=OrderAction.DEFEND,
        )
    
    def _make_attack_order(self, engine: BattleEngine) -> Order:
        """Issue an attack order against an enemy building."""
        # Pick a target building (prefer undestroyed ones)
        valid_targets = [b.index for b in self.enemy.buildings if not b.destroyed]
        if not valid_targets:
            return None
        
        # Strategy: early game attack front row, later go for back row
        if self.orders_issued < 3:
            # Attack front row first (0, 3, 6)
            front = [i for i in valid_targets if i % 3 == 0]
            target = random.choice(front) if front else random.choice(valid_targets)
        else:
            # Mix it up — sometimes go for back row
            target = random.choice(valid_targets)
        
        # Pick attacking class
        available_classes = self._get_classes_with_available()
        if not available_classes:
            return None
        
        # Match class to target strategy
        if target % 3 == 2:  # Back row — send assassins if available
            if MemberClass.ASSASSIN in available_classes:
                chosen_class = MemberClass.ASSASSIN
            else:
                chosen_class = random.choice(available_classes)
        elif target % 3 == 0:  # Front row — send demos to break buildings
            if MemberClass.DEMOLITIONIST in available_classes:
                chosen_class = MemberClass.DEMOLITIONIST
            else:
                chosen_class = random.choice(available_classes)
        else:
            chosen_class = random.choice(available_classes)
        
        self.orders_issued += 1
        
        return Order(
            member_class=chosen_class,
            target_building=target,
            action=OrderAction.ATTACK,
        )
    
    def _get_classes_with_available(self) -> list:
        """Get list of member classes that have available members."""
        available = []
        for cls in MemberClass:
            if self.empire.get_available_by_class(cls):
                available.append(cls)
        return available

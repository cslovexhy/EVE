"""EVE - Battle Engine: grid positions, movement, combat resolution, fog of war."""

import math
import random
from models import (
    Empire, Member, Building, Order, MemberClass, MemberState, OrderAction
)
import config


class BattleEngine:
    """Manages the battle state, movement, and combat resolution."""
    
    def __init__(self, player_empire: Empire, enemy_empire: Empire):
        self.player = player_empire
        self.enemy = enemy_empire
        self.battle_time = 0.0
        self.battle_over = False
        self.winner = None
        
        # Position buildings on the battlefield
        self._position_buildings()
        self._assign_initial_defenders()
    
    def _position_buildings(self):
        """Place buildings on the battlefield grid.
        
        Layout (from player's perspective):
        Player side (left):          Enemy side (right):
        [0] [1] [2]                  [0] [1] [2]
        [3] [4] [5]                  [3] [4] [5]
        [6] [7] [8]                  [6] [7] [8]
        
        Index 0,3,6 = front row (closest to center)
        Index 2,5,8 = back row (furthest from center)
        """
        center_x = config.BATTLEFIELD_X + config.BATTLEFIELD_WIDTH // 2
        
        # Calculate grid dimensions
        grid_w = 2 * config.GRID_CELL_SIZE  # 3 columns, spacing between them
        grid_h = 2 * config.GRID_CELL_SIZE  # 3 rows, spacing between them
        
        # Center player grid in left half
        left_half_center_x = config.BATTLEFIELD_X + config.BATTLEFIELD_WIDTH // 4
        left_half_center_y = config.BATTLEFIELD_Y + config.BATTLEFIELD_HEIGHT // 2
        
        # Center enemy grid in right half
        right_half_center_x = config.BATTLEFIELD_X + 3 * config.BATTLEFIELD_WIDTH // 4
        right_half_center_y = config.BATTLEFIELD_Y + config.BATTLEFIELD_HEIGHT // 2
        
        # Player buildings (left side, centered in left half)
        for b in self.player.buildings:
            row = b.index // 3   # 0, 1, 2 (top to bottom)
            col = b.index % 3    # 0=front, 1=mid, 2=back
            
            # X: front row (col 0) closer to center, back row (col 2) toward left edge
            b.x = left_half_center_x + (1 - col) * config.GRID_CELL_SIZE
            # Y: centered vertically
            b.y = left_half_center_y + (row - 1) * config.GRID_CELL_SIZE
        
        # Enemy buildings (right side, centered in right half)
        for b in self.enemy.buildings:
            row = b.index // 3
            col = b.index % 3
            
            # X: front row (col 0) closer to center, back row (col 2) toward right edge
            b.x = right_half_center_x + (col - 1) * config.GRID_CELL_SIZE
            # Y: centered vertically
            b.y = right_half_center_y + (row - 1) * config.GRID_CELL_SIZE
    
    def _assign_initial_defenders(self):
        """Distribute members across buildings as initial defenders."""
        # Player: spread evenly, 1 per building for first 8
        for i, member in enumerate(self.player.members):
            building_idx = i % 9
            building = self.player.buildings[building_idx]
            building.defenders.append(member)
            member.assigned_building = building_idx
            member.state = MemberState.DEFENDING
            member.x = building.x
            member.y = building.y
        
        # Enemy: same distribution
        for i, member in enumerate(self.enemy.members):
            building_idx = i % 9
            building = self.enemy.buildings[building_idx]
            building.defenders.append(member)
            member.assigned_building = building_idx
            member.state = MemberState.DEFENDING
            member.x = building.x
            member.y = building.y
    
    def update(self, dt: float):
        """Main update tick. Called every frame."""
        if self.battle_over:
            return
        
        self.battle_time += dt
        
        # Check battle end - timer
        if self.battle_time >= config.BATTLE_DURATION:
            self._end_battle()
            return
        
        # Check battle end - total destruction
        if self._check_elimination():
            return
        
        # Update all members
        for member in self.player.members + self.enemy.members:
            if member.is_alive:
                self._update_member(member, dt)
    
    def _update_member(self, member: Member, dt: float):
        """Update a single member: movement and combat."""
        member.attack_cooldown = max(0, member.attack_cooldown - dt)
        
        if member.state == MemberState.ATTACKING:
            self._update_attacker(member, dt)
        elif member.state == MemberState.MOVING:
            self._update_mover(member, dt)
        elif member.state == MemberState.DEFENDING:
            self._update_defender(member, dt)
    
    def _update_attacker(self, member: Member, dt: float):
        """Attacker: move toward target, fight defenders, damage building."""
        # Determine which empire this member belongs to
        is_player_member = member in self.player.members
        target_empire = self.enemy if is_player_member else self.player
        
        if member.target_building is None:
            return
        
        target_bldg = target_empire.buildings[member.target_building]
        
        # Move toward target building
        dist = self._distance(member.x, member.y, target_bldg.x, target_bldg.y)
        
        # Snipers stop at SNIPER_RANGE, others at ATTACK_RANGE
        if member.member_class == MemberClass.SNIPER:
            engage_range = config.SNIPER_RANGE
        else:
            engage_range = config.ATTACK_RANGE
        
        if dist > engage_range:
            # Move toward target
            speed = config.MEMBER_MOVE_SPEED * member.get_stats()["speed"]
            self._move_toward(member, target_bldg.x, target_bldg.y, speed, dt)
            # Assassin stealth: accumulate time since combat while moving
            if member.member_class == MemberClass.ASSASSIN:
                member.time_since_combat += dt
                if member.time_since_combat >= config.STEALTH_DELAY:
                    member.stealthed = True
        else:
            # In range — fight
            if member.attack_cooldown <= 0:
                # Break stealth on attack
                if member.stealthed:
                    member.stealthed = False
                    member.time_since_combat = 0.0
                self._resolve_attack(member, target_bldg, target_empire)
                member.attack_cooldown = member.get_stats()["attack_interval"]
                member.time_since_combat = 0.0
    
    def _update_mover(self, member: Member, dt: float):
        """Member moving to a defensive position."""
        dist = self._distance(member.x, member.y, member.target_x, member.target_y)
        
        if dist <= 10:
            # Arrived
            member.state = MemberState.DEFENDING
            member.x = member.target_x
            member.y = member.target_y
        else:
            speed = config.MEMBER_MOVE_SPEED * member.get_stats()["speed"]
            self._move_toward(member, member.target_x, member.target_y, speed, dt)
    
    def _update_defender(self, member: Member, dt: float):
        """Defender: attack nearby enemies."""
        # Assassin stealth while defending (accumulate out-of-combat time)
        if member.member_class == MemberClass.ASSASSIN:
            member.time_since_combat += dt
            if member.time_since_combat >= config.STEALTH_DELAY:
                member.stealthed = True
        
        if member.attack_cooldown > 0:
            return
        
        is_player_member = member in self.player.members
        enemy_members = self.enemy.members if is_player_member else self.player.members
        own_empire = self.player if is_player_member else self.enemy
        
        # Find closest enemy in range (skip stealthed enemies)
        attack_range = config.SNIPER_RANGE if member.member_class == MemberClass.SNIPER else config.ATTACK_RANGE
        
        closest = None
        closest_dist = float('inf')
        
        for enemy in enemy_members:
            if not enemy.is_alive or enemy.state not in (MemberState.ATTACKING, MemberState.MOVING):
                continue
            if enemy.stealthed:
                continue  # Can't target stealthed enemies
            dist = self._distance(member.x, member.y, enemy.x, enemy.y)
            if dist < closest_dist and dist <= attack_range:
                closest = enemy
                closest_dist = dist
        
        if closest:
            stats = member.get_stats()
            closest.take_damage(stats["damage_player"])
            member.attack_cooldown = stats["attack_interval"]
            # Break own stealth when attacking
            member.stealthed = False
            member.time_since_combat = 0.0
            
            if not closest.is_alive:
                # Award points
                scoring_empire = self.player if is_player_member else self.enemy
                scoring_empire.points += config.POINTS_PER_MEMBER_KILLED
    
    def _resolve_attack(self, attacker: Member, target_bldg: Building, target_empire: Empire):
        """Resolve an attack on a building or its defenders."""
        is_player_attacker = attacker in self.player.members
        stats = attacker.get_stats()
        
        # Find defenders at the target building first
        defenders_at_building = [
            m for m in target_empire.members
            if m.is_alive and m.assigned_building == target_bldg.index
            and m.state in (MemberState.DEFENDING, MemberState.IDLE)
        ]
        
        # Snipers: if no defenders at target, scan all buildings in range
        if not defenders_at_building and attacker.member_class == MemberClass.SNIPER:
            for bldg in target_empire.buildings:
                if bldg.destroyed:
                    continue
                dist = self._distance(attacker.x, attacker.y, bldg.x, bldg.y)
                if dist <= config.SNIPER_RANGE:
                    nearby_defenders = [
                        m for m in target_empire.members
                        if m.is_alive and m.assigned_building == bldg.index
                        and m.state in (MemberState.DEFENDING, MemberState.IDLE)
                    ]
                    if nearby_defenders:
                        target_member = random.choice(nearby_defenders)
                        damage = stats["damage_player"]
                        
                        # 50% accuracy penalty if building is not visible
                        if is_player_attacker:
                            visible = self.is_visible_to_player(bldg.index)
                        else:
                            visible = self.is_visible_to_enemy(bldg.index)
                        if not visible and random.random() < 0.5:
                            # Miss
                            return
                        
                        target_member.take_damage(damage)
                        if not target_member.is_alive:
                            if target_member in bldg.defenders:
                                bldg.defenders.remove(target_member)
                            scoring_empire = self.player if is_player_attacker else self.enemy
                            scoring_empire.points += config.POINTS_PER_MEMBER_KILLED
                        return
        
        if defenders_at_building:
            # Attack a random defender
            target_member = random.choice(defenders_at_building)
            
            damage = stats["damage_player"]
            # Sniper accuracy penalty for non-visible target building
            if attacker.member_class == MemberClass.SNIPER:
                if is_player_attacker:
                    visible = self.is_visible_to_player(target_bldg.index)
                else:
                    visible = self.is_visible_to_enemy(target_bldg.index)
                if not visible and random.random() < 0.5:
                    return  # Miss
            
            target_member.take_damage(damage)
            
            if not target_member.is_alive:
                if target_member in target_bldg.defenders:
                    target_bldg.defenders.remove(target_member)
                scoring_empire = self.player if is_player_attacker else self.enemy
                scoring_empire.points += config.POINTS_PER_MEMBER_KILLED
        else:
            # No defenders — damage the building
            if not target_bldg.destroyed:
                target_bldg.take_damage(stats["damage_building"])
                if target_bldg.destroyed:
                    scoring_empire = self.player if is_player_attacker else self.enemy
                    scoring_empire.points += config.POINTS_PER_BUILDING_DESTROYED
    
    def execute_order(self, order: Order, empire: Empire, target_empire: Empire):
        """Execute a player/AI order."""
        available = empire.get_available_by_class(order.member_class)
        
        if not available:
            return  # No available members of this class
        
        if order.action == OrderAction.ATTACK:
            target_bldg = target_empire.buildings[order.target_building]
            for member in available:
                # Remove from current building's defender list
                if member.assigned_building is not None:
                    old_bldg = empire.buildings[member.assigned_building]
                    if member in old_bldg.defenders:
                        old_bldg.defenders.remove(member)
                
                member.state = MemberState.ATTACKING
                member.target_building = order.target_building
                member.assigned_building = None
        
        elif order.action == OrderAction.DEFEND:
            target_bldg = empire.buildings[order.target_building]
            for member in available:
                # Remove from old building
                if member.assigned_building is not None:
                    old_bldg = empire.buildings[member.assigned_building]
                    if member in old_bldg.defenders:
                        old_bldg.defenders.remove(member)
                
                # Assign to new building
                member.assigned_building = order.target_building
                target_bldg.defenders.append(member)
                member.state = MemberState.MOVING
                member.target_x = target_bldg.x + random.uniform(-20, 20)
                member.target_y = target_bldg.y + random.uniform(-20, 20)
    
    def is_visible_to_player(self, building_index: int) -> bool:
        """Fog of war: flood-fill visibility from entry points through destroyed buildings.
        
        This is the PLAYER VIEW — includes building 9 (assassin intel).
        Used for rendering (what the player can see on screen).
        """
        visible = self._compute_visibility(self.enemy, assassin_entry=True)
        return building_index in visible
    
    def is_attackable_by_class(self, building_index: int, member_class, is_player: bool) -> bool:
        """Can this class attack/reach this building?
        
        Non-assassin classes can only reach buildings visible from entry points 1/4/7.
        Assassins can also use building 9 as entry point.
        Same logic applies to both sides (mirrored entry points for enemy).
        """
        if is_player:
            has_assassin_entry = (member_class == MemberClass.ASSASSIN)
            visible = self._compute_visibility(self.enemy, assassin_entry=has_assassin_entry)
        else:
            has_assassin_entry = (member_class == MemberClass.ASSASSIN)
            visible = self._compute_visibility(self.player, assassin_entry=has_assassin_entry, is_enemy_view=True)
        return building_index in visible
    
    def is_visible_to_enemy(self, building_index: int) -> bool:
        """Fog of war for enemy AI viewing player buildings.
        Enemy view — includes building 7 (their assassin backdoor entry)."""
        visible = self._compute_visibility(self.player, assassin_entry=True, is_enemy_view=True)
        return building_index in visible
    
    def _compute_visibility(self, target_empire, assassin_entry: bool = True, is_enemy_view: bool = False) -> set:
        """Flood-fill visibility through destroyed buildings.
        
        Args:
            target_empire: The empire whose buildings we're looking at
            assassin_entry: Whether to include the assassin backdoor entry point
            is_enemy_view: If True, use enemy's entry points (mirrored)
        """
        adjacency = {
            0: [1, 3],
            1: [0, 2, 4],
            2: [1, 5],
            3: [0, 4, 6],
            4: [1, 3, 5, 7],
            5: [2, 4, 8],
            6: [3, 7],
            7: [4, 6, 8],
            8: [5, 7],
        }
        
        if is_enemy_view:
            # Enemy entry points into player buildings: 1, 4, 7 (indices 0, 3, 6) + backdoor 9 (index 8)
            entry_points = {0, 3, 6}
            if assassin_entry:
                entry_points.add(8)  # Building 9 is backdoor
        else:
            # Player entry points into enemy buildings: 1, 4, 7 (indices 0, 3, 6) + backdoor 9 (index 8)
            entry_points = {0, 3, 6}
            if assassin_entry:
                entry_points.add(8)  # Building 9 is backdoor
        
        visible = set(entry_points)
        queue = list(entry_points)
        
        while queue:
            current = queue.pop(0)
            if target_empire.buildings[current].destroyed:
                for neighbor in adjacency[current]:
                    if neighbor not in visible:
                        visible.add(neighbor)
                        queue.append(neighbor)
        
        return visible
    
    def _check_elimination(self) -> bool:
        """Check if either side has lost all buildings or all members."""
        player_alive = len(self.player.get_alive_members()) > 0
        enemy_alive = len(self.enemy.get_alive_members()) > 0
        player_buildings = self.player.buildings_destroyed < 9
        enemy_buildings = self.enemy.buildings_destroyed < 9
        
        # Enemy fully eliminated
        if not enemy_alive or not enemy_buildings:
            self.battle_over = True
            self.winner = self.player
            return True
        
        # Player fully eliminated
        if not player_alive or not player_buildings:
            self.battle_over = True
            self.winner = self.enemy
            return True
        
        return False
    
    def _end_battle(self):
        """Determine winner based on points."""
        self.battle_over = True
        if self.player.points > self.enemy.points:
            self.winner = self.player
        elif self.enemy.points > self.player.points:
            self.winner = self.enemy
        else:
            # Tie: whoever has more building HP remaining wins
            if self.player.total_building_hp >= self.enemy.total_building_hp:
                self.winner = self.player
            else:
                self.winner = self.enemy
    
    def _distance(self, x1, y1, x2, y2) -> float:
        return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
    
    def _move_toward(self, member: Member, tx: float, ty: float, speed: float, dt: float):
        """Move member toward target position."""
        dx = tx - member.x
        dy = ty - member.y
        dist = math.sqrt(dx * dx + dy * dy)
        if dist > 0:
            member.x += (dx / dist) * speed * dt
            member.y += (dy / dist) * speed * dt

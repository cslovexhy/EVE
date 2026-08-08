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
        
        # Player buildings (left side)
        for b in self.player.buildings:
            row = b.index // 3   # 0, 1, 2 (top to bottom)
            col = b.index % 3    # 0=front, 1=mid, 2=back
            
            # X: front row closer to center, back row near left edge
            b.x = config.BATTLEFIELD_X + 80 + (2 - col) * config.GRID_CELL_SIZE
            # Y: spread vertically
            b.y = config.BATTLEFIELD_Y + 60 + row * (config.GRID_CELL_SIZE + 40)
        
        # Enemy buildings (right side, mirrored)
        for b in self.enemy.buildings:
            row = b.index // 3
            col = b.index % 3
            
            # X: front row closer to center, back row near right edge
            b.x = center_x + 40 + col * config.GRID_CELL_SIZE
            # Y: spread vertically
            b.y = config.BATTLEFIELD_Y + 60 + row * (config.GRID_CELL_SIZE + 40)
    
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
        # Priority: fight defenders first, then damage building
        defenders_at_building = [
            m for m in target_empire.members
            if m.is_alive and m.assigned_building == target_bldg.index
            and m.state in (MemberState.DEFENDING, MemberState.IDLE)
        ]
        
        stats = attacker.get_stats()
        
        if defenders_at_building:
            # Attack a random defender
            target_member = random.choice(defenders_at_building)
            target_member.take_damage(stats["damage_player"])
            
            if not target_member.is_alive:
                # Remove from building defenders list
                if target_member in target_bldg.defenders:
                    target_bldg.defenders.remove(target_member)
                # Award points
                is_player_attacker = attacker in self.player.members
                scoring_empire = self.player if is_player_attacker else self.enemy
                scoring_empire.points += config.POINTS_PER_MEMBER_KILLED
        else:
            # No defenders — damage the building
            if not target_bldg.destroyed:
                target_bldg.take_damage(stats["damage_building"])
                if target_bldg.destroyed:
                    is_player_attacker = attacker in self.player.members
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
        
        Grid (1-indexed, stored 0-indexed):
          [1] [2] [3]
          [4] [5] [6]
          [7] [8] [9]
        
        Player entry points (always visible): 1, 4, 7, 9
        Enemy entry points (mirror): 3, 6, 9, 7
        
        A building is visible if:
        - It's an entry point, OR
        - Any 4-connected neighbor is both visible AND destroyed
        
        This means you destroy your way in — each destroyed building
        reveals its adjacent neighbors.
        """
        # Compute full visibility set via flood fill
        visible = self._compute_visibility()
        return building_index in visible
    
    def _compute_visibility(self) -> set:
        """Flood-fill visibility from player's entry points through destroyed enemy buildings."""
        # 4-connected adjacency on 3x3 grid (0-indexed)
        # Grid positions:
        #   0 1 2
        #   3 4 5
        #   6 7 8
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
        
        # Player entry points (0-indexed): buildings 1,4,7,9 → indices 0,3,6,8
        entry_points = {0, 3, 6, 8}
        
        # BFS: start from entry points, spread through destroyed buildings
        visible = set(entry_points)
        queue = list(entry_points)
        
        while queue:
            current = queue.pop(0)
            # If this building is destroyed, its neighbors become visible
            if self.enemy.buildings[current].destroyed:
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

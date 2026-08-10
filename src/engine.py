"""EVE - Battle Engine: grid positions, movement, combat resolution, fog of war."""

import math
import os
import random
from models import (
    Empire, Member, Building, Order, MemberClass, MemberState, OrderAction,
    Projectile, ProjectileType
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
        self.projectiles = []  # Active projectiles in flight
        
        # Position buildings on the battlefield
        self._position_buildings()
        self._assign_initial_defenders()
    
    def _position_buildings(self):
        """Place buildings to match the parallelogram planks in the battlefield background.
        
        Loads positions from assets/building_positions.json if available (created by placement_tool.py).
        Otherwise uses calculated defaults with perspective compression.
        """
        import json
        
        bx = config.BATTLEFIELD_X
        by = config.BATTLEFIELD_Y
        bw = config.BATTLEFIELD_WIDTH
        bh = config.BATTLEFIELD_HEIGHT
        
        # Try loading saved positions from placement tool
        positions_file = os.path.join(os.path.dirname(__file__), "..", "assets", "building_positions.json")
        if os.path.exists(positions_file):
            with open(positions_file, "r") as f:
                saved = json.load(f)
            for b in self.player.buildings:
                px, py = saved["blue"][b.index]
                b.x = bx + px * bw
                b.y = by + py * bh
            for b in self.enemy.buildings:
                px, py = saved["red"][b.index]
                b.x = bx + px * bw
                b.y = by + py * bh
            return
        
        # Fallback: calculated positions with perspective compression
        # Row 3 (bottom) anchor positions as fractions of background image
        # These are tuned to sit on the planks
        # Building 8 is midpoint of 7 and 9
        # BLUE_X_OFFSET: negative = shift left, positive = shift right
        BLUE_X_OFFSET = -0.01
        
        blue_row3 = [(0.340 + BLUE_X_OFFSET, 0.779), (0.211 + BLUE_X_OFFSET, 0.779), (0.082 + BLUE_X_OFFSET, 0.779)]  # bldg 7, 8, 9
        red_row3 = [(0.662, 0.779), (0.791, 0.779), (0.920, 0.779)]    # bldg 7, 8, 9
        
        # Perspective compression: how much upper rows narrow compared to row 3
        # 0.0 = no compression (all rows same width), 1.0 = max compression
        PERSPECTIVE_STRENGTH = 0.075
        
        # Row Y positions
        row_y = [0.360, 0.551, 0.779]  # row 1 (top), row 2 (mid), row 3 (bottom)
        
        # Column spacing scale per row (derived from PERSPECTIVE_STRENGTH)
        # Row 3 = 1.0, row 2 = slightly narrower, row 1 = narrowest
        row_col_scale = [
            1.0 - PERSPECTIVE_STRENGTH * 2,  # row 1 (top)
            1.0 - PERSPECTIVE_STRENGTH,       # row 2 (mid)
            1.0,                              # row 3 (bottom)
        ]
        
        bx = config.BATTLEFIELD_X
        by = config.BATTLEFIELD_Y
        bw = config.BATTLEFIELD_WIDTH
        bh = config.BATTLEFIELD_HEIGHT
        
        # Blue side: front col (col 0) = bldg 7 position, back col (col 2) = bldg 9 position
        blue_front = blue_row3[0][0]  # 0.340 (front row X, anchored)
        blue_back = blue_row3[2][0]   # 0.082 (back row X at row 3)
        blue_span = blue_front - blue_back  # Full span at row 3
        
        for b in self.player.buildings:
            row = b.index // 3   # 0=top, 1=mid, 2=bottom
            col = b.index % 3    # 0=front, 1=mid, 2=back
            
            # Front position shifts slightly inward per row up
            front_x = blue_front + (2 - row) * 0.020
            # Column spacing compressed by perspective
            span = blue_span * row_col_scale[row]
            px = front_x - col * (span / 2.0)
            py = row_y[row]
            
            b.x = bx + px * bw
            b.y = by + py * bh
        
        # Red side: front col (col 0) = bldg 7 position, back col (col 2) = bldg 9 position
        red_front = red_row3[0][0]   # 0.662 (front row X, anchored)
        red_back = red_row3[2][0]    # 0.920 (back row X at row 3)
        red_span = red_back - red_front  # Full span at row 3
        
        for b in self.enemy.buildings:
            row = b.index // 3
            col = b.index % 3
            
            # Front position shifts slightly inward per row up
            front_x = red_front - (2 - row) * 0.020
            # Column spacing compressed by perspective
            span = red_span * row_col_scale[row]
            px = front_x + col * (span / 2.0)
            py = row_y[row]
            
            b.x = bx + px * bw
            b.y = by + py * bh
    
    def _assign_initial_defenders(self):
        """Distribute members across buildings.
        
        Non-enforcers (sniper/assassin/demo) all in building 3 (back, index 2).
        Enforcers spread across other buildings (1/2/4/5/6/7/8/9).
        """
        for empire in (self.player, self.enemy):
            enforcers = [m for m in empire.members if m.member_class == MemberClass.ENFORCER]
            others = [m for m in empire.members if m.member_class != MemberClass.ENFORCER]
            
            # Non-enforcers all go to building 3 (index 2)
            building_3 = empire.buildings[2]
            for member in others:
                building_3.defenders.append(member)
                member.assigned_building = 2
                member.state = MemberState.DEFENDING
                member.x = building_3.x + random.uniform(-20, 20)
                member.y = building_3.y + random.uniform(-20, 20)
            
            # Enforcers spread across other buildings (indices 0,1,3,4,5,6,7,8)
            other_indices = [0, 1, 3, 4, 5, 6, 7, 8]
            for i, member in enumerate(enforcers):
                bldg_idx = other_indices[i % len(other_indices)]
                building = empire.buildings[bldg_idx]
                building.defenders.append(member)
                member.assigned_building = bldg_idx
                member.state = MemberState.DEFENDING
                member.x = building.x + random.uniform(-15, 15)
                member.y = building.y + random.uniform(-15, 15)
    
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
        
        # Update projectiles
        self._update_projectiles(dt)
    
    def _update_member(self, member: Member, dt: float):
        """Update a single member: movement and combat."""
        member.attack_cooldown = max(0, member.attack_cooldown - dt)
        
        # Ammo regeneration
        member.ammo_regen_timer += dt
        if member.ammo_regen_timer >= config.AMMO_REGEN_INTERVAL:
            member.ammo_regen_timer -= config.AMMO_REGEN_INTERVAL
            if member.ammo < config.AMMO_MAX:
                member.ammo += 1
        
        if member.state == MemberState.ATTACKING:
            self._update_attacker(member, dt)
        elif member.state == MemberState.MOVING:
            self._update_mover(member, dt)
        elif member.state == MemberState.DEFENDING:
            self._update_defender(member, dt)
    
    def _update_attacker(self, member: Member, dt: float):
        """Attacker: shoot at target building from current position. No movement needed.
        
        All classes are ranged — they fire projectiles at the target building
        as long as it's visible. The only limit is ammo and attack speed.
        """
        is_player_member = member in self.player.members
        target_empire = self.enemy if is_player_member else self.player
        
        if member.target_building is None:
            return
        
        target_bldg = target_empire.buildings[member.target_building]
        
        # Can only attack visible buildings
        if is_player_member:
            if not self.is_visible_to_player(target_bldg.index):
                return  # Can't see target, do nothing
        else:
            if not self.is_visible_to_enemy(target_bldg.index):
                return
        
        # Assassin stealth: accumulate time since combat
        if member.member_class == MemberClass.ASSASSIN:
            member.time_since_combat += dt
            if member.time_since_combat >= config.STEALTH_DELAY:
                member.stealthed = True
        
        # Fire when ready and have ammo
        if member.attack_cooldown <= 0 and member.ammo > 0:
            # Break stealth on attack
            if member.stealthed:
                member.stealthed = False
                member.time_since_combat = 0.0
            
            # Consume ammo
            member.ammo -= 1
            
            # All classes fire projectiles from current position
            self._fire_projectile(member, target_bldg, target_empire)
            
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
        """Defender: stays in building. Defense is passive — you're a target for enemy fire.
        
        Since all combat is ranged and nobody moves, defenders just exist
        in their building to absorb shots before the building takes damage.
        Assassins still accumulate stealth while defending.
        """
        # Assassin stealth while defending
        if member.member_class == MemberClass.ASSASSIN:
            member.time_since_combat += dt
            if member.time_since_combat >= config.STEALTH_DELAY:
                member.stealthed = True
    
    def _resolve_attack(self, attacker: Member, target_bldg: Building, target_empire: Empire):
        """Resolve a melee attack on a building or its defenders (enforcer/assassin only)."""
        is_player_attacker = attacker in self.player.members
        stats = attacker.get_stats()
        
        # Find defenders at the target building
        defenders_at_building = [
            m for m in target_empire.members
            if m.is_alive and m.assigned_building == target_bldg.index
            and m.state in (MemberState.DEFENDING, MemberState.IDLE)
        ]
        
        if defenders_at_building:
            # Attack a random defender
            target_member = random.choice(defenders_at_building)
            target_member.take_damage(stats["damage_player"])
            
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
            for member in available:
                # Stay in current building, just switch to attacking state
                member.state = MemberState.ATTACKING
                member.target_building = order.target_building
        
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
                member.state = MemberState.DEFENDING
                member.target_building = None
                member.x = target_bldg.x + random.uniform(-20, 20)
                member.y = target_bldg.y + random.uniform(-20, 20)
    
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
    
    def _fire_projectile(self, attacker: Member, target_bldg: Building, target_empire: Empire):
        """Fire a projectile at a building or its defenders. All classes are ranged."""
        stats = attacker.get_stats()
        
        # Determine projectile type and speed based on class
        if attacker.member_class == MemberClass.SNIPER:
            proj_type = ProjectileType.SNIPER
            proj_speed = config.PROJECTILE_SPEED_SNIPER
        elif attacker.member_class == MemberClass.DEMOLITIONIST:
            proj_type = ProjectileType.DEMO
            proj_speed = config.PROJECTILE_SPEED_DEMO
        else:
            # Enforcer/Assassin use sniper-speed projectiles
            proj_type = ProjectileType.SNIPER
            proj_speed = config.PROJECTILE_SPEED_SNIPER
        
        # Find defenders at target building (skip stealthed)
        defenders_at_building = [
            m for m in target_empire.members
            if m.is_alive and m.assigned_building == target_bldg.index
            and m.state in (MemberState.DEFENDING, MemberState.IDLE, MemberState.ATTACKING)
            and not m.stealthed
        ]
        
        if defenders_at_building:
            # Fire at a random defender
            target_member = random.choice(defenders_at_building)
            
            proj = Projectile(
                x=attacker.x, y=attacker.y,
                target_x=target_member.x, target_y=target_member.y,
                speed=proj_speed,
                damage=stats["damage_player"],
                projectile_type=proj_type,
                target_member=target_member,
                missed=False,
            )
            self.projectiles.append(proj)
        else:
            # No defenders — fire at the building itself
            if not target_bldg.destroyed:
                proj = Projectile(
                    x=attacker.x, y=attacker.y,
                    target_x=target_bldg.x, target_y=target_bldg.y,
                    speed=proj_speed,
                    damage=stats["damage_building"],
                    projectile_type=proj_type,
                    target_building=target_bldg,
                    hit_building_directly=True,
                )
                self.projectiles.append(proj)
    
    def _fire_projectile_at_member(self, attacker: Member, target: Member):
        """Fire a projectile from a defending ranged unit at an enemy member."""
        stats = attacker.get_stats()
        
        if attacker.member_class == MemberClass.SNIPER:
            proj_type = ProjectileType.SNIPER
            proj_speed = config.PROJECTILE_SPEED_SNIPER
        else:
            proj_type = ProjectileType.DEMO
            proj_speed = config.PROJECTILE_SPEED_DEMO
        
        proj = Projectile(
            x=attacker.x, y=attacker.y,
            target_x=target.x, target_y=target.y,
            speed=proj_speed,
            damage=stats["damage_player"],
            projectile_type=proj_type,
            target_member=target,
            missed=False,
        )
        self.projectiles.append(proj)
    
    def _update_projectiles(self, dt: float):
        """Move projectiles and resolve impacts."""
        for proj in self.projectiles:
            if not proj.alive:
                continue
            
            # If target member died before impact, kill projectile
            if proj.target_member and not proj.target_member.is_alive:
                proj.alive = False
                continue
            
            # Update target position (track moving targets)
            if proj.target_member and proj.target_member.is_alive:
                proj.target_x = proj.target_member.x
                proj.target_y = proj.target_member.y
            
            # Move toward target
            dx = proj.target_x - proj.x
            dy = proj.target_y - proj.y
            dist = math.sqrt(dx * dx + dy * dy)
            
            if dist <= proj.speed * dt + 5:
                # Impact!
                proj.alive = False
                
                if proj.missed:
                    continue  # Missed shot, no damage
                
                if proj.hit_building_directly and proj.target_building:
                    # Damage building
                    if not proj.target_building.destroyed:
                        proj.target_building.take_damage(proj.damage)
                        if proj.target_building.destroyed:
                            # Award points — determine which side fired
                            # Check if target building belongs to enemy
                            if proj.target_building in self.enemy.buildings:
                                self.player.points += config.POINTS_PER_BUILDING_DESTROYED
                            else:
                                self.enemy.points += config.POINTS_PER_BUILDING_DESTROYED
                elif proj.target_member and proj.target_member.is_alive:
                    # Damage member
                    proj.target_member.take_damage(proj.damage)
                    if not proj.target_member.is_alive:
                        # Remove from building defenders list
                        for bldg in self.player.buildings + self.enemy.buildings:
                            if proj.target_member in bldg.defenders:
                                bldg.defenders.remove(proj.target_member)
                                break
                        # Award points
                        if proj.target_member in self.enemy.members:
                            self.player.points += config.POINTS_PER_MEMBER_KILLED
                        else:
                            self.enemy.points += config.POINTS_PER_MEMBER_KILLED
            else:
                # Move
                proj.x += (dx / dist) * proj.speed * dt
                proj.y += (dy / dist) * proj.speed * dt
        
        # Remove dead projectiles
        self.projectiles = [p for p in self.projectiles if p.alive]
    
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

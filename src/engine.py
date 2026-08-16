"""EVE - Battle Engine: grid positions, movement, combat resolution, fog of war."""

import math
import os
import random
from models import (
    Empire, Member, Building, Order, MemberClass, MemberState, OrderAction,
    Projectile, ProjectileType, BuildingType
)
import config
import buildings


class BattleEngine:
    """Manages the battle state, movement, and combat resolution."""
    
    def __init__(self, player_empire: Empire, enemy_empire: Empire):
        self.player = player_empire
        self.enemy = enemy_empire
        self.battle_time = 0.0
        self.battle_over = False
        self.winner = None
        self.projectiles = []  # Active projectiles in flight
        self.battle_log = []   # Text log of key events

        # Building-power state (per side).
        self._pack_timer = {"player": 0.0, "enemy": 0.0}   # Hospital pack generation
        self._nuke_charge = {"player": 0.0, "enemy": 0.0}  # Nuclear Silo charge (seconds)
        
        # Randomize enemy building placement and member assignment — unless the
        # enemy was pre-built (e.g. scaled from a region's underworld power).
        if not getattr(self.enemy, "building_order", None):
            self._randomize_enemy_setup()
        
        # Apply building types (and per-type HP) from each side's building_order
        self._apply_building_types()
        
        # Position buildings on the battlefield
        self._position_buildings()
        self._assign_initial_defenders()
    
    def _apply_building_types(self):
        """Set building types + type-based HP from each empire's building_order."""
        for empire in (self.player, self.enemy):
            order = getattr(empire, "building_order", None)
            if order:
                buildings.apply_building_order(empire, order)
    
    def _log(self, msg: str):
        """Add a timestamped entry to the battle log and write to file immediately."""
        t = self.battle_time
        entry = f"[{int(t)//60}:{int(t)%60:02d}.{int((t%1)*10)}] {msg}"
        self.battle_log.append(entry)
        # Write immediately to file
        log_path = os.path.join(os.path.dirname(__file__), "..", "battle_log.txt")
        with open(log_path, "a") as f:
            f.write(entry + "\n")
    
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
        
        Uses player's setup choices if available (building_order, member_assignments).
        Otherwise defaults: non-enforcers in building 3, enforcers spread elsewhere.
        """
        for empire in (self.player, self.enemy):
            # Check if this empire has custom assignments from setup UI
            if hasattr(empire, 'member_assignments') and empire.member_assignments:
                # Apply custom member assignments
                for slot_idx, member_indices in enumerate(empire.member_assignments):
                    building = empire.buildings[slot_idx]
                    for mi in member_indices:
                        member = empire.members[mi]
                        building.defenders.append(member)
                        member.assigned_building = slot_idx
                        member.state = MemberState.DEFENDING
                        member.x = building.x + __import__('random').uniform(-20, 20)
                        member.y = building.y + __import__('random').uniform(-20, 20)
            else:
                # Default assignment
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
    
    def _randomize_enemy_setup(self):
        """Randomize enemy building placement and member assignment.
        
        Building placement rules:
        - HQ (index 0) NOT in slots 1/4/7/5/9 (indices 0,3,6,4,8) → only slots 2,3,5,6,8 (indices 1,2,4,5,7)
        - Armory (index 1) NOT in slots 1/4/7 (indices 0,3,6)
        - Hospital (index 2) NOT in slots 1/4/7 (indices 0,3,6)
        - Other buildings: any slot
        
        Member assignment rules:
        - All attackers (sniper/assassin/demo) assigned to HQ slot (50% of them)
        - Enforcers fill defense slots in all buildings
        """
        # Building indices:
        # 0=HQ, 1=Armory, 2=Hospital, 3=Warehouse, 4=Bunker, 5=Nuke, 6=Sniper Tower, 7=ResLab, 8=Safehouse
        
        # Step 1: Randomize building placement
        FRONT_SLOTS = {0, 3, 6}             # Slots 1/4/7
        HQ_BANNED = {0, 3, 6, 4, 8}         # Slots 1/4/7/5/9
        ARMORY_HOSPITAL_BANNED = {0, 3, 6}   # Slots 1/4/7
        
        all_slots = set(range(9))
        
        # Place HQ first (most restricted)
        hq_valid = list(all_slots - HQ_BANNED)  # indices 1,2,5,7 (slots 2,3,6,8)
        hq_slot = random.choice(hq_valid)
        
        remaining_slots = list(all_slots - {hq_slot})
        
        # Place Armory (building index 1)
        armory_valid = [s for s in remaining_slots if s not in ARMORY_HOSPITAL_BANNED]
        armory_slot = random.choice(armory_valid)
        remaining_slots.remove(armory_slot)
        
        # Place Hospital (building index 2)
        hospital_valid = [s for s in remaining_slots if s not in ARMORY_HOSPITAL_BANNED]
        hospital_slot = random.choice(hospital_valid)
        remaining_slots.remove(hospital_slot)
        
        # Place remaining buildings (indices 3-8) randomly in remaining slots
        random.shuffle(remaining_slots)
        
        # Build the order: building_order[slot] = building_name_index
        building_order = [0] * 9
        building_order[hq_slot] = 0         # HQ
        building_order[armory_slot] = 1     # Armory
        building_order[hospital_slot] = 2   # Hospital
        
        other_buildings = [3, 4, 5, 6, 7, 8]  # Warehouse, Bunker, Nuke, Sniper Tower, ResLab, Safehouse
        for i, slot in enumerate(remaining_slots):
            building_order[slot] = other_buildings[i]
        
        self.enemy.building_order = building_order
        
        # Step 2: Assign members
        # All attackers (non-enforcers) go to HQ slot
        # Enforcers spread across all buildings
        enforcers = [i for i, m in enumerate(self.enemy.members)
                     if m.member_class == MemberClass.ENFORCER]
        attackers = [i for i, m in enumerate(self.enemy.members)
                     if m.member_class != MemberClass.ENFORCER]
        
        member_assignments = [[] for _ in range(9)]
        
        # Attackers in HQ (up to 50% of them, the rest also in HQ since there's no other spec)
        # Per the spec: "all attackers in HQ (50%)" — we interpret as all attackers go to HQ
        member_assignments[hq_slot] = list(attackers)
        
        # Enforcers fill defense slots in all buildings
        # Distribute enforcers evenly across all 9 slots
        all_building_slots = list(range(9))
        for i, enf_idx in enumerate(enforcers):
            slot = all_building_slots[i % len(all_building_slots)]
            member_assignments[slot].append(enf_idx)
        
        self.enemy.member_assignments = member_assignments
    
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

        # Building powers (hospital packs, nuke charge)
        self._update_powers(dt)

        # Update projectiles
        self._update_projectiles(dt)

    # --- building powers -------------------------------------------------
    def _side_key(self, empire: Empire) -> str:
        return "player" if empire is self.player else "enemy"

    def _active_of_type(self, empire: Empire, btype: BuildingType):
        """Non-destroyed buildings of a type — a power is active only while its
        building stands, so destroying it removes the power immediately."""
        return [b for b in empire.buildings
                if b.building_type == btype and not b.destroyed]

    def _bunkers_shielded(self, empire: Empire) -> bool:
        """A side's bunkers are untargetable until the defenders in ALL of its
        bunkers are eliminated (i.e. while any bunker still has a live defender)."""
        bunkers = self._active_of_type(empire, BuildingType.BUNKER)
        if not bunkers:
            return False
        bunker_slots = {b.index for b in bunkers}
        return any(m.is_alive and m.assigned_building in bunker_slots
                   for m in empire.members)

    def _update_powers(self, dt: float):
        for empire in (self.player, self.enemy):
            key = self._side_key(empire)
            # Hospital: each active hospital generates health packs over time.
            hospitals = len(self._active_of_type(empire, BuildingType.HOSPITAL))
            if hospitals:
                self._pack_timer[key] += dt * hospitals
                while self._pack_timer[key] >= config.HOSPITAL_PACK_INTERVAL:
                    self._pack_timer[key] -= config.HOSPITAL_PACK_INTERVAL
                    empire.health_packs += 1
            # Nuclear Silo: charge 0->100% over the battle while a silo stands.
            if self._active_of_type(empire, BuildingType.NUCLEAR_SILO):
                self._nuke_charge[key] = min(config.NUKE_CHARGE_TIME,
                                             self._nuke_charge[key] + dt)

    def nuke_charge_fraction(self, empire: Empire):
        """0..1 charge of the side's Nuclear Silo, or None if it has no silo."""
        if not self._active_of_type(empire, BuildingType.NUCLEAR_SILO):
            return None
        return self._nuke_charge[self._side_key(empire)] / config.NUKE_CHARGE_TIME

    def nuke_ready(self, empire: Empire) -> bool:
        frac = self.nuke_charge_fraction(empire)
        return frac is not None and frac >= 1.0

    def launch_nuke(self, empire: Empire, target_index: int) -> bool:
        """Launch the side's charged nuke at an enemy building: 3x3 blast damages
        every building and member in the block centered on target_index."""
        if not self.nuke_ready(empire):
            return False
        target_empire = self.enemy if empire is self.player else self.player
        self._nuke_charge[self._side_key(empire)] = 0.0  # consume charge

        r, c = target_index // 3, target_index % 3
        block = [rr * 3 + cc for rr in range(3) for cc in range(3)
                 if abs(rr - r) <= 1 and abs(cc - c) <= 1]
        side = "PLAYER" if empire is self.player else "ENEMY"
        self._log(f"{side} launched NUKE on building {target_index+1} (3x3 blast)")

        for idx in block:
            # Members in the blast.
            for m in list(target_empire.members):
                if m.is_alive and m.assigned_building == idx:
                    m.take_damage(config.NUKE_MEMBER_DAMAGE)
                    if not m.is_alive:
                        for b in target_empire.buildings:
                            if m in b.defenders:
                                b.defenders.remove(m)
                                break
                        empire.points += config.POINTS_PER_MEMBER_KILLED
            # Building in the blast.
            bldg = target_empire.buildings[idx]
            if not bldg.destroyed:
                bldg.take_damage(config.NUKE_BUILDING_DAMAGE)
                if bldg.destroyed:
                    empire.points += config.POINTS_PER_BUILDING_DESTROYED
        return True
    
    def _update_member(self, member: Member, dt: float):
        """Update a single member: movement and combat."""
        member.attack_cooldown = max(0, member.attack_cooldown - dt)
        
        # Ammo regeneration
        # Ammo regeneration (an active Armory speeds this up for the owning side).
        own_empire = self.player if member in self.player.members else self.enemy
        regen_interval = config.AMMO_REGEN_INTERVAL
        if self._active_of_type(own_empire, BuildingType.ARMORY):
            regen_interval /= config.ARMORY_AMMO_SPEEDUP
        member.ammo_regen_timer += dt
        if member.ammo_regen_timer >= regen_interval:
            member.ammo_regen_timer -= regen_interval
            if member.ammo < config.AMMO_MAX:
                member.ammo += 1
        
        if member.state == MemberState.ATTACKING:
            self._update_attacker(member, dt)
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
            
            # If attack-once mode, return to defending after firing
            if member.attack_once:
                member.state = MemberState.DEFENDING
                member.target_building = None
                member.attack_once = False
    
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
            hp_before = target_member.hp
            target_member.take_damage(stats["damage_player"])
            hp_after = target_member.hp
            side = "PLAYER" if is_player_attacker else "ENEMY"
            self._log(f"{side} hit {target_member.member_class.value} '{target_member.name}' for {hp_before-hp_after:.1f} dmg (HP: {hp_after:.0f}/{target_member.max_hp:.0f})")
            
            if not target_member.is_alive:
                if target_member in target_bldg.defenders:
                    target_bldg.defenders.remove(target_member)
                scoring_empire = self.player if is_player_attacker else self.enemy
                scoring_empire.points += config.POINTS_PER_MEMBER_KILLED
                self._log(f"{side} killed {target_member.member_class.value} '{target_member.name}' at bldg {target_bldg.index+1}")
        else:
            # No defenders — damage the building
            if not target_bldg.destroyed:
                target_bldg.take_damage(stats["damage_building"])
                self._log(f"{'PLAYER' if is_player_attacker else 'ENEMY'} hit building {target_bldg.index+1} for {stats['damage_building']:.1f} dmg (HP: {target_bldg.hp:.0f}/{target_bldg.max_hp})")
                if target_bldg.destroyed:
                    scoring_empire = self.player if is_player_attacker else self.enemy
                    scoring_empire.points += config.POINTS_PER_BUILDING_DESTROYED
    
    def execute_order(self, order: Order, empire: Empire, target_empire: Empire, attack_mode: str = "half"):
        """Execute a player/AI order.
        
        attack_mode:
            'half' — only half (rounded up) of available members fire, then stop
            'once' — all available members fire one volley, then stop
            'auto' — all available members fire continuously
        """
        available = empire.get_available_by_class(order.member_class)
        
        if not available:
            return  # No available members of this class
        
        if order.action == OrderAction.ATTACK:
            side = "PLAYER" if empire == self.player else "ENEMY"
            
            # In "half" mode, only select half the available members (rounded up)
            if attack_mode == "half":
                import math as _math
                count = _math.ceil(len(available) / 2)
                # Pick the first N available (deterministic, no randomness)
                members_to_order = available[:count]
            else:
                members_to_order = available
            
            self._log(f"{side} orders {len(members_to_order)} {order.member_class.value}(s) to attack building {order.target_building+1} ({attack_mode})")
            for member in members_to_order:
                member.state = MemberState.ATTACKING
                member.target_building = order.target_building
                member.attack_once = (attack_mode in ("once", "half"))
    
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

        # Research Lab: the attacking side can see + attack buildings 4/5/7/8/9.
        attacker_empire = self.enemy if is_enemy_view else self.player
        if self._active_of_type(attacker_empire, BuildingType.RESEARCH_LAB):
            visible |= set(config.RESEARCH_LAB_REVEAL)

        # Bunker shield: the defending side's bunkers are untargetable until the
        # defenders in ALL of its bunkers are eliminated.
        if self._bunkers_shielded(target_empire):
            visible -= {b.index for b in target_empire.buildings
                        if b.building_type == BuildingType.BUNKER and not b.destroyed}

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
        elif attacker.member_class == MemberClass.ENFORCER:
            proj_type = ProjectileType.ENFORCER
            proj_speed = config.PROJECTILE_SPEED_ENFORCER
        else:  # Assassin
            proj_type = ProjectileType.ASSASSIN
            proj_speed = config.PROJECTILE_SPEED_ASSASSIN

        # Sniper Tower: a Sniper stationed in one fires for bonus damage.
        dmg_mult = 1.0
        if attacker.member_class == MemberClass.SNIPER and attacker.assigned_building is not None:
            own = self.player if attacker in self.player.members else self.enemy
            b = own.buildings[attacker.assigned_building]
            if b.building_type == BuildingType.SNIPER_TOWER and not b.destroyed:
                dmg_mult = 1.0 + config.SNIPER_TOWER_DAMAGE_BONUS

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
                damage=stats["damage_player"] * dmg_mult,
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
                    damage=stats["damage_building"] * dmg_mult,
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
                    # Re-check for defenders — a healed member may now be here
                    target_bldg = proj.target_building
                    if not target_bldg.destroyed:
                        # Determine which empire owns this building
                        if target_bldg in self.player.buildings:
                            target_empire = self.player
                        else:
                            target_empire = self.enemy
                        
                        defenders_now = [
                            m for m in target_empire.members
                            if m.is_alive and m.assigned_building == target_bldg.index
                            and m.state in (MemberState.DEFENDING, MemberState.IDLE, MemberState.ATTACKING)
                            and not m.stealthed
                        ]
                        
                        if defenders_now:
                            # Redirect damage to a defender instead of building
                            target_member = random.choice(defenders_now)
                            hp_before = target_member.hp
                            target_member.take_damage(proj.damage)
                            hp_after = target_member.hp
                            if target_member in self.enemy.members:
                                shooter_side = "PLAYER"
                            else:
                                shooter_side = "ENEMY"
                            self._log(f"{shooter_side} hit {target_member.member_class.value} '{target_member.name}' for {hp_before-hp_after:.1f} dmg (HP: {hp_after:.0f}/{target_member.max_hp:.0f})")
                            if not target_member.is_alive:
                                for bldg in self.player.buildings + self.enemy.buildings:
                                    if target_member in bldg.defenders:
                                        bldg.defenders.remove(target_member)
                                        break
                                if target_member in self.enemy.members:
                                    self.player.points += config.POINTS_PER_MEMBER_KILLED
                                    self._log(f"PLAYER killed enemy {target_member.member_class.value} '{target_member.name}'")
                                else:
                                    self.enemy.points += config.POINTS_PER_MEMBER_KILLED
                                    self._log(f"ENEMY killed player {target_member.member_class.value} '{target_member.name}'")
                        else:
                            # No defenders — damage building
                            target_bldg.take_damage(proj.damage)
                            self._log(f"HIT building {target_bldg.index+1} for {proj.damage:.1f} dmg (HP: {target_bldg.hp:.0f}/{target_bldg.max_hp})")
                            if target_bldg.destroyed:
                                if target_bldg in self.enemy.buildings:
                                    self.player.points += config.POINTS_PER_BUILDING_DESTROYED
                                    self._log(f"PLAYER destroyed enemy building {target_bldg.index+1}")
                                else:
                                    self.enemy.points += config.POINTS_PER_BUILDING_DESTROYED
                                    self._log(f"ENEMY destroyed player building {target_bldg.index+1}")
                elif proj.target_member and proj.target_member.is_alive:
                    # Damage member
                    hp_before = proj.target_member.hp
                    proj.target_member.take_damage(proj.damage)
                    hp_after = proj.target_member.hp
                    # Determine who shot whom
                    if proj.target_member in self.enemy.members:
                        shooter_side = "PLAYER"
                    else:
                        shooter_side = "ENEMY"
                    self._log(f"{shooter_side} hit {proj.target_member.member_class.value} '{proj.target_member.name}' for {hp_before-hp_after:.1f} dmg (HP: {hp_after:.0f}/{proj.target_member.max_hp:.0f})")
                    
                    if not proj.target_member.is_alive:
                        # Remove from building defenders list
                        for bldg in self.player.buildings + self.enemy.buildings:
                            if proj.target_member in bldg.defenders:
                                bldg.defenders.remove(proj.target_member)
                                break
                        # Award points
                        if proj.target_member in self.enemy.members:
                            self.player.points += config.POINTS_PER_MEMBER_KILLED
                            self._log(f"PLAYER killed enemy {proj.target_member.member_class.value} '{proj.target_member.name}' at bldg {proj.target_member.assigned_building+1 if proj.target_member.assigned_building is not None else '?'}")
                        else:
                            self.enemy.points += config.POINTS_PER_MEMBER_KILLED
                            self._log(f"ENEMY killed player {proj.target_member.member_class.value} '{proj.target_member.name}' at bldg {proj.target_member.assigned_building+1 if proj.target_member.assigned_building is not None else '?'}")
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
            reason = "all members dead" if not enemy_alive else "all buildings destroyed"
            self._log(f"BATTLE OVER: Player wins (enemy {reason})")
            self._save_log()
            return True
        
        # Player fully eliminated
        if not player_alive or not player_buildings:
            self.battle_over = True
            self.winner = self.enemy
            reason = "all members dead" if not player_alive else "all buildings destroyed"
            self._log(f"BATTLE OVER: Enemy wins (player {reason})")
            self._save_log()
            return True
        
        return False
    
    def _end_battle(self):
        """Determine winner based on points (time ran out)."""
        self.battle_over = True
        if self.player.points > self.enemy.points:
            self.winner = self.player
        elif self.enemy.points > self.player.points:
            self.winner = self.enemy
        else:
            if self.player.total_building_hp >= self.enemy.total_building_hp:
                self.winner = self.player
            else:
                self.winner = self.enemy
        
        winner_name = "Player" if self.winner == self.player else "Enemy"
        self._log(f"BATTLE OVER: Time up. {winner_name} wins ({self.player.points} vs {self.enemy.points} pts)")
        self._save_log()
    
    def _save_log(self):
        """Save battle log to file with final state summary."""
        # Add final state
        self.battle_log.append("")
        self.battle_log.append("=== FINAL STATE ===")
        self.battle_log.append(f"Player: {self.player.points} pts, {len(self.player.get_alive_members())}/40 alive, "
                              f"{9-self.player.buildings_destroyed}/9 buildings, {self.player.health_packs} packs left")
        self.battle_log.append(f"Enemy:  {self.enemy.points} pts, {len(self.enemy.get_alive_members())}/40 alive, "
                              f"{9-self.enemy.buildings_destroyed}/9 buildings, {self.enemy.health_packs} packs left")
        
        self.battle_log.append("")
        self.battle_log.append("Player members alive:")
        for cls in MemberClass:
            alive = [m for m in self.player.members if m.member_class == cls and m.is_alive]
            if alive:
                names = [m.name for m in alive]
                self.battle_log.append(f"  {cls.value}: {len(alive)} - {names}")
        
        self.battle_log.append("")
        self.battle_log.append("Enemy members alive:")
        for cls in MemberClass:
            alive = [m for m in self.enemy.members if m.member_class == cls and m.is_alive]
            if alive:
                names = [m.name for m in alive]
                self.battle_log.append(f"  {cls.value}: {len(alive)} - {names}")
        
        # Save to file
        log_path = os.path.join(os.path.dirname(__file__), "..", "battle_log.txt")
        with open(log_path, "w") as f:
            f.write("\n".join(self.battle_log))
        print(f"Battle log saved to {log_path}")
    
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

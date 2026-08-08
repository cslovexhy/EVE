# EVE — Battle Mechanics Design

## Battle Duration
- **5 minutes** per war (compressed from UE's 2 hours)

## Player Control Model: 3-Click Orders

1. **Choose class** — Enforcer / Sniper / Assassin / Demolitionist
2. **Choose target** — Building number (1-9) or "defend building X"
3. **Choose action** — Attack / Defend / Special (TBD)

Example orders:
- "Enforcer → Building 3 → Defend" = all free Enforcers rally to defend Building 3
- "Assassin → Building 9 → Attack" = Assassins sneak to backdoor Building 9
- "Demolitionist → Building 5 → Attack" = Demos focus fire on Building 5 structure
- "Sniper → Building 3 → Attack" = Snipers shoot into Building 3 (blind fire if not visible)

## Member Behavior

### Assigned Defenders (pre-battle)
- Stay INSIDE their assigned building
- Attack enemies within range (those attacking their building)
- Do NOT leave unless explicitly ordered to

### Ordered to Defend (mid-battle)
- Rally FROM other buildings TO the target building
- Fight attackers in the FIELD in front of the building
- Different from assigned defenders — these are reinforcements fighting outside

### Ordered to Attack
- Move toward target building
- Engage enemy defenders along the way
- Goal: destroy building (demos) or kill defenders (others)

## Battlefield Layout (3×3 Grid)

```
ENEMY SIDE          YOUR SIDE
[7] [8] [9]        [1] [2] [3]
[4] [5] [6]        [4] [5] [6]
[1] [2] [3]        [7] [8] [9]
```

Each side sees the other's grid mirrored — your left faces their right.

## Visibility (Fog of War)

### What you can see of the enemy:
- **Front row (1, 4, 7)**: Fully visible — see defenders, their levels, rarity, health
- **Building 9 (with Assassins)**: Partially visible if you have assassin scouts
- **Other buildings (2, 3, 5, 6, 8)**: Only see placeholder silhouettes — don't know who's defender vs attacker, don't know levels/rarity

### What you see of enemy attackers:
- When enemy members leave their buildings to attack YOU, they become **visible in the field**
- Shown as **cards** with:
  - Level (number with star, top-left of frame)
  - Rarity (frame color: white/green/blue/gold)
  - Health bar
  - Class icon

### What enemy sees of you:
- Same rules apply in reverse

## Combat Flow Example

1. Battle starts — both sides have defenders in buildings
2. You order: "Demolitionist → Building 1 → Attack"
   - Your demos move toward enemy front row Building 1
   - They engage enemy defenders standing outside/in front
   - If they kill all defenders, they start damaging the building itself
3. Enemy orders their Enforcers to defend Building 1
   - Enemy enforcers from other buildings rally to Building 1's front
   - Melee breaks out between your demos and their enforcers
4. You see an opportunity: "Assassin → Building 9 → Attack"
   - While enemy is distracted at Building 1, assassins sneak to back
5. Enemy doesn't see it coming (Building 9 not in their visible defense range)

## Class Roles in Battle

| Class | Attack Strength | Defense Strength | Special |
|-------|----------------|-----------------|---------|
| Enforcer | Medium vs players | HIGH (tank) | Rallies fast, absorbs damage |
| Sniper | Medium vs players (ranged) | Low | Can shoot into non-adjacent buildings (blind fire) |
| Assassin | HIGH vs players | Low | Can reach back-row buildings, bonus vs unaware |
| Demolitionist | LOW vs players, HIGH vs buildings | Medium | Primary building destroyer |

## Order Logic & Prioritization

### Who responds to an order?
When you issue "Enforcer → Building 4 → Defend":
- All **idle/unengaged** Enforcers respond immediately
- Enforcers **defending other buildings** (assigned, not under attack) respond
- Enforcers **currently in combat on your side** respond (disengage and rally)

### Who does NOT respond:
- Members **actively attacking enemy buildings** — they're deep in enemy territory, doing work. Don't recall them.
- Members **currently engaged in enemy territory** — too far committed, pulling back would get them killed

### Smart Order Rules:
- Orders only pull members from **your side of the field** (defending, idle, in transit home)
- Members on **offensive operations in enemy territory** are committed — they finish or die
- To recall attackers, you'd need a separate explicit "Retreat" command (TBD if this exists)
- This prevents accidental self-sabotage (recalling assassins mid-backdoor)

### Implication:
- Once you send members on an attack, they're **committed**
- Defensive orders only summon members who are available on your side
- This creates real commitment cost — sending all your enforcers to attack means you CAN'T recall them to defend

## Open Questions
- How do tokens/action points work in the 5-min format? Cooldown on orders?
- Can you cancel/redirect an order mid-execution?
- What happens when a building is destroyed? Members inside die? Displaced?
- Do snipers need line of sight or can they always shoot "over" buildings?
- Auto-battle AI: what do members do when they have NO orders? (idle in building? auto-defend nearest?)
- Is there a "Retreat" command to pull back committed attackers? Cost/penalty?

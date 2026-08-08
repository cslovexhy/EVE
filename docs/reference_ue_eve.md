# Underworld Empire — EvE (Empire vs Empire) System Reference

Source: https://underworld-empire.fandom.com/wiki/Empire_War

## Overview

Empire Battles pit two **empires** (guilds) head-to-head. Minimum 7 members to participate. Wars last **2 hours** or until one empire wins. Wars are scheduled and matchmade by the system. Players join mid-war by spending 10 stamina.

Winner = empire with more points at the end. Tie = both lose.

---

## Battlefield Layout

Each empire has **9 buildings** in a **3×3 grid**. Your empire on the left, enemy on the right.

### Starting Buildings:
- 1× HQ
- 2× Safehouse
- 6× Warehouse

### Upgradeable Buildings:
| Building | Upgraded From |
|----------|--------------|
| Sniper Tower | Warehouse |
| Hospital | Warehouse |
| Armory | Warehouse |
| Nuclear Silo | Warehouse |
| Research Lab | Warehouse |
| Hardened Bunker | Safehouse |

Buildings have: HP, point value, defender slots, offensive slots. Upgradeable via donated resources.

---

## Tokens (Action Economy)

- Start with **10 tokens** (more if joining late)
- Most actions cost **1 token**
- Regen rate:
  - Sleeping (not yet attacked/joined): 1 per 8 min
  - Awake: 1 per 5 min
  - Rates improved by Armory upgrades
- Max tokens: **25 + 5 per Armory level**

---

## Player Health (EvE-specific)

Separate from normal health:
- Non-Enforcers: `3× Health stat + 1200`
- Enforcers: `4× Health stat + 1200`
- Veteran skill adds % bonus

### Health Thresholds:
| HP | State |
|----|-------|
| >400 | Healthy |
| <400 | Can be executed (Decapitate) |
| <200 | Dead (half damage, no skills) |
| 0 | Dead |

**Revival**: Hospital health packs restore 1200 + 200 per hospital level.

---

## Attacking

### Visibility:
- Normally can only target **front column** (3 nearest buildings)
- Buildings behind destroyed buildings become visible
- **Assassins**: can also see far building in bottom row
- **Snipers**: can see offensive slot player counts in all buildings (but not details/health)

### Combat:
- Attack any visible player
- When ALL defenders in a building are below 200 HP → building itself can be attacked
- Building at 0 HP → demolished
- Win or lose, both attacker and defender lose HP

---

## Player Classes & Skills

### Enforcer
- **Knockout**: Stuns target (reduced damage, slower tokens, more Assassin damage)
- **Stim Pack**: Immunity to status effects (25% resist, doubled on self)
- **Last Stand**: More counter damage + defense, expires on death

### Sniper
- **Concealed Shot**: Suppresses target (halved counter damage)
- **Mark Target**: Makes target visible to all friendly snipers
- Can attack any visible player, even back row

### Assassin
- **Poison**: 2% max HP damage per token spent, lasts 25 tokens
- **Decapitate**: Can execute below 400 HP threshold
- Bonus damage to sleeping/stunned players
- Can attack far bottom-row building

### Heavy Weapons
- **Burn**: 5 dmg/min for 5 min, stackable 3×
- **Booby Trap**: Target takes damage when healed, building also damaged
- **Explosives**: Target takes damage when Burned, splash damage

### Terminator
- **Napalm**: Damage over time indefinitely, reduced healing
- **Time Bomb**: Delayed damage to player + building, halved if detonated by heal

### Reaper
- **Plague**: % current HP damage per token, lasts indefinitely, building damage

### Ghost
- **Adrenaline Rush**: +40% crit rate, +40% crit damage, 2× counter damage taken
- **Ghost Tag**: +12% incoming damage, reduced defense/dodge/deflect

### Titan
- **Strengthen**: Stuns (same as Knockout)

---

## Building Super Powers

Enabled by collecting 320 credits (1 per member daily achievement, or 40 free per 24h). Officers activate for 24 hours.

| Building | Super Power |
|----------|-------------|
| HQ | +30% crit damage mitigation, cap incoming damage at max(2000, 33% HP), -30% splash |
| Hospital | +1000 HP all, +20% debuff resist, 3 random juggernauts (+min(10000, maxHP)) |
| Sniper Tower | +max(200, 5% atk), damage buff (10%→1.5×, 6%→2×, 3%→3×, 1%→4×) |
| Armory | All start awake (fast regen), +2 starting tokens |
| Nuclear Silo | 30% max building HP as damage + 15% splash, +50% napalm/plague chance |
| Research Lab | See opponent's back row + center; block their vision of non-front buildings |
| Hardened Bunker | Must kill ALL defenders in BOTH bunkers to attack either directly |

Super power deactivates if its building (or HQ) is destroyed.

---

## Points

### Player Points:
- Win attack vs player: **120 pts**
- Lose attack vs player: **80 pts**
- Attack building: **110 pts**

### Empire Points:
- Enemy player reduced to 0/below 200 HP: **1 pt** (lost if revived)
- Building destroyed: **building's point value**

---

## Rewards

- **Class coins** based on win/loss + individual points
- Bonuses for: Veteran level, Dojo level
- Category bonuses (+5-10%): MVP, Player Damage, Tokens Absorbed, KOs, Building Damage, Single Shot Damage, Battle Points
- XP gained per token used (3-5 XP/token) + end-of-battle XP

---

## Player States Summary

| State | Effect |
|-------|--------|
| Sleeping | Slow token regen, extra Assassin damage |
| Stunned | Reduced damage, slow tokens, extra Assassin damage, expires on action |
| Dead (0 HP) | Half damage, no active skills |
| Booby Trapped | Takes damage when healed, building also damaged |
| Burning | 5 dmg/min × 5 min, stackable 3× |
| Explosives | Takes damage when Burned, triggers splash |
| Stim Pack Immune | Resists status effects 25% |
| Last Stand | More counter damage + defense, expires on death |
| Suppressed | Halved counter damage, 50% expire/token |
| Marked | Visible to enemy snipers |
| Poisoned | 2% max HP/token, 25 tokens |
| Napalm | DOT indefinitely, reduced healing |
| Time Bomb | Delayed damage + building damage |
| Plague | % current HP/token, indefinite, building damage |
| Adrenaline Rush | +40% crit rate/damage, 2× counter taken |
| Ghost Tag | +12% incoming damage, reduced defense |

---

## Key Design Principles (for adaptation)

1. **Asymmetric information**: visibility mechanics (front row vs back row, Sniper/Assassin special vision)
2. **Resource management**: tokens as action economy with regen rates
3. **Positional strategy**: 3×3 grid, building placement matters, front-to-back exposure
4. **Role diversity**: each class has a distinct combat niche (tank, DPS, DOT, debuff, stealth)
5. **Building synergy**: buildings provide passive bonuses + super powers
6. **Time pressure**: 2-hour wars, token regen creates pacing
7. **Team coordination**: defender assignment, building upgrades via donations, chat
8. **Win conditions**: points-based (not pure elimination), multiple ways to score

# EVE — Members & Classes Design

## Members

### Starting Roster
- **8 members** at game start: 2 Enforcers, 2 Snipers, 2 Assassins, 2 Demolitionists

### Recruitment
- After defeating an empire, you're presented with **4 candidates** (1 per class) — the best from the defeated empire
- You **pick 1** to recruit
- This means roster grows by 1 per war won
- Higher-level/rarer members come from tougher empires (natural difficulty scaling)

### Stats
- **No individual stats** — all stats are determined by **level + rarity**
- Stats include:
  - Damage vs players
  - Damage vs buildings
  - Damage mitigation
  - Skills (class-determined)
- No RNG stat rolls, no gear, no customization per member
- A level 5 Rare Enforcer is always identical to any other level 5 Rare Enforcer

### Health
- **Full HP reset** at the start of every new battle
- Health is only meaningful **during** an EvE war
- Members don't do anything outside of EvE — no jobs, no idle tasks
- No injuries, no permadeath

### Leveling
- Members do **not** gain XP or level up through play
- Level is a fixed attribute tied to the member's rarity/origin
- Higher-level members are acquired by beating stronger empires

---

## Classes (4 Base)

| Class | Role | Theme |
|-------|------|-------|
| **Enforcer** | Tank/Protection | Stun, absorb, frontline |
| **Sniper** | Vision/Ranged | Suppress, mark, see hidden |
| **Assassin** | Burst/Stealth | Poison, execute, ambush |
| **Demolitionist** | Building/AoE | Burn, trap, explosives, building damage |

### Class Assignment
- **Fixed at recruit** — a member's class never changes
- You build your roster composition over time through recruitment choices

### Roster Strategy
- Start even (2 each) — balanced for early game
- Adjust composition based on **scouting** enemy empires
  - Enemy has heavily upgraded buildings? → Recruit more Demolitionists
  - Enemy has many defenders? → More Assassins to pick them off
  - Need visibility? → More Snipers
- Purely a player strategy/playstyle decision

---

## Rarity

| Rarity | Color | Stat Multiplier |
|--------|-------|-----------------|
| Common | White | 100% (base) |
| Uncommon | Green | 120% |
| Rare | Blue | 150% |
| Super Rare | Gold | 200% |

- Stats scale purely from level × rarity multiplier
- Higher rarity members appear in stronger empires (late game)
- **No fusion/combine system** — acquiring high-level members requires defeating strong empires, not grinding duplicates
- This prevents whales from trivializing progression through "play more time"
- Members are **not unique** — you can have two of the same character (e.g., two Overkills)

---

## Member Pool (from UW Lieutenants)

Source: https://underworld-empire.fandom.com/wiki/Category:Lieutenants

268 named characters available as the recruitable member pool. Each has:
- A name and visual identity
- A fixed class (Enforcer/Sniper/Assassin/Demolitionist)
- A rarity tier
- A level (determined by which empire they came from)

### Sample Names (from UW)
**Trending/Popular**: Overkill, Gustavo, Hotwire, Sandsnake, Duke, Lady Luck, Gunslinger, Anson

**A-Z sampling**: Abdullah, AK, Blade, Caine, Diablo, Fox, Ghost, Hammer, Isis, Jax, Kate, Lotus, Mastermind, Nightshade, Overkill, Phantom, Razor, Salvatore...

### Class Assignment (TBD)
Need to assign each of the 268 characters to one of the 4 classes. Could be:
- Based on their UW abilities/theme (if available)
- Random but balanced distribution
- Manually curated for character flavor

---

## Open Design (Deferred)

- Specific class skills and abilities — big topic, separate doc
- Folding upgraded class (Titan, Ghost, Reaper, Terminator) abilities into base 4
- Full lieutenant-to-member mapping (name → class → rarity)

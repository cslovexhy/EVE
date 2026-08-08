# EVE — Economy Design

## Resources

### 1. Energy (Action Currency)
- **Starting max**: 100
- **Regen rate**: 1 per 5 minutes (288/day passively)
- **Max increases**: +50 per city fully conquered
- **Cost to enter a war**: 10 energy
- **Refill**: Premium currency (Favor Points) can refill energy instantly
- Energy is the gating resource for how many wars you can fight per session

### 2. Money (Primary Currency)
- **Earned by**: winning EvE wars
- **Lost by**: losing EvE wars (risk/reward)
- **Spent on**:
  - Buy/upgrade **properties** (passive income generators)
  - Upgrade **EvE buildings** (very expensive, long-term goal)
- Money is the engine — you fight wars to earn it, invest it to grow stronger

### 3. Favor Points (Premium Currency)
- **Used for**: refilling energy
- **Acquisition**: TBD (daily rewards? achievements? IAP placeholder for future multiplayer?)
- Keeps the game playable in longer sessions without waiting for energy regen

---

## Money Flow

```
Win War → +Money (30% of enemy empire net worth)
  ↓
Buy Properties → Passive Money/time
  ↓
Accumulate → Upgrade EvE Buildings (expensive)
  ↓
Stronger Empire → Win Harder Wars → More Money
```

Lose War → −Money (30% of YOUR empire net worth)

### War Reward/Loss Formula

- **Enemy empire net worth** = 100 × sum of all enemy member levels
- **Win reward** = 30% of enemy net worth
- **Loss penalty** = 30% of your own net worth

Example: Enemy has 10 members averaging level 5 → net worth = 100 × 50 = 5,000 → you win 1,500.
Your empire has 8 members averaging level 4 → net worth = 100 × 32 = 3,200 → you lose 960 on defeat.

This means:
- Beating stronger empires pays more (risk/reward)
- Losing hurts more as you grow (keeps stakes real)
- You can't farm weak empires forever (low reward)

---

## Properties (Static Income)

- **Not EvE buildings** — completely separate system
- Purchased with money
- Generate passive money **per minute**, based on property level
- **Auto-collected to Safe House** (first property you build)
- Upgradeable (more income per level)
- Represent territory control on the city map
- **City-specific property types** — conquering new cities unlocks unique properties
  - e.g., Las Vegas → Casino (high income rate)
  - Each city has its own themed property types with different income curves
- Safe House is the starting/mandatory property — acts as your income vault
- **Properties cannot be lost** — they are permanent virtual investments
- **Money CAN be lost** on war defeat — loss penalty deducts from total cash regardless of where it's stored (Safe House doesn't protect against war losses)
- City/country conquering is the single-player campaign; future PvP is just a showcase stage

---

## EvE Building Upgrades

- Cost: **energy + money** (high money cost)
- **Exponential cost curve** — each level costs significantly more than the last
- Intentionally slow — long-term progression, not something you max in a day
- Upgrades improve: building HP, defender slots, super power strength, etc.
- Strategic choice: which buildings to upgrade first given limited resources

---

## Energy Sinks

- **Wars only** — energy exists solely to gate war entry (10 per war)
- No other energy costs (no scouting, recruiting, training, etc.)
- Simple and clean — energy = how many fights you get

---

## Favor Points (Premium Currency)

- **Real money only** (IAP) — no free earning method
- Used solely for energy refills
- Not a development concern — implement last, balance around free-to-play pacing

---

## Pacing / Session Design

| Timeframe | Activity |
|-----------|----------|
| Per session (30 min) | 3-6 wars (10 energy each), collect property income |
| Per day | ~288 energy natural = ~28 wars max (if no waiting) |
| Per week | Upgrade 1-2 properties, maybe 1 building upgrade |
| Per month+ | Full building upgrades, conquer city sections |

---

## Key Balance Levers

1. **War reward scaling** — early wars give small money, later wars more (incentivize pushing harder content)
2. **Property ROI** — time to break even on a property purchase (should feel good but not instant)
3. **EvE building costs** — exponential? Linear? Should feel like a meaningful milestone
4. **Loss penalty** — lose enough to sting, not enough to soft-lock the player
5. **Energy gating** — prevents binge-grinding, creates natural play sessions (or spend FP to keep going)

---

## Open Questions

1. How much money per war win? Flat? Scaled to enemy strength?
2. How much money lost on defeat? Percentage? Flat?
3. Property income rates — per minute? Per hour? Collected manually or auto?
4. Can properties be lost/raided? Or purely safe investments?
5. EvE building upgrade costs — linear or exponential curve?
6. Any other energy sinks besides entering wars? (Scouting? Recruiting?)

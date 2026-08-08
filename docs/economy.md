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
Win War → +Money
  ↓
Buy Properties → Passive Money/time
  ↓
Accumulate → Upgrade EvE Buildings (expensive)
  ↓
Stronger Empire → Win Harder Wars → More Money
```

Lose War → −Money (setback, not bankruptcy)

---

## Properties (Static Income)

- **Not EvE buildings** — completely separate system
- Purchased with money
- Generate passive money over time (idle income)
- Upgradeable (more income per level)
- Represent territory control on the city map
- Examples from UW: restaurants, clubs, warehouses, fronts, etc.
- Design TBD: how many types, income rates, upgrade costs

---

## EvE Building Upgrades

- Cost: **energy + money** (high money cost)
- Intentionally slow — long-term progression, not something you max in a day
- Upgrades improve: building HP, defender slots, super power strength, etc.
- Strategic choice: which buildings to upgrade first given limited resources

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

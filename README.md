# EVE

Empire vs Empire — a single-player guild war strategy game inspired by Underworld Empire's EvE system.

## Status

**Playable prototype.** Core battle system working with real-time 5-minute battles on a 3×3 grid.

## How to Play

```bash
# First time setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 src/download_portraits.py  # Download character art

# Run
./run.sh
```

### Controls

- **SPACE / E / A / S / D** — Select class (All / Enforcer / Assassin / Sniper / Demolitionist)
- **Click enemy building** — Attack with selected class
- **Click own building** — Defend with selected class
- **R** — Restart (after battle ends)
- **Q** — Quit

## Current Features

- 40 members per side (10 per class) with unique lieutenant portraits
- 4 distinct classes with different stats, attack speeds, and behaviors
- Real-time 5-minute battles with commander-level orders
- Fog of war: flood-fill visibility from entry points (1/4/7/9), destroy buildings to reveal neighbors
- Sniper: stays at range (200px), shoots without approaching
- Assassin: goes stealth after 5s out of combat, invisible + untargetable until engaging
- Demolitionist: primary building destroyer, essential for opening fog of war
- Enforcer: tanky frontline defender
- Mouse-click + keyboard hotkey order system
- AI opponent with scripted attack/defend decisions
- Class stats HUD for both sides
- Defender count bubbles on buildings
- Victory by points, or instant win on full elimination

## Reference Material

- `docs/reference_ue_eve.md` — Parsed mechanics from Underworld Empire's Empire War system
- `docs/vision.md` — Game vision and design direction
- `docs/battle_mechanics.md` — Battle mechanics design
- `docs/economy.md` — Economy design
- `docs/members.md` — Members & classes design
- `docs/presentation.md` — Art style and presentation notes
- `docs/questions.md` — Open design questions

## Tech Stack

- Python 3.14 + pygame-ce
- No external dependencies beyond pygame

## Worklog

### 2026-08-08 — Prototype Built

- Scaffolded project: config, models, engine, orders, AI, renderer, main loop
- Data models: Member (class/level/rarity/HP/stats), Building (HP/defenders), Empire, Order
- Battle engine: 3×3 grid positioning, movement, combat resolution, fog of war
- Order system: mouse-click buttons + keyboard hotkeys (SPACE/E/A/S/D), no cooldown
- AI opponent: scripted attack/defend on timer, class-appropriate targeting
- Renderer: battlefield, buildings with HP bars, member class icons, HUD, battle-over screen
- Downloaded 80 lieutenant portraits from UE Fandom wiki (40 player + 40 enemy)
- Class icons from UE wiki for battlefield representation
- Per-class attack intervals: Enforcer 2.0s, Sniper 2.5s, Assassin 1.0s, Demo 1.8s
- Sniper behavior: stays at range (200px), shoots without approaching
- Assassin stealth: invisible after 5s out of combat, breaks on attack/hit
- Fog of war: flood-fill visibility from entry points (1/4/7/9), destroy buildings to reveal neighbors
- Movement speed tuned to 60% (48px/s base)
- Early battle end on full elimination (all buildings or all members down)
- Defender count bubbles on buildings
- Class roster stats for both player and enemy
- Two-tier visibility: assassins can backdoor building 9, other classes blocked
- "No visibility" feedback when clicking unreachable buildings
- Coordinated AI: assassins+snipers assault together, demos finish buildings, enforcers defend
- AI weighted target selection: 30% each front row (1/4/7), 10% backdoor (9)
- Fullscreen mode with 2x building/member sizes, centered grid layout
- Sniper range targeting: shoots into nearby buildings within range, 50% accuracy on hidden
- Clean UI layout: HUD bar, stats bar, battlefield, order panel with proper spacing
- Removed order cooldown, removed "All" class selection

### 2026-08-09 — All-Ranged Combat + Assets

- Demolitionist: ranged attack (200px), stays at distance for safe building demolition
- Projectile system: visible projectiles (sniper=yellow trail, demo=orange fireball), damage on impact
- Health pack system: 8 packs per battle, revive dead class member at building 3, AI uses packs
- Battlefield background: UE Empire Wars artwork, isometric perspective
- Building placement tool (place.sh): drag-and-drop buildings onto background, saves to JSON
- Building sprites: downloaded 9 UE building images (HQ 2x size, others 1.2x), cropped to content
- Perspective-correct grid: row compression (85%/92.5%/100%) matching fake-3D background
- Ammo system: 10 per member, regen 1 per 10s, can't fire at 0
- All-ranged combat: members stay in buildings, fire across map at visible targets
- No movement needed: visibility is the only range limit
- Defender redistribution: non-enforcers in building 3 (safe backline), enforcers as frontline shields
- Removed miss chances (sniper/demo) — ammo scarcity replaces accuracy as limiting factor
- Passive defense: enforcers absorb shots, no active defender shooting
- Distinct projectile colors: sniper=yellow, demo=orange, enforcer=green, assassin=dark red
- Attack mode toggle: Auto (sustained fire) vs Once (single volley then stop), T key
- Class buttons show ammo count + current attack target
- Battle log: real-time text file with every hit, kill, building destroyed, orders issued
- Run.sh tails battle_log.txt in console while game runs
- No troop movement or defend orders — all positions are fixed from start

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
- Sniper behavior: stops at 200px range, shoots from distance
- Assassin stealth: invisible after 5s out of combat, breaks on attack/hit
- Fog of war: flood-fill from entry points (1/4/7/9) through destroyed buildings
- Movement speed tuned to 60% (48px/s base)
- Early battle end on full elimination (all buildings or all members down)
- Defender count bubbles on buildings
- Class roster stats for both player and enemy

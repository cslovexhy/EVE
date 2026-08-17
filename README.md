# EVE

Empire vs Empire — a single-player guild war strategy game inspired by Underworld Empire's EvE system.

## Status

**Playable prototype.** Core battle system working with real-time 5-minute battles on a 3×3 grid.

## Developer Notes / Red Flags

- **`player_profile.json` is the live save and is now tracked in git** (so it has
  history — an accidental overwrite is recoverable with `git checkout -- player_profile.json`).
  Still, back it up before running anything that can call `GameState.save()`
  (headless verification scripts, `EveLayout`/battle flows) so you don't
  *commit* garbage:
  ```bash
  cp player_profile.json /tmp/eve_profile_backup.json   # before
  cp /tmp/eve_profile_backup.json player_profile.json   # after
  ```
  Prefer constructing throwaway `GameState()` objects in tests and NOT calling
  `.save()`; if a test must save, point `game_state.PROFILE_PATH` at a temp file.

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

### 2026-08-16 — Recruits + Backup Force + Roster Management UI

- **Persisted roster**: the player roster is no longer regenerated deterministically each battle — it's saved in `player_profile.json` as `roster` (active) + `backup` (bench). Legacy saves auto-migrate by seeding the default 40 (`GameState.load` → `default_player_members`). `member_assignments` index the **active** roster and are validated against its size (`_valid_assignments(assignments, size)`). Battles use fresh member copies (`GameState.build_player_empire` + `Member.copy_identity`) so battle state never corrupts the saved roster.
- **Win a war → recruit**: defeating an empire recruits its **top-rarity** member (ties broken by highest level, then random — `models.top_rarity_recruit`) into your **Backup Force** (bench, cap `BACKUP_FORCE_CAP = 80`). A `RecruitPopup` reveals the acquisition on the victory screen. Works for both regular wars and the birthplace fight (`main._acquire_recruit`).
- **Force tab (roster management)**: EVE Layout gained a 4th tab, **Force**, using the full screen width (the building grid is hidden here) with two wide, well-spaced columns — Active Roster (N/cap, header turns red when over cap) and Backup Force (N/80). Both columns are **grouped by class** with headers like the Assign tab, and each row shows the member's name, level, and full rarity word in its rarity color (gray/green/blue/gold). Select a member and use the bottom action bar: **Move to Backup**, **Activate** (backup → roster, auto-assigned to the HQ slot / least-full building), or **Kick Out** (permanent). Moves re-index assignments and persist immediately.
- **Selected-member stat card**: selecting anyone in either Force column shows a detail card (bordered in the rarity color) with live `get_stats()` — Health, Damage vs members, Damage vs buildings, Mitigation, Attack interval, Move speed — so a Super Rare high-level recruit visibly out-stats a Common one.
- **Scalable member UI**: the old "Members" tab (now **Assign**) and both Force columns use a clipped viewport + mouse-wheel scrolling (`_Screen.handle_scroll`, `MOUSEWHEEL` dispatch) with scrollbars, so 80-member lists no longer run off-screen.
- **War-start cap gate**: activating recruits can push the active roster past the HQ cap; starting a war is then **blocked** by a `CapBlockedPopup` telling you to bench members (or level the HQ) — `GameState.roster_over_cap()` checked in `main` before launching.
- Verified headless: roster/backup persistence + legacy-save migration, recruit pick is a copy (enemy untouched), activate/bench/kick keep assignments valid, backup + HQ caps enforced, and an **end-to-end battle win that recruited and persisted a super-rare member**. 32 unit tests pass (`tests/test_roster.py` +11, `tests/test_bunker_ai.py`, `tests/test_buildings.py`).

### 2026-08-16 — Bunker Shield: Stop Wasting Ammo on Shielded Bunkers

- **Firing guard**: a member ordered onto a bunker now stops firing (drops the target, returns to defending) the moment that bunker becomes a shielded, defenderless dead-end — `engine._update_attacker` checks `bunker_block_reason`. Protects both the AI and the player from burning ammo on an invulnerable, empty bunker.
- **AI targeting**: the AI filters candidate targets through `engine.worthwhile_target` (reachable AND not a shielded/empty bunker) across opening/assault/push/cleanup, and abandons a current target that becomes a shielded dead-end (class-independent check so assassin-only backdoors aren't wrongly dropped).
- Verified headless against the live save: with the guard disabled the AI wasted shots on shielded bunkers; with it enabled, **0 wasted shots**. `tests/test_bunker_ai.py` covers target selection and the persistent-fire path.

### 2026-08-16 — Track the Save File in Git

- **`player_profile.json` is no longer git-ignored** — it's now tracked so the
  save has history and an accidental overwrite is recoverable via
  `git checkout -- player_profile.json`. (`player_setup.json` and `battle_log.txt`
  stay ignored as pure runtime churn.) Red-flag note updated accordingly.

### 2026-08-16 — HQ Leveling + Member Cap

- **HQ gates roster size**: no HQ → 40 members; each HQ level adds +10, up to **Lv4 = 80** (`BASE_MEMBER_CAP`, `HQ_MEMBERS_PER_LEVEL`, `HQ_MAX_LEVEL`).
- **HQ HP scales with level**: Lv1 1300 → Lv2 1700 → Lv3 2200 → Lv4 3000 (`HQ_LEVEL_HP`); `Building.apply_type_hp` uses it for HQs.
- **Escalating level-up cost**: Lv2 $8k · Lv3 $20k · Lv4 $45k (`HQ_LEVEL_UP_COST`), on top of the $6k to build the HQ. `buildings.can_level_hq` / `level_up_hq`.
- **EVE Layout**: selecting the HQ shows an "Upgrade HQ to LvN" row (HP / roster cap / cost); a "Roster cap: N (HQ LvX)" readout sits under the money chip. `building_levels` persists in `player_profile.json`.
- **Enemy HQ matches army size**: `enemy_gen` sets the enemy HQ level from its member count (Lv = ceil((members−40)/10), clamped 1–4), so cap ≥ member count and HQ HP reflects strength.
- `Empire.hq_level()` / `member_cap()`; `engine` applies per-slot `building_levels` when setting types.
- Verified headless: cap 40/50/60/70/80, per-level HP, level-up costs + persistence, enemy HQ (weak Lv1 / Danville Lv3 / Richmond Lv4), and the EVE Layout level-up click; 17 unit tests pass.

### 2026-08-16 — Territory Rollup, Control % + Paginated Map

- **Control rolls up every level**: `world_map.control/county_control/state_control/country_control` compute owned/total cities and % for any region from the conquered set. Each map tile now shows its control (`county/state/country`: "x/y cities · NN% controlled"; cities: pop, GDP/capita, crime, gang/police power, reward).
- **Owned propagates upward**: a county/state/country tile is marked **✓ owned** (green) once 100% of its cities are taken — so you can see at a glance where to push next. A control summary for the region you're viewing sits beside the breadcrumb (e.g. "Virginia: 12% controlled (29/241)").
- **Pagination**: the map pages when a level overflows (VA = 133 counties → 8 pages) with Prev/Next buttons, a page indicator, and ←/→ keys. Page resets on drill-down/back.
- **Birthplace win** now shows a "Congratulations! You are now in control of {city}, {state}." screen (Continue only); the stale "Press R to restart" battle-over hint is gone (retry only exists on the harsh birthplace loss).
- Verified headless: rollup math, owned propagation, 8-page county navigation, 17 unit tests pass.

### 2026-08-16 — Birthplace as First Battle + Region Info in Map

- **Birthplace is now a fight, not a gift**: picking a starting city stages you as a new force and launches a battle against that city's underworld (scaled from its `underworld_power`). **Win → you own the city and your empire begins. Lose → a game-over screen ("Your path to Godfather ends in {city}, {state}.") resets you to try again.** New `GameOverScreen`; `main._choose_birthplace` loops pick→fight→win/lose.
- `main._fight_city()` extracted and shared by birthplace and regular wars.
- **Map now shows region info** on every city tile — population, GDP/capita, crime rate, gang (underworld) power, police power, and (in war mode) reward. The confirm popup shows the full stat block so you can pick a winnable target.
- Verified headless: birthplace map + stats popup + game-over render; all modules import; 17 unit tests pass.

### 2026-08-16 — Real US Geography + Data-Driven Enemies (Virginia)

- **Data pipeline** (`tools/build_world_data.py`): joins BEA county GDP + Census population + County Health Rankings homicide rate + Census places into a normalized `Country ▸ State ▸ County ▸ City` dataset. Handles Virginia's independent cities (county-equivalents) and BEA "combination area" GDP gaps (estimated from population × state median GDP/capita). Generates `data/world/virginia.json` (133 county-equivalents, 241 cities). `--state XX` builds any state.
- **Two powers per city**: `underworld_power = K_U × crime_rate × population` (conquerable rival gangs) and `police_power = K_P × GDP` (raid boss, never conquered — deferred to a later phase). Police > underworld everywhere (ratio 2.4×–420×). `reward` ∝ city GDP percentile.
- **World layer** (`world_map.py`): loads `data/world/*.json`; 4-part city ids; nav + metric + scope-id helpers.
- **Scope gating** (`GameState`): birthplace = a city; scope ladder **county → state → country → world** (own the whole county to unlock the state, etc.). Self-heals stale saves whose home city isn't in the current world data.
- **Enemy scaling** (`enemy_gen.py`): `underworld_power` → member count (up to the 80 cap), level (1–15), rarity mix, and building fortification via log-scaling. Engine skips enemy randomization when a pre-built enemy is supplied.
- **Map screen**: drills `Country ▸ State ▸ County ▸ City`, shows each city's UW/police power + reward, gated by scope. Wars build the scaled enemy from the target's `underworld_power` and pay its `reward` on a win.
- Verified headless: data loads, scope ladder advances on full-region conquest, enemy scaling is monotonic in power, stale-profile self-heal, reward payout, 17 unit tests pass. **Police raid bosses are the next phase.**

### 2026-08-16 — Birthplace Selection + Map-Visibility Gating

- **Birthplace on first run**: with no `home_city`, the game opens a birthplace picker (`MapScreen` `mode="birthplace"`) — drill Country ▸ State ▸ City and "Start Here" sets your home city (auto-conquered) and home state/country. Backing out quits.
- **Scope gating** (`GameState.scope()` → `state` / `country` / `world`):
  - **state** — only your home state's cities are visible/challengeable.
  - **country** — conquering your whole home state unlocks all of that country's states/cities.
  - **world** — conquering the whole country unlocks the other countries.
- `MapScreen` derives a `min_level` from scope so navigation is locked to the unlocked region (Back stops at that level), with a status banner explaining what to conquer next to expand.
- New `world_map.py` holds `MAP_DATA` + helpers (`state_city_ids`, `country_city_ids`, etc.), shared by `screens` and `game_state` (no circular import). `GameState` gained persisted `home_city`, `set_birthplace`, `home_location`, `owns_entire_state/country`.
- Verified headless: 17 unit tests pass; scope smoke test walks none→state→country→world, birthplace pick, Nevada-locked navigation, and `home_city` persistence. Existing save migrated (`home_city` = Las Vegas).

### 2026-08-15 — Consolidated Base Management + Direct War Launch

- **EVE Layout is now the single base-management screen** with three tabs (TAB to cycle):
  - **Upgrade** — click a slot, buy an upgrade (money-gated by chain/limits)
  - **Arrange** — click two slots to swap their buildings *and* their assigned defenders
  - **Members** — click a member in the roster, click a slot to assign them
- **Everything persists to `player_profile.json`** on every change: money, `BuildingType` layout, and member assignments (9 lists of roster indices, validated to cover all 40 members).
- **Wars skip the pre-battle setup screen** — `BattleSession` now takes `building_order` + `member_assignments` directly and launches straight into the fight. `setup_ui.py` is retired from the flow (file kept).
- `GameState` gained `member_assignments` + `default_member_assignments()` + `ensure_member_assignments()`; `apply_to_empire` now also seeds defender assignments.
- Verified headless: 17 unit tests pass; smoke test exercises all three tabs (upgrade/swap/assign), a save→load roundtrip, and the direct war launch (slot HP + defender placement applied with no SetupUI).

### 2026-08-15 — Screen Navigation + Map + Functional Building Upgrades

- **Screen architecture**: new `main.py` navigator drives a screen state machine — Main Menu → EVE Layout / Map → Battle. Battle loop extracted from `main.py` into `battle_session.py` (`BattleSession.run()` returns the winner; ESC forfeits, window-close still quits).
- **Persistent profile** (`game_state.py`): `GameState` holds money, a 9-slot `BuildingType` layout, and conquered cities; JSON save/load to `player_profile.json`. Helpers: `apply_to_empire`, `empire_net_worth`, `war_reward` (30% of enemy net worth per economy doc).
- **Main Menu**: buttons for **Map**, **EVE Layout**, **Quit**.
- **EVE Layout page**: the real upgrade hookup — click a building slot, see valid/affordable upgrade targets (gated by `can_upgrade`: chain, per-type limit, funds), buy with `upgrade_building`; money deducts and the layout persists.
- **Map page**: layered **Country ▸ State ▸ City** drill-down; click an unconquered city → **Wage War?** popup → launches the battle. Winning marks the city conquered and awards money. Conquered cities are flagged and non-clickable. (`MAP_DATA` is a provisional placeholder — map structure in `docs/questions.md` §4 is still open.)
- **Interop**: `buildings.building_order_from_layout` / `apply_building_order` bridge the persistent `BuildingType` layout to the renderer/setup `building_order` (duplicates now allowed, e.g. many Warehouses). `SetupUI` accepts a seeded `building_order` and no longer requires a unique-permutation layout.
- Verified headless: 17 unit tests pass; smoke test covers imports, profile apply, upgrade+persist, layout→HP roundtrip (Armory 750, HQ blocked at $5k), and map drill-down → popup → conquer.

### 2026-08-15 — Building Upgrade Chain + Per-Type HP

- Building type system: `BuildingType` enum (9 types) + config-driven `BUILDING_TYPES` (HP, cost, chain, max count, sprite name-index)
- Upgrade chain: every building starts as **Warehouse** →
  - Warehouse → HQ / Armory / Hospital / Sniper Tower / Research Lab / Nuclear Silo (each unique) or Safehouse (max 2)
  - Safehouse → Bunker (max 2)
- Per-type HP: Warehouse 500 (base), Safehouse 650, Armory/Hospital 750, Research Lab 800, Sniper Tower 850, Nuclear Silo 950, **HQ & Bunker 1300** (tankiest)
- Money-based upgrade costs: Safehouse 1,500 · Armory/Hospital 2,500 · Research Lab/Sniper Tower 3,500 · Bunker 5,000 · HQ 6,000 · Nuclear Silo 10,000 (starting money 5,000)
- `buildings.py`: upgrade validation + apply logic — enforces chain (`invalid_chain`), per-type limits (`max_count_reached`), funds (`insufficient_funds`), slot bounds; deducts money and refreshes HP on success
- `Building` now carries `building_type`; HP is derived from type. `Empire` gained `money`, `apply_building_layout`, `count_building_type`
- Engine applies each side's `building_order` → building types before battle so combat HP reflects per-type HP (player + enemy)
- 17 unit tests (`tests/test_buildings.py`) covering chain, uniqueness/limits, costs, insufficient funds, and HP — all passing

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

### 2026-08-12 — Battle Setup + UX Improvements

- Half attack mode: fires only half (rounded up) of selected class, default mode, reduces ammo waste
- Attack mode rotation: Half → Once → Auto → Half (T key)
- Health pack UX rework: press H → click building to revive highest-HP dead defender there
- Pre-battle setup screen with two tabs (TAB to switch, ENTER to start):
  - Buildings tab: click-swap building arrangement across 9 grid slots
  - Members tab: click member then click building to assign
- Setup grid mirrors battlefield layout (3 2 1 / 6 5 4 / 9 8 7)
- Player setup persists to player_setup.json across restarts
- Enemy building randomization: HQ excluded from front+center slots, Armory/Hospital excluded from front
- Enemy member assignment: all attackers in HQ, enforcers distributed across all buildings
- Projectile re-checks defenders on impact — healed defenders absorb shots properly
- Battle-end reveal: all enemy members shown (stealthed assassins, fog of war) after battle ends
- Renderer uses empire building_order for correct building sprites per slot

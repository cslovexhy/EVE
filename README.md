# EVE

Empire vs Empire — a single-player guild war strategy game inspired by Underworld Empire's EvE system.

## Status

**Playable prototype.** Core battle system working with real-time 5-minute battles on a 3×3 grid.

## Developer Notes / Red Flags

- **Save files are sacred — never delete or overwrite one without backing it
  up first, and NEVER `rm` anything under `profiles/`.** The player's saves are
  `player_profile.json` (legacy single save) **and** every file under
  `profiles/<slug>.json` (the multi-profile saves). Treat the whole `profiles/`
  directory as live user data. Both `player_profile.json` and `profiles/` are
  **tracked in git** so an accidental overwrite is recoverable with
  `git checkout -- <path>` — but a file that was never committed is **not**
  recoverable, so **commit or back up new profiles before running anything that
  can touch them.** Back up before running anything that can call
  `GameState.save()` (headless verification scripts, `EveLayout`/battle flows):
  ```bash
  cp player_profile.json /tmp/eve_profile_backup.json   # before
  cp /tmp/eve_profile_backup.json player_profile.json   # after
  cp -r profiles /tmp/eve_profiles_backup               # before (whole dir)
  ```
- **Tests / smoke scripts MUST NOT write to the real saves.** Prefer throwaway
  `GameState(path=...)` objects and do NOT call `.save()`; if a test must save,
  point it at a temp file (`GameState.load(tmp_path)` / monkeypatch
  `game_state.PROFILE_PATH`) and sandbox `profiles.PROFILES_DIR` +
  `profiles.LEGACY_PATH` to a `tempfile.mkdtemp()` dir. Never let a test run the
  real `profiles.migrate_legacy()` / `create_profile()` against the real
  `profiles/` directory.

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

### 2026-09-12 — Offline voice control (always-on, parallel to keyboard/mouse)

- **You can now play by voice, fully offline.** A always-listening voice layer runs from game start to game exit and injects the **same** input the keyboard/mouse already produce — it never supersedes them. Both input paths are live at all times. Recognition is 100% on-device via **Vosk** (small English model, ~40MB) with a **closed 43-word grammar** for accuracy; no network, no API keys, no cloud.
- **Strict 1:1 mapping to existing controls.** Every command is either a single keystroke the game already handles or a numbered building target that reuses the exact same order logic as a mouse click:
  - **Battle (numbered):** `"{class} {n}"` selects the class **and** attacks enemy building *n* (e.g. "sniper three"); `"heal {n}"`; `"nuke {n}"`. Building numbers are spoken **1-based to match the on-screen label** and converted to the engine's 0-based index. Attacks honor the same visibility / attack-block checks as a click; nuke goes through `launch_nuke`; heal through the health-pack path. **"demo"** is the spoken word for the demolitionist (that full word isn't in the small model's vocabulary).
  - **Battle (plain keys):** `mode` (T), `auto`/`manual` (Tab), `speed up`/`speed down` (+/-), `forfeit` (Q), `sound` (M).
  - **Menu / map / layout:** `map`, `layout`, `quit`, `back`/`menu`, `next tab`, `zoom in`/`zoom out`, `pan left/right/up/down`, `reset`, `next page`/`previous page`, `yes`/`no`.
- **Architecture — additive, not invasive.** Two new modules: **`src/voice_intents.py`** (a dependency-free transcript→`Intent` parser) and **`src/voice.py`** (a `VoiceController` running Vosk on a **daemon thread** that pushes `Intent`s onto a thread-safe queue). The main loop calls `voice.pump()` once per frame; keystroke intents become **synthetic `pygame` `KEYDOWN`** events posted into the real event queue (so existing handlers react with no changes), and numbered battle commands are buffered for the `BattleSession` to consume via `voice.poll_battle_intents()`. Numbered commands are ignored outside battle context.
- **Integration footprint is tiny:** one `voice.pump()` line in `screens._Screen.run()` (covers every menu/map/layout screen), one `voice.pump()` + `poll_battle_intents()` block in `battle_session._handle_events` (new `_handle_voice_battle_intent` reuses existing order/nuke/heal logic), and lifecycle in `main.py` (`voice.start()` after audio init, `voice.set_context(...)` on transitions, `voice.stop()` in a `finally`). No existing handler logic was rewritten.
- **Safe by default, like `sound.py`.** If Vosk/sounddevice/the model/the mic are unavailable (headless, CI, or **denied mic permission** — macOS PortAudio `-9986`), the whole layer is a **no-op** and the game behaves exactly as before. Any error on the voice thread is swallowed. **`--no-voice`** disables it entirely; the daemon thread dies with the process so there's never a lingering listener. There is **no wake word** by default (a wake word can be re-enabled in the parser).
- **Deps:** added `vosk==0.3.44` and `sounddevice==0.5.6` to `requirements.txt` (both ship universal wheels that import on Python 3.14). The model is committed in-repo at `models/vosk-model-small-en-us-0.15/` (~68MB) so the game just works on a fresh clone — no download step, no first-run setup.
- Verified: **157 unit tests pass** (`tests/test_voice.py` +16 covering the full grammar, wake-word gating, intent→key routing, and the no-op fallback); a headless end-to-end sim confirmed a spoken "sniper" posts a synthetic `K_s` `KEYDOWN`, "map" posts a click at the menu button, and numbered attacks buffer for the battle session (and drop outside battle). **Live saves were byte-for-byte unchanged** (shasums matched before/after). Changed `src/main.py`, `src/screens.py`, `src/battle_session.py`, `requirements.txt`; added `src/voice.py`, `src/voice_intents.py`, `tests/test_voice.py`.

### 2026-09-04 — AI targeting personalities (deterministic per-city, per-side)

- **The enemy AI now has swappable targeting personalities.** The AI's building-choice logic was a single value-scoring model; it's now driven by a **profile** that only changes *how a reachable building is scored* — all the shared wave/phase machinery (reachability, class batching, health packs) is untouched. Six profiles in the new **`src/ai_profiles.py`**: `value` (**Balanced** — reproduces the old formula exactly), `easy_path` (**Opportunist** — hits the least-defended building), `hard_path` (**Juggernaut** — dives the most-defended), `hospital_destroyer` / `armory_destroyer` (**beeline one building type**, then degrade to the value formula once it's gone), and `random_path` (**Erratic** — any reachable target uniformly).
- **Deterministic, per-city, per-side assignment.** `ai_profiles.profile_name_for(city_id, police=...)` hashes the seed with **md5** (not the process-salted builtin `hash()`, so it's stable across runs). The seed is the **full city id folded with the side**, so a city's **gang and its police boss get independent — but each individually stable — strategies**. Police is always `hard_path` (the toughest personality); gangs draw from a weighted pool (`config.AI_PROFILE_GANG_POOL`). All bonuses/weights are config-tunable (`config.AI_PROFILE_*`).
- **Strategy is visible in the city profile popup.** The map's city-detail popup now shows a **"Gang strategy: …"** line (and **"Police strategy: …"** on the police popup) via `enemy_gen.city_strategies(city_id)` — computed without building the empire — so you can scout the personality and plan your base setup before committing.
- **Wiring.** `enemy_gen.build_enemy(..., profile_seed=city_id)` stamps `empire.ai_profile_name`; `describe()` gained an optional `profile_seed` that adds the strategy labels. `BattleAI(..., profile=...)` accepts an `AIProfile` or a name (None → the default `value` profile — this is the fallback the **player-side TAB auto-fight** uses); `_target_score` delegates to `profile.score(building, defenders, rng)`. `battle_session` passes the enemy's `ai_profile_name`; `main._fight_city` passes the target city id as the profile seed for both the gang and police paths. Also fixed a **stale class docstring** in `ai.py` that still described the long-removed position-weighted-random targeting.
- Verified: **141 unit tests pass** (`tests/test_ai_profiles.py` +22 covering each profile's scoring order, the value profile == legacy formula, md5 seed stability, police→hard_path, gang-from-pool, and the enemy_gen/describe integration); a headless end-to-end smoke test confirmed two different cities get different gang strategies and `BattleAI` picks up the empire's profile. Live saves were **byte-for-byte unchanged** by the test run (checksums matched before/after). Changed `src/ai.py`, `src/ai_profiles.py` (new), `src/config.py`, `src/enemy_gen.py`, `src/main.py`, `src/battle_session.py`, `src/screens.py`, `tests/test_ai_profiles.py` (new).

### 2026-08-30 — Zoomable/pannable US map (click tiny states like DC)

- **Zoom + pan on the visual US map.** Small states — DC most of all (a ~12 px² speck at default zoom) — were effectively unclickable. `USMapScreen` gained a view transform layered on the base projection: **mouse wheel zooms toward the cursor** (focus-preserving), **arrow keys pan**, **+/- zoom**, **R resets**, plus a **Reset View** button and a live zoom readout. Zoom clamps to **1x–12x**; pan is clamped so the map can't drift entirely off-screen. The map is **clipped to a content band** so it never overdraws the title/legend/controls when zoomed. Verified headless: DC's clickable area grows ~19× at 4.3× zoom (point-in-polygon hit confirmed), zoom homes in on the cursor, and clamps hold. 119 unit tests still pass.

### 2026-08-30 — Multiple save profiles (choose / create / delete at startup)

- **Multi-profile saves.** The game now opens on a **Profile Select** screen: pick an existing save to play, or **+ New Profile** (free-text name entry) to start fresh. Each profile is its own file under `profiles/<slug>.json`, in the exact format `GameState` already uses. Rows show a quick summary (money · cities conquered · home city). **Delete** a profile via the red **X** on its row (Y/N confirmation).
- **Per-file `GameState`.** `GameState` gained a non-serialized `path` (where it loads/saves) and a persisted `profile_name`. `GameState.load(path=...)` / `save()` use it; `load(path=None)` resolves the legacy `PROFILE_PATH` at call time (so existing tests that monkeypatch it still work). `save()` creates the parent dir as needed.
- **`profiles.py`** owns the directory + name↔path mapping (`_slugify`), listing (sorted by display name), create/load/delete, light summaries for the screen, and a one-time **legacy migration**: on first launch, an existing `player_profile.json` is copied into `profiles/default.json`, so current progress carries over untouched as the "default" profile. Idempotent (no-op once any profile exists).
- **`main.py` startup** now shows `ProfileSelect` before the main menu, binds the chosen/created `GameState`, initializes audio from that profile's `sound_on`, and only runs the birthplace picker for a fresh profile (no `home_city`).
- Verified: **119 unit tests pass** (`tests/test_profiles.py` +12 covering CRUD, slugify, duplicate/blank rejection, save/load round-trip, summaries, and migration idempotency); a headless smoke test drove the ProfileSelect screen's own handlers through create/select/delete/duplicate; the live `player_profile.json` was byte-for-byte **unchanged** by the test run.

### 2026-08-30 — All-states data + county reconciliation, sound off by default, smarter enemy AI

- **County data now reconciles to its cities.** The ETL (`tools/build_world_data.py`) mapped only *incorporated* places and allocated county GDP by each town's share of the **whole** county population, so a county's cities summed to **less** than the county (the unincorporated remainder was silently dropped). Added a **`"<County> (unincorporated)"` remainder city** per county carrying the leftover population + GDP (GDP subtracts the already-rounded town slices so children sum **exactly** to the parent). Whole-county cases (independent cities, place-less counties) are unchanged — their single city already equals the county. The remainder is a normal, challengeable city, so you must clear a county's unincorporated gangs (usually the largest slice of a rural county) before it reads 100% controlled.
- **Real data for all 49 map-reachable states** (lower-48 + DC). Expanded `STATE_FIPS`/`STATE_NAME` from 5 states to the full 50 + DC and re-ran the ETL, replacing the ~575-byte dummy placeholders. **3,109 counties / 16,520 city-leaves, 0 population or GDP mismatches.** AK/HI are intentionally left out — they're excluded from the visual map (`tools/build_us_map.py` `EXCLUDE`) because one flat equirectangular projection can't fit them without squashing the lower-48, so world data for them would be unreachable/orphaned. DC was already present (it's just a tiny dot between MD and VA).
- **Sound effects OFF by default**, with the preference **persisted**. New `GameState.sound_on` (default `False`) is loaded/saved with the profile; `main.py` inits the mixer from it (legacy saves default off). CLI overrides for one run: `--sound` forces on, `--mute` forces off. The in-battle **M** toggle now writes the choice back so it sticks across restarts. (There is no on-screen button — sound is keyboard-toggled with M; top-right HUD is unaffected.)
- **Enemy AI: enforcers now fight.** The old "enforcers stay home to defend, attack only as a last resort" doctrine was stale movement-era logic — combat is all-ranged and nobody moves, so an idle enforcer is just wasted fire (there is no "hold for defense" anymore). Enforcers are now **batched into every wave** (`_plan_opening`/`_plan_assault`/`_plan_push`) alongside assassins/snipers/demos, gated by the same front-door reachability check. Verified headless: enforcers issued attack orders throughout opening/assault (previously 0 outside the rarely-reached cleanup phase).
- **Enemy AI: value-based target selection.** Replaced the fixed position-weighted-random target pick with a **building score** — the AI now focuses the highest-value building it can currently **see/reach**. Score = building-type value + sum of live-defender values, config-tunable in `config.py`: defender **2**, enforcer **1**, **armory 20**, **hospital 10**, everything else **5** (`AI_TARGET_SCORE_*`). Wired into opening/push/cleanup (`_best_target` over reachable slots, ties broken randomly); `_plan_assault` still owns the "commit demos once defenders thin out" transition. The same AI drives the player side under **TAB**, so auto-fight benefits too. Verified: AI picks a reachable armory (20) over warehouses (5); scoring math checks out.
- Verified: **107 unit tests pass**; live save untouched (tests use throwaway/temp-path `GameState`). Changed `src/ai.py`, `src/config.py`, `src/game_state.py`, `src/main.py`, `tools/build_world_data.py`, and regenerated `data/world/*.json`.

### 2026-08-23 — Sniper/Assassin rebalance + skills, heal & roster fixes, richer battle log

- **Sniper vs Assassin rebalance** (all-ranged combat made the old melee-era numbers stale): swapped **both** base damages so neither class dominates the other on both axes — sniper now `damage_player 20 / damage_building 6`, assassin `15 / 8`. Attack intervals untouched (the assassin's fast unload stays its niche).
- **Sniper CRIT**: per-shot-vs-member crit chance by rarity (**5/10/15/20%**) dealing **1.5×** damage (`config.SNIPER_CRIT_CHANCE`, `SNIPER_CRIT_MULT`). Logged as `CRIT!`.
- **Assassin DECAPITATE**: chance by rarity (**10/20/30/40%**) to **instakill** a target already below **20% HP** (`ASSASSIN_DECAP_CHANCE`, `ASSASSIN_DECAP_HP_THRESHOLD`); otherwise a normal hit. Logged as `DECAPITATE!`. Skills resolve at projectile impact (`engine._apply_class_skill`); projectiles now carry `shooter_rarity`.
- **Heal picks the strongest**: `Empire.heal_building` now revives the **highest-max-HP** dead defender in a building (ties by level) instead of a random one, so a pack is never wasted on a weak member. Shared by player (H-click) and enemy AI.
- **Force-tab activation bug fixed**: activating a backup member no longer reshuffles the whole roster's building assignments. Root cause: `move_to_roster` grew the roster then called `ensure_member_assignments`, which saw a size mismatch and regenerated the distribution (scattering enforcers). Now the new member is appended directly into **building 3** (`config.DEFAULT_ACTIVATE_SLOT`), preserving every existing assignment.
- **Battle log is now self-diagnostic**: each battle log opens with a `=== BATTLE SETUP ===` dump (both sides, per-slot building type + HP + each defender's name/class/level/rarity/HP), the file is truncated fresh per battle, member-hit lines carry `@bldg N`, and shielded-bunker absorptions are tagged `[BUNKER SHIELD: 0 structural dmg]`. (`tools/fight_arlington.py` is a headless diagnostic runner.)
- Verified: **92 unit tests pass** (`tests/test_class_skills.py` +11; `test_heal.py` / `test_roster.py` updated); a live Arlington police battle logged 73 crits + 23 decapitates and both bunkers fell correctly; live save untouched.

### 2026-08-23 — Visual US states map + adjacency-based unlocking

- **Real-shape US map at the states level.** New `USMapScreen` draws each lower-48 state (+ DC) as a filled polygon, color-coded by conquest progress and labelled `"AB  NN%"`. Clicking an unlocked state drills into its county/city list (existing `MapScreen`, now launchable pinned to one state via `start_state`, Back returns to the US map); a locked state shows an adjacency hint.
- **Adjacency-based unlocking replaces the old 100%-hierarchy gate.** A state is challengeable if it's your home state or if any **bordering** state's control fraction ≥ `config.STATE_UNLOCK_THRESHOLD`. Threshold is **0.01 for testing** (documented intended value 0.50). `world_map.state_unlocked` + a static 48-state adjacency table drive it; `GameState.state_unlocked` wraps it with the home state.
- **Color buckets** (`world_map.state_color_bucket`, relative to the unlock bar X): gray locked · red 0–10% of X · orange 10–30% · yellow 30–100% · green ≥ X.
- **Data pipeline.** `tools/build_us_map.py` reads a public-domain per-state GeoJSON (PublicaMundi/census, cached in `data/raw/`), drops AK/HI/PR, simplifies + equirectangular-projects each state to normalized 0..1 coords with centroids, and bakes `data/us_states_map.json` (49 states, ~2000 pts, adjacency). The renderer just scales 0..1 into its on-screen rect. `tools/gen_dummy_states.py` seeds a 1-county/1-city placeholder for every state (Virginia keeps its real 133-county data) so all states are enterable for testing.
- Verified: US map renders correctly (recognizable shapes, labels, legend); VA (home, ≥1%) is green and its 6 neighbours unlock while the rest stay locked; clicking a state routes to its county list; point-in-polygon, color buckets, and symmetric adjacency all unit-tested. **80 unit tests pass** (`tests/test_us_map.py` +12); live save untouched.

### 2026-08-23 — Battle sound effects

- **8 SFX wired into battle**, each auditioned and approved: per-class fire (assassin/sniper = Kenney CC0 lasers; enforcer = real Desert Eagle; demolitionist = rocket launcher), member death scream, demolitionist building-hit explosion (trimmed to 1.5 s so rapid fire doesn't smear), building-destroyed collapse, and nuke detonation. Deliberately **no** generic member-hit sound and **no** building-hit sound for non-demo classes (avoids audio spam).
- **`sound.py` manager** — thin, headless-safe wrapper over `pygame.mixer`: if the mixer can't init (no audio device / dummy driver / CI), every call becomes a no-op instead of raising, so unit tests stay silent and green. Preloads a bank keyed by logical name, per-event volume trims, master volume, and a mute toggle.
- **Triggers** (`engine.py`): `play_for_class` on each shot fired; `member_death` on any kill (projectile + nuke blast); `building_hit_explosion` only for `ProjectileType.DEMO` building hits; `building_destroyed` on collapse; `nuke` on launch. `main.py` calls `sound.init(muted="--mute" in argv)`; **M** toggles mute mid-battle (`battle_session`).
- **Assets** live in `assets/sounds/*.ogg` (44.1 kHz, tracked in git — small & license-clean) with `CREDITS.md` (Kenney CC0 + Pixabay/Freesound Content License, no attribution required).
- Verified: sound init is a safe no-op under the dummy audio driver; **68 unit tests pass**; a scripted real-audio run fired each class, a death scream, a demo explosion, and a building collapse without errors; live save untouched.

### 2026-08-23 — No untargetable members: act on any visible slot

- **Problem:** a nuke damages members and the building independently, so it could flatten a building while its occupants survived — leaving a **live member orphaned in a destroyed slot**. Since every attack/nuke/heal/click path gated on `not building.destroyed`, that member became **untargetable** (and unhealable) for the rest of the battle.
- **Fix — a slot is actionable while there is still something there.** New engine helpers `slot_has_live_member` / `is_slot_targetable` (targetable = has a living member, even in rubble, OR a standing building). All the `destroyed` gates on *actions* now defer to this:
  - **Attack** (player click + AI target phases, funnelled through `worthwhile_target`, which now rejects only truly-dead slots): you can fire into a destroyed enemy slot to finish off orphaned members.
  - **Nuke** (player target picker + enemy auto-target): can target rubble slots that still hold live members; the blast already damaged members regardless of building state.
  - **Heal** (own slots — player H-click, AI, and `Empire.heal_building`): revives dead members orphaned in a destroyed slot, in place.
- **Unchanged rules:** building *powers* still deactivate when their building is destroyed (`_active_of_type`); the double-bunker shield still zeroes structural damage; a destroyed slot with **no** living members is a dead slot (not targetable, heal returns None, pack preserved). Visibility already treated destroyed slots as visible, so no fog change was needed.
- Verified headless: a live member orphaned in rubble is targetable and can be finished off (slot then becomes non-targetable); a dead orphan in rubble heals back to full; empty destroyed slots stay dead. **68 unit tests pass** (`tests/test_projectiles.py` +5, `test_heal.py` updated); live save untouched.

### 2026-08-23 — Unified projectile damage (close the heal-cancel exploit)

- **Building + defenders are one damage sink, resolved at impact.** Previously a shot locked onto a specific `target_member` at fire time and was **cancelled outright** if that member died before impact — so watching the incoming barrage and letting/healing the targeted defender away made a full volley deal **zero** damage (a strong enough exploit to beat the toughest gang). Now a shot in flight is never cancelled: at impact the engine recomputes live defenders at the target building and either damages a live defender (member damage) or, **if none remain, rolls the damage straight onto the building** (building damage).
- **Bunker shield is the only zeroing condition.** A defenderless bunker still takes **0** structural damage while the double-bunker shield is up (any bunker on that side still holds a live defender) — intended, unchanged.
- **Legitimate defence still works:** healing to keep a defender alive still absorbs the shot into that defender and spares the building; you just can't make the barrage *disappear* anymore.
- **Implementation** (`engine._update_projectiles`): removed the "target member died → cancel" early-out (dead-target shots now steer to the building and land); every projectile now carries `target_building` + a `building_damage` rollover value (`models.Projectile`); impact resolution unified into `_resolve_projectile_impact` / `_apply_member_hit` / `_apply_building_hit`.
- Verified headless: dead-defender shot rolls onto the building; live defender absorbs and building is spared; two same-tick shots kill the last defender then hit the building; shielded bunker takes 0, unshielded bunker takes full; a 10-shot barrage kills a lone guard then erodes the building (500→290). **63 unit tests pass** (`tests/test_projectiles.py` +5); live save untouched.

### 2026-08-21 — Challenge Police (repeatable raid boss) + level-cap headroom

- **Challenge Police**: once a city is **conquered**, clicking it on the map (war mode) now opens a **Challenge Police** popup instead of doing nothing. This is a **repeatable** end-of-city fight against the city's **police raid boss** — the toughest battle in the game. The city stays conquered win or lose, map scope is unaffected, and there is **no loss penalty**; on a win you get an **elevated reward** (`config.POLICE_REWARD_MULT = 2.0` × the city's base reward) plus the usual top-rarity **recruit** into the Backup Force.
- **Police boss scaling** (`enemy_gen.build_enemy(..., police=True)`): a city's `police_power` is 2×–420× its gang `underworld_power` (and far above the reference max), so the boss is always a **maxed roster (80 members)** with the **top HQ level**, fought at an elite fixed **`POLICE_LEVEL = 40`** so its members out-stat any gang's.
- **Level-cap headroom**: the old placeholder `MAX_LEVEL = 15` in `enemy_gen` was arbitrary — it only capped the *gang difficulty curve*, not any game rule (member stats scale unbounded at +15%/level in `models.Member.get_stats`). Raised to **30** so strong cities field genuinely high-level gangs (and richer recruits), with the police boss above that at 40.
- **Wiring**: `MapScreen` gained a `popup_police` state; owned-city tiles show a "★ Challenge Police" hint; confirming emits `("police", cid)`, routed in `main` to the new `Game._run_police` (guarded by the same roster-cap check as regular wars). `_fight_city` grew a `police` flag shared by both paths.
- Verified headless: police boss is 80× level-40 with a max HQ and out-levels the strongest gang; gang curve now tops out at 30; an end-to-end map click on a conquered city opens the police popup and yields `("police", cid)`. **56 unit tests pass** (`tests/test_police.py` +7); live save untouched.

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

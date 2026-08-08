# EVE — Game Vision Notes

## Core Premise

The player **manages an entire empire** (not a single member). This is the fundamental shift from UW.

In the original Underworld Empire:
- 80 players each control 1 member
- Each player independently grinds jobs, PvP, items
- They come together for EvE (Empire vs Empire) wars
- EvE was the core, everything else was filler/chores

In our game:
- The player IS the empire leader
- You manage all your members, buildings, strategy
- The game IS the EvE system — no filler
- Single-player, strategic management game

## What We Keep from UW

- **EvE battlefield** — 3×3 grid, buildings, defenders, attackers
- **Token action economy** — action points, regen rates, timing
- **Building system** — types, upgrades, HP, defender slots, super powers
- **Class system** (4 base classes):
  - **Enforcer** — tank, stun, protection
  - **Sniper** — vision, ranged, suppress
  - **Assassin** — stealth, poison, execute
  - **Demolitionist** — (renamed from Heavy Weapons) burn, traps, explosives
- **Visibility mechanics** — fog of war, front-to-back exposure
- **Points-based victory** — not pure elimination
- **Property system** — (needs elaboration — presumably territory/turf)

## What We Don't Keep

- **Job system** — boring chores, replaced by map/territory expansion
- **Individual player item system** — no RPG loot grind per member
- **PvP (1v1 player fights)** — all combat is through EvE
- **Upgraded classes** (Titan, Ghost, Reaper, Terminator) — their useful abilities get folded into the 4 base classes if needed

## Campaign / Progression

- **Start small** — your empire begins in a corner of a city map
- **Other gangs/empires rise up** on the map as you grow
- **Challenge them in EvE** to expand territory
- **Win EvE → gain better members** (recruit from defeated empires if lucky)
- **Future expansion**: more cities → states → countries (but start with one city)

## The "Job System" Replacement

Instead of boring repeatable chores, progression comes from:
- Territory control on the city map
- Challenging rival empires (EvE battles)
- Recruiting/upgrading members
- Building/upgrading your empire's infrastructure

## Key Design Questions (TBD)

1. **Member management** — How do you acquire/level members? Stats, XP, injuries?
2. **Economy** — What resources exist? How do you earn/spend?
3. **AI empires** — How do rival empires grow/behave on the map?
4. **Difficulty curve** — Early empires weak (5-10 members?), scale up to full 80?
5. **Battle AI** — During EvE, do you command in real-time? Turn-based? Auto with strategy presets?
6. **Between battles** — What do you do on the city map? Passive income? Scouting?
7. **Member recruitment** — Random? From defeated empires? Hire with money?
8. **Property system** — What does territory give you? Income? Member bonuses? Building materials?

---

## Design Consideration: Battlelog vs Physical Battlefield

### The Problem

The original UE EvE was a **battlelog system** — each member independently spends tokens to attack any visible target. There's no spatial coherence. A member can defend their own building while simultaneously attacking an enemy. This works as a text log but **breaks down in a visual/physical representation**.

When the player sees the battlefield from above (as an empire manager), physics must make sense:
- Members must **be somewhere** — they have a position
- A member **can't defend and attack at the same time** (unless they're at the same location)
- **Movement takes time** — getting to the back row means crossing the front
- **Visibility** works differently when you can literally see positions vs. abstract "rows"

### Possible Directions (TBD)

1. **Keep it abstract/card-based** — Don't show physical positions. Show the 3×3 grid as slots/cards. Actions happen instantly. Closer to the original. Less "game" feel, more management.

2. **Real-time tactical** — Members physically move on a battlefield. Assign them to attack or defend positions. Movement matters. Assassins are literally sneaking around the side. Feels like a tactics game (think: auto-battler or tower defense hybrid).

3. **Phase-based hybrid** — Each "round" (token spend), members are assigned a role: attack or defend. Attackers move toward targets, defenders stay put. Resolve combat per round. Compromise between log and physics.

4. **Simultaneous turns with replay** — Battles resolve as a simulation (like Football Manager match engine). Player sets strategy before battle, watches it play out. Can pause/adjust mid-battle at certain intervals.

5. **Compressed time** — 2-hour war compressed to 5-10 minutes of real-time play. Members auto-act based on AI/presets, player intervenes with special commands (like spending tokens on specific targets).

### Key Questions
- Does the player need to control DURING the battle, or just set up strategy BEFORE?
- How much "moment-to-moment" gameplay vs. strategic overview?
- Is the fun in the planning or the execution?
- How important is it to "watch" the battle vs. just see results?

### Decision: Commander-Level Real-Time Control

The player is the **war commander**. The fun comes from:

1. **Pre-battle**: Building layout design, defender allocation (right people in right spots)
2. **During battle**: Issuing high-level orders in real-time — directing squads/individuals to targets
3. **Watching it unfold**: Members execute via AI, player sees the results of their strategy

**Player control examples:**
- "Assassin squad — backdoor attack Building 9"
- "Snipers — blindly shoot into Building 3"
- "Demolitionists — focus on taking down Building 5"
- "Pull back defenders from Building 2 to reinforce Building 4"

**What the AI handles:**
- Individual combat resolution (attack rolls, damage, status effects)
- Member movement/pathfinding
- Token spending cadence
- Defender reactions to being attacked
- Healing/revival decisions

**What the player controls:**
- Which buildings to attack and with whom
- When to commit reserves
- When to shift focus/redirect
- Building layout and defender assignment (pre-battle)
- Special ability activations (super powers)

This means the battle IS physical — members move between buildings, but the player doesn't micromanage each one. They give squad-level orders and watch the AI execute. Think: **RTS commander mode** meets **football manager tactical view**.


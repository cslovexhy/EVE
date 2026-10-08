# Enemy Base Build Progression (proposed)

A single ordered sequence of **build actions**. Each row is exactly one action:
either **+1 level** to one existing building, or an **upgrade** that converts a
Warehouse → specialist, or Safehouse → Bunker. After each action the full state
of all 9 slots is shown.

- **Slots** map to the 3×3 grid (battlefield orientation `3 2 1 / 6 5 4 / 9 8 7`).
  Front row (exposed) = slots 1/4/7. HQ/Armory/Hospital are kept off the front
  row (existing placement bans); HQ sits in slot 5 (center backline).
- Notation: `Type Ln` = that building type at level `n`. Base is `Wh1`
  (Warehouse, max level 1).
- Max levels: Warehouse 1, Safehouse 3, everything else 4. Bunker requires the
  Safehouse to reach **L3** before converting.

**Gating rules (per product owner):**
- **Research Lab** may only be **BUILT after HQ reaches L3** (then levels normally).
- **Nuclear Silo** may only be **BUILT after HQ reaches L4** (then levels normally).
- The **slot-9 Warehouse** may be **upgraded to a Safehouse after HQ reaches
  L4** (then levels normally).

Slot roles chosen:
- Slot 1 (front): Sniper Tower
- Slot 2: Research Lab (built late, after HQ3)
- Slot 3 (backline): Hospital
- Slot 4 (front): Bunker (from Safehouse)
- Slot 5 (center backline): Headquarters
- Slot 6: Nuclear Silo (built late, after HQ4)
- Slot 7 (front): Bunker (from Safehouse)
- Slot 8: Armory
- Slot 9: Safehouse (from Warehouse, after HQ4)

Target end state (last row): **Sniper Tower, Research Lab, Hospital, Bunker, HQ,
Nuclear Silo, Bunker, Armory, Safehouse** — specialists/HQ/bunkers at max level,
slot-9 Safehouse at its max (L3).

| # | Action | S1 | S2 | S3 | S4 | S5 | S6 | S7 | S8 | S9 |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | (start) all warehouses | Wh1 | Wh1 | Wh1 | Wh1 | Wh1 | Wh1 | Wh1 | Wh1 | Wh1 |
| 1 | Build HQ (slot 5) | Wh1 | Wh1 | Wh1 | Wh1 | **HQ1** | Wh1 | Wh1 | Wh1 | Wh1 |
| 2 | Build Safehouse (slot 4) | Wh1 | Wh1 | Wh1 | **Sf1** | HQ1 | Wh1 | Wh1 | Wh1 | Wh1 |
| 3 | Build Safehouse (slot 7) | Wh1 | Wh1 | Wh1 | Sf1 | HQ1 | Wh1 | **Sf1** | Wh1 | Wh1 |
| 4 | Build Armory (slot 8) | Wh1 | Wh1 | Wh1 | Sf1 | HQ1 | Wh1 | Sf1 | **Ar1** | Wh1 |
| 5 | Build Hospital (slot 3) | Wh1 | Wh1 | **Ho1** | Sf1 | HQ1 | Wh1 | Sf1 | Ar1 | Wh1 |
| 6 | Build Sniper Tower (slot 1) | **St1** | Wh1 | Ho1 | Sf1 | HQ1 | Wh1 | Sf1 | Ar1 | Wh1 |
| 7 | HQ → L2 | St1 | Wh1 | Ho1 | Sf1 | **HQ2** | Wh1 | Sf1 | Ar1 | Wh1 |
| 8 | Armory → L2 | St1 | Wh1 | Ho1 | Sf1 | HQ2 | Wh1 | Sf1 | **Ar2** | Wh1 |
| 9 | Hospital → L2 | St1 | Wh1 | **Ho2** | Sf1 | HQ2 | Wh1 | Sf1 | Ar2 | Wh1 |
| 10 | Sniper Tower → L2 | **St2** | Wh1 | Ho2 | Sf1 | HQ2 | Wh1 | Sf1 | Ar2 | Wh1 |
| 11 | Safehouse (slot 4) → L2 | St2 | Wh1 | Ho2 | **Sf2** | HQ2 | Wh1 | Sf1 | Ar2 | Wh1 |
| 12 | Safehouse (slot 7) → L2 | St2 | Wh1 | Ho2 | Sf2 | HQ2 | Wh1 | **Sf2** | Ar2 | Wh1 |
| 13 | Safehouse (slot 4) → L3 | St2 | Wh1 | Ho2 | **Sf3** | HQ2 | Wh1 | Sf2 | Ar2 | Wh1 |
| 14 | Safehouse (slot 7) → L3 | St2 | Wh1 | Ho2 | Sf3 | HQ2 | Wh1 | **Sf3** | Ar2 | Wh1 |
| 15 | HQ → L3 | St2 | Wh1 | Ho2 | Sf3 | **HQ3** | Wh1 | Sf3 | Ar2 | Wh1 |
| 16 | **Build Research Lab (slot 2)** *(gated: after HQ3)* | St2 | **Rl1** | Ho2 | Sf3 | HQ3 | Wh1 | Sf3 | Ar2 | Wh1 |
| 17 | Armory → L3 | St2 | Rl1 | Ho2 | Sf3 | HQ3 | Wh1 | Sf3 | **Ar3** | Wh1 |
| 18 | Hospital → L3 | St2 | Rl1 | **Ho3** | Sf3 | HQ3 | Wh1 | Sf3 | Ar3 | Wh1 |
| 19 | Sniper Tower → L3 | **St3** | Rl1 | Ho3 | Sf3 | HQ3 | Wh1 | Sf3 | Ar3 | Wh1 |
| 20 | Research Lab → L2 | St3 | **Rl2** | Ho3 | Sf3 | HQ3 | Wh1 | Sf3 | Ar3 | Wh1 |
| 21 | Research Lab → L3 | St3 | **Rl3** | Ho3 | Sf3 | HQ3 | Wh1 | Sf3 | Ar3 | Wh1 |
| 22 | Safehouse (slot 4) → Bunker | St3 | Rl3 | Ho3 | **Bu1** | HQ3 | Wh1 | Sf3 | Ar3 | Wh1 |
| 23 | Safehouse (slot 7) → Bunker | St3 | Rl3 | Ho3 | Bu1 | HQ3 | Wh1 | **Bu1** | Ar3 | Wh1 |
| 24 | Bunker (slot 4) → L2 | St3 | Rl3 | Ho3 | **Bu2** | HQ3 | Wh1 | Bu1 | Ar3 | Wh1 |
| 25 | Bunker (slot 7) → L2 | St3 | Rl3 | Ho3 | Bu2 | HQ3 | Wh1 | **Bu2** | Ar3 | Wh1 |
| 26 | HQ → L4 (max) | St3 | Rl3 | Ho3 | Bu2 | **HQ4** | Wh1 | Bu2 | Ar3 | Wh1 |
| 27 | **Build Nuclear Silo (slot 6)** *(gated: after HQ4)* | St3 | Rl3 | Ho3 | Bu2 | HQ4 | **Nu1** | Bu2 | Ar3 | Wh1 |
| 28 | **Warehouse (slot 9) → Safehouse** *(gated: after HQ4)* | St3 | Rl3 | Ho3 | Bu2 | HQ4 | Nu1 | Bu2 | Ar3 | **Sf1** |
| 29 | Armory → L4 (max) | St3 | Rl3 | Ho3 | Bu2 | HQ4 | Nu1 | Bu2 | **Ar4** | Sf1 |
| 30 | Hospital → L4 (max) | St3 | Rl3 | **Ho4** | Bu2 | HQ4 | Nu1 | Bu2 | Ar4 | Sf1 |
| 31 | Sniper Tower → L4 (max) | **St4** | Rl3 | Ho4 | Bu2 | HQ4 | Nu1 | Bu2 | Ar4 | Sf1 |
| 32 | Research Lab → L4 (max) | St4 | **Rl4** | Ho4 | Bu2 | HQ4 | Nu1 | Bu2 | Ar4 | Sf1 |
| 33 | Nuclear Silo → L2 | St4 | Rl4 | Ho4 | Bu2 | HQ4 | **Nu2** | Bu2 | Ar4 | Sf1 |
| 34 | Nuclear Silo → L3 | St4 | Rl4 | Ho4 | Bu2 | HQ4 | **Nu3** | Bu2 | Ar4 | Sf1 |
| 35 | Bunker (slot 4) → L3 | St4 | Rl4 | Ho4 | **Bu3** | HQ4 | Nu3 | Bu2 | Ar4 | Sf1 |
| 36 | Bunker (slot 7) → L3 | St4 | Rl4 | Ho4 | Bu3 | HQ4 | Nu3 | **Bu3** | Ar4 | Sf1 |
| 37 | Nuclear Silo → L4 (max) | St4 | Rl4 | Ho4 | Bu3 | HQ4 | **Nu4** | Bu3 | Ar4 | Sf1 |
| 38 | Bunker (slot 4) → L4 (max) | St4 | Rl4 | Ho4 | **Bu4** | HQ4 | Nu4 | Bu3 | Ar4 | Sf1 |
| 39 | Bunker (slot 7) → L4 (max) | St4 | Rl4 | Ho4 | Bu4 | HQ4 | Nu4 | **Bu4** | Ar4 | Sf1 |
| 40 | Safehouse (slot 9) → L2 | St4 | Rl4 | Ho4 | Bu4 | HQ4 | Nu4 | Bu4 | Ar4 | **Sf2** |
| 41 | Safehouse (slot 9) → L3 (max) | St4 | Rl4 | Ho4 | Bu4 | HQ4 | Nu4 | Bu4 | Ar4 | **Sf3** |

**End state (row 41):** Sniper Tower L4, Research Lab L4, Hospital L4, Bunker L4,
HQ L4, Nuclear Silo L4, Bunker L4, Armory L4, Safehouse L3. 41 build actions
total from an all-warehouse start.

**Gates honored:**
- Research Lab is **built** (row 16, L1) *after* HQ L3 (row 15).
- Nuclear Silo is **built** (row 27, L1) *after* HQ L4 (row 26).
- Slot-9 Warehouse→Safehouse (row 28) *after* HQ L4 (row 26).

## Legend

| Abbrev | Type | Max level |
|---|---|---|
| Wh | Warehouse | 1 |
| Sf | Safehouse | 3 |
| Bu | Bunker | 4 |
| Ar | Armory | 4 |
| Ho | Hospital | 4 |
| Rl | Research Lab | 4 |
| St | Sniper Tower | 4 |
| Nu | Nuclear Silo | 4 |
| HQ | Headquarters | 4 |

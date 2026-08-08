# EVE — Open Design Questions

Organized by system. Answer when ready — no rush. Check off (replace `[ ]` with `[x]`) as decisions are made.

---

## 1. Economy

- [x] How much money per war win? → **30% of enemy empire net worth** (net worth = 100 × sum of member levels)
- [x] How much money lost on defeat? → **30% of your own empire net worth**
- [x] Property income — **per minute**, based on property level. Auto-collects to Safe House. City-specific types (e.g., Las Vegas → Casino).
- [x] Can properties be lost/raided? → **No. Properties are permanent/safe.** Money in Safe House CAN be lost on war defeat though (loss penalty auto-deducts regardless of where money is stored).
- [x] EvE building upgrade cost curve → **Exponential.**
- [x] Any other energy sinks besides entering wars? → **No, wars only for now.**
- [x] Favor Points acquisition → **Real money only (IAP). Not a concern during dev.**

---

## 2. Members & Classes

- [x] How many members do you start with? → **8 (2 per class)**
- [x] How do you recruit new members? → **After defeating an empire, pick 1 of 4 offered (best from each class of the defeated empire)**
- [x] Do members have individual stats? → **No. Stats are static, based solely on level + rarity.** Includes damage vs players/buildings, mitigation, skills.
- [x] Do members level up / gain XP? → **No. Level is a fixed attribute (tied to rarity/progression, not grindable).**
- [x] Can members be injured/killed permanently? → **No. Full HP reset every new battle. Health only matters during EvE.**
- [x] Class assignment — **Fixed at recruit. Cannot be changed.**
- [x] Class balance — **Player's strategic choice. Start even (2 each), adjust based on scouting enemy (e.g., more Demolitionists vs tough buildings).**
- [x] What abilities from upgraded classes get folded in? → **Deferred — class/skill design is its own topic.**

---

## 3. EvE Battle Mechanics

- [ ] Player control during battle — real-time commands? Turn-based? Auto with presets? Hybrid?
- [ ] Battle speed — real-time 2 hours (like UW)? Compressed to minutes? Instant sim?
- [ ] Token system — keep as-is? Simplify? Tokens per member or shared pool?
- [ ] How does the AI empire play during battle? Random? Scripted? Difficulty-scaled?
- [ ] Defender assignment — manual before battle? Auto-optimized? Rearrangeable mid-fight?
- [ ] Building placement — locked 3×3? Or player chooses arrangement before war?
- [ ] Victory condition — points only? Or also full destruction win?
- [ ] Retreat/forfeit option?

---

## 4. City Map & Progression

- [ ] Map structure — grid? Nodes? Zones/districts?
- [ ] How many rival empires per city?
- [ ] Do AI empires grow over time (time pressure) or stay static until challenged?
- [ ] Can you choose which empire to fight? Or matchmade/sequential?
- [ ] What does controlling territory give you? (Properties? Member pool? Bonuses?)
- [ ] How do you "fully conquer" a city to get the +50 max energy?
- [ ] Scouting — can you see enemy empire layout/strength before committing to a war?
- [ ] Any non-combat interactions on the map? (Trade? Diplomacy? Events?)

---

## 5. Buildings (EvE)

- [ ] Keep all UW building types? (HQ, Hospital, Armory, Sniper Tower, Nuclear Silo, Research Lab, Bunker)
- [ ] Simplify to fewer building types for our 4-class system?
- [ ] Building placement — does it matter which slot? (front row = exposed first)
- [ ] Super powers — keep? Simplify? Unlock at higher building levels?
- [ ] Building HP scaling — how tanky should buildings be?

---

## 6. Properties (Income)

- [ ] What types of properties? (Named/themed? Or generic tiers?)
- [ ] How many properties available per city district?
- [ ] Upgrade levels per property — cap?
- [ ] Income rate formula — linear per level? Diminishing?
- [ ] Visual representation on the city map?

---

## 7. Presentation & UX

- [ ] Art style — pixel art? Stylized? Text-heavy management sim?
- [ ] Tech stack — Python+Pygame (like DND)? Web? Mobile?
- [ ] Battle view — what does the player see during EvE? Animated? Log-based? Both?
- [ ] City map view — top-down? Stylized district map? Node graph?
- [ ] Sound/music direction?

---

## 8. Meta / Long-term

- [ ] Prestige/new game+ mechanic when you conquer a full city?
- [ ] Difficulty scaling across cities — new city = harder AI empires?
- [ ] Any multiplayer future? (Async PvP? Leaderboards?)
- [ ] Save system — single save? Multiple slots?
- [ ] Session length target — 10 min bursts? 30 min? Hour-long sessions?

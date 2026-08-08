# EVE — Presentation & Assets

## Art Style from UE

Underworld Empire uses a **card-style portrait** art direction:
- Character portraits are drawn illustrations (not pixel art, not 3D)
- Dark/gritty crime/urban theme
- Each lieutenant has a single portrait image
- Some have alternate skins (e.g., Overkill has "Extreme Anger Skin")
- Building artwork is illustrated panels

### Asset Sources (UE Fandom Wiki)

Character portraits hosted at:
```
https://static.wikia.nocookie.net/underworld-empire/images/X/XX/Lieutenant_NAME.png
```

Example:
- Overkill: `https://static.wikia.nocookie.net/underworld-empire/images/2/24/Lieutenant_overkill.png`

Item icons at:
```
https://static.wikia.nocookie.net/underworld-empire/images/X/XX/Item_NAME.png
```

### Available Asset Types:
1. **Character portraits** (~268 lieutenants) — card art for each member
2. **Building artwork** — HQ, Hospital, Armory, Sniper Tower, etc.
3. **Item icons** — weapons, armor, consumables
4. **UI elements** — status icons (stunned, poisoned, burning, etc.)
5. **Battlefield layout** — Empire Wars Battlefield screenshot

### Rarity Categories on Wiki:
- Category:Common_Lieutenants
- Category:Rare_Lieutenants  
- Category:Epic_Lieutenants
- (Uncommon/Super Rare likely exist too)

### Factions on Wiki:
- The Mafia Lieutenants
- The Cartel Lieutenants
- Dragon Syndicate Lieutenants
- Unaffiliated Lieutenants

---

## How to Reuse for Our Game

Since UE is a dead/shut-down game, we can reference the art style and names. For development:

1. **Placeholder phase**: Use the wiki portrait URLs directly during dev
2. **Production phase**: Either:
   - Commission similar-style art (same dark/urban/crime card aesthetic)
   - Use AI art generation in the same style
   - Or restyle entirely (your call)

### Mapping UE → Our Game:
| UE Concept | Our Game |
|------------|----------|
| Lieutenant portrait | Member card art |
| Star rating (1-9) | Level (from empire defeated) |
| Rarity (Common/Rare/Epic) | Rarity (Common/Uncommon/Rare/Super Rare) |
| Faction alignment | Could map to starting city/origin |
| Special ability | Class skill |

---

## Tech Stack (TBD)

Questions to decide:
- [ ] **Platform**: Mobile? Web? Desktop? All?
- [ ] **Engine/Framework**: Unity? Godot? Python+Pygame? React/web?
- [ ] **Battle view**: Animated 2D? Static cards with effects? Log-based?
- [ ] **City map view**: Stylized illustrated map? Node graph? Grid?
- [ ] **Sound/music**: Dark ambient? Crime film soundtrack?

---

## UE Lieutenant List by Rarity (Partial — from wiki categories)

### Trending/Popular (likely Epic/Super Rare):
Overkill, Gustavo, Hotwire, Sandsnake, Duke, Lady Luck, Gunslinger, Anson

### Available by purchase (likely Common/Uncommon):
AK (Lv1), Fang (Lv1), John (Lv1), Mia (Lv1), Charmaine (Lv4), Penelope (Lv4), Blade (Lv8), Cesar (Lv8), Hector (Lv15), Michael (Lv15), Lucas (Lv20), Blink (Lv25), Caine (Lv40), Fox (Lv45), Kate (Lv55), Tagg (Lv75)

### Full list: 268 characters (A-Z on wiki, paginated)
Source: https://underworld-empire.fandom.com/wiki/Category:Lieutenants

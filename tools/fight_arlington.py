"""Headless Arlington police-boss battle runner (diagnostic).

Fights the Arlington police raid boss with the player's saved base, driven by
the battle AI, and reports the double-bunker outcome: whether both bunkers were
cleared, when the shield dropped, and each bunker's final HP. Optional power
boost so we can actually push through a maxed level-40 roster and reach the
bunkers.

Never calls GameState.save(). Usage:
    python3 tools/fight_arlington.py [power_mult]
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import config  # noqa: E402
import enemy_gen  # noqa: E402
import world_map as wm  # noqa: E402
import buildings  # noqa: E402
from models import BuildingType, MemberClass  # noqa: E402
from game_state import GameState  # noqa: E402
from engine import BattleEngine  # noqa: E402
from ai import BattleAI  # noqa: E402
from orders import Order, OrderAction  # noqa: E402


def arlington_cid():
    for co, obj in wm.WORLD["United States"]["Virginia"].items():
        if "Arlington" in obj["cities"]:
            return wm.city_id("United States", "Virginia", co, "Arlington")
    return None


def run(power_mult=1.0):
    gs = GameState.load()
    player = gs.build_player_empire("Your Empire")
    # Temporary power boost: scale every player member's level.
    if power_mult != 1.0:
        for m in player.members:
            m.level = int(m.level * power_mult)
        print(f"[boost] player levels x{power_mult}")

    city = wm.get_city(arlington_cid())
    enemy = enemy_gen.build_enemy(city["police_power"], name="Arlington Police",
                                  police=True)

    order = buildings.building_order_from_layout(gs.building_layout)
    assignments = [list(s) for s in player.member_assignments]
    eng = BattleEngine(player, enemy, player_building_order=order,
                       player_member_assignments=assignments) \
        if "player_building_order" in BattleEngine.__init__.__code__.co_varnames \
        else BattleEngine(player, enemy)

    # Identify enemy bunkers.
    name_idx_to_type = {bt.spec["name_index"]: bt for bt in BuildingType}
    elayout = [name_idx_to_type[i] for i in enemy.building_order]
    bunkers = [i for i, bt in enumerate(elayout) if bt == BuildingType.BUNKER]
    print(f"enemy bunkers at slots {[b+1 for b in bunkers]}")

    ai = BattleAI(player, enemy, is_player=True)
    dt = 0.1
    shield_dropped_at = None
    first_bunker_down_at = None
    events = []
    t = 0.0
    prev_destroyed = {b: False for b in bunkers}
    steps = int(config.BATTLE_DURATION / dt) if hasattr(config, "BATTLE_DURATION") else 3000
    for _ in range(steps + 2000):
        if eng.battle_over:
            break
        o = ai.update(dt, eng)
        if o:
            tgt = enemy if o.action == OrderAction.ATTACK else player
            eng.execute_order(o, player, tgt, attack_mode="auto")
        eng.update(dt)
        t += dt
        # Track each bunker being destroyed + the other's state at that moment.
        for b in bunkers:
            if enemy.buildings[b].destroyed and not prev_destroyed[b]:
                prev_destroyed[b] = True
                others = [(ob + 1,
                           enemy.buildings[ob].hp,
                           sum(1 for i, m in enumerate(enemy.members)
                               if m.is_alive and m.assigned_building == ob))
                          for ob in bunkers if ob != b]
                events.append(
                    f"[{t:.1f}s] bunker slot {b+1} DESTROYED; "
                    f"other bunkers now: " +
                    "; ".join(f"slot {s} hp={hp:.0f} live_def={ld}" for s, hp, ld in others))
                if first_bunker_down_at is None:
                    first_bunker_down_at = t
        if shield_dropped_at is None and not eng._bunkers_shielded(enemy):
            shield_dropped_at = t

    print(f"\n=== RESULT after {t:.1f}s ===")
    print("battle_over:", eng.battle_over,
          "winner:", ("PLAYER" if eng.winner is player else
                      "ENEMY" if eng.winner is enemy else None))
    print("shield dropped at:", f"{shield_dropped_at:.1f}s" if shield_dropped_at else "NEVER")
    print("first bunker down at:", f"{first_bunker_down_at:.1f}s" if first_bunker_down_at else "NEVER")
    print("--- bunker destruction timeline ---")
    for e in events:
        print("  " + e)
    for b in bunkers:
        bld = enemy.buildings[b]
        live = [m.name for i, m in enumerate(enemy.members)
                if m.is_alive and m.assigned_building == b]
        print(f"  bunker slot {b+1}: hp {bld.hp:.0f}/{bld.max_hp} "
              f"destroyed={bld.destroyed} live_defenders={len(live)}")
    alive_enemy = sum(1 for m in enemy.members if m.is_alive)
    print("enemy alive:", alive_enemy, "/", len(enemy.members),
          "| enemy buildings left:", 9 - enemy.buildings_destroyed)


if __name__ == "__main__":
    mult = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
    run(mult)

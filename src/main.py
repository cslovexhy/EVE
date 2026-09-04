"""EVE - Empire vs Empire: screen navigator / entry point.

Flow:
    Birthplace (fight the town's gang; lose = game over/retry)
    Main Menu ──▶ EVE Layout (upgrade buildings)
             └──▶ Map (country ▸ state ▸ county ▸ city) ──▶ Wage War ──▶ Battle
                                                           └──▶ win: conquer + reward
"""
import sys

import pygame

import config
import buildings
import enemy_gen
import world_map as wm
from game_state import GameState, war_reward
from models import top_rarity_recruit
from screens import (ProfileSelect, MainMenu, EveLayout, MapScreen, USMapScreen,
                     GameOverScreen, VictoryScreen, RecruitPopup, CapBlockedPopup)
from battle_session import BattleSession


class Game:
    """Owns the window and drives navigation between screens."""

    def __init__(self):
        pygame.init()

        display_info = pygame.display.Info()
        config.SCREEN_WIDTH = display_info.current_w
        config.SCREEN_HEIGHT = display_info.current_h

        self.screen = pygame.display.set_mode(
            (config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.FULLSCREEN)
        pygame.display.set_caption(config.TITLE)

        # Battlefield layout metrics (used by the battle renderer).
        config.BATTLEFIELD_WIDTH = config.SCREEN_WIDTH - 80
        config.BATTLEFIELD_HEIGHT = (config.SCREEN_HEIGHT - config.BATTLEFIELD_Y
                                     - config.ORDER_PANEL_HEIGHT)

        # The active profile is chosen on the Profile Select screen at startup
        # (set in run()), so audio init is deferred until we know its sound_on.
        self.state = None

    def _init_audio(self):
        """Initialize the SFX mixer from the active profile's preference. Safe
        no-op if no audio device is available (headless). Sound is OFF by
        default and persisted per profile. CLI flags override for one run:
        --mute forces silent, --sound forces on."""
        import sound
        muted = not self.state.sound_on
        if "--mute" in sys.argv:
            muted = True
        elif "--sound" in sys.argv:
            muted = False
        sound.init(muted=muted)

    def run(self):
        # Choose (or create) a save profile before anything else.
        result = ProfileSelect(self.screen).run()
        if result == "quit" or result is None:
            pygame.quit()
            sys.exit()
        self.state = result           # a loaded/created GameState
        self._init_audio()

        # A freshly created profile has no birthplace yet: pick one first.
        if self.state.home_city is None:
            if not self._choose_birthplace():
                pygame.quit()
                sys.exit()

        screen_name = "menu"
        while True:
            if screen_name == "menu":
                screen_name = MainMenu(self.screen).run()
            elif screen_name == "layout":
                EveLayout(self.screen, self.state).run()
                screen_name = "menu"
            elif screen_name == "map":
                # Visual US map at the states level.
                result = USMapScreen(self.screen, self.state).run()
                if isinstance(result, tuple) and result[0] == "state":
                    self._browse_state(result[1])
                    screen_name = "map"   # back to the US map afterwards
                else:
                    screen_name = "menu"
            elif screen_name == "quit":
                break
            else:
                break

        pygame.quit()
        sys.exit()

    def _choose_birthplace(self) -> bool:
        """Pick a starting city and fight its gang. Win → that city becomes your
        home. Lose → game over, reset, and try again. Returns False only if the
        player backs out of the picker (quit)."""
        while True:
            result = MapScreen(self.screen, self.state, mode="birthplace").run()
            if not (isinstance(result, tuple) and result[0] == "birthplace"):
                return False
            cid = result[1]
            won, _ = self._fight_city(cid)
            if won:
                self.state.set_birthplace(cid)
                self.state.save()
                VictoryScreen(self.screen, cid).run()
                return True
            # Lost the first fight — your run ends here. Reset and retry.
            GameOverScreen(self.screen, cid).run()
            self.state = GameState()

    def _fight_city(self, target_city_id: str, police: bool = False):
        """Run one EvE battle against a city's underworld (police=False) or its
        police raid boss (police=True), using the player's current base. Returns
        (won, enemy) — enemy is the (defeated or victorious) enemy empire so the
        caller can size a net-worth-based reward. On a win, a top-rarity recruit
        from the defeated empire joins the Backup Force (popup shown)."""
        city = wm.get_city(target_city_id)
        city_name = wm.split_city_id(target_city_id)[-1]

        player = self.state.build_player_empire("Your Empire")
        order = buildings.building_order_from_layout(self.state.building_layout)
        member_assignments = [list(s) for s in player.member_assignments]

        if police:
            power = city["police_power"] if city else 0
            enemy = enemy_gen.build_enemy(power, name=f"{city_name} Police",
                                          police=True, profile_seed=target_city_id)
        else:
            power = city["underworld_power"] if city else 0
            enemy = enemy_gen.build_enemy(power, name=f"{city_name} Underworld",
                                          profile_seed=target_city_id)

        session = BattleSession(self.screen, player, enemy,
                                building_order=order,
                                member_assignments=member_assignments)
        won = session.run() is player
        # Persist any in-battle sound toggle (M key) so the choice sticks.
        import sound
        sound_on = not sound.is_muted()
        if sound_on != self.state.sound_on:
            self.state.sound_on = sound_on
            self.state.save()
        if won:
            self._acquire_recruit(enemy)
        return won, enemy

    def _acquire_recruit(self, enemy):
        """Recruit a top-rarity member from a defeated enemy into the backup
        force and show the reveal popup. The caller persists state on the win."""
        recruit = top_rarity_recruit(enemy)
        if recruit is None:
            return
        kept = self.state.add_recruit(recruit)
        RecruitPopup(self.screen, recruit, backup_full=not kept).run()

    def _browse_state(self, state_name: str):
        """Drill into one state's counties/cities (launched from the US map).
        Loops so that after a battle/raid we return to the same state's list;
        backing out of the state returns to the US map."""
        while True:
            result = MapScreen(self.screen, self.state,
                               start_state=state_name).run()
            if isinstance(result, tuple) and result[0] == "battle":
                if self.state.roster_over_cap():
                    CapBlockedPopup(self.screen, len(self.state.roster),
                                    self.state.member_cap()).run()
                else:
                    self._run_war(result[1])
                # loop back into the same state's list
            elif isinstance(result, tuple) and result[0] == "police":
                if self.state.roster_over_cap():
                    CapBlockedPopup(self.screen, len(self.state.roster),
                                    self.state.member_cap()).run()
                else:
                    self._run_police(result[1])
            else:
                return  # "us_map" (or anything else) -> back to the US map

    def _run_war(self, target_city_id: str):
        """Wage war on an already-owned-region city. A win pays the city's
        reward and marks it conquered."""
        won, _ = self._fight_city(target_city_id)
        if won:
            city = wm.get_city(target_city_id)
            self.state.money += (city["reward"] if city else 0)
            self.state.mark_conquered(target_city_id)
            self.state.save()

    def _run_police(self, target_city_id: str):
        """Challenge the police raid boss of an already-conquered city. This is
        repeatable: the city stays conquered win or lose, nothing about map
        scope changes, and there is no loss penalty. A win pays an elevated
        reward scaled to the boss's real strength — POLICE_REWARD_MULT x the
        standard war_reward (30% of the police empire's net worth) — so the
        payout tracks the hardest fight in the game rather than the flat,
        GDP-percentile city reward."""
        won, enemy = self._fight_city(target_city_id, police=True)
        if won:
            reward = int(war_reward(enemy) * config.POLICE_REWARD_MULT)
            self.state.money += reward
            self.state.save()


if __name__ == "__main__":
    Game().run()

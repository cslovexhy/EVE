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
from screens import (MainMenu, EveLayout, MapScreen, GameOverScreen,
                     VictoryScreen, RecruitPopup, CapBlockedPopup)
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

        self.state = GameState.load()

    def run(self):
        # First launch: choose a birthplace before anything else.
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
                result = MapScreen(self.screen, self.state).run()
                if isinstance(result, tuple) and result[0] == "battle":
                    if self.state.roster_over_cap():
                        CapBlockedPopup(self.screen, len(self.state.roster),
                                        self.state.member_cap()).run()
                    else:
                        self._run_war(result[1])
                    screen_name = "map"   # return to the map after the battle
                elif isinstance(result, tuple) and result[0] == "police":
                    if self.state.roster_over_cap():
                        CapBlockedPopup(self.screen, len(self.state.roster),
                                        self.state.member_cap()).run()
                    else:
                        self._run_police(result[1])
                    screen_name = "map"   # return to the map after the raid
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
                                          police=True)
        else:
            power = city["underworld_power"] if city else 0
            enemy = enemy_gen.build_enemy(power, name=f"{city_name} Underworld")

        session = BattleSession(self.screen, player, enemy,
                                building_order=order,
                                member_assignments=member_assignments)
        won = session.run() is player
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

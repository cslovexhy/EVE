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
from game_state import GameState
from models import create_starting_roster
from screens import MainMenu, EveLayout, MapScreen, GameOverScreen, VictoryScreen
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
                    self._run_war(result[1])
                    screen_name = "map"   # return to the map after the battle
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
            if self._fight_city(cid):
                self.state.set_birthplace(cid)
                self.state.save()
                VictoryScreen(self.screen, cid).run()
                return True
            # Lost the first fight — your run ends here. Reset and retry.
            GameOverScreen(self.screen, cid).run()
            self.state = GameState()

    def _fight_city(self, target_city_id: str) -> bool:
        """Run one EvE battle against a city's underworld, using the player's
        current base. Returns True if the player won."""
        city = wm.get_city(target_city_id)
        power = city["underworld_power"] if city else 0
        city_name = wm.split_city_id(target_city_id)[-1]

        player = create_starting_roster("Your Empire", is_player=True)
        self.state.apply_to_empire(player)
        order = buildings.building_order_from_layout(self.state.building_layout)
        member_assignments = [list(s) for s in player.member_assignments]

        enemy = enemy_gen.build_enemy(power, name=f"{city_name} Underworld")

        session = BattleSession(self.screen, player, enemy,
                                building_order=order,
                                member_assignments=member_assignments)
        return session.run() is player

    def _run_war(self, target_city_id: str):
        """Wage war on an already-owned-region city. A win pays the city's
        reward and marks it conquered."""
        if self._fight_city(target_city_id):
            city = wm.get_city(target_city_id)
            self.state.money += (city["reward"] if city else 0)
            self.state.mark_conquered(target_city_id)
            self.state.save()


if __name__ == "__main__":
    Game().run()

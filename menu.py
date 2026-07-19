"""The home screen: lists every game exposed by the game directories below and lets
the player pick one. Adding a new game means building its state machine in a new
directory (see quiz/ and color_game/ for the pattern), exposing it as a `Game` from
that directory's __init__.py, and importing it here.
"""

from dataclasses import dataclass, replace

from common import AnswerPicker, Game, GetReadyScreen, Input, draw_text, state_font

import color_game
import quiz

GAMES_PER_PAGE = 3

all_games = color_game.games + quiz.games


@dataclass
class MenuState:
    page: int = 0

    def _paginated(self):
        return len(all_games) > 5

    def _games_this_page(self):
        if not self._paginated():
            return all_games
        start = self.page * GAMES_PER_PAGE
        return all_games[start:start + GAMES_PER_PAGE]

    def _options_picker(self):
        games_this_page = self._games_this_page()
        if not self._paginated():
            options = [g.name for g in games_this_page]
            values = list(games_this_page)
        else:
            options = ["<"] + [g.name for g in games_this_page] + [">"]
            values = ["prev"] + list(games_this_page) + ["next"]
        return AnswerPicker(options, values)

    def draw(self, surface):
        CANVAS_WIDTH, CANVAS_HEIGHT = surface.get_size()
        draw_text(surface, state_font, "Choose a Game", (CANVAS_WIDTH // 2, CANVAS_HEIGHT // 3))
        self._options_picker().draw(surface)

    def next_state(self, input: Input):
        selection = self._options_picker().selection(input)

        if selection == "prev":
            return replace(self, page=max(0, self.page - 1))
        elif selection == "next":
            last_page = (len(all_games) - 1) // GAMES_PER_PAGE
            return replace(self, page=min(last_page, self.page + 1))
        elif isinstance(selection, Game):
            return GetReadyScreen(selection.initial_state)
        else:
            return self


def home():
    return MenuState()

"""The home screen: lists every game exposed by the game directories below and lets
the player pick one. Adding a new game means building its state machine in a new
directory (see quiz/ and color_game/ for the pattern), exposing it as a `Game` from
that directory's __init__.py, and importing it here.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import pygame

from common import AnswerPicker, Game, GetReadyScreen, Input, State, draw_text, font

import color_game
import quiz

GAMES_PER_PAGE = 3

all_games = color_game.games + quiz.games


@dataclass
class MenuState:
    page: int = 0
    # False right after a page turn, until every button is released again. The
    # game loop calls next_state every frame, so without this a single held
    # press of the paging button would flip through several pages at once.
    ready: bool = True

    def _paginated(self) -> bool:
        return len(all_games) > 5

    def _games_this_page(self) -> list[Game]:
        if not self._paginated():
            return all_games
        start = self.page * GAMES_PER_PAGE
        return all_games[start:start + GAMES_PER_PAGE]

    def _options_picker(self) -> AnswerPicker[Game | str]:
        games_this_page = self._games_this_page()
        if not self._paginated():
            options = [g.name for g in games_this_page]
            values: list[Game | str] = list(games_this_page)
        else:
            options = ["<"] + [g.name for g in games_this_page] + [">"]
            values = ["prev"] + list(games_this_page) + ["next"]
        return AnswerPicker(options, values)

    def draw(self, surface: pygame.Surface) -> None:
        CANVAS_WIDTH, CANVAS_HEIGHT = surface.get_size()
        draw_text(surface, font(60), "Choose a Game", (CANVAS_WIDTH // 2, CANVAS_HEIGHT // 3))
        self._options_picker().draw(surface)

    def next_state(self, input: Input) -> State | None:
        any_pressed = any(button.is_pressed() for button in input.buttons)
        if not any_pressed:
            # Buttons released -- arm the next press.
            return self if self.ready else replace(self, ready=True)
        if not self.ready:
            # A button is held from a press we already handled; wait for release.
            return self

        selection = self._options_picker().selection(input)

        if selection == "prev":
            return replace(self, page=max(0, self.page - 1), ready=False)
        elif selection == "next":
            last_page = (len(all_games) - 1) // GAMES_PER_PAGE
            return replace(self, page=min(last_page, self.page + 1), ready=False)
        elif isinstance(selection, Game):
            return GetReadyScreen(selection.initial_state)
        else:
            return self


def home() -> MenuState:
    return MenuState()

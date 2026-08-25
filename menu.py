"""The home screen: groups every game exposed by the game directories below
into a couple of categories, lets the player pick a category, then pick a
game within it. Adding a new game means building its state machine in a new
directory (see quiz/ and color_game/ for the pattern), exposing it as a
`Game` from that directory's __init__.py, importing it here, and adding it
to the right category below.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import pygame

import ball_machine
import breakout
import chain
import color_game
import flags
import mastermind
import pacman
import quiz
import simon
import space_invaders
import tetris
import tower_defense
import vault
from common import AnswerPicker, Game, GetReadyScreen, Input, State, draw_text, font
from hardware import big_red_button_pressed, buttons_in_order

GAMES_PER_PAGE = 3


@dataclass
class Category:
    name: str
    games: list[Game]


categories = [
    Category("Quiz Games", color_game.games + quiz.games + mastermind.games + chain.games + flags.games),
    Category(
        "Arcade Games",
        pacman.games
        + vault.games
        + breakout.games
        + space_invaders.games
        + tetris.games
        + tower_defense.games
        + simon.games
        + ball_machine.games,
    ),
]


@dataclass
class CategoryMenuState:
    """The top-level screen: pick a category to see the games in it. There
    are only ever a handful of categories, so unlike GameMenuState this
    never needs to paginate."""

    def _options_picker(self) -> AnswerPicker[Category]:
        return AnswerPicker([category.name for category in categories], categories)

    def draw(self, surface: pygame.Surface) -> None:
        CANVAS_WIDTH, CANVAS_HEIGHT = surface.get_size()
        draw_text(surface, font(60), "Choose a Category", (CANVAS_WIDTH // 2, CANVAS_HEIGHT // 3))
        self._options_picker().draw(surface)

    def _light_available_leds(self) -> None:
        options = self._options_picker().options
        for i, button in enumerate(buttons_in_order):
            button.set_led(i < len(options))

    def next_state(self, input: Input) -> State | None:
        self._light_available_leds()

        any_pressed = any(button.is_pressed() for button in input.buttons)
        if not any_pressed:
            return self

        selection = self._options_picker().selection(input)
        if isinstance(selection, Category):
            # Not ready yet -- the press that picked this category may still be
            # held on the very first frame here, and GameMenuState's own slots
            # mean something totally different. Wait for release before acting,
            # same debounce it already uses between page turns.
            return GameMenuState(category=selection, ready=False)
        return self


@dataclass
class GameMenuState:
    """The games within one category. The big red button steps back up to
    the category list, the same "go back" role it plays inside a game."""

    category: Category
    page: int = 0
    # False right after a page turn, until every button is released again. The
    # game loop calls next_state every frame, so without this a single held
    # press of the paging button would flip through several pages at once.
    ready: bool = True

    def _paginated(self) -> bool:
        return len(self.category.games) > 5

    def _games_this_page(self) -> list[Game]:
        if not self._paginated():
            return self.category.games
        start = self.page * GAMES_PER_PAGE
        return self.category.games[start:start + GAMES_PER_PAGE]

    def _options_picker(self) -> AnswerPicker[Game | str]:
        games_this_page = self._games_this_page()
        if not self._paginated():
            options = [g.name for g in games_this_page]
            values: list[Game | str] = list(games_this_page)
        else:
            left = ["<"] if self.page > 0 else [""]
            right = [">"] if self.page < (len(self.category.games) - 1) // GAMES_PER_PAGE else [""]
            options = left + [g.name for g in games_this_page] + right
            values = ["prev"] + list(games_this_page) + ["next"]
        return AnswerPicker(options, values)

    def draw(self, surface: pygame.Surface) -> None:
        CANVAS_WIDTH, CANVAS_HEIGHT = surface.get_size()
        draw_text(surface, font(60), self.category.name, (CANVAS_WIDTH // 2, CANVAS_HEIGHT // 3))
        self._options_picker().draw(surface)

    def _light_available_leds(self) -> None:
        """Only buttons that map to a real choice on this page light up -- the
        blank arrow slots on the first/last page (and any leftover slots when
        there are fewer than five options) stay dark."""
        options = self._options_picker().options
        for i, button in enumerate(buttons_in_order):
            button.set_led(i < len(options) and options[i] != "")

    def next_state(self, input: Input) -> State | None:
        if big_red_button_pressed():
            return CategoryMenuState()

        self._light_available_leds()

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
            last_page = (len(self.category.games) - 1) // GAMES_PER_PAGE
            return replace(self, page=min(last_page, self.page + 1), ready=False)
        elif isinstance(selection, Game):
            return GetReadyScreen(selection.initial_state)
        else:
            return self


def home() -> CategoryMenuState:
    return CategoryMenuState()

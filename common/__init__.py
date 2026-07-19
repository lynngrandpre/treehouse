"""Generic game-loop plumbing and screen widgets shared by every game and the menu:
Input, Game, draw_text, AnswerPicker, GetReadyScreen. None of this is tied to any
particular piece of hardware, beyond reading button state through the Button
objects defined in hardware.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, Protocol, TypeVar

import pygame

from hardware import Button, buttons_in_order

pygame.init()

state_font = pygame.font.SysFont("", 60)
answer_font = pygame.font.SysFont("", 25)


@dataclass
class Input:
    buttons: list[Button]
    current_time: int


class State(Protocol):
    """One screen of a game's state machine. States are duck-typed -- no base
    class, anything with these two methods qualifies. Returning None from
    next_state signals "this game is over, go back to the menu"."""

    def draw(self, surface: pygame.Surface) -> None: ...

    def next_state(self, input: Input) -> State | None: ...


@dataclass
class Game:
    name: str
    # A zero-arg callable rather than a plain state instance, since most games
    # (e.g. quizzes) need a freshly randomized state each time they're played.
    initial_state: Callable[[], State]


def draw_text(
    surface: pygame.Surface,
    font: pygame.font.Font,
    text: str,
    position: tuple[float, float],
    color: tuple[int, int, int] = (0, 0, 0),
) -> None:
    """Draws text on the given surface, centered at the given position."""
    text_surface = font.render(text, True, color)
    text_rect = text_surface.get_rect(center=position)
    surface.blit(text_surface, text_rect)


T = TypeVar("T")


@dataclass
class AnswerPicker(Generic[T]):
    """A "pick one of up to 5 options" widget, one option per button. Generic in
    the value each option carries: quizzes use bools, the menu uses Game | str."""

    options: list[str]
    values: list[T]

    def __post_init__(self) -> None:
        if len(self.options) > 5:
            raise ValueError(f"AnswerPicker: options must have at most 5 items. {self.options}")
        if len(self.values) != len(self.options):
            raise ValueError(f"AnswerPicker: values must have the same length as options. {len(self.values)=} {len(self.options)=}")

    def draw(self, surface: pygame.Surface) -> None:
        CANVAS_WIDTH, CANVAS_HEIGHT = surface.get_size()

        answer_height = CANVAS_HEIGHT // 4 * 3

        pygame.draw.rect(surface, (0, 0, 0), pygame.Rect(((0.5) * (CANVAS_WIDTH // 6) - 2, answer_height + 20 - 2), (5 * CANVAS_WIDTH // 6 + 2, 10 + 4)))

        for i in range(len(self.options)):
            pygame.draw.rect(surface, buttons_in_order[i].rgb.to_tuple(), pygame.Rect(((i + 0.5) * (CANVAS_WIDTH // 6), answer_height + 20), (CANVAS_WIDTH // 6, 10)))
            draw_text(surface, answer_font, self.options[i], (CANVAS_WIDTH // 6 * (i + 1), answer_height))

    def selection(self, input: Input) -> T | None:
        pressed_buttons = [i for i, button in enumerate(input.buttons) if button.is_pressed()]

        if len(pressed_buttons) != 1:
            return None

        idx = pressed_buttons[0]
        if idx >= len(self.values):
            return None

        return self.values[idx]


@dataclass
class GetReadyScreen:
    """A brief pause shown between picking a game and actually starting it, so a
    still-held selection button isn't immediately misread as an in-game press."""

    make_next_state: Callable[[], State]

    def draw(self, surface: pygame.Surface) -> None:
        CANVAS_WIDTH, CANVAS_HEIGHT = surface.get_size()
        draw_text(surface, state_font, "Get Ready...", (CANVAS_WIDTH // 2, CANVAS_HEIGHT // 2))

    def next_state(self, input: Input) -> State | None:
        pressed_buttons = [button for button in input.buttons if button.is_pressed()]

        if len(pressed_buttons) == 0:
            return self.make_next_state()
        else:
            return self

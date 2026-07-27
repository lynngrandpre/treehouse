"""Mastermind: guess a secret 4-peg code (any of the 5 button colors, repeats
allowed) within 10 attempts. Enter a guess one peg at a time by pressing color
buttons in order; once all 4 slots are filled, confirm with White (score the
guess) or Red (clear it and start re-entering). Scored guesses show feedback
pegs in the classic 2x2 grid: black for right color in the right slot, white
for right color in the wrong slot.
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass, field, replace

import pygame

from common import Input, State, draw_text, font
from hardware import Color, big_red_button_pressed, buttons

MAX_ATTEMPTS = 10
CODE_LENGTH = 4

# Left to right, matching buttons_in_order / the physical layout.
COLORS_IN_ORDER = [Color.RED, Color.GREEN, Color.BLUE, Color.YELLOW, Color.WHITE]


@dataclass(frozen=True)
class Feedback:
    black: int  # right color, right position
    white: int  # right color, wrong position


def score_guess(secret: list[Color], guess: list[Color]) -> Feedback:
    black = sum(s == g for s, g in zip(secret, guess))
    total_color_matches = sum((Counter(secret) & Counter(guess)).values())
    return Feedback(black=black, white=total_color_matches - black)


def random_secret() -> list[Color]:
    return [random.choice(COLORS_IN_ORDER) for _ in range(CODE_LENGTH)]


def _pressed_color(input: Input) -> Color | None:
    """The single color whose button is held this frame, or None if zero or
    more than one is held."""
    pressed = [i for i, button in enumerate(input.buttons) if button.is_pressed()]
    if len(pressed) != 1:
        return None
    return COLORS_IN_ORDER[pressed[0]]


def _draw_pegs(surface: pygame.Surface, pegs: list[Color], top_left: tuple[int, int], slot_size: int) -> None:
    x, y = top_left
    for i in range(CODE_LENGTH):
        center = (x + i * (slot_size + 8) + slot_size // 2, y + slot_size // 2)
        if i < len(pegs):
            pygame.draw.circle(surface, buttons[pegs[i]].rgb.to_tuple(), center, slot_size // 2)
        pygame.draw.circle(surface, (0, 0, 0), center, slot_size // 2, 2)


def _draw_feedback(surface: pygame.Surface, feedback: Feedback, top_left: tuple[int, int], dot_size: int = 16) -> None:
    x, y = top_left
    dots: list[tuple[int, int, int] | None] = (
        [(0, 0, 0)] * feedback.black
        + [(255, 255, 255)] * feedback.white
        + [None] * (CODE_LENGTH - feedback.black - feedback.white)
    )
    for i, color in enumerate(dots):
        row, col = divmod(i, 2)
        center = (x + col * (dot_size + 6) + dot_size // 2, y + row * (dot_size + 6) + dot_size // 2)
        if color is not None:
            pygame.draw.circle(surface, color, center, dot_size // 2)
        pygame.draw.circle(surface, (0, 0, 0), center, dot_size // 2, 1)


@dataclass
class MastermindResultScreen:
    secret: list[Color]
    history: list[tuple[list[Color], Feedback]]
    won: bool
    # Starts unarmed: the White (or Red) press that got us here is often still
    # held on the very first frame we're drawn, and we don't want that same
    # press to instantly bounce back to the menu. Require a release first.
    ready: bool = False

    @property
    def attempts(self) -> int:
        return len(self.history)

    def _message(self) -> str:
        if not self.won:
            return "Maybe stay in school"
        elif self.attempts <= 2:
            return "Genius!"
        elif self.attempts <= 4:
            return "Impressive!"
        elif self.attempts <= 6:
            return "Great job!"
        elif self.attempts <= 8:
            return "Phew, nice one!"
        else:
            return "Cutting it close!"

    def draw(self, surface: pygame.Surface) -> None:
        CANVAS_WIDTH, _ = surface.get_size()
        headline = "You Win!" if self.won else "You Lose :("
        draw_text(surface, font(32), f"{headline}  {self._message()}", (CANVAS_WIDTH // 2, 24))

        row_height = 38
        top = 52
        for i, (guess, feedback) in enumerate(self.history):
            y = top + i * row_height
            _draw_pegs(surface, guess, (30, y), slot_size=28)
            _draw_feedback(surface, feedback, (CANVAS_WIDTH // 2, y + 2), dot_size=14)

        if not self.won:
            y = top + len(self.history) * row_height
            draw_text(surface, font(24), "Answer:", (CANVAS_WIDTH // 2 - 110, y + 14))
            _draw_pegs(surface, self.secret, (CANVAS_WIDTH // 2 - 20, y), slot_size=28)

    def next_state(self, input: Input) -> State | None:
        if big_red_button_pressed():
            return None  # back to the menu

        any_pressed = any(button.is_pressed() for button in input.buttons)
        if not any_pressed:
            # Buttons released -- arm the next press.
            return self if self.ready else replace(self, ready=True)
        if not self.ready:
            # Still the confirm press that got us here; wait for it to release.
            return self

        return None  # a fresh press after that -- back to the menu


@dataclass
class GuessEntryState:
    secret: list[Color]
    history: list[tuple[list[Color], Feedback]] = field(default_factory=list)
    current_guess: list[Color] = field(default_factory=list)
    # Debounces button presses the same way MenuState does -- one action per
    # physical press, not one per frame a button is held.
    ready: bool = True

    def draw(self, surface: pygame.Surface) -> None:
        CANVAS_WIDTH, _ = surface.get_size()
        draw_text(surface, font(26), "Crack the Code", (CANVAS_WIDTH // 2, 15))

        row_height = 44
        top = 32
        slot_size = 30

        # All MAX_ATTEMPTS rows are drawn every frame -- filled in as history,
        # active as the current guess, or empty pegs for attempts not yet
        # used -- so the player can see how many guesses they have left, like
        # the pre-printed rows on the physical board.
        for i in range(MAX_ATTEMPTS):
            y = top + i * row_height
            if i < len(self.history):
                guess, feedback = self.history[i]
                _draw_pegs(surface, guess, (30, y), slot_size=slot_size)
                _draw_feedback(surface, feedback, (CANVAS_WIDTH // 2, y + 3), dot_size=16)
            elif i == len(self.history):
                _draw_pegs(surface, self.current_guess, (30, y), slot_size=slot_size)
                if len(self.current_guess) >= CODE_LENGTH:
                    draw_text(surface, font(18), "White=submit  Red=clear", (CANVAS_WIDTH - 145, y + slot_size // 2))
            else:
                _draw_pegs(surface, [], (30, y), slot_size=slot_size)

    def next_state(self, input: Input) -> State | None:
        if big_red_button_pressed():
            return None  # back to the menu

        any_pressed = any(button.is_pressed() for button in input.buttons)
        if not any_pressed:
            # Buttons released -- arm the next press.
            return self if self.ready else replace(self, ready=True)
        if not self.ready:
            # A button is held from a press we already handled; wait for release.
            return self

        color = _pressed_color(input)
        if color is None:
            # Ambiguous read (e.g. switch bounce momentarily showing two
            # buttons held) -- leave `ready` alone and wait for a clean single
            # press, the same way MenuState/AnswerPicker.selection() do rather
            # than locking out the press that's still in progress.
            return self

        if len(self.current_guess) < CODE_LENGTH:
            return replace(self, current_guess=self.current_guess + [color], ready=False)

        # A full guess is entered -- awaiting confirmation.
        if color == Color.WHITE:
            feedback = score_guess(self.secret, self.current_guess)
            new_history = self.history + [(self.current_guess, feedback)]
            if feedback.black == CODE_LENGTH:
                return MastermindResultScreen(self.secret, new_history, won=True)
            if len(new_history) >= MAX_ATTEMPTS:
                return MastermindResultScreen(self.secret, new_history, won=False)
            return GuessEntryState(self.secret, history=new_history, current_guess=[], ready=False)
        elif color == Color.RED:
            return replace(self, current_guess=[], ready=False)
        else:
            return replace(self, ready=False)


def new_mastermind() -> GuessEntryState:
    return GuessEntryState(secret=random_secret())

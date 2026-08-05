"""Simon Says: LEDs flash a growing color sequence, then the player repeats it
back on the matching buttons. One wrong press ends the round -- how long a
sequence can you hold in your head?

A single continuous state that mutates and returns itself every frame, in the
same "continuous game" style as Tetris -- timing is driven off absolute
timestamps (when to advance to the next flash, when to clear a feedback
flash) rather than per-frame deltas.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace

import pygame

from common import Input, State, draw_text, font
from hardware import Color, big_red_button_pressed, buttons

CANVAS_WIDTH = 800
CANVAS_HEIGHT = 480

# Declaration order matches buttons_in_order (hardware.py), so zipping
# input.buttons against this list pairs each Button with its Color.
COLORS = [Color.RED, Color.GREEN, Color.BLUE, Color.YELLOW, Color.WHITE]

SHOW_ON_MS = 500  # how long each flash in the playback stays lit
SHOW_GAP_MS = 250  # dark pause between flashes
FLASH_MS = 250  # how long a player's own press stays lit as feedback


def _light_result_leds() -> None:
    """Green: Play Again, Red: Main Menu -- the only two live buttons here."""
    buttons[Color.RED].set_led(True)
    buttons[Color.GREEN].set_led(True)
    buttons[Color.YELLOW].set_led(False)
    buttons[Color.BLUE].set_led(False)
    buttons[Color.WHITE].set_led(False)


def _clear_control_leds() -> None:
    for button in buttons.values():
        button.set_led(False)


def _draw_pad(surface: pygame.Surface, lit_color: Color | None) -> None:
    """The five buttons as on-screen squares, in their physical left-to-right
    order, so the sequence is visible on screen as well as on the LEDs."""
    size = 80
    gap = 20
    total_width = len(COLORS) * size + (len(COLORS) - 1) * gap
    left = (CANVAS_WIDTH - total_width) // 2
    top = CANVAS_HEIGHT // 2 - size // 2

    for i, color in enumerate(COLORS):
        rect = pygame.Rect(left + i * (size + gap), top, size, size)
        rgb = buttons[color].rgb.to_tuple()
        fill = rgb if color == lit_color else tuple(c // 4 for c in rgb)
        pygame.draw.rect(surface, fill, rect)
        pygame.draw.rect(surface, (255, 255, 255), rect, width=2)


@dataclass
class SimonState:
    sequence: list[Color]
    rounds_completed: int = 0
    phase: str = "showing"  # "showing" while playing back, "listening" while waiting on the player
    show_index: int = 0
    show_lit: bool = False
    # None only until the first real frame (or the start of a new round), so the
    # next flash is scheduled off an actual timestamp -- same idea as Tetris's
    # next_fall_at.
    phase_ends_at: int | None = None
    listen_index: int = 0
    lit_color: Color | None = None
    flash_ends_at: int = 0
    any_was_held: bool = False

    def _begin_show_step(self, current_time: int, index: int) -> None:
        self.show_index = index
        self.show_lit = True
        self.lit_color = self.sequence[index]
        buttons[self.lit_color].set_led(True)
        self.phase_ends_at = current_time + SHOW_ON_MS

    def _advance_showing(self, current_time: int) -> None:
        if self.phase_ends_at is None:
            self._begin_show_step(current_time, 0)
            return

        if current_time < self.phase_ends_at:
            return

        if self.show_lit:
            buttons[self.lit_color].set_led(False)
            self.lit_color = None
            self.show_lit = False
            self.phase_ends_at = current_time + SHOW_GAP_MS
            return

        next_index = self.show_index + 1
        if next_index >= len(self.sequence):
            self.phase = "listening"
            self.listen_index = 0
            self.phase_ends_at = None
            return

        self._begin_show_step(current_time, next_index)

    def _advance_listening(self, input: Input, current_time: int) -> State | None:
        if self.lit_color is not None and current_time >= self.flash_ends_at:
            buttons[self.lit_color].set_led(False)
            self.lit_color = None

        pressed = [color for button, color in zip(input.buttons, COLORS) if button.is_pressed()]

        if not pressed:
            self.any_was_held = False
            return self
        if self.any_was_held or len(pressed) != 1:
            return self
        self.any_was_held = True

        pressed_color = pressed[0]
        buttons[pressed_color].set_led(True)
        self.lit_color = pressed_color
        self.flash_ends_at = current_time + FLASH_MS

        if pressed_color != self.sequence[self.listen_index]:
            _clear_control_leds()
            return SimonResultScreen(score=self.rounds_completed)

        self.listen_index += 1
        if self.listen_index == len(self.sequence):
            # Round complete -- don't leave this press's feedback flash lit
            # once we switch over to playing back the longer sequence.
            if self.lit_color is not None:
                buttons[self.lit_color].set_led(False)
                self.lit_color = None
            self.rounds_completed += 1
            self.sequence.append(random.choice(COLORS))
            self.phase = "showing"
            self.phase_ends_at = None

        return self

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((10, 10, 25))
        white = (255, 255, 255)
        draw_text(surface, font(48), "Simon Says", (CANVAS_WIDTH // 2, 60), white)
        draw_text(surface, font(30), f"Round {self.rounds_completed + 1}", (CANVAS_WIDTH // 2, 120), white)

        hint = "Watch the pattern..." if self.phase == "showing" else "Your turn!"
        draw_text(surface, font(30), hint, (CANVAS_WIDTH // 2, 170), white)

        _draw_pad(surface, self.lit_color)

    def next_state(self, input: Input) -> State | None:
        if big_red_button_pressed():
            _clear_control_leds()
            return None  # back to the menu

        current_time = input.current_time

        if self.phase == "showing":
            self._advance_showing(current_time)
            return self

        return self._advance_listening(input, current_time)


@dataclass
class RulesScreen:
    """Shown once, before the first sequence plays, so the player knows the
    controls before they're standing at the box. "Play Again" from the result
    screen skips straight back into a fresh game rather than re-showing this.
    """

    ready: bool = True

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((10, 10, 25))
        white = (255, 255, 255)
        draw_text(surface, font(48), "Simon Says", (CANVAS_WIDTH // 2, 60), white)

        lines = [
            "Watch the buttons flash a pattern.",
            "Then press them back in the same order.",
            "Get it right and the pattern grows by one.",
            "One wrong press ends the game -- how far can you go?",
        ]
        y = 160
        for text in lines:
            draw_text(surface, font(28), text, (CANVAS_WIDTH // 2, y), white)
            y += 42

        draw_text(surface, font(30), "Press any button to continue", (CANVAS_WIDTH // 2, y + 20), white)

    def next_state(self, input: Input) -> State | None:
        if big_red_button_pressed():
            return None  # back to the menu

        any_pressed = any(button.is_pressed() for button in input.buttons)
        if not any_pressed:
            return self if self.ready else replace(self, ready=True)
        if not self.ready:
            return self

        return new_simon()


@dataclass
class SimonResultScreen:
    score: int  # rounds completed before the first wrong press
    ready: bool = False

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((10, 10, 25))
        white = (255, 255, 255)
        draw_text(surface, font(64), "Game Over", (CANVAS_WIDTH // 2, 90), white)
        draw_text(surface, font(32), f"Rounds completed: {self.score}", (CANVAS_WIDTH // 2, 160), white)
        draw_text(surface, font(30), "Green: Play Again", (CANVAS_WIDTH // 2, 260), white)
        draw_text(surface, font(30), "Red: Main Menu", (CANVAS_WIDTH // 2, 300), white)

    def next_state(self, input: Input) -> State | None:
        if big_red_button_pressed():
            _clear_control_leds()
            return None  # back to the menu

        _light_result_leds()

        any_pressed = any(button.is_pressed() for button in input.buttons)
        if not any_pressed:
            return self if self.ready else replace(self, ready=True)
        if not self.ready:
            return self

        if buttons[Color.GREEN].is_pressed():
            return new_simon()
        if buttons[Color.RED].is_pressed():
            return None  # back to the menu

        return self


def new_simon() -> SimonState:
    return SimonState(sequence=[random.choice(COLORS)])


def new_simon_with_rules() -> RulesScreen:
    return RulesScreen()

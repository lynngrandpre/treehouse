"""Vault Escape: a solo race against the clock through three short puzzle rooms,
each solved with the same five color buttons. Room 1 flashes a short code to
memorize and repeat; Room 2 is a riddle whose answer is one of the five colors;
Room 3 shows a code outright and just needs it entered correctly under
pressure. A wrong answer costs time rather than ending the game, so the whole
run is a single countdown shared across all three rooms -- reach the end of
Room 3 before the clock hits zero to escape.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace

import pygame

from common import Input, State, draw_text, font
from hardware import Color, big_red_button_pressed, buttons

TOTAL_TIME_MS = 90_000
WRONG_PENALTY_MS = 10_000

MEMORY_LENGTH = 4
FINAL_CODE_LENGTH = 4

FLASH_ON_MS = 500
FLASH_GAP_MS = 250

# Left to right, matching buttons_in_order / the physical layout.
COLORS_IN_ORDER = [Color.RED, Color.GREEN, Color.BLUE, Color.YELLOW, Color.WHITE]

RIDDLES: list[tuple[str, Color]] = [
    ("What color is a stop sign?", Color.RED),
    ("What color is fresh grass?", Color.GREEN),
    ("What color is a clear daytime sky?", Color.BLUE),
    ("What color is the sun in a kid's drawing?", Color.YELLOW),
    ("What color is fresh snow?", Color.WHITE),
    ("What color do you get mixing red and yellow paint?", Color.YELLOW),
    ("What color are most fire trucks?", Color.RED),
]

WIN_MESSAGE = "Vault cracked with time to spare!"


def _pressed_color(input: Input) -> Color | None:
    """The single color whose button is held this frame, or None if zero or
    more than one is held."""
    pressed = [i for i, button in enumerate(input.buttons) if button.is_pressed()]
    if len(pressed) != 1:
        return None
    return COLORS_IN_ORDER[pressed[0]]


def _random_code(length: int) -> list[Color]:
    return [random.choice(COLORS_IN_ORDER) for _ in range(length)]


def _seconds_left(deadline: int | None, current_time: int) -> int:
    remaining_ms = (deadline - current_time) if deadline is not None else TOTAL_TIME_MS
    return max(0, remaining_ms) // 1000


def _draw_hud(surface: pygame.Surface, room: int, deadline: int | None) -> None:
    CANVAS_WIDTH, _ = surface.get_size()
    surface.fill((10, 10, 25))
    white = (255, 255, 255)
    draw_text(surface, font(24), f"Room {room} of 3", (100, 24), white)
    seconds = _seconds_left(deadline, pygame.time.get_ticks())
    draw_text(surface, font(24), f"Time: {seconds}s", (CANVAS_WIDTH - 100, 24), white)


@dataclass
class VaultResultScreen:
    won: bool
    # Starts unarmed: the press (or timeout) that got us here can still have a
    # button held on the very first frame we're drawn, and we don't want that
    # to instantly bounce onward. Require a release first.
    ready: bool = False

    def draw(self, surface: pygame.Surface) -> None:
        CANVAS_WIDTH, _ = surface.get_size()
        surface.fill((10, 10, 25))
        white = (255, 255, 255)
        headline = "You Escaped!" if self.won else "Time's Up!"
        message = WIN_MESSAGE if self.won else "The vault stays locked this time."
        draw_text(surface, font(40), headline, (CANVAS_WIDTH // 2, 90), white)
        draw_text(surface, font(26), message, (CANVAS_WIDTH // 2, 160), white)
        draw_text(surface, font(28), "Green: Play Again", (CANVAS_WIDTH // 2, 280), white)
        draw_text(surface, font(28), "Red: Main Menu", (CANVAS_WIDTH // 2, 320), white)

    def next_state(self, input: Input) -> State | None:
        if big_red_button_pressed():
            return None  # back to the menu

        any_pressed = any(button.is_pressed() for button in input.buttons)
        if not any_pressed:
            # Buttons released -- arm the next press.
            return self if self.ready else replace(self, ready=True)
        if not self.ready:
            # Still the press (or timeout) that got us here; wait for release.
            return self

        if buttons[Color.GREEN].is_pressed():
            return new_vault_escape()
        if buttons[Color.RED].is_pressed():
            return None  # back to the menu

        return self


@dataclass
class MemoryShowState:
    """Room 1: flashes `sequence` once, then hands off to MemoryEntryState."""

    sequence: list[Color]
    # None only on the very first frame of the whole run, before a deadline
    # has been picked; also re-anchored (kept, not reset) on a wrong repeat.
    deadline: int | None = None
    # None whenever this room's flash still needs to (re)anchor -- fresh game
    # start or a wrong repeat sending the player back here.
    flash_start: int | None = None

    def draw(self, surface: pygame.Surface) -> None:
        CANVAS_WIDTH, CANVAS_HEIGHT = surface.get_size()
        _draw_hud(surface, room=1, deadline=self.deadline)
        white = (255, 255, 255)
        draw_text(surface, font(30), "Memorize the code!", (CANVAS_WIDTH // 2, 90), white)

        current_time = pygame.time.get_ticks()
        anchor = self.flash_start if self.flash_start is not None else current_time
        elapsed = max(0, current_time - anchor)
        step = FLASH_ON_MS + FLASH_GAP_MS
        index = elapsed // step
        if 0 <= index < len(self.sequence) and (elapsed % step) < FLASH_ON_MS:
            color = self.sequence[index]
            center = (CANVAS_WIDTH // 2, CANVAS_HEIGHT // 2 + 30)
            pygame.draw.circle(surface, buttons[color].rgb.to_tuple(), center, 80)
            pygame.draw.circle(surface, white, center, 80, 3)

    def next_state(self, input: Input) -> State | None:
        if big_red_button_pressed():
            return None  # back to the menu

        if self.deadline is None:
            return replace(self, deadline=input.current_time + TOTAL_TIME_MS, flash_start=input.current_time)
        if input.current_time >= self.deadline:
            return VaultResultScreen(won=False)
        if self.flash_start is None:
            return replace(self, flash_start=input.current_time)

        elapsed = max(0, input.current_time - self.flash_start)
        step = FLASH_ON_MS + FLASH_GAP_MS
        index = elapsed // step
        flashing = self.sequence[index] if 0 <= index < len(self.sequence) and (elapsed % step) < FLASH_ON_MS else None
        for color, button in buttons.items():
            button.set_led(color == flashing)

        if index >= len(self.sequence):
            for button in buttons.values():
                button.set_led(False)
            return MemoryEntryState(sequence=self.sequence, deadline=self.deadline)
        return self


@dataclass
class MemoryEntryState:
    """Room 1's second half: repeat the flashed sequence button-for-button."""

    sequence: list[Color]
    deadline: int
    progress: int = 0
    # Time-driven arrival from MemoryShowState, not a press -- no stale press
    # to debounce, so this starts armed.
    ready: bool = True

    def draw(self, surface: pygame.Surface) -> None:
        CANVAS_WIDTH, CANVAS_HEIGHT = surface.get_size()
        _draw_hud(surface, room=1, deadline=self.deadline)
        white = (255, 255, 255)
        draw_text(surface, font(30), f"Repeat the code ({self.progress}/{len(self.sequence)})", (CANVAS_WIDTH // 2, 90), white)

        dot_size = 26
        gap = 12
        total_width = len(self.sequence) * dot_size + max(0, len(self.sequence) - 1) * gap
        start_x = CANVAS_WIDTH // 2 - total_width // 2
        y = CANVAS_HEIGHT // 2 + 30
        for i in range(len(self.sequence)):
            center = (start_x + i * (dot_size + gap) + dot_size // 2, y)
            if i < self.progress:
                pygame.draw.circle(surface, white, center, dot_size // 2)
            pygame.draw.circle(surface, white, center, dot_size // 2, 2)

    def next_state(self, input: Input) -> State | None:
        if big_red_button_pressed():
            return None  # back to the menu
        if input.current_time >= self.deadline:
            return VaultResultScreen(won=False)

        any_pressed = any(button.is_pressed() for button in input.buttons)
        if not any_pressed:
            return self if self.ready else replace(self, ready=True)
        if not self.ready:
            return self

        color = _pressed_color(input)
        if color is None:
            return self

        if color != self.sequence[self.progress]:
            # Wrong repeat: costs time, re-flash the same code from scratch.
            return MemoryShowState(sequence=self.sequence, deadline=self.deadline - WRONG_PENALTY_MS)

        new_progress = self.progress + 1
        if new_progress >= len(self.sequence):
            return _new_riddle_state(self.deadline)
        return replace(self, progress=new_progress, ready=False)


@dataclass
class RiddleState:
    """Room 2: a riddle whose answer is one of the five button colors."""

    question: str
    answer: Color
    deadline: int
    ready: bool = True

    def draw(self, surface: pygame.Surface) -> None:
        CANVAS_WIDTH, _ = surface.get_size()
        _draw_hud(surface, room=2, deadline=self.deadline)
        white = (255, 255, 255)
        draw_text(surface, font(30), self.question, (CANVAS_WIDTH // 2, 160), white)
        draw_text(surface, font(24), "Press the button that answers it", (CANVAS_WIDTH // 2, 220), white)

    def next_state(self, input: Input) -> State | None:
        if big_red_button_pressed():
            return None  # back to the menu
        if input.current_time >= self.deadline:
            return VaultResultScreen(won=False)

        any_pressed = any(button.is_pressed() for button in input.buttons)
        if not any_pressed:
            return self if self.ready else replace(self, ready=True)
        if not self.ready:
            return self

        color = _pressed_color(input)
        if color is None:
            return self

        if color != self.answer:
            # Wrong answer: costs time, same riddle stays up to retry.
            return replace(self, deadline=self.deadline - WRONG_PENALTY_MS, ready=False)

        return _new_final_code_state(self.deadline)


@dataclass
class FinalCodeState:
    """Room 3: the code is shown outright -- just enter it correctly under
    the pressure of the ticking clock to escape."""

    code: list[Color]
    deadline: int
    progress: int = 0
    ready: bool = True

    def draw(self, surface: pygame.Surface) -> None:
        CANVAS_WIDTH, CANVAS_HEIGHT = surface.get_size()
        _draw_hud(surface, room=3, deadline=self.deadline)
        white = (255, 255, 255)
        draw_text(surface, font(30), "Enter the code to escape!", (CANVAS_WIDTH // 2, 90), white)

        slot_size = 40
        gap = 14
        total_width = len(self.code) * slot_size + max(0, len(self.code) - 1) * gap
        start_x = CANVAS_WIDTH // 2 - total_width // 2
        y = CANVAS_HEIGHT // 2 + 20
        for i, color in enumerate(self.code):
            center = (start_x + i * (slot_size + gap) + slot_size // 2, y)
            pygame.draw.circle(surface, buttons[color].rgb.to_tuple(), center, slot_size // 2)
            if i < self.progress:
                pygame.draw.circle(surface, white, center, slot_size // 2, 4)

    def next_state(self, input: Input) -> State | None:
        if big_red_button_pressed():
            return None  # back to the menu
        if input.current_time >= self.deadline:
            return VaultResultScreen(won=False)

        any_pressed = any(button.is_pressed() for button in input.buttons)
        if not any_pressed:
            return self if self.ready else replace(self, ready=True)
        if not self.ready:
            return self

        color = _pressed_color(input)
        if color is None:
            return self

        if color != self.code[self.progress]:
            # Wrong entry: costs time, start this code over from the top.
            return replace(self, progress=0, deadline=self.deadline - WRONG_PENALTY_MS, ready=False)

        new_progress = self.progress + 1
        if new_progress >= len(self.code):
            return VaultResultScreen(won=True)
        return replace(self, progress=new_progress, ready=False)


def _new_riddle_state(deadline: int) -> RiddleState:
    question, answer = random.choice(RIDDLES)
    return RiddleState(question=question, answer=answer, deadline=deadline)


def _new_final_code_state(deadline: int) -> FinalCodeState:
    return FinalCodeState(code=_random_code(FINAL_CODE_LENGTH), deadline=deadline)


def new_vault_escape() -> MemoryShowState:
    return MemoryShowState(sequence=_random_code(MEMORY_LENGTH))

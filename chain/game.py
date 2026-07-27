"""Chain Reaction: a two-player cooperative memory game. The chain starts
empty; on each turn the active player watches it flash back, repeats it
button-for-button, and then adds one new link of their own choosing. Turns
alternate, so the chain -- and the shared risk of forgetting it -- keeps
growing between both players. A wrong repeat breaks the chain for the whole
team; reaching WIN_LENGTH links is a shared win.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import pygame

from common import Input, State, draw_text, font
from hardware import Color, big_red_button_pressed, buttons

WIN_LENGTH = 12

FLASH_ON_MS = 500
FLASH_GAP_MS = 250

# Left to right, matching buttons_in_order / the physical layout.
COLORS_IN_ORDER = [Color.RED, Color.GREEN, Color.BLUE, Color.YELLOW, Color.WHITE]

WIN_MESSAGE = "Unbreakable! You chained the whole thing together!"


def _pressed_color(input: Input) -> Color | None:
    """The single color whose button is held this frame, or None if zero or
    more than one is held."""
    pressed = [i for i, button in enumerate(input.buttons) if button.is_pressed()]
    if len(pressed) != 1:
        return None
    return COLORS_IN_ORDER[pressed[0]]


@dataclass
class ChainResultScreen:
    sequence: list[Color]
    broke_turn: int  # which player (0 or 1) was active when the chain ended
    won: bool
    # Starts unarmed: the press that got us here is often still held on the
    # very first frame we're drawn, and we don't want that same press to
    # instantly bounce onward. Require a release first.
    ready: bool = False

    def _message(self) -> str:
        if self.won:
            return WIN_MESSAGE
        return f"Player {self.broke_turn + 1} dropped the chain at link {len(self.sequence) + 1}!"

    def draw(self, surface: pygame.Surface) -> None:
        CANVAS_WIDTH, _ = surface.get_size()
        surface.fill((10, 10, 25))
        headline = "Chain Complete!" if self.won else "Chain Broken :("
        white = (255, 255, 255)
        draw_text(surface, font(32), headline, (CANVAS_WIDTH // 2, 60), white)
        draw_text(surface, font(22), self._message(), (CANVAS_WIDTH // 2, 105), white)
        draw_text(surface, font(20), f"Final chain length: {len(self.sequence)}", (CANVAS_WIDTH // 2, 145), white)

        draw_text(surface, font(22), "Green: Play Again", (CANVAS_WIDTH // 2, 260), white)
        draw_text(surface, font(22), "Red: Main Menu", (CANVAS_WIDTH // 2, 292), white)

    def next_state(self, input: Input) -> State | None:
        if big_red_button_pressed():
            return None  # back to the menu

        any_pressed = any(button.is_pressed() for button in input.buttons)
        if not any_pressed:
            # Buttons released -- arm the next press.
            return self if self.ready else replace(self, ready=True)
        if not self.ready:
            # Still the press that got us here; wait for it to release.
            return self

        if buttons[Color.GREEN].is_pressed():
            return new_chain()
        if buttons[Color.RED].is_pressed():
            return None  # back to the menu

        # Any other button: message stays up, keep waiting for Green or Red.
        return self


@dataclass
class EntryState:
    sequence: list[Color]
    turn: int  # 0 or 1, whose turn it is to repeat-then-add
    progress: int = 0  # how many links of the sequence have been repeated so far
    # Debounces button presses the same way GuessEntryState does -- one action
    # per physical press, not one per frame a button is held.
    ready: bool = True

    def draw(self, surface: pygame.Surface) -> None:
        CANVAS_WIDTH, CANVAS_HEIGHT = surface.get_size()
        surface.fill((10, 10, 25))
        white = (255, 255, 255)
        draw_text(surface, font(28), f"Player {self.turn + 1}'s turn", (CANVAS_WIDTH // 2, 30), white)

        if self.progress < len(self.sequence):
            instruction = f"Repeat the chain ({self.progress}/{len(self.sequence)})"
        else:
            instruction = "Add a new link!"
        draw_text(surface, font(22), instruction, (CANVAS_WIDTH // 2, 70), white)
        draw_text(surface, font(18), f"Chain length: {len(self.sequence)}", (CANVAS_WIDTH // 2, 105), white)

        # Filled dots for links already repeated correctly this turn, empty
        # slots for the rest -- never reveals colors the player hasn't proven
        # they remember yet.
        dot_size = 22
        gap = 10
        total_width = len(self.sequence) * dot_size + max(0, len(self.sequence) - 1) * gap
        start_x = CANVAS_WIDTH // 2 - total_width // 2
        y = CANVAS_HEIGHT // 2 + 40
        for i in range(len(self.sequence)):
            center = (start_x + i * (dot_size + gap) + dot_size // 2, y)
            if i < self.progress:
                pygame.draw.circle(surface, buttons[self.sequence[i]].rgb.to_tuple(), center, dot_size // 2)
            pygame.draw.circle(surface, white, center, dot_size // 2, 2)

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
            # press, the same way GuessEntryState does.
            return self

        if self.progress < len(self.sequence):
            if color != self.sequence[self.progress]:
                return ChainResultScreen(sequence=self.sequence, broke_turn=self.turn, won=False)
            return replace(self, progress=self.progress + 1, ready=False)

        # Fully repeated the existing chain -- this press adds a new link.
        new_sequence = self.sequence + [color]
        if len(new_sequence) >= WIN_LENGTH:
            return ChainResultScreen(sequence=new_sequence, broke_turn=self.turn, won=True)
        return ShowSequenceState(sequence=new_sequence, turn=1 - self.turn)


@dataclass
class ShowSequenceState:
    sequence: list[Color]
    turn: int  # 0 or 1, whose turn is about to enter
    # Anchors the flash animation to the frame we're first drawn on, rather
    # than tick=0, the same way color_game times its victory animation off of
    # input.current_time. None on construction; next_state fills it in.
    start_time: int | None = None

    def draw(self, surface: pygame.Surface) -> None:
        CANVAS_WIDTH, CANVAS_HEIGHT = surface.get_size()
        surface.fill((10, 10, 25))
        white = (255, 255, 255)
        draw_text(surface, font(28), f"Player {self.turn + 1}'s turn -- watch!", (CANVAS_WIDTH // 2, 30), white)
        draw_text(surface, font(18), f"Chain length: {len(self.sequence)}", (CANVAS_WIDTH // 2, 65), white)

        current_time = pygame.time.get_ticks()
        anchor = self.start_time if self.start_time is not None else current_time
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

        if self.start_time is None:
            return replace(self, start_time=input.current_time)

        elapsed = max(0, input.current_time - self.start_time)
        step = FLASH_ON_MS + FLASH_GAP_MS
        index = elapsed // step
        flashing = self.sequence[index] if 0 <= index < len(self.sequence) and (elapsed % step) < FLASH_ON_MS else None
        for color, button in buttons.items():
            button.set_led(color == flashing)

        if index >= len(self.sequence):
            for button in buttons.values():
                button.set_led(False)
            # Unlike GuessEntryState's ready=False on a fresh guess, nothing
            # here was just pressed to cause this transition -- it's purely
            # time-driven -- so there's no stale press to debounce.
            return EntryState(sequence=self.sequence, turn=self.turn, progress=0)
        return self


def new_chain() -> ShowSequenceState:
    return ShowSequenceState(sequence=[], turn=0)

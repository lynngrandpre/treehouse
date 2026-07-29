"""Tetris: Red/Yellow slide the falling piece left and right, Green rotates it,
Blue hard-drops it straight to the floor. Pieces fall on their own; clear full
rows to score, and see how long you can last before the stack reaches the top.

A single continuous state that mutates and returns itself every frame, in the
"continuous game" style described in the README (see color_game) -- the board
and falling piece are shared mutable state, but unlike Breakout's pixel
physics everything here is driven off absolute timestamps gating discrete
grid steps (fall, shift, repeat), the same style already used for Breakout's
serve delay and turbo latch.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field, replace

import pygame

from common import Input, State, draw_text, font
from hardware import Color, big_red_button_pressed, buttons

CANVAS_WIDTH = 800
CANVAS_HEIGHT = 480
HUD_HEIGHT = 40
WALL_COLOR = (70, 70, 100)

BOARD_COLS = 10
BOARD_ROWS = 20
CELL_SIZE = 20

# A side panel (score, lines, next piece) sits to the right of the board, so
# the board is centered within the canvas *minus* that panel -- same layout
# idea as Breakout's score box.
SIDE_PANEL_WIDTH = 180
PLAY_REGION_WIDTH = CANVAS_WIDTH - SIDE_PANEL_WIDTH
BOARD_WIDTH = BOARD_COLS * CELL_SIZE
BOARD_HEIGHT = BOARD_ROWS * CELL_SIZE
BOARD_LEFT = (PLAY_REGION_WIDTH - BOARD_WIDTH) // 2
BOARD_TOP = HUD_HEIGHT + 10

SIDE_PANEL_LEFT = CANVAS_WIDTH - SIDE_PANEL_WIDTH
BOX_WIDTH = 140
BOX_LEFT = SIDE_PANEL_LEFT + (SIDE_PANEL_WIDTH - BOX_WIDTH) // 2
SCORE_BOX_RECT = pygame.Rect(BOX_LEFT, HUD_HEIGHT + 10, BOX_WIDTH, 90)
LINES_BOX_RECT = pygame.Rect(BOX_LEFT, SCORE_BOX_RECT.bottom + 15, BOX_WIDTH, 70)
NEXT_BOX_RECT = pygame.Rect(BOX_LEFT, LINES_BOX_RECT.bottom + 15, BOX_WIDTH, 140)

PIECE_SHAPES = {
    "I": [[0, 0, 0, 0], [1, 1, 1, 1], [0, 0, 0, 0], [0, 0, 0, 0]],
    "O": [[1, 1], [1, 1]],
    "T": [[0, 1, 0], [1, 1, 1], [0, 0, 0]],
    "S": [[0, 1, 1], [1, 1, 0], [0, 0, 0]],
    "Z": [[1, 1, 0], [0, 1, 1], [0, 0, 0]],
    "J": [[1, 0, 0], [1, 1, 1], [0, 0, 0]],
    "L": [[0, 0, 1], [1, 1, 1], [0, 0, 0]],
}
PIECE_COLORS = {
    "I": (70, 200, 230),
    "O": (230, 210, 50),
    "T": (170, 80, 200),
    "S": (70, 200, 90),
    "Z": (230, 60, 60),
    "J": (60, 90, 230),
    "L": (230, 140, 50),
}
PIECE_TYPES = list(PIECE_SHAPES.keys())


def _rotate_cw(matrix: list[list[int]]) -> list[list[int]]:
    n = len(matrix)
    return [[matrix[n - 1 - c][r] for c in range(n)] for r in range(n)]


def _all_rotations(shape: list[list[int]]) -> list[list[list[int]]]:
    rotations = [shape]
    current = shape
    for _ in range(3):
        current = _rotate_cw(current)
        rotations.append(current)
    return rotations


PIECE_ROTATIONS = {name: _all_rotations(shape) for name, shape in PIECE_SHAPES.items()}

LINE_SCORES = [0, 100, 300, 500, 800]  # indexed by lines cleared in one lock
INITIAL_FALL_INTERVAL_MS = 800
FALL_SPEEDUP_PER_LINES = 10  # every this many lines, the fall interval shortens
FALL_SPEEDUP_STEP_MS = 50
MIN_FALL_INTERVAL_MS = 150
MOVE_INITIAL_DELAY_MS = 200  # how long a held direction waits before repeating
MOVE_REPEAT_MS = 80  # repeat interval once auto-shift kicks in


def _spawn_position(piece_type: str) -> tuple[int, int]:
    size = len(PIECE_SHAPES[piece_type])
    return (BOARD_COLS - size) // 2, 0


def _piece_cells(piece_type: str, rotation: int, col: int, row: int) -> list[tuple[int, int]]:
    matrix = PIECE_ROTATIONS[piece_type][rotation % 4]
    return [(col + dx, row + dy) for dy, line in enumerate(matrix) for dx, filled in enumerate(line) if filled]


def _light_control_leds() -> None:
    """Every button but White does something here, so every one but White
    stays lit as a reminder."""
    buttons[Color.RED].set_led(True)
    buttons[Color.YELLOW].set_led(True)
    buttons[Color.GREEN].set_led(True)
    buttons[Color.BLUE].set_led(True)
    buttons[Color.WHITE].set_led(False)


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


def _draw_label_box(surface: pygame.Surface, rect: pygame.Rect, label: str, value: str) -> None:
    white = (255, 255, 255)
    pygame.draw.rect(surface, WALL_COLOR, rect, width=2)
    draw_text(surface, font(18), label, (rect.centerx, rect.top + 22), white)
    draw_text(surface, font(30), value, (rect.centerx, rect.top + 58), white)


def _draw_next_box(surface: pygame.Surface, rect: pygame.Rect, piece_type: str) -> None:
    white = (255, 255, 255)
    pygame.draw.rect(surface, WALL_COLOR, rect, width=2)
    draw_text(surface, font(18), "NEXT", (rect.centerx, rect.top + 22), white)

    matrix = PIECE_ROTATIONS[piece_type][0]
    preview_cell = 18
    grid_width = len(matrix[0]) * preview_cell
    origin_x = rect.centerx - grid_width // 2
    origin_y = rect.top + 40
    for dy, line in enumerate(matrix):
        for dx, filled in enumerate(line):
            if filled:
                cell_rect = pygame.Rect(origin_x + dx * preview_cell, origin_y + dy * preview_cell, preview_cell, preview_cell)
                pygame.draw.rect(surface, PIECE_COLORS[piece_type], cell_rect.inflate(-2, -2))


@dataclass
class TetrisState:
    board: list[list[str | None]]
    piece_type: str
    piece_rotation: int
    piece_col: int
    piece_row: int
    next_piece: str
    score: int = 0
    lines_cleared: int = 0
    # None only until the first real frame, so the fall timer is scheduled
    # off an actual timestamp rather than whatever time it was at import.
    next_fall_at: int | None = None
    move_repeat_at: int = 0
    last_move_dir: int = 0
    green_was_held: bool = False
    blue_was_held: bool = False

    def _fits(self, cells: list[tuple[int, int]]) -> bool:
        for col, row in cells:
            if col < 0 or col >= BOARD_COLS or row < 0 or row >= BOARD_ROWS:
                return False
            if self.board[row][col] is not None:
                return False
        return True

    def _try_move(self, dx: int, dy: int) -> bool:
        new_col, new_row = self.piece_col + dx, self.piece_row + dy
        if not self._fits(_piece_cells(self.piece_type, self.piece_rotation, new_col, new_row)):
            return False
        self.piece_col, self.piece_row = new_col, new_row
        return True

    def _try_rotate(self) -> bool:
        new_rotation = (self.piece_rotation + 1) % 4
        for kick_dx in (0, -1, 1, -2, 2):
            cells = _piece_cells(self.piece_type, new_rotation, self.piece_col + kick_dx, self.piece_row)
            if self._fits(cells):
                self.piece_rotation = new_rotation
                self.piece_col += kick_dx
                return True
        return False

    def _fall_interval_ms(self) -> int:
        steps = self.lines_cleared // FALL_SPEEDUP_PER_LINES
        return max(MIN_FALL_INTERVAL_MS, INITIAL_FALL_INTERVAL_MS - steps * FALL_SPEEDUP_STEP_MS)

    def _lock_piece(self) -> bool:
        """Locks the falling piece into the board, clears any full rows, and
        spawns the next piece. Returns True if that new piece has nowhere to
        spawn -- game over."""
        for col, row in _piece_cells(self.piece_type, self.piece_rotation, self.piece_col, self.piece_row):
            self.board[row][col] = self.piece_type

        remaining_rows = [row for row in self.board if any(cell is None for cell in row)]
        cleared = BOARD_ROWS - len(remaining_rows)
        for _ in range(cleared):
            remaining_rows.insert(0, [None] * BOARD_COLS)
        self.board = remaining_rows
        if cleared:
            self.lines_cleared += cleared
            self.score += LINE_SCORES[min(cleared, len(LINE_SCORES) - 1)]

        self.piece_type = self.next_piece
        self.piece_rotation = 0
        self.piece_col, self.piece_row = _spawn_position(self.piece_type)
        self.next_piece = random.choice(PIECE_TYPES)

        return not self._fits(_piece_cells(self.piece_type, self.piece_rotation, self.piece_col, self.piece_row))

    def _hard_drop(self) -> bool:
        while self._try_move(0, 1):
            pass
        return self._lock_piece()

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((10, 10, 25))

        board_rect = pygame.Rect(BOARD_LEFT, BOARD_TOP, BOARD_WIDTH, BOARD_HEIGHT)
        pygame.draw.rect(surface, WALL_COLOR, board_rect, width=3)

        for row in range(BOARD_ROWS):
            for col in range(BOARD_COLS):
                cell = self.board[row][col]
                if cell is not None:
                    self._draw_cell(surface, col, row, PIECE_COLORS[cell])
        for col, row in _piece_cells(self.piece_type, self.piece_rotation, self.piece_col, self.piece_row):
            self._draw_cell(surface, col, row, PIECE_COLORS[self.piece_type])

        _draw_label_box(surface, SCORE_BOX_RECT, "SCORE", str(self.score))
        _draw_label_box(surface, LINES_BOX_RECT, "LINES", str(self.lines_cleared))
        _draw_next_box(surface, NEXT_BOX_RECT, self.next_piece)

    def _draw_cell(self, surface: pygame.Surface, col: int, row: int, color: tuple[int, int, int]) -> None:
        rect = pygame.Rect(BOARD_LEFT + col * CELL_SIZE, BOARD_TOP + row * CELL_SIZE, CELL_SIZE, CELL_SIZE)
        pygame.draw.rect(surface, color, rect.inflate(-2, -2))

    def next_state(self, input: Input) -> State | None:
        if big_red_button_pressed():
            _clear_control_leds()
            return None  # back to the menu

        current_time = input.current_time
        if self.next_fall_at is None:
            self.next_fall_at = current_time + self._fall_interval_ms()

        _light_control_leds()

        red_held = buttons[Color.RED].is_pressed()
        yellow_held = buttons[Color.YELLOW].is_pressed()
        green_held = buttons[Color.GREEN].is_pressed()
        blue_held = buttons[Color.BLUE].is_pressed()

        desired_dx = 0
        if red_held and not yellow_held:
            desired_dx = -1
        elif yellow_held and not red_held:
            desired_dx = 1

        if desired_dx != 0:
            if desired_dx != self.last_move_dir:
                self._try_move(desired_dx, 0)
                self.move_repeat_at = current_time + MOVE_INITIAL_DELAY_MS
            elif current_time >= self.move_repeat_at:
                self._try_move(desired_dx, 0)
                self.move_repeat_at = current_time + MOVE_REPEAT_MS
        self.last_move_dir = desired_dx

        if green_held and not self.green_was_held:
            self._try_rotate()
        self.green_was_held = green_held

        if blue_held and not self.blue_was_held:
            if self._hard_drop():
                _clear_control_leds()
                return TetrisResultScreen(score=self.score, lines_cleared=self.lines_cleared)
        self.blue_was_held = blue_held

        if current_time >= self.next_fall_at:
            if not self._try_move(0, 1):
                if self._lock_piece():
                    _clear_control_leds()
                    return TetrisResultScreen(score=self.score, lines_cleared=self.lines_cleared)
            self.next_fall_at = current_time + self._fall_interval_ms()

        return self


@dataclass
class RulesScreen:
    """Shown once, before the pieces start falling, so the player knows the
    controls before they're standing at the box. "Play Again" from the result
    screen skips straight back into a fresh game rather than re-showing this.
    """

    ready: bool = True

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((10, 10, 25))
        white = (255, 255, 255)
        draw_text(surface, font(48), "Tetris", (CANVAS_WIDTH // 2, 50), white)

        lines = [
            ("Red = left, Yellow = right", white),
            ("Green = rotate, Blue = drop", white),
            ("Pieces fall on their own -- clear full rows to score.", white),
            ("The stack keeps rising -- see how long you can last.", white),
        ]
        y = 150
        for text, color in lines:
            draw_text(surface, font(30), text, (CANVAS_WIDTH // 2, y), color)
            y += 48

        draw_text(surface, font(30), "Press any button to continue", (CANVAS_WIDTH // 2, y + 20), white)

    def next_state(self, input: Input) -> State | None:
        if big_red_button_pressed():
            return None  # back to the menu

        any_pressed = any(button.is_pressed() for button in input.buttons)
        if not any_pressed:
            return self if self.ready else replace(self, ready=True)
        if not self.ready:
            return self

        return new_tetris()


@dataclass
class TetrisResultScreen:
    score: int
    lines_cleared: int
    # Starts unarmed: the press that got us here may still have a button
    # held on the very first frame we're drawn. Require a release first,
    # same as the other games' result screens.
    ready: bool = False

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((10, 10, 25))
        white = (255, 255, 255)
        draw_text(surface, font(64), "Game Over", (CANVAS_WIDTH // 2, 90), white)
        draw_text(surface, font(32), "The stack reached the top -- nice run!", (CANVAS_WIDTH // 2, 160), white)
        draw_text(surface, font(32), f"Score: {self.score}  |  Lines: {self.lines_cleared}", (CANVAS_WIDTH // 2, 205), white)
        draw_text(surface, font(30), "Green: Play Again", (CANVAS_WIDTH // 2, 300), white)
        draw_text(surface, font(30), "Red: Main Menu", (CANVAS_WIDTH // 2, 340), white)

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
            return new_tetris()
        if buttons[Color.RED].is_pressed():
            return None  # back to the menu

        return self


def new_tetris() -> TetrisState:
    piece_type = random.choice(PIECE_TYPES)
    next_piece = random.choice(PIECE_TYPES)
    piece_col, piece_row = _spawn_position(piece_type)
    return TetrisState(
        board=[[None] * BOARD_COLS for _ in range(BOARD_ROWS)],
        piece_type=piece_type,
        piece_rotation=0,
        piece_col=piece_col,
        piece_row=piece_row,
        next_piece=next_piece,
    )


def new_tetris_with_rules() -> RulesScreen:
    return RulesScreen()

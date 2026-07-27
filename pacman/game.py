"""Pac-Duo: a two-player cooperative maze chase. Control of the single shared
character is split across the two players -- Player 1 owns horizontal
movement (Red/Yellow), Player 2 owns vertical movement (Blue/Green) -- so
neither can cross the maze alone without the other's help. White cashes in a
stored power pellet to scare the ghosts for a while. Clear every pellet to
win; get caught by a ghost while not scared and the whole team loses.

A single continuous state that mutates and returns itself every frame, in the
"continuous game" style described in the README (see color_game), rather than
the discrete state-machine style of quiz/mastermind -- the maze, pellets, and
ghosts are all shared mutable state ticking forward in real time.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import pygame

from common import Input, State, draw_text, font
from hardware import Color, big_red_button_pressed, buttons

CELL = 40
COLS = 20
ROWS = 11
HUD_HEIGHT = 40

MOVE_INTERVAL_MS = 160
GHOST_INTERVAL_MS = 220
SCARED_DURATION_MS = 6000

WIN_MESSAGE = "Maze cleared! Flawless teamwork."


def _sign(n: int) -> int:
    return (n > 0) - (n < 0)


def _build_maze() -> tuple[list[list[str]], tuple[int, int], list[tuple[int, int]]]:
    grid = [['#' if r in (0, ROWS - 1) or c in (0, COLS - 1) else '.' for c in range(COLS)] for r in range(ROWS)]

    # A scattering of single-cell obstacles rather than a hand-carved maze --
    # trivially guarantees every open cell stays reachable, while still
    # giving the ghosts (and the players) something to dodge around.
    obstacles = [(3, 4), (3, 8), (3, 12), (3, 16), (7, 4), (7, 8), (7, 12), (7, 16)]
    for r, c in obstacles:
        grid[r][c] = '#'

    for r, c in [(1, 10), (9, 10)]:
        grid[r][c] = 'o'

    player_start = (5, 10)
    ghost_starts = [(1, 1), (9, 18)]
    for r, c in [player_start, *ghost_starts]:
        grid[r][c] = ' '

    return grid, player_start, ghost_starts


@dataclass
class Ghost:
    pos: tuple[int, int]
    start: tuple[int, int]


@dataclass
class PacDuoState:
    grid: list[list[str]]
    player_pos: tuple[int, int]
    ghosts: list[Ghost]
    pellets_remaining: int
    last_move_time: int = 0
    last_ghost_time: int = 0
    scared_until: int = 0
    stored_powerups: int = 0
    white_was_held: bool = False

    def _blocked(self, row: int, col: int) -> bool:
        return self.grid[row][col] == '#'

    def draw(self, surface: pygame.Surface) -> None:
        white = (255, 255, 255)
        surface.fill((0, 0, 0))
        draw_text(
            surface, font(20),
            f"Pellets: {self.pellets_remaining}   Power-ups: {self.stored_powerups} (White)",
            (surface.get_width() // 2, 20), white,
        )

        for row in range(len(self.grid)):
            for col in range(len(self.grid[row])):
                cell = self.grid[row][col]
                x, y = col * CELL, HUD_HEIGHT + row * CELL
                if cell == '#':
                    pygame.draw.rect(surface, (40, 40, 90), (x, y, CELL, CELL))
                elif cell == '.':
                    pygame.draw.circle(surface, (255, 220, 120), (x + CELL // 2, y + CELL // 2), 4)
                elif cell == 'o':
                    pygame.draw.circle(surface, (255, 180, 60), (x + CELL // 2, y + CELL // 2), 9)

        scared = pygame.time.get_ticks() < self.scared_until
        ghost_colors = [(230, 30, 30), (230, 30, 180)]
        for i, ghost in enumerate(self.ghosts):
            gx = ghost.pos[1] * CELL + CELL // 2
            gy = HUD_HEIGHT + ghost.pos[0] * CELL + CELL // 2
            color = (80, 120, 255) if scared else ghost_colors[i % len(ghost_colors)]
            pygame.draw.circle(surface, color, (gx, gy), CELL // 2 - 4)

        prow, pcol = self.player_pos
        px, py = pcol * CELL + CELL // 2, HUD_HEIGHT + prow * CELL + CELL // 2
        pygame.draw.circle(surface, (255, 230, 0), (px, py), CELL // 2 - 4)

    def _step_ghost(self, ghost: Ghost, scared: bool) -> None:
        row, col = ghost.pos
        prow, pcol = self.player_pos
        dr, dc = prow - row, pcol - col
        if scared:
            dr, dc = -dr, -dc

        moves = sorted(
            (m for m in [(_sign(dr), 0), (0, _sign(dc))] if m != (0, 0)),
            key=lambda m: -(abs(dr) if m[0] else abs(dc)),
        )
        for mr, mc in moves:
            nr, nc = row + mr, col + mc
            if not self._blocked(nr, nc):
                ghost.pos = (nr, nc)
                return

        # Every direct route toward (or away from) the player is blocked --
        # try any open neighbor so the ghost doesn't just freeze at a wall.
        for mr, mc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = row + mr, col + mc
            if not self._blocked(nr, nc):
                ghost.pos = (nr, nc)
                return

    def next_state(self, input: Input) -> State | None:
        if big_red_button_pressed():
            return None  # back to the menu

        current_time = input.current_time

        white_held = buttons[Color.WHITE].is_pressed()
        if white_held and not self.white_was_held and self.stored_powerups > 0:
            self.stored_powerups -= 1
            self.scared_until = current_time + SCARED_DURATION_MS
        self.white_was_held = white_held

        if current_time - self.last_move_time >= MOVE_INTERVAL_MS:
            self.last_move_time = current_time
            dx = (1 if buttons[Color.YELLOW].is_pressed() else 0) - (1 if buttons[Color.RED].is_pressed() else 0)
            dy = (1 if buttons[Color.GREEN].is_pressed() else 0) - (1 if buttons[Color.BLUE].is_pressed() else 0)
            row, col = self.player_pos
            if dx and not self._blocked(row, col + dx):
                col += dx
            if dy and not self._blocked(row + dy, col):
                row += dy
            self.player_pos = (row, col)

            cell = self.grid[row][col]
            if cell == '.':
                self.grid[row][col] = ' '
                self.pellets_remaining -= 1
            elif cell == 'o':
                self.grid[row][col] = ' '
                self.stored_powerups += 1

        if current_time - self.last_ghost_time >= GHOST_INTERVAL_MS:
            self.last_ghost_time = current_time
            scared = current_time < self.scared_until
            for ghost in self.ghosts:
                self._step_ghost(ghost, scared)

        if self.pellets_remaining <= 0:
            return PacDuoResultScreen(won=True)

        scared = current_time < self.scared_until
        for ghost in self.ghosts:
            if ghost.pos == self.player_pos:
                if scared:
                    ghost.pos = ghost.start
                else:
                    return PacDuoResultScreen(won=False)

        return self


@dataclass
class RulesScreen:
    """Shown once, before the maze starts, so both players know the split
    controls before they're standing at the box. "Play Again" from the result
    screen skips straight back into a fresh maze rather than re-showing this.
    """

    # GetReadyScreen only calls make_next_state() once every button is
    # already released, so there's no stale press to debounce here -- same
    # reasoning as EntryState/ShowSequenceState's un-pressed transitions.
    ready: bool = True

    def draw(self, surface: pygame.Surface) -> None:
        CANVAS_WIDTH, _ = surface.get_size()
        surface.fill((10, 10, 25))
        white = (255, 255, 255)
        draw_text(surface, font(48), "Pac-Duo", (CANVAS_WIDTH // 2, 50), white)

        lines = [
            ("Player 1: Red = Left, Yellow = Right", (255, 60, 60)),
            ("Player 2: Blue = Up, Green = Down", (60, 130, 255)),
            ("One shared character -- move together!", white),
            ("White: spend a power-up to scare the ghosts", (255, 180, 60)),
            ("Eat every dot to win.", white),
            ("Caught by a ghost (not scared) = game over.", white),
        ]
        y = 140
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

        return new_pacman()


@dataclass
class PacDuoResultScreen:
    won: bool
    # Starts unarmed: the press that got us here (a movement button, or none
    # at all if a ghost walked into the player) may still be held on the very
    # first frame we're drawn. Require a release first, same as the other
    # games' result screens.
    ready: bool = False

    def _message(self) -> str:
        return WIN_MESSAGE if self.won else "Gobbled up! Better luck next time."

    def draw(self, surface: pygame.Surface) -> None:
        CANVAS_WIDTH, _ = surface.get_size()
        surface.fill((10, 10, 25))
        white = (255, 255, 255)
        headline = "Maze Cleared!" if self.won else "Game Over"
        draw_text(surface, font(40), headline, (CANVAS_WIDTH // 2, 90), white)
        draw_text(surface, font(26), self._message(), (CANVAS_WIDTH // 2, 150), white)
        draw_text(surface, font(26), "Green: Play Again", (CANVAS_WIDTH // 2, 260), white)
        draw_text(surface, font(26), "Red: Main Menu", (CANVAS_WIDTH // 2, 300), white)

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
            return new_pacman()
        if buttons[Color.RED].is_pressed():
            return None  # back to the menu

        # Any other button: message stays up, keep waiting for Green or Red.
        return self


def new_pacman() -> PacDuoState:
    grid, player_start, ghost_starts = _build_maze()
    pellets_remaining = sum(row.count('.') for row in grid)
    return PacDuoState(
        grid=grid,
        player_pos=player_start,
        ghosts=[Ghost(pos=start, start=start) for start in ghost_starts],
        pellets_remaining=pellets_remaining,
    )


def new_pacman_with_rules() -> RulesScreen:
    return RulesScreen()

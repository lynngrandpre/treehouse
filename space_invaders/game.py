"""Space Invaders: Red/Yellow slide the ship left and right, Green fires a
single bullet at a time straight up. A grid of enemies drifts side to side,
stepping down and firing back whenever it hits a wall; clear them all to win,
or run out of lives (to their return fire) or let them reach the ship to lose.

A single continuous state that mutates and returns itself every frame, in the
"continuous game" style described in the README (see color_game) -- ship,
bullets, and the enemy grid are all shared mutable state ticking forward in
real time, rather than the discrete state-machine style of quiz/mastermind.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace

import pygame

from common import Input, State, draw_text, font
from hardware import Color, big_red_button_pressed, buttons

CANVAS_WIDTH = 800
CANVAS_HEIGHT = 480
HUD_HEIGHT = 40
PLAY_LEFT = 40
PLAY_RIGHT = CANVAS_WIDTH - 40

ENEMY_ROWS = 4
ENEMY_COLS = 8
ENEMY_WIDTH = 50
ENEMY_HEIGHT = 30
ENEMY_GAP_X = 14
ENEMY_GAP_Y = 16
ENEMY_TOP = HUD_HEIGHT + 20
ENEMY_LEFT = (CANVAS_WIDTH - (ENEMY_COLS * ENEMY_WIDTH + (ENEMY_COLS - 1) * ENEMY_GAP_X)) // 2
ENEMY_GRID_WIDTH = ENEMY_COLS * ENEMY_WIDTH + (ENEMY_COLS - 1) * ENEMY_GAP_X
ENEMY_GRID_HEIGHT = ENEMY_ROWS * ENEMY_HEIGHT + (ENEMY_ROWS - 1) * ENEMY_GAP_Y
ENEMY_COLOR = (70, 200, 90)
TOTAL_ENEMIES = ENEMY_ROWS * ENEMY_COLS

ENEMY_SPEED = 60  # pixels per second the whole formation drifts sideways
ENEMY_STEP_DOWN = 24  # pixels the formation drops each time it bounces off a wall

PLAYER_WIDTH = 60
PLAYER_HEIGHT = 16
PLAYER_Y = CANVAS_HEIGHT - 40
PLAYER_SPEED = 320  # pixels per second

# If the formation's leading edge reaches this line, they've reached the
# player -- an instant loss regardless of remaining lives.
DANGER_LINE_Y = PLAYER_Y - 10

BULLET_WIDTH = 4
BULLET_HEIGHT = 14
PLAYER_BULLET_SPEED = 420  # pixels per second, upward
ENEMY_BULLET_SPEED = 220  # pixels per second, downward
ENEMY_SHOT_MIN_INTERVAL_MS = 600
ENEMY_SHOT_MAX_INTERVAL_MS = 1400

STARTING_LIVES = 3
RESPAWN_DELAY_MS = 1000  # pause after being hit before the formation resumes

WIN_MESSAGE = "Every invader cleared -- Earth is safe!"


def _new_enemies() -> list[list[bool]]:
    return [[True] * ENEMY_COLS for _ in range(ENEMY_ROWS)]


def _enemy_rect(row: int, col: int, offset_x: float, offset_y: float) -> pygame.Rect:
    x = ENEMY_LEFT + col * (ENEMY_WIDTH + ENEMY_GAP_X) + offset_x
    y = ENEMY_TOP + row * (ENEMY_HEIGHT + ENEMY_GAP_Y) + offset_y
    return pygame.Rect(round(x), round(y), ENEMY_WIDTH, ENEMY_HEIGHT)


def _next_enemy_shot_delay() -> int:
    return random.randint(ENEMY_SHOT_MIN_INTERVAL_MS, ENEMY_SHOT_MAX_INTERVAL_MS)


def _light_control_leds() -> None:
    """Red/Yellow move the ship, Green fires -- those three stay lit. Blue and
    White have no role here, so they stay off."""
    buttons[Color.RED].set_led(True)
    buttons[Color.YELLOW].set_led(True)
    buttons[Color.GREEN].set_led(True)
    buttons[Color.BLUE].set_led(False)
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


@dataclass
class SpaceInvadersState:
    player_x: float
    enemies: list[list[bool]]
    enemies_remaining: int
    enemy_offset_x: float = 0.0
    enemy_offset_y: float = 0.0
    enemy_dir: int = 1
    next_enemy_shot_at: int = 0
    enemy_bullets: list[list[float]] = None  # each [x, y]
    player_bullet: list[float] | None = None  # [x, y] or None
    lives: int = STARTING_LIVES
    score: int = 0
    # None only on the very first frame, before we've measured a delta -- lets
    # everything sit still for one frame instead of jumping however long it
    # took to get from process start (or the rules screen) to here.
    last_update_time: int | None = None
    # Set to a future timestamp after the player is hit; the formation and
    # enemy fire pause until then, giving a beat before the action resumes.
    respawn_at: int | None = None

    def __post_init__(self) -> None:
        if self.enemy_bullets is None:
            self.enemy_bullets = []

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((10, 10, 25))
        white = (255, 255, 255)
        draw_text(surface, font(20), f"Lives: {self.lives}", (80, 20), white)
        draw_text(surface, font(20), f"Score: {self.score}", (CANVAS_WIDTH - 90, 20), white)

        for row in range(ENEMY_ROWS):
            for col in range(ENEMY_COLS):
                if self.enemies[row][col]:
                    pygame.draw.rect(surface, ENEMY_COLOR, _enemy_rect(row, col, self.enemy_offset_x, self.enemy_offset_y))

        pygame.draw.rect(surface, white, (self.player_x, PLAYER_Y, PLAYER_WIDTH, PLAYER_HEIGHT))

        if self.player_bullet is not None:
            x, y = self.player_bullet
            pygame.draw.rect(surface, (255, 230, 60), (round(x - BULLET_WIDTH / 2), round(y), BULLET_WIDTH, BULLET_HEIGHT))
        for x, y in self.enemy_bullets:
            pygame.draw.rect(surface, (230, 60, 60), (round(x - BULLET_WIDTH / 2), round(y), BULLET_WIDTH, BULLET_HEIGHT))

    def _lose_a_life(self, current_time: int) -> State | None:
        self.lives -= 1
        if self.lives <= 0:
            _clear_control_leds()
            return SpaceInvadersResultScreen(won=False, score=self.score)
        self.player_bullet = None
        self.enemy_bullets = []
        self.respawn_at = current_time + RESPAWN_DELAY_MS
        return self

    def next_state(self, input: Input) -> State | None:
        if big_red_button_pressed():
            _clear_control_leds()
            return None  # back to the menu

        current_time = input.current_time
        if self.last_update_time is None:
            self.last_update_time = current_time
            self.next_enemy_shot_at = current_time + _next_enemy_shot_delay()
            return self
        dt = max(0, current_time - self.last_update_time) / 1000.0
        self.last_update_time = current_time

        _light_control_leds()

        red_held = buttons[Color.RED].is_pressed()
        yellow_held = buttons[Color.YELLOW].is_pressed()
        dx = (1 if yellow_held else 0) - (1 if red_held else 0)
        self.player_x = min(max(self.player_x + dx * PLAYER_SPEED * dt, PLAY_LEFT), PLAY_RIGHT - PLAYER_WIDTH)

        if self.respawn_at is not None:
            if current_time < self.respawn_at:
                return self
            self.respawn_at = None
            self.next_enemy_shot_at = current_time + _next_enemy_shot_delay()

        if buttons[Color.GREEN].is_pressed() and self.player_bullet is None:
            self.player_bullet = [self.player_x + PLAYER_WIDTH / 2, PLAYER_Y]

        if self.player_bullet is not None:
            self.player_bullet[1] -= PLAYER_BULLET_SPEED * dt
            if self.player_bullet[1] + BULLET_HEIGHT < HUD_HEIGHT:
                self.player_bullet = None

        self.enemy_offset_x += self.enemy_dir * ENEMY_SPEED * dt
        formation_left = ENEMY_LEFT + self.enemy_offset_x
        formation_right = formation_left + ENEMY_GRID_WIDTH
        if formation_left <= PLAY_LEFT:
            self.enemy_offset_x = PLAY_LEFT - ENEMY_LEFT
            self.enemy_dir = 1
            self.enemy_offset_y += ENEMY_STEP_DOWN
        elif formation_right >= PLAY_RIGHT:
            self.enemy_offset_x = PLAY_RIGHT - ENEMY_LEFT - ENEMY_GRID_WIDTH
            self.enemy_dir = -1
            self.enemy_offset_y += ENEMY_STEP_DOWN

        if ENEMY_TOP + self.enemy_offset_y + ENEMY_GRID_HEIGHT >= DANGER_LINE_Y:
            _clear_control_leds()
            return SpaceInvadersResultScreen(won=False, score=self.score)

        if self.player_bullet is not None:
            bullet_rect = pygame.Rect(
                round(self.player_bullet[0] - BULLET_WIDTH / 2), round(self.player_bullet[1]),
                BULLET_WIDTH, BULLET_HEIGHT,
            )
            for row in range(ENEMY_ROWS):
                for col in range(ENEMY_COLS):
                    if not self.enemies[row][col]:
                        continue
                    if bullet_rect.colliderect(_enemy_rect(row, col, self.enemy_offset_x, self.enemy_offset_y)):
                        self.enemies[row][col] = False
                        self.enemies_remaining -= 1
                        self.score += 1
                        self.player_bullet = None
                        break
                else:
                    continue
                break

        if self.enemies_remaining <= 0:
            _clear_control_leds()
            return SpaceInvadersResultScreen(won=True, score=self.score)

        if current_time >= self.next_enemy_shot_at:
            shooter = self._pick_shooter()
            if shooter is not None:
                row, col = shooter
                rect = _enemy_rect(row, col, self.enemy_offset_x, self.enemy_offset_y)
                self.enemy_bullets.append([rect.centerx, rect.bottom])
            self.next_enemy_shot_at = current_time + _next_enemy_shot_delay()

        player_rect = pygame.Rect(round(self.player_x), PLAYER_Y, PLAYER_WIDTH, PLAYER_HEIGHT)
        surviving_bullets = []
        hit = False
        for x, y in self.enemy_bullets:
            y += ENEMY_BULLET_SPEED * dt
            if y > CANVAS_HEIGHT:
                continue
            bullet_rect = pygame.Rect(round(x - BULLET_WIDTH / 2), round(y), BULLET_WIDTH, BULLET_HEIGHT)
            if bullet_rect.colliderect(player_rect):
                hit = True
                continue
            surviving_bullets.append([x, y])
        self.enemy_bullets = surviving_bullets

        if hit:
            return self._lose_a_life(current_time)

        return self

    def _pick_shooter(self) -> tuple[int, int] | None:
        """A random alive enemy from the bottom-most alive row of a random
        column that still has one -- so shots always come from the formation's
        front line, never from behind a comrade."""
        columns_with_enemies = [col for col in range(ENEMY_COLS) if any(self.enemies[row][col] for row in range(ENEMY_ROWS))]
        if not columns_with_enemies:
            return None
        col = random.choice(columns_with_enemies)
        row = max(row for row in range(ENEMY_ROWS) if self.enemies[row][col])
        return row, col


@dataclass
class RulesScreen:
    """Shown once, before the action starts, so the player knows the controls
    before they're standing at the box. "Play Again" from the result screen
    skips straight back into a fresh game rather than re-showing this."""

    ready: bool = True

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((10, 10, 25))
        white = (255, 255, 255)
        draw_text(surface, font(48), "Space Invaders", (CANVAS_WIDTH // 2, 50), white)

        lines = [
            ("Red = ship left, Yellow = ship right", white),
            ("Green = fire (one bullet at a time)", white),
            ("Clear every invader to win.", white),
            ("Don't let them reach you, and watch out for their fire.", white),
            (f"Get hit {STARTING_LIVES} times and it's game over.", white),
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

        return new_space_invaders()


@dataclass
class SpaceInvadersResultScreen:
    won: bool
    score: int
    # Starts unarmed: the press (or the hit) that got us here may still have a
    # button held on the very first frame we're drawn. Require a release
    # first, same as the other games' result screens.
    ready: bool = False

    def _message(self) -> str:
        return WIN_MESSAGE if self.won else "Out of lives -- the invaders win this round."

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((10, 10, 25))
        white = (255, 255, 255)
        headline = "You Win!" if self.won else "Game Over"
        draw_text(surface, font(64), headline, (CANVAS_WIDTH // 2, 90), white)
        draw_text(surface, font(32), self._message(), (CANVAS_WIDTH // 2, 160), white)
        draw_text(surface, font(32), f"Score: {self.score} / {TOTAL_ENEMIES}", (CANVAS_WIDTH // 2, 205), white)
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
            return new_space_invaders()
        if buttons[Color.RED].is_pressed():
            return None  # back to the menu

        return self


def new_space_invaders() -> SpaceInvadersState:
    player_x = PLAY_LEFT + (PLAY_RIGHT - PLAY_LEFT - PLAYER_WIDTH) / 2
    return SpaceInvadersState(
        player_x=player_x,
        enemies=_new_enemies(),
        enemies_remaining=TOTAL_ENEMIES,
    )


def new_space_invaders_with_rules() -> RulesScreen:
    return RulesScreen()

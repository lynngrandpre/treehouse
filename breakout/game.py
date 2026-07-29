"""Breakout: a solo paddle-and-ball game. Red/Yellow slide the paddle left and
right; the ball bounces on its own off the walls, the paddle, and the bricks.
Clear every brick to win; let the ball fall past the paddle three times and
the game is over.

A single continuous state that mutates and returns itself every frame, in the
"continuous game" style described in the README (see color_game) -- the
paddle, ball, and brick grid are all shared mutable state ticking forward in
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

# A score box sits to the right of the play area, so the field is centered
# within the canvas *minus* that box rather than the full canvas -- the walls
# flank the field, and the box fills the margin freed up beside it.
SCORE_BOX_WIDTH = 160
PLAY_REGION_WIDTH = CANVAS_WIDTH - SCORE_BOX_WIDTH
SCORE_BOX_LEFT = CANVAS_WIDTH - SCORE_BOX_WIDTH
SCORE_BOX_TOP = HUD_HEIGHT + 10
SCORE_BOX_HEIGHT = 120

WALL_THICKNESS = 14
PLAY_AREA_WIDTH = 560
PLAY_LEFT = (PLAY_REGION_WIDTH - PLAY_AREA_WIDTH) // 2
PLAY_RIGHT = PLAY_LEFT + PLAY_AREA_WIDTH
WALL_COLOR = (70, 70, 100)

BRICK_ROWS = 5
BRICK_COLS = 10
BRICK_GAP = 6
BRICK_WIDTH = (PLAY_AREA_WIDTH - (BRICK_COLS - 1) * BRICK_GAP) // BRICK_COLS
BRICK_HEIGHT = 22
BRICK_TOP = HUD_HEIGHT + 10
BRICK_LEFT = PLAY_LEFT + (PLAY_AREA_WIDTH - (BRICK_COLS * BRICK_WIDTH + (BRICK_COLS - 1) * BRICK_GAP)) // 2
ROW_COLORS = [(230, 60, 60), (230, 140, 50), (230, 210, 50), (70, 200, 90), (70, 150, 230)]
TOTAL_BRICKS = BRICK_ROWS * BRICK_COLS

# A silly face sits behind the brick grid, exactly the size of the grid itself
# -- bricks are drawn on top of it each frame, so knocking one out uncovers
# that patch of the face underneath for good.
GRID_RECT = pygame.Rect(
    BRICK_LEFT, BRICK_TOP,
    BRICK_COLS * BRICK_WIDTH + (BRICK_COLS - 1) * BRICK_GAP,
    BRICK_ROWS * BRICK_HEIGHT + (BRICK_ROWS - 1) * BRICK_GAP,
)

PADDLE_WIDTH = 100
PADDLE_HEIGHT = 14
PADDLE_Y = CANVAS_HEIGHT - 40
PADDLE_SPEED = 480  # pixels per second
TURBO_MULTIPLIER = 2.0  # White held with Red or Yellow speeds the paddle up
TURBO_DURATION_MS = 15_000  # pressing the combo latches turbo on for this long

BALL_RADIUS = 8
INITIAL_BALL_VX = 150
INITIAL_BALL_VY = -260
MAX_BALL_VX = 300  # how much paddle-edge hits can redirect the ball sideways
SERVE_DELAY_MS = 1000  # pause after a miss before the next ball drops in
GAME_OVER_DELAY_MS = 3000  # let the fully revealed face sit a moment before the result screen

STARTING_LIVES = 3

WIN_MESSAGE = "Every brick cleared -- nice shooting!"


def _new_bricks() -> list[list[bool]]:
    return [[True] * BRICK_COLS for _ in range(BRICK_ROWS)]


def _brick_rect(row: int, col: int) -> pygame.Rect:
    x = BRICK_LEFT + col * (BRICK_WIDTH + BRICK_GAP)
    y = BRICK_TOP + row * (BRICK_HEIGHT + BRICK_GAP)
    return pygame.Rect(x, y, BRICK_WIDTH, BRICK_HEIGHT)


def _light_control_leds(turbo: bool) -> None:
    """Only the buttons that do something during play stay lit: Red/Yellow as
    a reminder those move the paddle, White only while turbo is engaged.
    Blue and Green have no role here, so they stay off."""
    buttons[Color.RED].set_led(True)
    buttons[Color.YELLOW].set_led(True)
    buttons[Color.WHITE].set_led(turbo)
    buttons[Color.GREEN].set_led(False)
    buttons[Color.BLUE].set_led(False)


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


def _point(rect: pygame.Rect, fx: float, fy: float) -> tuple[int, int]:
    """A point inside `rect` at the given (0..1, 0..1) fraction of its size."""
    return (round(rect.x + rect.w * fx), round(rect.y + rect.h * fy))


def _draw_grinning_face(surface: pygame.Surface, rect: pygame.Rect) -> None:
    pygame.draw.rect(surface, (255, 221, 89), rect)
    pygame.draw.circle(surface, (255, 255, 255), _point(rect, 0.3, 0.35), round(rect.h * 0.22))
    pygame.draw.circle(surface, (255, 255, 255), _point(rect, 0.7, 0.35), round(rect.h * 0.22))
    pygame.draw.circle(surface, (20, 20, 20), _point(rect, 0.34, 0.4), round(rect.h * 0.08))
    pygame.draw.circle(surface, (20, 20, 20), _point(rect, 0.66, 0.3), round(rect.h * 0.08))
    pygame.draw.line(surface, (20, 20, 20), _point(rect, 0.18, 0.15), _point(rect, 0.4, 0.22), 4)
    pygame.draw.line(surface, (20, 20, 20), _point(rect, 0.82, 0.15), _point(rect, 0.6, 0.24), 4)
    pygame.draw.circle(surface, (250, 140, 150), _point(rect, 0.16, 0.62), round(rect.h * 0.1))
    pygame.draw.circle(surface, (250, 140, 150), _point(rect, 0.84, 0.62), round(rect.h * 0.1))
    mouth = pygame.Rect(0, 0, round(rect.w * 0.5), round(rect.h * 0.3))
    mouth.center = _point(rect, 0.5, 0.74)
    pygame.draw.ellipse(surface, (200, 40, 50), mouth)
    teeth = pygame.Rect(0, 0, round(rect.w * 0.3), round(rect.h * 0.08))
    teeth.midtop = (mouth.centerx, mouth.top + 4)
    pygame.draw.rect(surface, (255, 255, 255), teeth)


def _draw_winking_face(surface: pygame.Surface, rect: pygame.Rect) -> None:
    pygame.draw.rect(surface, (140, 220, 140), rect)
    pygame.draw.circle(surface, (255, 255, 255), _point(rect, 0.3, 0.35), round(rect.h * 0.22))
    pygame.draw.circle(surface, (20, 20, 20), _point(rect, 0.34, 0.35), round(rect.h * 0.08))
    pygame.draw.arc(
        surface, (20, 20, 20),
        pygame.Rect(*_point(rect, 0.55, 0.28), round(rect.w * 0.3), round(rect.h * 0.2)),
        3.4, 6.0, 4,
    )
    pygame.draw.line(surface, (20, 20, 20), _point(rect, 0.16, 0.16), _point(rect, 0.42, 0.2), 4)
    pygame.draw.line(surface, (20, 20, 20), _point(rect, 0.58, 0.24), _point(rect, 0.86, 0.14), 4)
    mouth_points = [_point(rect, 0.28, 0.66), _point(rect, 0.72, 0.6), _point(rect, 0.6, 0.85), _point(rect, 0.32, 0.8)]
    pygame.draw.polygon(surface, (140, 30, 40), mouth_points)
    tongue = pygame.Rect(0, 0, round(rect.w * 0.14), round(rect.h * 0.16))
    tongue.center = _point(rect, 0.62, 0.92)
    pygame.draw.ellipse(surface, (250, 130, 150), tongue)


def _draw_shocked_face(surface: pygame.Surface, rect: pygame.Rect) -> None:
    pygame.draw.rect(surface, (176, 176, 250), rect)
    pygame.draw.circle(surface, (255, 255, 255), _point(rect, 0.32, 0.4), round(rect.h * 0.26))
    pygame.draw.circle(surface, (255, 255, 255), _point(rect, 0.68, 0.4), round(rect.h * 0.26))
    pygame.draw.circle(surface, (20, 20, 20), _point(rect, 0.32, 0.4), round(rect.h * 0.07))
    pygame.draw.circle(surface, (20, 20, 20), _point(rect, 0.68, 0.4), round(rect.h * 0.07))
    pygame.draw.arc(
        surface, (20, 20, 20),
        pygame.Rect(*_point(rect, 0.16, 0.02), round(rect.w * 0.28), round(rect.h * 0.2)),
        0.2, 2.6, 4,
    )
    pygame.draw.arc(
        surface, (20, 20, 20),
        pygame.Rect(*_point(rect, 0.56, 0.02), round(rect.w * 0.28), round(rect.h * 0.2)),
        0.5, 2.9, 4,
    )
    mouth = pygame.Rect(0, 0, round(rect.w * 0.22), round(rect.h * 0.3))
    mouth.center = _point(rect, 0.5, 0.78)
    pygame.draw.ellipse(surface, (40, 20, 20), mouth)
    drop = [_point(rect, 0.9, 0.15), _point(rect, 0.96, 0.28), _point(rect, 0.84, 0.28)]
    pygame.draw.polygon(surface, (120, 180, 250), drop)


REVEAL_FACES = [_draw_grinning_face, _draw_winking_face, _draw_shocked_face]


def _served_ball(paddle_x: float) -> tuple[float, float, float, float]:
    """Ball position/velocity for a fresh serve, resting just above the
    paddle's current position."""
    ball_x = paddle_x + PADDLE_WIDTH / 2
    ball_y = PADDLE_Y - BALL_RADIUS - 1
    return ball_x, ball_y, float(INITIAL_BALL_VX), float(INITIAL_BALL_VY)


@dataclass
class BreakoutState:
    paddle_x: float
    ball_x: float
    ball_y: float
    ball_vx: float
    ball_vy: float
    bricks: list[list[bool]]
    bricks_remaining: int
    lives: int = STARTING_LIVES
    # None only on the very first frame, before we've measured a delta -- lets
    # the ball sit still for one frame instead of jumping however long it took
    # to get from process start (or the rules screen) to here.
    last_update_time: int | None = None
    # Set to a future timestamp after a miss; the ball stays out of play (and
    # hidden) until then, so the next one doesn't drop in the instant the last
    # was lost.
    serve_at: int | None = None
    # Set to a future timestamp whenever the turbo combo is held; turbo stays
    # engaged until that time passes, regardless of whether the buttons are
    # still down, rather than cutting out the instant they're released.
    turbo_until: int | None = None
    # Which silly face (index into REVEAL_FACES) is hiding behind this game's
    # bricks -- picked once when the game starts and fixed for its duration.
    reveal_face: int = 0
    # Set once the win/lose condition is reached: the board freezes as-is
    # (face fully visible) and next_state keeps returning self until
    # game_over_at, so the player gets a moment to enjoy it before the result
    # screen takes over.
    pending_result: BreakoutResultScreen | None = None
    game_over_at: int | None = None

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((10, 10, 25))
        white = (255, 255, 255)
        draw_text(surface, font(20), f"Lives: {self.lives}", (80, 20), white)

        pygame.draw.rect(surface, WALL_COLOR, (PLAY_LEFT - WALL_THICKNESS, HUD_HEIGHT, WALL_THICKNESS, CANVAS_HEIGHT - HUD_HEIGHT))
        pygame.draw.rect(surface, WALL_COLOR, (PLAY_RIGHT, HUD_HEIGHT, WALL_THICKNESS, CANVAS_HEIGHT - HUD_HEIGHT))

        REVEAL_FACES[self.reveal_face](surface, GRID_RECT)
        for row in range(BRICK_ROWS):
            for col in range(BRICK_COLS):
                if self.bricks[row][col]:
                    pygame.draw.rect(surface, ROW_COLORS[row % len(ROW_COLORS)], _brick_rect(row, col))

        pygame.draw.rect(surface, white, (self.paddle_x, PADDLE_Y, PADDLE_WIDTH, PADDLE_HEIGHT))
        if self.serve_at is None and self.pending_result is None:
            pygame.draw.circle(surface, white, (round(self.ball_x), round(self.ball_y)), BALL_RADIUS)

        score_box = pygame.Rect(SCORE_BOX_LEFT, SCORE_BOX_TOP, SCORE_BOX_WIDTH, SCORE_BOX_HEIGHT)
        pygame.draw.rect(surface, WALL_COLOR, score_box, width=2)
        draw_text(surface, font(20), "SCORE", (SCORE_BOX_LEFT + SCORE_BOX_WIDTH // 2, SCORE_BOX_TOP + 28), white)
        bricks_hit = TOTAL_BRICKS - self.bricks_remaining
        draw_text(surface, font(36), str(bricks_hit), (SCORE_BOX_LEFT + SCORE_BOX_WIDTH // 2, SCORE_BOX_TOP + 78), white)

    def _lose_a_life(self, current_time: int) -> State | None:
        self.lives -= 1
        if self.lives <= 0:
            _clear_control_leds()
            self.pending_result = BreakoutResultScreen(won=False, bricks_hit=TOTAL_BRICKS - self.bricks_remaining)
            self.game_over_at = current_time + GAME_OVER_DELAY_MS
            return self
        self.serve_at = current_time + SERVE_DELAY_MS
        return self

    def next_state(self, input: Input) -> State | None:
        if big_red_button_pressed():
            _clear_control_leds()
            return None  # back to the menu

        current_time = input.current_time
        if self.last_update_time is None:
            self.last_update_time = current_time
            return self
        dt = max(0, current_time - self.last_update_time) / 1000.0
        self.last_update_time = current_time

        if self.pending_result is not None:
            if current_time < self.game_over_at:
                return self
            return self.pending_result

        red_held = buttons[Color.RED].is_pressed()
        yellow_held = buttons[Color.YELLOW].is_pressed()
        if buttons[Color.WHITE].is_pressed() and (red_held or yellow_held):
            self.turbo_until = current_time + TURBO_DURATION_MS
        turbo = self.turbo_until is not None and current_time < self.turbo_until
        _light_control_leds(turbo)
        speed = PADDLE_SPEED * TURBO_MULTIPLIER if turbo else PADDLE_SPEED
        dx = (1 if yellow_held else 0) - (1 if red_held else 0)
        self.paddle_x = min(max(self.paddle_x + dx * speed * dt, PLAY_LEFT), PLAY_RIGHT - PADDLE_WIDTH)

        if self.serve_at is not None:
            if current_time < self.serve_at:
                return self
            self.ball_x, self.ball_y, self.ball_vx, self.ball_vy = _served_ball(self.paddle_x)
            self.serve_at = None
            return self

        self.ball_x += self.ball_vx * dt
        self.ball_y += self.ball_vy * dt

        if self.ball_x <= PLAY_LEFT + BALL_RADIUS:
            self.ball_x = PLAY_LEFT + BALL_RADIUS
            self.ball_vx = abs(self.ball_vx)
        elif self.ball_x >= PLAY_RIGHT - BALL_RADIUS:
            self.ball_x = PLAY_RIGHT - BALL_RADIUS
            self.ball_vx = -abs(self.ball_vx)

        if self.ball_y <= HUD_HEIGHT + BALL_RADIUS:
            self.ball_y = HUD_HEIGHT + BALL_RADIUS
            self.ball_vy = abs(self.ball_vy)

        if (
            self.ball_vy > 0
            and self.ball_y + BALL_RADIUS >= PADDLE_Y
            and self.ball_y + BALL_RADIUS <= PADDLE_Y + PADDLE_HEIGHT
            and self.paddle_x - BALL_RADIUS <= self.ball_x <= self.paddle_x + PADDLE_WIDTH + BALL_RADIUS
        ):
            self.ball_y = PADDLE_Y - BALL_RADIUS
            offset = (self.ball_x - (self.paddle_x + PADDLE_WIDTH / 2)) / (PADDLE_WIDTH / 2)
            self.ball_vx = max(-1.0, min(1.0, offset)) * MAX_BALL_VX
            self.ball_vy = -abs(self.ball_vy)

        ball_rect = pygame.Rect(self.ball_x - BALL_RADIUS, self.ball_y - BALL_RADIUS, BALL_RADIUS * 2, BALL_RADIUS * 2)
        for row in range(BRICK_ROWS):
            for col in range(BRICK_COLS):
                if not self.bricks[row][col]:
                    continue
                if ball_rect.colliderect(_brick_rect(row, col)):
                    self.bricks[row][col] = False
                    self.bricks_remaining -= 1
                    self.ball_vy = -self.ball_vy
                    break
            else:
                continue
            break

        if self.bricks_remaining <= 0:
            _clear_control_leds()
            self.pending_result = BreakoutResultScreen(won=True, bricks_hit=TOTAL_BRICKS - self.bricks_remaining)
            self.game_over_at = current_time + GAME_OVER_DELAY_MS
            return self

        if self.ball_y - BALL_RADIUS > CANVAS_HEIGHT:
            return self._lose_a_life(current_time)

        return self


@dataclass
class RulesScreen:
    """Shown once, before the ball starts moving, so the player knows the
    controls before they're standing at the box. "Play Again" from the result
    screen skips straight back into a fresh game rather than re-showing this.
    """

    ready: bool = True

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((10, 10, 25))
        white = (255, 255, 255)
        draw_text(surface, font(48), "Breakout", (CANVAS_WIDTH // 2, 50), white)

        lines = [
            ("Red = paddle left, Yellow = paddle right", white),
            ("Hold White + Red/Yellow for a 15-second turbo boost", (255, 180, 60)),
            ("The ball bounces on its own -- keep it in play.", white),
            ("Clear every brick to win.", white),
            ("Watch for a silly face hiding behind the bricks!", (255, 180, 60)),
            (f"Miss the ball {STARTING_LIVES} times and it's game over.", white),
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

        return new_breakout()


@dataclass
class BreakoutResultScreen:
    won: bool
    bricks_hit: int
    # Starts unarmed: the press (or the falling ball) that got us here may
    # still have a button held on the very first frame we're drawn. Require a
    # release first, same as the other games' result screens.
    ready: bool = False

    def _message(self) -> str:
        return WIN_MESSAGE if self.won else "Out of lives -- the bricks win this round."

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((10, 10, 25))
        white = (255, 255, 255)
        headline = "You Win!" if self.won else "Game Over"
        draw_text(surface, font(64), headline, (CANVAS_WIDTH // 2, 90), white)
        draw_text(surface, font(32), self._message(), (CANVAS_WIDTH // 2, 160), white)
        draw_text(surface, font(32), f"Bricks hit: {self.bricks_hit} / {TOTAL_BRICKS}", (CANVAS_WIDTH // 2, 205), white)
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
            return new_breakout()
        if buttons[Color.RED].is_pressed():
            return None  # back to the menu

        return self


def new_breakout() -> BreakoutState:
    paddle_x = PLAY_LEFT + (PLAY_AREA_WIDTH - PADDLE_WIDTH) / 2
    ball_x, ball_y, ball_vx, ball_vy = _served_ball(paddle_x)
    return BreakoutState(
        paddle_x=paddle_x,
        ball_x=ball_x,
        ball_y=ball_y,
        ball_vx=ball_vx,
        ball_vy=ball_vy,
        bricks=_new_bricks(),
        bricks_remaining=TOTAL_BRICKS,
        reveal_face=random.randrange(len(REVEAL_FACES)),
    )


def new_breakout_with_rules() -> RulesScreen:
    return RulesScreen()

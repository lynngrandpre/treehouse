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

from dataclasses import dataclass, replace

import pygame

from common import Input, State, draw_text, font
from hardware import Color, big_red_button_pressed, buttons

CANVAS_WIDTH = 800
CANVAS_HEIGHT = 480
HUD_HEIGHT = 40

# The playing field is narrower than the canvas and centered, with a solid
# wall along each side -- the paddle and ball are confined between the walls'
# inner faces rather than the canvas edges.
WALL_THICKNESS = 14
PLAY_AREA_WIDTH = 700
PLAY_LEFT = (CANVAS_WIDTH - PLAY_AREA_WIDTH) // 2
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

PADDLE_WIDTH = 100
PADDLE_HEIGHT = 14
PADDLE_Y = CANVAS_HEIGHT - 40
PADDLE_SPEED = 480  # pixels per second
TURBO_MULTIPLIER = 2.0  # White held with Red or Yellow speeds the paddle up

BALL_RADIUS = 8
INITIAL_BALL_VX = 150
INITIAL_BALL_VY = -260
MAX_BALL_VX = 300  # how much paddle-edge hits can redirect the ball sideways
SERVE_DELAY_MS = 1000  # pause after a miss before the next ball drops in

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

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((10, 10, 25))
        white = (255, 255, 255)
        draw_text(surface, font(20), f"Lives: {self.lives}   Bricks: {self.bricks_remaining}", (110, 20), white)

        pygame.draw.rect(surface, WALL_COLOR, (PLAY_LEFT - WALL_THICKNESS, HUD_HEIGHT, WALL_THICKNESS, CANVAS_HEIGHT - HUD_HEIGHT))
        pygame.draw.rect(surface, WALL_COLOR, (PLAY_RIGHT, HUD_HEIGHT, WALL_THICKNESS, CANVAS_HEIGHT - HUD_HEIGHT))

        for row in range(BRICK_ROWS):
            for col in range(BRICK_COLS):
                if self.bricks[row][col]:
                    pygame.draw.rect(surface, ROW_COLORS[row % len(ROW_COLORS)], _brick_rect(row, col))

        pygame.draw.rect(surface, white, (self.paddle_x, PADDLE_Y, PADDLE_WIDTH, PADDLE_HEIGHT))
        if self.serve_at is None:
            pygame.draw.circle(surface, white, (round(self.ball_x), round(self.ball_y)), BALL_RADIUS)

    def _lose_a_life(self, current_time: int) -> State | None:
        self.lives -= 1
        if self.lives <= 0:
            _clear_control_leds()
            return BreakoutResultScreen(won=False)
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

        red_held = buttons[Color.RED].is_pressed()
        yellow_held = buttons[Color.YELLOW].is_pressed()
        turbo = buttons[Color.WHITE].is_pressed() and (red_held or yellow_held)
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
            return BreakoutResultScreen(won=True)

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
            ("Hold White + Red/Yellow for a turbo speed boost", (255, 180, 60)),
            ("The ball bounces on its own -- keep it in play.", white),
            ("Clear every brick to win.", white),
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
        draw_text(surface, font(40), headline, (CANVAS_WIDTH // 2, 90), white)
        draw_text(surface, font(26), self._message(), (CANVAS_WIDTH // 2, 150), white)
        draw_text(surface, font(26), "Green: Play Again", (CANVAS_WIDTH // 2, 260), white)
        draw_text(surface, font(26), "Red: Main Menu", (CANVAS_WIDTH // 2, 300), white)

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
        bricks_remaining=BRICK_ROWS * BRICK_COLS,
    )


def new_breakout_with_rules() -> RulesScreen:
    return RulesScreen()

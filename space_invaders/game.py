"""Space Invaders: Red/Blue slide the ship left and right, Green fires a
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
# The formation gets to swing almost edge to edge -- a much tighter margin
# than the player ship's PLAY_LEFT/PLAY_RIGHT -- so it travels noticeably
# farther each way before bouncing, instead of turning around well short of
# the screen's sides.
ENEMY_BOUND_LEFT = 10
ENEMY_BOUND_RIGHT = CANVAS_WIDTH - 10
# One cute color per row rather than a single flat color, same idea as Breakout's brick rows.
ENEMY_ROW_COLORS = [(230, 120, 60), (230, 200, 60), (120, 210, 90), (90, 170, 230)]
TOTAL_ENEMIES = ENEMY_ROWS * ENEMY_COLS

ENEMY_SPEED = 60  # pixels per second the whole formation drifts sideways
ENEMY_STEP_DOWN = 24  # pixels the formation drops each time it bounces off a wall
SPEED_UP_EVERY_N_ENEMIES = 10  # every this many aliens shot down, the formation gets a bit faster
SPEED_UP_FACTOR = 1.15

PLAYER_WIDTH = 60
PLAYER_HEIGHT = 16
PLAYER_Y = CANVAS_HEIGHT - 40
PLAYER_SPEED = 320  # pixels per second

BULLET_WIDTH = 4
BULLET_HEIGHT = 14
PLAYER_BULLET_SPEED = 420  # pixels per second, upward
ENEMY_BULLET_SPEED = 220  # pixels per second, downward
ENEMY_SHOT_MIN_INTERVAL_MS = 600
ENEMY_SHOT_MAX_INTERVAL_MS = 1400

STARTING_LIVES = 3
RESPAWN_DELAY_MS = 1000  # pause after being hit before the formation resumes

# A bonus saucer that occasionally zips across the top of the screen -- shoot
# it for extra points. Independent of the main formation entirely.
UFO_WIDTH = 46
UFO_HEIGHT = 20
UFO_Y = HUD_HEIGHT + 4
UFO_SPEED = 140  # pixels per second
UFO_BONUS_POINTS = 5
UFO_MIN_INTERVAL_MS = 8_000
UFO_MAX_INTERVAL_MS = 16_000
UFO_COLOR = (230, 80, 200)

WIN_MESSAGE = "Every invader cleared -- Earth is safe!"


def _new_enemies() -> list[list[bool]]:
    return [[True] * ENEMY_COLS for _ in range(ENEMY_ROWS)]


def _enemy_rect(row: int, col: int, offset_x: float, offset_y: float) -> pygame.Rect:
    x = ENEMY_LEFT + col * (ENEMY_WIDTH + ENEMY_GAP_X) + offset_x
    y = ENEMY_TOP + row * (ENEMY_HEIGHT + ENEMY_GAP_Y) + offset_y
    return pygame.Rect(round(x), round(y), ENEMY_WIDTH, ENEMY_HEIGHT)


def _alive_columns(enemies: list[list[bool]]) -> list[int]:
    return [col for col in range(ENEMY_COLS) if any(enemies[row][col] for row in range(ENEMY_ROWS))]


def _next_enemy_shot_delay() -> int:
    return random.randint(ENEMY_SHOT_MIN_INTERVAL_MS, ENEMY_SHOT_MAX_INTERVAL_MS)


def _next_ufo_delay() -> int:
    return random.randint(UFO_MIN_INTERVAL_MS, UFO_MAX_INTERVAL_MS)


PLAYER_HULL_COLOR = (90, 200, 255)
PLAYER_ACCENT_COLOR = (255, 210, 60)


def _draw_ship(surface: pygame.Surface, rect: pygame.Rect) -> None:
    """A little fighter jet instead of a plain block: swept wings, a canopy,
    and a cannon barrel poking out the front."""
    pygame.draw.polygon(surface, PLAYER_ACCENT_COLOR, [
        (rect.left, rect.bottom), (rect.left - 10, rect.bottom), (rect.left + rect.w * 0.2, rect.top + 2),
    ])
    pygame.draw.polygon(surface, PLAYER_ACCENT_COLOR, [
        (rect.right, rect.bottom), (rect.right + 10, rect.bottom), (rect.right - rect.w * 0.2, rect.top + 2),
    ])

    pygame.draw.polygon(surface, PLAYER_HULL_COLOR, [
        (rect.left + rect.w * 0.1, rect.bottom), (rect.right - rect.w * 0.1, rect.bottom),
        (rect.right - rect.w * 0.3, rect.top), (rect.left + rect.w * 0.3, rect.top),
    ])

    barrel = pygame.Rect(0, 0, max(4, round(rect.w * 0.12)), round(rect.h * 1.4))
    barrel.midbottom = (rect.centerx, rect.top + 2)
    pygame.draw.rect(surface, PLAYER_ACCENT_COLOR, barrel, border_radius=2)

    pygame.draw.circle(surface, (255, 255, 255), rect.center, max(3, rect.h // 4))
    pygame.draw.circle(surface, (40, 120, 200), rect.center, max(3, rect.h // 4), 1)


def _draw_ufo(surface: pygame.Surface, rect: pygame.Rect) -> None:
    """A little flying saucer: a wide disc body with a glowing dome and a
    row of lights along the bottom rim."""
    pygame.draw.ellipse(surface, UFO_COLOR, rect)
    dome = pygame.Rect(0, 0, round(rect.w * 0.5), round(rect.h * 0.9))
    dome.center = (rect.centerx, rect.top + 2)
    pygame.draw.ellipse(surface, (210, 245, 255), dome)
    for dx in (-rect.w * 0.3, 0, rect.w * 0.3):
        pygame.draw.circle(surface, (255, 255, 255), (round(rect.centerx + dx), rect.bottom - 3), 2)


def _draw_alien(surface: pygame.Surface, rect: pygame.Rect, row: int) -> None:
    """A little bug-eyed alien instead of a plain block: rounded body, two
    big eyes, a pair of antennae, and stubby feet. Row determines its color,
    purely for variety -- same shape for every alien."""
    color = ENEMY_ROW_COLORS[row % len(ENEMY_ROW_COLORS)]

    antenna_y = rect.top - 6
    for dx in (-rect.w // 4, rect.w // 4):
        x = rect.centerx + dx
        pygame.draw.line(surface, color, (x, rect.top + 2), (x, antenna_y), 2)
        pygame.draw.circle(surface, color, (x, antenna_y), 3)

    body = rect.inflate(0, -6)
    body.top = rect.top + 4
    pygame.draw.ellipse(surface, color, body)

    for dx in (-rect.w // 5, rect.w // 5):
        foot_x = rect.centerx + dx
        pygame.draw.line(surface, color, (foot_x, body.bottom - 2), (foot_x, rect.bottom), 3)

    eye_radius = max(3, rect.h // 6)
    pupil_radius = max(1, eye_radius // 2)
    for dx in (-rect.w // 5, rect.w // 5):
        eye_center = (rect.centerx + dx, body.centery - 2)
        pygame.draw.circle(surface, (255, 255, 255), eye_center, eye_radius)
        pygame.draw.circle(surface, (20, 20, 20), eye_center, pupil_radius)


def _light_control_leds() -> None:
    """Red/Blue move the ship, Green fires -- those three stay lit. Yellow and
    White have no role here, so they stay off."""
    buttons[Color.RED].set_led(True)
    buttons[Color.GREEN].set_led(True)
    buttons[Color.BLUE].set_led(True)
    buttons[Color.YELLOW].set_led(False)
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
    # Multiplies the formation's drift speed; bumped up by SPEED_UP_FACTOR
    # every SPEED_UP_EVERY_N_ENEMIES shot down, and stays in effect for the
    # rest of the game.
    speed_multiplier: float = 1.0
    # None only on the very first frame, before we've measured a delta -- lets
    # everything sit still for one frame instead of jumping however long it
    # took to get from process start (or the rules screen) to here.
    last_update_time: int | None = None
    # Set to a future timestamp after the player is hit; the formation and
    # enemy fire pause until then, giving a beat before the action resumes.
    respawn_at: int | None = None
    # None whenever the bonus UFO isn't on screen; its x position while it is.
    ufo_x: float | None = None
    ufo_dir: int = 1
    next_ufo_at: int = 0

    def __post_init__(self) -> None:
        if self.enemy_bullets is None:
            self.enemy_bullets = []

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((10, 10, 25))
        white = (255, 255, 255)
        draw_text(surface, font(20), f"Lives: {self.lives}", (80, 20), white)
        draw_text(surface, font(28), f"Score: {self.score}", (CANVAS_WIDTH - 110, 22), white)

        for row in range(ENEMY_ROWS):
            for col in range(ENEMY_COLS):
                if self.enemies[row][col]:
                    _draw_alien(surface, _enemy_rect(row, col, self.enemy_offset_x, self.enemy_offset_y), row)

        if self.ufo_x is not None:
            _draw_ufo(surface, pygame.Rect(round(self.ufo_x), UFO_Y, UFO_WIDTH, UFO_HEIGHT))

        _draw_ship(surface, pygame.Rect(round(self.player_x), PLAYER_Y, PLAYER_WIDTH, PLAYER_HEIGHT))

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
            self.next_ufo_at = current_time + _next_ufo_delay()
            return self
        dt = max(0, current_time - self.last_update_time) / 1000.0
        self.last_update_time = current_time

        _light_control_leds()

        red_held = buttons[Color.RED].is_pressed()
        blue_held = buttons[Color.BLUE].is_pressed()
        dx = (1 if blue_held else 0) - (1 if red_held else 0)
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

        # Only the live columns bound the formation -- as the outer ones are
        # shot out, the remaining block has farther to drift before its edge
        # reaches a wall and the whole thing steps down.
        alive_cols = _alive_columns(self.enemies)
        if alive_cols:
            left_col, right_col = min(alive_cols), max(alive_cols)
            live_left = ENEMY_LEFT + left_col * (ENEMY_WIDTH + ENEMY_GAP_X)
            live_right = ENEMY_LEFT + right_col * (ENEMY_WIDTH + ENEMY_GAP_X) + ENEMY_WIDTH

            self.enemy_offset_x += self.enemy_dir * ENEMY_SPEED * self.speed_multiplier * dt
            formation_left = live_left + self.enemy_offset_x
            formation_right = live_right + self.enemy_offset_x
            if formation_left <= ENEMY_BOUND_LEFT:
                self.enemy_offset_x = ENEMY_BOUND_LEFT - live_left
                self.enemy_dir = 1
                self.enemy_offset_y += ENEMY_STEP_DOWN
            elif formation_right >= ENEMY_BOUND_RIGHT:
                self.enemy_offset_x = ENEMY_BOUND_RIGHT - live_right
                self.enemy_dir = -1
                self.enemy_offset_y += ENEMY_STEP_DOWN

        if self.ufo_x is None:
            if current_time >= self.next_ufo_at:
                self.ufo_dir = random.choice((-1, 1))
                self.ufo_x = PLAY_LEFT - UFO_WIDTH if self.ufo_dir == 1 else PLAY_RIGHT
        else:
            self.ufo_x += self.ufo_dir * UFO_SPEED * dt
            if self.ufo_x > PLAY_RIGHT or self.ufo_x + UFO_WIDTH < PLAY_LEFT:
                self.ufo_x = None
                self.next_ufo_at = current_time + _next_ufo_delay()

        if self.player_bullet is not None:
            bullet_rect = pygame.Rect(
                round(self.player_bullet[0] - BULLET_WIDTH / 2), round(self.player_bullet[1]),
                BULLET_WIDTH, BULLET_HEIGHT,
            )
            ufo_rect = pygame.Rect(round(self.ufo_x), UFO_Y, UFO_WIDTH, UFO_HEIGHT) if self.ufo_x is not None else None
            if ufo_rect is not None and bullet_rect.colliderect(ufo_rect):
                self.score += UFO_BONUS_POINTS
                self.player_bullet = None
                self.ufo_x = None
                self.next_ufo_at = current_time + _next_ufo_delay()
            else:
                for row in range(ENEMY_ROWS):
                    for col in range(ENEMY_COLS):
                        if not self.enemies[row][col]:
                            continue
                        if bullet_rect.colliderect(_enemy_rect(row, col, self.enemy_offset_x, self.enemy_offset_y)):
                            self.enemies[row][col] = False
                            self.enemies_remaining -= 1
                            self.score += 1
                            self.player_bullet = None
                            if (TOTAL_ENEMIES - self.enemies_remaining) % SPEED_UP_EVERY_N_ENEMIES == 0:
                                self.speed_multiplier *= SPEED_UP_FACTOR
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

        # An alien has to actually reach and touch the ship to cost a life --
        # not just have the formation's row reach the ship's height.
        hit = any(
            self.enemies[row][col]
            and _enemy_rect(row, col, self.enemy_offset_x, self.enemy_offset_y).colliderect(player_rect)
            for row in range(ENEMY_ROWS) for col in range(ENEMY_COLS)
        )

        surviving_bullets = []
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
        columns_with_enemies = _alive_columns(self.enemies)
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
            ("Red = ship left, Blue = ship right", white),
            ("Green = fire (one bullet at a time)", white),
            ("Clear every invader to win.", white),
            ("They speed up a bit every 10 you shoot down.", white),
            ("Watch for the bonus saucer -- shoot it for extra points!", (255, 180, 60)),
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

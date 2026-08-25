"""Tower Defense Duo: Player 1 aims the tower with Red (up a lane) and Green
(down a lane); Player 2 answers the aimed lane's math problem with Blue,
Yellow, or White. The correct answer fires and destroys the enemy; a wrong
guess does nothing. Let an enemy reach the tower and it costs a life -- and
sends that same enemy back around with the same problem, so it has to be
answered eventually. Lose all your lives and the game's over. Every 25
points levels the game up, alternating between faster enemies and bigger
sums, with a short breather in between so you know it's getting harder.

A single continuous state that mutates and returns itself every frame, in the
"continuous game" style described in the README (see color_game) -- the
lanes and their enemies are shared mutable state ticking forward in real
time, the same dt-based approach used by Breakout and Space Invaders.
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
ANSWER_BAR_HEIGHT = 80

LANES = 3
PLAY_TOP = HUD_HEIGHT
PLAY_BOTTOM = CANVAS_HEIGHT - ANSWER_BAR_HEIGHT
LANE_HEIGHT = (PLAY_BOTTOM - PLAY_TOP) // LANES

TOWER_X = 70
ENEMY_START_X = CANVAS_WIDTH - 50
ENEMY_WIDTH = 70
ENEMY_HEIGHT = 46
LANE_COLOR = (55, 55, 85)
AIMED_LANE_COLOR = (85, 85, 130)

ENEMY_BODY_COLOR = (70, 195, 110)
ENEMY_OUTLINE_COLOR = (20, 60, 30)
ENEMY_ANTENNA_COLOR = (255, 210, 70)

# The line an enemy must be destroyed before crossing -- reaching it costs a life.
KILL_LINE_COLOR = (255, 90, 60)
KILL_LINE_WIDTH = 6

# A brief red wash over the playfield when an enemy gets through, so a life loss
# is impossible to miss even if you weren't looking right at that lane.
BREACH_FLASH_MS = 350
BREACH_FLASH_COLOR = (255, 40, 40, 70)

STARTING_LIVES = 3

# Buttons that answer the aimed lane's problem, in the same order as each
# Enemy's `choices` list -- choices[0] is the Blue answer, and so on.
ANSWER_BUTTONS = [Color.BLUE, Color.YELLOW, Color.WHITE]

# Every LEVEL_UP_EVERY points, the game levels up and a LevelUpScreen breather
# announces it. Levels alternate what gets harder: odd levels speed the
# enemies up, even levels raise the sum problems can add up to -- first speed,
# per the ask, and sums top out at the last entry in SUM_CAPS.
LEVEL_UP_EVERY = 25
SUM_CAPS = [10, 15, 20]
LEVEL_BREAK_MS = 3000

BASE_ENEMY_SPEED = 40  # pixels per second
ENEMY_SPEEDUP_STEP = 16
MAX_ENEMY_SPEED = 136
BASE_SPAWN_INTERVAL_MS = 3200
SPAWN_SPEEDUP_STEP_MS = 280
MIN_SPAWN_INTERVAL_MS = 1400


def _level(score: int) -> int:
    return score // LEVEL_UP_EVERY


def _speed_tier(level: int) -> int:
    return (level + 1) // 2


def _sum_tier(level: int) -> int:
    return min(level // 2, len(SUM_CAPS) - 1)


def _enemy_speed(score: int) -> float:
    return min(MAX_ENEMY_SPEED, BASE_ENEMY_SPEED + _speed_tier(_level(score)) * ENEMY_SPEEDUP_STEP)


def _spawn_interval_ms(score: int) -> int:
    return max(MIN_SPAWN_INTERVAL_MS, BASE_SPAWN_INTERVAL_MS - _speed_tier(_level(score)) * SPAWN_SPEEDUP_STEP_MS)


def _sum_cap(score: int) -> int:
    return SUM_CAPS[_sum_tier(_level(score))]


def _level_up_message(level: int) -> str:
    """What actually changed going into this level -- speed and sum caps both
    top out eventually, so a milestone can be reached without either moving;
    fall back to something generic rather than claim a change that didn't happen."""
    prior_score = (level - 1) * LEVEL_UP_EVERY
    this_score = level * LEVEL_UP_EVERY
    if _enemy_speed(this_score) != _enemy_speed(prior_score):
        return "The aliens are moving faster now!"
    if _sum_cap(this_score) != _sum_cap(prior_score):
        return f"Problems can now add up to {_sum_cap(this_score)}!"
    return "Keep up the great work!"


def _generate_problem(score: int) -> tuple[str, int]:
    """Addition only. The sum cap rises as the level climbs (see SUM_CAPS)."""
    cap = _sum_cap(score)
    a = random.randint(1, cap - 1)
    b = random.randint(1, cap - a)
    return f"{a} + {b}", a + b


def _generate_choices(correct: int) -> list[int]:
    wrong: set[int] = set()
    while len(wrong) < 2:
        candidate = correct + random.choice([-3, -2, -1, 1, 2, 3])
        if candidate != correct and candidate >= 0:
            wrong.add(candidate)
    choices = [correct, *wrong]
    random.shuffle(choices)
    return choices


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


def _lane_center_y(lane: int) -> int:
    return PLAY_TOP + lane * LANE_HEIGHT + LANE_HEIGHT // 2


def _readable_text_color(background: tuple[int, int, int]) -> tuple[int, int, int]:
    """Black or white, whichever reads better against the given background --
    keeps answer-bar and enemy text legible regardless of button/body color."""
    r, g, b = background
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return (15, 15, 15) if luminance > 140 else (255, 255, 255)


def _draw_enemy(surface: pygame.Surface, enemy: Enemy, lane: int) -> None:
    """A little antenna'd alien standing in for the plain rectangle enemies used
    to be -- its belly carries the math problem, drawn large and high-contrast."""
    center = (round(enemy.x), _lane_center_y(lane))
    cx, cy = center

    body_rect = pygame.Rect(0, 0, ENEMY_WIDTH, ENEMY_HEIGHT)
    body_rect.center = center
    pygame.draw.ellipse(surface, ENEMY_BODY_COLOR, body_rect)
    pygame.draw.ellipse(surface, ENEMY_OUTLINE_COLOR, body_rect, 3)

    for dx in (-14, 14):
        base = (cx + dx, body_rect.top + 6)
        tip = (cx + dx * 1.6, body_rect.top - 12)
        pygame.draw.line(surface, ENEMY_OUTLINE_COLOR, base, tip, 3)
        pygame.draw.circle(surface, ENEMY_ANTENNA_COLOR, tip, 4)

    for dx in (-16, 16):
        eye_center = (cx + dx, cy - 14)
        pygame.draw.circle(surface, (255, 255, 255), eye_center, 7)
        pygame.draw.circle(surface, (10, 10, 10), eye_center, 3)

    draw_text(surface, font(30), enemy.text, (cx, cy + 11), _readable_text_color(ENEMY_BODY_COLOR))


@dataclass
class Enemy:
    x: float
    text: str
    correct_answer: int
    choices: list[int]  # answers for Blue, Yellow, White, in that order
    # Only one guess per lap -- once used, further presses do nothing until this
    # enemy reaches the tower and comes back around for another try.
    guess_used: bool = False


@dataclass
class TowerDefenseState:
    lanes: list[Enemy | None] = field(default_factory=lambda: [None] * LANES)
    current_lane: int = LANES // 2
    lives: int = STARTING_LIVES
    score: int = 0
    # None only until the first real frame, so timers are scheduled off an
    # actual timestamp rather than whatever time it was at import.
    next_spawn_at: int | None = None
    last_update_time: int | None = None
    breach_flash_until: int = 0
    announced_level: int = 0
    red_was_held: bool = False
    green_was_held: bool = False
    blue_was_held: bool = False
    yellow_was_held: bool = False
    white_was_held: bool = False

    def _try_answer(self, choice_index: int) -> None:
        enemy = self.lanes[self.current_lane]
        if enemy is None or enemy.guess_used:
            return
        enemy.guess_used = True
        if enemy.choices[choice_index] == enemy.correct_answer:
            self.lanes[self.current_lane] = None
            self.score += 1

    def _light_control_leds(self) -> None:
        """Red/Green always aim the tower. Blue/Yellow/White answer the aimed
        lane's problem, but only while that enemy still has a guess left --
        once it's used them, those three go dark until the aim moves or the
        enemy comes back around."""
        buttons[Color.RED].set_led(True)
        buttons[Color.GREEN].set_led(True)
        enemy = self.lanes[self.current_lane]
        can_guess = enemy is not None and not enemy.guess_used
        for color in ANSWER_BUTTONS:
            buttons[color].set_led(can_guess)

    def _spawn_enemy(self) -> None:
        empty_lanes = [i for i, enemy in enumerate(self.lanes) if enemy is None]
        if not empty_lanes:
            return
        lane = random.choice(empty_lanes)
        text, answer = _generate_problem(self.score)
        self.lanes[lane] = Enemy(x=ENEMY_START_X, text=text, correct_answer=answer, choices=_generate_choices(answer))

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((10, 10, 30))
        white = (255, 255, 255)
        draw_text(surface, font(24), f"Lives: {self.lives}", (90, 22), white)
        draw_text(surface, font(24), f"Score: {self.score}", (CANVAS_WIDTH - 90, 22), white)

        for lane in range(LANES):
            top = PLAY_TOP + lane * LANE_HEIGHT
            rect = pygame.Rect(TOWER_X, top, CANVAS_WIDTH - TOWER_X - 20, LANE_HEIGHT)
            pygame.draw.rect(surface, AIMED_LANE_COLOR if lane == self.current_lane else LANE_COLOR, rect)
            pygame.draw.line(surface, (20, 20, 40), (TOWER_X, top), (CANVAS_WIDTH - 20, top), 2)

        # The kill line: an enemy destroyed before crossing this is a win, past it costs a life.
        pygame.draw.line(surface, KILL_LINE_COLOR, (TOWER_X, PLAY_TOP), (TOWER_X, PLAY_BOTTOM), KILL_LINE_WIDTH)

        turret_y = _lane_center_y(self.current_lane)
        pygame.draw.polygon(
            surface, (230, 230, 230),
            [(TOWER_X - 30, turret_y - 18), (TOWER_X - 30, turret_y + 18), (TOWER_X, turret_y)],
        )

        for lane, enemy in enumerate(self.lanes):
            if enemy is not None:
                _draw_enemy(surface, enemy, lane)

        # last_update_time tracks the clock frame-by-frame in next_state, so by the
        # time draw() runs it's effectively "now" -- good enough to time this flash.
        if (self.last_update_time or 0) < self.breach_flash_until:
            flash = pygame.Surface((CANVAS_WIDTH, PLAY_BOTTOM - PLAY_TOP), pygame.SRCALPHA)
            flash.fill(BREACH_FLASH_COLOR)
            surface.blit(flash, (0, PLAY_TOP))

        self._draw_answer_bar(surface)

    def _draw_answer_bar(self, surface: pygame.Surface) -> None:
        bar_top = CANVAS_HEIGHT - ANSWER_BAR_HEIGHT
        pygame.draw.rect(surface, (20, 20, 40), (0, bar_top, CANVAS_WIDTH, ANSWER_BAR_HEIGHT))

        enemy = self.lanes[self.current_lane]
        locked = enemy is not None and enemy.guess_used
        slot_width = CANVAS_WIDTH // 3
        for i, color in enumerate(ANSWER_BUTTONS):
            text = str(enemy.choices[i]) if enemy is not None else "-"
            slot_rect = pygame.Rect(slot_width * i + 15, bar_top + 12, slot_width - 30, ANSWER_BAR_HEIGHT - 24)
            button_color = buttons[color].rgb.to_tuple()
            if locked:
                button_color = tuple(c // 3 for c in button_color)
            pygame.draw.rect(surface, button_color, slot_rect, border_radius=10)
            draw_text(surface, font(40), text, slot_rect.center, _readable_text_color(button_color))

    def next_state(self, input: Input) -> State | None:
        if big_red_button_pressed():
            _clear_control_leds()
            return None  # back to the menu

        current_time = input.current_time
        if self.last_update_time is None:
            self.last_update_time = current_time
            self.next_spawn_at = current_time + _spawn_interval_ms(self.score)
            return self  # burn a frame so dt below is never measured from import time
        dt = max(0, current_time - self.last_update_time) / 1000.0
        self.last_update_time = current_time

        self._light_control_leds()

        red_held = buttons[Color.RED].is_pressed()
        green_held = buttons[Color.GREEN].is_pressed()
        if red_held and not self.red_was_held:
            self.current_lane = max(0, self.current_lane - 1)
        if green_held and not self.green_was_held:
            self.current_lane = min(LANES - 1, self.current_lane + 1)
        self.red_was_held = red_held
        self.green_was_held = green_held

        for i, color in enumerate(ANSWER_BUTTONS):
            attr = f"{color.name.lower()}_was_held"
            held = buttons[color].is_pressed()
            if held and not getattr(self, attr):
                self._try_answer(i)
            setattr(self, attr, held)

        new_level = _level(self.score)
        if new_level > self.announced_level:
            self.announced_level = new_level
            _clear_control_leds()
            return LevelUpScreen(resume_state=self, level=new_level, message=_level_up_message(new_level))

        speed = _enemy_speed(self.score)
        for lane, enemy in enumerate(self.lanes):
            if enemy is None:
                continue
            enemy.x -= speed * dt
            if enemy.x <= TOWER_X:
                self.lives -= 1
                self.breach_flash_until = current_time + BREACH_FLASH_MS
                if self.lives <= 0:
                    self.lanes[lane] = None
                    _clear_control_leds()
                    return TowerDefenseResultScreen(score=self.score)
                # Send it back around with the same problem instead of a fresh
                # one, so a problem that got through has to be answered eventually.
                # A new lap means a new guess.
                self.lanes[lane] = replace(enemy, x=ENEMY_START_X, guess_used=False)

        if current_time >= self.next_spawn_at:
            self._spawn_enemy()
            self.next_spawn_at = current_time + _spawn_interval_ms(self.score)

        return self


@dataclass
class LevelUpScreen:
    """A short breather shown whenever a score milestone raises the difficulty.
    Holds for LEVEL_BREAK_MS -- the wrapped TowerDefenseState just sits there,
    since this screen never calls its next_state -- then hands control straight
    back to it."""

    resume_state: TowerDefenseState
    level: int
    message: str
    shown_until: int | None = None

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((10, 10, 30))
        white = (255, 255, 255)
        draw_text(surface, font(50), f"Level {self.level + 1}!", (CANVAS_WIDTH // 2, 160), white)
        draw_text(surface, font(28), "Take a quick breather...", (CANVAS_WIDTH // 2, 230), white)
        draw_text(surface, font(28), self.message, (CANVAS_WIDTH // 2, 280), (255, 210, 90))

    def next_state(self, input: Input) -> State | None:
        if big_red_button_pressed():
            _clear_control_leds()
            return None  # back to the menu

        current_time = input.current_time
        if self.shown_until is None:
            self.shown_until = current_time + LEVEL_BREAK_MS
            return self

        if current_time < self.shown_until:
            return self

        # Resume with a clean clock so the paused time isn't counted as dt.
        self.resume_state.last_update_time = None
        return self.resume_state


@dataclass
class RulesScreen:
    """Shown once, before the enemies start marching, so both players know
    their half of the controls. "Play Again" from the result screen skips
    straight back into a fresh game rather than re-showing this."""

    ready: bool = True

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((10, 10, 30))
        white = (255, 255, 255)
        draw_text(surface, font(44), "Tower Defense Duo", (CANVAS_WIDTH // 2, 46), white)

        lines = [
            ("Player 1: Red = aim up a lane, Green = aim down", white),
            ("Player 2: Blue/Yellow/White = the aimed problem's answer", white),
            ("Answer correctly to fire and destroy that enemy.", white),
            ("Let one reach the tower and you lose a life.", white),
            (f"Lose all {STARTING_LIVES} lives and it's game over.", white),
            (f"Every {LEVEL_UP_EVERY} points it levels up and gets harder.", white),
        ]
        y = 130
        for text, color in lines:
            draw_text(surface, font(26), text, (CANVAS_WIDTH // 2, y), color)
            y += 42

        draw_text(surface, font(28), "Press any button to continue", (CANVAS_WIDTH // 2, y + 20), white)

    def next_state(self, input: Input) -> State | None:
        if big_red_button_pressed():
            return None  # back to the menu

        any_pressed = any(button.is_pressed() for button in input.buttons)
        if not any_pressed:
            return self if self.ready else replace(self, ready=True)
        if not self.ready:
            return self

        return new_tower_defense()


@dataclass
class TowerDefenseResultScreen:
    score: int
    # Starts unarmed: the press that got us here may still have a button held
    # on the very first frame we're drawn. Require a release first, same as
    # the other games' result screens.
    ready: bool = False

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((10, 10, 30))
        white = (255, 255, 255)
        draw_text(surface, font(60), "Game Over", (CANVAS_WIDTH // 2, 90), white)
        draw_text(surface, font(30), "The tower held out as long as it could!", (CANVAS_WIDTH // 2, 160), white)
        draw_text(surface, font(32), f"Problems solved: {self.score}", (CANVAS_WIDTH // 2, 205), white)
        draw_text(surface, font(28), "Green: Play Again", (CANVAS_WIDTH // 2, 300), white)
        draw_text(surface, font(28), "Red: Main Menu", (CANVAS_WIDTH // 2, 340), white)

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
            return new_tower_defense()
        if buttons[Color.RED].is_pressed():
            return None  # back to the menu

        return self


def new_tower_defense() -> TowerDefenseState:
    return TowerDefenseState()


def new_tower_defense_with_rules() -> RulesScreen:
    return RulesScreen()

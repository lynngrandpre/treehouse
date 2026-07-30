"""Tower Defense Duo: Player 1 aims the tower with Red (up a lane) and Green
(down a lane); Player 2 answers the aimed lane's math problem with Blue,
Yellow, or White. The correct answer fires and destroys the enemy; a wrong
guess does nothing. Let an enemy reach the tower and it costs a life -- lose
them all and the game's over. Enemies get faster and their problems get
harder the more you solve, so see how long the two of you can hold out.

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
ENEMY_WIDTH = 60
ENEMY_HEIGHT = 36
LANE_COLOR = (55, 55, 85)
AIMED_LANE_COLOR = (85, 85, 130)

STARTING_LIVES = 3

# Buttons that answer the aimed lane's problem, in the same order as each
# Enemy's `choices` list -- choices[0] is the Blue answer, and so on.
ANSWER_BUTTONS = [Color.BLUE, Color.YELLOW, Color.WHITE]

# Every SPEEDUP_EVERY correct answers, enemies move a little faster and spawn
# a little more often -- the same "ramp up over time" idea as Tetris's
# FALL_SPEEDUP_PER_LINES.
SPEEDUP_EVERY = 5
BASE_ENEMY_SPEED = 40  # pixels per second
ENEMY_SPEEDUP_STEP = 6
MAX_ENEMY_SPEED = 130
BASE_SPAWN_INTERVAL_MS = 3200
SPAWN_SPEEDUP_STEP_MS = 120
MIN_SPAWN_INTERVAL_MS = 1400


def _difficulty_tier(score: int) -> int:
    return score // SPEEDUP_EVERY


def _enemy_speed(score: int) -> float:
    return min(MAX_ENEMY_SPEED, BASE_ENEMY_SPEED + _difficulty_tier(score) * ENEMY_SPEEDUP_STEP)


def _spawn_interval_ms(score: int) -> int:
    return max(MIN_SPAWN_INTERVAL_MS, BASE_SPAWN_INTERVAL_MS - _difficulty_tier(score) * SPAWN_SPEEDUP_STEP_MS)


def _generate_problem(score: int) -> tuple[str, int]:
    """Bigger numbers and harder operations the more problems have been solved."""
    tier = _difficulty_tier(score)
    if tier == 0:
        a, b = random.randint(1, 10), random.randint(1, 10)
        return f"{a} + {b}", a + b
    elif tier == 1:
        a, b = random.randint(1, 15), random.randint(1, 15)
        if random.choice([True, False]):
            return f"{a} + {b}", a + b
        a, b = max(a, b), min(a, b)
        return f"{a} - {b}", a - b
    else:
        op = random.choice(["+", "-", "x"])
        if op == "+":
            a, b = random.randint(5, 25), random.randint(5, 25)
            return f"{a} + {b}", a + b
        elif op == "-":
            a, b = random.randint(1, 30), random.randint(1, 30)
            a, b = max(a, b), min(a, b)
            return f"{a} - {b}", a - b
        else:
            a, b = random.randint(2, 12), random.randint(2, 12)
            return f"{a} x {b}", a * b


def _generate_choices(correct: int) -> list[int]:
    wrong: set[int] = set()
    while len(wrong) < 2:
        candidate = correct + random.choice([-3, -2, -1, 1, 2, 3])
        if candidate != correct and candidate >= 0:
            wrong.add(candidate)
    choices = [correct, *wrong]
    random.shuffle(choices)
    return choices


def _light_control_leds() -> None:
    """Every button has a job here -- Red/Green aim the tower, Blue/Yellow/White
    answer the aimed lane's problem -- so all five stay lit."""
    for button in buttons.values():
        button.set_led(True)


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


@dataclass
class Enemy:
    x: float
    text: str
    correct_answer: int
    choices: list[int]  # answers for Blue, Yellow, White, in that order


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
    red_was_held: bool = False
    green_was_held: bool = False
    blue_was_held: bool = False
    yellow_was_held: bool = False
    white_was_held: bool = False

    def _try_answer(self, choice_index: int) -> None:
        enemy = self.lanes[self.current_lane]
        if enemy is not None and enemy.choices[choice_index] == enemy.correct_answer:
            self.lanes[self.current_lane] = None
            self.score += 1

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

        turret_y = _lane_center_y(self.current_lane)
        pygame.draw.polygon(
            surface, (230, 230, 230),
            [(TOWER_X - 30, turret_y - 18), (TOWER_X - 30, turret_y + 18), (TOWER_X, turret_y)],
        )

        for lane, enemy in enumerate(self.lanes):
            if enemy is None:
                continue
            rect = pygame.Rect(0, 0, ENEMY_WIDTH, ENEMY_HEIGHT)
            rect.center = (round(enemy.x), _lane_center_y(lane))
            pygame.draw.rect(surface, (230, 90, 90), rect, border_radius=8)
            draw_text(surface, font(22), enemy.text, rect.center, (20, 20, 20))

        self._draw_answer_bar(surface)

    def _draw_answer_bar(self, surface: pygame.Surface) -> None:
        bar_top = CANVAS_HEIGHT - ANSWER_BAR_HEIGHT
        pygame.draw.rect(surface, (20, 20, 40), (0, bar_top, CANVAS_WIDTH, ANSWER_BAR_HEIGHT))

        enemy = self.lanes[self.current_lane]
        slot_width = CANVAS_WIDTH // 3
        for i, color in enumerate(ANSWER_BUTTONS):
            text = str(enemy.choices[i]) if enemy is not None else "-"
            slot_rect = pygame.Rect(slot_width * i + 15, bar_top + 12, slot_width - 30, ANSWER_BAR_HEIGHT - 24)
            pygame.draw.rect(surface, buttons[color].rgb.to_tuple(), slot_rect, border_radius=10)
            draw_text(surface, font(28), text, slot_rect.center, (20, 20, 20))

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

        _light_control_leds()

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

        speed = _enemy_speed(self.score)
        for lane, enemy in enumerate(self.lanes):
            if enemy is None:
                continue
            enemy.x -= speed * dt
            if enemy.x <= TOWER_X:
                self.lanes[lane] = None
                self.lives -= 1
                if self.lives <= 0:
                    _clear_control_leds()
                    return TowerDefenseResultScreen(score=self.score)

        if current_time >= self.next_spawn_at:
            self._spawn_enemy()
            self.next_spawn_at = current_time + _spawn_interval_ms(self.score)

        return self


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

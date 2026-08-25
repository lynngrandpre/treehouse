"""Math Blaster: an addition-facts arcade game for a 9-year-old. The gameplay
verb IS the math -- there's no separate "quiz" wrapper around a rocket theme,
answering correctly blasts the alien. Every session mixes a handful of
struggling facts (picked by progress.py's adaptive priority score) in among
facts the player already knows, so weak spots get repeated exposure without
the whole session feeling hard.

Session shape: a short easy warm-up, a longer main round that leans on the
session's 3-4 target facts, then a quick confidence-building boss round
pulled only from facts already known. A wrong (or slow-but-correct) answer
reinserts that same fact a few questions later in the same session -- struggle
now, see it again soon, not just "better luck next session."

State machine (discrete, like quiz/game.py): IntroScreen -> QuestionState ->
FeedbackState -> QuestionState -> ... -> ResultScreen -> None. Session holds
all the cross-question bookkeeping (queues, score, streak, the Progress
object) and is mutated in place as the player answers -- passed around by
reference rather than rebuilt with dataclasses.replace(), since it's really
one continuous run through a session, not a series of independent screens.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone

import pygame

from common import AnswerPicker, Input, State, draw_text, font
from hardware import big_red_button_pressed, buttons_in_order

from .facts import ALL_FACTS, FACTS_BY_KEY, Fact, generate_choices, strategy_hint
from .progress import SLOW_MS, Progress

WARM_UP_COUNT = 3
MAIN_COUNT = 14
BOSS_COUNT = 4
TARGET_FACT_COUNT = 4
TARGET_PICK_PROBABILITY = 0.45

FEEDBACK_CORRECT_MS = 900
FEEDBACK_WRONG_MS = 2200

BURST_DURATION_MS = 500
BURST_PARTICLES = 14
BURST_COLORS = [(255, 210, 60), (255, 150, 40), (120, 220, 120)]

BG_COLOR = (18, 18, 34)
TEXT_COLOR = (240, 240, 245)
HUD_COLOR = (180, 190, 220)
ROCKET_COLOR = (220, 220, 230)
ROCKET_FLAME_COLOR = (255, 160, 40)
ALIEN_COLOR = (120, 220, 120)
ALIEN_EYE_COLOR = (20, 40, 20)

BOX_GAP = 8

_STATUS_RANK = {"new": 0, "red": 1, "yellow": 2, "green": 3}


# --- Session: the adaptive scheduler for one ~5-minute play session ---------


@dataclass
class Session:
    progress: Progress
    target_facts: list[Fact]
    queue: list[Fact]
    boss_queue: list[Fact]
    rng: random.Random
    starting_status: dict[str, str]
    asked_count: int = 0
    boss_started: bool = False
    correct: int = 0
    wrong: int = 0
    streak: int = 0
    best_streak: int = 0
    touched: set[str] = field(default_factory=set)

    @property
    def phase(self) -> str:
        if self.boss_started:
            return "boss"
        return "warmup" if self.asked_count < WARM_UP_COUNT else "main"

    def pop_next(self) -> tuple[Fact, str] | None:
        if not self.boss_started:
            if self.queue:
                fact = self.queue.pop(0)
                label = "Warm-Up!" if self.asked_count < WARM_UP_COUNT else ""
                self.asked_count += 1
                return fact, label
            self.boss_started = True
        if self.boss_queue:
            return self.boss_queue.pop(0), "BOSS ROUND!"
        return None

    def requeue_soon(self, fact: Fact) -> None:
        """Brings a struggled-with fact back within the next few questions,
        rather than leaving it to a future session."""
        if self.boss_started:
            return
        insert_at = min(len(self.queue), self.rng.randint(3, 6))
        self.queue.insert(insert_at, fact)

    def record_answer(self, fact: Fact, correct: bool, response_ms: int, chosen: int) -> None:
        now = datetime.now(timezone.utc)
        self.progress.stats_for(fact).record(correct, response_ms, chosen, now)
        self.touched.add(fact.key)
        self.starting_status.setdefault(fact.key, "new")

        if correct:
            self.correct += 1
            self.streak += 1
            self.best_streak = max(self.best_streak, self.streak)
            needs_more_practice = response_ms > SLOW_MS
        else:
            self.wrong += 1
            self.streak = 0
            needs_more_practice = True

        if needs_more_practice:
            self.requeue_soon(fact)


def new_session(progress: Progress, now: datetime, rng: random.Random) -> Session:
    target = progress.target_facts(TARGET_FACT_COUNT, now, rng)
    known = progress.known_facts(now, rng)

    warmup = [rng.choice(known) for _ in range(WARM_UP_COUNT)]

    weighted_pool = [(f, progress.stats_for(f).priority(now) + 1.0) for f in ALL_FACTS]
    pool_facts = [f for f, _ in weighted_pool]
    pool_weights = [w for _, w in weighted_pool]

    main: list[Fact] = []
    for _ in range(MAIN_COUNT):
        if target and rng.random() < TARGET_PICK_PROBABILITY:
            main.append(rng.choice(target))
        else:
            main.append(rng.choices(pool_facts, weights=pool_weights, k=1)[0])

    queue = warmup + main
    for i in range(1, len(queue)):
        if queue[i] == queue[i - 1]:
            for j in range(i + 1, len(queue)):
                if queue[j] != queue[i]:
                    queue[i], queue[j] = queue[j], queue[i]
                    break

    boss_pool = known if len(known) >= BOSS_COUNT else ALL_FACTS
    boss_queue = rng.sample(boss_pool, min(BOSS_COUNT, len(boss_pool)))
    while len(boss_queue) < BOSS_COUNT:
        boss_queue.append(rng.choice(boss_pool))

    touched_candidates = set(queue) | set(boss_queue) | set(target)
    starting_status = {f.key: progress.status_for(f, now) for f in touched_candidates}

    return Session(
        progress=progress,
        target_facts=target,
        queue=queue,
        boss_queue=boss_queue,
        rng=rng,
        starting_status=starting_status,
    )


# --- LEDs ---------------------------------------------------------------


def _light_choice_leds(count: int) -> None:
    for i, button in enumerate(buttons_in_order):
        button.set_led(i < count)


def _light_single_led(index: int) -> None:
    for i, button in enumerate(buttons_in_order):
        button.set_led(i == index)


def _light_all_leds() -> None:
    for button in buttons_in_order:
        button.set_led(True)


def _clear_leds() -> None:
    for button in buttons_in_order:
        button.set_led(False)


# --- Drawing helpers ------------------------------------------------------


def _text_color_for(rgb: tuple[int, int, int]) -> tuple[int, int, int]:
    r, g, b = rgb
    luminance = 0.299 * r + 0.587 * g + 0.114 * b
    return (20, 20, 20) if luminance > 140 else (255, 255, 255)


def _draw_hud(surface: pygame.Surface, session: Session) -> None:
    canvas_width, _ = surface.get_size()
    draw_text(surface, font(20), f"Score {session.correct}", (75, 20), HUD_COLOR)
    draw_text(surface, font(20), f"Streak {session.streak}", (canvas_width - 85, 20), HUD_COLOR)


def _draw_scene(surface: pygame.Surface, canvas_width: int, canvas_height: int) -> None:
    mid_y = canvas_height // 2 - 40
    rocket_x = 90
    pygame.draw.polygon(
        surface, ROCKET_COLOR, [(rocket_x, mid_y - 26), (rocket_x - 22, mid_y + 20), (rocket_x + 22, mid_y + 20)]
    )
    pygame.draw.polygon(
        surface, ROCKET_FLAME_COLOR, [(rocket_x - 10, mid_y + 20), (rocket_x + 10, mid_y + 20), (rocket_x, mid_y + 36)]
    )

    alien_x = canvas_width - 90
    pygame.draw.circle(surface, ALIEN_COLOR, (alien_x, mid_y), 26)
    pygame.draw.circle(surface, ALIEN_EYE_COLOR, (alien_x - 9, mid_y - 6), 4)
    pygame.draw.circle(surface, ALIEN_EYE_COLOR, (alien_x + 9, mid_y - 6), 4)


def _box_area_top(canvas_height: int) -> int:
    return int(canvas_height * 0.66)


def _draw_answer_boxes(
    surface: pygame.Surface,
    choices: list[int],
    correct_index: int | None = None,
    wrong_index: int | None = None,
) -> None:
    canvas_width, canvas_height = surface.get_size()
    box_area_top = _box_area_top(canvas_height)
    box_area_height = canvas_height - box_area_top - 16
    box_width = (canvas_width - BOX_GAP * 6) // 5

    for i, value in enumerate(choices):
        x = BOX_GAP + i * (box_width + BOX_GAP)
        rect = pygame.Rect(x, box_area_top, box_width, box_area_height)
        color = buttons_in_order[i].rgb.to_tuple()
        pygame.draw.rect(surface, color, rect, border_radius=14)

        if correct_index is not None and i == correct_index:
            pygame.draw.rect(surface, (255, 255, 255), rect, width=6, border_radius=14)
        elif wrong_index is not None and i == wrong_index:
            pygame.draw.rect(surface, (40, 40, 40), rect, width=5, border_radius=14)

        draw_text(surface, font(52), str(value), rect.center, _text_color_for(color))


def _draw_burst(surface: pygame.Surface, center: tuple[int, int], elapsed: int) -> None:
    if elapsed >= BURST_DURATION_MS:
        return
    progress = elapsed / BURST_DURATION_MS
    for i in range(BURST_PARTICLES):
        angle = (2 * math.pi * i) / BURST_PARTICLES
        distance = progress * (40 + (i * 17) % 30)
        x = center[0] + math.cos(angle) * distance
        y = center[1] + math.sin(angle) * distance
        size = max(1, int(6 * (1 - progress)))
        color = BURST_COLORS[i % len(BURST_COLORS)]
        pygame.draw.rect(surface, color, pygame.Rect(int(x) - size // 2, int(y) - size // 2, size, size))


# --- States ---------------------------------------------------------------


def _build_question(session: Session, fact: Fact, current_time: int, label: str) -> QuestionState:
    choices = generate_choices(fact, session.rng)
    correct_index = choices.index(fact.answer)
    swap = session.rng.random() < 0.5
    return QuestionState(
        session=session,
        fact=fact,
        choices=choices,
        correct_index=correct_index,
        swap=swap,
        label=label,
        asked_at=current_time,
    )


@dataclass
class IntroScreen:
    session: Session

    def draw(self, surface: pygame.Surface) -> None:
        canvas_width, canvas_height = surface.get_size()
        surface.fill(BG_COLOR)
        draw_text(surface, font(52), "Math Blaster", (canvas_width // 2, 90), TEXT_COLOR)
        draw_text(surface, font(24), "Blast the right answer before the alien attacks!", (canvas_width // 2, 150), TEXT_COLOR)
        draw_text(surface, font(20), "Press the button that matches your answer's color.", (canvas_width // 2, 185), HUD_COLOR)
        draw_text(surface, font(28), "Press any button to launch!", (canvas_width // 2, canvas_height - 60), (255, 220, 60))

    def next_state(self, input: Input) -> State | None:
        if big_red_button_pressed():
            _clear_leds()
            return None

        _light_all_leds()

        if not any(button.is_pressed() for button in input.buttons):
            return self

        nxt = self.session.pop_next()
        if nxt is None:
            return ResultScreen(self.session)
        fact, label = nxt
        return _build_question(self.session, fact, input.current_time, label)


@dataclass
class QuestionState:
    session: Session
    fact: Fact
    choices: list[int]
    correct_index: int
    swap: bool
    label: str
    asked_at: int

    def _picker(self) -> AnswerPicker[int]:
        return AnswerPicker([str(c) for c in self.choices], self.choices)

    def draw(self, surface: pygame.Surface) -> None:
        canvas_width, canvas_height = surface.get_size()
        surface.fill(BG_COLOR)

        if self.label:
            draw_text(surface, font(28), self.label, (canvas_width // 2, 24), (255, 220, 60))

        _draw_hud(surface, self.session)
        _draw_scene(surface, canvas_width, canvas_height)
        draw_text(surface, font(64), self.fact.prompt(self.swap), (canvas_width // 2, canvas_height // 2 - 40), TEXT_COLOR)
        draw_text(surface, font(40), "= ?", (canvas_width // 2, canvas_height // 2 + 20), TEXT_COLOR)

        _draw_answer_boxes(surface, self.choices)

    def next_state(self, input: Input) -> State | None:
        if big_red_button_pressed():
            _clear_leds()
            return ResultScreen(self.session)

        _light_choice_leds(len(self.choices))

        selection = self._picker().selection(input)
        if selection is None:
            return self

        response_ms = max(0, input.current_time - self.asked_at)
        correct = selection == self.fact.answer
        self.session.record_answer(self.fact, correct, response_ms, selection)

        return FeedbackState(
            session=self.session,
            fact=self.fact,
            choices=self.choices,
            correct_index=self.correct_index,
            swap=self.swap,
            chosen=selection,
            correct=correct,
            shown_at=input.current_time,
        )


@dataclass
class FeedbackState:
    session: Session
    fact: Fact
    choices: list[int]
    correct_index: int
    swap: bool
    chosen: int
    correct: bool
    shown_at: int

    def draw(self, surface: pygame.Surface) -> None:
        canvas_width, canvas_height = surface.get_size()
        surface.fill(BG_COLOR)
        _draw_hud(surface, self.session)
        _draw_scene(surface, canvas_width, canvas_height)

        accent = (90, 220, 120) if self.correct else (230, 90, 70)
        headline = "Nice!" if self.correct else "So close!"
        draw_text(surface, font(28), headline, (canvas_width // 2, 24), accent)

        draw_text(surface, font(64), self.fact.prompt(self.swap), (canvas_width // 2, canvas_height // 2 - 40), TEXT_COLOR)
        draw_text(surface, font(40), f"= {self.fact.answer}", (canvas_width // 2, canvas_height // 2 + 20), accent)

        if not self.correct:
            hint_y = _box_area_top(canvas_height) - 20
            draw_text(surface, font(20), strategy_hint(self.fact), (canvas_width // 2, hint_y), HUD_COLOR)

        wrong_index = None if self.correct else self.choices.index(self.chosen)
        _draw_answer_boxes(surface, self.choices, correct_index=self.correct_index, wrong_index=wrong_index)

        if self.correct:
            elapsed = pygame.time.get_ticks() - self.shown_at
            _draw_burst(surface, (canvas_width - 90, canvas_height // 2 - 40), elapsed)

    def next_state(self, input: Input) -> State | None:
        if big_red_button_pressed():
            _clear_leds()
            return ResultScreen(self.session)

        _light_single_led(self.correct_index)

        delay = FEEDBACK_CORRECT_MS if self.correct else FEEDBACK_WRONG_MS
        if input.current_time - self.shown_at < delay:
            return self

        nxt = self.session.pop_next()
        if nxt is None:
            _clear_leds()
            return ResultScreen(self.session)
        fact, label = nxt
        return _build_question(self.session, fact, input.current_time, label)


@dataclass
class ResultScreen:
    session: Session
    saved: bool = False
    new_personal_best: bool = False

    def _fact_transitions(self) -> tuple[list[Fact], list[Fact]]:
        now = datetime.now(timezone.utc)
        mastered, improving = [], []
        for key in self.session.touched:
            fact = FACTS_BY_KEY[key]
            before = self.session.starting_status.get(key, "new")
            after = self.session.progress.status_for(fact, now)
            if after == "green" and before != "green":
                mastered.append(fact)
            elif after != "green" and _STATUS_RANK[after] > _STATUS_RANK[before]:
                improving.append(fact)
        return mastered, improving

    def draw(self, surface: pygame.Surface) -> None:
        canvas_width, canvas_height = surface.get_size()
        surface.fill(BG_COLOR)
        session = self.session
        total = session.correct + session.wrong

        draw_text(surface, font(48), "Mission Complete!", (canvas_width // 2, 50), (255, 220, 60))
        draw_text(surface, font(28), f"Score: {session.correct} / {total}", (canvas_width // 2, 105), TEXT_COLOR)
        draw_text(surface, font(24), f"Best Streak: {session.best_streak}", (canvas_width // 2, 140), TEXT_COLOR)
        if self.new_personal_best:
            draw_text(surface, font(22), "New Personal Best!", (canvas_width // 2, 170), (255, 220, 60))

        mastered, improving = self._fact_transitions()
        y = 215
        if mastered:
            names = ", ".join(f.prompt(False) for f in mastered[:6])
            draw_text(surface, font(20), f"Mastered: {names}", (canvas_width // 2, y), (100, 230, 120))
            y += 30
        if improving:
            names = ", ".join(f.prompt(False) for f in improving[:6])
            draw_text(surface, font(20), f"Getting Better: {names}", (canvas_width // 2, y), (120, 190, 255))
            y += 30

        draw_text(surface, font(20), "Press any button for the menu", (canvas_width // 2, canvas_height - 30), HUD_COLOR)

    def next_state(self, input: Input) -> State | None:
        if not self.saved:
            self.new_personal_best = self.session.best_streak > self.session.progress.meta.best_streak
            self.session.progress.meta.best_streak = max(self.session.progress.meta.best_streak, self.session.best_streak)
            self.session.progress.meta.sessions_played += 1
            self.session.progress.save()
            self.saved = True

        if big_red_button_pressed() or any(button.is_pressed() for button in input.buttons):
            return None
        return self


def new_math_blaster() -> IntroScreen:
    progress = Progress.load()
    session = new_session(progress, datetime.now(timezone.utc), random.Random())
    return IntroScreen(session=session)

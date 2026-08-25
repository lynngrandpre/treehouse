"""Exercises the fact/distractor generation (facts.py), the adaptive
spaced-repetition scheduler (progress.py), and the arcade state machine
(game.py) directly -- the same layered approach test_tetris.py takes with
its board logic. Never calls draw().

Progress.save()/load() write real JSON next to progress.py; every test here
gets that redirected to a throwaway tmp_path so the test suite never touches
(or depends on) the real save file.
"""

import random
from datetime import datetime, timezone
from pathlib import Path

import pytest
import sim_gpio
from common import Input
from hardware import BIG_RED_BUTTON_PIN, buttons_in_order

import math_blaster.progress as progress_module
from math_blaster.facts import ALL_FACTS, MAX_ADDEND, MIN_ADDEND, Fact, generate_choices, strategy_hint
from math_blaster.game import (
    BOSS_COUNT,
    FEEDBACK_CORRECT_MS,
    FEEDBACK_WRONG_MS,
    MAIN_COUNT,
    WARM_UP_COUNT,
    FeedbackState,
    IntroScreen,
    QuestionState,
    ResultScreen,
    Session,
    _build_question,
    new_session,
)
from math_blaster.progress import FactStats, Meta, Progress


@pytest.fixture(autouse=True)
def isolate_progress_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(progress_module, "DATA_DIR", tmp_path)
    monkeypatch.setattr(progress_module, "PROGRESS_PATH", tmp_path / "progress.json")


def press(*indices: int, current_time: int) -> Input:
    for i, button in enumerate(buttons_in_order):
        sim_gpio.set_input_state(button.switch_pin, i in indices)
    return Input(buttons_in_order, current_time=current_time)


def release(current_time: int = 0) -> Input:
    return press(current_time=current_time)


def _fresh_progress() -> Progress:
    return Progress(facts={f.key: FactStats() for f in ALL_FACTS}, meta=Meta())


def _session(seed: int = 1) -> Session:
    return new_session(_fresh_progress(), datetime.now(timezone.utc), random.Random(seed))


# --- facts.py ---------------------------------------------------------------


def test_all_facts_cover_the_grid_once_each():
    expected = (MAX_ADDEND - MIN_ADDEND + 1) * (MAX_ADDEND - MIN_ADDEND + 2) // 2
    assert len(ALL_FACTS) == expected
    assert all(f.a <= f.b for f in ALL_FACTS)


def test_generate_choices_are_five_unique_positive_values_including_the_answer():
    rng = random.Random(0)
    for fact in ALL_FACTS:
        choices = generate_choices(fact, rng)
        assert len(choices) == 5
        assert len(set(choices)) == 5
        assert all(c > 0 for c in choices)
        assert fact.answer in choices


def test_generate_choices_reshuffles_the_answer_position_across_occurrences():
    rng = random.Random(0)
    fact = Fact(7, 8)
    positions = {generate_choices(fact, rng).index(fact.answer) for _ in range(20)}
    assert len(positions) > 1  # the correct answer doesn't camp on one button


def test_strategy_hint_calls_out_a_double():
    assert "double" in strategy_hint(Fact(6, 6)).lower()


def test_strategy_hint_uses_make_ten_when_it_applies():
    fact = Fact(4, 9)
    assert "make 10" in strategy_hint(fact).lower()


# --- progress.py --------------------------------------------------------


def test_new_fact_stats_status_is_new():
    now = datetime.now(timezone.utc)
    assert FactStats().status(now) == "new"


def test_four_fast_correct_answers_in_a_row_reach_mastery():
    now = datetime.now(timezone.utc)
    stats = FactStats()
    for _ in range(4):
        stats.record(correct=True, response_ms=1000, chosen_answer=9, now=now)
    assert stats.mastered
    assert stats.status(now) == "green"


def test_a_wrong_answer_resets_the_fast_streak():
    now = datetime.now(timezone.utc)
    stats = FactStats()
    stats.record(correct=True, response_ms=1000, chosen_answer=9, now=now)
    stats.record(correct=False, response_ms=1000, chosen_answer=8, now=now)
    assert stats.fast_streak == 0
    assert stats.status(now) == "red"


def test_mastered_fact_priority_drops_to_zero():
    now = datetime.now(timezone.utc)
    stats = FactStats()
    for _ in range(4):
        stats.record(correct=True, response_ms=1000, chosen_answer=9, now=now)
    assert stats.priority(now) == 0.0


def test_repeated_wrong_choice_surfaces_as_a_misconception():
    now = datetime.now(timezone.utc)
    stats = FactStats()
    stats.record(correct=False, response_ms=2000, chosen_answer=8, now=now)
    assert stats.likely_misconception() is None  # one slip isn't a pattern yet
    stats.record(correct=False, response_ms=2000, chosen_answer=8, now=now)
    assert stats.likely_misconception() == 8


def test_progress_save_and_load_roundtrip():
    progress = _fresh_progress()
    fact = ALL_FACTS[0]
    now = datetime.now(timezone.utc)
    progress.stats_for(fact).record(correct=True, response_ms=1200, chosen_answer=fact.answer, now=now)
    progress.meta.sessions_played = 3
    progress.save()

    reloaded = Progress.load()
    assert reloaded.stats_for(fact).correct == 1
    assert reloaded.meta.sessions_played == 3


# --- game.py: the session state machine ----------------------------------


def test_new_session_builds_the_expected_queue_lengths():
    session = _session()
    assert len(session.queue) == WARM_UP_COUNT + MAIN_COUNT
    assert len(session.boss_queue) == BOSS_COUNT


def test_intro_screen_launches_the_first_question_on_any_press():
    session = _session()
    result = IntroScreen(session=session).next_state(press(0, current_time=0))
    assert isinstance(result, QuestionState)


def test_intro_screen_waits_for_a_press():
    session = _session()
    intro = IntroScreen(session=session)
    assert intro.next_state(release(current_time=0)) is intro


def test_correct_answer_moves_to_feedback_and_scores():
    session = _session()
    fact, label = session.pop_next()
    question = _build_question(session, fact, current_time=0, label=label)

    result = question.next_state(press(question.correct_index, current_time=500))
    assert isinstance(result, FeedbackState)
    assert result.correct is True
    assert session.correct == 1
    assert session.streak == 1


def test_feedback_holds_for_a_moment_then_advances():
    session = _session()
    fact, label = session.pop_next()
    question = _build_question(session, fact, current_time=0, label=label)
    feedback = question.next_state(press(question.correct_index, current_time=0))

    assert feedback.next_state(release(current_time=FEEDBACK_CORRECT_MS - 1)) is feedback

    advanced = feedback.next_state(release(current_time=FEEDBACK_CORRECT_MS + 1))
    assert isinstance(advanced, (QuestionState, ResultScreen))


def test_wrong_answer_requeues_the_fact_within_a_few_questions():
    session = _session()
    fact, label = session.pop_next()
    question = _build_question(session, fact, current_time=0, label=label)
    wrong_index = next(i for i in range(5) if i != question.correct_index)

    feedback = question.next_state(press(wrong_index, current_time=0))
    assert isinstance(feedback, FeedbackState)
    assert feedback.correct is False
    assert session.wrong == 1
    assert fact in session.queue[:7]  # requeue_soon inserts 3-6 slots ahead


def test_wrong_answer_holds_longer_than_a_correct_one():
    assert FEEDBACK_WRONG_MS > FEEDBACK_CORRECT_MS


def test_big_red_jumps_straight_to_the_result_screen():
    session = _session()
    fact, label = session.pop_next()
    question = _build_question(session, fact, current_time=0, label=label)

    sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, True)
    try:
        result = question.next_state(release(current_time=0))
    finally:
        sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, False)
    assert isinstance(result, ResultScreen)


def test_result_screen_saves_progress_once_then_exits_on_any_press():
    session = _session()
    session.correct = 5
    session.best_streak = 5
    screen = ResultScreen(session=session)

    screen.next_state(release(current_time=0))
    assert session.progress.meta.sessions_played == 1
    assert session.progress.meta.best_streak == 5

    screen.next_state(release(current_time=1))
    assert session.progress.meta.sessions_played == 1  # not saved twice

    assert screen.next_state(press(0, current_time=2)) is None

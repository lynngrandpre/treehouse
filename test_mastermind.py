"""Walks the Mastermind state machine directly through the simulator's GPIO
backend, the same way test_menu.py exercises the menu. Never calls draw().
"""

from typing import Any

import sim_gpio
from common import Input
from hardware import BIG_RED_BUTTON_PIN, Color, buttons_in_order
from mastermind.game import (
    Feedback,
    GuessEntryState,
    MastermindResultScreen,
    score_guess,
)


def press(*indices: int) -> Input:
    """An Input with exactly the buttons at the given left-to-right indices held."""
    for i, button in enumerate(buttons_in_order):
        sim_gpio.set_input_state(button.switch_pin, i in indices)
    return Input(buttons_in_order, current_time=0)


def release() -> Input:
    return press()  # no indices held


def tap(state: Any, index: int) -> Any:
    """One full press-then-release of a single button, as a real tap would
    land across two frames."""
    pressed = state.next_state(press(index))
    released = pressed.next_state(release())
    return released


# Button order is Red, Green, Blue, Yellow, White -- matches COLORS_IN_ORDER.
RED, GREEN, BLUE, YELLOW, WHITE = 0, 1, 2, 3, 4


def enter_guess(state: Any, *indices: int) -> Any:
    for i in indices:
        state = tap(state, i)
    return state


def test_score_guess_all_correct():
    secret = [Color.RED, Color.GREEN, Color.BLUE, Color.YELLOW]
    assert score_guess(secret, secret) == Feedback(black=4, white=0)


def test_score_guess_all_wrong_position():
    secret = [Color.RED, Color.GREEN, Color.BLUE, Color.YELLOW]
    guess = [Color.YELLOW, Color.BLUE, Color.GREEN, Color.RED]
    assert score_guess(secret, guess) == Feedback(black=0, white=4)


def test_score_guess_handles_duplicate_colors():
    secret = [Color.RED, Color.RED, Color.GREEN, Color.BLUE]
    guess = [Color.RED, Color.GREEN, Color.RED, Color.WHITE]
    # idx0 matches (black). Color counts: RED min(2,2)=2, GREEN min(1,1)=1,
    # BLUE min(1,0)=0, WHITE min(0,1)=0 -> 3 total color matches, 1 black, 2 white.
    assert score_guess(secret, guess) == Feedback(black=1, white=2)


def test_entering_pegs_builds_current_guess_in_order():
    state = GuessEntryState(secret=[Color.RED, Color.RED, Color.RED, Color.RED])
    state = enter_guess(state, RED, GREEN, BLUE)
    assert state.current_guess == [Color.RED, Color.GREEN, Color.BLUE]


def test_wrong_guess_confirmed_with_white_adds_history_row_and_resets():
    secret = [Color.RED, Color.RED, Color.RED, Color.RED]
    state = GuessEntryState(secret=secret)
    state = enter_guess(state, GREEN, GREEN, GREEN, GREEN)
    state = tap(state, WHITE)  # confirm
    assert isinstance(state, GuessEntryState)
    assert state.current_guess == []
    assert len(state.history) == 1
    guess, feedback = state.history[0]
    assert guess == [Color.GREEN, Color.GREEN, Color.GREEN, Color.GREEN]
    assert feedback == Feedback(black=0, white=0)


def test_clearing_with_red_discards_current_guess_not_history():
    state = GuessEntryState(secret=[Color.RED, Color.RED, Color.RED, Color.RED])
    state = enter_guess(state, GREEN, GREEN, GREEN, GREEN)
    state = tap(state, RED)  # clear, not a color peg since we're awaiting confirm
    assert isinstance(state, GuessEntryState)
    assert state.current_guess == []
    assert state.history == []


def test_correct_guess_wins_immediately():
    secret = [Color.RED, Color.GREEN, Color.BLUE, Color.YELLOW]
    state = GuessEntryState(secret=secret)
    state = enter_guess(state, RED, GREEN, BLUE, YELLOW)
    state = tap(state, WHITE)  # confirm
    assert isinstance(state, MastermindResultScreen)
    assert state.won is True
    assert state.attempts == 1


def test_ten_wrong_guesses_loses():
    secret = [Color.RED, Color.RED, Color.RED, Color.RED]
    state = GuessEntryState(secret=secret)
    for _ in range(10):
        state = enter_guess(state, GREEN, GREEN, GREEN, GREEN)
        state = tap(state, WHITE)
    assert isinstance(state, MastermindResultScreen)
    assert state.won is False
    assert state.attempts == 10


def test_big_red_button_returns_to_menu_mid_entry():
    state = GuessEntryState(secret=[Color.RED, Color.RED, Color.RED, Color.RED])
    state = enter_guess(state, RED, GREEN)
    sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, True)
    try:
        result = state.next_state(release())
    finally:
        sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, False)
    assert result is None


def test_result_screen_ignores_the_confirm_press_still_held_then_exits_on_the_next_one():
    state = MastermindResultScreen(secret=[Color.RED, Color.RED, Color.RED, Color.RED], history=[], won=True)
    # The White press that produced this screen is often still held on the very
    # first frame -- that must NOT immediately bounce back to the menu.
    still_held = state.next_state(press(WHITE))
    assert isinstance(still_held, MastermindResultScreen)
    # Only once it's released, and a fresh press follows, do we leave.
    armed = still_held.next_state(release())
    assert isinstance(armed, MastermindResultScreen)
    assert armed.next_state(press(RED)) is None


def test_result_screen_stays_up_while_untouched():
    state = MastermindResultScreen(secret=[Color.RED, Color.RED, Color.RED, Color.RED], history=[], won=True)
    assert isinstance(state.next_state(release()), MastermindResultScreen)

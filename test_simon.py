"""Drives the Simon Says continuous state directly, the same way test_tetris.py
exercises Tetris. Never calls draw().
"""

import sim_gpio
from common import Input
from hardware import BIG_RED_BUTTON_PIN, Color, buttons, buttons_in_order
from simon.game import (
    SHOW_GAP_MS,
    SHOW_ON_MS,
    RulesScreen,
    SimonResultScreen,
    SimonState,
    new_simon,
    new_simon_with_rules,
)


def press(*indices: int) -> Input:
    """An Input with exactly the buttons at the given left-to-right indices held."""
    for i, button in enumerate(buttons_in_order):
        sim_gpio.set_input_state(button.switch_pin, i in indices)
    return Input(buttons_in_order, current_time=0)


def release() -> Input:
    return press()  # no indices held


def held(*indices: int, current_time: int) -> Input:
    for i, button in enumerate(buttons_in_order):
        sim_gpio.set_input_state(button.switch_pin, i in indices)
    return Input(buttons_in_order, current_time=current_time)


# Button order is Red, Green, Blue, Yellow, White -- matching Color's declared order.
RED, GREEN, BLUE, YELLOW, WHITE = 0, 1, 2, 3, 4


def test_new_simon_with_rules_starts_on_the_rules_screen():
    state = new_simon_with_rules()
    assert isinstance(state, RulesScreen)


def test_rules_screen_advances_to_the_game_on_any_press():
    state = RulesScreen()
    result = state.next_state(press(BLUE))
    assert isinstance(result, SimonState)


def test_rules_screen_big_red_button_returns_to_menu():
    state = RulesScreen()
    sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, True)
    try:
        result = state.next_state(release())
    finally:
        sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, False)
    assert result is None


def test_new_simon_starts_with_a_single_step_sequence():
    state = new_simon()
    assert len(state.sequence) == 1
    assert state.rounds_completed == 0
    assert state.phase == "showing"


def test_showing_phase_plays_back_the_whole_sequence_then_starts_listening():
    state = SimonState(sequence=[Color.RED, Color.GREEN])

    result = state.next_state(held(current_time=0))
    assert result is state
    assert state.phase == "showing"
    assert state.lit_color == Color.RED
    assert sim_gpio.get_output_state(buttons[Color.RED].led_pin) is True

    state.next_state(held(current_time=SHOW_ON_MS))
    assert state.lit_color is None
    assert sim_gpio.get_output_state(buttons[Color.RED].led_pin) is False

    state.next_state(held(current_time=SHOW_ON_MS + SHOW_GAP_MS))
    assert state.lit_color == Color.GREEN
    assert sim_gpio.get_output_state(buttons[Color.GREEN].led_pin) is True

    state.next_state(held(current_time=SHOW_ON_MS + SHOW_GAP_MS + SHOW_ON_MS))
    assert state.lit_color is None

    state.next_state(held(current_time=2 * SHOW_ON_MS + 2 * SHOW_GAP_MS))
    assert state.phase == "listening"
    assert state.listen_index == 0


def test_correct_sequence_grows_the_pattern_and_stays_in_the_game():
    state = SimonState(sequence=[Color.RED, Color.GREEN], phase="listening")

    result = state.next_state(held(RED, current_time=1_000))
    assert result is state
    assert state.listen_index == 1

    state.next_state(release())  # require release between presses

    result = state.next_state(held(GREEN, current_time=1_100))
    assert isinstance(result, SimonState)
    assert state.rounds_completed == 1
    assert len(state.sequence) == 3
    assert state.phase == "showing"


def test_wrong_press_ends_the_game():
    state = SimonState(sequence=[Color.RED], phase="listening")

    result = state.next_state(held(GREEN, current_time=1_000))
    assert isinstance(result, SimonResultScreen)
    assert result.score == 0


def test_wrong_press_after_a_correct_round_reports_rounds_completed():
    state = SimonState(sequence=[Color.RED, Color.GREEN], phase="listening", rounds_completed=3)

    result = state.next_state(held(BLUE, current_time=1_000))
    assert isinstance(result, SimonResultScreen)
    assert result.score == 3


def test_holding_a_button_only_registers_once():
    state = SimonState(sequence=[Color.RED, Color.RED], phase="listening")

    state.next_state(held(RED, current_time=1_000))
    assert state.listen_index == 1

    state.next_state(held(RED, current_time=1_050))  # still holding, ignored
    assert state.listen_index == 1

    state.next_state(release())
    result = state.next_state(held(RED, current_time=1_100))
    assert isinstance(result, SimonState)
    assert state.rounds_completed == 1


def test_control_leds_turn_off_when_a_wrong_press_ends_the_game():
    state = SimonState(sequence=[Color.RED], phase="listening")
    state.next_state(held(GREEN, current_time=1_000))

    for color in Color:
        assert sim_gpio.get_output_state(buttons[color].led_pin) is False


def test_big_red_button_returns_to_menu():
    state = new_simon()
    sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, True)
    try:
        result = state.next_state(release())
    finally:
        sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, False)
    assert result is None


def test_result_screen_ignores_the_confirm_press_still_held_then_exits_on_the_next_one():
    state = SimonResultScreen(score=5)
    still_held = state.next_state(press(BLUE))
    assert isinstance(still_held, SimonResultScreen)
    armed = still_held.next_state(release())
    assert isinstance(armed, SimonResultScreen)
    assert armed.next_state(press(RED)) is None


def test_result_screen_green_starts_a_new_game():
    state = SimonResultScreen(score=5, ready=True)
    new_state = state.next_state(press(GREEN))
    assert isinstance(new_state, SimonState)
    assert new_state.rounds_completed == 0


def test_result_screen_ignores_other_buttons():
    state = SimonResultScreen(score=5, ready=True)
    assert isinstance(state.next_state(press(YELLOW)), SimonResultScreen)

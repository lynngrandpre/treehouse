"""Walks the Chain Reaction state machine directly through the simulator's GPIO
backend, the same way test_mastermind.py exercises Mastermind. Never calls draw().
"""

from typing import Any

import sim_gpio
from chain.game import ChainResultScreen, EntryState, ShowSequenceState, new_chain
from common import Input
from hardware import BIG_RED_BUTTON_PIN, Color, buttons_in_order


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


def past_the_flash(state: ShowSequenceState) -> EntryState:
    """A ShowSequenceState always resolves to an EntryState once enough time
    has passed -- no button presses involved, just ticks."""
    state = state.next_state(Input(buttons_in_order, current_time=0))  # anchors start_time
    state = state.next_state(Input(buttons_in_order, current_time=1_000_000))  # far past any flash
    assert isinstance(state, EntryState)
    return state


def enter_link(state: Any, *indices: int) -> Any:
    for i in indices:
        state = tap(state, i)
    return state


def test_new_chain_starts_empty_and_waiting_on_player_one():
    state = new_chain()
    assert isinstance(state, ShowSequenceState)
    assert state.sequence == []
    assert state.turn == 0


def test_empty_chain_resolves_straight_to_entry_for_player_one():
    state = past_the_flash(new_chain())
    assert state.sequence == []
    assert state.turn == 0
    assert state.progress == 0


def test_first_add_grows_the_chain_and_flips_the_turn():
    state = past_the_flash(new_chain())
    state = enter_link(state, RED)
    assert isinstance(state, ShowSequenceState)
    assert state.sequence == [Color.RED]
    assert state.turn == 1


def test_second_player_repeats_then_adds_their_own_link():
    state = past_the_flash(new_chain())
    state = enter_link(state, RED)  # player 1 adds RED, turn -> player 2

    state = past_the_flash(state)
    assert state.turn == 1
    assert state.progress == 0

    state = enter_link(state, RED, GREEN)  # repeat RED, then add GREEN
    assert isinstance(state, ShowSequenceState)
    assert state.sequence == [Color.RED, Color.GREEN]
    assert state.turn == 0


def test_wrong_repeat_breaks_the_chain_for_the_whole_team():
    state = past_the_flash(new_chain())
    state = enter_link(state, RED)  # chain: [RED], turn -> player 2
    state = past_the_flash(state)

    state = enter_link(state, BLUE)  # should have repeated RED
    assert isinstance(state, ChainResultScreen)
    assert state.won is False
    assert state.broke_turn == 1
    assert state.sequence == [Color.RED]


def test_reaching_win_length_is_a_shared_win():
    state: Any = past_the_flash(new_chain())
    # Every "turn" here just repeats what's there and adds RED again -- easy
    # to construct, and irrelevant to the win-length logic being tested.
    for _ in range(11):
        state = enter_link(state, *([RED] * len(state.sequence) + [RED]))
        state = past_the_flash(state)
    # One more full turn (11 links repeated + 1 new) reaches WIN_LENGTH=12.
    state = enter_link(state, *([RED] * len(state.sequence) + [RED]))
    assert isinstance(state, ChainResultScreen)
    assert state.won is True
    assert len(state.sequence) == 12


def test_big_red_button_returns_to_menu_from_entry():
    state = past_the_flash(new_chain())
    sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, True)
    try:
        result = state.next_state(release())
    finally:
        sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, False)
    assert result is None


def test_result_screen_ignores_the_confirm_press_still_held_then_exits_on_the_next_one():
    state = ChainResultScreen(sequence=[Color.RED], broke_turn=0, won=False)
    still_held = state.next_state(press(BLUE))
    assert isinstance(still_held, ChainResultScreen)
    armed = still_held.next_state(release())
    assert isinstance(armed, ChainResultScreen)
    assert armed.next_state(press(RED)) is None


def test_result_screen_green_starts_a_new_game():
    state = ChainResultScreen(sequence=[Color.RED], broke_turn=0, won=False, ready=True)
    new_state = state.next_state(press(GREEN))
    assert isinstance(new_state, ShowSequenceState)
    assert new_state.sequence == []
    assert new_state.turn == 0


def test_result_screen_ignores_other_buttons():
    state = ChainResultScreen(sequence=[Color.RED], broke_turn=0, won=False, ready=True)
    assert isinstance(state.next_state(press(YELLOW)), ChainResultScreen)

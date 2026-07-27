"""Walks the Vault Escape state machine directly through the simulator's GPIO
backend, the same way test_chain.py exercises Chain Reaction. Never calls draw().
"""

from typing import Any

import sim_gpio
from common import Input
from hardware import BIG_RED_BUTTON_PIN, Color, buttons_in_order
from vault.game import (
    TOTAL_TIME_MS,
    WRONG_PENALTY_MS,
    FinalCodeState,
    MemoryEntryState,
    MemoryShowState,
    RiddleState,
    VaultResultScreen,
    new_vault_escape,
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


def tap(state: Any, index: int, current_time: int) -> Any:
    """One full press-then-release of a single button, as a real tap would
    land across two frames."""
    pressed = state.next_state(held(index, current_time=current_time))
    released = pressed.next_state(held(current_time=current_time))
    return released


# Button order is Red, Green, Blue, Yellow, White -- matches COLORS_IN_ORDER.
RED, GREEN, BLUE, YELLOW, WHITE = 0, 1, 2, 3, 4
INDEX_OF = {Color.RED: RED, Color.GREEN: GREEN, Color.BLUE: BLUE, Color.YELLOW: YELLOW, Color.WHITE: WHITE}


def past_the_flash(state: MemoryShowState) -> MemoryEntryState:
    """A MemoryShowState always resolves to a MemoryEntryState once enough
    time has passed -- no button presses involved, just ticks."""
    state = state.next_state(Input(buttons_in_order, current_time=0))  # sets the deadline, anchors the flash
    state = state.next_state(Input(buttons_in_order, current_time=5_000))  # past the flash, well before the deadline
    assert isinstance(state, MemoryEntryState)
    return state


def enter_sequence(state: Any, colors: list[Color], current_time: int) -> Any:
    for color in colors:
        state = tap(state, INDEX_OF[color], current_time)
    return state


def test_new_vault_escape_starts_on_the_memory_room():
    state = new_vault_escape()
    assert isinstance(state, MemoryShowState)
    assert len(state.sequence) == 4


def test_memory_show_sets_a_deadline_on_the_first_tick():
    state = new_vault_escape()
    result = state.next_state(Input(buttons_in_order, current_time=500))
    assert result.deadline == 500 + TOTAL_TIME_MS


def test_repeating_the_memory_code_correctly_advances_to_the_riddle():
    state = past_the_flash(new_vault_escape())
    state = enter_sequence(state, state.sequence, current_time=5_000)
    assert isinstance(state, RiddleState)


def test_wrong_repeat_costs_time_and_goes_back_to_the_flash():
    state = past_the_flash(new_vault_escape())
    deadline_before = state.deadline
    wrong = Color.WHITE if state.sequence[0] != Color.WHITE else Color.RED
    result = state.next_state(held(INDEX_OF[wrong], current_time=5_000))
    assert isinstance(result, MemoryShowState)
    assert result.sequence == state.sequence
    assert result.deadline == deadline_before - WRONG_PENALTY_MS


def test_riddle_wrong_answer_costs_time_and_keeps_the_same_riddle():
    state = RiddleState(question="Q", answer=Color.GREEN, deadline=100_000)
    wrong = Color.RED
    result = state.next_state(held(INDEX_OF[wrong], current_time=1_000))
    assert isinstance(result, RiddleState)
    assert result.question == "Q"
    assert result.answer == Color.GREEN
    assert result.deadline == 100_000 - WRONG_PENALTY_MS


def test_riddle_correct_answer_advances_to_the_final_code():
    state = RiddleState(question="Q", answer=Color.GREEN, deadline=100_000)
    result = state.next_state(held(INDEX_OF[Color.GREEN], current_time=1_000))
    assert isinstance(result, FinalCodeState)
    assert result.deadline == 100_000


def test_final_code_wrong_entry_resets_progress_and_costs_time():
    state = FinalCodeState(code=[Color.RED, Color.GREEN], deadline=100_000, progress=1)
    wrong = Color.WHITE
    result = state.next_state(held(INDEX_OF[wrong], current_time=1_000))
    assert isinstance(result, FinalCodeState)
    assert result.progress == 0
    assert result.deadline == 100_000 - WRONG_PENALTY_MS


def test_final_code_completed_wins():
    state = FinalCodeState(code=[Color.RED, Color.GREEN], deadline=100_000, progress=0)
    state = enter_sequence(state, [Color.RED, Color.GREEN], current_time=1_000)
    assert isinstance(state, VaultResultScreen)
    assert state.won is True


def test_running_out_the_clock_loses():
    state = MemoryEntryState(sequence=[Color.RED], deadline=1_000)
    result = state.next_state(held(current_time=1_000))
    assert isinstance(result, VaultResultScreen)
    assert result.won is False


def test_big_red_button_returns_to_menu():
    state = past_the_flash(new_vault_escape())
    sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, True)
    try:
        result = state.next_state(held(current_time=5_000))
    finally:
        sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, False)
    assert result is None


def test_result_screen_ignores_the_confirm_press_still_held_then_exits_on_the_next_one():
    state = VaultResultScreen(won=False)
    still_held = state.next_state(press(BLUE))
    assert isinstance(still_held, VaultResultScreen)
    armed = still_held.next_state(release())
    assert isinstance(armed, VaultResultScreen)
    assert armed.next_state(press(RED)) is None


def test_result_screen_green_starts_a_new_game():
    state = VaultResultScreen(won=True, ready=True)
    new_state = state.next_state(press(GREEN))
    assert isinstance(new_state, MemoryShowState)


def test_result_screen_ignores_other_buttons():
    state = VaultResultScreen(won=False, ready=True)
    assert isinstance(state.next_state(press(YELLOW)), VaultResultScreen)

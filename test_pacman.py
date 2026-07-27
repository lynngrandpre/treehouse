"""Drives the Pac-Duo continuous state directly, the same way test_chain.py
exercises Chain Reaction, but with hand-built tiny mazes so the tests stay
independent of the real maze layout. Never calls draw().
"""

from typing import Any

import sim_gpio
from common import Input
from hardware import BIG_RED_BUTTON_PIN, buttons_in_order
from pacman.game import (
    GHOST_INTERVAL_MS,
    MOVE_INTERVAL_MS,
    Ghost,
    PacDuoResultScreen,
    PacDuoState,
    RulesScreen,
    new_pacman,
    new_pacman_with_rules,
)


def press(*indices: int) -> Input:
    """An Input with exactly the buttons at the given left-to-right indices held."""
    for i, button in enumerate(buttons_in_order):
        sim_gpio.set_input_state(button.switch_pin, i in indices)
    return Input(buttons_in_order, current_time=0)


def release() -> Input:
    return press()  # no indices held


# Button order is Red, Green, Blue, Yellow, White.
RED, GREEN, BLUE, YELLOW, WHITE = 0, 1, 2, 3, 4


def held(*indices: int, current_time: int) -> Input:
    for i, button in enumerate(buttons_in_order):
        sim_gpio.set_input_state(button.switch_pin, i in indices)
    return Input(buttons_in_order, current_time=current_time)


# A 5x5 room, walled on the border, open (pellet-filled) inside -- enough to
# test movement, pellets, and ghost contact without depending on the real
# maze layout.
def tiny_room() -> list[list[str]]:
    return [
        list("#####"),
        list("#...#"),
        list("#...#"),
        list("#...#"),
        list("#####"),
    ]


def make_state(grid=None, player_pos=(2, 2), ghosts=None, **overrides: Any) -> PacDuoState:
    grid = grid if grid is not None else tiny_room()
    ghosts = ghosts if ghosts is not None else [Ghost(pos=(1, 1), start=(1, 1))]
    pellets_remaining = sum(row.count('.') for row in grid)
    state = PacDuoState(grid=grid, player_pos=player_pos, ghosts=ghosts, pellets_remaining=pellets_remaining)
    for key, value in overrides.items():
        setattr(state, key, value)
    return state


def test_new_pacman_with_rules_starts_on_the_rules_screen():
    state = new_pacman_with_rules()
    assert isinstance(state, RulesScreen)


def test_rules_screen_advances_to_the_maze_on_any_press():
    state = RulesScreen()
    result = state.next_state(press(BLUE))
    assert isinstance(result, PacDuoState)


def test_rules_screen_big_red_button_returns_to_menu():
    state = RulesScreen()
    sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, True)
    try:
        result = state.next_state(release())
    finally:
        sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, False)
    assert result is None


def test_rules_screen_carries_difficulty_into_the_maze():
    state = RulesScreen(ghost_count=1, ghost_interval_ms=340)
    result = state.next_state(press(BLUE))
    assert isinstance(result, PacDuoState)
    assert len(result.ghosts) == 1
    assert result.ghost_interval_ms == 340


def test_easy_pacman_has_one_slower_ghost():
    state = new_pacman(ghost_count=1, ghost_interval_ms=340)
    assert len(state.ghosts) == 1
    assert state.ghost_interval_ms == 340


def test_new_pacman_starts_with_pellets_and_the_expected_layout():
    state = new_pacman()
    assert isinstance(state, PacDuoState)
    assert state.player_pos == (5, 10)
    assert len(state.ghosts) == 2
    assert state.pellets_remaining > 0
    assert state.stored_powerups == 0


def test_player_moves_right_toward_yellow():
    state = make_state(player_pos=(2, 1))
    result = state.next_state(held(YELLOW, current_time=MOVE_INTERVAL_MS))
    assert result is state
    assert state.player_pos == (2, 2)


def test_player_moves_up_toward_green_and_down_toward_blue():
    up = make_state(player_pos=(2, 2))
    up.next_state(held(GREEN, current_time=MOVE_INTERVAL_MS))
    assert up.player_pos == (1, 2)

    down = make_state(player_pos=(2, 2))
    down.next_state(held(BLUE, current_time=MOVE_INTERVAL_MS))
    assert down.player_pos == (3, 2)


def test_player_cannot_move_through_a_wall():
    state = make_state(player_pos=(1, 1))  # already against the top-left corridor
    state.next_state(held(GREEN, YELLOW, current_time=MOVE_INTERVAL_MS))
    # Yellow (right) succeeds, Green (up, blocked by the border) does not.
    assert state.player_pos == (1, 2)


def test_movement_is_gated_by_the_move_interval():
    state = make_state(player_pos=(2, 2))
    state.next_state(held(YELLOW, current_time=MOVE_INTERVAL_MS - 1))
    assert state.player_pos == (2, 2)  # not enough time has passed yet


def test_moving_onto_a_pellet_eats_it():
    state = make_state(player_pos=(2, 1))
    before = state.pellets_remaining
    state.next_state(held(YELLOW, current_time=MOVE_INTERVAL_MS))
    assert state.player_pos == (2, 2)
    assert state.grid[2][2] == ' '
    assert state.pellets_remaining == before - 1


def test_moving_onto_a_power_pellet_stores_a_powerup_without_scaring():
    grid = tiny_room()
    grid[2][2] = 'o'
    state = make_state(grid=grid, player_pos=(2, 1))
    state.next_state(held(YELLOW, current_time=MOVE_INTERVAL_MS))
    assert state.grid[2][2] == ' '
    assert state.stored_powerups == 1
    assert state.scared_until == 0


def test_white_consumes_a_stored_powerup_once_per_press():
    state = make_state(stored_powerups=1)
    state.next_state(held(WHITE, current_time=100))
    assert state.stored_powerups == 0
    assert state.scared_until == 100 + 6000  # SCARED_DURATION_MS

    # Still held next frame -- shouldn't consume a second (nonexistent) charge.
    scared_at = state.scared_until
    state.next_state(held(WHITE, current_time=101))
    assert state.stored_powerups == 0
    assert state.scared_until == scared_at


def test_white_does_nothing_without_a_stored_powerup():
    state = make_state(stored_powerups=0)
    state.next_state(held(WHITE, current_time=100))
    assert state.scared_until == 0


def test_ghost_catches_player_when_not_scared_ends_the_game():
    state = make_state(player_pos=(1, 1), ghosts=[Ghost(pos=(1, 1), start=(1, 1))])
    result = state.next_state(release())
    assert isinstance(result, PacDuoResultScreen)
    assert result.won is False


def test_ghost_is_eaten_when_scared_and_resets_to_start():
    state = make_state(
        player_pos=(1, 1),
        ghosts=[Ghost(pos=(1, 1), start=(3, 3))],
        scared_until=1_000_000,
    )
    result = state.next_state(Input(buttons_in_order, current_time=0))
    assert result is state
    assert state.ghosts[0].pos == (3, 3)


def test_eating_the_last_pellet_wins():
    # The win check only cares about the counter, so drive it to zero
    # directly rather than choreographing the exact move that empties it.
    state = make_state(ghosts=[])
    state.pellets_remaining = 0
    result = state.next_state(release())
    assert isinstance(result, PacDuoResultScreen)
    assert result.won is True


def test_ghost_steps_toward_the_player_along_the_larger_axis():
    state = make_state(player_pos=(3, 3), ghosts=[Ghost(pos=(1, 1), start=(1, 1))])
    state.next_state(held(current_time=GHOST_INTERVAL_MS))
    # Row distance (2) and column distance (2) are tied in this setup, so
    # either single-axis step is a valid greedy move toward the player.
    assert state.ghosts[0].pos in [(2, 1), (1, 2)]


def test_big_red_button_returns_to_menu():
    state = make_state()
    sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, True)
    try:
        result = state.next_state(release())
    finally:
        sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, False)
    assert result is None


def test_result_screen_ignores_the_confirm_press_still_held_then_exits_on_the_next_one():
    state = PacDuoResultScreen(won=False)
    still_held = state.next_state(press(BLUE))
    assert isinstance(still_held, PacDuoResultScreen)
    armed = still_held.next_state(release())
    assert isinstance(armed, PacDuoResultScreen)
    assert armed.next_state(press(RED)) is None


def test_result_screen_green_starts_a_new_game():
    state = PacDuoResultScreen(won=True, ready=True)
    new_state = state.next_state(press(GREEN))
    assert isinstance(new_state, PacDuoState)
    assert new_state.player_pos == (5, 10)


def test_result_screen_green_preserves_difficulty():
    state = PacDuoResultScreen(won=False, ghost_count=1, ghost_interval_ms=340, ready=True)
    new_state = state.next_state(press(GREEN))
    assert isinstance(new_state, PacDuoState)
    assert len(new_state.ghosts) == 1
    assert new_state.ghost_interval_ms == 340


def test_ghost_catch_carries_difficulty_into_the_result_screen():
    state = make_state(
        player_pos=(1, 1),
        ghosts=[Ghost(pos=(1, 1), start=(1, 1))],
        ghost_interval_ms=340,
    )
    result = state.next_state(release())
    assert isinstance(result, PacDuoResultScreen)
    assert result.ghost_count == 1
    assert result.ghost_interval_ms == 340


def test_result_screen_ignores_other_buttons():
    state = PacDuoResultScreen(won=False, ready=True)
    assert isinstance(state.next_state(press(YELLOW)), PacDuoResultScreen)

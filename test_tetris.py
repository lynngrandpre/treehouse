"""Drives the Tetris continuous state directly, the same way test_breakout.py
exercises Breakout. Never calls draw().
"""

import sim_gpio
from common import Input
from hardware import BIG_RED_BUTTON_PIN, Color, buttons, buttons_in_order
from tetris.game import (
    BOARD_COLS,
    BOARD_ROWS,
    BOMB_LINES_PER_CHARGE,
    BOMB_ROWS_REMOVED,
    LINE_SCORES,
    MOVE_INITIAL_DELAY_MS,
    MOVE_REPEAT_MS,
    PIECE_TYPES,
    RulesScreen,
    TetrisResultScreen,
    TetrisState,
    _piece_cells,
    _spawn_position,
    new_tetris,
    new_tetris_with_rules,
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


# Button order is Red, Green, Blue, Yellow, White.
RED, GREEN, BLUE, YELLOW, WHITE = 0, 1, 2, 3, 4


def test_new_tetris_with_rules_starts_on_the_rules_screen():
    state = new_tetris_with_rules()
    assert isinstance(state, RulesScreen)


def test_rules_screen_advances_to_the_game_on_any_press():
    state = RulesScreen()
    result = state.next_state(press(BLUE))
    assert isinstance(result, TetrisState)


def test_rules_screen_big_red_button_returns_to_menu():
    state = RulesScreen()
    sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, True)
    try:
        result = state.next_state(release())
    finally:
        sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, False)
    assert result is None


def test_new_tetris_starts_with_an_empty_board_and_zero_score():
    state = new_tetris()
    assert state.score == 0
    assert state.lines_cleared == 0
    assert state.piece_rotation == 0
    assert state.piece_type in PIECE_TYPES
    assert state.next_piece in PIECE_TYPES
    assert all(cell is None for row in state.board for cell in row)
    assert (state.piece_col, state.piece_row) == _spawn_position(state.piece_type)


def test_blue_moves_the_piece_right_and_red_moves_it_left():
    state = new_tetris()
    state.piece_type = "O"
    state.piece_col, state.piece_row = 4, 0

    result = state.next_state(held(BLUE, current_time=1_000))
    assert result is state
    assert state.piece_col == 5

    state.next_state(held(RED, current_time=1_050))
    assert state.piece_col == 4


def test_holding_a_direction_repeats_after_the_initial_delay():
    state = new_tetris()
    state.piece_type = "O"
    state.piece_col, state.piece_row = 4, 0

    state.next_state(held(BLUE, current_time=1_000))
    assert state.piece_col == 5

    state.next_state(held(BLUE, current_time=1_000 + MOVE_INITIAL_DELAY_MS - 1))
    assert state.piece_col == 5  # not yet time to repeat

    state.next_state(held(BLUE, current_time=1_000 + MOVE_INITIAL_DELAY_MS))
    assert state.piece_col == 6  # auto-shift kicked in


def test_horizontal_movement_is_clamped_within_the_board():
    state = new_tetris()
    state.piece_type = "O"
    state.piece_col, state.piece_row = 4, 0

    t = 1_000
    for _ in range(20):
        state.next_state(held(RED, current_time=t))
        t += MOVE_REPEAT_MS + 10
    assert state.piece_col == 0

    for _ in range(20):
        state.next_state(held(BLUE, current_time=t))
        t += MOVE_REPEAT_MS + 10
    assert state.piece_col == BOARD_COLS - 2  # O piece is 2 columns wide


def test_green_rotates_the_piece():
    state = new_tetris()
    state.piece_type = "T"
    state.piece_col, state.piece_row = 4, 5

    result = state.next_state(held(GREEN, current_time=1_000))
    assert result is state
    assert state.piece_rotation == 1


def test_rotation_is_blocked_when_there_is_no_room():
    state = new_tetris()
    state.piece_type = "T"
    state.piece_col, state.piece_row = 4, 5
    current_cells = set(_piece_cells("T", 0, 4, 5))
    for row in range(BOARD_ROWS):
        for col in range(BOARD_COLS):
            if (col, row) not in current_cells:
                state.board[row][col] = "Z"

    result = state.next_state(held(GREEN, current_time=1_000))
    assert result is state
    assert state.piece_rotation == 0


def test_white_hard_drops_the_piece_to_the_floor():
    state = new_tetris()
    state.piece_type = "O"
    state.piece_col, state.piece_row = 4, 0

    result = state.next_state(held(WHITE, current_time=1_000))
    assert result is state
    assert state.board[BOARD_ROWS - 1][4] == "O"
    assert state.board[BOARD_ROWS - 1][5] == "O"
    assert state.board[BOARD_ROWS - 2][4] == "O"
    assert state.board[BOARD_ROWS - 2][5] == "O"
    assert state.piece_row == 0  # a fresh piece has spawned back at the top


def test_completing_a_row_clears_it_and_scores():
    state = new_tetris()
    # Fill the bottom row except for a 2-wide gap on the left, sized for an O piece.
    for col in range(2, BOARD_COLS):
        state.board[BOARD_ROWS - 1][col] = "Z"
    state.piece_type = "O"
    state.piece_col, state.piece_row = 0, 0

    result = state.next_state(held(WHITE, current_time=1_000))
    assert result is state
    assert state.lines_cleared == 1
    assert state.score == LINE_SCORES[1]
    assert state.board[0] == [None] * BOARD_COLS  # a fresh empty row was inserted at the top
    assert state.board[BOARD_ROWS - 1][0] == "O"  # the row below the cleared one shifted down
    assert state.board[BOARD_ROWS - 1][2] is None


def test_locking_a_piece_with_no_room_to_spawn_ends_the_game():
    state = new_tetris()
    state.piece_type = "O"
    state.next_piece = "O"
    for row in range(BOARD_ROWS):
        for col in range(BOARD_COLS):
            state.board[row][col] = "Z"
        state.board[row][BOARD_COLS - 1] = None  # keep a column open so no row is ever "full"
    state.piece_col, state.piece_row = 0, 0
    state.board[0][0] = state.board[0][1] = None
    state.board[1][0] = state.board[1][1] = None

    result = state.next_state(held(WHITE, current_time=1_000))
    assert isinstance(result, TetrisResultScreen)
    assert result.lines_cleared == 0


def test_control_leds_turn_off_when_the_game_ends():
    state = new_tetris()
    state.piece_type = "O"
    state.next_piece = "O"
    for row in range(BOARD_ROWS):
        for col in range(BOARD_COLS):
            state.board[row][col] = "Z"
        state.board[row][BOARD_COLS - 1] = None
    state.piece_col, state.piece_row = 0, 0
    state.board[0][0] = state.board[0][1] = None
    state.board[1][0] = state.board[1][1] = None

    state.next_state(held(WHITE, current_time=1_000))
    assert sim_gpio.get_output_state(buttons[Color.RED].led_pin) is False
    assert sim_gpio.get_output_state(buttons[Color.YELLOW].led_pin) is False
    assert sim_gpio.get_output_state(buttons[Color.GREEN].led_pin) is False
    assert sim_gpio.get_output_state(buttons[Color.BLUE].led_pin) is False
    assert sim_gpio.get_output_state(buttons[Color.WHITE].led_pin) is False


def test_big_red_button_returns_to_menu():
    state = new_tetris()
    sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, True)
    try:
        result = state.next_state(release())
    finally:
        sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, False)
    assert result is None


def test_result_screen_ignores_the_confirm_press_still_held_then_exits_on_the_next_one():
    state = TetrisResultScreen(score=500, lines_cleared=4)
    still_held = state.next_state(press(BLUE))
    assert isinstance(still_held, TetrisResultScreen)
    armed = still_held.next_state(release())
    assert isinstance(armed, TetrisResultScreen)
    assert armed.next_state(press(RED)) is None


def test_result_screen_green_starts_a_new_game():
    state = TetrisResultScreen(score=500, lines_cleared=4, ready=True)
    new_state = state.next_state(press(GREEN))
    assert isinstance(new_state, TetrisState)
    assert new_state.score == 0


def test_result_screen_ignores_other_buttons():
    state = TetrisResultScreen(score=500, lines_cleared=4, ready=True)
    assert isinstance(state.next_state(press(YELLOW)), TetrisResultScreen)


def test_normal_mode_bomb_is_never_ready():
    state = new_tetris()
    state.lines_cleared = BOMB_LINES_PER_CHARGE
    assert state.bomb_ready is False


def test_bomb_mode_bomb_becomes_ready_after_enough_lines():
    state = new_tetris(bomb_mode=True)
    assert state.bomb_ready is False
    state.lines_cleared = BOMB_LINES_PER_CHARGE
    assert state.bomb_ready is True


def test_big_red_detonates_a_ready_bomb_removing_random_rows():
    state = new_tetris(bomb_mode=True)
    state.lines_cleared = BOMB_LINES_PER_CHARGE
    for row in range(BOARD_ROWS):
        state.board[row][0] = "Z"

    sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, True)
    try:
        result = state.next_state(held(current_time=1_000))
    finally:
        sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, False)
    assert result is state
    assert state.bombs_used == 1
    assert state.bomb_ready is False
    filled_rows = sum(1 for row in state.board if row[0] == "Z")
    assert filled_rows == BOARD_ROWS - BOMB_ROWS_REMOVED
    assert state.board[0] == [None] * BOARD_COLS


def test_big_red_does_nothing_without_a_ready_bomb():
    state = new_tetris(bomb_mode=True)
    for row in range(BOARD_ROWS):
        state.board[row][0] = "Z"

    sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, True)
    try:
        result = state.next_state(held(current_time=1_000))
    finally:
        sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, False)
    assert result is state
    assert state.bombs_used == 0
    assert all(row[0] == "Z" for row in state.board)


def test_big_red_no_longer_quits_bomb_mode():
    state = new_tetris(bomb_mode=True)
    sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, True)
    try:
        result = state.next_state(held(current_time=1_000))
    finally:
        sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, False)
    assert result is state


def test_yellow_and_white_together_quit_bomb_mode():
    state = new_tetris(bomb_mode=True)
    result = state.next_state(held(YELLOW, WHITE, current_time=1_000))
    assert result is None


def test_yellow_alone_does_not_quit_bomb_mode():
    state = new_tetris(bomb_mode=True)
    result = state.next_state(held(YELLOW, current_time=1_000))
    assert result is state


def test_big_red_still_quits_normal_mode():
    state = new_tetris()
    sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, True)
    try:
        result = state.next_state(held(current_time=1_000))
    finally:
        sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, False)
    assert result is None


def test_rules_screen_starts_a_bomb_mode_game():
    state = RulesScreen(bomb_mode=True)
    result = state.next_state(press(BLUE))
    assert isinstance(result, TetrisState)
    assert result.bomb_mode is True


def test_result_screen_play_again_preserves_bomb_mode():
    state = TetrisResultScreen(score=500, lines_cleared=4, bomb_mode=True, ready=True)
    new_state = state.next_state(press(GREEN))
    assert isinstance(new_state, TetrisState)
    assert new_state.bomb_mode is True

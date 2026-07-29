"""Drives the Breakout continuous state directly, the same way test_pacman.py
exercises Pac-Duo. Never calls draw().
"""

import sim_gpio
from breakout.game import (
    BALL_RADIUS,
    BRICK_COLS,
    BRICK_ROWS,
    CANVAS_HEIGHT,
    GAME_OVER_DELAY_MS,
    HUD_HEIGHT,
    PADDLE_WIDTH,
    PADDLE_Y,
    PLAY_LEFT,
    PLAY_RIGHT,
    REVEAL_FACES,
    SERVE_DELAY_MS,
    STARTING_LIVES,
    TOTAL_BRICKS,
    TURBO_DURATION_MS,
    TURBO_MULTIPLIER,
    BreakoutResultScreen,
    BreakoutState,
    RulesScreen,
    new_breakout,
    new_breakout_with_rules,
)
from common import Input
from hardware import BIG_RED_BUTTON_PIN, Color, buttons, buttons_in_order


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


def ticking(state: BreakoutState) -> BreakoutState:
    """The first next_state call only anchors last_update_time (dt would
    otherwise be however long it took to get here) -- burn that frame."""
    result = state.next_state(release())
    assert result is state
    return state


def test_new_breakout_with_rules_starts_on_the_rules_screen():
    state = new_breakout_with_rules()
    assert isinstance(state, RulesScreen)


def test_rules_screen_advances_to_the_game_on_any_press():
    state = RulesScreen()
    result = state.next_state(press(BLUE))
    assert isinstance(result, BreakoutState)


def test_rules_screen_big_red_button_returns_to_menu():
    state = RulesScreen()
    sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, True)
    try:
        result = state.next_state(release())
    finally:
        sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, False)
    assert result is None


def test_new_breakout_starts_with_full_bricks_and_lives_and_a_centered_paddle():
    state = new_breakout()
    assert state.lives == STARTING_LIVES
    assert state.bricks_remaining == BRICK_ROWS * BRICK_COLS
    assert all(all(row) for row in state.bricks)
    assert state.paddle_x == PLAY_LEFT + (PLAY_RIGHT - PLAY_LEFT - PADDLE_WIDTH) / 2


def test_new_breakout_picks_a_valid_reveal_face_and_keeps_it_across_ticks():
    state = ticking(new_breakout())
    assert state.reveal_face in range(len(REVEAL_FACES))
    face = state.reveal_face
    state.next_state(held(current_time=50))
    assert state.reveal_face == face


def test_first_tick_only_anchors_the_clock_and_does_not_move_anything():
    state = new_breakout()
    ball_before = (state.ball_x, state.ball_y)
    result = state.next_state(held(current_time=5_000))
    assert result is state
    assert (state.ball_x, state.ball_y) == ball_before


def test_paddle_moves_right_toward_yellow_and_left_toward_red():
    state = ticking(new_breakout())
    state.next_state(held(YELLOW, current_time=1_100))
    assert state.paddle_x > PLAY_LEFT + (PLAY_RIGHT - PLAY_LEFT - PADDLE_WIDTH) / 2

    state = ticking(new_breakout())
    state.next_state(held(RED, current_time=1_100))
    assert state.paddle_x < PLAY_LEFT + (PLAY_RIGHT - PLAY_LEFT - PADDLE_WIDTH) / 2


def test_paddle_is_clamped_to_the_play_area():
    state = ticking(new_breakout())
    state.next_state(held(RED, current_time=10_000))  # way more than enough to cross the whole play area
    assert state.paddle_x == PLAY_LEFT

    state = ticking(new_breakout())
    state.next_state(held(YELLOW, current_time=10_000))
    assert state.paddle_x == PLAY_RIGHT - PADDLE_WIDTH


def test_turbo_moves_the_paddle_faster_than_normal():
    # A short dt so neither run clamps against the play-area wall.
    state = ticking(new_breakout())
    start = state.paddle_x
    state.next_state(held(YELLOW, current_time=50))
    normal_distance = state.paddle_x - start

    state = ticking(new_breakout())
    start = state.paddle_x
    state.next_state(held(WHITE, YELLOW, current_time=50))
    turbo_distance = state.paddle_x - start

    assert turbo_distance == normal_distance * TURBO_MULTIPLIER


def test_white_alone_does_not_move_the_paddle():
    state = ticking(new_breakout())
    start = state.paddle_x
    state.next_state(held(WHITE, current_time=50))
    assert state.paddle_x == start


def test_red_and_yellow_leds_light_up_as_a_control_cue():
    state = ticking(new_breakout())
    state.next_state(held(current_time=50))
    assert sim_gpio.get_output_state(buttons[Color.RED].led_pin) is True
    assert sim_gpio.get_output_state(buttons[Color.YELLOW].led_pin) is True


def test_white_led_lights_up_only_during_turbo():
    state = ticking(new_breakout())
    state.next_state(held(YELLOW, current_time=50))
    assert sim_gpio.get_output_state(buttons[Color.WHITE].led_pin) is False

    state.next_state(held(WHITE, YELLOW, current_time=100))
    assert sim_gpio.get_output_state(buttons[Color.WHITE].led_pin) is True


def test_turbo_stays_engaged_after_release_until_the_duration_elapses():
    state = ticking(new_breakout())
    state.next_state(held(WHITE, YELLOW, current_time=50))  # presses the combo
    assert sim_gpio.get_output_state(buttons[Color.WHITE].led_pin) is True

    # Buttons released, but still within the 15-second turbo window.
    state.next_state(held(current_time=50 + TURBO_DURATION_MS - 1))
    assert sim_gpio.get_output_state(buttons[Color.WHITE].led_pin) is True

    # Window has now elapsed.
    state.next_state(held(current_time=50 + TURBO_DURATION_MS))
    assert sim_gpio.get_output_state(buttons[Color.WHITE].led_pin) is False


def test_pressing_turbo_again_extends_the_window():
    state = ticking(new_breakout())
    state.next_state(held(WHITE, YELLOW, current_time=50))
    state.next_state(held(WHITE, YELLOW, current_time=1_000))  # re-pressed, resets the clock

    # Would have expired under the first press's window, but not the second's.
    state.next_state(held(current_time=50 + TURBO_DURATION_MS))
    assert sim_gpio.get_output_state(buttons[Color.WHITE].led_pin) is True


def test_blue_and_green_leds_stay_off_during_gameplay():
    state = ticking(new_breakout())
    state.next_state(held(current_time=50))
    assert sim_gpio.get_output_state(buttons[Color.BLUE].led_pin) is False
    assert sim_gpio.get_output_state(buttons[Color.GREEN].led_pin) is False


def test_result_screen_lights_only_red_and_green():
    state = BreakoutResultScreen(won=False, bricks_hit=12, ready=True)
    state.next_state(press(BLUE))
    assert sim_gpio.get_output_state(buttons[Color.RED].led_pin) is True
    assert sim_gpio.get_output_state(buttons[Color.GREEN].led_pin) is True
    assert sim_gpio.get_output_state(buttons[Color.YELLOW].led_pin) is False
    assert sim_gpio.get_output_state(buttons[Color.BLUE].led_pin) is False
    assert sim_gpio.get_output_state(buttons[Color.WHITE].led_pin) is False


def test_control_leds_turn_off_when_the_game_ends():
    state = BreakoutState(
        paddle_x=300, ball_x=400, ball_y=CANVAS_HEIGHT - 5, ball_vx=0, ball_vy=200,
        bricks=[[False] * BRICK_COLS for _ in range(BRICK_ROWS)], bricks_remaining=5,
        lives=1, last_update_time=1_000,
    )
    state.next_state(held(current_time=1_100))
    assert sim_gpio.get_output_state(buttons[Color.RED].led_pin) is False
    assert sim_gpio.get_output_state(buttons[Color.YELLOW].led_pin) is False
    assert sim_gpio.get_output_state(buttons[Color.WHITE].led_pin) is False


def test_ball_bounces_off_the_left_wall():
    state = BreakoutState(
        paddle_x=PLAY_LEFT, ball_x=PLAY_LEFT + BALL_RADIUS + 1, ball_y=200, ball_vx=-100, ball_vy=-50,
        bricks=[[False] * BRICK_COLS for _ in range(BRICK_ROWS)], bricks_remaining=0, last_update_time=1_000,
    )
    state.next_state(held(current_time=1_100))
    assert state.ball_vx > 0


def test_ball_bounces_off_the_right_wall():
    state = BreakoutState(
        paddle_x=PLAY_LEFT, ball_x=PLAY_RIGHT - BALL_RADIUS - 1, ball_y=200, ball_vx=100, ball_vy=-50,
        bricks=[[False] * BRICK_COLS for _ in range(BRICK_ROWS)], bricks_remaining=0, last_update_time=1_000,
    )
    state.next_state(held(current_time=1_100))
    assert state.ball_vx < 0


def test_ball_bounces_off_the_top_wall():
    state = BreakoutState(
        paddle_x=0, ball_x=400, ball_y=HUD_HEIGHT + BALL_RADIUS + 1, ball_vx=0, ball_vy=-100,
        bricks=[[False] * BRICK_COLS for _ in range(BRICK_ROWS)], bricks_remaining=0, last_update_time=1_000,
    )
    state.next_state(held(current_time=1_100))
    assert state.ball_vy > 0


def test_ball_bounces_off_the_paddle_and_center_hit_goes_straight_up():
    paddle_x = 300.0
    state = BreakoutState(
        paddle_x=paddle_x, ball_x=paddle_x + PADDLE_WIDTH / 2, ball_y=PADDLE_Y - BALL_RADIUS - 1,
        ball_vx=0, ball_vy=200,
        bricks=[[False] * BRICK_COLS for _ in range(BRICK_ROWS)], bricks_remaining=0, last_update_time=1_000,
    )
    state.next_state(held(current_time=1_010))
    assert state.ball_vy < 0
    assert state.ball_vx == 0


def test_ball_hitting_a_brick_removes_it_and_bounces():
    bricks = [[False] * BRICK_COLS for _ in range(BRICK_ROWS)]
    bricks[0][0] = True
    bricks[0][1] = True  # a second brick left standing so this hit doesn't also win the game
    from breakout.game import _brick_rect
    rect = _brick_rect(0, 0)
    state = BreakoutState(
        paddle_x=0, ball_x=rect.centerx, ball_y=rect.bottom + BALL_RADIUS - 1, ball_vx=0, ball_vy=-50,
        bricks=bricks, bricks_remaining=2, last_update_time=1_000,
    )
    result = state.next_state(held(current_time=1_010))
    assert result is state
    assert state.bricks[0][0] is False
    assert state.bricks_remaining == 1
    assert state.ball_vy > 0


def test_clearing_the_last_brick_wins_after_a_delay_to_admire_the_face():
    bricks = [[False] * BRICK_COLS for _ in range(BRICK_ROWS)]
    bricks[0][0] = True
    from breakout.game import _brick_rect
    rect = _brick_rect(0, 0)
    state = BreakoutState(
        paddle_x=0, ball_x=rect.centerx, ball_y=rect.bottom + BALL_RADIUS - 1, ball_vx=0, ball_vy=-50,
        bricks=bricks, bricks_remaining=1, last_update_time=1_000,
    )
    result = state.next_state(held(current_time=1_010))
    assert result is state  # board stays up, showing the fully revealed face
    assert state.pending_result is not None
    assert state.pending_result.won is True
    assert state.pending_result.bricks_hit == TOTAL_BRICKS

    still_showing = state.next_state(held(current_time=1_010 + GAME_OVER_DELAY_MS - 1))
    assert still_showing is state

    result = state.next_state(held(current_time=1_010 + GAME_OVER_DELAY_MS))
    assert isinstance(result, BreakoutResultScreen)
    assert result.won is True
    assert result.bricks_hit == TOTAL_BRICKS


def test_missing_the_ball_costs_a_life_and_starts_the_serve_delay():
    state = BreakoutState(
        paddle_x=300, ball_x=400, ball_y=CANVAS_HEIGHT - 5, ball_vx=0, ball_vy=200,
        bricks=[[False] * BRICK_COLS for _ in range(BRICK_ROWS)], bricks_remaining=5,
        lives=STARTING_LIVES, last_update_time=1_000,
    )
    result = state.next_state(held(current_time=1_100))
    assert result is state
    assert state.lives == STARTING_LIVES - 1
    assert state.serve_at == 1_100 + SERVE_DELAY_MS


def test_a_new_ball_stays_hidden_until_the_serve_delay_elapses_then_serves():
    state = BreakoutState(
        paddle_x=300, ball_x=400, ball_y=CANVAS_HEIGHT - 5, ball_vx=0, ball_vy=200,
        bricks=[[False] * BRICK_COLS for _ in range(BRICK_ROWS)], bricks_remaining=5,
        lives=STARTING_LIVES, last_update_time=1_000,
    )
    state.next_state(held(current_time=1_100))  # loses a life, starts the delay

    still_waiting = state.next_state(held(current_time=1_100 + SERVE_DELAY_MS - 1))
    assert still_waiting is state
    assert state.serve_at is not None

    state.next_state(held(current_time=1_100 + SERVE_DELAY_MS))
    assert state.serve_at is None
    assert state.ball_y < CANVAS_HEIGHT  # served fresh, back above the paddle


def test_paddle_still_moves_during_the_serve_delay():
    state = BreakoutState(
        paddle_x=300, ball_x=400, ball_y=CANVAS_HEIGHT - 5, ball_vx=0, ball_vy=200,
        bricks=[[False] * BRICK_COLS for _ in range(BRICK_ROWS)], bricks_remaining=5,
        lives=STARTING_LIVES, last_update_time=1_000,
    )
    state.next_state(held(current_time=1_100))  # loses a life, starts the delay
    state.next_state(held(YELLOW, current_time=1_150))
    assert state.paddle_x > 300


def test_missing_the_ball_on_the_last_life_ends_the_game_after_a_delay():
    state = BreakoutState(
        paddle_x=300, ball_x=400, ball_y=CANVAS_HEIGHT - 5, ball_vx=0, ball_vy=200,
        bricks=[[False] * BRICK_COLS for _ in range(BRICK_ROWS)], bricks_remaining=5,
        lives=1, last_update_time=1_000,
    )
    result = state.next_state(held(current_time=1_100))
    assert result is state  # board stays up for a moment rather than cutting straight away
    assert state.pending_result is not None
    assert state.pending_result.won is False
    assert state.pending_result.bricks_hit == TOTAL_BRICKS - 5

    result = state.next_state(held(current_time=1_100 + GAME_OVER_DELAY_MS))
    assert isinstance(result, BreakoutResultScreen)
    assert result.won is False
    assert result.bricks_hit == TOTAL_BRICKS - 5


def test_big_red_button_returns_to_menu():
    state = new_breakout()
    sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, True)
    try:
        result = state.next_state(release())
    finally:
        sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, False)
    assert result is None


def test_result_screen_ignores_the_confirm_press_still_held_then_exits_on_the_next_one():
    state = BreakoutResultScreen(won=False, bricks_hit=12)
    still_held = state.next_state(press(BLUE))
    assert isinstance(still_held, BreakoutResultScreen)
    armed = still_held.next_state(release())
    assert isinstance(armed, BreakoutResultScreen)
    assert armed.next_state(press(RED)) is None


def test_result_screen_green_starts_a_new_game():
    state = BreakoutResultScreen(won=True, bricks_hit=TOTAL_BRICKS, ready=True)
    new_state = state.next_state(press(GREEN))
    assert isinstance(new_state, BreakoutState)
    assert new_state.lives == STARTING_LIVES


def test_result_screen_ignores_other_buttons():
    state = BreakoutResultScreen(won=False, bricks_hit=12, ready=True)
    assert isinstance(state.next_state(press(YELLOW)), BreakoutResultScreen)

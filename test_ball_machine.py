"""Drives the Ball Machine continuous state directly, the same way test_tetris.py
exercises Tetris. Never calls draw().
"""

from math import pi

import sim_gpio
from ball_machine.game import (
    DEFAULT_AZIMUTH,
    DEFAULT_ELEVATION,
    ELEVATION_MAX,
    ELEVATION_MIN,
    BallMachineState,
    new_ball_machine,
)
from common import Input
from hardware import BIG_RED_BUTTON_PIN, buttons_in_order


def held(*indices: int, current_time: int) -> Input:
    for i, button in enumerate(buttons_in_order):
        sim_gpio.set_input_state(button.switch_pin, i in indices)
    return Input(buttons_in_order, current_time=current_time)


def release(current_time: int = 0) -> Input:
    return held(current_time=current_time)


# Button order is Red, Green, Blue, Yellow, White.
RED, GREEN, BLUE, YELLOW, WHITE = 0, 1, 2, 3, 4


def test_new_ball_machine_starts_at_the_default_view():
    state = new_ball_machine()
    assert state.azimuth == DEFAULT_AZIMUTH
    assert state.elevation == DEFAULT_ELEVATION


def test_holding_blue_rotates_the_camera_right_over_time():
    state = new_ball_machine()
    state.next_state(held(BLUE, current_time=0))
    result = state.next_state(held(BLUE, current_time=1000))
    assert result is state
    assert state.azimuth > DEFAULT_AZIMUTH


def test_holding_red_rotates_the_camera_left_over_time():
    state = new_ball_machine()
    state.next_state(held(RED, current_time=0))
    state.next_state(held(RED, current_time=100))  # small enough not to wrap past zero
    assert state.azimuth < DEFAULT_AZIMUTH


def test_azimuth_wraps_within_a_full_turn():
    state = new_ball_machine()
    state.next_state(held(BLUE, current_time=0))
    state.next_state(held(BLUE, current_time=1_000_000))
    assert 0 <= state.azimuth < 2 * pi


def test_holding_green_tilts_up_and_clamps():
    state = new_ball_machine()
    state.next_state(held(GREEN, current_time=0))
    state.next_state(held(GREEN, current_time=1_000_000))
    assert state.elevation == ELEVATION_MAX


def test_holding_yellow_tilts_down_and_clamps():
    state = new_ball_machine()
    state.next_state(held(YELLOW, current_time=0))
    state.next_state(held(YELLOW, current_time=1_000_000))
    assert state.elevation == ELEVATION_MIN


def test_holding_both_rotate_buttons_cancels_out():
    state = new_ball_machine()
    state.next_state(held(RED, BLUE, current_time=0))
    state.next_state(held(RED, BLUE, current_time=1000))
    assert state.azimuth == DEFAULT_AZIMUTH


def test_white_resets_the_view():
    state = BallMachineState(azimuth=1.2, elevation=-0.8)
    result = state.next_state(held(WHITE, current_time=0))
    assert result is state
    assert state.azimuth == DEFAULT_AZIMUTH
    assert state.elevation == DEFAULT_ELEVATION


def test_white_reset_only_fires_on_the_press_edge():
    state = BallMachineState(azimuth=1.2, elevation=-0.8)
    state.next_state(held(WHITE, current_time=0))
    state.azimuth = 1.2  # nudge it away again while White is still held
    state.next_state(held(WHITE, current_time=16))
    assert state.azimuth == 1.2  # unchanged -- reset shouldn't repeat while held


def test_big_red_returns_to_the_menu():
    state = new_ball_machine()
    sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, True)
    try:
        result = state.next_state(release(current_time=1000))
    finally:
        sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, False)
    assert result is None

"""Drives the Tower Defense Duo continuous state directly, the same way
test_tetris.py exercises Tetris. Never calls draw().
"""

import sim_gpio
from common import Input
from hardware import BIG_RED_BUTTON_PIN, Color, buttons, buttons_in_order
from tower_defense.game import (
    ENEMY_START_X,
    LANES,
    STARTING_LIVES,
    TOWER_X,
    Enemy,
    RulesScreen,
    TowerDefenseResultScreen,
    TowerDefenseState,
    new_tower_defense,
    new_tower_defense_with_rules,
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


def test_new_tower_defense_with_rules_starts_on_the_rules_screen():
    state = new_tower_defense_with_rules()
    assert isinstance(state, RulesScreen)


def test_rules_screen_advances_to_the_game_on_any_press():
    state = RulesScreen()
    result = state.next_state(press(BLUE))
    assert isinstance(result, TowerDefenseState)


def test_rules_screen_big_red_button_returns_to_menu():
    state = RulesScreen()
    sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, True)
    try:
        result = state.next_state(release())
    finally:
        sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, False)
    assert result is None


def test_new_tower_defense_starts_with_empty_lanes_full_lives_and_zero_score():
    state = new_tower_defense()
    assert state.lanes == [None] * LANES
    assert state.lives == STARTING_LIVES
    assert state.score == 0
    assert state.current_lane == LANES // 2


def test_first_frame_just_anchors_the_clock_and_does_not_move_anything():
    state = new_tower_defense()
    result = state.next_state(held(current_time=1_000))
    assert result is state
    assert state.lanes == [None] * LANES


def test_red_and_green_move_the_aim_one_lane_at_a_time():
    state = new_tower_defense()
    state.next_state(held(current_time=1_000))  # burn the anchor frame

    state.next_state(held(RED, current_time=1_050))
    assert state.current_lane == LANES // 2 - 1

    state.next_state(release())
    state.next_state(held(GREEN, current_time=1_100))
    assert state.current_lane == LANES // 2

    state.next_state(release())
    state.next_state(held(GREEN, current_time=1_150))
    assert state.current_lane == LANES // 2 + 1


def test_aim_is_clamped_within_the_lanes():
    state = new_tower_defense()
    state.next_state(held(current_time=1_000))

    t = 1_050
    for _ in range(10):
        state.next_state(held(RED, current_time=t))
        state.next_state(release())
        t += 10
    assert state.current_lane == 0

    for _ in range(10):
        state.next_state(held(GREEN, current_time=t))
        state.next_state(release())
        t += 10
    assert state.current_lane == LANES - 1


def test_holding_red_only_moves_the_aim_once():
    state = new_tower_defense()
    state.next_state(held(current_time=1_000))
    starting_lane = state.current_lane

    state.next_state(held(RED, current_time=1_050))
    assert state.current_lane == starting_lane - 1

    state.next_state(held(RED, current_time=1_100))
    assert state.current_lane == starting_lane - 1  # still held, no repeat


def test_correct_answer_kills_the_aimed_enemy_and_scores():
    state = new_tower_defense()
    state.next_state(held(current_time=1_000))
    state.lanes[state.current_lane] = Enemy(x=500, text="3 + 4", correct_answer=7, choices=[7, 3, 9])

    state.next_state(held(BLUE, current_time=1_050))
    assert state.lanes[state.current_lane] is None
    assert state.score == 1


def test_wrong_answer_does_nothing():
    state = new_tower_defense()
    state.next_state(held(current_time=1_000))
    state.lanes[state.current_lane] = Enemy(x=500, text="3 + 4", correct_answer=7, choices=[7, 3, 9])

    state.next_state(held(YELLOW, current_time=1_050))
    assert state.lanes[state.current_lane] is not None
    assert state.score == 0


def test_answering_an_empty_lane_does_nothing():
    state = new_tower_defense()
    state.next_state(held(current_time=1_000))
    assert state.lanes[state.current_lane] is None

    result = state.next_state(held(BLUE, current_time=1_050))
    assert result is state
    assert state.score == 0


def test_an_enemy_reaching_the_tower_costs_a_life_and_repeats_its_problem():
    state = new_tower_defense()
    state.next_state(held(current_time=1_000))
    lane = 0
    state.lanes[lane] = Enemy(x=TOWER_X + 1, text="1 + 1", correct_answer=2, choices=[2, 1, 3])

    result = state.next_state(held(current_time=1_500))
    assert result is state
    assert state.lanes[lane] is not None
    assert state.lanes[lane].text == "1 + 1"
    assert state.lanes[lane].correct_answer == 2
    assert state.lanes[lane].x == ENEMY_START_X
    assert state.lives == STARTING_LIVES - 1


def test_losing_the_last_life_ends_the_game():
    state = new_tower_defense()
    state.next_state(held(current_time=1_000))
    state.lives = 1
    state.lanes[0] = Enemy(x=TOWER_X + 1, text="1 + 1", correct_answer=2, choices=[2, 1, 3])

    result = state.next_state(held(current_time=1_500))
    assert isinstance(result, TowerDefenseResultScreen)
    assert result.score == state.score


def test_control_leds_turn_off_when_the_game_ends():
    state = new_tower_defense()
    state.next_state(held(current_time=1_000))
    state.lives = 1
    state.lanes[0] = Enemy(x=TOWER_X + 1, text="1 + 1", correct_answer=2, choices=[2, 1, 3])

    state.next_state(held(current_time=1_500))
    for color in Color:
        assert sim_gpio.get_output_state(buttons[color].led_pin) is False


def test_big_red_button_returns_to_menu():
    state = new_tower_defense()
    sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, True)
    try:
        result = state.next_state(release())
    finally:
        sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, False)
    assert result is None


def test_result_screen_ignores_the_confirm_press_still_held_then_exits_on_the_next_one():
    state = TowerDefenseResultScreen(score=12)
    still_held = state.next_state(press(BLUE))
    assert isinstance(still_held, TowerDefenseResultScreen)
    armed = still_held.next_state(release())
    assert isinstance(armed, TowerDefenseResultScreen)
    assert armed.next_state(press(RED)) is None


def test_result_screen_green_starts_a_new_game():
    state = TowerDefenseResultScreen(score=12, ready=True)
    new_state = state.next_state(press(GREEN))
    assert isinstance(new_state, TowerDefenseState)
    assert new_state.score == 0


def test_result_screen_ignores_other_buttons():
    state = TowerDefenseResultScreen(score=12, ready=True)
    assert isinstance(state.next_state(press(YELLOW)), TowerDefenseResultScreen)

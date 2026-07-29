"""Drives the Space Invaders continuous state directly, the same way
test_breakout.py exercises Breakout. Never calls draw().
"""

import sim_gpio
from common import Input
from hardware import BIG_RED_BUTTON_PIN, Color, buttons, buttons_in_order
from space_invaders.game import (
    CANVAS_HEIGHT,
    ENEMY_COLS,
    ENEMY_ROWS,
    HUD_HEIGHT,
    PLAY_LEFT,
    PLAY_RIGHT,
    PLAYER_WIDTH,
    PLAYER_Y,
    RESPAWN_DELAY_MS,
    STARTING_LIVES,
    TOTAL_ENEMIES,
    RulesScreen,
    SpaceInvadersResultScreen,
    SpaceInvadersState,
    _enemy_rect,
    new_space_invaders,
    new_space_invaders_with_rules,
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


def ticking(state: SpaceInvadersState) -> SpaceInvadersState:
    """The first next_state call only anchors last_update_time (dt would
    otherwise be however long it took to get here) -- burn that frame."""
    result = state.next_state(held(current_time=1_000))
    assert result is state
    return state


def test_new_space_invaders_with_rules_starts_on_the_rules_screen():
    state = new_space_invaders_with_rules()
    assert isinstance(state, RulesScreen)


def test_rules_screen_advances_to_the_game_on_any_press():
    state = RulesScreen()
    result = state.next_state(press(BLUE))
    assert isinstance(result, SpaceInvadersState)


def test_rules_screen_big_red_button_returns_to_menu():
    state = RulesScreen()
    sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, True)
    try:
        result = state.next_state(release())
    finally:
        sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, False)
    assert result is None


def test_new_space_invaders_starts_with_a_full_grid_and_lives_and_a_centered_ship():
    state = new_space_invaders()
    assert state.lives == STARTING_LIVES
    assert state.enemies_remaining == TOTAL_ENEMIES == ENEMY_ROWS * ENEMY_COLS
    assert all(all(row) for row in state.enemies)
    assert state.player_x == PLAY_LEFT + (PLAY_RIGHT - PLAY_LEFT - PLAYER_WIDTH) / 2


def test_player_moves_left_and_right():
    state = ticking(new_space_invaders())
    start_x = state.player_x
    state.next_state(held(BLUE, current_time=1_100))
    assert state.player_x > start_x

    mid_x = state.player_x
    state.next_state(held(RED, current_time=1_200))
    assert state.player_x < mid_x


def test_player_is_clamped_within_the_play_area():
    state = ticking(new_space_invaders())
    for t in range(1_100, 5_000, 100):
        state.next_state(held(RED, current_time=t))
    assert state.player_x == PLAY_LEFT

    for t in range(5_100, 9_000, 100):
        state.next_state(held(BLUE, current_time=t))
    assert state.player_x == PLAY_RIGHT - PLAYER_WIDTH


def test_green_fires_a_bullet_that_travels_up():
    state = ticking(new_space_invaders())
    state.next_state(held(GREEN, current_time=1_100))
    assert state.player_bullet is not None
    y_after_first_shot = state.player_bullet[1]

    state.next_state(held(current_time=1_200))
    assert state.player_bullet[1] < y_after_first_shot


def test_only_one_player_bullet_at_a_time():
    state = ticking(new_space_invaders())
    state.next_state(held(GREEN, current_time=1_100))
    first_bullet = state.player_bullet
    state.next_state(held(GREEN, current_time=1_150))
    assert state.player_bullet is first_bullet


def test_bullet_hitting_an_enemy_removes_it_and_scores():
    state = ticking(new_space_invaders())
    rect = _enemy_rect(0, 0, state.enemy_offset_x, state.enemy_offset_y)
    state.player_bullet = [rect.centerx, rect.bottom - 1]

    # +10ms: enough for a tick, small enough the bullet is still overlapping
    # the brick it was placed against rather than sailing past it.
    result = state.next_state(held(current_time=1_010))
    assert result is state
    assert state.enemies[0][0] is False
    assert state.enemies_remaining == TOTAL_ENEMIES - 1
    assert state.score == 1
    assert state.player_bullet is None


def test_clearing_every_enemy_wins():
    enemies = [[False] * ENEMY_COLS for _ in range(ENEMY_ROWS)]
    enemies[0][0] = True
    state = SpaceInvadersState(
        player_x=300, enemies=enemies, enemies_remaining=1, last_update_time=1_000,
    )
    rect = _enemy_rect(0, 0, state.enemy_offset_x, state.enemy_offset_y)
    state.player_bullet = [rect.centerx, rect.bottom - 1]

    result = state.next_state(held(current_time=1_010))
    assert isinstance(result, SpaceInvadersResultScreen)
    assert result.won is True
    assert result.score == 1


def test_enemy_reaching_the_danger_line_ends_the_game():
    state = SpaceInvadersState(
        player_x=300,
        enemies=[[True] * ENEMY_COLS for _ in range(ENEMY_ROWS)],
        enemies_remaining=TOTAL_ENEMIES,
        enemy_offset_y=CANVAS_HEIGHT,  # formation already reached the ship
        last_update_time=1_000,
    )
    result = state.next_state(held(current_time=1_100))
    assert isinstance(result, SpaceInvadersResultScreen)
    assert result.won is False


def test_enemy_bullet_hitting_the_player_costs_a_life_and_starts_the_respawn_delay():
    state = SpaceInvadersState(
        player_x=300,
        enemies=[[False] * ENEMY_COLS for _ in range(ENEMY_ROWS)],
        enemies_remaining=0,
        enemy_bullets=[[300 + PLAYER_WIDTH / 2, PLAYER_Y - 1]],
        lives=STARTING_LIVES,
        last_update_time=1_000,
    )
    # A single enemy left standing so clearing the board doesn't also win the
    # game before the hit is processed.
    state.enemies[0][0] = True
    state.enemies_remaining = 1

    # +10ms: enough for a tick, small enough the bullet is still overlapping
    # the player it was placed against rather than sailing past it.
    result = state.next_state(held(current_time=1_010))
    assert result is state
    assert state.lives == STARTING_LIVES - 1
    assert state.enemy_bullets == []
    assert state.respawn_at == 1_010 + RESPAWN_DELAY_MS


def test_enemies_pause_during_the_respawn_delay_then_resume():
    state = SpaceInvadersState(
        player_x=300,
        enemies=[[True] * ENEMY_COLS for _ in range(ENEMY_ROWS)],
        enemies_remaining=TOTAL_ENEMIES,
        enemy_bullets=[[300 + PLAYER_WIDTH / 2, PLAYER_Y - 1]],
        lives=STARTING_LIVES,
        last_update_time=1_000,
    )
    state.next_state(held(current_time=1_010))  # loses a life, starts the delay
    assert state.respawn_at == 1_010 + RESPAWN_DELAY_MS
    offset_x_at_hit = state.enemy_offset_x

    still_waiting = state.next_state(held(current_time=1_010 + RESPAWN_DELAY_MS - 1))
    assert still_waiting is state
    assert state.enemy_offset_x == offset_x_at_hit  # formation frozen
    assert state.respawn_at is not None

    state.next_state(held(current_time=1_010 + RESPAWN_DELAY_MS))
    assert state.respawn_at is None

    state.next_state(held(current_time=1_010 + RESPAWN_DELAY_MS + 100))
    assert state.enemy_offset_x != offset_x_at_hit  # formation moving again


def test_losing_the_last_life_ends_the_game():
    state = SpaceInvadersState(
        player_x=300,
        enemies=[[True] * ENEMY_COLS for _ in range(ENEMY_ROWS)],
        enemies_remaining=TOTAL_ENEMIES,
        enemy_bullets=[[300 + PLAYER_WIDTH / 2, PLAYER_Y - 1]],
        lives=1,
        last_update_time=1_000,
    )
    result = state.next_state(held(current_time=1_010))
    assert isinstance(result, SpaceInvadersResultScreen)
    assert result.won is False


def test_control_leds_turn_off_when_the_game_ends():
    enemies = [[False] * ENEMY_COLS for _ in range(ENEMY_ROWS)]
    enemies[0][0] = True
    state = SpaceInvadersState(
        player_x=300, enemies=enemies, enemies_remaining=1,
        enemy_bullets=[[300 + PLAYER_WIDTH / 2, PLAYER_Y - 1]],
        lives=1, last_update_time=1_000,
    )
    state.next_state(held(current_time=1_010))
    assert sim_gpio.get_output_state(buttons[Color.RED].led_pin) is False
    assert sim_gpio.get_output_state(buttons[Color.GREEN].led_pin) is False
    assert sim_gpio.get_output_state(buttons[Color.BLUE].led_pin) is False


def test_big_red_button_returns_to_menu():
    state = new_space_invaders()
    sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, True)
    try:
        result = state.next_state(release())
    finally:
        sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, False)
    assert result is None


def test_result_screen_ignores_the_confirm_press_still_held_then_exits_on_the_next_one():
    state = SpaceInvadersResultScreen(won=False, score=12)
    still_held = state.next_state(press(BLUE))
    assert isinstance(still_held, SpaceInvadersResultScreen)
    armed = still_held.next_state(release())
    assert isinstance(armed, SpaceInvadersResultScreen)
    assert armed.next_state(press(RED)) is None


def test_result_screen_green_starts_a_new_game():
    state = SpaceInvadersResultScreen(won=True, score=TOTAL_ENEMIES, ready=True)
    new_state = state.next_state(press(GREEN))
    assert isinstance(new_state, SpaceInvadersState)
    assert new_state.lives == STARTING_LIVES


def test_result_screen_ignores_other_buttons():
    state = SpaceInvadersResultScreen(won=False, score=12, ready=True)
    assert isinstance(state.next_state(press(YELLOW)), SpaceInvadersResultScreen)

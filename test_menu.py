"""Walks the menu state machine directly, driving the real Button objects through
the simulator's GPIO backend -- exactly how the driver feeds input in --simulator
mode. Never calls draw(), so pygame's font/display subsystems stay uninitialized;
this is pure navigation logic.

conftest.py sets SIMULATOR=1, so hardware.buttons_in_order are wired to sim_gpio,
and set_input_state below is the same hook the driver's mouse/keyboard handling
uses to press them."""

import sim_gpio
from common import GetReadyScreen, Input
from hardware import buttons_in_order
import menu
from menu import MenuState
from quiz.game import AskingQuestionState


def press(*indices: int) -> Input:
    """An Input with exactly the buttons at the given left-to-right indices held."""
    for i, button in enumerate(buttons_in_order):
        sim_gpio.set_input_state(button.switch_pin, i in indices)
    return Input(buttons_in_order, current_time=0)


def release() -> Input:
    return press()  # no indices held


def options(state: MenuState) -> list[str]:
    return state._options_picker().options


def click(state: MenuState, index: int) -> MenuState:
    """One full press-then-release of a single paging button, as a real tap would
    land across two frames. Asserts we stay in the menu and returns that state."""
    pressed = state.next_state(press(index))
    assert isinstance(pressed, MenuState)
    released = pressed.next_state(release())
    assert isinstance(released, MenuState)
    return released


# These tests assume seven games across three pages of three. If the roster
# changes so the menu stops paginating, that's a different design and these
# pagination tests should be revisited.
def test_roster_is_paginated():
    assert len(menu.all_games) == 7
    assert MenuState()._paginated()


def test_first_page_shows_three_games_between_arrows():
    assert options(MenuState()) == ["<", "Color Easy", "Color Medium", "Color Hard", ">"]


def test_next_advances_exactly_one_page():
    # Regression: a held "next" used to race through pages and clamp on the last
    # one, so a single tap jumped straight past the middle page.
    page1 = click(MenuState(), 4)  # rightmost button = ">"
    assert page1.page == 1
    assert options(page1) == ["<", "Capitals HARD", "Capitals", "Sports", ">"]


def test_next_twice_reaches_last_page():
    state = click(click(MenuState(), 4), 4)
    assert state.page == 2
    assert options(state) == ["<", "Jeopardy!", ">"]


def test_next_clamps_on_last_page():
    state = click(click(click(MenuState(), 4), 4), 4)
    assert state.page == 2


def test_prev_goes_back_and_clamps_at_zero():
    state = click(click(MenuState(), 4), 4)  # to page 2
    state = click(state, 0)                  # leftmost button = "<"
    assert state.page == 1
    state = click(click(state, 0), 0)        # back to 0, then try to go past it
    assert state.page == 0


def test_holding_next_does_not_skip_pages():
    # The same physical button held down across many frames without release.
    state = MenuState().next_state(press(4))
    assert isinstance(state, MenuState)
    assert state.page == 1
    for _ in range(10):
        nxt = state.next_state(press(4))
        assert isinstance(nxt, MenuState)
        state = nxt
    assert state.page == 1  # still one page in, not clamped at the end


def test_selecting_a_game_starts_it_via_get_ready():
    # Middle button on page 1 maps to "Capitals" (prev, g, g, g, next -> index 2).
    page1 = click(MenuState(), 4)
    result = page1.next_state(press(2))
    assert isinstance(result, GetReadyScreen)

    # GetReadyScreen builds the chosen game once buttons are released.
    started = result.next_state(release())
    assert isinstance(started, AskingQuestionState)


def test_arrow_button_does_not_start_a_game():
    # Pressing "<" on page 0 keeps us in the menu (not a GetReadyScreen), at page 0.
    pressed = MenuState().next_state(press(0))
    assert isinstance(pressed, MenuState)
    assert pressed.page == 0

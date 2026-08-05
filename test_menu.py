"""Walks the menu state machine directly, driving the real Button objects through
the simulator's GPIO backend -- exactly how the driver feeds input in --simulator
mode. Never calls draw(), so pygame's font/display subsystems stay uninitialized;
this is pure navigation logic.

conftest.py sets SIMULATOR=1, so hardware.buttons_in_order are wired to sim_gpio,
and set_input_state below is the same hook the driver's mouse/keyboard handling
uses to press them."""

import menu
import sim_gpio
from common import GetReadyScreen, Input
from hardware import BIG_RED_BUTTON_PIN, buttons_in_order
from menu import CategoryMenuState, GameMenuState
from quiz.game import AskingQuestionState


def led_states(state) -> list[bool]:
    state.next_state(release())
    return [sim_gpio.get_output_state(button.led_pin) for button in buttons_in_order]


def press(*indices: int) -> Input:
    """An Input with exactly the buttons at the given left-to-right indices held."""
    for i, button in enumerate(buttons_in_order):
        sim_gpio.set_input_state(button.switch_pin, i in indices)
    return Input(buttons_in_order, current_time=0)


def release() -> Input:
    return press()  # no indices held


def options(state) -> list[str]:
    return state._options_picker().options


def click(state, index: int):
    """One full press-then-release of a single paging button, as a real tap would
    land across two frames. Asserts we stay in the given state's type and returns it."""
    state_type = type(state)
    pressed = state.next_state(press(index))
    assert isinstance(pressed, state_type)
    released = pressed.next_state(release())
    assert isinstance(released, state_type)
    return released


def quiz_games_menu() -> GameMenuState:
    result = CategoryMenuState().next_state(press(0))
    assert isinstance(result, GameMenuState)
    released = result.next_state(release())
    assert isinstance(released, GameMenuState)
    return released


def arcade_games_menu() -> GameMenuState:
    result = CategoryMenuState().next_state(press(1))
    assert isinstance(result, GameMenuState)
    released = result.next_state(release())
    assert isinstance(released, GameMenuState)
    return released


# These tests assume two categories: fourteen Quiz Games across four full
# pages of three plus a final page of two, and eight Arcade Games across two
# full pages plus a final page of two. If the roster changes, these
# pagination tests should be revisited.
def test_categories_cover_every_game():
    assert [c.name for c in menu.categories] == ["Quiz Games", "Arcade Games"]
    assert len(menu.categories[0].games) == 14
    assert len(menu.categories[1].games) == 8


def test_category_menu_lists_the_categories():
    assert options(CategoryMenuState()) == ["Quiz Games", "Arcade Games"]


def test_category_menu_lights_only_the_categories():
    assert led_states(CategoryMenuState()) == [True, True, False, False, False]


def test_selecting_a_category_enters_its_game_menu():
    result = CategoryMenuState().next_state(press(0))
    assert isinstance(result, GameMenuState)
    assert result.category.name == "Quiz Games"

    result = CategoryMenuState().next_state(press(1))
    assert isinstance(result, GameMenuState)
    assert result.category.name == "Arcade Games"


def test_quiz_games_first_page_shows_three_games_between_arrows():
    assert options(quiz_games_menu()) == ["", "Color Easy", "Color Medium", "Color Hard", ">"]


def test_quiz_games_next_advances_exactly_one_page():
    # Regression: a held "next" used to race through pages and clamp on the last
    # one, so a single tap jumped straight past the middle page.
    page1 = click(quiz_games_menu(), 4)  # rightmost button = ">"
    assert page1.page == 1
    assert options(page1) == ["<", "Capitals HARD", "Capitals", "Sports", ">"]


def test_quiz_games_next_twice_reaches_a_middle_page():
    state = click(click(quiz_games_menu(), 4), 4)
    assert state.page == 2
    assert options(state) == ["<", "Jeopardy!", "Mastermind", "Chain Reaction", ">"]


def test_quiz_games_next_four_times_reaches_the_last_page():
    state = quiz_games_menu()
    for _ in range(4):
        state = click(state, 4)
    assert state.page == 4
    # Last page has only two games, so the right arrow slot is blank
    # rather than a live ">".
    assert options(state) == ["<", "Americas Flags", "Oceania Flags", ""]


def test_quiz_games_next_clamps_on_the_last_page():
    state = quiz_games_menu()
    for _ in range(6):  # two more presses than there are pages
        state = click(state, 4)
    assert state.page == 4


def test_quiz_games_prev_goes_back_and_clamps_at_zero():
    state = quiz_games_menu()
    for _ in range(4):
        state = click(state, 4)  # to the last page
    assert state.page == 4
    state = click(state, 0)     # leftmost button = "<"
    assert state.page == 3
    for _ in range(5):          # more presses than needed, should clamp at 0
        state = click(state, 0)
    assert state.page == 0


def test_quiz_games_holding_next_does_not_skip_pages():
    # The same physical button held down across many frames without release.
    state = quiz_games_menu().next_state(press(4))
    assert isinstance(state, GameMenuState)
    assert state.page == 1
    for _ in range(10):
        nxt = state.next_state(press(4))
        assert isinstance(nxt, GameMenuState)
        state = nxt
    assert state.page == 1  # still one page in, not clamped at the end


def test_arcade_games_last_page_holds_the_two_games_that_spilled_over():
    state = click(click(arcade_games_menu(), 4), 4)
    assert state.page == 2
    assert options(state) == ["<", "Tower Defense Duo", "Simon Says", ""]


def test_selecting_a_game_starts_it_via_get_ready():
    # Middle button on page 1 maps to "Capitals" (prev, g, g, g, next -> index 2).
    page1 = click(quiz_games_menu(), 4)
    result = page1.next_state(press(2))
    assert isinstance(result, GetReadyScreen)

    # GetReadyScreen builds the chosen game once buttons are released.
    started = result.next_state(release())
    assert isinstance(started, AskingQuestionState)


def test_quiz_games_first_page_lights_only_the_games_and_the_next_arrow():
    # ["", "Color Easy", "Color Medium", "Color Hard", ">"] -- blank "<" slot stays dark.
    assert led_states(quiz_games_menu()) == [False, True, True, True, True]


def test_quiz_games_middle_page_lights_all_five_slots():
    # ["<", "Jeopardy!", "Mastermind", "Chain Reaction", ">"] -- every slot is live.
    state = click(click(quiz_games_menu(), 4), 4)
    assert led_states(state) == [True, True, True, True, True]


def test_quiz_games_last_page_lights_the_prev_arrow_and_two_games():
    # ["<", "Flags: Americas", "Flags: Oceania", ""] -- blank ">" slot stays dark.
    state = quiz_games_menu()
    for _ in range(4):
        state = click(state, 4)
    assert led_states(state) == [True, True, True, False, False]


def test_arrow_button_does_not_start_a_game():
    # Pressing "<" on page 0 keeps us in the game menu (not a GetReadyScreen), at page 0.
    pressed = quiz_games_menu().next_state(press(0))
    assert isinstance(pressed, GameMenuState)
    assert pressed.page == 0


def test_big_red_button_steps_back_up_to_the_category_menu():
    state = quiz_games_menu()
    sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, True)
    try:
        result = state.next_state(release())
    finally:
        sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, False)
    assert isinstance(result, CategoryMenuState)

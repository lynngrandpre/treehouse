"""Drives the flags quiz state directly, the same way test_menu.py exercises
the menu -- pressing simulated buttons and asserting on the resulting state.
Never calls draw().
"""

import sim_gpio
from common import Input
from flags.data import CONTINENTS
from flags.game import (
    DONE,
    AskingQuestionState,
    FlagsResultScreen,
    RevealAnswer,
    new_flags_quiz,
)
from hardware import BIG_RED_BUTTON_PIN, buttons_in_order


def press(*indices: int) -> Input:
    """An Input with exactly the buttons at the given left-to-right indices held."""
    for i, button in enumerate(buttons_in_order):
        sim_gpio.set_input_state(button.switch_pin, i in indices)
    return Input(buttons_in_order, current_time=0)


def release() -> Input:
    return press()  # no indices held


def test_every_continent_has_at_least_five_countries_with_unique_names():
    for continent, countries in CONTINENTS.items():
        assert len(countries) >= 5
        names = [c.name for c in countries]
        assert len(names) == len(set(names)), f"duplicate country name in {continent}"


def test_new_flags_quiz_mixes_flag_and_capital_questions():
    state = new_flags_quiz("Europe")
    assert isinstance(state, AskingQuestionState)

    countries = CONTINENTS["Europe"]
    all_questions = state.score.remaining_questions
    assert len(all_questions) == len(countries) * 2
    assert sum(1 for q in all_questions if q.flag is not None) == len(countries)
    assert sum(1 for q in all_questions if q.flag is None) == len(countries)


def test_every_question_has_five_options_including_the_correct_one():
    state = new_flags_quiz("Africa")
    for q in state.score.remaining_questions:
        assert len(q.options) == 5
        assert len(set(q.options)) == 5  # no duplicate options
        assert 0 <= q.correct_index < 5


def test_capital_question_prompt_names_the_country():
    state = new_flags_quiz("Asia")
    capital_question = next(q for q in state.score.remaining_questions if q.flag is None)
    assert "capital" in capital_question.prompt.lower()
    assert any(country.name in capital_question.prompt for country in CONTINENTS["Asia"])


def test_correct_answer_advances_score_and_removes_the_question():
    state = new_flags_quiz("Americas")
    question = state.question
    correct_button = question.correct_index

    result = state.next_state(press(correct_button))
    assert isinstance(result, RevealAnswer)
    assert result.score.correct == 1
    assert question not in result.score.remaining_questions


def test_wrong_answer_advances_score_without_removing_the_question():
    state = new_flags_quiz("Oceania")
    question = state.question
    wrong_button = next(i for i in range(5) if i != question.correct_index)

    result = state.next_state(press(wrong_button))
    assert isinstance(result, RevealAnswer)
    assert result.score.wrong == 1
    assert question in result.score.remaining_questions


def test_five_wrong_answers_ends_the_game():
    state = new_flags_quiz("Africa")
    for _ in range(DONE):
        question = state.question
        wrong_button = next(i for i in range(5) if i != question.correct_index)
        reveal = state.next_state(press(wrong_button))
        assert isinstance(reveal, RevealAnswer)
        next_state = reveal.next_state(release())
        if isinstance(next_state, FlagsResultScreen):
            break
        state = next_state
    assert isinstance(next_state, FlagsResultScreen)
    assert next_state.score.wrong == DONE


def test_answering_every_question_correctly_wins():
    state = new_flags_quiz("Europe")
    while True:
        question = state.question
        reveal = state.next_state(press(question.correct_index))
        assert isinstance(reveal, RevealAnswer)
        next_state = reveal.next_state(release())
        if isinstance(next_state, FlagsResultScreen):
            break
        state = next_state
    assert len(next_state.score.remaining_questions) == 0


def test_big_red_button_ends_the_quiz_early():
    state = new_flags_quiz("Asia")
    sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, True)
    try:
        result = state.next_state(release())
    finally:
        sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, False)
    assert isinstance(result, FlagsResultScreen)


def test_result_screen_returns_to_menu_on_any_press():
    state = FlagsResultScreen(score=new_flags_quiz("Africa").score)
    assert state.next_state(release()) is state
    assert state.next_state(press(0)) is None

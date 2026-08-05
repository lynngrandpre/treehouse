"""Flags quiz: one game per continent, mixing two question types -- "which
country is this flag?" (drawn with pygame.draw, since there are no image
assets in this codebase) and "what is the capital of X?". Structurally a
sibling of quiz/game.py: same Score/AskingQuestionState/RevealAnswer/
ResultScreen shape, kept separate since this module owns its own drawing.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace

import pygame

from common import AnswerPicker, Input, State, draw_text, font
from hardware import big_red_button_pressed

from .data import CONTINENTS, Country, Flag

DONE = 5  # number of incorrect guesses to end the game

FLAG_RECT = pygame.Rect(300, 60, 200, 120)


def draw_flag(surface: pygame.Surface, flag: Flag) -> None:
    rect = FLAG_RECT
    pygame.draw.rect(surface, (0, 0, 0), rect.inflate(4, 4))

    n = len(flag.stripes)
    for i, color in enumerate(flag.stripes):
        if flag.orientation == "vertical":
            width = rect.width // n
            stripe_rect = pygame.Rect(rect.x + i * width, rect.y, width, rect.height)
        else:
            height = rect.height // n
            stripe_rect = pygame.Rect(rect.x, rect.y + i * height, rect.width, height)
        pygame.draw.rect(surface, color, stripe_rect)

    if flag.canton is not None:
        canton_rect = pygame.Rect(rect.x, rect.y, rect.width * 2 // 5, rect.height // 2)
        pygame.draw.rect(surface, flag.canton, canton_rect)

    if flag.circle is not None:
        pygame.draw.circle(surface, flag.circle, rect.center, rect.height // 4)


@dataclass
class FlagQuestion:
    prompt: str  # shown as text; empty when a flag is drawn instead
    flag: Flag | None
    options: list[str]
    correct_index: int

    def answer_picker(self, reveal_answer: bool) -> AnswerPicker[bool]:
        options = self.options
        if reveal_answer:
            options = ["" if i != self.correct_index else o for i, o in enumerate(self.options)]

        return AnswerPicker(
            options,
            [i == self.correct_index for i in range(len(self.options))]
        )


@dataclass
class Score:
    correct: int
    wrong: int
    remaining_questions: list[FlagQuestion]

    def question_answered(self, correct: bool, question: FlagQuestion) -> Score:
        if correct:
            return replace(
                self,
                correct=self.correct + 1,
                remaining_questions=[q for q in self.remaining_questions if q != question]
            )
        else:
            return replace(self, wrong=self.wrong + 1)

    def random_question(self) -> FlagQuestion:
        return random.choice(self.remaining_questions)


@dataclass
class FlagsResultScreen:
    score: Score

    def draw(self, surface: pygame.Surface) -> None:
        CANVAS_WIDTH, CANVAS_HEIGHT = surface.get_size()

        if len(self.score.remaining_questions) == 0:
            draw_text(surface, font(60), "You Win", (CANVAS_WIDTH // 2, CANVAS_HEIGHT // 2))
            draw_text(surface, font(60), f"Mistakes: {self.score.wrong}", (CANVAS_WIDTH // 2, CANVAS_HEIGHT // 2 + 50))
        else:
            draw_text(surface, font(60), "You Lose :(", (CANVAS_WIDTH // 2, CANVAS_HEIGHT // 2))
            draw_text(surface, font(60), f"Correct: {self.score.correct}", (CANVAS_WIDTH // 2, CANVAS_HEIGHT // 2 + 50))

    def next_state(self, input: Input) -> State | None:
        pressed_buttons = [button for button in input.buttons if button.is_pressed()]

        if len(pressed_buttons) > 0:
            return None  # back to the menu
        else:
            return self


def draw_prompt(surface: pygame.Surface, question: FlagQuestion) -> None:
    CANVAS_WIDTH, CANVAS_HEIGHT = surface.get_size()

    if question.flag is not None:
        draw_flag(surface, question.flag)
        draw_text(surface, font(30), "Which country is this?", (CANVAS_WIDTH // 2, 220))
    else:
        draw_text(surface, font(40), question.prompt, (CANVAS_WIDTH // 2, 140))


@dataclass
class RevealAnswer:
    question: FlagQuestion
    score: Score

    def draw(self, surface: pygame.Surface) -> None:
        CANVAS_WIDTH, CANVAS_HEIGHT = surface.get_size()

        draw_prompt(surface, self.question)

        self.question.answer_picker(True).draw(surface)

        draw_text(surface, font(30), f"Correct {self.score.correct}", (CANVAS_WIDTH - 100, 50))
        draw_text(surface, font(30), f"Wrong   {self.score.wrong}", (CANVAS_WIDTH - 100, 80))

    def next_state(self, input: Input) -> State | None:
        if big_red_button_pressed():
            return FlagsResultScreen(replace(self.score, remaining_questions=[]))

        pressed_buttons = [button for button in input.buttons if button.is_pressed()]

        if len(pressed_buttons) == 0:
            if len(self.score.remaining_questions) == 0:
                return FlagsResultScreen(self.score)
            elif self.score.wrong == DONE:
                return FlagsResultScreen(self.score)
            else:
                return AskingQuestionState(
                    question=self.score.random_question(),
                    score=self.score
                )
        else:
            return self


@dataclass
class AskingQuestionState:
    question: FlagQuestion
    score: Score

    def draw(self, surface: pygame.Surface) -> None:
        CANVAS_WIDTH, CANVAS_HEIGHT = surface.get_size()

        draw_prompt(surface, self.question)

        self.question.answer_picker(False).draw(surface)

        draw_text(surface, font(30), f"Correct {self.score.correct}", (CANVAS_WIDTH - 100, 50))
        draw_text(surface, font(30), f"Wrong   {self.score.wrong}", (CANVAS_WIDTH - 100, 80))

    def next_state(self, input: Input) -> State | None:
        if big_red_button_pressed():
            return FlagsResultScreen(replace(self.score, remaining_questions=[]))

        correct = self.question.answer_picker(False).selection(input)
        if correct is None:
            return self

        new_score = self.score.question_answered(correct, self.question)

        return RevealAnswer(
            question=self.question,
            score=new_score
        )


def _flag_questions(countries: list[Country]) -> list[FlagQuestion]:
    qs = []
    for country in countries:
        others = [c.name for c in countries if c.name != country.name]
        options = random.sample(others, 4)
        correct_index = random.randint(0, 4)
        options = options[:correct_index] + [country.name] + options[correct_index:]
        qs.append(FlagQuestion(prompt="", flag=country.flag, options=options, correct_index=correct_index))
    return qs


def _capital_questions(countries: list[Country]) -> list[FlagQuestion]:
    qs = []
    for country in countries:
        others = [c.capital for c in countries if c.name != country.name]
        options = random.sample(others, 4)
        correct_index = random.randint(0, 4)
        options = options[:correct_index] + [country.capital] + options[correct_index:]
        prompt = f"What is the capital of {country.name}?"
        qs.append(FlagQuestion(prompt=prompt, flag=None, options=options, correct_index=correct_index))
    return qs


def new_flags_quiz(continent: str) -> AskingQuestionState:
    countries = CONTINENTS[continent]
    qs = _flag_questions(countries) + _capital_questions(countries)

    score = Score(
        correct=0,
        wrong=0,
        remaining_questions=qs,
    )
    return AskingQuestionState(
        question=score.random_question(),
        score=score
    )

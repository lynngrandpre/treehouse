from __future__ import annotations

import json
import random
from dataclasses import dataclass, replace
from pathlib import Path

import pygame

from common import AnswerPicker, Input, State, draw_text, font

from .state_info import state_info

DONE = 5     # number of incorrect guesses to end the game

DATA_DIR = Path(__file__).resolve().parent / "data"


@dataclass
class Score:
    correct: int
    wrong: int
    remaining_questions: list[Question]

    def question_answered(self, correct: bool, question: Question) -> Score:
        if correct:
            return replace(
                self,
                correct=self.correct + 1,
                remaining_questions=[s for s in self.remaining_questions if s != question]
            )
        else:
            return replace(self, wrong=self.wrong + 1)

    def random_question(self) -> Question:
        return random.choice(self.remaining_questions)


@dataclass
class Question:
    question: str
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
class QuizResultScreen:
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


def draw_question(surface: pygame.Surface, question: str) -> None:
    CANVAS_WIDTH, CANVAS_HEIGHT = surface.get_size()

    if len(question) < 40:
        draw_text(surface, font(60), question, (CANVAS_WIDTH // 2, CANVAS_HEIGHT / 2))
    else:
        halfway = len(question) // 2
        # Find the first space after halfway
        cutoff = question.find(' ', halfway)
        if cutoff == -1:
            cutoff = halfway  # fallback if no space found
        start = question[:cutoff]
        end = question[cutoff:].lstrip()

        draw_text(surface, font(35), start, (CANVAS_WIDTH // 2, CANVAS_HEIGHT / 2))
        draw_text(surface, font(35), end, (CANVAS_WIDTH // 2, CANVAS_HEIGHT / 2 + 40))


@dataclass
class RevealAnswer:
    question: Question
    score: Score

    def draw(self, surface: pygame.Surface) -> None:
        CANVAS_WIDTH, CANVAS_HEIGHT = surface.get_size()

        draw_question(surface, self.question.question)

        self.question.answer_picker(True).draw(surface)

        draw_text(surface, font(30), f"Correct {self.score.correct}", (CANVAS_WIDTH - 100, 50))
        draw_text(surface, font(30), f"Wrong   {self.score.wrong}", (CANVAS_WIDTH - 100, 80))

    def next_state(self, input: Input) -> State | None:
        pressed_buttons = [button for button in input.buttons if button.is_pressed()]

        if len(pressed_buttons) == 0:
            # move on
            if len(self.score.remaining_questions) == 0:
                return QuizResultScreen(self.score)
            elif self.score.wrong == DONE:
                return QuizResultScreen(self.score)
            else:
                return AskingQuestionState(
                    question=self.score.random_question(),
                    score=self.score
                )
        else:
            return self


@dataclass
class AskingQuestionState:
    question: Question
    score: Score

    def draw(self, surface: pygame.Surface) -> None:
        CANVAS_WIDTH, CANVAS_HEIGHT = surface.get_size()

        draw_question(surface, self.question.question)

        self.question.answer_picker(False).draw(surface)

        draw_text(surface, font(30), f"Correct {self.score.correct}", (CANVAS_WIDTH - 100, 50))
        draw_text(surface, font(30), f"Wrong   {self.score.wrong}", (CANVAS_WIDTH - 100, 80))

    def next_state(self, input: Input) -> State | None:
        correct = self.question.answer_picker(False).selection(input)
        if correct is None:
            return self

        new_score = self.score.question_answered(correct, self.question)

        return RevealAnswer(
            question=self.question,
            score=new_score
        )


def state_capital_questions(hard_mode: bool) -> list[Question]:
    qs = []
    for state_name in state_info.keys():
        correct_answer = state_info[state_name]['capital']

        options = random.sample(
            [state_info[state]['capital'] for state in state_info.keys() if state != state_name],
            4
        )

        if hard_mode:
            options = random.sample([c for c in state_info[state_name]["large_cities"] if c != correct_answer], 4)

        correct_index = random.randint(0, 4)
        options = options[:correct_index] + [correct_answer] + options[correct_index:]

        qs.append(Question(
            question=state_name,
            options=options,
            correct_index=correct_index,
        ))
    return qs


def jeopardy_questions() -> list[Question]:
    with open(DATA_DIR / "jeopardy_quiz.json", "r") as f:
        jeopardy_data = json.load(f)

    qs = []

    for q in jeopardy_data:
        category = q["category"]
        clue_value = q["clue_value"]
        question = f'{category} for {clue_value}: {q["question"]}'

        options = random.sample(
            q["wrong_answers"],
            4
        )

        correct_index = random.randint(0, 4)
        options = options[:correct_index] + [q["correct_answer"]] + options[correct_index:]

        qs.append(Question(
            question=question,
            options=options,
            correct_index=correct_index,
        ))
    return random.sample(qs, 20)


def sports_team_questions() -> list[Question]:
    qs = []
    all_options = list(state_info.keys())
    for state_name, info in state_info.items():
        for team in info["sports_teams"]:
            question = f"Which state is the {team['name']} {team['sport']} team from?"

            options = random.sample(
                [s for s in all_options if s != state_name],
                4
            )

            correct_index = random.randint(0, 4)
            options = options[:correct_index] + [state_name] + options[correct_index:]

            qs.append(Question(
                question=question,
                options=options,
                correct_index=correct_index,
            ))
    return random.sample(qs, 20)


def new_quiz(mode: str) -> AskingQuestionState:
    if mode == "capitals":
        qs = state_capital_questions(False)
    elif mode == "capitals_hard":
        qs = state_capital_questions(True)
    elif mode == "sports":
        qs = sports_team_questions()
    elif mode == "jeopardy":
        qs = jeopardy_questions()
    else:
        raise ValueError(f"Unknown quiz mode: {mode}")

    score = Score(
        correct=0,
        wrong=0,
        remaining_questions=qs,
    )
    return AskingQuestionState(
        question=score.random_question(),
        score=score
    )

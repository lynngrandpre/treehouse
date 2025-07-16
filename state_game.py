import pygame
import random
from dataclasses import dataclass, replace

from state_info import state_info

import RPi.GPIO as GPIO

from enum import Enum

DONE             = 5     # number of incorrect guesses to end the game



pygame.init()
pygame.mouse.set_visible(False) # Hide cursor here

state_font = pygame.font.SysFont("", 60)
answer_font = pygame.font.SysFont("", 25)
scoreboard_font = pygame.font.SysFont("", 30)


class Color(Enum):
    RED = 1
    GREEN = 2
    BLUE = 3
    YELLOW = 4
    WHITE = 5

all_colors = [Color.RED, Color.GREEN, Color.BLUE, Color.YELLOW, Color.WHITE]

@dataclass
class RGB:
    red: int
    green: int
    blue: int

    def __add__(self, other):
        return RGB(self.red + other.red, self.green + other.green, self.blue + other.blue)
    
    def __truediv__(self, scalar):
        return RGB(self.red//scalar, self.green//scalar, self.blue//scalar)
    
    def __mul__(self, scalar):
        return RGB(self.red*scalar, self.green*scalar, self.blue*scalar)
    
    def __eq__(self, other):
        return self.red == other.red and self.blue == other.blue and self.green == other.green

    def to_tuple(self):
        return (self.red, self.green, self.blue)

@dataclass
class Button:
    led_pin: int
    switch_pin: int
    rgb: RGB

    def set_led(self, on: bool):
        GPIO.output(self.led_pin, on) 
    
    def is_pressed(self):
        return not GPIO.input(self.switch_pin)
        

buttons= {
    Color.RED:    Button(20,26,RGB(240,15,25)),
    Color.GREEN:  Button(16, 19,RGB(0,220,0)),
    Color.WHITE:  Button(13, 12, RGB(255,255,255)),
    Color.YELLOW: Button(6, 5, RGB(255,235,0)),
    Color.BLUE:   Button(23, 22, RGB(0,0,255)),
}

buttons_in_order = [buttons[c] for c in [Color.RED, Color.GREEN, Color.BLUE, Color.YELLOW, Color.WHITE]]


# Set up GPIO using BCM numbering
GPIO.setmode(GPIO.BCM)

# Set GPIO PIN as output
# Set GPIO PIN_IN as input

for button in buttons.values():
    GPIO.setup(button.led_pin, GPIO.OUT)
    GPIO.setup(button.switch_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

@dataclass
class Input:
    buttons: "list[Button]"


@dataclass
class Score:
    correct: int
    wrong: int
    remaining_questions: "list[Question]"

    def question_answered(self, correct, question):
        if correct:
            return replace(
                self, 
                correct=self.correct + 1, 
                remaining_questions=[s for s in self.remaining_questions if s != question]
            )
        else:
            return replace(self, wrong=self.wrong + 1)

    def random_question(self):
        return random.choice(self.remaining_questions)

        

@dataclass
class Question:
    question: str
    options: "list[str]"
    correct_index: int




@dataclass 
class WinScreen:
    score: Score

    def draw(self, surface):
        CANVAS_WIDTH, CANVAS_HEIGHT = surface.get_size()

        if len(self.score.remaining_questions) == 0:
            draw_text(surface, state_font, "You Win", (CANVAS_WIDTH//2, CANVAS_HEIGHT//2))
            draw_text(surface, state_font, f"Mistakes: {self.score.wrong}", (CANVAS_WIDTH//2, CANVAS_HEIGHT//2 + 50))
        else:
            draw_text(surface, state_font, "You Lose :(", (CANVAS_WIDTH//2, CANVAS_HEIGHT//2))
            draw_text(surface, state_font, f"Correct: {self.score.correct}", (CANVAS_WIDTH//2, CANVAS_HEIGHT//2 + 50))

        draw_text(surface, scoreboard_font, f"Press Red for HARD MODE, Green for normal, Blue for sports", (CANVAS_WIDTH//2, CANVAS_HEIGHT//2 + 100))
    
    def next_state(self, input):
        pressed_buttons = [(i, button) for i, button in enumerate(input.buttons) if button.is_pressed()]

        if len(pressed_buttons) == 0:
            return self
        else:
            next_game = "capitals"
            if input.buttons[0].is_pressed():
                next_game = "capitals_hard"
            if input.buttons[2].is_pressed():
                next_game = "sports_teams"

            return GetReadyScreen(next_game)
        
@dataclass 
class GetReadyScreen:
    next_game: str

    def draw(self, surface):
        CANVAS_WIDTH, CANVAS_HEIGHT = surface.get_size()

        draw_text(surface, state_font, "Get Ready...", (CANVAS_WIDTH//2, CANVAS_HEIGHT//2))
       
    def next_state(self, input):
        pressed_buttons = [(i, button) for i, button in enumerate(input.buttons) if button.is_pressed()]

        if len(pressed_buttons) == 0:
            return new_game(self.next_game)
        else:
            return self


@dataclass 
class RevealAnswer:
    question: Question
    score: Score

    def draw(self, surface):
        CANVAS_WIDTH, CANVAS_HEIGHT = surface.get_size()

        draw_text(surface, state_font, self.question.question, (CANVAS_WIDTH//2, CANVAS_HEIGHT /2))
        

        answer_height = CANVAS_HEIGHT // 4 * 3

        pygame.draw.rect(surface, (0,0,0), pygame.Rect(((0.5) * (CANVAS_WIDTH//6) - 2, answer_height + 20 - 2), (5*CANVAS_WIDTH//6 + 2, 10 + 4)))
        for i in range(5):
            pygame.draw.rect(surface, buttons_in_order[i].rgb.to_tuple(), pygame.Rect((( i+ 0.5) * (CANVAS_WIDTH//6), answer_height + 20), (CANVAS_WIDTH//6, 10)))

        i = self.question.correct_index
        draw_text(surface, answer_font, self.question.options[i], (CANVAS_WIDTH//6 * (i + 1), answer_height))

        draw_text(surface, scoreboard_font, f"Correct {self.score.correct}", (CANVAS_WIDTH - 100, 50))
        draw_text(surface, scoreboard_font, f"Wrong   {self.score.wrong}", (CANVAS_WIDTH - 100, 80))


        
    def next_state(self, input: Input):
        pressed_buttons = [(i, button) for i, button in enumerate(input.buttons) if button.is_pressed()]

        if len(pressed_buttons) == 0:
            # move on
            if len(self.score.remaining_questions) == 0:
                return WinScreen(self.score)
            elif self.score.wrong == DONE:
                return WinScreen(self.score)
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

    def draw(self, surface):
        CANVAS_WIDTH, CANVAS_HEIGHT = surface.get_size()

        draw_text(surface, state_font, self.question.question, (CANVAS_WIDTH//2, CANVAS_HEIGHT /2))

        answer_height = CANVAS_HEIGHT // 4 * 3

        pygame.draw.rect(surface, (0,0,0), pygame.Rect(((0.5) * (CANVAS_WIDTH//6) - 2, answer_height + 20 - 2), (5*CANVAS_WIDTH//6 + 2, 10 + 4)))

        for i in range(5):
            pygame.draw.rect(surface, buttons_in_order[i].rgb.to_tuple(), pygame.Rect((( i+ 0.5) * (CANVAS_WIDTH//6), answer_height + 20), (CANVAS_WIDTH//6, 10)))
            draw_text(surface, answer_font, self.question.options[i], (CANVAS_WIDTH//6 * (i + 1), answer_height))

        draw_text(surface, scoreboard_font, f"Correct {self.score.correct}", (CANVAS_WIDTH - 100, 50))
        draw_text(surface, scoreboard_font, f"Wrong   {self.score.wrong}", (CANVAS_WIDTH - 100, 80))


    def next_state(self, input: Input):
        pressed_buttons = [(i, button) for i, button in enumerate(input.buttons) if button.is_pressed()]

        if len(pressed_buttons) != 1:
            return self
        index, _button = pressed_buttons[0]


        correct = index == self.question.correct_index
        new_score = self.score.question_answered(correct, self.question)

        return RevealAnswer(
            question=self.question,
            score=new_score
        )


from typing import Union


    

def draw_text(surface, font, text, position, color=(0, 0, 0)):
    """Draws text on the given surface at the specified position."""
    text_surface = font.render(text, True, color)
    text_rect = text_surface.get_rect(center=position)
    surface.blit(text_surface, text_rect)


def state_capital_questions(hard_mode):
    qs = []
    for state_name in state_info.keys():
        correct_answer = state_info[state_name]['capital']

        options = random.sample(
            [state_info[state]['capital'] for state in state_info.keys() if state != state_name],
            4
        )

        if hard_mode:
            options = [c for c in state_info[state_name]["large_cities"] if c != correct_answer]
            random.shuffle(options)
        
        correct_index = random.randint(0, 4)
        options = options[:correct_index] + [correct_answer] + options[correct_index:]

        qs.append(Question(
            question=state_name,
            options=options,
            correct_index=correct_index,
        ))
    return qs

def sports_team_questions():
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

def new_game(mode:str):
    qs = []
    if mode == "capitals":
        qs = state_capital_questions(False)
    elif mode == "capitals_hard":
        qs = state_capital_questions(True)
    elif mode == "sports_teams":
        qs = sports_team_questions()
     
    score = Score(
        correct=0,
        wrong=0, 
        remaining_questions=qs,
    )
    state = AskingQuestionState(
        question=score.random_question(),
        score=score
    )
    return state

def main():
    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)

    state = WinScreen(Score(0,0,[]))



    game_over = False
    while not game_over:
        screen.fill((240, 240, 240))  # RGB for white background
        state = state.next_state(Input(buttons_in_order))
        state.draw(screen)
        pygame.display.flip()  # Update the display
        for event in pygame.event.get():
            pass
           
def safe_remove(key, state_list):
    # function checks to make sure there is an item in the list to be removed
    if state_list:          
        state_list.remove(key)

if __name__ == '__main__':
    main()
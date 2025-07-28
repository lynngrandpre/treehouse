import pygame
import random
from dataclasses import dataclass, replace
from math import cos, sin, pi # Added for color_mixer animation

from state_info import state_info

import RPi.GPIO as GPIO

from enum import Enum
from typing import Union

DONE = 5     # number of incorrect guesses to end the game



pygame.init()
pygame.mouse.set_visible(False) # Hide cursor here

state_font = pygame.font.SysFont("", 60)
answer_font = pygame.font.SysFont("", 25)
scoreboard_font = pygame.font.SysFont("", 30)
q_font_small = pygame.font.SysFont("", 35)



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
    current_time: int # Added current_time to Input


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
class AnswerPicker():
    options: "list[str]"
    values: "list[str|bool]"

    def __post_init__(self):
        if len(self.options) > 5:
            raise ValueError(f"AnswerPicker: options must have at most 5 items. {self.options}")
        if len(self.values) != len(self.options):
            raise ValueError(f"AnswerPicker: values must have the same length as options. {len(self.values)=} {len(self.options)=}")

    def draw(self, surface):
        CANVAS_WIDTH, CANVAS_HEIGHT = surface.get_size()

        answer_height = CANVAS_HEIGHT // 4 * 3

        pygame.draw.rect(surface, (0,0,0), pygame.Rect(((0.5) * (CANVAS_WIDTH//6) - 2, answer_height + 20 - 2), (5*CANVAS_WIDTH//6 + 2, 10 + 4)))

        for i in range(len(self.options)):
            pygame.draw.rect(surface, buttons_in_order[i].rgb.to_tuple(), pygame.Rect((( i+ 0.5) * (CANVAS_WIDTH//6), answer_height + 20), (CANVAS_WIDTH//6, 10)))
            draw_text(surface, answer_font, self.options[i], (CANVAS_WIDTH//6 * (i + 1), answer_height))

    def selection(self, input):
        pressed_buttons = [i for i, button in enumerate(input.buttons) if button.is_pressed()]

        if len(pressed_buttons) != 1:
            return None
        
        idx = pressed_buttons[0]
        if idx >= len(self.values):
            return None
        
        return self.values[idx]


@dataclass
class Question:
    question: str
    options: "list[str]"
    correct_index: int

    def answer_picker(self, reveal_answer: bool):
        options = self.options
        if reveal_answer:
            options = ["" if i != self.correct_index else o for i, o in enumerate(self.options)]

        return AnswerPicker(
            options,
            [i == self.correct_index for i in range(len(self.options))]
        )


@dataclass 
class WinScreen:
    score: Score

    def options_picker(self):
        # Added "Color Mixer" as a new option
        return AnswerPicker(
            ["Capitals HARD", "Capitals", "Sports", "Jeopardy!", "Color Mixer"],
            ["capitals_hard", "capitals", "sports", "jeopardy", "color_mixer"]
        )

    def draw(self, surface):
        CANVAS_WIDTH, CANVAS_HEIGHT = surface.get_size()

        if len(self.score.remaining_questions) == 0:
            draw_text(surface, state_font, "You Win", (CANVAS_WIDTH//2, CANVAS_HEIGHT//2))
            draw_text(surface, state_font, f"Mistakes: {self.score.wrong}", (CANVAS_WIDTH//2, CANVAS_HEIGHT//2 + 50))
        else:
            draw_text(surface, state_font, "You Lose :(", (CANVAS_WIDTH//2, CANVAS_HEIGHT//2))
            draw_text(surface, state_font, f"Correct: {self.score.correct}", (CANVAS_WIDTH//2, CANVAS_HEIGHT//2 + 50))

        
        self.options_picker().draw(surface)
    
    def next_state(self, input):
        selection = self.options_picker().selection(input)
        if selection is not None:
            return GetReadyScreen(selection)
        else:
            return self
        
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


def draw_question(surface, question):
    CANVAS_WIDTH, CANVAS_HEIGHT = surface.get_size()

    if len(question) < 40:
        draw_text(surface, state_font, question, (CANVAS_WIDTH//2, CANVAS_HEIGHT /2))
    else:
        halfway = len(question) // 2
        # Find the first space after halfway
        cutoff = question.find(' ', halfway)
        if cutoff == -1:
            cutoff = halfway  # fallback if no space found
        start = question[:cutoff]
        end = question[cutoff:].lstrip()

        draw_text(surface, q_font_small, start, (CANVAS_WIDTH//2, CANVAS_HEIGHT /2))
        draw_text(surface, q_font_small, end, (CANVAS_WIDTH//2, CANVAS_HEIGHT /2 + 40))

@dataclass 
class RevealAnswer:
    question: Question
    score: Score

    def draw(self, surface):
        CANVAS_WIDTH, CANVAS_HEIGHT = surface.get_size()

        draw_question(surface, self.question.question)

        self.question.answer_picker(True).draw(surface)


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

        
        draw_question(surface, self.question.question)


        self.question.answer_picker(False).draw(surface)


        draw_text(surface, scoreboard_font, f"Correct {self.score.correct}", (CANVAS_WIDTH - 100, 50))
        draw_text(surface, scoreboard_font, f"Wrong   {self.score.wrong}", (CANVAS_WIDTH - 100, 80))


    def next_state(self, input: Input):
        correct = self.question.answer_picker(False).selection(input)
        if correct is None:
            return self

        new_score = self.score.question_answered(correct, self.question)

        return RevealAnswer(
            question=self.question,
            score=new_score
        )



    

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
            options = random.sample([c for c in state_info[state_name]["large_cities"] if c != correct_answer],4)
        
        correct_index = random.randint(0, 4)
        options = options[:correct_index] + [correct_answer] + options[correct_index:]

        qs.append(Question(
            question=state_name,
            options=options,
            correct_index=correct_index,
        ))
    return qs

import json
import csv


def jeopardy_questions():
    with open("./data/jeopardy_quiz.json", "r") as f:
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

# --- Color Mixer Game Logic Integration ---

# Helper functions for color mixer
def average(rgbs):
    current_color = RGB(0,0,0)
    if len(rgbs) == 0:
        return current_color

    for rgb in rgbs:
        current_color += rgb

    return current_color / len(rgbs)

# Fixed max_num_buttons for the integrated game
COLOR_MIXER_MAX_BUTTONS = 3 # Can be adjusted

def gen_target_colors(max_num_buttons_for_mix):
    # Ensure we don't try to sample more colors than available
    num_colors_to_mix = random.randint(1, min(max_num_buttons_for_mix, len(all_colors)))
    cols = random.sample(all_colors, num_colors_to_mix)
    return [buttons[col].rgb for col in cols ]

# Constants for color mixer animation
COLOR_MIXER_ANIM_DURATION = 750
COLOR_MIXER_ANIM_HOLD_FINAL = 1250
COLOR_MIXER_MIN_VICTORY_SCREEN_DURATION = COLOR_MIXER_ANIM_DURATION + COLOR_MIXER_ANIM_HOLD_FINAL


@dataclass
class ColorMixerState:
    target_rgbs: "list[RGB]"
    victory_anim_start_time: int
    victory_screen_end_time: int
    victory_rgbs: "list[RGB]"
    last_change_time: int
    last_rgb: RGB
    max_num_buttons: int

    def __post_init__(self):
        # Initialize target_rgbs if not provided (e.g., for initial game start)
        if not self.target_rgbs:
            self.target_rgbs = gen_target_colors(self.max_num_buttons)
        # Initialize time variables for a fresh start
        self.victory_anim_start_time = -COLOR_MIXER_MIN_VICTORY_SCREEN_DURATION # Ensure initial screen is game
        self.victory_screen_end_time = -COLOR_MIXER_MIN_VICTORY_SCREEN_DURATION
        self.victory_rgbs = []
        self.last_change_time = -100
        self.last_rgb = RGB(0,0,0)


    def draw(self, surface):
        CANVAS_WIDTH, CANVAS_HEIGHT = surface.get_size()
        center_x = CANVAS_WIDTH // 2
        center_y = CANVAS_HEIGHT // 2
        current_time = pygame.time.get_ticks() # Get current time for drawing logic

        if current_time > self.victory_screen_end_time:
            # Normal game screen
            current_rgb_from_buttons = average([button.rgb for button in buttons_in_order if button.is_pressed()])
            surface.fill(current_rgb_from_buttons.to_tuple())
            pygame.draw.circle(surface, average(self.target_rgbs).to_tuple(), (center_x, center_y), 100)
        else:
            # Victory animation screen
            surface.fill((222,222,222)) # Background for animation

            num_squares = len(self.victory_rgbs)

            t = max(0, (current_time - self.victory_anim_start_time) / COLOR_MIXER_ANIM_DURATION)
            t_capped = min(1, t)
            u = max(0, (current_time - self.victory_anim_start_time) / COLOR_MIXER_MIN_VICTORY_SCREEN_DURATION)

            for i, victory_rgb in enumerate(self.victory_rgbs):
                surf = pygame.Surface((200, 200), flags=pygame.SRCALPHA)
                surf.fill((0,0,0,0)) # Transparent background

                pygame.draw.circle(surf, victory_rgb.to_tuple() + (255 // num_squares,), (100,100), 100)
                
                start_center_x = center_x
                start_center_y = center_y

                direction_rads = i / num_squares * (2 * pi) - pi / 2 + u / 2 * pi
                distance_to_travel = 60
                dx = distance_to_travel * cos(direction_rads)
                dy = distance_to_travel * sin(direction_rads)

                end_center_x = start_center_x + dx
                end_center_y = start_center_y + dy

                current_center_x = start_center_x + (end_center_x - start_center_x) * t_capped
                current_center_y = start_center_y + (end_center_y - start_center_y) * t_capped

                surface.blit(surf, (current_center_x - 100, current_center_y - 100))


    def next_state(self, input: Input):
        current_time = input.current_time # Use the current_time from Input

        # Handle button LEDs
        for button in buttons.values():
            if not button.is_pressed():
                button.set_led(True)
            else:
                button.set_led(False)

        if current_time > self.victory_screen_end_time:
            # Game is active, not in victory animation
            rgbs = [button.rgb for button in input.buttons if button.is_pressed()]
            current_rgb = average(rgbs)

            if current_rgb != self.last_rgb:
                self.last_rgb = current_rgb
                self.last_change_time = current_time

            if current_rgb == average(self.target_rgbs) and (self.last_change_time + 150 < current_time):
                # Correct mix achieved, start victory animation
                self.victory_rgbs = self.target_rgbs # Store for animation
                self.target_rgbs = gen_target_colors(self.max_num_buttons) # Generate new target
                self.victory_screen_end_time = current_time + COLOR_MIXER_MIN_VICTORY_SCREEN_DURATION
                self.victory_anim_start_time = current_time
        else:
            # In victory animation, check if any button is pressed to extend it
            if any(button.is_pressed() for button in input.buttons):
                self.victory_screen_end_time = max(self.victory_screen_end_time, current_time + 200)

        return self # Always return self for now, as color mixer doesn't transition to other game types

# --- End Color Mixer Game Logic Integration ---


def new_game(mode:str):
    qs = []
    if mode == "capitals":
        qs = state_capital_questions(False)
    elif mode == "capitals_hard":
        qs = state_capital_questions(True)
    elif mode == "sports":
        qs = sports_team_questions()
    elif mode == "jeopardy":
        qs = jeopardy_questions()
    elif mode == "color_mixer": # New game mode
        return ColorMixerState(
            target_rgbs=[], # Will be initialized in __post_init__
            victory_anim_start_time=0, # Placeholder, will be set in __post_init__
            victory_screen_end_time=0, # Placeholder, will be set in __post_init__
            victory_rgbs=[], # Placeholder, will be set in __post_init__
            last_change_time=0, # Placeholder, will be set in __post_init__
            last_rgb=RGB(0,0,0), # Placeholder, will be set in __post_init__
            max_num_buttons=COLOR_MIXER_MAX_BUTTONS
        )
     
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
        current_time = pygame.time.get_ticks() # Get current time in main loop
        state = state.next_state(Input(buttons_in_order, current_time)) # Pass current_time
        state.draw(screen)
        pygame.display.flip()  # Update the display
        for event in pygame.event.get():
            # Allow quitting the game
            if event.type == pygame.QUIT:
                game_over = True
            # Check for escape key to quit, ensuring it's a KEYDOWN event
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                game_over = True
           
def safe_remove(key, state_list):
    # function checks to make sure there is an item in the list to be removed
    if state_list:          
        state_list.remove(key)

if __name__ == '__main__':
    try:
        main()
    finally:
        GPIO.cleanup() # Clean up GPIO on exit

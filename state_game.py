import pygame
import random
from dataclasses import dataclass, replace

from state_info import state_info

import RPi.GPIO as GPIO

from enum import Enum

CANVAS_WIDTH     = 800   # Width  of canvas   
CANVAS_HEIGHT    = 400   # Height of canvas
BALL_SIZE        = 25    # ball to play with
BUTTON_SIZE      = 75    # diameter of the buttons 
GOAL             = 50     # number of correct guesses to end game
DONE             = 5     # number of incorrect guesses to end the game
DELAY            = 0.0001 # for my bouncing ball at the end
INITIAL_VELOCITY = 5     # for the ball
PADDLE_WIDTH     = 50    # of course we need a paddle
PADDLE_HEIGHT    = 15    # and a paddle needs some thickness
PADDLE_VELOCITY  = 5     # How fast the paddle moves

state_font = pygame.font.SysFont(None, 20)
answer_font = pygame.font.SysFont(None, 15)
scoreboard_font = pygame.font.SysFont(None, 30)


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

    def question_answered(self, correct):
        if correct:
            return replace(self, correct=self.correct + 1)
        else:
            return replace(self, wrong=self.wrong + 1)

@dataclass
class Question:
    state_name: str
    options: "list[str]"
    correct_index: int


def random_question():
    state_name = random.choice(list(state_info.keys()))
    correct_answer = state_info[state_name]['capital']

    options = random.sample(
        [state_info[state]['capital'] for state in state_info.keys() if state != state_name],
        4
    )
    
    correct_index = random.randint(0, 5)
    options = options[:correct_index] + [correct_answer] + options[correct_index:]

    return Question(
        state_name=state_name,
        options=options,
        correct_index=correct_index,
    )


@dataclass
class AskingQuestionState:
    question: Question
    score: Score

    def draw(self, surface):
        draw_text(surface, state_font, self.question.state_name, (CANVAS_WIDTH//6, CANVAS_HEIGHT /3))
        for i in range(5):
            draw_text(surface, answer_font, self.question.options[i], (CANVAS_WIDTH//6 * (i + 1), CANVAS_HEIGHT - 40))

        draw_text(surface, scoreboard_font, f"Correct {self.score.correct}", (CANVAS_WIDTH - 100, 50))
        draw_text(surface, scoreboard_font, f"Wrong   {self.score.wrong}", (CANVAS_WIDTH - 100, 80))


    def next_state(self, input: Input):
        pressed_buttons = [(i, button) for i, button in enumerate(input.buttons) if button.is_pressed()]

        if len(pressed_buttons) != 1:
            return self
        index, _button = pressed_buttons[0]


        correct = index == self.question.correct_index
        new_score = self.score.question_answered(correct)

        return AskingQuestionState(
            question=random_question(),
            score=new_score
        )


from typing import Union



def pick_a_state():
    # we'll need four random capitals to choose from
    # plus the correct capital
    correct_capital = state_info[key]['capital']
        
    # now pick 4 random capitals from capital_list
    rnd_cap = []       # start with an empty list then pick 4
    while len(rnd_cap) < 4:
        new_item = random.choice(capital_list)
        while new_item == correct_capital:        # make sure we didn't pick the correct one
            new_item = random.choice(capital_list) # try again
        
        # Check if the new item is already in the list
        # so we don't get repeat items
        if new_item not in rnd_cap:
            rnd_cap.append(new_item)
        
    # we want to add the correct_capital to my random captial list in a random order
    # Generate a random index between 0 and the length of the list
    random_index = random.randint(0, len(rnd_cap))
    # Insert the new item at the random index
    rnd_cap.insert(random_index, correct_capital)
    
    

def draw_text(surface, font, text, position, color=(0, 0, 0)):
    """Draws text on the given surface at the specified position."""
    text_surface = font.render(text, True, color)
    text_rect = text_surface.get_rect(center=position)
    surface.blit(text_surface, text_rect)

def main():
    # This program will create a state capital
    # quiz game to help kids learn the state capitals.
    # If a state has an NBA team and the player can
    # name it, they get to play a 3-point shooting game
    # to earn bonus points
    # lets use pictures of the states and buttons to select 
    # capitals


   

    # set up a dictionary of the state images with 
    # the state name as the key

    

    pygame.init()

    screen = pygame.display.set_mode((CANVAS_WIDTH, CANVAS_HEIGHT))




    state = AskingQuestionState(
        question=random_question(),
        score=Score(0,0)
    )



    game_over = False
    while not game_over:
        screen.fill((255, 255, 255))  # RGB for white
        state = state.next_state(Input(list(buttons.values())))
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
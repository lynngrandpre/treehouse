# Color Mixer Game
# 
# Usage: python color_mixer.py max_num_buttons
# max_num_buttons: maximum number of colors to mix
#
# Game chooses several colors to mix together in a dot on the screen.
# Hold down the buttons corresponding to the colors to guess the color mix

import pygame

pygame.init()

screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)


# Variable to keep the main loop running
running = True

import sys
max_num_buttons = int(sys.argv[1])


from enum import Enum
import RPi.GPIO as GPIO
import time

from dataclasses import dataclass

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
    

def average(rgbs):
    current_color = RGB(0,0,0)
    if len(rgbs) == 0:
        return current_color

    for rgb in rgbs:
        current_color += rgb

    return current_color / len(rgbs)

import random


def gen_target_colors():
    cols = random.sample(all_colors, min(max_num_buttons, random.randint(1, len(all_colors))))
    return [buttons[col].rgb for col in cols ]

center = (510, 320)

target_rgbs = gen_target_colors()

anim_duration = 750
anim_hold_final = 1250
min_victory_screen_duration = anim_duration + anim_hold_final

current_time = pygame.time.get_ticks()

victory_anim_start_time = -100
victory_screen_end_time = -min_victory_screen_duration
victory_rgbs = []

last_change_time = -100
last_rgb = RGB(0,0,0)

from math import cos, sin, pi

# Main loop
while running:
    # Look at every event in the queue
    for event in pygame.event.get():
        pass
    
    current_time = pygame.time.get_ticks()

    rgbs = []
    for (color, button) in buttons.items():
        
        if not button.is_pressed():
            button.set_led(True)
        else:
            # print(f"{color} DOWN!")
            button.set_led(False)
            rgbs.append(button.rgb)

    current_rgb = average(rgbs)
    if current_rgb != last_rgb:
        last_rgb = current_rgb
        last_change_time = current_time

    if current_time > victory_screen_end_time:

        screen.fill(current_rgb.to_tuple())
        pygame.draw.circle(screen, average(target_rgbs).to_tuple(), center, 100)
          
        if current_rgb == average(target_rgbs) and (last_change_time + 150 < current_time):
            victory_rgbs = target_rgbs
            target_rgbs = gen_target_colors()
            victory_screen_end_time = current_time + min_victory_screen_duration
            victory_anim_start_time = current_time
    else:
        if len(rgbs) > 0:
            victory_screen_end_time = max(victory_screen_end_time, current_time + 200)

        screen.fill((222,222,222))

        num_squares = len(victory_rgbs)

        t = max(0, (current_time - victory_anim_start_time) / anim_duration)
        t_capped = min(1, t)
        u = max(0, (current_time - victory_anim_start_time) / min_victory_screen_duration)

        for i, victory_rgb in enumerate(victory_rgbs):
            surf = pygame.Surface((200, 200), flags=pygame.SRCALPHA)
            surf.fill((0,0,0,0))

            
            pygame.draw.circle(surf, victory_rgb.to_tuple() + (255 // num_squares,), (100,100), 100)
            rect = surf.get_rect()

            start_center_x = center[0]
            start_center_y = center[1]

            direction_rads = i / num_squares * (2 * pi) - pi / 2 + u / 2 * pi
            distance_to_travel = 60
            dx = distance_to_travel * cos(direction_rads)
            dy = distance_to_travel * sin(direction_rads)

            end_center_x = start_center_x + dx
            end_center_y = start_center_y + dy

            current_center_x = start_center_x + (end_center_x - start_center_x) * t_capped
            current_center_y = start_center_y + (end_center_y - start_center_y) * t_capped

            print(current_center_x, current_center_y)

            screen.blit(surf, (current_center_x - 100, current_center_y - 100))



    pygame.display.flip()

    
    
    
    

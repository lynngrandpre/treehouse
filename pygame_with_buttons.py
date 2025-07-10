import pygame

pygame.init()

# Define constants for the screen width and height
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600

# Create the screen object
# The size is determined by the constant SCREEN_WIDTH and SCREEN_HEIGHT
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))

# Variable to keep the main loop running
running = True


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

@dataclass
class RGB:
    red: int
    green: int
    blue: int

    def __add__(self, other):
        return RGB(self.red + other.red, self.green + other.green, self.blue + other.blue)
    
    def __div__(self, scalar):
        return RGB(self.red/scalar, self.green/scalar, self.blue/scalar)
    
    def __mul__(self, scalar):
        return RGB(self.red*scalar, self.green*scalar, self.blue*scalar)


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
    Color.RED:    Button(20,26,RGB(255,0,0)),
    Color.GREEN:  Button(16, 19,RGB(0,255,0)),
    Color.WHITE:  Button(13, 12, RGB(255,255,255)),
    Color.YELLOW: Button(6, 5, RGB(128,128,0)),
    Color.BLUE:   Button(23, 22, RGB(0,0,255)),
}


# Set up GPIO using BCM numbering
GPIO.setmode(GPIO.BCM)

# Set GPIO PIN as output
# Set GPIO PIN_IN as input

for button in buttons.values():
    GPIO.setup(button.led_pin, GPIO.OUT)
    GPIO.setup(button.switch_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def game_loop():


# Main loop
while running:
    # Look at every event in the queue
    for event in pygame.event.get():
        pass
    
    current_color = RGB(0,0,0)
    num_colors = 0
    for (color, button) in buttons.items():
        if not button.is_pressed():
            button.set_led(True)
        else:
            print(f"{color} DOWN!")
            button.set_led(False)
            current_color += color
            num_colors += 1
    current_color /= num_colors

    
    screen.fill((current_color.red, current_color.green, current_color.blue))

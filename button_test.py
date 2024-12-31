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
class Button:
    led_pin: int
    switch_pin: int

    def set_led(self, on: bool):
        GPIO.output(self.led_pin, on) 
    
    def is_pressed(self):
        return not GPIO.input(self.switch_pin)
        

buttons= {
    Color.red:    Button(20,26),
    Color.green:  Button(16, 19),
    Color.white:  Button(13, 12),
    Color.yellow: Button(6, 5),
    Color.blue:   Button(23, 22),
}


# Set up GPIO using BCM numbering
GPIO.setmode(GPIO.BCM)

# Set GPIO PIN as output
# Set GPIO PIN_IN as input

for button in buttons.values():
    GPIO.setup(button.led_pin, GPIO.OUT)
    GPIO.setup(button.switch_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def game_loop():
    for (color, button) in buttons.items():
        if not button.is_pressed():
            button.set_led(True)
        else:
            print(f"{color} DOWN!")
            button.set_led(False)


"""
if GPIO.input():
    GPIO.output(PIN, GPIO.LOW)
else:
    GPIO.output(PIN,GPIO.HIGH)
"""

try:
    while True:
        game_loop()
except KeyboardInterrupt:
    # Clean up GPIO on CTRL+C exit
    GPIO.cleanup()

# Clean up GPIO on normal exit
GPIO.cleanup()
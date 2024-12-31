import RPi.GPIO as GPIO
import time

from dataclasses import dataclass


@dataclass
class Button:
    led_pin: int
    switch_pin: int

    def set_led(self, on: bool):
        GPIO.output(self.led_pin, on) 
    
    def is_pressed(self):
        return GPIO.input(self.switch_pin)
        

buttons= [Button(20,26)]


# Set up GPIO using BCM numbering
GPIO.setmode(GPIO.BCM)

# Set GPIO PIN as output
# Set GPIO PIN_IN as input

for button in buttons:
    GPIO.setup(button.led_pin, GPIO.OUT)
    GPIO.setup(button.switch_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

def game_loop():
    if button.is_pressed():
        button.set_led(True)
    else:
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
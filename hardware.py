"""The physical hardware: GPIO backend selection and the buttons (with their LEDs
and switches) wired to it.

Sits at the very bottom of the import graph -- imports nothing from anywhere else
in the app, so everything else can import it freely without cycles.
"""

# Makes annotations lazy, so modern syntax (list[str], X | None, forward refs,
# unquoted) works even on the Pi's older system Python. Same idea in every file.
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from enum import Enum

SIMULATOR = "--simulator" in sys.argv or os.environ.get("SIMULATOR") == "1"

if SIMULATOR:
    import sim_gpio as GPIO
else:
    import RPi.GPIO as GPIO


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

    def __add__(self, other: RGB) -> RGB:
        return RGB(self.red + other.red, self.green + other.green, self.blue + other.blue)

    def __truediv__(self, scalar: int) -> RGB:
        return RGB(self.red // scalar, self.green // scalar, self.blue // scalar)

    def __mul__(self, scalar: int) -> RGB:
        return RGB(self.red * scalar, self.green * scalar, self.blue * scalar)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RGB):
            return NotImplemented
        return self.red == other.red and self.blue == other.blue and self.green == other.green

    def to_tuple(self) -> tuple[int, int, int]:
        return (self.red, self.green, self.blue)


@dataclass
class Button:
    led_pin: int
    switch_pin: int
    rgb: RGB

    def set_led(self, on: bool) -> None:
        GPIO.output(self.led_pin, on)

    def is_pressed(self) -> bool:
        return not GPIO.input(self.switch_pin)


buttons = {
    Color.RED:    Button(20, 26, RGB(240, 15, 25)),
    Color.GREEN:  Button(16, 19, RGB(0, 220, 0)),
    Color.WHITE:  Button(13, 12, RGB(255, 255, 255)),
    Color.YELLOW: Button(6, 5, RGB(255, 235, 0)),
    Color.BLUE:   Button(23, 22, RGB(0, 0, 255)),
}

# Left to right, as the buttons are physically wired up.
buttons_in_order = [buttons[c] for c in [Color.RED, Color.GREEN, Color.BLUE, Color.YELLOW, Color.WHITE]]

GPIO.setmode(GPIO.BCM)

for button in buttons.values():
    GPIO.setup(button.led_pin, GPIO.OUT)
    GPIO.setup(button.switch_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

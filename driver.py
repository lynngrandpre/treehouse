"""The general-purpose driver: hardware setup and the input -> update -> draw game
loop shared by every game. Game-specific code (like state_game.py) only needs to
build an initial state object -- with `next_state(input)` and `draw(surface)` -- and
hand it to `run()`.

Runs against real hardware by default. Pass --simulator (or set SIMULATOR=1) to run
in a window on a laptop instead: the device's screen is drawn as an embedded
rectangle, with clickable on-screen buttons (also mappable to keys 1-5) standing in
for the physical ones.
"""

import os
import sys
from dataclasses import dataclass
from enum import Enum

import pygame

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

    def __add__(self, other):
        return RGB(self.red + other.red, self.green + other.green, self.blue + other.blue)

    def __truediv__(self, scalar):
        return RGB(self.red // scalar, self.green // scalar, self.blue // scalar)

    def __mul__(self, scalar):
        return RGB(self.red * scalar, self.green * scalar, self.blue * scalar)

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


@dataclass
class Input:
    buttons: "list[Button]"
    current_time: int


pygame.init()

# The real device is a small touchscreen run fullscreen at whatever resolution
# it happens to have. The simulator has no such screen to ask, so it stands
# one in with a reasonable default -- the embedded "device" rectangle below
# is drawn at exactly this size regardless of the surrounding window.
DEVICE_WIDTH = 800
DEVICE_HEIGHT = 480

_MARGIN = 30
_BUTTON_AREA_HEIGHT = 140
_BUTTON_SIZE = 90
_BUTTON_GAP = 20
_BUTTON_KEYS = [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5]

if SIMULATOR:
    _button_font = pygame.font.SysFont("", 40)


def _button_rects():
    total_width = len(buttons_in_order) * _BUTTON_SIZE + (len(buttons_in_order) - 1) * _BUTTON_GAP
    start_x = _MARGIN + (DEVICE_WIDTH - total_width) // 2
    y = _MARGIN + DEVICE_HEIGHT + (_BUTTON_AREA_HEIGHT - _BUTTON_SIZE) // 2
    return [
        pygame.Rect(start_x + i * (_BUTTON_SIZE + _BUTTON_GAP), y, _BUTTON_SIZE, _BUTTON_SIZE)
        for i in range(len(buttons_in_order))
    ]


def _update_simulated_input(button_rects):
    mouse_pos = pygame.mouse.get_pos()
    mouse_down = pygame.mouse.get_pressed()[0]
    keys_down = pygame.key.get_pressed()

    for i, button in enumerate(buttons_in_order):
        pressed = (mouse_down and button_rects[i].collidepoint(mouse_pos)) or keys_down[_BUTTON_KEYS[i]]
        GPIO.set_input_state(button.switch_pin, pressed)


def _draw_simulator_chrome(window, device_surface, button_rects):
    window.fill((60, 60, 60))
    window.blit(device_surface, (_MARGIN, _MARGIN))
    pygame.draw.rect(window, (0, 0, 0), (_MARGIN, _MARGIN, DEVICE_WIDTH, DEVICE_HEIGHT), 2)

    for i, button in enumerate(buttons_in_order):
        rect = button_rects[i]
        lit = GPIO.get_output_state(button.led_pin)
        color = button.rgb.to_tuple() if lit else tuple(c // 3 for c in button.rgb.to_tuple())

        pygame.draw.rect(window, color, rect, border_radius=10)
        pygame.draw.rect(window, (0, 0, 0), rect, 2, border_radius=10)

        label = _button_font.render(str(i + 1), True, (0, 0, 0))
        window.blit(label, label.get_rect(center=rect.center))


def run(initial_state):
    """Runs the game loop until the window is closed or Escape is pressed.

    `initial_state` must implement `next_state(input) -> state` and `draw(surface)`;
    the loop repeatedly polls input, advances state, and draws the result.
    """
    try:
        if SIMULATOR:
            button_rects = _button_rects()
            window = pygame.display.set_mode(
                (DEVICE_WIDTH + 2 * _MARGIN, DEVICE_HEIGHT + _BUTTON_AREA_HEIGHT + 2 * _MARGIN)
            )
            device_surface = pygame.Surface((DEVICE_WIDTH, DEVICE_HEIGHT))
        else:
            window = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            device_surface = window
            pygame.mouse.set_visible(False)

        state = initial_state
        game_over = False
        while not game_over:
            if SIMULATOR:
                _update_simulated_input(button_rects)

            device_surface.fill((240, 240, 240))
            current_time = pygame.time.get_ticks()
            state = state.next_state(Input(buttons_in_order, current_time))
            state.draw(device_surface)

            if SIMULATOR:
                _draw_simulator_chrome(window, device_surface, button_rects)

            pygame.display.flip()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    game_over = True
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    game_over = True
    finally:
        GPIO.cleanup()

"""The entry point and game loop: sets up the simulator window (if enabled) and
repeatedly polls input, advances the current state, and draws it. A game's
`next_state(input)` can return None to signal "I'm done, take me back to the menu" --
the loop catches that and resets to menu.home(), through a brief GetReadyScreen so a
still-held button isn't misread as a press in the menu.

Runs against real hardware by default. Pass --simulator (or set SIMULATOR=1) to run
in a window on a laptop instead: the device's screen is drawn as an embedded
rectangle, with clickable on-screen buttons (also mappable to keys 1-5) standing in
for the physical ones.
"""

import pygame

from hardware import SIMULATOR, GPIO, buttons_in_order
from common import Input, GetReadyScreen

import menu

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

    `initial_state` must implement `next_state(input) -> state | None` and
    `draw(surface)`; the loop repeatedly polls input, advances state, and draws the
    result. Returning None from `next_state` sends the player back to the menu.
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
            if state is None:
                state = GetReadyScreen(menu.home)
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


if __name__ == '__main__':
    run(menu.home())

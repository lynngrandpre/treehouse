"""Optional game-controller support: maps every connected joystick/gamepad's
buttons onto the same five colored buttons and the big red button that the
physical panel exposes. Every game gets this for free, since they all read
input through Button.is_pressed()/big_red_button_pressed() (see hardware.py),
never pygame.joystick directly.

Several controllers can be plugged in at once and they all drive the same
shared set of buttons, same as several kids sharing the physical panel --
e.g. one controller's D-pad aims (tower_defense's Red/Green) while another's
face buttons answer (Blue/Yellow/White).

Button-index mapping below targets the standard Xinput layout that Xbox
controllers and 8BitDo pads (in their X-input mode) report on Linux:
  0=A  1=B  2=X  3=Y  4=LB  5=RB  6=Back/View  7=Start/Menu
The D-pad comes through as a hat, not buttons. Untested against real
hardware as of writing -- if a controller's buttons don't line up once one
arrives, this is the only file that needs adjusting.
"""

from __future__ import annotations

import pygame

from hardware import Color, set_big_red_override, set_button_override

_BUTTON_A = 0
_BUTTON_B = 1
_BUTTON_X = 2
_BUTTON_BACK = 6

_joysticks: dict[int, pygame.joystick.Joystick] = {}


def _sync_joysticks() -> None:
    """Cheap enough to call every frame, and means controllers can be plugged
    in or unplugged without restarting the game."""
    count = pygame.joystick.get_count()
    if count == len(_joysticks):
        return
    for joystick in _joysticks.values():
        joystick.quit()
    _joysticks.clear()
    for i in range(count):
        joystick = pygame.joystick.Joystick(i)
        joystick.init()
        _joysticks[i] = joystick


def poll() -> None:
    """Call once per frame, before anything reads button/big-red state.
    Requires pygame's event queue to have been pumped this frame already,
    or joystick state will lag a frame behind."""
    _sync_joysticks()

    red = green = blue = yellow = white = back = False
    for joystick in _joysticks.values():
        if joystick.get_numhats() > 0:
            _, hat_y = joystick.get_hat(0)
            red = red or hat_y > 0
            green = green or hat_y < 0
        numbuttons = joystick.get_numbuttons()
        if numbuttons > _BUTTON_A:
            blue = blue or joystick.get_button(_BUTTON_A)
        if numbuttons > _BUTTON_B:
            yellow = yellow or joystick.get_button(_BUTTON_B)
        if numbuttons > _BUTTON_X:
            white = white or joystick.get_button(_BUTTON_X)
        if numbuttons > _BUTTON_BACK:
            back = back or joystick.get_button(_BUTTON_BACK)

    set_button_override(Color.RED, red)
    set_button_override(Color.GREEN, green)
    set_button_override(Color.BLUE, blue)
    set_button_override(Color.YELLOW, yellow)
    set_button_override(Color.WHITE, white)
    set_big_red_override(back)

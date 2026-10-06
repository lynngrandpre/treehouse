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

from dataclasses import dataclass
from typing import Any

import pygame

try:
    from pygame._sdl2 import controller as sdl_controller
except ImportError:
    sdl_controller = None

from hardware import Color, set_big_red_override, set_button_override

_BUTTON_A = 0
_BUTTON_B = 1
_BUTTON_X = 2
_BUTTON_BACK = 6

_joysticks: dict[int, pygame.joystick.JoystickType] = {}
_controllers: dict[int, Any] = {}
_slots: list[int | None] = [None, None]


@dataclass(frozen=True)
class Pad:
    connected: bool = False
    name: str = "Keyboard"
    lx: float = 0
    ly: float = 0
    rx: float = 0
    ry: float = 0
    a: bool = False
    b: bool = False
    x: bool = False
    y: bool = False
    start: bool = False
    back: bool = False
    up: bool = False
    down: bool = False
    fire: bool = False


def _deadzone(value: float) -> float:
    return 0.0 if abs(value) < .18 else value


def _sync_joysticks() -> None:
    """Cheap enough to call every frame, and means controllers can be plugged
    in or unplugged without restarting the game."""
    if not pygame.joystick.get_init():
        pygame.joystick.init()
    if sdl_controller is not None and not sdl_controller.get_init():
        sdl_controller.init()
    present = set()
    for i in range(pygame.joystick.get_count()):
        try:
            joystick = pygame.joystick.Joystick(i)
            joystick.init()
            identity = joystick.get_instance_id()
            present.add(identity)
            if identity not in _joysticks:
                _joysticks[identity] = joystick
                if None in _slots:
                    _slots[_slots.index(None)] = identity
                if sdl_controller is not None and sdl_controller.is_controller(i):
                    _controllers[identity] = sdl_controller.Controller.from_joystick(joystick)
        except pygame.error:
            continue  # a device can disappear between enumeration and opening
    for identity in set(_joysticks) - present:
        _joysticks.pop(identity).quit()
        controller = _controllers.pop(identity, None)
        if controller is not None:
            controller.quit()
        for slot, current in enumerate(_slots):
            if current == identity:
                _slots[slot] = None
    # Fill vacant roles without moving a still-connected wingmate into pilot.
    for identity in _joysticks:
        if identity not in _slots and None in _slots:
            _slots[_slots.index(None)] = identity


def snapshot(slot: int) -> Pad:
    identity = _slots[slot]
    joystick = _joysticks.get(identity)
    if joystick is None:
        return Pad()
    try:
        controller = _controllers.get(identity)
        if controller is not None:
            def axis(index: int) -> float:
                return _deadzone(controller.get_axis(index) / 32768.0)

            def button(index: int) -> bool:
                return bool(controller.get_button(index))

            return Pad(True, joystick.get_name(),
                       axis(pygame.CONTROLLER_AXIS_LEFTX), axis(pygame.CONTROLLER_AXIS_LEFTY),
                       axis(pygame.CONTROLLER_AXIS_RIGHTX), axis(pygame.CONTROLLER_AXIS_RIGHTY),
                       button(pygame.CONTROLLER_BUTTON_A), button(pygame.CONTROLLER_BUTTON_B),
                       button(pygame.CONTROLLER_BUTTON_X), button(pygame.CONTROLLER_BUTTON_Y),
                       button(pygame.CONTROLLER_BUTTON_START), button(pygame.CONTROLLER_BUTTON_BACK),
                       button(pygame.CONTROLLER_BUTTON_DPAD_UP), button(pygame.CONTROLLER_BUTTON_DPAD_DOWN),
                       axis(pygame.CONTROLLER_AXIS_TRIGGERRIGHT) > .2 or button(pygame.CONTROLLER_BUTTON_A))
        # XInput joystick fallback for SDL builds without a controller mapping.
        def raw_axis(index: int) -> float:
            return _deadzone(joystick.get_axis(index)) if index < joystick.get_numaxes() else 0.0

        def raw_button(index: int) -> bool:
            return bool(joystick.get_button(index)) if index < joystick.get_numbuttons() else False

        hat = joystick.get_hat(0) if joystick.get_numhats() else (0, 0)
        return Pad(True, joystick.get_name(), raw_axis(0), raw_axis(1), raw_axis(3), raw_axis(4),
                   raw_button(0), raw_button(1), raw_button(2), raw_button(3), raw_button(7),
                   raw_button(6), hat[1] > 0, hat[1] < 0, raw_button(0))
    except pygame.error:
        return Pad()


def any_activity() -> bool:
    return any(p.connected and (abs(p.lx) + abs(p.ly) + abs(p.rx) + abs(p.ry) > .2 or
               p.a or p.b or p.x or p.y or p.fire or p.start or p.back or p.up or p.down)
               for p in (snapshot(0), snapshot(1)))


def poll(shared_buttons: bool = True) -> None:
    """Call once per frame, before anything reads button/big-red state.
    Requires pygame's event queue to have been pumped this frame already,
    or joystick state will lag a frame behind."""
    _sync_joysticks()

    red = green = blue = yellow = white = back = False
    for joystick in (_joysticks.values() if shared_buttons else []):
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

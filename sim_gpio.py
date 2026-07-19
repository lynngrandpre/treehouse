"""A drop-in stand-in for RPi.GPIO, used when the driver runs in simulator mode.

Implements just the pieces of the RPi.GPIO interface that Button (in hardware.py)
relies on, backed by in-memory pin state instead of real hardware. Games never
import this directly -- hardware.py picks it or the real RPi.GPIO based on mode.
"""

BCM = "BCM"
OUT = "OUT"
IN = "IN"
PUD_UP = "PUD_UP"
HIGH = 1
LOW = 0

_input_state = {}   # switch pin -> HIGH (not pressed) / LOW (pressed)
_output_state = {}  # led pin -> bool


def setmode(mode):
    pass


def setup(pin, direction, pull_up_down=None):
    if direction == IN:
        _input_state.setdefault(pin, HIGH)
    elif direction == OUT:
        _output_state.setdefault(pin, False)


def output(pin, value):
    _output_state[pin] = bool(value)


def input(pin):
    return _input_state.get(pin, HIGH)


def cleanup():
    pass


# --- simulator-only hooks, not part of the real RPi.GPIO interface ---
# The driver's simulator loop calls these to feed in mouse/keyboard input
# and to read back LED state for drawing the on-screen buttons.

def set_input_state(pin, pressed: bool):
    _input_state[pin] = LOW if pressed else HIGH


def get_output_state(pin) -> bool:
    return _output_state.get(pin, False)

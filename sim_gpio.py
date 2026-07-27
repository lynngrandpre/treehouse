"""A drop-in stand-in for RPi.GPIO, used when the driver runs in simulator mode.

Implements just the pieces of the RPi.GPIO interface that Button (in hardware.py)
relies on, backed by in-memory pin state instead of real hardware. Games never
import this directly -- hardware.py picks it or the real RPi.GPIO based on mode.
"""

from __future__ import annotations

# Matching RPi.GPIO's actual constant values (not just names) so a type checker,
# which sees `GPIO` as a union of this module and the real one, doesn't flag a
# mismatch at call sites like GPIO.setmode(GPIO.BCM).
BCM = 11
OUT = 0
IN = 1
PUD_UP = 22
HIGH = 1
LOW = 0

_input_state: dict[int, int] = {}    # switch pin -> HIGH (not pressed) / LOW (pressed)
_output_state: dict[int, bool] = {}  # led pin -> bool


def setmode(mode: int) -> None:
    pass


def setup(pin: int, direction: int, pull_up_down: int | None = None) -> None:
    if direction == IN:
        _input_state.setdefault(pin, HIGH)
    elif direction == OUT:
        _output_state.setdefault(pin, False)


def output(pin: int, value: bool) -> None:
    _output_state[pin] = bool(value)


def input(pin: int) -> bool:
    return bool(_input_state.get(pin, HIGH))


def cleanup() -> None:
    pass


# --- simulator-only hooks, not part of the real RPi.GPIO interface ---
# The driver's simulator loop calls these to feed in mouse/keyboard input
# and to read back LED state for drawing the on-screen buttons.

def set_input_state(pin: int, pressed: bool) -> None:
    _input_state[pin] = LOW if pressed else HIGH


def get_output_state(pin: int) -> bool:
    return _output_state.get(pin, False)

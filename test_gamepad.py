"""Hot-plug roles and legacy shared-button compatibility without physical pads."""

import pytest

import gamepad
import hardware


class FakeJoystick:
    def __init__(self, identity: int) -> None:
        self.identity = identity
        self.buttons = [False] * 8
        self.axes = [0.0] * 6
        self.hat = (0, 0)

    def init(self):
        pass

    def quit(self):
        pass

    def get_instance_id(self):
        return self.identity

    def get_name(self):
        return "Test Xbox"

    def get_numbuttons(self):
        return len(self.buttons)

    def get_button(self, index: int):
        return self.buttons[index]

    def get_numaxes(self):
        return len(self.axes)

    def get_axis(self, index: int):
        return self.axes[index]

    def get_numhats(self):
        return 1

    def get_hat(self, index: int):
        return self.hat


@pytest.fixture
def devices(monkeypatch: pytest.MonkeyPatch):
    devices = [FakeJoystick(11), FakeJoystick(22)]
    monkeypatch.setattr(gamepad, "_joysticks", {})
    monkeypatch.setattr(gamepad, "_controllers", {})
    monkeypatch.setattr(gamepad, "_slots", [None, None])
    monkeypatch.setattr(gamepad, "sdl_controller", None)
    monkeypatch.setattr(hardware, "_gamepad_overrides", {})
    monkeypatch.setattr(gamepad.pygame.joystick, "get_init", lambda: True)
    monkeypatch.setattr(gamepad.pygame.joystick, "get_count", lambda: len(devices))
    monkeypatch.setattr(gamepad.pygame.joystick, "Joystick", lambda i: devices[i])
    return devices


def test_disconnect_does_not_move_wingmate_into_pilot_role(devices: list[FakeJoystick]):
    gamepad.poll(False)
    assert gamepad._slots == [11, 22]
    devices.pop(0)
    gamepad.poll(False)
    assert gamepad._slots == [None, 22]
    assert not gamepad.snapshot(0).connected
    assert gamepad.snapshot(1).connected
    devices.append(FakeJoystick(33))
    gamepad.poll(False)
    assert gamepad._slots == [33, 22]


def test_same_device_count_replacement_is_detected(devices: list[FakeJoystick]):
    gamepad.poll(False)
    devices[1] = FakeJoystick(44)
    gamepad.poll(False)
    assert gamepad._slots == [11, 44]
    assert 22 not in gamepad._joysticks


def test_legacy_buttons_and_independent_mode_do_not_leak(devices: list[FakeJoystick]):
    devices[0].buttons[0] = True
    gamepad.poll()
    assert hardware.buttons[hardware.Color.BLUE].is_pressed()
    gamepad.poll(False)
    assert not hardware._gamepad_overrides[hardware.buttons[hardware.Color.BLUE].switch_pin]
    assert gamepad.snapshot(0).fire
    assert not gamepad.snapshot(1).fire


def test_stick_activity_wakes_display_and_small_drift_does_not(devices: list[FakeJoystick]):
    gamepad.poll(False)
    devices[0].axes[0] = .1
    assert not gamepad.any_activity()
    devices[1].axes[0] = .7
    assert gamepad.any_activity()


def test_sdl_standard_mapping_uses_right_trigger_and_independent_sticks(devices: list[FakeJoystick]):
    gamepad.poll(False)
    p = gamepad.pygame
    class FakeController:
        def get_axis(self, index: int):
            return {p.CONTROLLER_AXIS_LEFTX: 16384, p.CONTROLLER_AXIS_RIGHTY: -32768,
                    p.CONTROLLER_AXIS_TRIGGERRIGHT: 24000}.get(index, 0)

        def get_button(self, index: int):
            return index == p.CONTROLLER_BUTTON_X

    gamepad._controllers[11] = FakeController()
    pad = gamepad.snapshot(0)
    assert pad.fire and pad.x and not pad.a
    assert pad.lx == .5
    assert pad.ry == -1
    assert not gamepad.snapshot(1).fire

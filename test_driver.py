"""Drives IdleMonitor directly -- the only piece of driver.py's game loop that's
plain logic rather than a pygame/hardware side effect. Never touches pygame.
"""

from driver import IDLE_TIMEOUT_MS, IdleMonitor


def test_stays_awake_before_the_timeout():
    monitor = IdleMonitor()
    assert monitor.update(0, any_pressed=False) is False
    assert monitor.update(IDLE_TIMEOUT_MS - 1, any_pressed=False) is False


def test_goes_idle_once_the_timeout_elapses_with_nothing_pressed():
    monitor = IdleMonitor()
    monitor.update(0, any_pressed=False)
    assert monitor.update(IDLE_TIMEOUT_MS, any_pressed=False) is True


def test_a_press_resets_the_idle_clock():
    monitor = IdleMonitor()
    monitor.update(0, any_pressed=False)
    monitor.update(IDLE_TIMEOUT_MS - 1, any_pressed=True)  # activity right before the deadline
    assert monitor.update(IDLE_TIMEOUT_MS, any_pressed=False) is False
    assert monitor.update(IDLE_TIMEOUT_MS - 1 + IDLE_TIMEOUT_MS, any_pressed=False) is True


def test_waking_press_is_swallowed_until_released():
    monitor = IdleMonitor()
    monitor.update(0, any_pressed=False)
    monitor.update(IDLE_TIMEOUT_MS, any_pressed=False)  # now idle

    assert monitor.update(IDLE_TIMEOUT_MS + 100, any_pressed=True) is True  # waking, still blanked
    assert monitor.update(IDLE_TIMEOUT_MS + 150, any_pressed=True) is True  # still held
    assert monitor.update(IDLE_TIMEOUT_MS + 200, any_pressed=False) is False  # released -- awake now

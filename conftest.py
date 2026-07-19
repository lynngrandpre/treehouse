"""Runs before any test module is imported. Forces simulator mode so that
importing hardware.py picks the in-memory sim_gpio backend instead of RPi.GPIO,
which isn't installed off the Pi."""

import os

os.environ["SIMULATOR"] = "1"

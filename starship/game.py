"""Treehouse state-machine adapter and keyboard / independent controller input."""

from __future__ import annotations

import math
from array import array
from dataclasses import replace
from pathlib import Path

import pygame

import gamepad
from common import Input, State
from hardware import BIG_RED_BUTTON_PIN, GPIO, buttons_in_order

from .model import SYSTEMS, Controls, Universe, load_game, save_game, save_path
from .render import Renderer


class Audio:
    """Small synthesized cues: no downloads, codecs or external assets needed."""

    def __init__(self) -> None:
        self.cache: dict[str, pygame.mixer.Sound] = {}
        self.enabled = True

    def play(self, sounds: list[str]) -> None:
        settings = pygame.mixer.get_init()
        if not self.enabled or settings is None:
            return
        pitches = {"laser": (680, .045), "heavy": (130, .18), "hit": (85, .05),
                   "explosion": (58, .23), "notice": (420, .09), "reward": (880, .23),
                   "shield": (360, .2), "boost": (180, .22), "repair": (560, .2),
                   "tractor": (240, .15), "jump": (1000, .35)}
        rate, size, channels = settings
        if size != -16:
            return
        for name in list(dict.fromkeys(sounds))[:3]:
            if name not in self.cache:
                hz, duration = pitches.get(name, (420, .09))
                samples = array("h")
                for i in range(int(rate * duration)):
                    envelope = (1 - i / (rate * duration)) ** 2
                    sample = int(math.sin(i * hz * math.tau / rate) * envelope * 2200)
                    samples.extend([sample] * channels)
                self.cache[name] = pygame.mixer.Sound(buffer=samples)
            self.cache[name].play()


class StarshipState:
    independent_gamepads = True

    def __init__(self, world: Universe | None = None, path: Path | None = None) -> None:
        self.path = path or save_path()
        self.world = world or load_game(self.path)
        self.mode = "title"
        self.return_mode = "title"
        self.selection = 0
        self.map_selection = self.world.campaign.system
        self.last_time: int | None = None
        self.last_save = 0.0
        self.started = False
        self.save_status = "Campaign autosaves"
        self.previous: set[str] = set()
        self.renderer: Renderer | None = None
        self.audio = Audio()
        self.pilot_connected = False
        self.wing_keyboard = False
        self.exit_requested = False
        self.await_release = False

    def save(self) -> bool:
        if getattr(self.world, "save_blocked", False):
            self.save_status = "Original save preserved. Start a new campaign to enable saving."
            return False
        try:
            save_game(self.world, self.path)
            self.last_save = self.world.time
            self.save_status = "Campaign saved"
            return True
        except (OSError, ValueError):
            self.save_status = "Save failed. Check free disk space and folder permissions."
            self.world.tell(self.save_status)
            return False

    def on_close(self) -> None:
        if self.started:
            self.save()
        for button in buttons_in_order:
            button.set_led(False)

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.selection = 0
        if mode == "flight":
            self.await_release = True

    def menu_items(self) -> list[tuple[str, str]]:
        c = self.world.campaign
        if self.mode == "title":
            return [("Continue voyage" if self.path.exists() or self.started else "Begin voyage", "play"),
                    ("Crew controls", "help"), ("New campaign", "new"), ("Treehouse games", "exit")]
        if self.mode == "dock":
            contract = ("Raider patrol / 600 cr" if c.system == 0 and c.deliveries and c.bounties < c.deliveries
                        else "Greenhouse delivery / 300 cr" if c.system == 0 else "Rescue survivors / 450 cr")
            return [("Contract: " + ("in progress" if c.mission else contract), "contract"),
                    ("Outfitter / upgrade your ship", "shop"), ("Trading exchange", "trade"),
                    ("Launch / leave port", "launch"), ("Save and return to games", "exit")]
        if self.mode == "shop":
            from .model import UPGRADE_NAMES, UPGRADES
            return [(f"{name}  {c.upgrades[key]}/3   " +
                     ("MAX" if c.upgrades[key] == 3 else f"{self.world.upgrade_price(i)} cr"), f"upgrade:{i}")
                    for i, (key, name) in enumerate(zip(UPGRADES, UPGRADE_NAMES))] + [("Back to port", "dock")]
        if self.mode == "trade":
            price = SYSTEMS[c.system]["price"]
            return [(f"Buy supplies / {price} cr each", "buy"),
                    (f"Sell supplies / {price} cr each", "sell"), ("Back to port", "dock")]
        if self.mode == "pause":
            return [("Resume flight", "flight"), ("Crew controls", "help"),
                    ("Sound: " + ("ON" if self.audio.enabled else "OFF"), "sound"),
                    ("Save and return to games", "exit")]
        if self.mode == "confirm_new":
            return [("Keep current campaign", "title"), ("Start fresh / replace campaign", "reset")]
        if self.mode == "confirm_tow":
            return [("Keep exploring", "map"), ("Call tug / up to 60 credits", "tow")]
        return []

    def dispatch(self, action: str) -> None:
        w = self.world
        if action == "play":
            self.started = True
            self.set_mode("flight")
            w.tell("Welcome aboard. Pilot: X / E to dock, Y / Tab for chart.")
        elif action == "help":
            self.return_mode = self.mode
            self.set_mode("help")
        elif action == "new":
            self.set_mode("confirm_new")
        elif action == "reset":
            # Keep a recoverable copy, including when the original was malformed.
            try:
                if self.path.exists():
                    backup = self.path.with_suffix(".previous.json")
                    backup.write_bytes(self.path.read_bytes())
            except OSError:
                w.tell("Could not back up the current save. New campaign cancelled.")
                self.set_mode("title")
                return
            self.world = Universe()
            self.started = True
            self.save()
            self.set_mode("flight")
        elif action == "exit":
            self.on_close()
            self.exit_requested = True
        elif action == "contract":
            w.accept_contract()
            self.save()
        elif action in ("shop", "trade", "dock", "flight", "title", "map"):
            self.set_mode(action)
        elif action == "launch":
            self.save()
            self.set_mode("flight")
            w.tell("Departure cleared. Safe travels, Treehouse.")
        elif action == "sound":
            self.audio.enabled = not self.audio.enabled
        elif action.startswith("upgrade:"):
            w.buy_upgrade(int(action.split(":")[1]))
            self.save()
        elif action in ("buy", "sell"):
            w.trade(action == "buy")
            self.save()
        elif action == "tow":
            w.recover()
            w.dock()
            self.save()
            self.set_mode("dock")

    def _read(self) -> tuple[Controls, set[str]]:
        keys = pygame.key.get_pressed() if pygame.display.get_init() else None

        def key(code: int) -> bool:
            return bool(keys is not None and keys[code])

        pilot, wing = gamepad.snapshot(0), gamepad.snapshot(1)
        self.pilot_connected = pilot.connected
        names = set()
        # Read physical GPIO only: controller buttons must never fire console systems.
        modules = tuple(not GPIO.input(b.switch_pin) or key(k) for b, k in zip(
            buttons_in_order, (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5)))
        for i, pressed in enumerate(modules):
            if pressed:
                names.add(f"module{i}")
        tests = {
            "up": pilot.up or pilot.ly < -.6 or key(pygame.K_UP) or key(pygame.K_w),
            "down": pilot.down or pilot.ly > .6 or key(pygame.K_DOWN) or key(pygame.K_s),
            "select": pilot.a or key(pygame.K_RETURN),
            "back": pilot.b or key(pygame.K_BACKSPACE),
            "map": pilot.y or key(pygame.K_TAB),
            "dock": pilot.x or key(pygame.K_e),
            "pause": pilot.start or pilot.back or key(pygame.K_ESCAPE) or key(pygame.K_p),
            "toggle": wing.x or key(pygame.K_o),
            "wing_keyboard": key(pygame.K_F2),
            "big_red": not GPIO.input(BIG_RED_BUTTON_PIN),
        }
        names.update(name for name, held in tests.items() if held)
        aim = math.atan2(pilot.ly, pilot.lx) if math.hypot(pilot.lx, pilot.ly) > .25 else None
        wing_x = wing.lx or float(key(pygame.K_l)) - float(key(pygame.K_j))
        wing_y = wing.ly or float(key(pygame.K_k)) - float(key(pygame.K_i))
        if math.hypot(wing_x, wing_y) > 1:
            length = math.hypot(wing_x, wing_y)
            wing_x, wing_y = wing_x / length, wing_y / length
        wing_aim = math.atan2(wing.ry, wing.rx) if math.hypot(wing.rx, wing.ry) > .25 else None
        controls = Controls(
            turn=float(key(pygame.K_RIGHT) or key(pygame.K_d)) - float(key(pygame.K_LEFT) or key(pygame.K_a)),
            thrust=max(math.hypot(pilot.lx, pilot.ly), float(key(pygame.K_UP) or key(pygame.K_w))),
            aim=aim, fire=pilot.fire or key(pygame.K_SPACE),
            brake=pilot.b or key(pygame.K_DOWN) or key(pygame.K_s),
            wing_x=wing_x, wing_y=wing_y, wing_aim=wing_aim,
            wing_fire=wing.fire or key(pygame.K_u),
            wing_toggle="toggle" in names and "toggle" not in self.previous,
            wing_present=wing.connected or self.wing_keyboard, modules=modules,
        )
        return controls, names

    def next_state(self, input: Input) -> State | None:
        controls, names = self._read()
        pressed = names - self.previous
        self.previous = names
        dt = 0 if self.last_time is None else max(0, input.current_time - self.last_time) / 1000
        self.last_time = input.current_time
        if "big_red" in pressed:
            self.on_close()
            return None
        if "wing_keyboard" in pressed:
            self.wing_keyboard = not self.wing_keyboard
        if self.mode == "flight":
            if self.await_release:
                if not any(controls.modules) and not controls.fire and not controls.wing_fire:
                    self.await_release = False
                controls = replace(controls, modules=(False,) * 5, fire=False, wing_fire=False)
            if "pause" in pressed:
                self.save()
                self.set_mode("pause")
            elif "map" in pressed:
                self.map_selection = self.world.campaign.system
                self.set_mode("map")
            elif "dock" in pressed:
                if self.world.dock():
                    self.save()
                    self.set_mode("dock")
            else:
                self.world.step(dt, controls)
                if self.world.recovered:
                    self.world.dock()
                    self.save()
                    self.set_mode("dock")
                if self.world.time - self.last_save >= 20:
                    self.save()
        elif self.mode == "map":
            if pressed & {"up", "module0"}:
                self.map_selection = (self.map_selection - 1) % 3
            if pressed & {"down", "module1"}:
                self.map_selection = (self.map_selection + 1) % 3
            if pressed & {"select", "module2"} and self.world.jump(self.map_selection):
                self.save()
                self.set_mode("flight")
            if pressed & {"module3"}:
                self.set_mode("confirm_tow")
            elif pressed & {"back", "map", "pause", "module4"}:
                self.set_mode("flight")
        elif self.mode == "help":
            if pressed & {"back", "select", "pause", "module2", "module4"}:
                self.set_mode(self.return_mode)
        else:
            items = self.menu_items()
            if items:
                if pressed & {"up", "module0"}:
                    self.selection = (self.selection - 1) % len(items)
                if pressed & {"down", "module1"}:
                    self.selection = (self.selection + 1) % len(items)
                if pressed & {"select", "module2"}:
                    self.dispatch(items[self.selection][1])
                elif pressed & {"back", "pause", "module4"}:
                    self.set_mode("dock" if self.mode in ("shop", "trade") else
                                  "flight" if self.mode in ("pause", "confirm_tow") else "title")
        for i, button in enumerate(buttons_in_order):
            ready = self.world.module_ready(i)
            if i == 1:
                ready = ready and self.world.ship.hull < 140
            button.set_led(ready if self.mode == "flight" else i in (0, 1, 2, 4) or self.mode == "map")
        self.audio.play(self.world.sounds)
        self.world.sounds.clear()
        return None if self.exit_requested else self

    def draw(self, surface: pygame.Surface) -> None:
        if self.renderer is None:
            self.renderer = Renderer()
        self.renderer.draw(surface, self)

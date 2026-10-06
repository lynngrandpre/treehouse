"""Campaign, flight, persistence, and physical/controller isolation regressions."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pygame
import pytest

import gamepad
import sim_gpio
from common import Input
from hardware import BIG_RED_BUTTON_PIN, Color, buttons_in_order, set_button_override
from starship.game import StarshipState
from starship.model import Controls, Enemy, Pickup, Shot, Universe, load_game, save_game


@pytest.fixture(autouse=True)
def clean_inputs(monkeypatch: pytest.MonkeyPatch):
    for b in buttons_in_order:
        sim_gpio.set_input_state(b.switch_pin, False)
    sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, False)
    for color in Color:
        set_button_override(color, False)
    monkeypatch.setattr(gamepad, "snapshot", lambda slot: gamepad.Pad())
    yield
    for b in buttons_in_order:
        sim_gpio.set_input_state(b.switch_pin, False)
    sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, False)
    for color in Color:
        set_button_override(color, False)


def advance(world: Universe, seconds: float, controls: Controls | None = None):
    for _ in range(round(seconds * 60)):
        world.step(1 / 60, controls or Controls())


def at_port(world: Universe):
    world.ship.x, world.ship.y = world.port_position
    assert world.dock()


def test_delivery_and_rescue_campaign_round_trip():
    w = Universe()
    at_port(w)
    assert w.accept_contract()
    assert w.campaign.used_cargo == 4
    assert w.jump(1)
    assert w.jump(2)
    at_port(w)
    assert w.campaign.deliveries == 1
    assert w.campaign.credits == 480
    assert w.campaign.scrap == 1
    assert w.campaign.used_cargo == 0
    assert w.accept_contract()
    assert w.jump(1)
    pod = next(p for p in w.pickups if p.kind == "pod")
    w.enemies.clear()
    w.pickups = [pod]
    w.ship.x, w.ship.y = pod.x - 60, pod.y
    assert w.activate(4)
    advance(w, 1.3)
    assert w.campaign.mission_progress == 1
    assert w.jump(2)
    at_port(w)
    assert w.campaign.rescues == 1
    assert w.campaign.credits == 930
    assert w.campaign.rangers == 1
    assert w.finish_contract() is False  # can't cash the same contract twice


def test_jump_rejects_disconnected_routes_close_threats_and_empty_fuel():
    w = Universe()
    assert not w.jump(2)
    assert w.campaign.fuel == 4
    w.enemies = [Enemy(w.ship.x + 100, w.ship.y)]
    assert not w.jump(1)
    w.enemies.clear()
    w.campaign.fuel = 0
    assert not w.jump(1)
    w.recover()
    assert w.campaign.fuel == 4
    assert w.campaign.credits == 120


def test_reserved_mission_cargo_cannot_be_sold_or_overfilled():
    w = Universe()
    assert w.accept_contract()
    assert not w.trade(False)
    for _ in range(4):
        assert w.trade(True)
    assert not w.trade(True)
    assert w.campaign.used_cargo == w.campaign.capacity
    for _ in range(4):
        assert w.trade(False)
    assert w.campaign.used_cargo == 4
    assert not w.trade(False)


def test_trade_profit_and_upgrade_change_ship_rules():
    w = Universe()
    assert w.trade(True)
    assert w.jump(1) and w.jump(2)
    assert w.trade(False)
    assert w.campaign.credits == 215
    assert w.buy_upgrade(1)
    assert w.max_shield == 120
    assert w.campaign.credits == 15
    assert not w.buy_upgrade(1)
    w.campaign.credits = 5000
    assert w.buy_upgrade(1) and w.buy_upgrade(1)
    assert not w.buy_upgrade(1)


def test_movement_braking_and_pause_time_clamp():
    w = Universe()
    y = w.ship.y
    advance(w, 1, Controls(thrust=1))
    assert w.ship.y < y - 40
    speed = math.hypot(w.ship.vx, w.ship.vy)
    advance(w, 1, Controls(brake=True))
    assert math.hypot(w.ship.vx, w.ship.vy) < speed / 10
    old_y = w.ship.y
    w.step(300, Controls(thrust=1))
    assert abs(w.ship.y - old_y) < 30


@pytest.mark.parametrize("index", range(5))
def test_systems_use_shared_energy_and_cooldowns(index: int):
    w = Universe()
    w.ship.hull = 90
    energy = w.ship.energy
    assert w.activate(index)
    assert w.ship.energy < energy
    assert not w.activate(index)
    w.cooldowns[index] = 0
    w.ship.energy = 0
    assert not w.activate(index)


def test_shield_and_repair_actually_protect_and_restore_hull():
    w = Universe()
    w.ship.shield = 0
    w.ship.hull = 60
    assert w.activate(2)
    w.damage_ship(100)
    assert w.ship.hull == 60
    assert w.activate(1)
    advance(w, 2)
    assert w.ship.hull > 80


def test_heavy_cannon_disables_and_tractor_captures_bounty():
    w = Universe()
    w.campaign.mission = "bounty"
    e = Enemy(w.ship.x + 80, w.ship.y, bounty=True)
    w.enemies = [e]
    w.ship.angle = 0
    assert w.activate(0)
    advance(w, .15)
    assert e.disabled and e.hull > 0
    assert w.activate(4)
    advance(w, 1.3)
    assert not w.enemies
    assert w.campaign.captures == 1
    assert w.campaign.mission_progress == 1
    assert w.campaign.credits == 300


def test_kills_complete_bounty_and_pay_once():
    w = Universe()
    w.campaign.deliveries = 1
    assert w.accept_contract()
    assert w.campaign.mission == "bounty"
    w.jump(1)
    for e in list(w.enemies):
        e.hull = 5
        w.shots.append(Shot(e.x, e.y, 0, 0, 100, True))
    w._shots(.01)
    assert w.campaign.mission_progress == 3
    assert w.jump(0)
    at_port(w)
    assert w.campaign.bounties == 1
    assert w.campaign.credits == 885


def test_wingmate_launch_dock_range_leash_and_disconnect():
    w = Universe()
    w.step(.01, Controls(wing_present=True, wing_toggle=True))
    assert not w.wing_docked
    advance(w, 3, Controls(wing_present=True, wing_x=1))
    assert math.dist((w.wing_x, w.wing_y), (w.ship.x, w.ship.y)) <= 320.01
    w.step(.01, Controls(wing_present=True, wing_toggle=True))
    assert not w.wing_docked  # too far away to dock
    w.step(.01, Controls(wing_present=False))
    assert w.wing_docked


def test_wingmate_can_collect_salvage_and_recover_to_turret():
    w = Universe()
    w.step(.01, Controls(wing_present=True, wing_toggle=True))
    w.pickups = [Pickup(w.wing_x, w.wing_y)]
    w.step(.01, Controls(wing_present=True))
    assert w.campaign.cargo == 1
    w.wing_hull = 5
    w.shots = [Shot(w.wing_x, w.wing_y, 0, 0, 10, False)]
    w._shots(.01)
    assert w.wing_docked
    assert w.wing_hull == 0
    advance(w, 4, Controls(wing_present=True))
    assert w.wing_hull > 25


def test_auto_turret_does_not_destroy_disabled_capture_targets():
    w = Universe()
    w.enemies = [Enemy(w.ship.x + 100, w.ship.y, disabled=True)]
    advance(w, 2)
    assert w.enemies[0].hull == 66
    w.enemies[0].disabled = False
    advance(w, .1)
    assert w.enemies[0].hull < 66


def test_ship_loss_preserves_contract_and_recovers_without_negative_money():
    w = Universe()
    w.accept_contract()
    w.campaign.credits = 10
    w.campaign.cargo = 2
    w.ship.hull = -1
    w.step(.01, Controls())
    assert w.recovered and w.near_port
    assert w.campaign.credits == 0
    assert w.campaign.mission == "delivery"
    assert w.campaign.cargo == 2
    assert w.ship.hull == 140


def test_save_reload_preserves_encounter_and_contract(tmp_path: Path):
    path = tmp_path / "campaign.json"
    w = Universe()
    w.accept_contract()
    w.jump(1)
    w.enemies[0].disabled = True
    w.enemies[0].hull = 12
    w.pickups.pop()
    w.ship.x = 111.5
    save_game(w, path)
    loaded = load_game(path)
    assert loaded.campaign == w.campaign
    assert loaded.ship == w.ship
    assert loaded.enemies == w.enemies
    assert loaded.pickups == w.pickups
    assert not path.with_suffix('.tmp').exists()


@pytest.mark.parametrize("bad", ['broken', '[]', '{"version":99}', '{"version":1,"campaign":null}'])
def test_bad_save_is_preserved_and_never_automatically_overwritten(tmp_path: Path, bad: str):
    path = tmp_path / "campaign.json"
    path.write_text(bad)
    state = StarshipState(path=path)
    assert state.world.save_blocked
    state.started = True
    state.on_close()
    assert path.read_text() == bad
    state.dispatch("reset")
    assert path.with_suffix(".previous.json").read_text() == bad
    assert json.loads(path.read_text())["version"] == 1


def test_failed_atomic_save_leaves_previous_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    path = tmp_path / "campaign.json"
    w = Universe()
    save_game(w, path)
    original = path.read_text()
    w.campaign.credits = 1000
    def fail_replace(self: Path, target: Path):
        raise OSError("disk error")
    monkeypatch.setattr(type(path), "replace", fail_replace)
    with pytest.raises(OSError):
        save_game(w, path)
    assert path.read_text() == original


def test_controller_overrides_cannot_activate_console_modules(tmp_path: Path):
    state = StarshipState(Universe(), tmp_path / "save.json")
    for color in Color:
        set_button_override(color, True)
    controls, _ = state._read()
    assert not any(controls.modules)
    sim_gpio.set_input_state(buttons_in_order[2].switch_pin, True)
    controls, _ = state._read()
    assert controls.modules == (False, False, True, False, False)


def test_panel_menu_debounce_and_big_red_saves(tmp_path: Path):
    path = tmp_path / "save.json"
    state = StarshipState(Universe(), path)
    inp = Input(buttons_in_order, 100)
    sim_gpio.set_input_state(buttons_in_order[1].switch_pin, True)
    for _ in range(5):
        state.next_state(inp)
    assert state.selection == 1
    sim_gpio.set_input_state(buttons_in_order[1].switch_pin, False)
    state.next_state(inp)
    sim_gpio.set_input_state(buttons_in_order[1].switch_pin, True)
    state.next_state(inp)
    assert state.selection == 2
    state.started = True
    sim_gpio.set_input_state(BIG_RED_BUTTON_PIN, True)
    assert state.next_state(inp) is None
    assert path.exists()


def test_pause_does_not_advance_combat_or_cooldowns(tmp_path: Path):
    state = StarshipState(Universe(), tmp_path / "save.json")
    state.mode = "pause"
    state.world.cooldowns[0] = 4
    state.next_state(Input(buttons_in_order, 1))
    state.next_state(Input(buttons_in_order, 120_000))
    assert state.world.cooldowns[0] == 4
    assert state.world.time == 0


def test_held_menu_confirm_does_not_fire_a_ship_system(tmp_path: Path):
    state = StarshipState(Universe(), tmp_path / "save.json")
    sim_gpio.set_input_state(buttons_in_order[2].switch_pin, True)
    state.next_state(Input(buttons_in_order, 100))
    assert state.mode == "flight"
    state.next_state(Input(buttons_in_order, 150))
    assert state.world.shield_timer == 0
    assert state.world.ship.energy == 100
    sim_gpio.set_input_state(buttons_in_order[2].switch_pin, False)
    state.next_state(Input(buttons_in_order, 200))
    sim_gpio.set_input_state(buttons_in_order[2].switch_pin, True)
    state.next_state(Input(buttons_in_order, 250))
    assert state.world.shield_timer > 0


def test_all_screens_render_at_device_and_laptop_sizes(tmp_path: Path):
    pygame.font.init()
    state = StarshipState(Universe(), tmp_path / "save.json")
    for size in ((800, 480), (1000, 600), (1280, 720)):
        surface = pygame.Surface(size)
        for mode in ("title", "flight", "dock", "shop", "trade", "help", "map", "pause", "confirm_new", "confirm_tow"):
            state.mode = mode
            state.draw(surface)
    # Battle state exercises beam, projectiles, repairs, shield and escort art.
    state.world.jump(1)
    state.world.ship.hull = 80
    state.world.ship.energy = 100
    for index in (0, 1, 2, 4):
        state.world.activate(index)
    state.world.wing_docked = False
    state.mode = "flight"
    state.draw(pygame.Surface((800, 480)))

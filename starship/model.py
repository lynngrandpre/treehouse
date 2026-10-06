"""Deterministic game rules, independent of GPIO, displays and controllers.

Coordinates are world units. All timers use seconds, advanced only by step().
The versioned save contains the campaign, ship and current encounter, so quitting
in space neither loses mission cargo nor respawns a cleared fight.
"""

from __future__ import annotations

import json
import math
import os
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TypedDict


class System(TypedDict):
    name: str
    subtitle: str
    faction: str
    port: str | None
    color: tuple[int, int, int]
    planet: tuple[int, int]
    description: str
    price: int
    neighbors: list[int]

TAU = math.tau
WORLD_LIMIT = 1250
SYSTEMS: list[System] = [
    {"name": "Canopy", "subtitle": "VERDANT REACH", "faction": "Star Rangers",
     "port": "Canopy Anchorage", "color": (86, 213, 163), "planet": (-370, -140),
     "description": "A sheltered green world. Every great voyage starts small.",
     "price": 35, "neighbors": [1]},
    {"name": "The Drift", "subtitle": "RUSTBELT FRONTIER", "faction": "Freebooters",
     "port": None, "color": (243, 164, 91), "planet": (420, -380),
     "description": "Broken ships, valuable salvage. Keep your shields ready.",
     "price": 0, "neighbors": [0, 2]},
    {"name": "Lantern", "subtitle": "ECHO SHOAL", "faction": "Scrap Union",
     "port": "Lantern Outpost", "color": (157, 153, 255), "planet": (360, 100),
     "description": "A moon colony at the edge of the chart. They need a crew.",
     "price": 70, "neighbors": [1]},
]
MODULES = ("cannon", "repair", "shield", "boost", "tractor")
MODULE_NAMES = ("CANNON", "REPAIR", "SHIELD", "BOOST", "TRACTOR")
MODULE_COLORS = ((249, 101, 106), (107, 226, 166), (100, 183, 255),
                 (255, 210, 101), (225, 232, 245))
COSTS = (26, 22, 20, 18, 14)
COOLDOWNS = (4.0, 8.0, 6.0, 5.0, 3.0)
UPGRADES = ("cannon", "shield", "engine", "cargo", "tractor")
UPGRADE_NAMES = ("Arc cannon", "Shield lattice", "Vector engines", "Cargo racks", "Tractor array")
UPGRADE_DESCRIPTIONS = (
    "Harder-hitting main guns and heavy cannon.", "More shields, faster recovery.",
    "Faster thrust and a longer boost.", "Four more cargo spaces per level.",
    "Reach farther. Recover wrecks more quickly.",
)


def clamp(value: float, low: float, high: float) -> float:
    return min(high, max(low, value))


def angle_diff(target: float, angle: float) -> float:
    return (target - angle + math.pi) % TAU - math.pi


@dataclass
class Controls:
    turn: float = 0
    thrust: float = 0
    aim: float | None = None
    fire: bool = False
    brake: bool = False
    wing_x: float = 0
    wing_y: float = 0
    wing_aim: float | None = None
    wing_fire: bool = False
    wing_toggle: bool = False
    wing_present: bool = False
    modules: tuple[bool, ...] = (False,) * 5


@dataclass
class Ship:
    x: float = 0
    y: float = 70
    vx: float = 0
    vy: float = 0
    angle: float = -math.pi / 2
    hull: float = 140
    shield: float = 90
    energy: float = 100


@dataclass
class Enemy:
    x: float
    y: float
    hull: float = 66
    angle: float = 0
    cooldown: float = 1
    disabled: bool = False
    bounty: bool = False


@dataclass
class Shot:
    x: float
    y: float
    vx: float
    vy: float
    damage: float
    friendly: bool
    life: float = 1.5
    heavy: bool = False


@dataclass
class Pickup:
    x: float
    y: float
    kind: str = "salvage"


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    color: tuple[int, int, int]


@dataclass
class Campaign:
    credits: int = 180
    fuel: int = 4
    system: int = 0
    cargo: int = 0
    mission: str = ""
    mission_progress: int = 0
    deliveries: int = 0
    rescues: int = 0
    bounties: int = 0
    captures: int = 0
    rangers: int = 0
    scrap: int = 0
    visited: list[int] = field(default_factory=lambda: [0])
    upgrades: dict[str, int] = field(default_factory=lambda: dict.fromkeys(UPGRADES, 0))

    @property
    def capacity(self) -> int:
        return 8 + 4 * self.upgrades["cargo"]

    @property
    def used_cargo(self) -> int:
        return self.cargo + (4 if self.mission == "delivery" else 0)


class Universe:
    def __init__(self, campaign: Campaign | None = None, seed: int = 42) -> None:
        self.campaign = campaign or Campaign()
        self.ship = Ship()
        self.rng = random.Random(seed)
        self.enemies: list[Enemy] = []
        self.shots: list[Shot] = []
        self.pickups: list[Pickup] = []
        self.particles: list[Particle] = []
        self.cooldowns = [0.0] * 5
        self.shield_timer = self.boost_timer = self.repair_timer = 0.0
        self.tractor_timer = 0.0
        self.tractor_target: tuple[float, float] | None = None
        self.tractor_progress = 0.0
        self.gun_timer = self.wing_gun_timer = 0.0
        self.damage_timer = self.time = 0.0
        self.wing_x, self.wing_y = 60.0, 80.0
        self.wing_angle = -math.pi / 2
        self.wing_hull = 60.0
        self.wing_docked = True
        self.wing_present = False
        self.recovered = False
        self.save_blocked = False
        self.messages: list[tuple[str, float]] = []
        self.sounds: list[str] = []
        self.enter_system(self.campaign.system, initial=True)

    @property
    def max_shield(self) -> int:
        return 90 + self.campaign.upgrades["shield"] * 30

    @property
    def port_position(self) -> tuple[float, float]:
        return (-220, 70) if self.campaign.system == 0 else (130, 120)

    @property
    def near_port(self) -> bool:
        return bool(SYSTEMS[self.campaign.system]["port"]) and math.dist(
            (self.ship.x, self.ship.y), self.port_position) < 165

    @property
    def danger_near(self) -> bool:
        return any(not e.disabled and math.dist((e.x, e.y), (self.ship.x, self.ship.y)) < 380
                   for e in self.enemies)

    @property
    def objective(self) -> str:
        c = self.campaign
        if c.mission == "delivery":
            return "Deliver greenhouse parts to Lantern Outpost"
        if c.mission == "rescue":
            return ("Return survivors to Lantern Outpost" if c.mission_progress
                    else "Recover the escape pod in The Drift: use TRACTOR")
        if c.mission == "bounty":
            return ("Claim your bounty at Canopy Anchorage" if c.mission_progress >= 3
                    else f"Clear the marked raiders in The Drift: {c.mission_progress}/3")
        return "Dock at a port to take a contract, trade and upgrade"

    def tell(self, message: str, sound: str = "notice") -> None:
        self.messages.append((message, 5.0))
        self.messages = self.messages[-3:]
        self.sounds.append(sound)

    def burst(self, x: float, y: float, color: tuple[int, int, int], count: int = 15) -> None:
        for _ in range(count):
            angle = self.rng.uniform(0, TAU)
            speed = self.rng.uniform(25, 140)
            self.particles.append(Particle(x, y, math.cos(angle) * speed,
                                           math.sin(angle) * speed, self.rng.uniform(.2, .8), color))
        self.particles = self.particles[-180:]

    def enter_system(self, system: int, initial: bool = False) -> None:
        self.campaign.system = system
        if system not in self.campaign.visited:
            self.campaign.visited.append(system)
        self.ship.x, self.ship.y = ((-100, 70) if system == 0 else (-450, 240))
        self.ship.vx = self.ship.vy = 0
        self.wing_x, self.wing_y = self.ship.x + 60, self.ship.y + 30
        self.wing_docked = True
        self.shots.clear()
        self.particles.clear()
        self.tractor_timer = self.tractor_progress = 0
        self.tractor_target = None
        self.pickups = []
        self.enemies = []
        if system == 1:
            bounty = self.campaign.mission == "bounty"
            count = max(0, 3 - self.campaign.mission_progress) if bounty else 2
            self.enemies = [Enemy(240 + i * 160, -160 + i * 120,
                                  cooldown=1 + i * .5, bounty=bounty) for i in range(count)]
            self.pickups = [Pickup(-230, 120), Pickup(310, 360), Pickup(-140, -240)]
            if self.campaign.mission == "rescue" and not self.campaign.mission_progress:
                self.pickups.append(Pickup(-40, -220, "pod"))
        if not initial:
            self.tell(f"Jump complete. Welcome to {SYSTEMS[system]['name']}.", "jump")

    def jump(self, destination: int) -> bool:
        if destination not in SYSTEMS[self.campaign.system]["neighbors"]:
            self.tell("Choose a connected system.")
            return False
        if self.campaign.fuel <= 0:
            self.tell("No jump fuel. Call the rescue tug from the chart.")
            return False
        if self.danger_near:
            self.tell("Enemy too close! Boost clear before jumping.")
            return False
        self.campaign.fuel -= 1
        self.enter_system(destination)
        return True

    def module_ready(self, index: int) -> bool:
        return self.cooldowns[index] <= 0 and self.ship.energy >= COSTS[index]

    def activate(self, index: int) -> bool:
        if not self.module_ready(index):
            return False
        if index == 1 and self.ship.hull >= 140:
            return False
        self.ship.energy -= COSTS[index]
        self.cooldowns[index] = COOLDOWNS[index]
        if index == 0:
            self.shoot(self.ship.x, self.ship.y, self.ship.angle, True, heavy=True)
            self.sounds.append("heavy")
        elif index == 1:
            self.repair_timer = 3.0
            self.tell("Repair drones deployed.", "repair")
        elif index == 2:
            self.shield_timer = 2.6
            self.ship.shield = min(self.max_shield, self.ship.shield + 18)
            self.sounds.append("shield")
        elif index == 3:
            self.boost_timer = 1.8 + self.campaign.upgrades["engine"] * .3
            self.sounds.append("boost")
        else:
            self.tractor_timer = 3.0
            self.tractor_progress = 0
            self.sounds.append("tractor")
        return True

    def shoot(self, x: float, y: float, angle: float, friendly: bool,
              heavy: bool = False) -> None:
        speed = 780 if friendly else 310
        damage = ((52 if heavy else 12) + self.campaign.upgrades["cannon"] * 5
                  if friendly else 10)
        self.shots.append(Shot(x + math.cos(angle) * 28, y + math.sin(angle) * 28,
                               math.cos(angle) * speed, math.sin(angle) * speed,
                               damage, friendly, 1.8, heavy))

    def damage_ship(self, damage: float) -> None:
        if self.shield_timer > 0:
            damage *= .12
        absorbed = min(self.ship.shield, damage)
        self.ship.shield -= absorbed
        self.ship.hull -= damage - absorbed
        self.damage_timer = .2
        self.sounds.append("hit")

    def _tractor(self, dt: float) -> None:
        self.tractor_target = None
        if self.tractor_timer <= 0:
            self.tractor_progress = 0
            return
        radius = 240 + self.campaign.upgrades["tractor"] * 65
        targets: list[Pickup | Enemy] = list(self.pickups) + [e for e in self.enemies if e.disabled]
        targets = [t for t in targets if math.dist((t.x, t.y), (self.ship.x, self.ship.y)) < radius]
        if not targets:
            self.tractor_progress = 0
            return
        target = min(targets, key=lambda t: math.dist((t.x, t.y), (self.ship.x, self.ship.y)))
        self.tractor_target = target.x, target.y
        self.tractor_progress += dt * (1 + .3 * self.campaign.upgrades["tractor"])
        if self.tractor_progress < 1.15:
            return
        if isinstance(target, Enemy):
            self.enemies.remove(target)
            self.campaign.credits += 120
            self.campaign.captures += 1
            if target.bounty:
                self.campaign.mission_progress += 1
            self.tell("Raider secured! Salvage rights: +120 credits.", "reward")
        elif target.kind == "pod":
            self.pickups.remove(target)
            self.campaign.mission_progress = 1
            self.tell("Survivors aboard! Return them to Lantern.", "reward")
        elif self.campaign.used_cargo < self.campaign.capacity:
            self.pickups.remove(target)
            self.campaign.cargo += 1
            self.tell("Salvage aboard. Sell it at a port.", "reward")
        else:
            self.tell("Cargo hold full. Sell supplies at a port.")
            self.tractor_timer = 0
        self.tractor_progress = 0

    def step(self, dt: float, controls: Controls) -> None:
        # Clamp gaps caused by window dragging, suspension, or a sleeping display.
        dt = clamp(dt, 0, .05)
        self.time += dt
        self.recovered = False
        self.messages = [(m, t - dt) for m, t in self.messages if t > dt]
        self.cooldowns = [max(0, t - dt) for t in self.cooldowns]
        for name in ("shield_timer", "boost_timer", "repair_timer", "tractor_timer",
                     "gun_timer", "wing_gun_timer", "damage_timer"):
            setattr(self, name, max(0, getattr(self, name) - dt))
        s = self.ship
        s.energy = min(100, s.energy + dt * 10)
        s.shield = min(self.max_shield, s.shield + dt * (2 + self.campaign.upgrades["shield"]))
        if self.repair_timer > 0:
            s.hull = min(140, s.hull + dt * 13)
        for index, held in enumerate(controls.modules):
            if held:
                self.activate(index)
        if controls.aim is not None:
            s.angle += clamp(angle_diff(controls.aim, s.angle), -3.4 * dt, 3.4 * dt)
        else:
            s.angle += controls.turn * 3.1 * dt
        thrust = max(controls.thrust, 1 if self.boost_timer > 0 else 0)
        acceleration = (180 + self.campaign.upgrades["engine"] * 28) * (2.5 if self.boost_timer > 0 else 1)
        s.vx += math.cos(s.angle) * thrust * acceleration * dt
        s.vy += math.sin(s.angle) * thrust * acceleration * dt
        drag = math.exp(-dt * (4.5 if controls.brake else .48))
        s.vx *= drag
        s.vy *= drag
        speed = math.hypot(s.vx, s.vy)
        maximum = (300 + self.campaign.upgrades["engine"] * 35) * (1.7 if self.boost_timer > 0 else 1)
        if speed > maximum:
            s.vx *= maximum / speed
            s.vy *= maximum / speed
        s.x = clamp(s.x + s.vx * dt, -WORLD_LIMIT, WORLD_LIMIT)
        s.y = clamp(s.y + s.vy * dt, -WORLD_LIMIT, WORLD_LIMIT)
        if controls.fire and self.gun_timer <= 0:
            self.shoot(s.x, s.y, s.angle, True)
            self.gun_timer = .19
            self.sounds.append("laser")
        self._wing(dt, controls)
        self._enemies(dt)
        self._shots(dt)
        self._tractor(dt)
        for p in self.particles:
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.life -= dt
        self.particles = [p for p in self.particles if p.life > 0]
        if s.hull <= 0:
            self.recover()

    def _wing(self, dt: float, c: Controls) -> None:
        self.wing_present = c.wing_present
        if not c.wing_present:
            self.wing_docked = True
        if c.wing_toggle and c.wing_present:
            if self.wing_docked:
                if self.wing_hull < 25:
                    self.tell("Escort repairing. Turret ready while you wait.")
                else:
                    self.wing_docked = False
                    self.wing_x, self.wing_y = self.ship.x + 55, self.ship.y + 30
                    self.tell("Wingmate launched.")
            elif math.dist((self.wing_x, self.wing_y), (self.ship.x, self.ship.y)) < 150:
                self.wing_docked = True
                self.tell("Wingmate docked. Turret online.")
            else:
                self.tell("Fly closer to the mothership to dock.")
        if self.wing_docked:
            self.wing_x, self.wing_y = self.ship.x, self.ship.y
            self.wing_hull = min(60, self.wing_hull + dt * 8)
        else:
            self.wing_x += c.wing_x * 330 * dt
            self.wing_y += c.wing_y * 330 * dt
            dx, dy = self.wing_x - self.ship.x, self.wing_y - self.ship.y
            distance = math.hypot(dx, dy)
            # A visible flight radius keeps both players on the shared display.
            if distance > 320:
                self.wing_x = self.ship.x + dx / distance * 320
                self.wing_y = self.ship.y + dy / distance * 320
            for pickup in list(self.pickups):
                if (pickup.kind == "salvage" and self.campaign.used_cargo < self.campaign.capacity
                        and math.dist((pickup.x, pickup.y), (self.wing_x, self.wing_y)) < 27):
                    self.pickups.remove(pickup)
                    self.campaign.cargo += 1
                    self.tell("Wingmate recovered supplies!", "reward")
        if c.wing_aim is not None:
            self.wing_angle = c.wing_aim
        elif abs(c.wing_x) + abs(c.wing_y) > .2:
            self.wing_angle = math.atan2(c.wing_y, c.wing_x)
        active = [e for e in self.enemies if not e.disabled]
        if not c.wing_present and active and self.wing_gun_timer <= 0:
            target = min(active, key=lambda e: math.dist((e.x, e.y), (self.ship.x, self.ship.y)))
            if math.dist((target.x, target.y), (self.ship.x, self.ship.y)) < 460:
                self.wing_angle = math.atan2(target.y - self.ship.y, target.x - self.ship.x)
                self.shoot(self.ship.x, self.ship.y, self.wing_angle, True)
                self.wing_gun_timer = .65
        elif c.wing_present and c.wing_fire and self.wing_gun_timer <= 0:
            self.shoot(self.wing_x, self.wing_y, self.wing_angle, True)
            self.wing_gun_timer = .16 if self.wing_docked else .23

    def _enemies(self, dt: float) -> None:
        for e in self.enemies:
            if e.disabled:
                e.angle += dt * .15
                continue
            dx, dy = self.ship.x - e.x, self.ship.y - e.y
            distance = math.hypot(dx, dy)
            if distance > 800:
                continue
            angle = math.atan2(dy, dx)
            e.angle = angle
            approach = 1 if distance > 220 else -.35
            e.x += (math.cos(angle) * approach * 115 - math.sin(angle) * 48) * dt
            e.y += (math.sin(angle) * approach * 115 + math.cos(angle) * 48) * dt
            e.cooldown -= dt
            if e.cooldown <= 0 and distance < 550:
                if self.wing_present and not self.wing_docked and self.rng.random() < .3:
                    angle = math.atan2(self.wing_y - e.y, self.wing_x - e.x)
                self.shoot(e.x, e.y, angle, False)
                e.cooldown = self.rng.uniform(.9, 1.6)

    def _shots(self, dt: float) -> None:
        survivors = []
        for shot in self.shots:
            shot.x += shot.vx * dt
            shot.y += shot.vy * dt
            shot.life -= dt
            hit = False
            if shot.friendly:
                for e in list(self.enemies):
                    if math.dist((shot.x, shot.y), (e.x, e.y)) < (32 if shot.heavy else 24):
                        e.hull -= shot.damage
                        self.burst(e.x, e.y, (255, 158, 102), 7)
                        if e.hull <= 0:
                            self.enemies.remove(e)
                            self.campaign.credits += 35
                            if e.bounty:
                                self.campaign.mission_progress += 1
                            self.pickups.append(Pickup(e.x, e.y))
                            self.burst(e.x, e.y, (255, 201, 126), 22)
                            self.sounds.append("explosion")
                        elif e.hull <= 22 and not e.disabled:
                            e.disabled = True
                            self.tell("Raider disabled. Stop firing; TRACTOR to capture!")
                        hit = True
                        break
            elif math.dist((shot.x, shot.y), (self.ship.x, self.ship.y)) < 30:
                self.damage_ship(shot.damage)
                hit = True
            elif (not self.wing_docked and
                  math.dist((shot.x, shot.y), (self.wing_x, self.wing_y)) < 19):
                self.wing_hull -= shot.damage
                hit = True
                if self.wing_hull <= 0:
                    self.wing_docked = True
                    self.wing_hull = 0
                    self.tell("Escort recovered. Take the turret while it repairs.")
            if not hit and shot.life > 0:
                survivors.append(shot)
        self.shots = survivors

    def recover(self) -> None:
        self.campaign.credits = max(0, self.campaign.credits - 60)
        self.campaign.fuel = 4
        self.ship = Ship(shield=self.max_shield)
        self.cooldowns = [0.0] * 5
        self.shield_timer = self.repair_timer = self.boost_timer = 0
        self.wing_hull = 60
        self.enter_system(0)
        self.ship.x, self.ship.y = self.port_position
        self.recovered = True
        self.tell("Rangers towed you home. Recovery: up to 60 credits. Cargo safe.", "repair")

    def dock(self) -> bool:
        if not self.near_port:
            self.tell("Fly within the port's docking ring.")
            return False
        if self.danger_near:
            self.tell("Clear nearby threats before docking.")
            return False
        self.ship.vx = self.ship.vy = 0
        self.ship.hull, self.ship.shield, self.ship.energy = 140, self.max_shield, 100
        self.campaign.fuel = 4
        self.wing_hull = 60
        self.wing_docked = True
        self.shots.clear()
        self.finish_contract()
        return True

    def accept_contract(self) -> bool:
        c = self.campaign
        if c.mission:
            self.tell("Finish your current contract first.")
            return False
        if c.system == 0 and c.deliveries and c.bounties < c.deliveries:
            c.mission = "bounty"
            self.tell("Ranger contract: clear three marked raiders in The Drift.")
        elif c.system == 0:
            if c.capacity - c.used_cargo < 4:
                self.tell("Make four spaces in your cargo hold first.")
                return False
            c.mission = "delivery"
            self.tell("Four crates loaded. Deliver to Lantern: 300 credits.")
        elif c.system == 2:
            c.mission = "rescue"
            self.tell("Distress call! Recover survivors in The Drift: 450 credits.")
        else:
            return False
        c.mission_progress = 0
        return True

    def finish_contract(self) -> bool:
        c = self.campaign
        if c.mission == "delivery" and c.system == 2:
            c.credits += 300
            c.deliveries += 1
            c.scrap += 1
            self.tell("Greenhouses saved! +300 credits. Scrap Union trust +1.", "reward")
        elif c.mission == "rescue" and c.mission_progress and c.system == 2:
            c.credits += 450
            c.rescues += 1
            c.rangers += 1
            self.tell("Everyone made it home! +450 credits. Ranger trust +1.", "reward")
        elif c.mission == "bounty" and c.mission_progress >= 3 and c.system == 0:
            c.credits += 600
            c.bounties += 1
            c.rangers += 2
            self.tell("Trade route secured! +600 credits. Ranger trust +2.", "reward")
        else:
            return False
        c.mission = ""
        c.mission_progress = 0
        return True

    def trade(self, buy: bool) -> bool:
        c = self.campaign
        price = int(SYSTEMS[c.system]["price"])
        if not price:
            return False
        if buy:
            if c.credits < price or c.used_cargo >= c.capacity:
                self.tell("Not enough credits or cargo space.")
                return False
            c.credits -= price
            c.cargo += 1
            self.tell(f"Bought supplies for {price} credits.", "reward")
        elif c.cargo:
            c.credits += price
            c.cargo -= 1
            self.tell(f"Sold supplies for {price} credits.", "reward")
        else:
            self.tell("No trade supplies aboard. Mission cargo stays reserved.")
            return False
        return True

    def upgrade_price(self, index: int) -> int:
        return 200 + self.campaign.upgrades[UPGRADES[index]] * 175

    def buy_upgrade(self, index: int) -> bool:
        key = UPGRADES[index]
        if self.campaign.upgrades[key] >= 3:
            self.tell("That module is fully upgraded.")
            return False
        price = self.upgrade_price(index)
        if self.campaign.credits < price:
            self.tell(f"Need {price} credits for this upgrade.")
            return False
        self.campaign.credits -= price
        self.campaign.upgrades[key] += 1
        self.tell(f"{UPGRADE_NAMES[index]} upgraded!", "reward")
        return True


def save_path() -> Path:
    override = os.environ.get("STARSHIP_SAVE_PATH")
    if override:
        return Path(override)
    return Path(__file__).parent / "data" / "campaign.json"


def save_game(world: Universe, path: Path | None = None) -> None:
    """Atomic replace: interruption cannot truncate the previous campaign."""
    path = path or save_path()
    payload = {"version": 1, "campaign": asdict(world.campaign), "ship": asdict(world.ship),
               "enemies": [asdict(e) for e in world.enemies],
               "pickups": [asdict(p) for p in world.pickups]}
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    with temporary.open("w") as handle:
        json.dump(payload, handle, indent=2, allow_nan=False)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def load_game(path: Path | None = None) -> Universe:
    path = path or save_path()
    if not path.exists():
        return Universe()
    try:
        data = json.loads(path.read_text())
        if data["version"] != 1:
            raise ValueError("Unsupported save version")
        campaign = Campaign(**data["campaign"])
        if (campaign.system not in range(3) or campaign.mission not in ("", "delivery", "rescue", "bounty")
                or not isinstance(campaign.upgrades, dict)):
            raise ValueError("Invalid campaign")
        for key in UPGRADES:
            if type(campaign.upgrades.get(key)) is not int or not 0 <= campaign.upgrades[key] <= 3:
                raise ValueError("Invalid upgrade")
        for name in ("credits", "fuel", "cargo", "mission_progress", "deliveries", "rescues",
                     "bounties", "captures", "rangers", "scrap"):
            if type(getattr(campaign, name)) is not int or getattr(campaign, name) < 0:
                raise ValueError("Invalid campaign value")
        if campaign.fuel > 4 or campaign.used_cargo > campaign.capacity:
            raise ValueError("Invalid cargo/fuel")
        if not isinstance(campaign.visited, list) or any(type(i) is not int or i not in range(3) for i in campaign.visited):
            raise ValueError("Invalid chart")
        world = Universe(campaign)
        world.ship = Ship(**data["ship"])
        world.enemies = [Enemy(**e) for e in data["enemies"]]
        world.pickups = [Pickup(**p) for p in data["pickups"]]
        for obj in [world.ship, *world.enemies, *world.pickups]:
            for value in asdict(obj).values():
                if isinstance(value, (int, float)) and not math.isfinite(value):
                    raise ValueError("Non-finite position")
        if not 0 < world.ship.hull <= 140 or not 0 <= world.ship.energy <= 100:
            raise ValueError("Invalid ship")
        world.ship.shield = clamp(world.ship.shield, 0, world.max_shield)
        world.wing_x, world.wing_y = world.ship.x, world.ship.y
        return world
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        # Never overwrite an unreadable save automatically. The UI disables
        # autosave until the user explicitly chooses a fresh campaign.
        world = Universe()
        world.tell("Save could not be read. Original preserved; saving disabled.")
        world.save_blocked = True
        return world

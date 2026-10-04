"""Original procedural cockpit artwork, cached for the Raspberry Pi's CPU renderer."""

from __future__ import annotations

import math
import random
from collections.abc import Sequence
from functools import lru_cache
from typing import TYPE_CHECKING

import pygame

from .model import COOLDOWNS, COSTS, MODULE_COLORS, MODULE_NAMES, SYSTEMS, Universe

if TYPE_CHECKING:
    from .game import StarshipState

W, H = 1000, 600
INK = (8, 15, 29)
PANEL = (15, 26, 43)
LINE = (41, 62, 82)
TEXT = (231, 239, 246)
MUTED = (141, 166, 187)
MINT = (124, 242, 194)
AMBER = (255, 204, 122)


@lru_cache(maxsize=64)
def font(size: int, bold: bool = False) -> pygame.font.Font:
    return pygame.font.SysFont("Arial", size, bold=bold)


def text(surface: pygame.Surface, value: str, x: float, y: float, size: int = 18,
         color: tuple[int, int, int] = TEXT, bold: bool = False, limit: int = 0) -> None:
    face = font(size, bold)
    if limit:
        while face.size(value)[0] > limit and len(value) > 3:
            value = value[:-4] + "..."
    surface.blit(face.render(value, True, color), (int(x), int(y)))


def card(surface: pygame.Surface, rect: tuple[int, int, int, int],
         fill: tuple[int, int, int] = PANEL, border: tuple[int, int, int] = LINE) -> None:
    pygame.draw.rect(surface, fill, rect, border_radius=12)
    pygame.draw.rect(surface, border, rect, 1, border_radius=12)


def meter(surface: pygame.Surface, x: int, y: int, width: int, fraction: float,
          color: tuple[int, int, int], height: int = 5) -> None:
    pygame.draw.rect(surface, (36, 49, 65), (x, y, width, height), border_radius=3)
    if fraction > 0:
        pygame.draw.rect(surface, color, (x, y, max(1, int(width * min(1, fraction))), height), border_radius=3)


@lru_cache(maxsize=12)
def planet(radius: int, scheme: int) -> pygame.Surface:
    result = pygame.Surface((radius * 2 + 24, radius * 2 + 24), pygame.SRCALPHA)
    center = (radius + 12, radius + 12)
    color = SYSTEMS[scheme]["color"]
    for r in range(radius + 10, radius, -1):
        pygame.draw.circle(result, (*color, (radius + 11 - r) * 5), center, r)
    pygame.draw.circle(result, (14, 25, 42), center, radius)
    rng = random.Random(991 + scheme)
    for y in range(-radius, radius):
        half = math.sqrt(max(0, radius * radius - y * y))
        for x in range(-int(half), int(half), 2):
            z = math.sqrt(max(0, 1 - (x / radius) ** 2 - (y / radius) ** 2))
            light = max(.045, (-x / radius * .5 - y / radius * .35 + z * .65))
            terrain = math.sin(x * .05 + math.sin(y * .09) * 3) + math.cos(y * .12 + x * .028)
            tint = .75 + .2 * terrain + rng.uniform(-.025, .025)
            rgb = tuple(max(0, min(255, int(c * light * tint))) for c in color)
            pygame.draw.line(result, rgb, (center[0] + x, center[1] + y),
                             (center[0] + x + 1, center[1] + y))
    return result


def ship_art(surface: pygame.Surface, x: float, y: float, angle: float,
             scale: float = 1, color: tuple[int, int, int] = (158, 191, 203),
             thrust: bool = False, escort: bool = False, time: float = 0) -> None:
    cosine, sine = math.cos(angle), math.sin(angle)

    def points(coords: Sequence[tuple[float, float]]) -> list[tuple[int, int]]:
        return [(round(x + (a * cosine - b * sine) * scale),
                 round(y + (a * sine + b * cosine) * scale)) for a, b in coords]

    if thrust:
        length = 24 + math.sin(time * 45) * 7
        for offset in ((-6, 6) if not escort else (0,)):
            pygame.draw.polygon(surface, (48, 113, 172), points([(-18, offset - 5), (-18 - length, offset), (-18, offset + 5)]))
            pygame.draw.polygon(surface, (156, 239, 241), points([(-18, offset - 2), (-25 - length * .5, offset), (-18, offset + 2)]))
    hull = [(29, 0), (12, -9), (0, -10), (-13, -21), (-23, -21), (-17, -6),
            (-23, 0), (-17, 6), (-23, 21), (-13, 21), (0, 10), (12, 9)]
    if escort:
        hull = [(23, 0), (-19, -14), (-11, 0), (-19, 14)]
    pygame.draw.polygon(surface, (4, 9, 17), points(hull), 0)
    pygame.draw.polygon(surface, color, points(hull), 2)
    pygame.draw.polygon(surface, tuple(int(c * .5) for c in color), points([(24, 0), (3, -7), (-15, -5), (-15, 5), (3, 7)]))
    pygame.draw.polygon(surface, (128, 233, 233), points([(14, 0), (4, -4), (4, 4)]))
    pygame.draw.line(surface, (222, 228, 207), points([(-10, 0)])[0], points([(2, 0)])[0], 2)
    if not escort:
        for offset in (-14, 14):
            pygame.draw.line(surface, (204, 225, 222), points([(-15, offset)])[0], points([(-3, offset)])[0], 3)


class Renderer:
    def __init__(self) -> None:
        self.canvas = pygame.Surface((W, H))
        rng = random.Random(63)
        self.stars = [(rng.randrange(W), rng.randrange(H), rng.choice((1, 1, 1, 2)),
                       rng.randrange(55, 180)) for _ in range(260)]
        self.backgrounds: dict[int, pygame.Surface] = {}
        self.camera_x = self.camera_y = 0.0
        self.zoom = .66

    def background(self, system: int) -> pygame.Surface:
        if system not in self.backgrounds:
            surface = pygame.Surface((W, H))
            surface.fill(INK)
            glow = pygame.Surface((W, H), pygame.SRCALPHA)
            color = SYSTEMS[system]["color"]
            for radius in range(520, 30, -18):
                pygame.draw.circle(glow, (*tuple(c // 4 for c in color), 3), (740, 190), radius)
                surface.blit(glow, (0, 0))
                glow.fill((0, 0, 0, 0))
            self.backgrounds[system] = surface
        return self.backgrounds[system]

    def screen(self, x: float, y: float) -> tuple[int, int]:
        return round(500 + (x - self.camera_x) * self.zoom), round(282 + (y - self.camera_y) * self.zoom)

    def space(self, w: Universe) -> None:
        s = self.canvas
        s.blit(self.background(w.campaign.system), (0, 0))
        self.camera_x, self.camera_y = w.ship.x, w.ship.y
        for x, y, radius, brightness in self.stars:
            sx = int((x - w.ship.x * .06 * radius) % W)
            sy = int((y - w.ship.y * .06 * radius) % H)
            pygame.draw.circle(s, (brightness, brightness, min(230, brightness + 25)), (sx, sy), radius)
        s.set_clip(pygame.Rect(0, 96, W, 395))
        system = SYSTEMS[w.campaign.system]
        px, py = self.screen(*system["planet"])
        art = planet(105, w.campaign.system)
        s.blit(art, (px - 117, py - 117))
        if system["port"]:
            x, y = self.screen(*w.port_position)
            pygame.draw.circle(s, (51, 103, 108), (x, y), 108, 1)
            pygame.draw.circle(s, (68, 149, 151), (x, y), 35, 2)
            for i in range(4):
                angle = i * math.pi / 2 + w.time * .07
                a = (x + math.cos(angle) * 24, y + math.sin(angle) * 24)
                b = (x + math.cos(angle) * 50, y + math.sin(angle) * 50)
                pygame.draw.line(s, (164, 200, 193), a, b, 9)
            pygame.draw.circle(s, MINT, (x, y), 8)
            text(s, system["port"].upper(), x - 100, y + 57, 15, MINT)
            if w.near_port:
                text(s, "X / E  DOCK", x - 44, y + 77, 16, TEXT, True)
        else:
            # Wreck silhouette marks the rescue site.
            x, y = self.screen(-40, -220)
            ship_art(s, x, y, .4, 1.8, (95, 93, 95))
            text(s, "DERELICT FREIGHTER", x - 80, y + 47, 14, AMBER)
        for pickup in w.pickups:
            x, y = self.screen(pickup.x, pickup.y)
            color = MINT if pickup.kind == "pod" else AMBER
            pygame.draw.circle(s, color, (x, y), 16 + int(3 * math.sin(w.time * 3)), 1)
            pygame.draw.rect(s, color, (x - 5, y - 6, 10, 12), 2, border_radius=2)
            if pickup.kind == "pod":
                text(s, "SURVIVORS", x - 42, y + 22, 14, MINT)
        for enemy in w.enemies:
            x, y = self.screen(enemy.x, enemy.y)
            color = (168, 147, 112) if enemy.disabled else (247, 125, 122)
            ship_art(s, x, y, enemy.angle, .9, color, not enemy.disabled, True, w.time)
            if enemy.disabled:
                text(s, "DISABLED / TRACTOR", x - 65, y + 23, 13, AMBER)
            else:
                meter(s, x - 22, y - 26, 44, enemy.hull / 66, color, 3)
                if enemy.bounty:
                    pygame.draw.circle(s, AMBER, (x, y), 30, 1)
        if w.tractor_target:
            tx, ty = self.screen(*w.tractor_target)
            pygame.draw.line(s, (94, 171, 180), (500, 282), (tx, ty), 7)
            pygame.draw.line(s, (184, 249, 226), (500, 282), (tx, ty), 2)
            meter(s, tx - 25, ty + 28, 50, w.tractor_progress / 1.15, MINT)
        elif w.tractor_timer > 0:
            pygame.draw.circle(s, (59, 100, 120), (500, 282), int((240 + w.campaign.upgrades["tractor"] * 65) * self.zoom), 1)
        for shot in w.shots:
            x, y = self.screen(shot.x, shot.y)
            length = math.hypot(shot.vx, shot.vy)
            color = AMBER if shot.heavy else MINT if shot.friendly else (255, 122, 128)
            end = (x - shot.vx / length * (18 if shot.heavy else 9), y - shot.vy / length * (18 if shot.heavy else 9))
            pygame.draw.line(s, color, (x, y), end, 5 if shot.heavy else 2)
        for p in w.particles:
            x, y = self.screen(p.x, p.y)
            pygame.draw.circle(s, p.color, (x, y), max(1, int(p.life * 4)))
        if w.shield_timer > 0:
            pygame.draw.circle(s, (89, 179, 246), (500, 282), 39, 2)
            pygame.draw.circle(s, (50, 95, 133), (500, 282), 44, 1)
        if w.repair_timer > 0:
            for i in range(3):
                angle = w.time * 3 + i * math.tau / 3
                pygame.draw.circle(s, MINT, (int(500 + math.cos(angle) * 38), int(282 + math.sin(angle) * 38)), 3)
        ship_art(s, 500, 282, w.ship.angle, 1.1, (200, 221, 215),
                 math.hypot(w.ship.vx, w.ship.vy) > 45, time=w.time)
        text(s, "T H E   T R E E H O U S E", 432, 327, 12, MUTED)
        if not w.wing_docked:
            x, y = self.screen(w.wing_x, w.wing_y)
            ship_art(s, x, y, w.wing_angle, .65, (182, 168, 255), True, True, w.time)
            text(s, "P2", x - 9, y + 18, 13, (193, 183, 255))
        else:
            end = (500 + math.cos(w.wing_angle) * 23, 282 + math.sin(w.wing_angle) * 23)
            pygame.draw.line(s, (192, 167, 255), (500, 282), end, 3)
        # Navigation edge marker ensures the port is findable after a long flight.
        if system["port"]:
            x, y = self.screen(*w.port_position)
            if not pygame.Rect(80, 125, 750, 310).collidepoint(x, y):
                ex, ey = max(80, min(800, x)), max(130, min(430, y))
                pygame.draw.circle(s, MINT, (ex, ey), 5)
                text(s, "PORT", ex + 10, ey - 9, 14, MINT)
        s.set_clip(None)

    def hud(self, state: StarshipState) -> None:
        s, w = self.canvas, state.world
        c = w.campaign
        pygame.draw.rect(s, INK, (0, 0, W, 96))
        pygame.draw.line(s, LINE, (0, 95), (W, 95))
        text(s, "TREEHOUSE / STARSHIP", 22, 12, 16, MINT, True)
        text(s, SYSTEMS[c.system]["name"].upper(), 22, 36, 27, TEXT, True)
        text(s, SYSTEMS[c.system]["faction"], 24, 70, 14, MUTED)
        text(s, "HULL", 270, 18, 13, MUTED)
        text(s, "SHIELD", 437, 18, 13, MUTED)
        text(s, "REACTOR", 604, 18, 13, MUTED)
        meter(s, 270, 43, 137, w.ship.hull / 140, MINT)
        meter(s, 437, 43, 137, w.ship.shield / w.max_shield, MODULE_COLORS[2])
        meter(s, 604, 43, 137, w.ship.energy / 100, AMBER)
        text(s, w.objective, 270, 63, 15, TEXT, limit=510)
        text(s, f"{c.credits:,} CR", 806, 18, 23, AMBER, True)
        text(s, f"FUEL {c.fuel}/4   CARGO {c.used_cargo}/{c.capacity}", 806, 52, 14, MUTED)
        self.minimap(w)
        card(s, (22, 111, 250, 51), (12, 23, 38))
        text(s, "P1  " + ("PILOT CONNECTED" if state.pilot_connected else "KEYBOARD PILOT"), 35, 120, 14, MINT)
        wing = "ESCORT" if not w.wing_docked else "TURRET" if w.wing_present else "AUTO TURRET"
        text(s, f"P2  {wing}" + (f" / {int(w.wing_hull)} HP" if w.wing_present else " / CONNECT TO JOIN"), 35, 141, 13, MUTED)
        if w.messages:
            message = w.messages[-1][0]
            card(s, (180, 443, 640, 37), (13, 29, 43))
            text(s, message, 195, 452, 15, MINT, limit=610)
        pygame.draw.rect(s, INK, (0, 490, W, 110))
        text(s, "SYSTEMS OFFICER", 22, 490, 12, MUTED, True)
        text(s, "PILOT: X/E Dock   Y/Tab Chart   Start/P Pause", 500, 490, 12, MUTED)
        for i, (name, color) in enumerate(zip(MODULE_NAMES, MODULE_COLORS)):
            x = 20 + i * 196
            ready = w.module_ready(i) and (i != 1 or w.ship.hull < 140)
            card(s, (x, 511, 184, 73), (18, 30, 45), color if ready else LINE)
            pygame.draw.circle(s, color if ready else tuple(v // 3 for v in color), (x + 19, 530), 5)
            text(s, name, x + 32, 521, 15, TEXT, True)
            status = (f"{w.cooldowns[i]:.1f}s" if w.cooldowns[i] > 0 else
                      "LOW POWER" if w.ship.energy < COSTS[i] else
                      "HULL FULL" if i == 1 and w.ship.hull >= 140 else "READY")
            text(s, f"{i + 1}  {status}", x + 12, 548, 13, color if ready else MUTED)
            text(s, f"{COSTS[i]} E", x + 139, 548, 12, MUTED)
            meter(s, x + 12, 575, 160, 1 - w.cooldowns[i] / COOLDOWNS[i], color, 3)

    def minimap(self, w: Universe) -> None:
        s = self.canvas
        card(s, (846, 111, 132, 111), (12, 23, 38))
        text(s, "LOCAL RADAR", 856, 119, 11, MUTED)
        center = (912, 176)
        pygame.draw.circle(s, LINE, center, 35, 1)
        pygame.draw.line(s, LINE, (870, 176), (954, 176))
        pygame.draw.line(s, LINE, (912, 140), (912, 210))
        objects = [(w.ship.x, w.ship.y, MINT)] + [(e.x, e.y, MODULE_COLORS[0]) for e in w.enemies]
        if SYSTEMS[w.campaign.system]["port"]:
            objects.append((*w.port_position, (130, 189, 250)))
        for x, y, color in objects:
            pygame.draw.circle(s, color, (int(912 + x * .029), int(176 + y * .025)), 3)

    def menu(self, state: StarshipState) -> None:
        s, w = self.canvas, state.world
        if state.mode == "title":
            s.blit(self.background(0), (0, 0))
            for x, y, radius, brightness in self.stars:
                pygame.draw.circle(s, (brightness, brightness, min(230, brightness + 25)), (x, y), radius)
            s.blit(planet(160, 0), (654, 55))
            pygame.draw.circle(s, (45, 86, 91), (820, 245), 204, 1)
            ship_art(s, 731, 320, -.58, 3.1, (191, 218, 211), True, time=w.time)
            ship_art(s, 896, 373, -.58, 1.1, (181, 167, 255), True, True)
            text(s, "A TREEHOUSE CREW ADVENTURE", 56, 53, 15, MINT, True)
            text(s, "TREEHOUSE", 52, 89, 57, TEXT, True)
            text(s, "STARSHIP", 52, 146, 68, TEXT, True)
            text(s, "Small crew. Wide-open galaxy.", 56, 234, 24, MUTED)
            text(s, "EXPLORE   /   TRADE   /   RESCUE   /   SURVIVE", 56, 277, 13, MINT)
            for i, (label, _) in enumerate(state.menu_items()):
                y = 324 + i * 47
                selected = i == state.selection
                card(s, (56, y, 435, 39), (27, 51, 57) if selected else (15, 25, 40), MINT if selected else LINE)
                text(s, (">  " if selected else "   ") + label, 73, y + 8, 18, TEXT if selected else MUTED, selected)
            text(s, "2-3 CREW  /  5 PHYSICAL BUTTONS  /  2 CONTROLLERS", 542, 507, 12, MUTED)
        else:
            shade = pygame.Surface((W, H), pygame.SRCALPHA)
            shade.fill((4, 10, 20, 228))
            s.blit(shade, (0, 0))
            card(s, (48, 46, 904, 498), (13, 24, 39))
            titles = {"dock": SYSTEMS[w.campaign.system]["port"] or "Port",
                      "shop": "THE OUTFITTER", "trade": "TRADING EXCHANGE", "pause": "CREW ON BREAK",
                      "confirm_new": "A FRESH START?", "confirm_tow": "CALL THE RANGER TUG?"}
            text(s, titles.get(state.mode, "TREEHOUSE STARSHIP"), 78, 69, 32, TEXT, True)
            text(s, f"{w.campaign.credits:,} CR", 774, 80, 23, AMBER, True)
            description = {"dock": "Refueled, repaired and ready for your next adventure.",
                           "shop": "Make this ship your own. Every module has three upgrade levels.",
                           "trade": "Canopy buys/sells at 35 cr. Lantern buys/sells at 70 cr.",
                           "pause": "Flight is paused. Swap roles, take a breath, plan your next jump.",
                           "confirm_new": "Your current campaign will be backed up, then replaced.",
                           "confirm_tow": "Return to Canopy with your mission and cargo. Costs up to 60 cr."}
            text(s, description.get(state.mode, ""), 80, 119, 17, MUTED, limit=820)
            items = state.menu_items()
            for i, (label, _) in enumerate(items):
                y = 164 + i * 45
                selected = i == state.selection
                card(s, (78, y, 563, 38), (26, 49, 54) if selected else (17, 30, 47), MINT if selected else LINE)
                text(s, (">  " if selected else "   ") + label, 91, y + 8, 17, TEXT if selected else MUTED, selected, 535)
            pygame.draw.line(s, LINE, (668, 164), (668, 450))
            text(s, "THE TREEHOUSE", 696, 169, 18, MINT, True)
            ship_art(s, 795, 240, -.3, 1.7)
            for i, line in enumerate((f"Cargo {w.campaign.used_cargo}/{w.campaign.capacity}",
                                      f"Ranger trust +{w.campaign.rangers}", f"Scrap Union trust +{w.campaign.scrap}",
                                      f"Captures {w.campaign.captures}", f"Systems found {len(w.campaign.visited)}/3")):
                text(s, line, 696, 300 + i * 26, 16, MUTED)
            if state.mode == "trade":
                text(s, f"Trade supplies: {w.campaign.cargo}  /  Mission crates are reserved", 80, 348, 16, AMBER)
            if state.mode == "shop" and state.selection < 5:
                from .model import UPGRADE_DESCRIPTIONS
                text(s, UPGRADE_DESCRIPTIONS[state.selection], 80, 453, 16, MINT, limit=550)
            message = w.messages[-1][0] if w.messages else state.save_status
            text(s, message, 80, 500, 15, MINT, limit=840)
        self.menu_footer()

    def menu_footer(self, map_mode: bool = False) -> None:
        s = self.canvas
        labels = ("1 / RED  Previous", "2 / GREEN  Next", "3 / BLUE  Jump" if map_mode else "3 / BLUE  Select",
                  "4 / YELLOW  Rescue tug" if map_mode else "A / ENTER  Select", "5 / WHITE  Back")
        for i, label in enumerate(labels):
            text(s, label, 25 + i * 198, 565, 13, MODULE_COLORS[i])

    def chart(self, state: StarshipState) -> None:
        s, w = self.canvas, state.world
        s.blit(self.background(2), (0, 0))
        text(s, "THE KNOWN REACH", 54, 43, 34, TEXT, True)
        text(s, "Choose your next jump. Every place has a story.", 56, 91, 18, MUTED)
        text(s, f"JUMP FUEL  {w.campaign.fuel}/4", 748, 55, 18, AMBER, True)
        points = [(210, 249), (500, 207), (790, 278)]
        for i in range(2):
            pygame.draw.line(s, LINE, points[i], points[i + 1], 3)
        for i, (system, position) in enumerate(zip(SYSTEMS, points)):
            x, y = position
            if i == state.map_selection:
                pygame.draw.circle(s, MINT, position, 56, 2)
            s.blit(planet(35, i), (x - 47, y - 47))
            text(s, system["name"].upper(), x - 73, y + 65, 20, TEXT, True)
            text(s, "YOU ARE HERE" if i == w.campaign.system else
                 "CHARTED" if i in w.campaign.visited else "UNEXPLORED", x - 64, y + 95, 12, MINT if i == w.campaign.system else MUTED)
        chosen = SYSTEMS[state.map_selection]
        card(s, (54, 416, 892, 120))
        text(s, chosen["subtitle"], 78, 434, 14, MINT, True)
        text(s, chosen["description"], 78, 460, 18, TEXT)
        status = ("Current system" if state.map_selection == w.campaign.system else
                  "Connected route / costs 1 fuel" if state.map_selection in SYSTEMS[w.campaign.system]["neighbors"] else
                  "Travel through The Drift to reach this system")
        text(s, status, 78, 493, 16, AMBER)
        if w.messages:
            text(s, w.messages[-1][0], 54, 383, 15, MINT, limit=880)
        self.menu_footer(True)

    def help(self) -> None:
        s = self.canvas
        s.fill(INK)
        text(s, "EVERY SEAT MATTERS", 45, 30, 34, TEXT, True)
        text(s, "Two crew: systems + pilot. Three crew: add a wingmate.", 47, 77, 19, MUTED)
        rows = [
            ("01  SYSTEMS OFFICER", MINT, ["Use the five physical buttons, or keyboard 1-5.",
              "Red: heavy cannon   Green: repair   Blue: shield surge", "Yellow: boost   White: tractor beam for cargo / survivors / disabled ships.",
              "Lit means ready. Systems share reactor energy. Hold to repeat."]),
            ("02  PILOT / FIRST CONTROLLER", MODULE_COLORS[2], ["Left stick: steer and thrust   A / RT: fire   B: brake",
              "X: dock near port   Y: star chart   Start: pause", "Keyboard: arrows or WASD, Space fire, E dock, Tab chart, P pause."]),
            ("03  WINGMATE / SECOND CONTROLLER", (185, 169, 255), ["Left stick: fly escort   Right stick: aim   A / RT: fire",
              "X: launch from turret / dock when close. Repairs while docked.",
              "Keyboard: F2 join, IJKL fly/aim, U fire, O launch/dock."]),
        ]
        y = 125
        for title, color, lines in rows:
            text(s, title, 47, y, 17, color, True)
            for j, line in enumerate(lines):
                text(s, line, 47, y + 29 + j * 24, 17, TEXT)
            y += 29 + len(lines) * 24 + 16
        text(s, "Menus: D-pad / arrows, A / Enter. Panel: red up, green down, blue select, white back.", 47, 535, 16, MUTED)
        text(s, "A / ENTER / BLUE to return. Big red button saves and returns to Treehouse games.", 47, 565, 16, MINT)

    def draw(self, target: pygame.Surface, state: StarshipState) -> None:
        self.space(state.world)
        if state.mode == "flight":
            self.hud(state)
        elif state.mode == "map":
            self.chart(state)
        elif state.mode == "help":
            self.help()
        else:
            self.menu(state)
        width, height = target.get_size()
        factor = min(width / W, height / H)
        size = (max(1, int(W * factor)), max(1, int(H * factor)))
        target.fill(INK)
        if size == (W, H):
            target.blit(self.canvas, ((width - W) // 2, (height - H) // 2))
        else:
            scaled = pygame.transform.smoothscale(self.canvas, size)
            target.blit(scaled, ((width - size[0]) // 2, (height - size[1]) // 2))

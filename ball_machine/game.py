"""Ball Machine: a perpetual-motion kinetic sculpture -- a three-lobed wavy
track, mounted on a tripod base, with balls forever circling it. Nothing to
win, nothing to lose; the fun is in walking around it. Red/Blue orbit the
camera left and right, Green/Yellow tilt it up and down, White snaps back to
the starting view.

A single continuous state that mutates and returns itself every frame, in
the "continuous game" style described in the README (see color_game). All
geometry is fixed at import time -- only the camera (azimuth/elevation)
lives in the state. Ball positions and the projected 3D-to-2D render are
recomputed fresh every frame off pygame.time.get_ticks(), the same live-clock
pattern color_game's victory animation uses for its own draw-only timing.

No 3D library is available here, so this hand-rolls the pipeline: rotate
each world point by the camera's azimuth/elevation, push it out along Z by
the camera distance, project with a simple pinhole perspective divide, and
depth-sort every line segment and ball with a painter's algorithm so nearer
things draw over farther ones.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, pi, sin

import pygame

from common import Input, State, draw_text, font
from hardware import Color, big_red_button_pressed, buttons

Vec3 = tuple[float, float, float]

# --- Camera -----------------------------------------------------------------

FOCAL_LENGTH = 600.0
CAMERA_DISTANCE = 520.0
ROTATE_RATE_RAD_PER_MS = 0.0015  # about one full turn every 4.2s held
TILT_RATE_RAD_PER_MS = 0.0012
ELEVATION_MIN = -1.3
ELEVATION_MAX = 1.3
DEFAULT_AZIMUTH = 0.7
DEFAULT_ELEVATION = 0.35

# --- Track geometry -----------------------------------------------------------
# A closed, three-lobed curve (radius wobbles with cos(3*theta), height wobbles
# with sin(3*theta)) -- asymmetric enough that rotating around it actually
# reveals a different silhouette from every side.

TRACK_LOBES = 3
TRACK_RADIUS = 140.0
TRACK_RADIUS_WOBBLE = 55.0
TRACK_HEIGHT_WOBBLE = 70.0
TRACK_SEGMENTS = 160
TRACK_COLOR = (150, 160, 200)

BASE_RADIUS = 190.0
BASE_Y = -170.0
BASE_SEGMENTS = 48
BASE_COLOR = (90, 90, 120)

LEG_COUNT = 3
LEG_COLOR = (110, 110, 140)

BALL_COUNT = 6
BALL_COLORS = [
    (230, 60, 60),
    (60, 90, 230),
    (70, 200, 90),
    (230, 210, 50),
    (170, 80, 200),
    (70, 200, 230),
]
BALL_SPEED_PER_MS = 1 / 6000  # one full lap every 6 seconds
BALL_RADIUS = 10.0


def _track_point(t: float) -> Vec3:
    theta = t * 2 * pi
    radius = TRACK_RADIUS + TRACK_RADIUS_WOBBLE * cos(TRACK_LOBES * theta)
    x = radius * cos(theta)
    z = radius * sin(theta)
    y = TRACK_HEIGHT_WOBBLE * sin(TRACK_LOBES * theta)
    return (x, y, z)


TRACK_POINTS = [_track_point(i / TRACK_SEGMENTS) for i in range(TRACK_SEGMENTS + 1)]

BASE_POINTS = [
    (
        BASE_RADIUS * cos(2 * pi * i / BASE_SEGMENTS),
        BASE_Y,
        BASE_RADIUS * sin(2 * pi * i / BASE_SEGMENTS),
    )
    for i in range(BASE_SEGMENTS + 1)
]

# Each leg runs from one of the track's three low points (where the wobble
# bottoms out, so the track sits right on top of its support) down and out
# to the base ring, tripod-style.
_LEG_ANGLES = [-pi / 6 + k * (2 * pi / LEG_COUNT) for k in range(LEG_COUNT)]
LEGS: list[tuple[Vec3, Vec3]] = [
    (
        (TRACK_RADIUS * cos(a), -TRACK_HEIGHT_WOBBLE, TRACK_RADIUS * sin(a)),
        (BASE_RADIUS * cos(a), BASE_Y, BASE_RADIUS * sin(a)),
    )
    for a in _LEG_ANGLES
]


def _rotate_y(p: Vec3, angle: float) -> Vec3:
    x, y, z = p
    c, s = cos(angle), sin(angle)
    return (x * c + z * s, y, -x * s + z * c)


def _rotate_x(p: Vec3, angle: float) -> Vec3:
    x, y, z = p
    c, s = cos(angle), sin(angle)
    return (x, y * c - z * s, y * s + z * c)


def _to_camera_space(p: Vec3, azimuth: float, elevation: float) -> Vec3:
    x, y, z = _rotate_x(_rotate_y(p, azimuth), elevation)
    return (x, y, z + CAMERA_DISTANCE)


def _project(p: Vec3, cx: int, cy: int) -> tuple[tuple[float, float], float, float]:
    x, y, z = p
    z = max(z, 1.0)  # the geometry never actually gets this close to the camera
    scale = FOCAL_LENGTH / z
    return (cx + x * scale, cy - y * scale), scale, z


def _light_control_leds() -> None:
    for button in buttons.values():
        button.set_led(True)


def _clear_control_leds() -> None:
    for button in buttons.values():
        button.set_led(False)


@dataclass
class BallMachineState:
    azimuth: float = DEFAULT_AZIMUTH
    elevation: float = DEFAULT_ELEVATION
    last_frame_at: int | None = None
    white_was_held: bool = False

    def draw(self, surface: pygame.Surface) -> None:
        canvas_width, canvas_height = surface.get_size()
        surface.fill((8, 8, 20))
        cx, cy = canvas_width // 2, canvas_height // 2 + 30

        # (depth, kind, ...) tuples, painter's-algorithm sorted farthest-first
        # right before drawing so every line and ball occludes correctly
        # regardless of camera angle.
        draw_items: list[tuple[float, str, object]] = []

        def add_segment(p1: Vec3, p2: Vec3, color: tuple[int, int, int], width: int) -> None:
            c1 = _to_camera_space(p1, self.azimuth, self.elevation)
            c2 = _to_camera_space(p2, self.azimuth, self.elevation)
            s1, scale1, z1 = _project(c1, cx, cy)
            s2, scale2, z2 = _project(c2, cx, cy)
            depth = (z1 + z2) / 2
            line_width = max(1, int(width * (scale1 + scale2) / 2))
            draw_items.append((depth, "line", (s1, s2, color, line_width)))

        for p1, p2 in zip(TRACK_POINTS, TRACK_POINTS[1:]):
            add_segment(p1, p2, TRACK_COLOR, 4)
        for p1, p2 in zip(BASE_POINTS, BASE_POINTS[1:]):
            add_segment(p1, p2, BASE_COLOR, 3)
        for top, bottom in LEGS:
            add_segment(top, bottom, LEG_COLOR, 6)

        current_time = pygame.time.get_ticks()
        for i, color in enumerate(BALL_COLORS[:BALL_COUNT]):
            t = (current_time * BALL_SPEED_PER_MS + i / BALL_COUNT) % 1.0
            cam_pos = _to_camera_space(_track_point(t), self.azimuth, self.elevation)
            screen_pos, scale, z = _project(cam_pos, cx, cy)
            radius = max(3, int(BALL_RADIUS * scale))
            draw_items.append((z, "ball", (screen_pos, color, radius)))

        draw_items.sort(key=lambda item: item[0], reverse=True)

        for _, kind, payload in draw_items:
            if kind == "line":
                s1, s2, color, width = payload
                pygame.draw.line(surface, color, s1, s2, width)
            else:
                pos, color, radius = payload
                center = (int(pos[0]), int(pos[1]))
                pygame.draw.circle(surface, color, center, radius)
                pygame.draw.circle(surface, (255, 255, 255), center, radius, 1)

        draw_text(surface, font(26), "Ball Machine", (canvas_width // 2, 26), (255, 255, 255))
        draw_text(
            surface,
            font(16),
            "Red/Blue: rotate    Green/Yellow: tilt    White: reset view",
            (canvas_width // 2, canvas_height - 16),
            (200, 200, 200),
        )

    def next_state(self, input: Input) -> State | None:
        if big_red_button_pressed():
            _clear_control_leds()
            return None  # back to the menu

        current_time = input.current_time
        dt = 0 if self.last_frame_at is None else max(0, current_time - self.last_frame_at)
        self.last_frame_at = current_time

        _light_control_leds()

        red_held = buttons[Color.RED].is_pressed()
        blue_held = buttons[Color.BLUE].is_pressed()
        green_held = buttons[Color.GREEN].is_pressed()
        yellow_held = buttons[Color.YELLOW].is_pressed()
        white_held = buttons[Color.WHITE].is_pressed()

        if red_held and not blue_held:
            self.azimuth -= ROTATE_RATE_RAD_PER_MS * dt
        elif blue_held and not red_held:
            self.azimuth += ROTATE_RATE_RAD_PER_MS * dt
        self.azimuth %= 2 * pi

        if green_held and not yellow_held:
            self.elevation = min(ELEVATION_MAX, self.elevation + TILT_RATE_RAD_PER_MS * dt)
        elif yellow_held and not green_held:
            self.elevation = max(ELEVATION_MIN, self.elevation - TILT_RATE_RAD_PER_MS * dt)

        if white_held and not self.white_was_held:
            self.azimuth = DEFAULT_AZIMUTH
            self.elevation = DEFAULT_ELEVATION
        self.white_was_held = white_held

        return self


def new_ball_machine() -> BallMachineState:
    return BallMachineState()

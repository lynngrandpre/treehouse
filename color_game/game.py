import random
from dataclasses import dataclass
from math import cos, sin, pi

import pygame

from hardware import Color, RGB, buttons, buttons_in_order
from common import Input


def average(rgbs):
    current_color = RGB(0, 0, 0)
    if len(rgbs) == 0:
        return current_color

    for rgb in rgbs:
        current_color += rgb

    return current_color / len(rgbs)


MAX_BUTTONS_TO_MIX = 3

COLOR_MIXER_ANIM_DURATION = 750
COLOR_MIXER_ANIM_HOLD_FINAL = 1250
COLOR_MIXER_MIN_VICTORY_SCREEN_DURATION = COLOR_MIXER_ANIM_DURATION + COLOR_MIXER_ANIM_HOLD_FINAL


def gen_target_colors(max_num_buttons_for_mix):
    all_colors = list(Color)
    num_colors_to_mix = random.randint(1, min(max_num_buttons_for_mix, len(all_colors)))
    cols = random.sample(all_colors, num_colors_to_mix)
    return [buttons[col].rgb for col in cols]


@dataclass
class ColorMixerState:
    target_rgbs: "list[RGB]"
    victory_anim_start_time: int
    victory_screen_end_time: int
    victory_rgbs: "list[RGB]"
    last_change_time: int
    last_rgb: RGB
    max_num_buttons: int

    def __post_init__(self):
        if not self.target_rgbs:
            self.target_rgbs = gen_target_colors(self.max_num_buttons)
        # Ensure the initial screen is the game, not a victory animation.
        self.victory_anim_start_time = -COLOR_MIXER_MIN_VICTORY_SCREEN_DURATION
        self.victory_screen_end_time = -COLOR_MIXER_MIN_VICTORY_SCREEN_DURATION
        self.victory_rgbs = []
        self.last_change_time = -100
        self.last_rgb = RGB(0, 0, 0)

    def draw(self, surface):
        CANVAS_WIDTH, CANVAS_HEIGHT = surface.get_size()
        center_x = CANVAS_WIDTH // 2
        center_y = CANVAS_HEIGHT // 2
        current_time = pygame.time.get_ticks()

        if current_time > self.victory_screen_end_time:
            current_rgb_from_buttons = average([button.rgb for button in buttons_in_order if button.is_pressed()])
            surface.fill(current_rgb_from_buttons.to_tuple())
            pygame.draw.circle(surface, average(self.target_rgbs).to_tuple(), (center_x, center_y), 100)
        else:
            surface.fill((222, 222, 222))

            num_squares = len(self.victory_rgbs)

            t = max(0, (current_time - self.victory_anim_start_time) / COLOR_MIXER_ANIM_DURATION)
            t_capped = min(1, t)
            u = max(0, (current_time - self.victory_anim_start_time) / COLOR_MIXER_MIN_VICTORY_SCREEN_DURATION)

            for i, victory_rgb in enumerate(self.victory_rgbs):
                surf = pygame.Surface((200, 200), flags=pygame.SRCALPHA)
                surf.fill((0, 0, 0, 0))

                pygame.draw.circle(surf, victory_rgb.to_tuple() + (255 // num_squares,), (100, 100), 100)

                start_center_x = center_x
                start_center_y = center_y

                direction_rads = i / num_squares * (2 * pi) - pi / 2 + u / 2 * pi
                distance_to_travel = 60
                dx = distance_to_travel * cos(direction_rads)
                dy = distance_to_travel * sin(direction_rads)

                end_center_x = start_center_x + dx
                end_center_y = start_center_y + dy

                current_center_x = start_center_x + (end_center_x - start_center_x) * t_capped
                current_center_y = start_center_y + (end_center_y - start_center_y) * t_capped

                surface.blit(surf, (current_center_x - 100, current_center_y - 100))

    def next_state(self, input: Input):
        current_time = input.current_time

        for button in buttons.values():
            if not button.is_pressed():
                button.set_led(True)
            else:
                button.set_led(False)

        if current_time > self.victory_screen_end_time:
            rgbs = [button.rgb for button in input.buttons if button.is_pressed()]
            current_rgb = average(rgbs)

            if current_rgb != self.last_rgb:
                self.last_rgb = current_rgb
                self.last_change_time = current_time

            if current_rgb == average(self.target_rgbs) and (self.last_change_time + 150 < current_time):
                self.victory_rgbs = self.target_rgbs
                self.target_rgbs = gen_target_colors(self.max_num_buttons)
                self.victory_screen_end_time = current_time + COLOR_MIXER_MIN_VICTORY_SCREEN_DURATION
                self.victory_anim_start_time = current_time
        else:
            if any(button.is_pressed() for button in input.buttons):
                self.victory_screen_end_time = max(self.victory_screen_end_time, current_time + 200)

        return self


def new_color_game():
    return ColorMixerState(
        target_rgbs=[],
        victory_anim_start_time=0,
        victory_screen_end_time=0,
        victory_rgbs=[],
        last_change_time=0,
        last_rgb=RGB(0, 0, 0),
        max_num_buttons=MAX_BUTTONS_TO_MIX,
    )

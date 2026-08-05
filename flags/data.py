"""Country data grouped by continent: name, capital, and a simplified flag
description. Flags here are stylized -- stripes, an optional corner canton,
and an optional center circle -- since the game only has pygame's drawing
primitives to work with, not real flag images. They're recognizable, not
pixel-accurate.
"""

from __future__ import annotations

from dataclasses import dataclass

RGB = tuple[int, int, int]


@dataclass
class Flag:
    stripes: list[RGB]
    orientation: str = "horizontal"  # or "vertical"
    canton: RGB | None = None
    circle: RGB | None = None


@dataclass
class Country:
    name: str
    capital: str
    flag: Flag


WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (206, 17, 38)
GREEN = (0, 135, 81)
YELLOW = (255, 205, 0)
BLUE = (0, 39, 118)

CONTINENTS: dict[str, list[Country]] = {
    "Africa": [
        Country("Nigeria", "Abuja", Flag([GREEN, WHITE, GREEN], "vertical")),
        Country("Ghana", "Accra", Flag([RED, YELLOW, GREEN], "horizontal", circle=BLACK)),
        Country("Kenya", "Nairobi", Flag([BLACK, RED, GREEN], "horizontal")),
        Country("Egypt", "Cairo", Flag([RED, WHITE, BLACK], "horizontal")),
        Country("Ethiopia", "Addis Ababa", Flag([GREEN, YELLOW, RED], "horizontal")),
        Country("Mali", "Bamako", Flag([GREEN, YELLOW, RED], "vertical")),
        Country("Senegal", "Dakar", Flag([GREEN, YELLOW, RED], "vertical", circle=GREEN)),
        Country("Cameroon", "Yaounde", Flag([GREEN, RED, YELLOW], "vertical", circle=YELLOW)),
    ],
    "Asia": [
        Country("Japan", "Tokyo", Flag([WHITE], "horizontal", circle=RED)),
        Country("India", "New Delhi", Flag([(255, 153, 51), WHITE, GREEN], "horizontal", circle=(0, 0, 128))),
        Country("China", "Beijing", Flag([RED], "horizontal", canton=YELLOW)),
        Country("Indonesia", "Jakarta", Flag([RED, WHITE], "horizontal")),
        Country("Thailand", "Bangkok", Flag([RED, WHITE, BLUE, WHITE, RED], "horizontal")),
        Country("Vietnam", "Hanoi", Flag([RED], "horizontal", circle=YELLOW)),
        Country("Bangladesh", "Dhaka", Flag([GREEN], "horizontal", circle=RED)),
        Country("Turkey", "Ankara", Flag([RED], "horizontal", circle=WHITE)),
    ],
    "Europe": [
        Country("France", "Paris", Flag([BLUE, WHITE, RED], "vertical")),
        Country("Germany", "Berlin", Flag([BLACK, RED, YELLOW], "horizontal")),
        Country("Italy", "Rome", Flag([GREEN, WHITE, RED], "vertical")),
        Country("Ireland", "Dublin", Flag([GREEN, WHITE, (255, 136, 0)], "vertical")),
        Country("Belgium", "Brussels", Flag([BLACK, YELLOW, RED], "vertical")),
        Country("Poland", "Warsaw", Flag([WHITE, RED], "horizontal")),
        Country("Netherlands", "Amsterdam", Flag([RED, WHITE, BLUE], "horizontal")),
        Country("Sweden", "Stockholm", Flag([BLUE], "horizontal", canton=YELLOW)),
    ],
    "Americas": [
        Country("United States", "Washington D.C.", Flag([RED, WHITE, RED, WHITE, RED], "horizontal", canton=BLUE)),
        Country("Canada", "Ottawa", Flag([RED, WHITE, RED], "vertical")),
        Country("Mexico", "Mexico City", Flag([GREEN, WHITE, RED], "vertical")),
        Country("Brazil", "Brasilia", Flag([GREEN], "horizontal", circle=YELLOW)),
        Country("Argentina", "Buenos Aires", Flag([(117, 170, 219), WHITE, (117, 170, 219)], "horizontal")),
        Country("Colombia", "Bogota", Flag([YELLOW, BLUE, RED], "horizontal")),
        Country("Bolivia", "La Paz", Flag([RED, YELLOW, GREEN], "horizontal")),
        Country("Chile", "Santiago", Flag([WHITE, RED], "horizontal", canton=BLUE)),
    ],
    "Oceania": [
        Country("Australia", "Canberra", Flag([(0, 34, 78)], "horizontal", canton=WHITE)),
        Country("New Zealand", "Wellington", Flag([(0, 34, 78)], "horizontal", canton=RED)),
        Country("Fiji", "Suva", Flag([(114, 168, 222)], "horizontal", canton=WHITE)),
        Country("Papua New Guinea", "Port Moresby", Flag([RED, BLACK], "horizontal")),
        Country("Samoa", "Apia", Flag([RED], "horizontal", canton=BLUE)),
        Country("Tonga", "Nuku'alofa", Flag([RED], "horizontal", canton=WHITE)),
        Country("Vanuatu", "Port Vila", Flag([RED, GREEN, BLACK], "vertical")),
        Country("Palau", "Ngerulmud", Flag([(0, 133, 202)], "horizontal", circle=YELLOW)),
    ],
}

from common import Game

from .game import new_pacman_with_rules

games = [
    Game("Pac-Duo", new_pacman_with_rules),
]

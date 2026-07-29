from common import Game

from .game import new_space_invaders_with_rules

games = [
    Game("Space Invaders", new_space_invaders_with_rules),
]

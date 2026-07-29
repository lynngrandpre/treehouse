from common import Game

from .game import new_tetris_with_rules

games = [
    Game("Tetris", new_tetris_with_rules),
]

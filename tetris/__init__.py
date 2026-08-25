from common import Game

from .game import new_tetris_with_rules

games = [
    Game("Papa Tetris", new_tetris_with_rules),
    Game("Papa Tetris: Bomb", lambda: new_tetris_with_rules(bomb_mode=True)),
]

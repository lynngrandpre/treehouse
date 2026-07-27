from common import Game

from .game import new_breakout_with_rules

games = [
    Game("Breakout", new_breakout_with_rules),
]

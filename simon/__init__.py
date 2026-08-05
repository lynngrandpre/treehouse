from common import Game

from .game import new_simon_with_rules

games = [
    Game("Simon Says", new_simon_with_rules),
]

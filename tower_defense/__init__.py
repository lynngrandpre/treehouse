from common import Game

from .game import new_tower_defense_with_rules

games = [
    Game("Tower Defense Duo", new_tower_defense_with_rules),
]

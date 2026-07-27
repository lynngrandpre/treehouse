from common import Game

from .game import new_pacman_with_rules

games = [
    Game("Pac-Duo Easy", lambda: new_pacman_with_rules(ghost_count=1, ghost_interval_ms=480)),
    Game("Pac-Duo", new_pacman_with_rules),
]

from common import Game

from .game import new_mastermind

games = [
    Game("Mastermind", new_mastermind),
]

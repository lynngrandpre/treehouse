from common import Game

from .game import new_color_game

games = [
    Game("Color Easy", lambda: new_color_game(1, 2)),
    Game("Color Medium", lambda: new_color_game(2, 4)),
    Game("Color Hard", lambda: new_color_game(3, 5)),
]

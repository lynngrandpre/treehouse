from common import Game

from .game import new_quiz

games = [
    Game("Capitals HARD", lambda: new_quiz("capitals_hard")),
    Game("Capitals", lambda: new_quiz("capitals")),
    Game("Sports", lambda: new_quiz("sports")),
    Game("Jeopardy!", lambda: new_quiz("jeopardy")),
]

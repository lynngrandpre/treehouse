from common import Game

from .game import new_flags_quiz

games = [
    Game("Africa Flags", lambda: new_flags_quiz("Africa")),
    Game("Asia Flags", lambda: new_flags_quiz("Asia")),
    Game("Europe Flags", lambda: new_flags_quiz("Europe")),
    Game("Americas Flags", lambda: new_flags_quiz("Americas")),
    Game("Oceania Flags", lambda: new_flags_quiz("Oceania")),
]

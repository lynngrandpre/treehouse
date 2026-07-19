# Running

On the Pi: `uv run driver.py`
Simulator: `uv run driver.py --simulator`

# Editing

Linter: `uvx ruff check`
Typecheck: `uvx ty check`
Test: `uvx run pytest`

# Structure

New games should be place in their own directory. They should expose a list of games in **init**.py, and that list should be imported from menu.py

Ideally, every game should be written in the "state machine style" of quiz. For more continuous games, you can do something like color_game - just one state that always returns itself.

Returning None from next_state will yield control back to the menu, and allow the player to pick a new game.

#!/bin/sh
set -eu
cd "$(dirname "$0")"
if command -v uv >/dev/null 2>&1; then
    exec uv run driver.py --simulator --starship
fi
if python3 -c 'import pygame' >/dev/null 2>&1; then
    exec python3 driver.py --simulator --starship
fi
echo "Pygame is required. From this folder run:"
echo "  python3 -m venv .venv"
echo "  .venv/bin/pip install pygame"
echo "  .venv/bin/python driver.py --simulator --starship"
printf 'Press Enter to close.'
read answer

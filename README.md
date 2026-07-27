# Running

On the Pi: `uv run driver.py`
Simulator: `uv run driver.py --simulator`

# Editing

Linter: `uvx ruff check`
Typecheck: `uvx ty check`
Test: `uvx run pytest`

# Structure

New games should be place in their own directory. They should expose a list of games in `__init__.py`, and that list should be imported from menu.py

Ideally, every game should be written in the "state machine style" of quiz. For more continuous games, you can do something like color_game - just one state that always returns itself.

Returning None from next_state will yield control back to the menu, and allow the player to pick a new game.

# Deployment (this Pi)

The game runs as a systemd **user** service, not an ad-hoc background process:

```bash
systemctl --user status treehouse
systemctl --user restart treehouse
systemctl --user stop treehouse
journalctl --user -u treehouse -f   # logs
```

Unit file: `~/.config/systemd/user/treehouse.service`. It runs `uv run driver.py` from this directory, with `Restart=on-failure` so a crash auto-recovers.

## NanoClaw agent (Telegram)

This project has a [NanoClaw](https://github.com/nanocoai/nanoclaw) agent ("Tarzan") wired to a Telegram bot (`@grandpre_treehouse_bot`), so changes can be requested and applied by messaging the bot. The agent runs in an isolated Docker container with this directory mounted read-write at `/workspace/extra/treehouse`.

### Restarting the game to test changes

Because the agent runs in an isolated container, it has no direct access to the host's systemd. A small bridge exists for exactly one purpose — restarting `treehouse.service` — so the agent can apply and test changes without an operator manually restarting it:

- **Listener**: `~/nanoclaw/scripts/treehouse-restart-listener.py`, run as the systemd user service `treehouse-restart-listener.service`. Binds to `172.17.0.1` (the Docker bridge IP) on port `8765` — reachable from containers on the default bridge network and from the host itself, not from the LAN or internet.
- **Auth**: a random token lives at `.restart-token` in this directory (gitignored, mode 600). The listener only restarts the service if the caller supplies the matching `X-Restart-Token` header.
- **Trigger a restart** (from inside the agent's container, or from the host):

  ```bash
  TOKEN=$(cat /workspace/extra/treehouse/.restart-token)   # from inside the container
  # TOKEN=$(cat .restart-token)                            # from the host
  curl -s -X POST -H "X-Restart-Token: $TOKEN" http://172.17.0.1:8765/restart
  ```

  Returns `200 restarted` on success, `403` on a missing/wrong token.

Management commands for both services:

```bash
systemctl --user status|restart|stop treehouse-restart-listener
journalctl --user -u treehouse-restart-listener -f
```

Both units are enabled (`systemctl --user enable`) and `loginctl linger` is on for this user, so they come back after a reboot without needing a login session.

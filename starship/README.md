# Treehouse Starship

A persistent, local cooperative space adventure for one systems officer at the
five-button panel and one or two players with wired Xbox controllers. Original
artwork and synthesized audio; no network connection or asset downloads at play time.

## Play

On the existing Raspberry Pi installation, choose **Arcade Games → last page →
Treehouse Starship**. Or start directly with `uv run driver.py --starship`.

On a Mac, double-click `Play Starship.command`, or use:

```sh
python3 driver.py --simulator --starship
# With the project's uv environment:
uv run driver.py --simulator --starship
```

If Pygame is missing, create a local environment:

```sh
python3 -m venv .venv
.venv/bin/pip install pygame
.venv/bin/python driver.py --simulator --starship
```

## Your first voyage

1. Choose **Begin voyage** with A / Enter / the blue panel button.
2. You start inside Canopy Anchorage's docking range. Press controller X or E.
3. Select the greenhouse delivery contract. Four mission crates are loaded.
4. Launch, open the chart with Y / Tab, select **The Drift**, and jump with A.
5. Explore, collect salvage with the white button, or continue to **Lantern**.
   Nearby active enemies prevent a jump; defeat them or boost out of range.
6. Fly toward Lantern Outpost's ring (the radar and PORT marker guide you), then
   press X / E. Docking pays 300 credits and refuels/repairs the ship for free.
7. Buy an upgrade or accept Lantern's rescue contract. Recover its escape pod
   in The Drift using the tractor beam, then return to Lantern for 450 credits.
8. Return to Canopy for the raider contract. Destroy or capture its three marked
   targets, then dock at Canopy to claim 600 credits.

Trading supplies cost/sell for 35 credits at Canopy and 70 at Lantern. Contracts
reserve cargo space; mission cargo cannot accidentally be sold. One contract is
active at a time. Contracts can be repeated to fund further upgrades.

## Crew controls

| Role | Xbox controller | Keyboard / physical panel |
| --- | --- | --- |
| Systems officer | Separate from both gamepads | Red / 1 heavy cannon; green / 2 repair; blue / 3 shield; yellow / 4 boost; white / 5 tractor |
| Pilot, first controller | Left stick steer/thrust; A or RT fire; B brake; X dock; Y chart; Start pause | WASD or arrows; Space fire; S/down brake; E dock; Tab chart; P/Escape pause |
| Wingmate, second controller | Left stick move; right stick aim; A or RT fire; X launch/dock | F2 join; IJKL move/aim; U fire; O launch/dock |

Panel LEDs show readiness. Systems use shared energy, recharge over time, and
repeat while held. Repair stays unlit at full hull. Tractor locks onto the
nearest salvage, survivor pod, or disabled raider within its visible radius;
stay close for the recovery cycle. Stop shooting disabled ships to capture them.

The wingmate starts in the turret. Launch to collect salvage or fight within the
mothership's shared-screen flight radius. Return within 150 world units to dock.
A downed escort is recovered automatically; the player keeps using the turret
while the escort repairs. Without a wingmate, the turret assists automatically.

Menus use D-pad / arrows and A / Enter. Panel menus use **red previous, green next,
blue select, white back**. On the chart, yellow offers a rescue tug with a
confirmation step. The big red hardware button saves and returns to the original
Treehouse menu.

Controllers are assigned in connection order for this application session. Unplugging
the pilot does not promote the wingmate into the pilot role. A replacement fills
the vacant role. SDL's standard Xbox mappings are used when recognized, with a
basic XInput fallback (A to fire). The cockpit shows controller/role status.

## What's in this first playable version

- Three connected systems, two ports, free flight, a local radar and star chart.
- Delivery, rescue and bounty contracts; trading, salvage and ship capture.
- Independent pilot and wingmate, dockable escort, automatic turret, five console systems.
- Five upgrade families, each with three levels; fuel, cargo and shared energy.
- Ranger and Scrap Union reputation counters, mission milestones and visited systems.
- Automatic recovery after ship loss. The rescue tug also prevents fuel softlocks.
- Persistent campaign and current encounter; pause/help screens and synthesized sound.

The larger concept's additional ship hulls, branching faction storylines, ambient
trader fleets, extra planets, and physical patch-cable puzzles are future expansion
points. This build uses one upgradeable mothership and one escort.

## Saves

Saved in `starship/data/campaign.json`, outside version control. Saving happens
every 20 seconds of flight, at purchases, docking, jumps, pausing and graceful exit.
An interrupted write cannot truncate the last good save. New Campaign asks for
confirmation and preserves the previous file as `campaign.previous.json`.

An unreadable or newer-format save is preserved and autosaving is disabled until
the player explicitly starts a new campaign. Save failures appear in the UI.
For isolated testing, set `STARSHIP_SAVE_PATH` to a different path.

## Integration and installation

This adds `starship/` and updates `menu.py`, `driver.py`, and `gamepad.py`. It uses
the existing `hardware.py` GPIO mapping. Starship keeps controller inputs separate;
other games retain their original shared-controller behavior. The driver also
counts stick activity for screen wakefulness and limits its loop to 60 FPS.

Merge/apply the reviewed change into the Pi's existing repository, keeping local
hardware configuration and saved data. Then use the existing service:

```sh
systemctl --user restart treehouse
systemctl --user status treehouse --no-pager
journalctl --user -u treehouse -n 40 --no-pager
```

For a separate, reversible trial, unpack the source package into a new directory
on the Pi, copy its working `hardware.py` if it differs, stop the existing service,
and run `uv run driver.py --starship` in the new directory. After the trial, restart
the original service. Do not run two games against GPIO simultaneously.

## Validation

```sh
python3 -m pytest -q
ruff check starship gamepad.py driver.py menu.py test_starship.py test_gamepad.py test_menu.py
ty check starship gamepad.py driver.py menu.py
```

The tests cover full contract round trips, combat/capture, recovery, energy and
cooldowns, controller hot-plug/role isolation, atomic saves and corrupt-save
protection. All screens render at 800×480, 1000×600 and 1280×720. Physical Xbox
controller mappings and actual Pi frame rate still require hardware validation.

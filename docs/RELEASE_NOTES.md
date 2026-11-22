# Krampuslauf 1.8.0-beta.5

A Windows beta for seasonal gift runs in the official Ultima Online Classic Client with Razor Enhanced. Character Seeder fills available character slots on selected shards and Gift Cycler logs existing characters in and out for eligible holiday rewards.

## What's new since 1.8.0-beta.4

- Characters 2–7 on a shard that was already entered click the last-shard button. The built-in game-area point is (192, 429). The shard list is used the first time a shard is entered.
- The pointer is no longer moved to a corner.
- Setup progress can open Profiles, Game Client, and Shards. The checklist no longer shows an administrator status.

## Install

Download `Krampuslauf_1.8.0-beta.5_Windows_x64.zip`, extract the entire archive, and open `Krampuslauf.exe`. The build includes its Python runtime. Keep the extracted folder together and follow the [configuration guide](../CONFIGURATION.md) to set up Razor Enhanced and the Classic Client. Start with one shard and one existing character before enabling character creation.

If you prefer to run from source, use either of the source archives generated for this release. See [Run the source](../README.md#run-the-source) for prerequisites and setup.

## What's included

- Built-in menu recognition and click positions for the Classic Client's 640 x 480 game area. Use **Setup > Game Client > Check current screen** to confirm detection.
- Character creation with fixed or randomized appearance, automatic naming, and the option to reserve one open slot per shard.
- Per-account progress, shard selections, and slot skips for Gift Cycler and Character Seeder. You can retry an interrupted run without starting the whole list again.
- **Escape** pauses a run. Press it again while paused to stop, or use **Resume** in the Activity window to continue.

## December 2026 holiday gifts

Seed your account early. Publish 125 lists a minimum age of **30 days** for veteran characters and a **December 1–31, 2026** redemption window in Eastern time. Once your new characters reach 30 days old, start a **New gift cycle** and run **Gift Cycler** before the window closes. [Official Ultima Online Publish 125 notes](https://uo.com/wiki/ultima-online-wiki/publish-notes/publish-125/)

## Updating and feedback

Close Krampuslauf and back up `%LOCALAPPDATA%\Krampuslauf` before updating. Keep your character histories and Razor profile-recovery backups. If you already installed the supplied bridge, use the configuration guide to confirm Razor starts a single copy of `krampuslauf_bridge.py`.

Gift Cycler records verified login, wait, and logout. Check your character's backpack for the reward after your first run.

Include your beta version, Windows display scaling, and a short relevant activity-log excerpt when reporting an issue. [GitHub issues](https://github.com/mystic-llama/krampuslauf/issues)

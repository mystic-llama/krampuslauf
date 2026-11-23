# Krampuslauf 1.8.0-beta.7

A Windows beta for seasonal gift runs in the official Ultima Online Classic Client with Razor Enhanced. Character Seeder fills available character slots on selected shards and Gift Cycler logs existing characters in and out for eligible holiday rewards.

## What's new since 1.8.0-beta.6

- **Resume after an unconfirmed creation.** Dismiss any open game message and restart from Login or Shard Select. Character Seeder checks the live shard menu and records the old attempt. If there is room, it continues with a fresh name.
- **Transfer-slot limits use the live roster.** If the earlier attempt created a character, that character counts toward the limit when the Seeder checks the shard again.

## Install

Run `Krampuslauf_1.8.0-beta.7_Windows_x64_Setup.exe` to install. For a portable copy, extract `Krampuslauf_1.8.0-beta.7_Windows_x64.zip` and open `Krampuslauf.exe` inside the extracted folder. Both Windows packages include the Python runtime.

Use `Krampuslauf_1.8.0-beta.7_Full_Source.zip` for development or to build from source. See [Run the source](../README.md#run-the-source) for prerequisites and setup.

Follow the [configuration guide](../CONFIGURATION.md) to set up Razor Enhanced and the Classic Client.

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

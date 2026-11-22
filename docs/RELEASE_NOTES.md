# Krampuslauf 1.8.0-beta.6

A Windows beta for seasonal gift runs in the official Ultima Online Classic Client with Razor Enhanced. Character Seeder fills available character slots on selected shards and Gift Cycler logs existing characters in and out for eligible holiday rewards.

## What's new since 1.8.0-beta.5

- **Shard groups.** Choose All, English, or Asian shards on either automation page. Each account saves its selection, and the individual shard checkboxes still apply.
- **Randomize All.** Choose this option on the Appearance page to use all available appearance choices for new characters.
- **Race-based naming.** Character Seeder applies appearance before reserving a fantasy name for the selected race and sex. The gargoyle libraries now have 5,496 male and 3,381 female single-word names.
- **Resume with new preferences.** Change appearance or naming options between runs. The Seeder checks unsubmitted name reservations against the new selection and preserves submitted names for recovery.
- **Fantasy name screening.** Skip common blocked fragments within words and across the space in a full name. The Seeder rechecks saved names that have yet to be submitted.
- **Shard scanning.** The scan brings the chosen Classic Client window to the foreground before checking whether the shard list is open.

## Install

Run `Krampuslauf_1.8.0-beta.6_Windows_x64_Setup.exe` to install. For a portable copy, extract `Krampuslauf_1.8.0-beta.6_Windows_x64.zip` and open `Krampuslauf.exe` inside the extracted folder. Both Windows packages include the Python runtime.

Use `Krampuslauf_1.8.0-beta.6_Full_Source.zip` for development or to build from source. See [Run the source](../README.md#run-the-source) for prerequisites and setup.

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

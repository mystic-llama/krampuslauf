# Krampuslauf 1.8.0-beta.4

A public source beta for the official Ultima Online Classic Client with Razor Enhanced.

## Download and configure

Download the **Full Source ZIP**, extract it, and follow the included **CONFIGURATION.md** from the beginning. The source needs Windows, Python 3.12 and the .NET Framework runtime. This source package does not include a compiled Windows EXE.

## Changes

- **Global transfer-slot reservation:** under **Automation > Character Seeder**, choose the actual account capacity, enable **Keep one slot empty on every shard**, and click **Save history**. Seven-slot accounts stop creation at six total characters, including existing characters. Both creation modes honor this saved account setting; it is off by default.
- Standalone reservation checks existing rows without recording gift completion. Existing seventh characters can still receive Gift Cycler processing. Full shards are not cleared or altered; no character is deleted.
- Clearer pre-click marker error: tooltip interference is explained without incorrectly reporting a mouse pause. Native mouse timing is unchanged.
- Hardened profile restoration: saved file paths must match the expected Razor registry and recovery locations. Linked paths, malformed recovery records and invalid backup content are refused before restoration.
- Full **250 × 250** Krampuslauf artwork beside the Setup checklist, with the compact banner logo retained.
- **MIT license**, private-data `.gitignore`, and a detailed configuration guide.
- Includes the beta.2 improvements: typing approval persists across naming choices; a missed mouse target pauses before an unsent click; Resume checks the same game screen/window; Escape pauses and a second press while paused stops.
- Six full-width main tabs, focused subtabs, clear NEXT instructions and Help artwork/theme controls.

## Existing users

Close Krampuslauf and privately back up `%LOCALAPPDATA%\Krampuslauf` before updating. All versions share that data folder. The first launch moves an older data folder when the new one is not already there. Keep pending-creation records, name histories and profile-recovery backups. A source update requires rebuilding any previously compiled EXE.

The included Razor bridge is unchanged from the supplied 1.7.6 baseline. If you already use that exact script, no bridge replacement is required. New users must install it in Razor's **default** profile and enable **AutoStart at Login**.

Capacity is selected by the user, not automatically detected. Reservation relies on calibrated row/menu recognition. Check one partly populated shard before unattended operation. Siege Perilous and Mugen are excluded from creation and gift runs. Pending creation and route-recovery safeguards remain in force.

## Validation and beta limits

**286 tests and 19 subtests pass**, including transfer-slot reservation, profile restoration, bridge simulations, naming approval, input interruption and pending-character recovery. The updated Seeder page has been checked in both browser-preview themes. These checks do not establish native Windows or live-game behavior; a Windows build and supervised client testing remain necessary.

Start with one shard and an existing character. Gift completion records verified entry, waiting and logout; it does not inspect inventory. Town Crier right-click cleanup is optional and can interact with the world if the window is absent. Inspect an uncertain creation before using **Automation > Recovery**.

Report the version, Windows scaling, tab/action and a short relevant saved activity-log excerpt through the [Krampuslauf project](https://github.com/mystic-llama/krampuslauf). Remove personal details before posting. Do not upload your app-data folder or Razor settings.

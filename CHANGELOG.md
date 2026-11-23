# 1.8.0-beta.7

- Resume Character Seeder from the live shard menu after an unconfirmed character creation. Keep a record of the earlier attempt and use a fresh name if a slot is open.
- Recheck live character slots before continuing so an earlier attempt that created a character counts toward the transfer-slot limit.
- Update the recovery message and add tests for resuming with an open slot and at the transfer-slot limit.

# 1.8.0-beta.6

- Add per-account shard groups for Gift Cycler and Character Seeder. Run all eligible shards, English shards, or Asian shards alongside individual shard exclusions.
- Add Randomize All to Appearance. The Seeder applies the chosen appearance before reserving a fantasy name for that race and sex. Changed appearance and naming settings apply to future creations, with submitted names preserved for recovery.
- Expand gargoyle single-name pools to 5,496 male and 3,381 female names.
- Screen fantasy names for common blocked fragments within each word and across the space in a full name. Recheck unsubmitted reservations before reuse.
- Bring the selected Classic Client window to the foreground for the shard scan's opening screen check.
- Publish a Windows x64 installer alongside the portable and full source ZIPs.

# 1.8.0-beta.5

- The pointer is no longer moved to a corner at any point. Checklist item 1 asks for tooltips off or a 5000 ms delay, and item 3 includes AutoStart at Login.
- Characters 2–7 on the last shard click the last-shard button at game-area (192, 429). The shard list is used only the first time a shard is entered.
- Setup progress can jump to Profiles, Game Client, and Shards. Setup no longer shows an administrator status.
- Setup shows the remaining steps in order, opens the bridge script in Explorer, and fills a Razor data folder when only one is found.
- Saved data now lives in `%LOCALAPPDATA%\Krampuslauf`. The first launch moves an older data folder when the new one is not already there.
- Help explains why donations matter, shows the PayPal donate button, and gives Discord @mystikllama for in-game gold.
- Point project and support links at https://github.com/mystic-llama/krampuslauf.
- Close reminders now offer Return to Profiles or explicit Close anyway; X, Escape and Enter keep the app open and return to Profiles.
- Remove unsupported shards from destinations and run tasks while retaining their physical row positions for accurate navigation.
- Remove End attempt / Start fresh. A fresh logged-out run retains confirmed characters and archives their interrupted routes without replaying them or erasing finished checkpoints.
- Add an optional Donate with PayPal button on Help using the supplied hosted donation link.
- Remove header gift bookends, expand the title into a 144-pixel header, and enlarge checklist artwork to 350 x 438. The 720 x 890 layout fixes the previous checklist overlap and text clipping.

- Map all 54 elf hair colours and 18 gargoyle horn/facial-horn colours using the supplied palette images, including race-specific screen recognition and 100%/125%/150% coordinate scaling. Colour choices save per race; unavailable facial colours are skipped.
- Remove the duplicate History tab. Keep the Activity window and saved activity/error logs, accessible through Help / Status > Status > Open local data folder.
- Add a per-account Before inn route (sec) setting to Character Seeder: 0–120 seconds, default 5, after verified world entry and before requesting the route. Applies to both creation modes.

- Rename the application, executable, documentation and title to Krampuslauf; preserve existing data identities and bridge compatibility.
- Expand account selection to 15 accounts in five rows of three, with optional nicknames capped at 16 characters. Existing accounts retain their nicknames, settings and progress.
- Add the required checklist item for tooltips off or a 5000 ms delay in Game Options. Checking every box is required before proceeding. Render both lines of checklist captions.
- **No more menu calibration.** The Classic Client draws its login, shard, character and creation menus in a fixed 640 × 480 game area. Click positions and screen markers are now built in (`menu_layout.py`, `assets/screen_markers/`), measured from the game area instead of the outer window corner, so title-bar height, borders and Windows theme no longer affect them.
- Windows display scaling is detected from the game-area size (for example 800 × 600 at 125%) and applied to clicks and marker images automatically. A non-4:3 or in-world view is reported as unknown and never clicked.
- Removed Calibration > Client & menus markers/points, Calibration > Creation, Calibration > Warnings and Calibration > World entry. The Calibration tab is now **Game client**: select the window and use **Check current screen**, a read-only report of game-area size, scaling and the recognized menu.
- Removed all Town Crier and window-cleanup behavior (right-click mode, RE-managed Town Crier/All modes and their tests). `krampuslauf_bridge.py` is unchanged; it simply never receives a cleanup command.
- **Game client > Click points:** re-record any built-in click position by hovering over it (measured in the 640 × 480 game area), or reset it to built-in. Recorded points are saved as `point_overrides`.
- **Automation > Appearance / Skin tone:** choose sex, race, hair, facial hair or horn styles and skin tones for new characters, in Fixed or Random mode. Appearance is selected before the name is typed. Skin tones are calculated from each palette's recorded top-left and bottom-right cells. Appearance-screen click positions are estimated and should be verified on a first creation.
- Retired the name-typing test and its creation gate.
- **Shards are found by reading the list.** The client draws shard names in one fixed font, so `shard_rows.py` matches the visible rows against a small saved picture of each name. Runs scroll the list with the mouse wheel (one row per wheel event), read the rows again after every step and click only a row read as the target, instead of counting arrow clicks. Dropped wheel events are corrected by the next read. If names cannot be read, the scroll-arrow burst is used as before.
- **Shards > Learn shard names** saves those pictures in one wheel-only pass (about 20 seconds), labelled from the verified shard order. They are also learned automatically from title-verified shard clicks and from the scan. A picture that ever leads to the wrong shard is deleted. Pictures live in `%LOCALAPPDATA%\Krampuslauf\shard_names`.
- **The pointer is no longer moved after every click or key press.** It stays where the last input left it. If it has rested in one place for 4 seconds while the program waits, it is moved to blank menu artwork so a tooltip cannot cover a screen marker. A pointer you have moved yourself is never touched, nothing is moved while paused or in the world view, and `park_idle_seconds` in `settings.json` changes the delay (0 turns it off). Reading the shard list still moves the pointer off the rows first, because the pointer itself hides names.
- **Much faster screen reading.** Pillow's `ImageGrab.grab(bbox)` copies the whole primary screen and crops afterwards, and every marker was captured separately: a screen read took about 200 ms and each click about 850 ms. `screen_capture.py` now copies only the needed rectangle with GDI, and one read captures the menu area once and cuts all the marker regions from it (a screen copy costs about one display refresh whatever its size). A read is now about 16 ms. Images stay in memory and are never saved or sent. The New-button check also stops as soon as two of its three samples decide it.
- **Shard rows are double-clicked at human speed** (about 0.11 s between clicks), including retries and the scan, because a single click on a row was sometimes ignored. Just before the second click the screen is read again, and the second click is only sent while the shard list is still showing, so it can never land on the character list the first click opened. Character slots were already double-clicked.
- A slow shard connection no longer halts the run or triggers Origin-error recovery. The stone panel the client shows while it connects or loads the world matches the Origin error marker, and the previous checks gave up after 0.2 to 0.6 s. Shard selection, menu navigation and world entry now wait up to 30 seconds (`sync_transient_seconds` in `settings.json`) for the panel to clear before treating it as a real error; no input is sent while waiting.
- Existing saved points are no longer used. On first start, a settings file containing old points is copied once to `settings.before-built-in-layout.json`; old marker images in the data folder are left untouched.

# 1.8.0-beta.4

- Added an account-scoped **Keep one slot empty on every shard** option and a 5/6/7-slot capacity selector to Automation > Character Seeder. Both creation modes stop at capacity minus one, including existing characters. Default is off.
- Standalone reservation checks existing rows using the existing world-entry/identity flow, without updating gift progress. It stores a separate handoff checkpoint so later gift runs do not skip existing characters. Existing seventh characters remain eligible for gifts.
- One-slot shards receive no new creation while reservation is enabled. Already-full shards are never cleared. Lowering the limit preserves pending and unfinished records; raising it permits another discovery pass.
- Corrected marker-mismatch wording when no mouse pause occurred, with tooltip-safe calibration guidance. Native mouse timing and the Razor bridge are unchanged.
- Updated configuration/release instructions and added simulated reservation, persistence, recovery and gift-eligibility tests. Source only; native Windows and live-client validation remain required.

# 1.8.0-beta.3

- Show the 250 × 250 Krampuslauf artwork beside a readable two-column Setup checklist, retaining the banner icon and NEXT directions.

- Constrain profile recovery to the two Razor NewProfiles files and the application’s recovery folder. Refuse redirected paths, malformed records and invalid backup content before restoration.
- Add regression coverage for tampered paths, attempted outside-file writes/deletions, symlinks, simulated Windows reparse points and recovery errors.
- Add the MIT license, expanded private-data .gitignore, detailed configuration, publishing instructions and source security review.
- Include LICENSE and CONFIGURATION.md in the Windows distribution.
- Game automation and the Razor bridge are unchanged from beta.2. This package contains source; Windows build and live-client validation are still required.

# 1.8.0-beta.2

- Preserve successful typing approval across naming changes and application restarts. Removed the per-fantasy-style retest requirement and the old name-format invalidation. A changed name-field point clears approval before saving; recalibrating to the identical point keeps it.
- Show/activate Activity before starting worker input, removing a startup focus race. Verify the shard menu and allow a short settling period before selecting it. Log a normal first selection separately from a genuine retry.
- Native movement also sends an absolute mouse movement event. Verify the pointer immediately before button-down.
- Pause on a failed pointer move; wait for explicit Resume and recheck the same window/screen. Never replay a partially completed double-click.
- Exclude paused time from local navigation deadlines and waits. Do not instruct users to return to Login while resuming a suspended action.
- Run-scoped Escape shortcut: Pause, then Stop while paused; held keys do not repeat. Always release the registration when the job exits. Buttons remain available if Windows cannot reserve Escape.
- Apply the guarded click path to manual shard selection; cursor diagnostics can pause after a failed move too.

Validation: 230 tests and 19 subtests pass in Linux. Native Windows hotkey/input and live-client verification remain pending. The RE bridge is unchanged.

# 1.8.0-beta.1

Consolidates the supplied 1.7.6 source and 1.8.0-preview.1 interface work.

## Interface

- Six full-width main tabs and task-specific subtabs in a 720 × 720 base window.
- Supplied banner logo, Help artwork and icon; removed the subtitle.
- Help opens first under Help / Status. Support is on the left, art on the right and theme controls below.
- Consistent rounded buttons, clear text hierarchy and lime next-step directions.
- Actionable error prompts, technical details in History and relevant-page navigation while idle.
- Town Crier controls together; visible Clear history; corrected native multiline line endings.

## Reliability

- Combined shard checkpoints include the gift-cycle ID; only the matching cycle may skip or resume a shard.
- Current-cycle creations are excluded from gift collection; earlier tagged creations can be visited in later cycles.
- Legacy creation tags are written only after backing up the original ledger. Pending, created, completed and name-assignment records are preserved.
- Combined creation requires an explicitly loaded/saved local history. Pending characters stay protected across cycles.
- A confirmed-absent attempt retried in a later cycle receives the new cycle tag.
- Invalid slot ranges produce clear correction instructions without allocating excessive ranges.
- Corrected the Windows restart function signature.

## Source distribution

- Replaced superseded patch instructions with one README and developer handoff.
- Removed the duplicate fantasy-name implementation and moved its tests into tests/.
- Removed unused GUI imports, an unused control builder and unused status-building work.
- Build includes icon, bridge, artwork and release documentation beside the EXE; launcher uses the same Python lookup as the builder.
- Razor bridge, bridge protocol, native mouse and profile-isolation implementations are unchanged from the supplied 1.7.6 baseline.

See docs/DEVELOPMENT.md for validation and remaining Windows checks. No completed Windows build or live-client validation is claimed.

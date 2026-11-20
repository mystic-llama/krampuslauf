# Beta development handoff

Version: **1.8.0-beta.4**. Original application: Python 3.12, pythonnet and native Windows Forms. The baseline is the supplied 1.7.6 full-source package; this release carries forward the 1.8.0-preview.1 layout redesign.

## Current structure

- **Game-area coordinates (unreleased).** `client_geometry.py` reads the client area with `GetClientRect` + `ClientToScreen` (the process is DPI-aware, so these are physical pixels). Menus are a fixed 640 × 480 area; `menu_scale()` accepts only uniformly scaled 4:3 sizes and returns `None` otherwise (for example the in-world view). `GameArea.to_screen()` refuses to map clicks when the area is not a menu. `menu_layout.py` holds the built-in points and marker regions in 640 × 480 space; marker PNGs live in `assets/screen_markers/` at 100% scale and are resized per detected scale in `GameWorker._template_for`. Settings never persist `points`; the GUI always loads `menu_layout.default_points()`. Town Crier/gump cleanup was removed from the GUI, engines and bridge protocol; `krampuslauf_bridge.py` still accepts `tidy_gumps` for compatibility but it is never sent.

- Beta.3 validates profile recovery manifests before reads/writes, binds the two registry targets and recovery paths, rejects links/reparse points, bounds reads, and validates backup JSON. The local writable data directory is still not an authentication boundary.
- Setup now displays `assets/logo.png` at 250 × 250 beside two-line checklist controls. The 60 × 60 banner and 350 × 350 Help artwork remain.
- Public release files include MIT LICENSE, expanded .gitignore, CONFIGURATION.md and docs/GITHUB_PUBLISHING.md, RELEASE_NOTES.md and SECURITY_REVIEW.md.

- `escape_hotkey.py`: run-scoped Windows RegisterHotKey/PeekMessage loop on a dedicated thread; MOD_NOREPEAT; unregister on exit. Callback touches events and bridge abort only, never WinForms controls. No keyboard logging or mouse locking.
- `native_mouse.py`: verifies immediately before button-down and reports how many clicks were sent on interruption. A partially sent double-click must never enter the no-click retry path.
- Worker pause time is subtracted only from local navigation deadlines. Bridge/session freshness and commands already issued use real time. An in-flight Razor action can finish before Pause takes effect.
- Typing approval is about the name-field/input method. Naming choices must not invalidate it. Existing reserved/pending names still retain their creation safeguards.

- `ui_layout.py`: all 10 pages, three main tabs, control bindings, type hierarchy, next-step directions and static bounds checks. The main window is 720 × 720 at 96 DPI; Windows scales it as a unit.
- `Krampuslauf.py`: native controls, event handlers, Activity window and artwork lifetime. Main/subtab buttons fill their header width. Existing controls have one owner; navigation shortcuts do not duplicate saved state.
- `ui_guidance.py`: plain-language errors and destinations. Known failures give a specific action; unknown failures point to Status and its local-data-folder action without inventing a cause. This module grants no automation permissions.
- `ui_assets.py`: ordinary asset lookup and native CRLF normalization. The PNGs and ICO are the supplied originals.
- `cycle_state.py`: cycle-scoped handoffs and creation-age tags. Permanent creation and fantasy-name histories remain separate from gift-cycle progress.
- `seeder_engine.py`: backs up legacy creation history before adding cycle tags; records the cycle before a pending creation is submitted; writes handoff checkpoints with cycle IDs.
- `cycler_engine.py`: revisits earlier-cycle creations by identity while excluding current-cycle or unknown-age creations and all pending names.
- `tools/build_layout_preview.py`: offline browser preview from the real layout definitions, with relative asset files and no base64.
- `tools/check_windows_ui.py`: Windows-only render/text/bounds check against temporary app data. No client enumeration or game input.

The bridge script and bridge protocol are byte-for-byte unchanged from the supplied 1.7.6 baseline. Profile isolation retains beta.3 hardening. Beta.4 changes the creation engines to support transfer-slot reservation; native input timing is unchanged from beta.2. Do not reinstall the bridge solely for this beta if that exact version is already installed.

`recovery_rules.creation_limit` applies the configured capacity minus one when `reserve_transfer_slot` is enabled. Standalone reservation reuses `GameWorker.run(creation_only=True)` to check existing rows without waiting for gifts or saving gift completions. A temporary config ignores gift-slot skips and is restored in `finally`. Its handoff is stored as `reserved_seeder_shard`, separate from `combined_shard`; pending/created/completed records and creation-cycle tags remain shared. The limit is checked again inside `seed_one` before any creation input.

## Completed validation

- Python 3.12 syntax compilation for source, tools and tests.
- **286 tests and 19 subtests passed** in Linux. Tests cover the existing bridge/route simulations, calibration, profile restoration, pending recovery, name persistence and shifted rosters.
- New cycle tests exercise exact-byte migration backups, failure before writing, permanent ledger preservation, same/new-cycle handoffs, earlier-cycle gift eligibility, pending protection and a later retry after confirming an attempt absent.
- Added input tests cover no click after pointer drift, partial double-click release, changed-screen retry rejection, Stop while paused, pause-aware time, hotkey release, first-shard selection/retry logging, and persistent typing approval across modes/styles.
- GUI method tests exercise real layout mounting, saved-option round trips, error navigation/redaction, clear-history safeguards and invalid slot input without WinForms or mouse injection.
- All **14 preview pages in both themes (28 renders)** fit within the 720 × 720 design. No measured control/text overflow, missing artwork, clipped navigation or browser script errors remained.
- Supplied art matches its originals. Original source packages remain untouched.

- Beta.3 recovery security tests add 23 cases; normal profile restoration remains covered. Updated Setup was rendered in both preview themes with no measured overflow. Native Windows checks remain outstanding.
- Beta.4 adds 33 tests covering capacity, partial/full/empty rosters, one-slot shards, separate standalone checkpoints, unchanged gift eligibility, pending protection, limit changes, saved account choices and accurate marker-error wording. The updated Seeder page was rendered in both preview themes without measured overflow or browser errors. Artwork, license, ignore rules, native mouse and profile-isolation code match beta.3 byte for byte.

These checks are not evidence of native Windows operation or successful gift delivery. No EXE was built here.

## Windows checks remaining

Beta.4 focus: on a supervised test shard, validate empty, partly filled, six-character and already-full rosters with the correct account capacity. Confirm reservation is saved per local history, existing seventh characters still receive gift processing, and standalone reservation does not mark gifts complete. Check both modes and a resumed creation at the new limit. Re-capture profession markers away from tooltips; click timing has not been changed.

Beta.3 focus: verify native two-line checkboxes and the 250px Setup art at each supported DPI; exercise normal prepare/restore with a private backup of real data. The simulated reparse test is not a real NTFS-junction test.

Beta.2 focus: verify first-shard selection from a newly opened Activity window, deliberately bump the pointer before a click, Resume without changing the game screen, and press/release Escape twice to Pause then Stop. Hold Escape once to confirm it does not auto-repeat into Stop. Verify the key works normally after completion and the explicit unavailable message appears if another app reserves it. Do not use a real creation as the first input-interruption trial.

1. Build with Python 3.12 using `Build_Windows_EXE.bat`; launch the resulting complete distribution folder and verify artwork/icon, theme, tabs and source-independent asset lookup.
2. Run the native UI check in dark/light at 100%, 125% and 150% scaling. Check keyboard navigation, compact Activity Pause/Stop/return behavior and that every relevant error opens the correct page when idle.
3. With backed-up real app data, validate one existing character and one disposable creation. Confirm window/shard identity, warning recovery, bridge world entry, the inn route and actual safe logout.
4. Exercise interruption/recovery and a new gift cycle against the same local history. Current-cycle creations must remain excluded; earlier tagged creations must not be skipped solely because an old combined handoff was complete.

## Persistence rules to preserve

All releases use `%LOCALAPPDATA%\Krampuslauf`. A separate source/EXE folder does not isolate real settings. The UI smoke check changes LOCALAPPDATA before importing the application, then removes its temporary folder on exit.

Never fix a halt by erasing settings, pending/created/completed records, name assignments, used fantasy names or profile-isolation backups. New gift cycles retain old progress; Clear history touches only activity logs. Legacy records get conservative first-cycle tags after backup, and untagged handoffs cannot skip a shard. A failed migration backup must stop the write.

A distinct local history label must be explicitly loaded/saved for each account before creation. Keep the selected game title out of persistent settings and redact it from UI exception details. Logs may still contain character and shard names.

## Known behavior limits

Gift completion is world confirmation + wait + verified logout, not inventory inspection. The built-in layout was measured on one Classic Client at 100% scaling; scaled recognition is simulated in tests and still needs native checks at 125% and 150%. The existing route/coordinate checks do not establish every in-game safe-logout condition. Stop/Pause, pending-creation guards, identity matching and profile-backup protections must remain intact during further UI work.

Reservation uses the existing row-discovery heuristic: repeated unconfirmed entry plus a verified New button can start the handoff. It is not a direct roster-count API. Correct capacity and row/menu calibration remain prerequisites; a misdetected row can give the wrong count. The feature must be validated in the real client before unattended use. One-slot shards have a creation ceiling of zero while reservation is enabled; existing characters are never deleted.

The public README and CHANGELOG replace accumulated patch instructions. This release is a full source package. It does not delete user data or patch a compiled EXE.

## API references

- Windows RegisterHotKey: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-registerhotkey
- UnregisterHotKey: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-unregisterhotkey
- PeekMessage: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-peekmessagew

The hotkey and native-input paths are simulated in the cross-platform suite; actual Windows dispatch, focus and game consumption require the above native checks.

# Krampuslauf — first-time configuration

For **1.8.0-beta.5**, using the official Ultima Online Classic Client and Razor Enhanced.

Follow the steps in order. The bright **NEXT** messages in the application point to the next tab. The usual path is **Setup → Game client → Shards → Automation**.

This is beta software. The source has passed automated tests; native Windows operation and live-game behavior still need testing. Begin with one shard and an existing character before enabling character creation.

## 1. Install and open Krampuslauf

You need a Windows PC, the official Classic Client (`client.exe`), Razor Enhanced, and the .NET Framework runtime used by Windows Forms. This application does not target ClassicUO.

**If the release includes a Windows application ZIP:**

1. Download it from [Mystic Llama / Krampuslauf](https://github.com/mystic-llama/krampuslauf).
2. Extract the entire ZIP into a permanent local folder. Do not run it from inside the ZIP.
3. Keep `Krampuslauf.exe`, `_internal`, `assets`, and `krampuslauf_bridge.py` together. Run `Krampuslauf.exe`.

**If you downloaded the full source ZIP:**

1. Install Python **3.12** for Windows, including its launcher, and extract the source into a permanent local folder.
2. Open that folder in File Explorer. Type `cmd` in the address bar and press Enter.
3. Install dependencies and start the application:

   ```bat
   py -3.12 -m pip install -r requirements.txt
   py -3.12 Krampuslauf.py
   ```

4. For later launches, use `Run_WinForms_GUI.bat`. If Python is not found, set `GM_PYTHON` in that file to your Python 3.12 `python.exe` location. The batch file checks the usual per-user Python 3.12 location first.

The full source package does not contain a compiled EXE. Ordinary EXE users do not need a separate Python installation.

## 2. Set up Razor Enhanced

Open **Setup > Checklist** in Krampuslauf, then complete these Razor and game settings. **Checking every box is required before a run can start.**

1. In **Technical**, select the existing **default** profile. Do not create a separate Krampuslauf profile.
2. In **Scripting**, add the supplied `krampuslauf_bridge.py` from its permanent location. Enable its **AutoStart at Login** option. This script runs inside Razor; do not double-click it to run it with desktop Python.
3. In **Options**, enable **Automatically Open Doors**.
4. In **Technical**, enable **Remember passwords**. Enter credentials only in the normal game/Razor login flow. Krampuslauf does not ask for your game password.
5. Launch the game through Razor.
6. **In Game Options (Paperdoll), turn off tooltips or set Tooltip delay to 5000 ms.**
7. **Check all five boxes**, then click **Save checklist**. Configuring the settings alone does not check these confirmation boxes for you. **Show bridge script** opens Explorer with `krampuslauf_bridge.py` selected. Add that file in Razor; do not run it with desktop Python.

**NEXT: CLOSE RAZOR AND CLASSIC CLIENT → SETUP > PROFILES.**

## 3. Prepare temporary profile isolation

Razor can switch profiles when it recognizes a character. Temporary isolation keeps the default profile available throughout a run.

1. Close Razor Enhanced and Classic Client. Leave Krampuslauf open.
2. Go to **Setup > Profiles**.
3. Paste the Razor data folder that contains **both** `Profiles` and `Backup`, then click **Find / validate folder**. Copy that path from File Explorer. Profiles has no Browse button, because a folder window opened from Krampuslauf can appear behind this window. If several installations are found, paste the one your Razor actually uses.
4. Click **Prepare Krampuslauf** and read the confirmation.
5. Wait for the status to report that character links are isolated.
6. Start Razor with the **default** profile selected, then launch the game through Razor.

Only the two `RazorEnhanced.NewProfiles` files are changed. Original copies are retained for restoration; profile names, named profile folders and saved Razor passwords are not intentionally changed. Use real local folders; linked folders and network locations are not supported for profile recovery.

If preparation or recovery reports a problem, keep the backups. Do not delete the recovery record or repeatedly prepare again to clear the error.

**NEXT: GAME CLIENT.**

## 4. Select the game window

No calibration is needed. The Classic Client draws its login, shard, character and creation menus in a fixed 640 × 480 game area. Krampuslauf ships the screen markers and click positions for those menus and measures them from the game area itself, so window borders, the title bar and the Windows theme do not matter. Windows display scaling (for example 125%, which shows the menus at 800 × 600) is detected automatically.

1. Open **Game client**.
2. Click **Refresh windows**, then select the official Classic Client. Select it again whenever Krampuslauf is relaunched.
3. Put the game on its login screen, shard list or a character list and click **Check current screen**. It reports the game-area size, the detected scaling and the recognized menu. It sends no mouse or keyboard input.
4. If a menu is reported as **unknown**, make sure nothing overlaps the game window and the pointer is not hovering over a button, then check again. In Game Options (Paperdoll), set Tooltip delay to 5000 ms, or turn tooltips off, so a tooltip cannot cover a menu marker.
5. If a click ever misses its target, open **Setup > Game Client > Click points**, choose the point, show the matching game screen, click **Record selected** and hover over the control within 4 seconds. **Reset to built-in** undoes a recorded point.

Use one Classic Client window during setup and testing. Recognized warning dialogs (account still online, Origin communication error) are dismissed with Enter; unknown dialogs stop the run.

**NEXT: SHARDS → SCAN / RESUME.**

## 5. Discover and verify the shard order

1. Put Classic Client on the shard list and scroll all the way to the top.
2. Open **Shards** in Krampuslauf. Confirm the row spacing matches your client. Leave the other navigation settings at their defaults for the first test.
3. Click **Scan / resume** and follow its prompt. An interrupted scan can resume from saved progress.
4. Let the scan finish and check that it reports **VERIFIED**.
5. Compare the displayed order with the game. The text list uses one shard per line. If you edit it, click **Save shard order**, then check **I verified the order in-game** after comparing it.
6. Click **Save navigation options** if you changed navigation settings.
7. Optional but recommended: put Classic Client on the shard list and click **Learn shard names**. It scrolls the list once with the mouse wheel and saves a small picture of each shard name. Later runs scroll with the wheel and click a row only after reading its name, which is much faster than clicking the scroll arrows. Pictures are also learned automatically from title-verified shard clicks.

Rescan after changing Windows time zone or shard-row geometry. A manual list does not replace the verified scan used by the default configuration.

## 6. Check the bridge

1. Manually log an existing character into the world. Confirm Razor is using **default** and the bridge script is running.
2. Go to **Help / Status > Diagnostics** and click **RE bridge**.
3. Confirm the successful result. If it fails, check the script's AutoStart setting, the active profile, and that only one Classic Client is open.
4. For a logout test, put the character in a safe logout location and use **RE logout**. This disconnects the character.
5. Return the game to its normal login or shard menu before starting a run.

Green diagnostic labels record previous successful tests. They are not a continuous connection indicator.

**NEXT: AUTOMATION > GIFT CYCLER.**

## 7. Run a small Gift Cycler test

1. Open **Automation > Gift Cycler**.
2. Include only one test shard. Click **No shards**, then check that shard. **All shards** selects the full list again.
3. Leave **Create characters in available slots using Character Seeder** unchecked for this first test.
4. If necessary, enter slot skips such as `Atlantic: 1-5` or `Origin: 1,3,5`, then click **Save slot skips**. Empty slots are not recorded as received gifts.
5. Leave the timing defaults for the first test, then click **Save run options**.
6. Use **New cycle / account** when switching accounts or starting a new gift event. Keep the same cycle when resuming an interrupted run on the same account.
7. Click **Start Gift Cycler**. Watch the first login, wait and logout. Verify the actual gift in game before expanding the run.

The completion record means that world entry, the configured wait and logout were verified. Krampuslauf does not inspect inventory to prove a gift arrived.

## 8. Optional: enable Character Seeder

Skip this section if you only want to cycle existing characters. Creation-screen markers and click positions are built in, like the other menus.

1. Open **Automation > Character Seeder** and choose **Main Account** or **Account 2–15**, arranged in five rows of three. Account Nickname is optional, capped at 16 characters, and updates the radio-button caption; it never changes the stored history identity. Existing nicknames, settings and progress are preserved when upgrading.
2. Open **Automation > Appearance**. Choose **Shard + Slot** or **Fantasy (default)**. For Shard + Slot, use a prefix of 1–10 letters. For fantasy names, choose Single, First + Last, or Mixed. Use **Preview names** to review examples.
3. Optional: open **Automation > Appearance** to choose sex, race and hair, facial hair or horn styles, and skin colours on the same page (see below). Leave **Customize appearance** off to keep the game's default male human.
4. Name typing needs no test. Launch the game through Razor.
5. Set **Account slots per normal shard** to this account's actual capacity: **5, 6 or 7**. To leave room for a transfer, enable **Keep one slot empty on every shard**. On a seven-slot account this limits creation to **six total characters**, including characters already there. No per-shard skip entries are needed. The option starts off for existing and new installations.
6. Settings and history save to the selected account automatically. The last-used account is restored at launch; start confirmations state the selected nickname.
7. Use **Start Character Seeder** for a creation run. Alternatively, enable the creation option in **Automation > Gift Cycler** for combined operation. The loaded history is required in either case. Both modes honor the same reservation.

**Appearance.** Tick **Customize appearance** and choose a mode:

- **Fixed:** tick at most one option per group. Every new character uses that selection until you stop the run and change it.
- **Random:** each new character gets a random pick from the ticked options.

Unselected sex, race and style groups use Male, Human and the default style. An unselected skin shade is randomized for the chosen race. Use **Style list** to switch between the hair, facial hair and horn lists. Options that do not apply are skipped automatically: females and elves have no facial list, and only male gargoyles have facial horns. Krampuslauf selects race, then sex, then styles and skin tone, before typing the name. Click **Save appearance**.

**Skin tone.** Select a race to display its palette beside the vertical race choices. Click a shade to select it; click again or Clear current shade for a random shade. Selections are remembered separately per race (64 human, 32 elf, 28 gargoyle). All three palettes ship with measured first/last cell centres, so no first-run skin calibration is required. Krampuslauf calculates every cell from those built-in centres and adjusts for display scaling. If a click misses, override the Skin Tone swatch or the top-left/bottom-right cell centres under **Setup > Game Client > Click points**; Reset to built-in restores the measured defaults.

**Hair and horn colour.** Select a race, then choose Hair colour or Facial hair colour from the palette dropdown. Humans have 48 choices, elves have 54 hair colours, and gargoyles have 18 horn and 18 facial-horn colours. Choices are stored separately for each race and for hair/horns versus facial hair/horns. Fixed mode uses one selection; Random mode chooses among the checked colours. No colour selected keeps the game default. Elves have no facial hair, and female characters have no facial hair/horns. Colour is also skipped for an explicitly bald or beardless style. Click **Save appearance** after editing.

**Before inn route (sec).** Under **Automation > Character Seeder**, choose a pause from 0 to 120 seconds (default 5). It starts after the new character is verified in the world and before the inn-route request. The value is saved separately per account and applies to both standalone Seeder and Gift Cycler creation. Stop and Pause remain available. The bridge still performs its existing spawn/readiness checks before moving.


The appearance-screen click positions (race and sex buttons, dropdown arrows and list rows) are built in but were estimated from a screenshot. Watch the first creation; if a click misses, record that point under **Setup > Game Client > Click points**.

Seeder creates only when the New option is verified. Existing characters are not replaced. The route goes through Moonglow to `(4403,1170)` and `(4403,1164)`; verify safe logout in the real client. Newly created characters are excluded from their creation cycle's gift run.

**Transfer-slot behavior:** reservation limits are 4/5/6 total characters for 5/6/7-slot accounts. The app does not detect the account's maximum capacity automatically; choose the correct value. Existing character rows and the New button must be recognized correctly. Test one partly populated shard first. In standalone reservation mode, existing characters may be logged in and out to check occupancy; this does not update gift-completion records, although the game may still award a login gift. Gift Cycler continues to include an occupied seventh slot unless you explicitly skip it. Already-full shards stay full: Krampuslauf never deletes a character to create space. Unsupported shards are excluded from both creation and gift runs, regardless of reservation settings.

After a route failure, return the game to the login or shard menu and restart the Seeder. Previously confirmed characters are retained, their interrupted routes are not replayed, and finished-shard checkpoints remain. No reset button is needed. If a creation was submitted but never confirmed, inspect the character list and saved activity log before retrying.

## 9. Pause, resume and stop

- Click **Pause**, or press **Escape** once during a job. Click **Resume** to continue.
- Press Escape a second time while paused, or click **Stop**, to end the job. Stop does not necessarily log out a character already in the world.
- A mouse-targeting failure pauses before an unsent click. Leave the game on the same screen, in the same window position and size, then use **Resume**. If validation fails, the click is refused. A partially sent double-click is not blindly replayed.
- The pointer is not locked. Avoid using the computer for other tasks during automation. PyAutoGUI's corner fail-safe can still stop the job.
- A Razor command already underway may finish before a pause takes effect. If Escape is unavailable because another application reserved it, use the Activity window buttons.

After a route failure, return the game to the login or shard menu and restart the Seeder. Previously confirmed characters are retained, their interrupted routes are not replayed, and finished-shard checkpoints remain. No reset button is needed. If a creation was submitted but never confirmed, inspect the character list and saved activity log before retrying.

## 10. Restore normal profiles when finished

1. Stop automation and check the game's current state.
2. Close Razor Enhanced and Classic Client.
3. Open **Setup > Profiles** and click **Restore original profiles**.
4. Read the confirmation, especially if Razor changed temporary profile links. Restoration puts back the saved originals and may discard links made during isolation.
5. Restart Razor and verify your usual profile links.

If restoration is refused, keep all recovery files and ask for help with the relevant saved activity-log message.

## Saved data, updates and support

Settings, run progress and recovery backups live in `%LOCALAPPDATA%\Krampuslauf`. **Every application version uses that same folder.** The first launch moves an older data folder into it when the new folder is not already there. Close Krampuslauf and back up that folder before updating; keep the backup private. Installing the new source in a different directory does not create fresh account history. **Help / Status > Status** names this folder so it is not mistaken for a missing install.

**Help / Status > Status > Open local data folder** opens the folder containing `activity_history.log` and its rotated copies. The Activity window shows the current run; there is no separate History tab. Gift cycles, Seeder records, reserved names and profile backups remain saved. Do not erase saved state to work around a failed run.

Use **Help / Status > Help** for the GitHub link, donations and theme setting. PayPal donations open in the browser. In-game gold can be sent by reaching Mystic on Discord at **@mystikllama**. Save appearance changes and restart. For a problem report, include the app version, Windows display scaling, the tab/action, what happened, and a short relevant saved activity-log excerpt. Remove account or character details you do not want public. Never attach the entire app-data folder, Razor profile folder or password file.

Project and support: [github.com/mystic-llama/krampuslauf](https://github.com/mystic-llama/krampuslauf).

Naming, race, sex, styles, skin and profession are together under **Automation > Appearance**. Profession offers Samurai, Ninja, Paladin, Necromancer, Warrior, Mage, Blacksmith, or Randomize (one of the seven per character). Blacksmith remains the initial profession.

Completed standalone shards are recorded in `seeder_progress.json` under the selected account with `standalone_seed` checkpoints. A restart skips finished shards and retains the unfinished shard. Per-account settings are in `account_profiles.json`; radio identities and nicknames are in `account_catalog.json`. Existing hashed history IDs are preserved during migration.


**Supported shards.** Siege Perilous and Mugen are removed from run choices, diagnostic targets, and the editable supported-shard list. Existing maps retain all physical client rows internally, so excluding those destinations does not shift later shard clicks. Full scans still identify physical rows for navigation, but never log a character into those unsupported worlds. When manually changing the supported order, use Scan / resume to establish fresh physical row positions before relying on arrow navigation.

**Closing with profiles isolated.** Choose Return to Profiles to restore them; dismissing the reminder also keeps the app open. Close anyway explicitly leaves restoration for later. Verified local backups remain available.

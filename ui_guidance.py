"""Plain-language UI recovery advice. This module never authorizes game actions."""
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class Guidance:
    title: str
    message: str
    page: str = 'status'


class ActionNeeded(RuntimeError):
    def __init__(self, title, message, page):
        self.guidance = Guidance(title, message, page)
        super().__init__(message)


def advise(title, message, page):
    return Guidance(title, message, page)


def explain_error(error):
    """Translate known conditions; never guess a cause for an unknown failure."""
    if isinstance(error, Guidance):
        return error
    if isinstance(error, ActionNeeded):
        return error.guidance
    raw = str(error)
    text = raw.casefold()
    if 'profile recovery' in text or 'linked profile or recovery' in text:
        return advise('Profile recovery needs attention',
                      'Keep Razor Enhanced and Classic Client closed. Do not delete recovery files or prepare again.\n\n'
                      'Open Setup > Profiles and check the saved folder. Read the saved activity log for details and get help '
                      'before restoring; the recovery record could not be safely verified.', 'profiles')
    if 'game screen changed before mouse' in text:
        return advise('Check the game screen',
                      'Krampuslauf could not verify the same screen before clicking. No click was sent. '
                      'This does not mean you moved the mouse.\n\n'
                      'A tooltip or overlapping window can hide part of a screen marker. Move the pointer '
                      'off buttons, keep the client unobstructed, then open Game client and click '
                      'Check current screen.', 'client')
    if any(t in text for t in ('game screen or window changed while paused',
                              'cannot verify the game screen after mouse pause')):
        return advise('Check the screen before continuing',
                      'Krampuslauf could not verify the same screen and window after the pause, so the click was not repeated. '
                      'Check the game, then restart from a recognized menu. '
                      'If character creation was underway, check the character list and saved activity log first.', 'status')
    if 'account slot capacity' in text or 'transfer slot reserved' in text:
        return advise('Check the creation limit',
                      'Open Automation > Character Seeder. Choose this account’s actual slot capacity '
                      '(5, 6 or 7), set Keep one slot empty on every shard, for the selected account. Settings save when you start, switch accounts, or close the app. '
                      'Do not use a larger capacity than this account supports.', 'seeder')
    if 'mouse target' in text or 'sendinput' in text:
        return advise('Check mouse access to the game',
                      'Restore the Classic Client window and keep it fully on screen. '
                      'Launch the game through Razor. '
                      'Use Help / Status > Diagnostics to compare Game cursor and Desktop cursor.', 'diagnostics')
    if 'no unfinished' in text or 'no pending' in text:
        return advise('No recovery record was found',
                      'Check the selected account under Automation > Character Seeder. '
                      'Select the account used for this run. '
                      'If this is the correct history, there is nothing saved to recover.', 'seeder')
    # Protect unfinished characters before suggesting any retry or new setup.
    if any(term in text for term in ('pending', 'unresolved creation', 'creation outcome unknown',
                                     'unfinished routing', 'inn-route/logout recovery', 'creation submitted')):
        return advise('Check the unfinished character',
                      'Dismiss any message in Classic Client and return to the login or shard menu. '
                      'Restart the Seeder. It will check the shard’s live character or creation menu '
                      'and continue with a new name if there is room for another character.', 'seeder')
    if 'backup' in text and any(t in text for t in ('missing', 'checksum', 'verification failed', 'unreadable')):
        return advise('Profile backup needs attention',
                      'Keep Razor Enhanced and Classic Client closed. Do not prepare profiles again.\n\n'
                      'Open Help / Status > Status > Open local data folder for the saved activity log. Get help before changing any recovery files.', 'status')
    if 'recovery record is unreadable' in text or 'restoration failed' in text:
        return advise('Profile recovery needs attention',
                      'Keep Razor and Classic Client closed. Do not prepare profiles again or delete backups.\n\n'
                      'Read the saved activity log in Help / Status > Status > Open local data folder before attempting another restoration.', 'profiles')
    if any(t in text for t in ('fingerprint mismatch', 'wrong shard:', 'shard mismatch', 'does not match any unfinished')):
        return advise('The character or shard does not match',
                      'Stop and check the selected account, shard and character in the game.\n\n'
                      'For an unfinished character, choose its saved history under Automation > Character Seeder, '
                      'then return to the login or shard menu before restarting.', 'seeder')
    if 'close razor enhanced and classic client' in text or 'close re and classic client' in text:
        return advise('Close the game and Razor first',
                      'Close both Razor Enhanced and Classic Client.\n\nReturn to Setup > Profiles and try the action again.', 'profiles')
    if 'containing both profiles and backup' in text or 'razor data folder' in text:
        return advise('Choose the Razor data folder',
                      'Open Setup > Profiles. Paste the folder that contains both Profiles and Backup, '
                      'then click Find / validate folder.', 'profiles')
    if 'default folder is missing' in text or 'exactly one default profile' in text:
        return advise('Set up Razor’s default profile',
                      'In Razor Enhanced, select or configure the default profile. Close Razor and Classic Client, '
                      'then return to Setup > Profiles.', 'profiles')
    if 'newprofiles is missing' in text:
        return advise('Let Razor create its profile files',
                      'Launch Razor Enhanced normally once. Close it and Classic Client, '
                      'then return to Setup > Profiles and try again.', 'profiles')
    if any(t in text for t in ('temporary profile isolation', 'earlier profile isolation', 'temporary registr',
                              'registry changed', 'profile registry', 'registry contains', 'symlink registry',
                              'linked profile directories', 'parse razorenhanced.newprofiles', 'profile records')):
        return advise('Review profile preparation',
                      'Open Setup > Profiles and click Refresh status. Close Razor and Classic Client before changes.\n\n'
                      'If a previous preparation is active, restore original profiles before preparing again. '
                      'Do not delete recovery backups.', 'profiles')
    if 'setup checklist' in text or 'default-profile setup' in text:
        return advise('Finish the setup checklist',
                      'Open Setup > Checklist. Complete the Razor and game settings, check EVERY box, '
                      'then click Save checklist. The checkmarks are required before a run can start.', 'setup')
    if any(t in text for t in ('exactly one', 'one game client per', 'close extra official')) and ('client' in text or 'window' in text):
        return advise('Keep one Classic Client open',
                      'Close extra Classic Client windows. Open Game client, '
                      'click Refresh windows, and select the remaining client.', 'client')
    if any(t in text for t in ('select the official classic', 'select exactly one classic', 'window not found',
                              'window closed', 'no official client', 'no classic client')):
        return advise('Select the game window',
                      'Start Classic Client through Razor Enhanced. Open Game client, '
                      'click Refresh windows, and select your game.', 'client')
    if 'not a 640x480 menu screen' in text or 'outside the 640x480 game area' in text:
        return advise('Return the client to a game menu',
                      'Krampuslauf clicks only on the 640×480 login, shard, character and creation menus. '
                      'Return Classic Client to one of those menus, keep Windows display scaling unchanged, '
                      'then use Setup > Game Client > Check current screen.', 'client')
    if 'open the shard list before scanning' in text:
        return advise('Check the shard list',
                      'Keep Classic Client fully visible, open the shard list, and scroll to the top. '
                      'Use Setup > Game Client > Check current screen. When it shows servers, '
                      'retry Setup > Shards > Scan / resume.', 'client')
    if any(t in text for t in ('row geometry', 'row/spacing', 'shard row spacing')):
        return advise('Check the shard row spacing',
                      'Open Shards and correct the row spacing. Return the game’s shard list '
                      'to the top, then click Scan / resume shards.', 'shards')
    if 'record click point' in text or 'click points' in text:
        return advise('Record the missing click points',
                      'Open Setup > Game Client > Click points. Choose each point named in the activity log, open the game '
                      'screen that shows it (for skin corners, open that race’s palette), click Record '
                      'selected and hover over it within 4 seconds.', 'client')
    if any(t in text for t in ('built-in', 'screen_markers', 'reinstall the')):
        return advise('Reinstall the complete application',
                      'A built-in screen marker or menu position is missing. Extract the complete Krampuslauf '
                      'package again, keeping the assets folder beside the application.', 'client')
    if 'profession' in text:
        return advise('Choose a profession', 'Open Automation > Appearance. Choose a profession or Randomize, then Save appearance.', 'looks')
    if any(t in text for t in ('appearance', 'skin tone')):
        return advise('Check the appearance choices',
                      'Open Automation > Appearance. In Fixed mode, tick at most one option in each group '
                      'and one skin tone per race; or switch to Random. Then click Save appearance.', 'looks')
    if any(t in text for t in ('local account nickname', 'non-secret local', 'load seeder history', 'save seeder history', 'creation-history records')):
        return advise('Choose this account’s local history',
                      'Open Automation > Character Seeder. Choose one of the 15 accounts. '
                      'The selected account loads its saved history automatically; the nickname is optional.', 'seeder')
    if 'name prefix' in text or 'prefix must contain' in text:
        return advise('Check the name prefix',
                      'Open Automation > Appearance. For Shard + Slot names, enter 1–10 letters '
                      'without spaces or digits.', 'looks')
    if any(t in text for t in ('naming mode', 'fantasy-name style', 'single, full, or mixed')):
        return advise('Check the naming options',
                      'Open Automation > Appearance. Choose Shard + Slot or Fantasy. '
                      'For Fantasy names, choose Single Name, First + Last, or Mixed.', 'looks')
    if any(t in text for t in ('slot-skip', 'slot rule', 'slot skips', 'skip_slots')):
        return advise('Correct the slot-skip entry',
                      'Open Automation > Gift Cycler. Use an exact shard name and slots 1–7, '
                      'for example Atlantic: 1-5 or Origin: 1,3,5. Leave it blank to skip no slots, '
                      'then click Save slot skips.', 'gift')
    if 'every shard is excluded' in text or 'no included shards' in text:
        return advise('Include at least one shard',
                      'Open Automation > Gift Cycler. Check at least one shard in the selected '
                      'group, or pick a different shard group.', 'gift')
    if 'choose a gift cycle' in text:
        return advise('Start a gift cycle',
                      'Open Automation > Gift Cycler and click New cycle / new account. '
                      'Use one cycle per account and event.', 'gift')
    if any(t in text for t in ('shard order', 'saved shard map', 'time zone', 'row geometry',
                              'duplicate shard', 'ordered list', 'at least one shard', 'scroll reset', 'row/spacing')):
        return advise('Verify the shard list',
                      'Open Shards. Check the row spacing, put the game’s shard list at the very top, '
                      'then click Scan / resume shards. After a time-zone change, start a fresh scan.', 'shards')
    if any(t in text for t in ('post-logout delay', 'online cooldown')):
        return advise('Check the run timing',
                      'Open Automation > Gift Cycler. Between logins must be 3–60 seconds; '
                      'Online conflict wait must be 300–900 seconds. Save run options.', 'gift')
    if 'already logged in' in text:
        return advise('Return to a game menu first',
                      'Log out to a recognized game menu before starting a normal run. '
                      'Return to the login or shard menu before restarting the Seeder; confirmed characters are kept.', 'gift')
    if 'logout' in text and any(t in text for t in ('not verified', 'did not acknowledge', 'will not logout')):
        return advise('Logout was not confirmed',
                      'Check whether the character is still in the game. Move to a safe logout location '
                      'and log out manually if needed. Verify the result before starting again.', 'status')
    if any(t in text for t in ('bridge', 'autostart', 'heartbeat')):
        return advise('Check the Razor connection',
                      'In Razor’s default profile, make sure krampuslauf_bridge.py is running and AutoStart at Login is enabled. '
                      'Log into a character to test it under Help / Status > Diagnostics > RE bridge. '
                      'Log out again before starting a normal run.', 'diagnostics')
    if any(t in text for t in ('unrecognized screen', 'not recognized', 'unknown menu', 'screen changed', 'no enter sent')):
        return advise('Check the game screen',
                      'Look at Classic Client and close any unexpected dialog manually. '
                      'Return to a known menu, then use Setup > Game Client > Check current screen.', 'client')
    if 'stop ' in text and any(t in text for t in ('first', 'before', 'active automation', 'current run')):
        return advise('Stop the current operation first',
                      'Click Stop in the Activity window and wait for it to finish. Then try this action again.', 'status')
    if 'permission denied' in text or isinstance(error, PermissionError):
        return advise('A file could not be updated',
                      'Close other copies of Krampuslauf and any program using its data files. '
                      'Use Help / Status > Status > Open local data folder and check that it is writable. The saved activity log contains the file details.', 'status')
    return advise('The action could not finish',
                  'Check the game’s current screen before trying again. For details, use Help / Status > Status > '
                  'Open local data folder and read activity_history.log. Share the relevant error entry when reporting a problem.', 'status')

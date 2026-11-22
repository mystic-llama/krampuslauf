"""Shared, display-independent layout for the native UI and its design preview.

Coordinates are logical pixels at 96 DPI. WinForms scales the complete form.
Every settings page fits 676 x 602; only user data lists/logs may scroll.
Actions name existing MainWindow handlers, never automation implementations.
"""
from account_profiles import SLOTS, NICKNAME_LIMIT
from appearance import COLOR_ASSETS
from shard_policy import SHARD_GROUP_OPTIONS

VERSION = '1.8.0-beta.6'
PROJECT_URL = 'https://github.com/mystic-llama/krampuslauf'
PAGE_WIDTH, PAGE_HEIGHT = 676, 602
HEADER_HEIGHT = 144
DONATION_URL = 'https://www.paypal.com/donate/?hosted_button_id=T6R4TNGR4UUL6'
BUTTON_HEIGHT = 36
FONT_PT = {'heading': 13, 'body': 10.5, 'muted': 10,
           'note': 9.5, 'warning': 9.5, 'next': 10, 'button': 10, 'mono': 10}

# A task has one home. Related actions can link to it without duplicating state.
NAVIGATION = (
    ('Setup', (('1. Checklist', 'setup'), ('2. Profiles', 'profiles'),
               ('3. Game Client', 'client'), ('4. Shards', 'shards'))),
    ('Automation', (('Gift Cycler', 'gift'), ('Character Seeder', 'seeder'), ('Appearance', 'looks'))),
    ('Help / Status', (('Help', 'appearance'), ('Status', 'status'),
                      ('Diagnostics', 'diagnostics'))),
)


def item(kind, text, x, y, w, h, **options):
    return dict(kind=kind, text=text, x=x, y=y, w=w, h=h, **options)


def text(caption, y, x=16, w=644, h=24, role='body', ref=None):
    return item('text', caption, x, y, w, h, role=role, ref=ref)


def heading(caption, y=14, x=16, w=644):
    return text(caption, y, x, w, 28, 'heading')


def button(caption, action, x, y, w=204, ref=None, tone=None):
    return item('button', caption, x, y, w, BUTTON_HEIGHT,
                action=action, ref=ref, tone=tone)


def field(ref, x, y, w, config=None, default='', kind='entry', h=28, **options):
    return item(kind, '', x, y, w, h, ref=ref, config=config,
                default=default, **options)


def check(caption, ref, config, x, y, w=644, default=False, h=28):
    return item('check', caption, x, y, w, h, ref=ref, config=config, default=default)


def rule(y):
    return item('rule', '', 16, y, 644, 1)


def number(caption, ref, config, x, y, low, high, default, w=204):
    return [text(caption, y, x, w),
            field(ref, x, y+28, w, config, default, 'number', low=low, high=high)]


LAYOUTS = {
    'setup': [
        heading('Connect Razor Enhanced', w=320),
        check('1: In Game Options (Paperdoll)\nTurn off tooltips, or set delay to 5000 ms', 'setup_checks.tooltip_delay', None, 16, 44, 320, h=48),
        check('2: Razor Technical tab\nLoad the default profile', 'setup_checks.default_profile', None, 16, 98, 320, h=48),
        check('3: Razor Scripting tab\nadd krampuslauf_bridge.py. AutoStart at Login', 'setup_checks.script', None, 16, 152, 320, h=48),
        button('Show bridge script', 'show_bridge_script', 16, 206, 320),
        check('4: Razor Options\nTurn on Auto-open doors', 'setup_checks.doors', None, 16, 252, 320, h=44),
        check('5: Razor Technical tab\nTurn on Remember passwords', 'setup_checks.passwords', None, 16, 302, 320, h=44),
        item('image', 'Krampuslauf', 352, 8, 308, 250, asset='logo.png', ref='setup_art'),
        heading('Setup progress', 268, 352, 308),
        text('', 300, 352, 308, 160, role='muted', ref='setup_progress'),
        button('Go: Profiles', 'page:profiles', 16, 424, 100),
        button('Go: Game', 'page:client', 120, 424, 100),
        button('Go: Shards', 'page:shards', 224, 424, 100),
        rule(478),
        button('Save checklist', 'save_setup_checklist', 16, 492, 320, tone='accent'),
        button('Prepare profiles \u2192', 'page:profiles', 348, 492, 312),
    ],
    'profiles': [
        heading('Temporary profile isolation'),
        text('This keeps Razor on the default profile for the whole run.', 48, role='muted'),
        text('Close Razor Enhanced and Classic Client before preparing or restoring.', 82, h=40, role='warning'),
        text('Paste the folder path from Explorer. It must contain both Profiles and Backup.\n'
             'There is no Browse button, because that window can open behind Krampuslauf.',
             126, h=38),
        field('re_root_field', 16, 170, 424, 'razor_data_root'),
        button('Find / validate folder', 'choose_re_root', 456, 166),
        button('Prepare Krampuslauf', 'prepare_profile_mode', 16, 226, tone='accent'),
        button('Restore original profiles', 'restore_profile_mode', 236, 226),
        button('Refresh status', 'check_isolation_status', 456, 226),
        text('', 284, h=68, role='muted', ref='isolation_status_label'),
        rule(370),
        heading('What changes', 386),
        text('Only RazorEnhanced.NewProfiles in Profiles and Backup is updated.\n'
             'Verified originals are retained for restoration.', 422, h=40, role='muted'),
        button('Next: Game Client', 'page:client', 456, 470),
    ],
    'client': [
        heading('Find the Classic Client'),
        text('Step 3 of 4: select the game window, then check its current screen.', 48, role='muted'),
        field('game_pick', 16, 82, 424, kind='choice'),
        button('Refresh windows', 'load_windows', 456, 78),
        button('Check current screen', 'verify_screen', 16, 132, tone='accent'),
        text('', 180, h=64, role='muted', ref='screen_status'),
        rule(254),
        heading('Click points', 268),
        text('Optional. Built-in 640 x 480 positions. Record a point only after a click misses.',
             304, role='muted'),
        field('point_pick', 16, 338, 644, kind='choice', source='click_points'),
        button('Record selected', 'record_point', 16, 382),
        button('Reset to built-in', 'reset_point', 236, 382),
        text('', 426, w=424, h=72, role='muted', ref='point_status'),
        button('Next: Shards', 'page:shards', 456, 464),
    ],
    'shards': [
        heading('Shard order & discovery'),
        text('One shard per line, matching the current order in Classic Client.', 48, role='muted'),
        field('shard_text', 16, 88, 316, kind='textarea', h=268, source='shards'),
        button('Save shard order', 'save_shards', 344, 88, 316),
        check('I verified the order in-game', 'sort_confirm', 'verified_order', 344, 140, 316),
        heading('Verified discovery', 190, 344, 316),
        text('', 226, 344, 316, 42, 'muted', 'map_status_label'),
        button('Scan / resume', 'scan_shards', 344, 282, 152, tone='accent'),
        button('Learn shard names', 'learn_shard_names', 508, 282, 152),
        text('Scan: identify shards from the title.\nLearn: read names straight off the list.', 330, 344, 316, 40, 'muted'),
        *number('Shard row spacing (px)', 'row_spacing', 'row_spacing', 16, 382, 5, 150, 25),
        *number('Max UP reset clicks', 'scroll_reset_clicks', 'scroll_reset_clicks', 236, 382, 0, 40, 18),
        text('Characters 2–7 use the last-shard button.\nThe list is for a shard\'s first entry.',
             378, 456, 204, 80, 'muted'),
        button('Next: Automation \u2192', 'page:gift', 16, 464),
        button('Save navigation options', 'save_settings_click', 456, 464, tone='accent'),
    ],
    'gift': [
        heading('Gift Cycler', w=316),
        button('Select account', 'page:seeder', 344, 12, 316),
        text('Shard group', 52, w=112),
        field('gift_shard_group', 140, 48, 192, 'shard_group', 'all', 'choice',
              items=SHARD_GROUP_OPTIONS),
        text('Run checked shards in this group', 88, w=316),
        field('shard_checks', 16, 116, 316, kind='checklist', h=110),
        button('Check all', 'select_all_shards', 16, 240, 152),
        button('Uncheck all', 'select_no_shards', 180, 240, 152),
        text('Skip character slots (optional)\nExample: Atlantic: 1-5', 52, 344, 316, 44),
        field('slots_field', 344, 104, 316, kind='textarea', h=100, source='slot_rules'),
        button('Save slot skips', 'save_slot_rules', 344, 220, 316),
        check('Create characters in available slots using Character Seeder', 'create_missing_checkbox', 'create_missing', 16, 280),
        text('Uses the selected account under Character Seeder.\n'
             'New characters are excluded from this event’s gift run.', 310, h=38, role='note'),
        *number('Gift wait (sec)', 'gift_wait', 'gift_wait', 16, 358, 3, 120, 12),
        *number('Between logins (sec)', 'post_logout', 'post_logout_seconds', 236, 358, 3, 60, 7),
        *number('Online conflict wait (sec)', 'online_cooldown', 'online_cooldown_seconds', 456, 358, 300, 900, 305),
        text('New cycle when starting a new gift event.', 428, w=424, role='muted'),
        text('', 428, 456, 204, 24, 'muted', 'cycle_status_label'),
        button('Start Gift Cycler', 'start_run', 16, 464, ref='start_btn', tone='start'),
        button('New gift cycle', 'new_gift_cycle', 236, 464),
        button('Save run options', 'save_settings_click', 456, 464),
    ],
    'seeder': [
        heading('Character Seeder', w=316),
        button('Names and appearance', 'page:looks', 344, 8, 316),
        text('Account and shard group apply to both modes.', 48, w=316, role='note'),
        text('Shard group', 52, 344, 112),
        field('seed_shard_group', 456, 48, 204, 'shard_group', 'all', 'choice',
              items=SHARD_GROUP_OPTIONS),
        text('Account', 76, w=204),
        *(field('account_radios.' + slot, 16 + (index % 3) * 220,
                104 + (index // 3) * 28, 204, kind='radio', h=24, default=index == 0)
          for index, slot in enumerate(SLOTS)),
        text('Account Nickname (if desired)', 252),
        field('account_field', 16, 282, 424, default='', max_length=NICKNAME_LIMIT),
        button('Save nickname', 'save_account_profile', 456, 278),
        text('', 322, h=36, role='muted', ref='account_history_summary'),
        text('Account slots per shard', 368, w=204),
        field('seed_capacity_pick', 16, 400, 204, 'account_cap', 7, 'choice',
              items=(('5 slots', 5), ('6 slots', 6), ('7 slots', 7))),
        check('Keep one slot empty\non every shard', 'reserve_slot_checkbox', 'reserve_transfer_slot', 236, 394, 204, h=40),
        *number('Before inn route (sec)', 'seed_route_delay', 'seed_route_delay_seconds', 456, 368, 0, 120, 5),
        text('Set the actual capacity. Applies to both creation modes; existing characters stay.',
             440, h=18, role='note'),
        button('Start Character Seeder', 'start_seeder_run', 16, 464, 644, 'seed_start_btn', 'start'),
    ],
    'looks': [
        heading('Names and appearance'),
        text('Naming mode', 48, w=204),
        text('Fantasy style', 48, 236, 204),
        text('Profession', 48, 456, 204),
        field('seed_mode_pick', 16, 78, 204, 'seed_naming_mode', 'fantasy', 'choice',
              items=(('Shard + Slot', 'convention'), ('Fantasy (default)', 'fantasy'))),
        field('seed_style_pick', 236, 78, 204, 'seed_fantasy_style', 'mixed', 'choice',
              items=(('Single Name', 'single'), ('First + Last', 'full'), ('Mixed', 'mixed'))),
        field('seed_profession_pick', 456, 78, 204, 'seed_profession', 'blacksmith', 'choice',
              items=(('Samurai', 'samurai'), ('Ninja', 'ninja'), ('Paladin', 'paladin'),
                     ('Necromancer', 'necromancer'), ('Warrior', 'warrior'), ('Mage', 'mage'),
                     ('Blacksmith', 'blacksmith'), ('Randomize', 'random'))),
        text('Prefix (Shard + Slot)', 116, w=204),
        field('seed_prefix_field', 16, 146, 204, 'seed_name_prefix', 'Llama', max_length=10),
        button('Preview names', 'preview_seed_names', 236, 142),
        text('', 116, 456, 204, 64, 'muted', 'seed_name_hint'),
        rule(190),
        check('Customize appearance', 'app_enabled', None, 16, 202, 300),
        button('Randomize All', 'randomize_all_appearance', 320, 198, 120),
        field('app_mode', 456, 202, 204, kind='choice',
              items=(('Fixed selections', 'fixed'), ('Random from selected', 'random'),
                     ('Randomize All', 'all'))),
        text('Sex', 248, w=52),
        check('Male', 'app_checks.sex_male', None, 76, 244, 90),
        check('Female', 'app_checks.sex_female', None, 176, 244, 104),
        text('Race', 284, w=96),
        check('Human', 'app_checks.race_human', None, 16, 314, 112),
        check('Elf', 'app_checks.race_elf', None, 16, 350, 112),
        check('Gargoyle', 'app_checks.race_gargoyle', None, 16, 386, 112),
        field('app_palette_pick', 144, 280, 160, kind='choice',
              items=(('Skin tone', 'skin'), ('Hair colour', 'hair'), ('Facial hair colour', 'facial'))),
        item('palette', 'Human skin tones', 144, 314, 160, 124, asset='human_skin.png',
             ref='skin_palettes.human', stack='skin'),
        item('palette', 'Elf skin tones', 144, 314, 160, 124, asset='elf_skin.png',
             ref='skin_palettes.elf', stack='skin'),
        item('palette', 'Gargoyle skin tones', 144, 314, 160, 124, asset='gargoyle_skin.png',
             ref='skin_palettes.gargoyle', stack='skin'),
        *(item('palette', '{} {} colours'.format(race.title(), part), 144, 314, 160, 124,
               asset=asset, ref='color_palettes.{}_{}'.format(race, part), stack='skin')
          for race, parts in COLOR_ASSETS.items() for part, asset in parts.items()),
        text('Style list', 248, 324, 336),
        field('app_style_group', 324, 278, 336, kind='choice', source='style_groups'),
        field('app_style_items', 324, 316, 336, kind='checklist', h=122),
        text('No shade selected: random', 444, w=288, role='muted', ref='skin_status'),
        button('Save appearance', 'save_appearance', 16, 474, tone='accent'),
        button('Clear current choice', 'clear_skin', 236, 474),
        button('Character Seeder', 'page:seeder', 456, 474),
    ],
    'status': [
        heading('Application status'),
        text('This local snapshot is informational. Starting a run still checks all prerequisites.', 48, h=40, role='muted'),
        text('', 104, h=244, role='body', ref='health_status'),
        button('Refresh status', 'refresh_health_status', 16, 370),
        button('Open local data folder', 'open_data_folder', 236, 370),
        button('Diagnostics →', 'page:diagnostics', 456, 370),
        rule(430),
        text('Ready. Run details appear in Activity; saved logs are in the local data folder.',
             450, h=50, role='muted', ref='status'),
    ],
    'diagnostics': [
        heading('Manual diagnostics'),
        text('Tests do not retry or change production scan checkpoints.', 48, role='muted'),
        text('Target shard', 88),
        field('test_shard_pick', 16, 118, 644, kind='choice'),
        button('RE bridge', 'test_probe', 16, 170, ref='test_buttons.bridge'),
        button('RE logout', 'test_logout', 236, 170, ref='test_buttons.logout'),
        button('Select shard', 'test_scroll', 456, 170, ref='test_buttons.shard_select'),
        button('Game cursor', 'test_cursor', 16, 222, ref='test_buttons.game_cursor'),
        button('Desktop cursor', 'test_desktop_cursor', 236, 222, ref='test_buttons.desktop_cursor'),
        button('Focus check', 'test_focus_comparison', 456, 222, ref='test_buttons.focus_check'),
        button('Last shard', 'test_last_shard', 16, 274, ref='test_buttons.last_shard'),
        button('Read shard title', 'test_title_shard', 236, 274, ref='test_buttons.shard_title'),
        button('Check screen →', 'page:client', 456, 274),
        text('', 338, h=40, role='muted', ref='test_status_label'),
        text('Green labels mean a previously confirmed result, not a fresh connection check.\n'
             'Naming options live under Automation > Appearance.', 390, h=46, role='note'),
        button('Clear test results', 'clear_test_results', 16, 464),
        button('Name settings & test →', 'page:seeder', 236, 464),
    ],
    'appearance': [
        heading('Project & support', 4, w=368),
        text('Mystic Llama', 36, w=368),
        text('Krampuslauf on GitHub', 62, w=368, role='muted'),
        button('Open GitHub project', 'open_project_link', 16, 92, 250, tone='accent'),
        text(VERSION, 136, w=368, role='muted'),
        item('image', 'Mystic Llama', 400, 4, 250, 236, asset='helplogo.png', ref='help_art'),

        heading('Donations', 245),
        text('Donations help keep me producing high-end applications and scripts for the\n'
             'community. I am a single father with a full-time career, so rest assured\n'
             'ALL donations get reinvested into gold, gametime, gear, and materials\n'
             'to keep creating, testing, and publishing utilities. As we all know, it\n'
             'costs an enormous amount of gold just to play anymore. — Sincerely, thank you.',
             273, h=100),

        item('image', 'Donate with PayPal', 24, 378, 220, 94,
             asset='paypal_donate.png', ref='donate_art', action='open_donation_link'),
        item('image', 'Discord', 396, 398, 52, 52, asset='discord.png', ref='discord_art'),
        text('Discord', 396, 456, 204, 22, role='muted'),
        field('discord_handle', 456, 420, 188, default='@mystikllama', readonly=True),

        text('If you would rather donate gold on ATL in-game, reach me on Discord @mystikllama.',
             478, h=24, role='muted'),
        rule(508),
        heading('Theme', 516),
        field('theme_pick', 16, 548, 316, 'appearance_theme', 'system', 'choice',
              items=(('Follow Windows', 'system'), ('Light', 'light'), ('Dark', 'dark'))),
        button('Save appearance', 'save_settings_click', 344, 544, 316, tone='accent'),
        text('Save and restart Krampuslauf to apply a theme change.', 584, h=18, role='note'),
    ],
}
# Reserve a prominent next-step strip without reducing font or button sizes.
NEXT_STEPS = {
    'setup': 'NEXT: CLOSE RAZOR + CLIENT → SETUP > PROFILES.',
    'profiles': 'NEXT: START RAZOR + CLIENT → GAME CLIENT.',
    'client': 'NEXT: SHARDS → SCAN / RESUME SHARDS.',
    'shards': 'NEXT: HELP / STATUS > DIAGNOSTICS → RE BRIDGE.',
    'diagnostics': 'NEXT: AUTOMATION → GIFT CYCLER. TEST ONE SHARD.',
    'gift': 'NEXT: START GIFT CYCLER; WATCH THE ACTIVITY WINDOW.',
    'seeder': 'NEXT: CHOOSE ACCOUNT > START CHARACTER SEEDER.',
}
for _page, _guide in NEXT_STEPS.items():
    if _page != 'setup':
        for _control in LAYOUTS[_page]:
            _control['y'] = round(_control['y'] * .94)
    LAYOUTS[_page].append(text(_guide, 564 if _page == 'setup' else 478, h=34, role='next'))


def tab_widths(available, count, gap=3):
    """Evenly fill the header, including its final pixel, at any window/DPI size."""
    if count <= 0:
        return []
    usable = max(count, int(available) - max(0, count - 1) * gap)
    base, extra = divmod(usable, count)
    return [base + (i < extra) for i in range(count)]


def layout_issues():
    """Catch clipping, overlap, duplicate bindings and dead navigation before Windows."""
    issues, refs = [], set()
    pages = [key for _, children in NAVIGATION for _, key in children]
    if len(pages) != len(set(pages)) or set(pages) != set(LAYOUTS):
        issues.append('Navigation must contain every page exactly once.')
    for page, controls in LAYOUTS.items():
        for i, a in enumerate(controls):
            if min(a['x'], a['y']) < 0 or a['x']+a['w'] > PAGE_WIDTH or a['y']+a['h'] > PAGE_HEIGHT:
                issues.append((page, 'out of bounds', a.get('ref') or a['text']))
            ref = a.get('ref')
            if ref:
                if ref in refs:
                    issues.append((page, 'duplicate binding', ref))
                refs.add(ref)
            if a.get('action', '').startswith('page:') and a['action'][5:] not in LAYOUTS:
                issues.append((page, 'unknown destination', a['action']))
            for b in controls[i+1:]:
                if a.get('stack') and a.get('stack') == b.get('stack'):
                    continue  # Only the active race palette is visible.
                if (a['x'] < b['x']+b['w'] and a['x']+a['w'] > b['x'] and
                        a['y'] < b['y']+b['h'] and a['y']+a['h'] > b['y']):
                    issues.append((page, 'overlap', a.get('ref') or a['text'], b.get('ref') or b['text']))
    return issues

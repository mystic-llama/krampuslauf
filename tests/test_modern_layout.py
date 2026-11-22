"""Layout/behavior checks without CLR, game processes, or real mouse input."""
import ast
from decimal import Decimal
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest

from ui_layout import LAYOUTS, NAVIGATION, FONT_PT, PROJECT_URL, layout_issues
from setup_checklist import checklist_from
from shard_policy import SHARD_GROUP_OPTIONS
from ui_assets import windows_text, artwork_path
from activity_history import ActivityHistory

ROOT = Path(__file__).resolve().parents[1]
TREE = ast.parse((ROOT / 'Krampuslauf.py').read_text(encoding='utf8'))
MAIN = next(n for n in TREE.body if isinstance(n, ast.ClassDef) and n.name == 'MainWindow')
METHODS = {n.name: n for n in MAIN.body if isinstance(n, ast.FunctionDef)}


def actual_methods(names, namespace):
    tree = ast.Module(body=[ast.ClassDef(name='Harness', bases=[], keywords=[],
                          body=[METHODS[n] for n in names], decorator_list=[])], type_ignores=[])
    exec(compile(ast.fix_missing_locations(tree), '<actual-gui-methods>', 'exec'), namespace)
    return namespace['Harness']


def test_every_page_fits_without_overlap_or_duplicate_bindings():
    assert layout_issues() == []
    assert len(NAVIGATION) == 3
    assert FONT_PT['heading'] > FONT_PT['body'] > FONT_PT['note']
    assert FONT_PT['warning'] == FONT_PT['note'] >= 9.5
    assert {s['h'] for page in LAYOUTS.values() for s in page if s['kind'] == 'button'} == {36}


def test_actions_still_resolve_and_creation_controls_are_unique():
    actions = [s['action'] for page in LAYOUTS.values() for s in page if s.get('action')]
    for action in actions:
        if ':' not in action:
            assert action in METHODS, action
    for action in ('start_run', 'start_seeder_run', 'open_donation_link',
                   'prepare_profile_mode', 'restore_profile_mode', 'verify_screen', 'record_point',
                   'reset_point', 'clear_skin'):
        assert actions.count(action) == 1
    refs = {s.get('ref') for page in LAYOUTS.values() for s in page}
    assert not {'gump_mode', 'town_crier_calibrate', 'seed_point_pick', 'name_verified_label'} & refs
    assert 'history' not in LAYOUTS
    assert 'clear_history' not in actions
    assert next(s for s in LAYOUTS['status'] if s.get('ref') == 'status')
    assert 'open_data_folder' in actions
    assert PROJECT_URL == 'https://github.com/mystic-llama/krampuslauf'
    help_text = '\n'.join(s['text'] for s in LAYOUTS['appearance'] if s['kind'] == 'text')
    assert 'high-end applications and scripts' in help_text
    assert 'enormous amount of gold' in help_text
    assert '@mystikllama' in help_text
    donate = [s for s in LAYOUTS['appearance'] if s.get('action') == 'open_donation_link']
    assert donate == [s for s in LAYOUTS['appearance'] if s.get('asset') == 'paypal_donate.png']
    assert any(s.get('asset') == 'discord.png' for s in LAYOUTS['appearance'])


class Items(list):
    def Add(self, value):
        self.append(value)


class Control:
    def __init__(self):
        self.Items = Items()
        self.Controls = Items()
        self.Text = ''
        self.SelectedIndex = -1
        self.Enabled = True


def make(parent, text, x, y, w, h=28, *args, **kwargs):
    ctl = Control()
    ctl.Text, ctl.Location, ctl.Size = str(text), (x, y), (w, h)
    parent.Controls.Add(ctl)
    return ctl


@pytest.fixture
def mounted():
    written = []
    def entry(parent, x, y, w, value, multiline=False):
        return make(parent, windows_text(value) if multiline else value, x, y, w)
    ns = dict(LAYOUTS=LAYOUTS, FONT_PT=FONT_PT,
              label=make, button=make, entry=entry, combo=lambda p, x, y, w: make(p, '', x, y, w),
              NumericUpDown=Control, CheckBox=Control, RadioButton=Control, ListBox=Control, Panel=Control,
              CheckedListBox=Control, POINT_LABELS=(('first_row', 'First row'),),
              appearance=__import__('appearance'),
              Point=lambda x,y:(x,y), Size=lambda x,y:(x,y), Font=lambda *v:v,
              Color=SimpleNamespace(FromArgb=lambda *v:v), Padding=lambda *v:v,
              ContentAlignment=SimpleNamespace(MiddleLeft=1),
              Decimal=SimpleNamespace(Parse=Decimal), ScrollBars=SimpleNamespace(Vertical=1),
              BorderStyle=SimpleNamespace(FixedSingle=1), Cursors=SimpleNamespace(Hand=1),
              protected_ui=lambda callback: callback,
              INK='ink', CARD='card', PANEL='panel',
              ACCENT='accent', MUTED='muted', windows_text=windows_text,
              net_integer=int, CONFIG_FILE='temporary-settings',
              checklist_from=checklist_from, SHARD_GROUP_OPTIONS=SHARD_GROUP_OPTIONS,
              atomic_json=lambda path, data: written.append(data.copy()))
    cls = actual_methods(['mount_page', 'layout_action', 'save_settings', 'format_slot_rules',
                          'update_seed_name_mode', 'randomize_all_appearance', 'sync_shard_group'], ns)
    app = cls()
    app.cfg = dict(shards=['Legends', 'Atlantic'], gift_wait=9, row_spacing=25,
                   post_logout_seconds=7, online_cooldown_seconds=305,
                   appearance_theme='dark', points={'first_row': [377, 114]},
                   window_title='private account title', skip_slots={'Atlantic': [1, 2]},
                   monkey_setup={'doors': True}, seed_name_prefix='Llama')
    app.pages = {k: Control() for k in LAYOUTS}
    app.setup_checks, app.test_buttons, app.app_checks, app.skin_palettes, app.account_radios = {}, {}, {}, {}, {}
    app.color_palettes = {}
    for method in METHODS:
        if not hasattr(app, method):
            setattr(app, method, Mock())

    class Event(list):
        def __iadd__(self, handler):
            self.append(handler)
            return self

    def add_artwork(parent, filename, x, y, width, height):
        ctl = Control()
        ctl.Click = Event()
        parent.Controls.Add(ctl)
        return ctl

    app.add_artwork = add_artwork
    for key in LAYOUTS:
        app.mount_page(key)
    return app, written


def test_mounting_all_pages_preserves_saved_options_and_test_bindings(mounted):
    app, _ = mounted
    assert app.theme_pick.SelectedIndex == 2
    assert app.gift_wait.Value == 9
    assert app.setup_checks['doors'].Checked
    assert len(app.test_buttons) == 8
    assert hasattr(app, 'screen_status') and hasattr(app, 'point_status')
    assert set(app.app_checks) == {'sex_male', 'sex_female', 'race_human', 'race_elf', 'race_gargoyle'}
    assert set(app.skin_palettes) == {'human', 'elf', 'gargoyle'}
    assert set(app.color_palettes) == {'human_hair', 'human_facial', 'elf_hair', 'gargoyle_hair', 'gargoyle_facial'}
    assert app.app_style_group.Items == list(__import__('appearance').STYLE_LABELS.values())
    assert app.point_pick.Items == ['First row']
    assert app.shard_text.Text == 'Legends\r\nAtlantic'
    assert app.slots_field.Text == 'Atlantic: 1,2'
    assert not hasattr(app, 'log')
    assert app.status in app.pages['status'].Controls


def test_distributed_settings_round_trip_without_saving_window_title(mounted):
    app, written = mounted
    app.gift_wait.Value = 15
    app.theme_pick.SelectedIndex = 1
    app.seed_mode_pick.SelectedIndex = 1
    app.seed_style_pick.SelectedIndex = 0
    app.seed_prefix_field.Text = 'unused prefix'
    app.save_settings()
    result = written[-1]
    assert result['gift_wait'] == 15
    assert 'gump_cleanup_mode' not in result
    assert 'points' not in result  # Built-in layout is never persisted as user calibration.
    assert result['appearance_theme'] == 'light'
    assert result['seed_naming_mode'] == 'fantasy'
    assert result['seed_fantasy_style'] == 'single'
    assert result['seed_name_prefix'] == 'Llama'
    assert result['window_title'] == ''
    assert result['account_cap'] == 7 and result['visible_rows'] == 9


def test_naming_controls_follow_mode_and_routes_bind_to_their_own_target(mounted):
    app, _ = mounted
    app.seed_mode_pick.SelectedIndex = 1
    app.update_seed_name_mode()
    assert app.seed_style_pick.Enabled and not app.seed_prefix_field.Enabled
    app.layout_action('page:client')(None, None)
    app.show_page.assert_called_once_with('client')


def test_shard_group_controls_share_and_save_the_selection(mounted):
    app, written = mounted
    assert app.gift_shard_group.Items == app.seed_shard_group.Items == [
        'All shards', 'English shards', 'Asian shards']
    for picker, index, group in ((app.seed_shard_group, 2, 'asian'),
                                  (app.gift_shard_group, 1, 'english')):
        picker.SelectedIndex = index
        app.sync_shard_group(picker, None)
        assert app.gift_shard_group.SelectedIndex == app.seed_shard_group.SelectedIndex == index
        app.save_settings()
        assert written[-1]['shard_group'] == group


def test_randomize_all_button_enables_appearance_and_saves_mode(mounted):
    app, _ = mounted
    app.layout_action('randomize_all_appearance')(None, None)
    assert app.app_enabled.Checked
    assert app.app_mode.Items[app.app_mode.SelectedIndex] == 'Randomize All'
    app.save_appearance.assert_called_once_with(None, None)


def test_account_settings_snapshots_preserve_exclusions_capacity_and_cycle():
    from account_profiles import settings_snapshot, new_catalog
    first = dict(excluded=['Legends'], skip_slots={'Atlantic': [2]}, account_cap=5,
                 reserve_transfer_slot=True, gift_cycle_id='first')
    saved = settings_snapshot(first)
    first['excluded'].append('Pacific')
    assert saved['excluded'] == ['Legends']
    assert saved['account_cap'] == 5 and saved['reserve_transfer_slot']
    assert saved['skip_slots'] == {'Atlantic': [2]}
    assert saved['gift_cycle_id'] == 'first'
    catalog = new_catalog()
    key = catalog['accounts']['account2']['history_id']
    catalog['accounts']['account2']['nickname'] = 'Weekend account'
    assert catalog['accounts']['account2']['history_id'] == key


@pytest.mark.parametrize('active', [False, True])
def test_logging_persists_and_updates_activity_without_a_history_page(tmp_path, active):
    app = actual_methods(['log_line'], {'datetime': datetime})()
    app.history_store = ActivityHistory(tmp_path / 'activity_history.log')
    app.status = SimpleNamespace(Text='Ready')
    app.activity_window = SimpleNamespace(log=Mock(TextLength=42), status=SimpleNamespace(Text='Ready'))
    app.active_compact_run = active
    config = tmp_path / 'settings.json'
    config.write_text('preserve account settings')
    app.log_line('ERROR DETAILS: test failure')
    assert not hasattr(app, 'log')
    assert 'ERROR DETAILS: test failure' in app.history_store.tail()
    assert app.status.Text == 'ERROR DETAILS: test failure'
    if active:
        app.activity_window.log.AppendText.assert_called_once()
        assert 'ERROR DETAILS: test failure' in app.activity_window.log.AppendText.call_args.args[0]
        app.activity_window.log.ScrollToCaret.assert_called_once()
        assert app.activity_window.status.Text == 'ERROR DETAILS: test failure'
    else:
        app.activity_window.log.AppendText.assert_not_called()
    assert config.read_text() == 'preserve account settings'


def test_logging_before_controls_exist_still_saves_the_error(tmp_path):
    app = actual_methods(['log_line'], {'datetime': datetime})()
    app.history_store = ActivityHistory(tmp_path / 'activity_history.log')
    app.log_line('Artwork could not be loaded')
    assert 'Artwork could not be loaded' in app.history_store.tail()


def test_history_normalization_keeps_lines_and_is_idempotent():
    text = 'Legends\nAtlantic\r\nCatskills\rOrigin'
    normalized = windows_text(text)
    assert normalized == 'Legends\r\nAtlantic\r\nCatskills\r\nOrigin'
    assert windows_text(normalized) == normalized


def test_editable_art_beside_exe_takes_priority_and_missing_art_is_optional(tmp_path):
    source, bundle, exe = (tmp_path/name for name in ('source', 'bundle', 'app'))
    for folder in (source, bundle, exe):
        (folder/'assets').mkdir(parents=True)
    args = dict(executable=exe/'app.exe', source_dir=source, bundle_dir=bundle)
    assert artwork_path(**args) is None
    (bundle/'assets'/'logo.png').write_bytes(b'bundled')
    assert artwork_path(**args) == bundle/'assets'/'logo.png'
    (exe/'assets'/'logo.png').write_bytes(b'custom')
    assert artwork_path(**args) == exe/'assets'/'logo.png'


@pytest.mark.parametrize('compact', [False, True])
def test_all_jobs_expose_pause_stop_while_only_runs_hide_main(compact):
    class InlineThread:
        def __init__(self, target, daemon):
            self.target = target
        def start(self):
            self.target()
    ns = dict(threading=SimpleNamespace(Thread=InlineThread), Cancelled=RuntimeError,
              BridgeCancelled=RuntimeError, pg=SimpleNamespace(FailSafeException=RuntimeError),
              EscapeHotkey=lambda callback: SimpleNamespace(start=lambda: True, close=Mock()))
    app = actual_methods(['run_job'], ns)()
    app.busy = lambda: False
    app.stop_event, app.pause_event, app.events = Mock(), Mock(), Mock()
    for name in ('start_btn', 'seed_start_btn', 'tabs', 'stop_btn', 'pause_btn'):
        setattr(app, name, SimpleNamespace(Enabled=True, Text=''))
    app.activity_window = SimpleNamespace(escape_hint=SimpleNamespace(Text=""))
    app.signal_escape = Mock()
    app.show_activity_window, app.log_line = Mock(), Mock()
    def diagnostic():
        app.show_activity_window.assert_called_once_with(hide_main=compact)
    app.run_job(diagnostic, compact=compact)
    app.show_activity_window.assert_called_once_with(hide_main=compact)
    assert app.active_compact_run and app.stop_btn.Enabled and app.pause_btn.Enabled
    assert not app.tabs.Enabled
    assert app.events.put.call_args.args[0][0] == 'done'


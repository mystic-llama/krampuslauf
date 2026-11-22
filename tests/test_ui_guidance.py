"""Users receive an action and a real destination; raw diagnostics stay in the saved activity log."""
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ui_guidance import ActionNeeded, explain_error
from ui_layout import LAYOUTS, tab_widths


def test_marker_mismatch_explains_tooltips_without_blame_or_a_false_pause():
    result = explain_error('Game screen changed before mouse input; no click sent.')
    assert result.page == 'client'
    assert 'tooltip' in result.message and 'Check current screen' in result.message
    assert 'while paused' not in result.message
    assert 'Calibrat' not in result.message


def test_creation_capacity_error_names_the_setting_and_destination():
    result = explain_error('Choose the actual account slot capacity: 5, 6 or 7.')
    assert result.page == 'seeder'
    assert 'Keep one slot empty' in result.message and 'selected account' in result.message


@pytest.mark.parametrize('error,page,action', [
    ('Incomplete setup checklist', 'setup', 'Save checklist'),
    ('Built-in login screen marker is missing from assets/screen_markers; reinstall', 'client', 'assets folder'),
    ('Classic Client game area is 1024x768, not a 640x480 menu screen', 'client', 'Check current screen'),
    ('Shard row/spacing setting invalid', 'shards', 'row spacing'),
    ('Record click point app_skin_elf_first under Game client > Click points', 'client', 'Record selected'),
    ('Fixed appearance mode allows one race only.', 'looks', 'Save appearance'),
    ('No unfinished or pending creations in this Seeder history', 'seeder', 'Select the account'),
    ('Creation outcome unknown; PENDING', 'seeder', 'restart'),
    ('No krampuslauf_bridge.py heartbeat', 'diagnostics', 'AutoStart at Login'),
    ('No included shards in the selected shard group.', 'gift', 'Check at least one shard'),
    ('Logout NOT verified', 'status', 'log out manually'),
    ('Close Razor Enhanced and Classic Client', 'profiles', 'Close both'),
])
def test_known_failures_have_specific_recovery(error, page, action):
    issue = explain_error(RuntimeError(error))
    assert issue.page == page and issue.page in LAYOUTS
    assert action in issue.message


def test_unknown_error_does_not_guess_or_leak_technical_text():
    issue = explain_error(RuntimeError('0xDEADBEEF private-file-path.py:246'))
    assert issue.page == 'status'
    assert 'Open local data folder' in issue.message and 'activity_history.log' in issue.message
    assert '0xDEADBEEF' not in issue.message


def actual_gui_method(name, ns):
    tree = ast.parse((Path(__file__).resolve().parents[1] / 'Krampuslauf.py').read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'MainWindow')
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])), '<gui>', 'exec'), ns)
    return ns[name]


@pytest.mark.parametrize('entry', ['Origin: abc', 'Origin: 2-1', 'Origin: 1-1000000000'])
def test_bad_slot_input_has_no_python_conversion_error(entry):
    reader = actual_gui_method('read_slot_rules', {'ActionNeeded': ActionNeeded})
    app = SimpleNamespace(slots_field=SimpleNamespace(Text=entry), cfg={'shards': ['Origin']})
    with pytest.raises(ActionNeeded) as caught:
        reader(app)
    assert explain_error(caught.value).page == 'gift'


def test_prompt_is_actionable_logs_details_and_only_navigates_when_idle():
    shown = []
    ns = dict(explain_error=explain_error, MessageBox=SimpleNamespace(Show=lambda *a: shown.append(a)),
              MessageBoxButtons=SimpleNamespace(OK=1), MessageBoxIcon=SimpleNamespace(Warning=2))
    report = actual_gui_method('report_ui_error', ns)
    app = SimpleNamespace(cfg={'window_title': 'private title'}, page_paths={'client': True},
                          busy=lambda: False, log_line=Mock(), show_page=Mock())
    report(app, RuntimeError('Built-in servers marker missing; private title'))
    assert '[selected client]' in app.log_line.call_args.args[0]
    assert 'private title' not in app.log_line.call_args.args[0]
    assert 'assets folder' in shown[-1][1]
    app.show_page.assert_called_once_with('client')
    app.show_page.reset_mock()
    app.busy = lambda: True
    report(app, RuntimeError('Built-in servers marker missing'))
    app.show_page.assert_not_called()


def test_tabs_fill_available_width_at_common_display_scales():
    for width in (676, 845, 1014, 1352):
        for count in (2, 3, 4, 6):
            widths = tab_widths(width, count)
            assert sum(widths) + 3 * (count - 1) == width
            assert max(widths) - min(widths) <= 1

"""Exercise actual input/pause methods with no Windows or real mouse input."""
import ast
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import native_mouse
import escape_hotkey

ROOT = Path(__file__).resolve().parents[1]


def methods(filename, owner, names, ns):
    tree = ast.parse((ROOT / filename).read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == owner)
    body = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert len(body) == len(names)
    target = ast.ClassDef(name='Harness', bases=[], keywords=[], body=body, decorator_list=[])
    exec(compile(ast.fix_missing_locations(ast.Module(body=[target], type_ignores=[])), '<production>', 'exec'), ns)
    return ns['Harness']


def pointer_worker(on_pause):
    cancelled = type('Cancelled', (Exception,), {})
    ns = dict(native_mouse=native_mouse, Cancelled=cancelled,
              focus_game=lambda title: None, point_screen=lambda title, x, y: (x, y))
    worker = methods('cycler_engine.py', 'GameWorker', ['pointer_action'], ns)()
    worker.pause, worker.stop = threading.Event(), threading.Event()
    worker.window_title = 'test'
    worker.context = (1, 0, 0, 800, 600, 'servers', None)
    worker.input_context = lambda: worker.context
    worker.sleep = lambda seconds: None
    worker.messages = []
    worker.say = worker.emit = worker.messages.append
    def check():
        if worker.pause.is_set():
            on_pause(worker)
        if worker.stop.is_set():
            raise cancelled('Stopped')
    worker.check = check
    return worker, cancelled


def test_bump_pauses_before_click_then_resume_retries_same_verified_action():
    phases = []
    def resume(w):
        phases.append('paused')
        assert not any(p == 'clicked' for p in phases)
        w.pause.clear()
    w, _ = pointer_worker(resume)
    calls = []
    def action(x, y, before_click):
        calls.append((x, y))
        if len(calls) == 1:
            raise native_mouse.PointerInterrupted('bumped')
        before_click(0)
        phases.append('clicked')
        return {'ok': True}
    assert w.pointer_action((10, 20), action, expected='servers') == {'ok': True}
    assert phases == ['paused', 'clicked'] and len(calls) == 2


def test_stop_while_mouse_paused_sends_no_retry():
    w, cancelled = pointer_worker(lambda w: w.stop.set())
    action = Mock(side_effect=native_mouse.PointerInterrupted('bumped'))
    with pytest.raises(cancelled):
        w.pointer_action((10, 20), action)
    assert action.call_count == 1


def test_screen_change_while_paused_prevents_retry():
    def changed(w):
        w.context = (*w.context[:5], 'characters', 'Catskills')
        w.pause.clear()
    w, _ = pointer_worker(changed)
    action = Mock(side_effect=native_mouse.PointerInterrupted('bumped'))
    with pytest.raises(RuntimeError, match='changed while paused'):
        w.pointer_action((10, 20), action)
    assert action.call_count == 1


def test_marker_change_before_first_click_is_not_reported_as_a_mouse_pause():
    w, _ = pointer_worker(lambda _: pytest.fail('No mouse interruption occurred'))
    w.input_context = Mock(side_effect=[w.context, (*w.context[:5], 'unknown', None)])
    action = Mock()
    with pytest.raises(RuntimeError, match='changed before mouse input'):
        w.pointer_action((10, 20), action)
    action.assert_not_called()


def test_partial_double_click_waits_for_resume_but_is_never_replayed():
    w, _ = pointer_worker(lambda w: w.pause.clear())
    action = Mock(side_effect=native_mouse.PointerInterrupted('after first click', clicks_sent=1))
    result = w.pointer_action((10, 20), action)
    assert result == {'clicks_sent': 1, 'interrupted': True}
    assert action.call_count == 1


def test_native_pointer_change_sends_no_button_down(monkeypatch):
    sent = []
    monkeypatch.setattr(native_mouse, 'move_cursor', lambda *a: {})
    monkeypatch.setattr(native_mouse, 'cursor_position', lambda: (300, 400))
    monkeypatch.setattr(native_mouse, '_input_mouse', lambda flags: sent.append(flags))
    with pytest.raises(native_mouse.PointerInterrupted) as caught:
        native_mouse.click_cursor(10, 20)
    assert caught.value.clicks_sent == 0 and sent == []


def test_native_move_notifies_input_queue_even_when_setcursorpos_succeeded(monkeypatch):
    notified = []
    monkeypatch.setattr(native_mouse, '_win_only', lambda: None)
    monkeypatch.setattr(native_mouse, '_user', SimpleNamespace(SetCursorPos=lambda x,y: 1), raising=False)
    monkeypatch.setattr(native_mouse.ctypes, 'set_last_error', lambda n: None, raising=False)
    monkeypatch.setattr(native_mouse.ctypes, 'get_last_error', lambda: 0, raising=False)
    monkeypatch.setattr(native_mouse, 'cursor_position', lambda: (10,20))
    monkeypatch.setattr(native_mouse, 'clip_rectangle', lambda: (0,0,800,600))
    monkeypatch.setattr(native_mouse, 'virtual_desktop', lambda: (0,0,800,600))
    monkeypatch.setattr(native_mouse, '_send_absolute', lambda x,y: (notified.append((x,y)) or 1,0))
    monkeypatch.setattr(native_mouse.time, 'sleep', lambda seconds: None)
    native_mouse.move_cursor(10,20)
    assert notified == [(10,20)]


def test_second_click_interruption_releases_first_button_and_reports_partial(monkeypatch):
    sent = []
    monkeypatch.setattr(native_mouse, '_win_only', lambda: None)
    monkeypatch.setattr(native_mouse, 'move_cursor', lambda *a: {})
    monkeypatch.setattr(native_mouse, 'cursor_position', lambda: (10, 20))
    monkeypatch.setattr(native_mouse.time, 'sleep', lambda seconds: None)
    monkeypatch.setattr(native_mouse, '_input_mouse', lambda flags: (sent.append(flags) or 1, 0))
    def guard(clicks_sent):
        if clicks_sent:
            raise native_mouse.PointerInterrupted('paused')
    with pytest.raises(native_mouse.PointerInterrupted) as caught:
        native_mouse.double_click_cursor(10, 20, before_click=guard)
    assert sent == [0x0002, 0x0004]
    assert caught.value.clicks_sent == 1


def double_click_harness(monkeypatch):
    sent = []
    monkeypatch.setattr(native_mouse, '_win_only', lambda: None)
    monkeypatch.setattr(native_mouse, 'move_cursor', lambda *a: {})
    monkeypatch.setattr(native_mouse, 'cursor_position', lambda: (10, 20))
    monkeypatch.setattr(native_mouse.time, 'sleep', lambda seconds: None)
    monkeypatch.setattr(native_mouse, '_input_mouse', lambda flags: (sent.append(flags) or 1, 0))
    return sent


def test_double_click_sends_both_clicks_when_the_screen_check_passes(monkeypatch):
    sent = double_click_harness(monkeypatch)
    result = native_mouse.double_click_cursor(10, 20, between_clicks=lambda: True)
    assert sent == [0x0002, 0x0004] * 2 and 'second_click_skipped' not in result


def test_double_click_skips_the_second_click_when_the_screen_changed(monkeypatch):
    sent = double_click_harness(monkeypatch)
    result = native_mouse.double_click_cursor(10, 20, between_clicks=lambda: False)
    assert sent == [0x0002, 0x0004] and result['second_click_skipped'] is True


def test_double_click_without_a_screen_check_is_unchanged(monkeypatch):
    sent = double_click_harness(monkeypatch)
    native_mouse.double_click_cursor(10, 20)
    assert sent == [0x0002, 0x0004] * 2


def double_click_worker(screen):
    calls = {}
    ns = dict(native_mouse=SimpleNamespace(
        click_cursor=object(),
        double_click_cursor=lambda *a, **kw: calls.update(args=a, kwargs=kw) or {}), DOUBLE_CLICK_GAP=.09)
    target = methods('cycler_engine.py', 'GameWorker', ['click', 'second_click_allowed'], ns)()
    target.state = lambda: screen
    target.messages = []
    target.say = target.messages.append
    target.pointer_action = lambda point, operation, **kw: operation(1, 2, before_click=None)
    return target, calls


def test_shard_double_click_asks_the_screen_before_the_second_click():
    target, calls = double_click_worker('servers')
    target.click([5, 6], expected='servers', double=True)
    assert calls['kwargs']['interval'] == .09 and calls['kwargs']['between_clicks']() is True
    target.state = lambda: 'characters'
    assert calls['kwargs']['between_clicks']() is False
    assert 'second click was not sent' in target.messages[-1]


def test_a_double_click_must_name_the_screen_it_expects():
    target, _ = double_click_worker('servers')
    with pytest.raises(ValueError):
        target.click([5, 6], double=True)


def test_pause_time_does_not_consume_navigation_or_wait_deadline():
    clock = SimpleNamespace(value=0.0)
    def sleep(seconds): clock.value += seconds
    ns = dict(time=SimpleNamespace(monotonic=lambda: clock.value, sleep=sleep),
              Cancelled=RuntimeError)
    w = methods('cycler_engine.py', 'GameWorker', ['clock', 'check', 'sleep'], ns)()
    w.pause = threading.Event()
    w.pause.set()
    def wait(seconds):
        clock.value += 120
        w.pause.clear()
        return False
    w.stop = SimpleNamespace(is_set=lambda: False, wait=wait)
    w.emit = Mock()
    w.sleep(1)
    assert w.clock() == pytest.approx(1)
    assert clock.value == pytest.approx(121)


def test_escape_pauses_then_stops_and_never_resumes():
    ns = dict(escape_action=escape_hotkey.escape_action)
    w = methods('Krampuslauf.py', 'MainWindow', ['signal_escape'], ns)()
    w.stop_event, w.pause_event = threading.Event(), threading.Event()
    w.events = Mock()
    bridge = Mock()
    w.game_worker = SimpleNamespace(bridge=bridge)
    w.signal_escape()
    assert w.pause_event.is_set() and not w.stop_event.is_set()
    w.signal_escape()
    assert w.stop_event.is_set()
    bridge.abort.assert_called_once()
    w.signal_escape()
    bridge.abort.assert_called_once()


@pytest.mark.parametrize('callback_fails', [False, True])
def test_hotkey_lease_uses_no_repeat_and_always_unregisters(monkeypatch, callback_fails):
    user = SimpleNamespace(RegisterHotKey=Mock(return_value=1),
                           UnregisterHotKey=Mock(return_value=1), PeekMessageW=Mock())
    h = escape_hotkey.EscapeHotkey(lambda: None)
    delivered = []
    def callback():
        delivered.append('escape')
        h._ending.set()
        if callback_fails:
            raise RuntimeError('callback failed')
    h.callback = callback
    def peek(pointer, *args):
        if delivered: return 0
        pointer._obj.wParam = 0x474D
        return 1
    user.PeekMessageW.side_effect = peek
    monkeypatch.setattr(escape_hotkey.ctypes, 'WinDLL', lambda *a, **k: user, raising=False)
    h._run()
    assert delivered == ['escape']
    user.RegisterHotKey.assert_called_once_with(None, 0x474D, 0x4000, 0x1B)
    user.UnregisterHotKey.assert_called_once_with(None, 0x474D)


@pytest.mark.parametrize('kind', ['click', 'press'])
def test_input_no_longer_kicks_the_cursor_afterwards(kind):
    events = []
    ns = dict(native_mouse=SimpleNamespace(click_cursor=object()),
              focus_game=lambda *a: None, pg=SimpleNamespace(press=lambda key: events.append('key-up')))
    target = methods('cycler_engine.py', 'GameWorker', ['click', 'press'], ns)()
    target.window_title = 'test'
    target.check = lambda: None
    target.park_menu_cursor = lambda: events.append('park')
    target.pointer_action = lambda *args, **kw: events.append('button-up') or {}
    if kind == 'click': target.click([10, 20])
    else: target.press('enter')
    assert events == [('button-up' if kind == 'click' else 'key-up')]


def test_idle_pointer_reports_only_a_pointer_still_where_it_was_placed(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(native_mouse.time, 'monotonic', lambda: now[0])
    monkeypatch.setattr(native_mouse, '_last_placed', (100.0, 400, 500))
    monkeypatch.setattr(native_mouse, 'cursor_position', lambda: (401, 499))
    assert native_mouse.idle_pointer(4) is None
    now[0] = 104.5
    assert native_mouse.idle_pointer(4) == (401, 499)
    monkeypatch.setattr(native_mouse, 'cursor_position', lambda: (900, 500))
    assert native_mouse.idle_pointer(4) is None
    monkeypatch.setattr(native_mouse, '_last_placed', None)
    assert native_mouse.idle_pointer(4) is None


def test_incomplete_click_does_not_park_cursor():
    parked = []
    target = methods('cycler_engine.py', 'GameWorker', ['click'],
                     dict(native_mouse=SimpleNamespace(click_cursor=object())))()
    target.pointer_action = lambda *a, **kw: {'interrupted': True}
    target.park_menu_cursor = lambda: parked.append(True)
    target.click([10, 20])
    assert not parked


def test_scroll_burst_positions_once_and_stops_after_partial_interruption(monkeypatch):
    positions, inputs = [], []
    monkeypatch.setattr(native_mouse, 'move_cursor', lambda *a: positions.append(a) or {})
    monkeypatch.setattr(native_mouse, 'cursor_position', lambda: (10,20))
    monkeypatch.setattr(native_mouse, '_input_mouse', lambda flag: (inputs.append(flag) or 1,0))
    monkeypatch.setattr(native_mouse.time, 'sleep', lambda *a: None)
    def before(count):
        if count==3: raise native_mouse.PointerInterrupted('user moved mouse')
    with pytest.raises(native_mouse.PointerInterrupted) as caught:
        native_mouse.click_cursor_many(10,20,18,before_click=before)
    assert caught.value.clicks_sent==3
    assert positions==[(10,20)]
    assert inputs==[0x0002,0x0004]*3


def test_partial_scroll_burst_never_selects_an_unverified_row():
    ns=dict(native_mouse=SimpleNamespace())
    target=methods('cycler_engine.py','GameWorker',['scroll_shard_arrow'],ns)()
    target.cfg={'points':{'scroll_down':[537,354]}}
    target.pointer_action=lambda *a,**kw:{'interrupted':True,'clicks_sent':3}
    target.shard_list_at_top=True
    target.park_menu_cursor=lambda:pytest.fail('must halt before more input')
    with pytest.raises(RuntimeError,match='row position is unverified'):
        target.scroll_shard_arrow('scroll_down',18)
    assert not target.shard_list_at_top

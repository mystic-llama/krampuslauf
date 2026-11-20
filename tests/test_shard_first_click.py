"""Actual shard selector: first success, genuine retry and transition safety."""
import ast
from pathlib import Path

import pytest


def selector(outcomes, wrong_title=False):
    path = Path(__file__).resolve().parents[1] / 'cycler_engine.py'
    tree = ast.parse(path.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'GameWorker')
    nodes = [n for n in cls.body if isinstance(n, ast.FunctionDef)
             and n.name in ('scroll_to_shard', 'wait_out_sync_panel')]
    ns = dict(KNOWN_SHARDS=['Catskills'], shard_from_title=lambda *a: None,
              SyncScreen=RuntimeError, OnlineBusy=RuntimeError, SYNC_PATIENCE_SECONDS=30.0)
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), '<selector>', 'exec'), ns)
    class Worker:
        def __init__(self):
            self.cfg = {'shards':['Catskills'], 'visible_rows':9, 'row_spacing':25,
                        'points':{'first_row':(50,80)}}
            self.shard_list_at_top = True
            self.current = 'servers'
            self.t = 0
            self.calls, self.messages = [], []
            self.selected_index = None
        def clock(self): return self.t
        def state(self): return self.current
        def sleep(self, seconds): self.t += seconds
        def seed_visible(self, marker): return False
        def say(self, text): self.messages.append(text)
        def click(self, point, **kwargs):
            self.calls.append((point, kwargs))
            self.current = outcomes[min(len(self.calls)-1,len(outcomes)-1)]
        wait_out_sync_panel = ns['wait_out_sync_panel']
        def shard_row_point(self, index): return (50, 80)
        def title_identity_check(self, wanted):
            if wrong_title: raise RuntimeError('wrong shard')
            return wanted
        def verify_selected_shard(self, wanted): return self.title_identity_check(wanted)
    return Worker(), ns['scroll_to_shard']


def test_successful_first_selection_does_not_log_a_retry():
    w, select = selector(['characters'])
    select(w, 0)
    assert len(w.calls) == 1 and w.selected_index == 0
    assert w.calls[0][1] == {'expected':'servers', 'settle':.35, 'double':True}
    assert not any('retry' in line.lower() or 'attempt 1/3' in line for line in w.messages)


def test_retry_only_after_no_response_on_verified_shard_list():
    w, select = selector(['servers', 'characters'])
    select(w, 0)
    assert len(w.calls) == 2 and w.t >= 7
    assert any('did not open within 6 seconds' in line for line in w.messages)
    assert any('attempt 2/3' in line for line in w.messages)


def test_ambiguous_transition_never_gets_an_extra_shard_click():
    w, select = selector(['unknown'])
    # Unknown menu with no known title is still not permission for a retry.
    select.__globals__['selected_window'] = lambda title: type('Window',(),{'title':''})()
    w.window_title = 'test'
    with pytest.raises(RuntimeError, match='refusing extra click'):
        select(w, 0)
    assert len(w.calls) == 1


def test_wrong_shard_identity_is_still_rejected_before_character_input():
    w, select = selector(['characters'], wrong_title=True)
    with pytest.raises(RuntimeError, match='wrong shard'):
        select(w, 0)
    assert len(w.calls) == 1 and w.selected_index is None


def test_title_can_change_before_character_marker_appears():
    w, select = selector(['unknown'])
    w.window_title = 'test'
    states = iter(['servers', 'unknown', 'unknown', 'characters'])
    w.state = lambda: next(states, 'characters')
    select.__globals__['selected_window'] = lambda title: type('Window', (), {'title': 'Catskills'})()
    select.__globals__['shard_from_title'] = lambda *args: 'Catskills'
    select(w, 0)
    assert w.selected_index == 0
    assert len(w.calls) == 1
    assert any('finish loading' in text for text in w.messages)


def test_title_transition_never_authorizes_an_extra_click_even_if_list_reappears():
    w, select = selector(['unknown'])
    w.window_title = 'test'
    states = iter(['servers', 'unknown'])
    w.state = lambda: next(states, 'servers')
    select.__globals__['selected_window'] = lambda title: type('Window', (), {'title': 'Catskills'})()
    select.__globals__['shard_from_title'] = lambda *args: 'Catskills'
    with pytest.raises(RuntimeError, match='refusing extra click'):
        select(w, 0)
    assert len(w.calls) == 1
    assert w.t >= 6


def test_slow_shard_connection_panel_is_waited_out_without_input():
    w, select = selector(['unknown'])
    states = iter(['servers'] + ['sync_error'] * 8)
    w.state = lambda: next(states, 'characters')
    select(w, 0)
    assert w.selected_index == 0 and len(w.calls) == 1
    assert any('Transient Origin marker' in text for text in w.messages)


def test_very_slow_connection_is_still_waited_out_well_beyond_the_old_limit():
    w, select = selector(['unknown'])
    states = iter(['servers'] + ['sync_error'] * 40)
    w.state = lambda: next(states, 'characters')
    select(w, 0)
    assert w.selected_index == 0 and len(w.calls) == 1 and w.t > 10


def test_origin_panel_that_never_clears_still_halts_after_the_patience_window():
    w, select = selector(['unknown'])
    w.cfg['sync_transient_seconds'] = 4
    states = iter(['servers'])
    w.state = lambda: next(states, 'sync_error')
    with pytest.raises(RuntimeError, match='Origin error'):
        select(w, 0)
    assert len(w.calls) == 1 and 3.9 <= w.t <= 6


@pytest.mark.parametrize('settled', ['characters', 'sync_error'])
def test_origin_warning_requires_a_second_frame_before_halting(settled):
    w, select = selector(['unknown'])
    states = iter(['servers', 'sync_error', settled])
    w.state = lambda: next(states, settled)
    if settled == 'characters':
        select(w, 0)
        assert w.selected_index == 0
    else:
        with pytest.raises(RuntimeError, match='Origin error'):
            select(w, 0)
        assert w.selected_index is None
    assert len(w.calls) == 1

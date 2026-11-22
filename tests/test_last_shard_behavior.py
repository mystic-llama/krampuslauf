"""Execute just the platform-independent shortcut method with fake screens."""
import ast
import pathlib
import time
import unittest
ROOT = pathlib.Path(__file__).resolve().parents[1]
root = ast.parse((ROOT / 'cycler_engine.py').read_text(encoding='utf-8'))
worker = next(n for n in root.body if isinstance(n, ast.ClassDef) and n.name == 'GameWorker')
method = next(n for n in worker.body if isinstance(n, ast.FunctionDef) and n.name == 'select_last_shard_shortcut')
function_code = compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])), 'isolated', 'exec')
namespace = {'time': time}
exec(function_code, namespace)
select_shortcut = namespace['select_last_shard_shortcut']

class FakeWorker:
    def __init__(self, cfg, last, states):
        self.cfg = cfg
        self.last_verified_shard = last
        self.fast_shortcut_failed = set()
        self._states = iter(states)
        self.pressed = []
        self.clicked = []
        self.logs = []
        self.selected_index = None
        self.cfg.setdefault('points', {})['last_shard'] = [200, 460]
    def clock(self):
        return time.monotonic()
    def state(self):
        return next(self._states, 'characters')
    def press(self, key):
        self.pressed.append(key)
    def click(self, point, expected=None):
        self.clicked.append((point, expected))
    def sleep(self, seconds):
        pass
    def say(self, text):
        self.logs.append(text)
    def title_identity_check(self, shard):
        self.logs.append('title identity check: ' + shard)
        return shard

class FastReturnBehavior(unittest.TestCase):
    def config(self, enabled=True):
        return {'shards': ['Legends', 'Atlantic'], 'fast_last_shard': enabled}
    def test_saved_checkbox_does_not_block_the_button(self):
        w = FakeWorker(self.config(False), 'Atlantic', ['servers', 'servers', 'characters'])
        self.assertTrue(select_shortcut(w, 1))
        self.assertEqual(w.clicked, [([200, 460], 'servers')])
        self.assertEqual(w.pressed, [])
    def test_unverified_shard_cannot_use_fast_path(self):
        w = FakeWorker(self.config(), None, ['servers', 'characters'])
        self.assertFalse(select_shortcut(w, 1))
        self.assertEqual(w.pressed, [])
        self.assertEqual(w.clicked, [])
    def test_wrong_shard_cannot_use_fast_path(self):
        w = FakeWorker(self.config(), 'Legends', ['servers', 'characters'])
        self.assertFalse(select_shortcut(w, 1))
        self.assertEqual(w.pressed, [])
        self.assertEqual(w.clicked, [])
    def test_menu_is_verified_before_enter(self):
        w = FakeWorker(self.config(), 'Atlantic', ['characters'])
        with self.assertRaisesRegex(RuntimeError, 'not on shard list'):
            select_shortcut(w, 1)
        self.assertEqual(w.pressed, [])
        self.assertEqual(w.clicked, [])
    def test_button_is_clicked_once_on_the_server_menu(self):
        w = FakeWorker(self.config(), 'Atlantic', ['servers', 'servers', 'characters'])
        self.assertTrue(select_shortcut(w, 1))
        self.assertEqual(w.clicked, [([200, 460], 'servers')])
        self.assertEqual(w.pressed, [])
        self.assertEqual(w.selected_index, 1)
    def test_login_screen_after_the_button_fails_closed(self):
        w = FakeWorker(self.config(), 'Atlantic', ['servers', 'login'])
        with self.assertRaisesRegex(RuntimeError, 'returned to login'):
            select_shortcut(w, 1)
        self.assertEqual(w.clicked, [([200, 460], 'servers')])
        self.assertEqual(w.pressed, [])

if __name__ == '__main__':
    unittest.main()


def test_confirmed_creation_enables_fast_return(monkeypatch):
    from types import SimpleNamespace
    import seeder_engine
    from menu_layout import default_points
    from seeder_rules import name_hash
    from unittest.mock import Mock
    w = FakeWorker({'shards': ['Legends'], 'fast_last_shard': True,
                    'points': default_points()}, None, ['servers', 'characters'])
    record = {'created': [], 'completed': []}
    status = {'name_sha256': name_hash('Arin Vale'), 'instance_id': 'new-world', 'shard': 'Legends'}
    w.check_seed_setup = w.check = lambda: None
    w.seed_record = lambda shard: ({}, record)
    w.seed_update = lambda shard, **updates: record.update(updates)
    w.seed_name_for_slot = lambda *args, **kwargs: 'Arin Vale'
    w.seed_new_available = lambda: True
    w.seed_wait_marker = lambda *args: None
    w.apply_appearance = lambda: None
    w.click = lambda *args, **kwargs: None
    w.seed_visible = lambda marker: True
    w.bridge_status = lambda *args, **kwargs: status
    w.bridge = SimpleNamespace(request_route_inn=lambda *args, **kwargs: [4403, 1164, 0])
    w.logout = lambda: None
    monkeypatch.setattr(seeder_engine.pg, 'write', Mock())
    assert seeder_engine.SeederOperations.seed_one(w, 0, 'Legends')
    assert w.last_verified_shard == 'Legends'
    w.click = lambda point, expected=None: w.clicked.append((point, expected))
    assert select_shortcut(w, 0)
    assert w.clicked == [([200, 460], 'servers')]
    assert w.pressed == []


def test_wrong_creation_fingerprint_does_not_enable_fast_return(monkeypatch):
    from types import SimpleNamespace
    import pytest
    import seeder_engine
    from menu_layout import default_points
    from unittest.mock import Mock
    w = FakeWorker({'shards': ['Legends'], 'fast_last_shard': True,
                    'points': default_points()}, None, ['servers', 'characters'])
    record = {'created': [], 'completed': []}
    w.check_seed_setup = w.check = lambda: None
    w.seed_record = lambda shard: ({}, record)
    w.seed_update = lambda shard, **updates: record.update(updates)
    w.seed_name_for_slot = lambda *args, **kwargs: 'Arin Vale'
    w.seed_new_available = lambda: True
    w.seed_wait_marker = lambda *args: None
    w.apply_appearance = lambda: None
    w.click = lambda *args, **kwargs: None
    w.seed_visible = lambda marker: True
    w.bridge_status = lambda *args, **kwargs: {'name_sha256': 'wrong', 'instance_id': 'new-world'}
    monkeypatch.setattr(seeder_engine.pg, 'write', Mock())
    with pytest.raises(RuntimeError, match='fingerprint mismatch'):
        seeder_engine.SeederOperations.seed_one(w, 0, 'Legends')
    assert w.last_verified_shard is None
    assert not select_shortcut(w, 0)
    assert w.clicked == []
    assert w.pressed == []

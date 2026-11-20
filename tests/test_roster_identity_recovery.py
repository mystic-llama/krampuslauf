"""Pure, no-Windows-session regression tests for shifted character menus."""
import ast
import json
import os
import time
import tempfile
import threading
import unittest
from pathlib import Path
from datetime import datetime
from unittest.mock import patch

import recovery_rules
from seeder_rules import account_token, name_hash

# Load the real GameWorker class without importing Windows-only PyAutoGUI,
# native mouse, or image grabbing into this Linux-based regression suite.
ROOT = Path(__file__).resolve().parents[1]
tree = ast.parse((ROOT / 'cycler_engine.py').read_text(encoding='utf-8'))
klass = next(node for node in tree.body if isinstance(node, ast.ClassDef)
             and node.name == 'GameWorker')
ns = {'time': time, 'datetime': datetime, 'PVP_SHARDS': recovery_rules.PVP_SHARDS,
      'occupied_slots_for': recovery_rules.occupied_slots_for}
exec(compile(ast.fix_missing_locations(ast.Module(body=[node for node in tree.body if isinstance(node, ast.ClassDef) and node.name in ('Cancelled','SyncScreen','OnlineBusy','EmptySlot','GameWorker')], type_ignores=[])),
             'cycler_engine.py', 'exec'), ns)
GameWorker = ns['GameWorker']

def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return default

def atomic_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj), encoding='utf-8')

ns['load_json'] = load_json
ns['atomic_json'] = atomic_json


class FakeBridge:
    def __init__(self, stop):
        self.stop = stop
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def get_status(self): return None


class RosterResumeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        names = ('PROGRESS_FILE', 'IDENTITY_PROGRESS_FILE', 'ROSTER_CHANGE_FILE',
                 'SEED_PROGRESS_FILE', 'ISSUES_FILE')
        for name in names:
            ns[name] = root / (name.lower() + '.json')
        ns['BridgeSession'] = FakeBridge

    def worker(self):
        w = GameWorker.__new__(GameWorker)
        w.cfg = {
            'shards': ['Catskills'], 'excluded': [],
            'auto_detect_slots': True, 'skip_slots': {'Catskills': [3,4,5,6,7]},
            'create_missing': True, 'post_logout_seconds': 3,
            'seed_name_prefix': 'Llama',
        }
        w.progress_id = 'cycle-test'
        w.completed = {'Catskills|1'}   # old row-1 completion before roster shifted
        w.gift_identity_history = {}
        w.roster_sensitive_shards = set()
        w.seeded_character_hashes = {}
        w.seed_account_id = account_token('Seeder session A')
        w.stop = threading.Event()
        w.last_bridge = None
        w.pause = threading.Event()
        w.emit = lambda *_: None
        w.say = lambda *_: None
        w.sleep = lambda *_: None
        w.check = lambda *_: None
        w.reach_characters = lambda *_: None
        w.logout = lambda *_: None
        w.waited_gifts = []
        w.wait_gift = lambda shard: w.waited_gifts.append(w.last_bridge['name_sha256'])
        w.state = lambda: 'characters'
        w.title_identity_check = lambda *_args, **_kwargs: None
        w.seed_new_available = lambda: True
        w.bridge = None
        w._save_progress = lambda: None
        return w

    def seed_history(self, names):
        atomic_json(ns['SEED_PROGRESS_FILE'], {
            'profiles': {account_token('Seeder session A'): {
                'Catskills': {'pending': None, 'created': list(names), 'completed': list(names)}
            }}
        })

    def test_reloaded_shifted_roster_processes_by_identity(self):
        self.seed_history(['Llama CAT b'])
        worker = self.worker()
        order = {1: 'Llama CAT b', 2: 'Veteran Cat'}
        def enter(_index, slot):
            worker.last_bridge = {'name_sha256': name_hash(order[slot+1])}
            return True
        worker.enter_slot = enter
        worker.run()
        self.assertEqual(worker.waited_gifts, [name_hash('Veteran Cat')])
        data = load_json(ns['IDENTITY_PROGRESS_FILE'], {})
        self.assertEqual(data['cycle-test']['Catskills'], [name_hash('Veteran Cat')])
        self.assertIn('Catskills', load_json(ns['ROSTER_CHANGE_FILE'], {})['cycle-test'])
        # Legacy row-1 completion did not cause the newly shifted row-2
        # character to be skipped, nor count the fresh character as a gift.

    def test_next_cycle_collects_earlier_creations_but_excludes_current_ones(self):
        self.seed_history(['Earlier Name', 'Current Name'])
        state = load_json(ns['SEED_PROGRESS_FILE'], {})
        record = state['profiles'][account_token('Seeder session A')]['Catskills']
        record['creation_cycles'] = {'Earlier Name': 'previous', 'Current Name': 'new'}
        atomic_json(ns['SEED_PROGRESS_FILE'], state)
        worker = self.worker()
        worker.cfg['gift_cycle_id'] = 'new'
        order = {1: 'Earlier Name', 2: 'Current Name'}
        def enter(_index, slot):
            worker.last_bridge = {'name_sha256': name_hash(order[slot + 1])}
            return True
        worker.enter_slot = enter
        worker.run()
        self.assertEqual(worker.waited_gifts, [name_hash('Earlier Name')])
        self.assertEqual(load_json(ns['SEED_PROGRESS_FILE'], {}), state)

    def test_saved_fingerprint_avoids_repeat_after_restart(self):
        self.seed_history(['Llama CAT b'])
        worker = self.worker()
        atomic_json(ns['IDENTITY_PROGRESS_FILE'], {
            'cycle-test': {'Catskills': [name_hash('Veteran Cat')]}
        })
        worker.gift_identity_history = worker._read_identity_progress()
        names = {1: 'Llama CAT b', 2: 'Veteran Cat'}
        def enter(_index, slot):
            worker.last_bridge = {'name_sha256': name_hash(names[slot+1])}
            return True
        worker.enter_slot = enter
        worker.run()
        self.assertFalse(worker.waited_gifts)

    def test_successful_seed_finishes_shard_without_revisiting_rows(self):
        # A veteran occupies row 1 and row 2 is empty. With combined mode,
        # inspect row 1 by identity even when old slot progress says complete.
        self.seed_history([])
        worker = self.worker()
        veteran=name_hash('Veteran Cat')
        worker.gift_identity_history={'Catskills': {veteran}}
        attempted_slots=[]
        handoffs=[]
        def enter(_index, slot):
            attempted_slots.append(slot + 1)
            if slot==0:
                worker.last_bridge={'name_sha256': veteran}
                return True
            return False
        worker.enter_slot=enter
        worker.complete_combined_shard=lambda index, shard, slot, **kw: handoffs.append((index,shard,slot,kw)) or True
        worker.run()
        self.assertEqual(attempted_slots, [1,2,2])
        self.assertEqual(handoffs, [(0,'Catskills',2,{})])
        self.assertFalse(worker.waited_gifts)

    def test_zero_character_shard_enters_seeder_directly(self):
        self.seed_history([])
        worker = self.worker()
        calls = []
        worker.reach_characters = lambda *_: 'creation'
        worker.state = lambda: 'new_character'
        worker.seed_visible = lambda marker: marker == 'seed_appearance'
        worker.enter_slot = lambda *_: self.fail('Must not click a character slot on a zero-character shard')
        worker.complete_combined_shard = lambda idx, shard, slot, **kw: calls.append((idx,shard,slot,kw)) or True
        worker.run()
        self.assertEqual(calls, [(0,'Catskills',1,{'on_creation':True})])

    def test_interrupted_seeder_is_resumed_before_any_gift_slot(self):
        self.seed_history([])
        worker = self.worker()
        calls=[]
        worker.combined_shard_status=lambda shard: {'status':'in_progress','next_slot':3}
        worker.complete_combined_shard=lambda idx, shard, slot, **kw: calls.append((idx,shard,slot)) or True
        worker.enter_slot=lambda *_: self.fail('Must not try shifted rows during a Seeder resume')
        worker.run()
        self.assertEqual(calls,[(0,'Catskills',3)])

    def test_completed_seeder_skips_shard_before_row_selection(self):
        self.seed_history([])
        worker=self.worker()
        worker.combined_shard_status=lambda shard:{'status':'complete','next_slot':8}
        worker.enter_slot=lambda *_: self.fail('Must not revisit a seeded shard in this cycle')
        worker.run()

    def test_warning_already_returned_to_login_is_not_clicked(self):
        w = self.worker()
        states = iter(['unknown', 'login'])
        w.state = lambda: next(states)
        w.press = lambda *_: self.fail('Must not send Enter on login screen')
        w.login_after_warning = False
        w.selected_index = 6
        w.acknowledge_warning('sync_error')
        self.assertTrue(w.login_after_warning)
        self.assertIsNone(w.selected_index)

    def test_unknown_warning_still_halts_without_input(self):
        w = self.worker()
        w.state = lambda: 'unknown'
        w.press = lambda *_: self.fail('Must not send Enter on unknown screen')
        with self.assertRaisesRegex(RuntimeError, 'No Enter sent'):
            w.acknowledge_warning('sync_error')


if __name__ == '__main__':
    unittest.main()

import unittest
from pathlib import Path
from seed_recovery import (
    pending_seed_candidates, confirm_pending_not_created,
    promote_pending_after_world_proof, name_fingerprint,
)

ACCOUNT = 'testhistory'
SHARD = 'Catskills'
NAME = 'Llama CAT b'


def sample():
    return {'profiles': {ACCOUNT: {SHARD: {
        'pending': NAME, 'created': ['Llama CAT a'], 'completed': ['Llama CAT a']
    }, 'Atlantic': {'pending': None, 'created': [], 'completed': []}}}}


class PendingRecoveryTests(unittest.TestCase):
    def test_find_specific_pending_and_preserve_other_shards(self):
        self.assertEqual(pending_seed_candidates(sample(), ACCOUNT), [(SHARD, NAME)])

    def test_manually_confirmed_absence_clears_only_pending(self):
        s = sample()
        confirm_pending_not_created(s, ACCOUNT, SHARD, NAME)
        rec = s['profiles'][ACCOUNT][SHARD]
        self.assertIsNone(rec['pending'])
        self.assertEqual(rec['created'], ['Llama CAT a'])
        self.assertEqual(rec['completed'], ['Llama CAT a'])
        self.assertEqual(rec['manual_resolutions'][0]['decision'], 'not_created')
        self.assertIsNone(s['profiles'][ACCOUNT]['Atlantic']['pending'])

    def test_wrong_pending_name_is_rejected(self):
        with self.assertRaises(ValueError):
            confirm_pending_not_created(sample(), ACCOUNT, SHARD, 'Llama CAT c')

    def test_pending_existing_in_created_is_not_cleared(self):
        s = sample()
        s['profiles'][ACCOUNT][SHARD]['created'].append(NAME)
        with self.assertRaises(ValueError):
            confirm_pending_not_created(s, ACCOUNT, SHARD, NAME)

    def test_world_proof_promotes_pending_to_created(self):
        s = sample()
        status={'connected': True, 'shard': SHARD, 'name_sha256': name_fingerprint(NAME)}
        promote_pending_after_world_proof(s, ACCOUNT, SHARD, NAME, status)
        rec = s['profiles'][ACCOUNT][SHARD]
        self.assertIsNone(rec['pending'])
        self.assertIn(NAME, rec['created'])
        self.assertNotIn(NAME, rec['completed'])

    def test_incorrect_or_disconnected_bridge_never_promotes(self):
        for status in [
            {'connected':False, 'shard':SHARD, 'name_sha256':name_fingerprint(NAME)},
            {'connected':True, 'shard':'Atlantic', 'name_sha256':name_fingerprint(NAME)},
            {'connected':True, 'shard':SHARD, 'name_sha256':name_fingerprint('Llama CAT c')},
        ]:
            s=sample()
            with self.assertRaises(ValueError):
                promote_pending_after_world_proof(s, ACCOUNT, SHARD, NAME, status)
            self.assertEqual(s['profiles'][ACCOUNT][SHARD]['pending'], NAME)

    def test_five_second_character_screen_watch_is_separate(self):
        root=Path(__file__).resolve().parents[1]
        engine=(root/'cycler_engine.py').read_text()
        self.assertIn('self.clock() - character_screen_seen_after > 5:', engine)
        self.assertIn('"world_timeout": 55', engine)
        self.assertIn('Double-clicked character slot', engine)

    def test_recovery_and_reset_controls_are_removed(self):
        from ui_layout import LAYOUTS
        self.assertNotIn('recovery', LAYOUTS)
        self.assertNotIn('end_previous_attempt', [s.get('action') for s in LAYOUTS['seeder']])


if __name__=='__main__':
    unittest.main()


def test_manual_absence_releases_saved_name_assignment():
    state = sample()
    record = state['profiles'][ACCOUNT][SHARD]
    record['name_assignments'] = {'2': NAME, '3': 'Other Name'}
    confirm_pending_not_created(state, ACCOUNT, SHARD, NAME)
    assert record['name_assignments'] == {'3': 'Other Name'}


def test_end_attempt_archives_pending_routes_and_assignments_without_touching_others():
    from copy import deepcopy
    from seed_recovery import end_seed_attempt
    state = sample()
    record = state['profiles'][ACCOUNT][SHARD]
    record['name_assignments'] = {'2': NAME}
    record['combined_shard'] = {'next_slot': 2, 'status': 'in_progress'}
    state['profiles']['other'] = {'Atlantic': {'pending': 'Keep Me'}}
    previous = deepcopy(state['profiles'][ACCOUNT])
    end_seed_attempt(state, ACCOUNT, 'attempt-archive')
    assert state['profiles'][ACCOUNT] == {}
    assert state['archived_attempts']['attempt-archive']['records'] == previous
    assert state['profiles']['other']['Atlantic']['pending'] == 'Keep Me'
    state['profiles'][ACCOUNT]['New'] = {}
    assert 'New' not in state['archived_attempts']['attempt-archive']['records']

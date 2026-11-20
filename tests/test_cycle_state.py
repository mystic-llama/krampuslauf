"""Migration and cycle boundaries must preserve the permanent creation ledger."""
import ast
import copy
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from cycle_state import adopt_legacy_creations, checkpoint_for_cycle, excluded_creation_names
from seeder_rules import account_token

ROOT = Path(__file__).resolve().parents[1]


def test_legacy_adoption_is_once_per_name_and_only_for_selected_account():
    record = {'created': ['Old Name'], 'completed': ['Old Name'], 'pending': 'Pending Name',
              'name_assignments': {'1': 'Old Name'},
              'combined_shard': {'status': 'complete', 'next_slot': 8}}
    state = {'profiles': {'selected': {'Catskills': record}, 'other': {'Origin': copy.deepcopy(record)}}}
    original = copy.deepcopy(state)
    assert adopt_legacy_creations(state, 'selected', 'first-cycle')
    assert not adopt_legacy_creations(state, 'selected', 'second-cycle')
    assert state['profiles']['other'] == original['profiles']['other']
    assert {k: v for k, v in record.items() if k != 'creation_cycles'} == original['profiles']['selected']['Catskills']
    assert record['creation_cycles'] == {'Old Name': 'first-cycle', 'Pending Name': 'first-cycle'}
    assert excluded_creation_names(record, 'first-cycle') == ['Old Name', 'Pending Name']
    assert excluded_creation_names(record, 'second-cycle') == ['Pending Name']
    assert checkpoint_for_cycle(record, 'first-cycle') == {}


def test_only_matching_cycle_can_skip_or_resume_a_shard():
    for status in ('complete', 'in_progress'):
        checkpoint = {'status': status, 'next_slot': 3, 'cycle_id': 'event-one'}
        record = {'combined_shard': checkpoint}
        assert checkpoint_for_cycle(record, 'event-one') == checkpoint
        assert checkpoint_for_cycle(record, 'event-two') == {}
        assert checkpoint_for_cycle(record, '') == {}
    assert checkpoint_for_cycle({'combined_shard': {'status': 'complete'}}, 'new') == {}


def seed_worker(tmp_path, cycle='first-cycle'):
    tree = ast.parse((ROOT / 'seeder_engine.py').read_text(encoding='utf8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'SeederOperations')
    methods = [n for n in cls.body if isinstance(n, ast.FunctionDef)
               and n.name in ('seed_init', 'seed_record', 'seed_update')]
    ledger = tmp_path / 'seeder_progress.json'
    ns = dict(SEED_PROGRESS_FILE=ledger, account_token=account_token,
              load_json=lambda p, default: json.loads(p.read_text()) if p.exists() else default,
              atomic_json=lambda p, data: p.write_text(json.dumps(data)))
    module = ast.Module(body=[ast.ClassDef(name='Worker', bases=[], keywords=[], body=methods,
                                         decorator_list=[])], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), '<production-seeder>', 'exec'), ns)
    worker = ns['Worker']()
    worker.cfg = {'gift_cycle_id': cycle}
    return worker, ledger


def legacy_ledger(path):
    data = {'profiles': {account_token('local account'): {'Catskills': {
        'created': ['Old Name'], 'completed': ['Old Name'], 'pending': None}}}}
    path.write_text(json.dumps(data, indent=4) + '\n')
    return path.read_bytes()


def test_real_seed_init_backs_up_exact_bytes_before_migration(tmp_path):
    worker, ledger = seed_worker(tmp_path)
    before = legacy_ledger(ledger)
    worker.seed_init('local account')
    backups = list(tmp_path.glob('seeder_progress.before-cycle-tags-*.json'))
    assert len(backups) == 1 and backups[0].read_bytes() == before
    worker.cfg['gift_cycle_id'] = 'next-cycle'
    worker.seed_init('local account')
    assert len(list(tmp_path.glob('seeder_progress.before-cycle-tags-*.json'))) == 1
    _, record = worker.seed_record('Catskills')
    assert record['creation_cycles']['Old Name'] == 'first-cycle'
    assert record['created'] == record['completed'] == ['Old Name']


def test_failed_migration_backup_cannot_change_live_ledger(tmp_path):
    worker, ledger = seed_worker(tmp_path)
    before = legacy_ledger(ledger)
    with patch('shutil.copy2', side_effect=OSError('backup unavailable')):
        with pytest.raises(OSError):
            worker.seed_init('local account')
    assert ledger.read_bytes() == before


def test_pending_submission_saves_cycle_and_recovery_cannot_retag_it(tmp_path):
    worker, ledger = seed_worker(tmp_path)
    worker.seed_init('local account')
    worker.seed_update('Catskills', pending='New Name')
    saved = json.loads(ledger.read_text())['profiles'][account_token('local account')]['Catskills']
    assert saved['pending'] == 'New Name'
    assert saved['creation_cycles'] == {'New Name': 'first-cycle'}
    worker.cfg['gift_cycle_id'] = 'later-cycle'
    worker.seed_update('Catskills', pending='New Name')
    assert worker.seed_record('Catskills')[1]['creation_cycles']['New Name'] == 'first-cycle'


def test_unknown_age_and_pending_names_are_conservatively_excluded():
    record = {'created': ['Unknown', 'Earlier', 'Current'], 'pending': 'Pending',
              'creation_cycles': {'Earlier': 'old', 'Current': 'now', 'Pending': 'old'}}
    assert excluded_creation_names(record, 'now') == ['Unknown', 'Current', 'Pending']


def test_confirmed_absent_retry_belongs_to_new_cycle(tmp_path):
    from seed_recovery import confirm_pending_not_created
    worker, ledger = seed_worker(tmp_path)
    worker.seed_init('local account')
    worker.seed_update('Catskills', pending='Retry Name')
    state = json.loads(ledger.read_text())
    confirm_pending_not_created(state, worker.seed_account_id, 'Catskills', 'Retry Name')
    ledger.write_text(json.dumps(state))
    worker.cfg['gift_cycle_id'] = 'later-cycle'
    worker.seed_update('Catskills', pending='Retry Name')
    record = worker.seed_record('Catskills')[1]
    assert record['creation_cycles']['Retry Name'] == 'later-cycle'
    worker.seed_update('Catskills', created=['Retry Name'], completed=['Retry Name'], pending=None)
    assert excluded_creation_names(worker.seed_record('Catskills')[1], 'later-cycle') == ['Retry Name']

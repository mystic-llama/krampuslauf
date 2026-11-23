"""Exercise reservation through the production workers, without game input."""
import ast
import copy
from pathlib import Path
from types import MethodType

import pytest

import test_combined_shard_seeding as combined
import test_roster_identity_recovery as roster
from recovery_rules import PVP_SHARDS, creation_limit, occupied_slots_for
from seed_recovery import archive_pending_after_menu
from seeder_rules import generated_name, name_hash

ROOT = Path(__file__).resolve().parents[1]
tree = ast.parse((ROOT / 'seeder_engine.py').read_text(encoding='utf8'))
source = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'SeederOperations')
names = {'seed_record', 'seed_update', 'combined_shard_status',
         'complete_combined_shard', 'run_seeder', 'seed_one', 'archive_pending_creation'}
body = [n for n in source.body if isinstance(n, ast.FunctionDef) and n.name in names]
namespace = dict(PVP_SHARDS=PVP_SHARDS, generated_name=generated_name,
                 SeedNotReady=RuntimeError, load_json=roster.load_json,
                 atomic_json=roster.atomic_json, archive_pending_after_menu=archive_pending_after_menu)
exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.ClassDef(
    name='Seeder', bases=[], keywords=[], body=body, decorator_list=[])],
    type_ignores=[])), '<production-reservation-methods>', 'exec'), namespace)
Seeder = namespace['Seeder']


@pytest.mark.parametrize('capacity,limit', [(5, 4), (6, 5), (7, 6)])
def test_creation_ceiling_is_total_capacity_minus_one(capacity, limit):
    cfg = {'account_cap': capacity, 'reserve_transfer_slot': True}
    assert creation_limit(cfg, 'Catskills') == limit
    assert creation_limit(dict(cfg, reserve_transfer_slot=False), 'Catskills') == capacity


@pytest.mark.parametrize('shard', ['Mugen', 'Siege Perilous'])
def test_unsupported_shards_have_no_eligible_slots(shard):
    cfg = {'account_cap': 7, 'reserve_transfer_slot': True, 'auto_detect_slots': True}
    assert creation_limit(cfg, shard) == 0
    assert occupied_slots_for(cfg, shard) == []
    assert occupied_slots_for(cfg, 'Catskills') == list(range(1, 8))


@pytest.mark.parametrize('capacity', [0, 4, 8, 'unknown'])
def test_invalid_capacity_is_rejected(capacity):
    with pytest.raises(ValueError):
        creation_limit({'account_cap': capacity}, 'Catskills')


@pytest.mark.parametrize('capacity', [5, 6, 7])
def test_partly_populated_handoff_includes_existing_characters(capacity):
    h = combined.Harness(cap=capacity)
    h.cfg['reserve_transfer_slot'] = True
    h.complete_combined_shard(0, 'Catskills', 3)
    assert [a[1] for a in h.actions if a[0] == 'create'] == list(range(3, capacity))
    assert h.saved['Catskills']['combined_shard']['reason'] == 'transfer_slot_reserved'


def test_reserved_empty_row_returns_from_creation_without_submitting():
    h = combined.Harness()
    h.cfg['reserve_transfer_slot'] = True
    h.recover_empty_slot = lambda: h.actions.append(('back',))
    h.complete_combined_shard(0, 'Catskills', 7, on_creation=True)
    assert h.actions == [('back',)]


@pytest.mark.parametrize('unfinished', [False, True])
def test_lowering_limit_cannot_hide_pending_or_unfinished_creation(unfinished):
    h = combined.Harness()
    h.cfg['reserve_transfer_slot'] = True
    h.seed_update('Catskills', combined_shard={
        'cycle_id': 'test-cycle', 'status': 'in_progress', 'next_slot': 7, 'cap': 7},
        pending=None if unfinished else 'Llama CAT g',
        created=['Llama CAT g'] if unfinished else [])
    with pytest.raises(RuntimeError, match='Unfinished|PENDING'):
        h.complete_combined_shard(0, 'Catskills', 1)
    assert h.saved['Catskills']['combined_shard']['status'] == 'in_progress'
    assert not h.actions


def test_lowered_limit_completes_without_creating_and_can_later_be_raised():
    h = combined.Harness()
    h.cfg['reserve_transfer_slot'] = True
    h.seed_update('Catskills', combined_shard={
        'cycle_id': 'test-cycle', 'status': 'in_progress', 'next_slot': 7, 'cap': 7})
    h.complete_combined_shard(0, 'Catskills', 1)
    assert not h.actions
    assert h.combined_shard_status('Catskills')['status'] == 'complete'
    h.cfg['reserve_transfer_slot'] = False
    assert h.combined_shard_status('Catskills') == {}
    assert h.saved['Catskills']['combined_shard']['cap'] == 6


@pytest.fixture
def worker():
    case = roster.RosterResumeTests(methodName='runTest')
    case.setUp()
    w = case.worker()
    namespace['SEED_PROGRESS_FILE'] = roster.ns['SEED_PROGRESS_FILE']
    for name in names - {'seed_one'}:
        setattr(w, name, MethodType(getattr(Seeder, name), w))
    w.cfg.update(account_cap=7, reserve_transfer_slot=True,
                 gift_cycle_id='cycle-test', skip_slots={})
    w.seed_nickname = 'Seeder session A'
    w.check_seed_setup = lambda: None
    w.attempted_rows, w.created_rows, w.logouts, w.messages = [], [], [], []
    w.say = w.messages.append
    w.logout = lambda: w.logouts.append(True)
    w.reach_characters = lambda _index: 'characters'
    w.recover_empty_slot = lambda: None
    def create(index, shard, already_on_creation=False, slot_number=None):
        name = generated_name('Llama', '', index, slot_number - 1, shard=shard)
        w.seed_update(shard, pending=name)
        _, rec = w.seed_record(shard)
        w.seed_update(shard, pending=None, created=rec['created'] + [name],
                      completed=rec['completed'] + [name])
        w.created_rows.append(slot_number)
        return True
    w.seed_one = create
    yield w
    case.doCleanups()


def occupied_rows(w, count):
    def enter(_index, zero_based):
        row = zero_based + 1
        w.attempted_rows.append(row)
        if row > count:
            return False
        w.last_bridge = {'name_sha256': name_hash('Existing {}'.format(row))}
        return True
    w.enter_slot = enter


@pytest.mark.parametrize('existing,created', [(2, [3, 4, 5, 6]), (6, []), (7, [])])
def test_standalone_checks_total_without_recording_gifts(worker, existing, created):
    occupied_rows(worker, existing)
    # Seeder must examine rows even if the user skipped them in Gift Cycler.
    worker.cfg['skip_slots'] = {'Catskills': [1, 2, 3, 4, 5, 6, 7]}
    original = copy.deepcopy(worker.cfg)
    completed = set(worker.completed)
    worker.run_seeder()
    assert worker.created_rows == created
    assert worker.attempted_rows[:min(existing, 6)] == list(range(1, min(existing, 6) + 1))
    assert not worker.waited_gifts
    assert worker.completed == completed and not worker.gift_identity_history
    assert worker.cfg == original and not worker._seeder_reserve_only
    record = worker.seed_record('Catskills')[1]
    assert record['reserved_seeder_shard']['status'] == 'complete'
    assert 'combined_shard' not in record
    assert worker.combined_shard_status('Catskills') == {}
    assert set(record.get('creation_cycles', {}).values()) <= {'cycle-test'}


@pytest.mark.parametrize('existing, expected', [(5, [6]), (6, [])])
def test_pending_restart_uses_live_roster_to_keep_transfer_slot(worker, existing, expected):
    occupied_rows(worker, existing)
    worker.seed_update(
        'Catskills', pending='Shitha Rowan', name_assignments={'6': 'Shitha Rowan'},
        reserved_seeder_shard={'status': 'in_progress', 'cycle_id': 'cycle-test',
                               'next_slot': 6, 'cap': 6})

    worker.run_seeder()

    assert worker.attempted_rows[:existing] == list(range(1, existing + 1))
    assert worker.created_rows == expected
    _, record = worker.seed_record('Catskills')
    assert record['pending'] is None
    assert record['unconfirmed_creations'] == ['Shitha Rowan']
    assert record['reserved_seeder_shard']['status'] == 'complete'


def test_standalone_restores_settings_after_failure(worker):
    original = worker.cfg
    worker.run = lambda **_: (_ for _ in ()).throw(RuntimeError('interrupted'))
    with pytest.raises(RuntimeError, match='interrupted'):
        worker.run_seeder()
    assert worker.cfg is original and not worker._seeder_reserve_only


def test_standalone_skips_one_slot_shard_without_game_input(worker):
    worker.cfg['shards'] = ['Mugen']
    worker.reach_characters = lambda *_: pytest.fail('One-slot shard must not be entered')
    worker.run_seeder()
    assert not worker.created_rows and not worker.waited_gifts


def test_empty_shard_standalone_creates_only_six_characters(worker):
    worker.reach_characters = lambda *_: 'creation'
    worker.state = lambda: 'new_character'
    worker.enter_slot = lambda *_: pytest.fail('Do not click rows on a creation screen')
    worker.run_seeder()
    assert worker.created_rows == [1, 2, 3, 4, 5, 6]


def test_unsupported_shard_in_combined_mode_sends_no_input(worker):
    worker.cfg['shards'] = ['Mugen']
    worker.reach_characters = lambda *_: 'creation'
    worker.state = lambda: 'new_character'
    exits = []
    worker.recover_empty_slot = lambda: exits.append(True)
    worker.run()
    assert exits == [] and not worker.created_rows


def test_unsupported_shard_never_gets_gift_processing(worker):
    worker.cfg['shards'] = ['Mugen']
    occupied_rows(worker, 1)
    worker.run()
    assert worker.waited_gifts == []
    assert not worker.created_rows


def test_combined_mode_collects_from_existing_seventh_character(worker):
    occupied_rows(worker, 7)
    worker.run()
    assert worker.attempted_rows == list(range(1, 8))
    assert worker.waited_gifts == [name_hash('Existing {}'.format(n)) for n in range(1, 8)]
    assert not worker.created_rows


@pytest.mark.parametrize('mode', ['cycler', 'combined', 'reserved_seeder'])
def test_cycler_paths_run_only_checked_shards_in_the_selected_group(worker, mode):
    worker.cfg.update(shards=['Catskills', 'Balhae', 'Atlantic', 'Sakura'],
                      shard_group='asian', excluded=['Sakura'],
                      create_missing=mode == 'combined')
    occupied_rows(worker, 7)
    enter_slot = worker.enter_slot
    visited = set()

    def record_visit(index, row):
        visited.add(index)
        return enter_slot(index, row)

    worker.enter_slot = record_visit
    if mode == 'reserved_seeder':
        worker.run_seeder()
    else:
        worker.run()
    assert visited == {1}


def test_combined_mode_collects_existing_characters_before_seeding(worker):
    occupied_rows(worker, 2)
    worker.run()
    assert worker.created_rows == [3, 4, 5, 6]
    assert worker.waited_gifts == [name_hash('Existing 1'), name_hash('Existing 2')]


def test_standalone_checkpoint_does_not_skip_existing_gifts_later(worker):
    occupied_rows(worker, 6)
    worker.run_seeder()
    worker.attempted_rows.clear()
    worker.run()
    assert worker.waited_gifts == [name_hash('Existing {}'.format(n)) for n in range(1, 7)]
    assert not worker.created_rows


@pytest.mark.parametrize('slot', [None, 7])
def test_seed_one_blocks_unknown_or_reserved_slot_before_input(worker, slot):
    with pytest.raises(RuntimeError, match='Transfer slot reserved'):
        Seeder.seed_one(worker, 0, 'Catskills', slot_number=slot)
    assert not worker.created_rows and not worker.attempted_rows

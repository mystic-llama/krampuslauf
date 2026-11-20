"""Account isolation and restart behavior without a game or real user data."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
import seeder_engine
from account_profiles import new_catalog, complete_catalog, display_name, settings_snapshot, shard_seed_complete


def test_nickname_changes_do_not_change_history_identity():
    catalog = new_catalog()
    before = {slot: row['history_id'] for slot,row in catalog['accounts'].items()}
    catalog['accounts']['account2']['nickname'] = 'Holiday crew'
    assert display_name(catalog,'account2') == 'Holiday crew'
    assert {slot: row['history_id'] for slot,row in catalog['accounts'].items()} == before
    assert len(set(before.values())) == 15


def test_expanding_existing_catalog_preserves_nicknames_and_history_ids():
    catalog = new_catalog()
    catalog['accounts'] = {slot: catalog['accounts'][slot] for slot in ('main','account2','account3')}
    catalog['accounts']['main']['nickname'] = 'Mum'
    catalog['accounts']['account2']['nickname'] = 'Tim'
    catalog['accounts']['account3']['nickname'] = 'Dru'
    catalog['selected'] = 'account2'
    original = deepcopy(catalog)
    expanded = complete_catalog(catalog)
    assert catalog == original
    assert expanded['selected'] == 'account2'
    assert len(expanded['accounts']) == 15
    assert all(expanded['accounts'][slot] == entry for slot,entry in original['accounts'].items())
    assert len({entry['history_id'] for entry in expanded['accounts'].values()}) == 15


def test_pending_or_capacity_change_invalidates_finished_checkpoint():
    record = {'standalone_seed': {'status':'complete','cap':7}}
    assert shard_seed_complete(record,7)
    assert not shard_seed_complete(record,6)
    record['pending'] = 'Unknown Character'
    assert not shard_seed_complete(record,7)


class Bridge:
    def __init__(self,*args): pass
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def get_status(self): return None


def worker(monkeypatch, records):
    monkeypatch.setattr(seeder_engine,'BridgeSession',Bridge)
    w = SimpleNamespace(cfg={'shards':['Drachenfels','Europa','Balhae'],
                            'account_cap':7, 'reserve_transfer_slot':False}, stop=None)
    w.check_seed_setup = w.check = w.say = w.sleep = lambda *a: None
    w.seed_record = lambda shard: ({}, records.setdefault(shard,{}))
    w.seed_update = lambda shard, **values: records.setdefault(shard,{}).update(values)
    w.reach_characters = Mock(return_value=None)
    w.seed_new_available = lambda: False
    w.seed_one = Mock()
    w.retire_interrupted_routes = Mock()
    return w


def test_restart_skips_finished_shards_without_any_client_input(monkeypatch):
    records = {shard:{'standalone_seed':{'status':'complete','cap':7}}
               for shard in ('Drachenfels','Europa')}
    first = worker(monkeypatch,records)
    seeder_engine.SeederOperations.run_seeder(first)
    assert first.reach_characters.call_args_list == [((2,),)]
    assert shard_seed_complete(records['Balhae'],7)
    second = worker(monkeypatch,deepcopy(records))
    seeder_engine.SeederOperations.run_seeder(second)
    second.reach_characters.assert_not_called()
    second.seed_one.assert_not_called()


def test_halt_retains_current_shard_checkpoint_and_completed_shards(monkeypatch):
    records = {shard:{'standalone_seed':{'status':'complete','cap':7}}
               for shard in ('Drachenfels','Europa')}
    w=worker(monkeypatch,records)
    w.seed_new_available=lambda:True
    w.seed_one=Mock(side_effect=RuntimeError('interrupted'))
    with pytest.raises(RuntimeError,match='interrupted'):
        seeder_engine.SeederOperations.run_seeder(w)
    assert records['Balhae']['standalone_seed']['status']=='in_progress'
    assert shard_seed_complete(records['Drachenfels'],7)
    assert shard_seed_complete(records['Europa'],7)



def test_overnight_migration_keeps_both_accounts_and_only_restores_proven_shards():
    from account_profiles import migrate_overnight_history
    from seeder_rules import account_token
    a,b=account_token('Seeder Session A'),account_token('Seeder Session B')
    history={'profiles':{a:{'Drachenfels':{'created':['Real Character']},
                            'Balhae':{'created':['Keep Existing'],'pending':None}},
                         b:{'Legends':{'created':['Other Account']}}}}
    cfg,saved,state,catalog,restored=migrate_overnight_history(
        {'account_cap':7,'excluded':['Legends']},{'profiles':{b:{'account_cap':5}}},history,
        ['[time] No New button on Drachenfels. No additional creation attempted.'])
    assert catalog['accounts']['account2']['history_id']==a
    assert catalog['accounts']['main']['history_id']==b
    assert cfg['selected_account_slot']=='account2'
    assert restored==['Drachenfels']
    assert shard_seed_complete(state['profiles'][a]['Drachenfels'],7)
    assert not shard_seed_complete(state['profiles'][a]['Balhae'],7)
    assert state['profiles'][b]==history['profiles'][b]
    assert state['profiles'][a]['Balhae']==history['profiles'][a]['Balhae']
    assert saved['profiles'][b]['account_cap']==5
    assert 'standalone_seed' not in history['profiles'][a]['Drachenfels']

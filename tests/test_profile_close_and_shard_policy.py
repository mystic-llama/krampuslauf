import ast
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from shard_policy import normalize_shards, supported_shards, physical_index
from recovery_rules import creation_limit, occupied_slots_for

ROOT = Path(__file__).resolve().parents[1]


def actual_method(name, namespace):
    main = next(node for node in ast.parse((ROOT / 'Krampuslauf.py').read_text(encoding='utf-8')).body
                if isinstance(node, ast.ClassDef) and node.name == 'MainWindow')
    method = next(node for node in main.body if isinstance(node, ast.FunctionDef) and node.name == name)
    module = ast.Module(body=[method], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), 'actual-method', 'exec'), namespace)
    return namespace[name]


@pytest.mark.parametrize('active,close_anyway', [(True,False),(True,True),(False,False)])
def test_profile_reminder_only_closes_after_explicit_choice(active, close_anyway):
    timer = SimpleNamespace(Stop=Mock())
    window = SimpleNamespace(busy=lambda:False, save_settings=Mock(), ui_timer=timer,
        confirm_profile_close=Mock(return_value=close_anyway), show_page=Mock(), update_isolation_state=Mock())
    event = SimpleNamespace(Cancel=False)
    method = actual_method('before_close', {'APP_DIR':None,'session_status':lambda _: {'active':active}})
    method(window,None,event)
    if active and not close_anyway:
        assert event.Cancel
        window.show_page.assert_called_once_with('profiles')
        window.update_isolation_state.assert_called_once()
        timer.Stop.assert_not_called()
    else:
        assert not event.Cancel
        timer.Stop.assert_called_once()
    if not active:
        window.confirm_profile_close.assert_not_called()


def test_busy_close_stops_worker_and_does_not_open_profile_dialog():
    bridge = SimpleNamespace(abort=Mock())
    window = SimpleNamespace(busy=lambda:True, stop_event=SimpleNamespace(set=Mock()),
        game_worker=SimpleNamespace(bridge=bridge), confirm_profile_close=Mock())
    event = SimpleNamespace(Cancel=False)
    actual_method('before_close', {'window_message':Mock()})(window,None,event)
    assert event.Cancel
    bridge.abort.assert_called_once()
    window.confirm_profile_close.assert_not_called()


def test_legacy_full_order_retains_physical_positions_and_other_settings():
    order=['Legends','Siege Perilous','Origin','Mugen','Pacific']
    config={'shards':order, 'excluded':['Mugen','Pacific'], 'skip_slots':{'Mugen':[1],'Origin':[3]},
            'account_history_id':'unchanged', 'gift_cycle_id':'same-cycle'}
    normalized=normalize_shards(deepcopy(config))
    assert normalized['shards']==['Legends','Origin','Pacific']
    assert normalized['navigation_shards']==order
    assert [physical_index(normalized,n) for n in range(3)]==[0,2,4]
    assert normalized['excluded']==['Pacific'] and normalized['skip_slots']=={'Origin':[3]}
    assert normalized['account_history_id']=='unchanged' and normalized['gift_cycle_id']=='same-cycle'
    assert normalize_shards(deepcopy(normalized))==normalized
    assert config['shards']==order


def test_modified_filtered_order_never_guesses_hidden_row_positions():
    config={'shards':['Origin','Legends'],'navigation_shards':[]}
    normalize_shards(config)
    with pytest.raises(ValueError,match='row positions are unknown'):
        physical_index(config,0)


@pytest.mark.parametrize('name',['Mugen','Siege Perilous','  MUGEN  ','siege perilous'])
def test_unsupported_shards_have_no_creation_or_gift_slots(name):
    assert supported_shards([name])==[]
    assert creation_limit({'account_cap':7},name)==0
    assert occupied_slots_for({'auto_detect_slots':True},name)==[]


def test_arrow_navigation_uses_real_row_after_hidden_shard():
    from cycler_engine import GameWorker
    worker=GameWorker.__new__(GameWorker)
    worker.cfg={'shards':['Legends','Origin'], 'navigation_shards':['Legends','Siege Perilous','Origin'],
                'visible_rows':9,'scroll_reset_clicks':18}
    worker.shard_list_at_top=True
    worker.say=Mock();worker.scroll_shard_arrow=Mock()
    worker.shard_templates=lambda:{'Origin':object()}
    worker.row_point=lambda row:('row',row)
    assert worker.arrow_shard_row_point(1)==('row',2)
    worker.scroll_shard_arrow.assert_not_called()


def test_shard_groups_preserve_physical_rows_and_apply_exclusions():
    from cycler_engine import KNOWN_SHARDS
    from shard_policy import matches_shard_group, normalize_shards, physical_index, run_shards

    asian = ['Arirang', 'Asuka', 'Balhae', 'Formosa', 'Hokuto',
             'Izumo', 'Mizuho', 'Sakura', 'Wakoku', 'Yamato']
    assert [name for name in KNOWN_SHARDS if matches_shard_group(name, 'asian')] == asian
    assert len([name for name in KNOWN_SHARDS if matches_shard_group(name, 'english')]) == 17
    config = normalize_shards({'shards': KNOWN_SHARDS, 'excluded': ['Atlantic', 'Balhae']})
    targets = run_shards(dict(config, shard_group='asian'))
    assert [name for _, name in targets] == [name for name in asian if name != 'Balhae']
    assert all(physical_index(config, index) == KNOWN_SHARDS.index(name) for index, name in targets)
    english = run_shards(dict(config, shard_group='english'))
    assert len(english) == 14
    assert set(english) | set(targets) == set(run_shards(config))
    assert config['navigation_shards'] == KNOWN_SHARDS


def test_donation_uses_only_the_supplied_url(monkeypatch):
    import webbrowser
    from ui_layout import DONATION_URL
    opened=[];monkeypatch.setattr(webbrowser,'open',opened.append)
    actual_method('open_donation_link', {'DONATION_URL':DONATION_URL})(None)
    assert opened==['https://www.paypal.com/donate/?hosted_button_id=T6R4TNGR4UUL6']


def test_restart_retires_routes_without_erasing_progress_or_unknown_submissions(tmp_path,monkeypatch):
    import seeder_engine
    path=tmp_path/'seeder_progress.json'
    original={'profiles':{'main':{'Atlantic':{'created':['Confirmed'], 'completed':[], 'pending':None,
          'name_assignments':{'1':'Confirmed'},'standalone_seed':{'status':'in_progress'}},
          'Pacific':{'created':[], 'completed':[], 'pending':'Unconfirmed'}},
          'other':{'Atlantic':{'created':['Keep'], 'completed':[]}}}}
    path.write_text(json.dumps(original))
    monkeypatch.setattr(seeder_engine,'SEED_PROGRESS_FILE',path)
    worker=type('Worker',(seeder_engine.SeederOperations,),{})()
    worker.cfg = {}
    worker.seed_account_id='main';worker.say=Mock()
    worker.retire_interrupted_routes()
    saved=json.loads(path.read_text())
    assert saved['profiles']['main']['Atlantic']['abandoned_routes']==['Confirmed']
    for key,value in original['profiles']['main']['Atlantic'].items():
        assert saved['profiles']['main']['Atlantic'][key]==value
    assert saved['profiles']['main']['Pacific']==original['profiles']['main']['Pacific']
    assert saved['profiles']['other']==original['profiles']['other']
    assert len(list(tmp_path.glob('*.before-interrupted-routes-*.json')))==1
    worker.retire_interrupted_routes()
    assert json.loads(path.read_text())==saved

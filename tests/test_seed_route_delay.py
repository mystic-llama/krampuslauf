"""Appearance, naming and world-entry behavior in the shared creation path."""
import random
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import cycler_engine
import seeder_engine
from menu_layout import default_points
from seeder_rules import name_hash


@pytest.fixture
def creation_worker(monkeypatch):
    events = []
    record = {'created': [], 'completed': []}
    name = 'Arin Vale'
    status = {'name_sha256': name_hash(name), 'instance_id': 'new-world', 'shard': 'Legends'}
    worker = seeder_engine.SeederOperations()
    worker.cfg = {'points': default_points()}
    worker.check_seed_setup = worker.check = lambda: None
    worker.clock = time.monotonic
    worker.seed_record = lambda shard: ({}, record)
    worker.seed_update = lambda shard, **updates: record.update(updates)
    worker.seed_name_for_slot = lambda *args, **kwargs: name
    worker.seed_new_available = lambda: True
    worker.seed_wait_marker = lambda *args: None
    worker.apply_appearance = lambda: None
    worker.click = lambda *args: None
    worker.seed_visible = lambda marker: True
    worker.say = lambda text: events.append(('log', text))
    worker.sleep = lambda seconds: events.append(('sleep', seconds))
    worker.bridge_status = Mock(side_effect=lambda *args, **kwargs: events.append(('world', status)) or status)
    worker.bridge = SimpleNamespace(request_route_inn=Mock(
        side_effect=lambda *args, **kwargs: events.append(('route', args[0])) or [4403, 1164, 0]))
    worker.logout = Mock(side_effect=lambda: events.append(('logout', None)))
    monkeypatch.setattr(seeder_engine.pg, 'write', Mock())
    return worker, events, record, status


@pytest.mark.parametrize('delay', [None, 0, 17, 120])
def test_configured_pause_precedes_identity_recheck_and_route(creation_worker, delay):
    worker, events, record, status = creation_worker
    if delay is not None:
        worker.cfg['seed_route_delay_seconds'] = delay
    assert worker.seed_one(0, 'Legends')
    expected = 5 if delay is None else delay
    world = next(i for i, event in enumerate(events) if event[0] == 'world')
    pause = events.index(('sleep', expected), world + 1)
    recheck = next(i for i in range(pause + 1, len(events)) if events[i][0] == 'world')
    route = next(i for i, event in enumerate(events) if event[0] == 'route')
    assert world < pause < recheck < route
    assert any(event[0] == 'log' and 'Waiting {} seconds before the inn route'.format(expected) in event[1]
               for event in events)
    assert record['created'] == record['completed'] == ['Arin Vale']


@pytest.mark.parametrize('look,race,sex', [
    ({'race': ['elf'], 'sex': ['male']}, 'elf', 'male'),
    ({'mode': 'random', 'race': ['human', 'elf', 'gargoyle'], 'sex': ['male', 'female']},
     'gargoyle', 'female'),
])
def test_seed_one_applies_appearance_before_reserving_and_typing_a_name(
        creation_worker, monkeypatch, tmp_path, look, race, sex):
    worker, events, record, _ = creation_worker
    monkeypatch.setattr(seeder_engine, 'APP_DIR', tmp_path)
    monkeypatch.setattr(seeder_engine, 'SEED_PROGRESS_FILE', tmp_path / 'seeder_progress.json')
    del worker.apply_appearance
    del worker.seed_name_for_slot
    worker.cfg['appearance'] = {'enabled': True, **look}
    worker._appearance_rng = random.Random(5)
    worker.seed_init('test account')
    worker.click = lambda point: events.append(('click', point))
    seeder_engine.pg.write.side_effect = cycler_engine.Cancelled('Name typed')
    with pytest.raises(cycler_engine.Cancelled, match='Name typed'):
        worker.seed_one(0, 'Legends', already_on_creation=True)
    name = record['name_assignments']['1']
    generator = worker.fantasy_name_generator
    assert generator.matches(name, category=race + '_' + sex)
    assert name.lower() in generator.used_names
    points = worker.cfg['points']
    appearance_applied = next(i for i, (kind, value) in enumerate(events)
                              if kind == 'log' and value.startswith('Appearance selected:'))
    name_reserved = next(i for i, (kind, value) in enumerate(events)
                        if kind == 'log' and value.startswith('FANTASY NAME RESERVED:'))
    assert events.index(('click', points['app_race_' + race])) < appearance_applied
    assert events.index(('click', points['app_sex_' + sex])) < appearance_applied
    assert appearance_applied < name_reserved < events.index(('click', points['seed_name_field']))
    seeder_engine.pg.write.assert_called_once_with(name, interval=.075)


def test_identity_change_during_pause_never_sends_route(creation_worker):
    worker, events, record, status = creation_worker
    worker.cfg['seed_route_delay_seconds'] = 23
    worker.bridge_status.side_effect = [status, dict(status, instance_id='different-client')]
    with pytest.raises(RuntimeError, match='bridge changed after first-login settling'):
        worker.seed_one(0, 'Legends')
    assert ('sleep', 23) in events
    worker.bridge.request_route_inn.assert_not_called()
    worker.logout.assert_not_called()
    assert record['created'] == ['Arin Vale'] and record['completed'] == []


def test_stop_during_world_pause_never_sends_route(creation_worker):
    worker, events, record, status = creation_worker
    worker.cfg['seed_route_delay_seconds'] = 23
    def pause(seconds):
        if seconds == 23:
            raise cycler_engine.Cancelled('Stopped during world-entry pause')
    worker.sleep = pause
    with pytest.raises(cycler_engine.Cancelled, match='world-entry pause'):
        worker.seed_one(0, 'Legends')
    worker.bridge.request_route_inn.assert_not_called()
    worker.logout.assert_not_called()
    assert record['created'] == ['Arin Vale'] and record['completed'] == []


@pytest.mark.parametrize('value', [-1, 121, '5', None, True, 1.5])
def test_invalid_pause_is_rejected_before_start(value):
    cfg = dict(cycler_engine.DEFAULTS, seed_route_delay_seconds=value)
    issues = cycler_engine.test_config(cfg)
    assert any('Before inn route delay' in issue for issue in issues)


@pytest.mark.parametrize('value', [0, 5, 120])
def test_allowed_pause_passes_preflight_validation(value):
    cfg = dict(cycler_engine.DEFAULTS, seed_route_delay_seconds=value)
    assert not any('Before inn route delay' in issue for issue in cycler_engine.test_config(cfg))

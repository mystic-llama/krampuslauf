"""Headless simulated tests for scanner; no mouse or Windows display required."""
import importlib.util
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest.mock import patch

import shard_map

ROOT=Path(__file__).resolve().parents[1]


def scanner_module():
    fake=types.ModuleType('cycler_engine')
    fake.GameWorker=object
    fake.KNOWN_SHARDS=[f'Shard{i}' for i in range(27)]
    fake.APP_DIR=Path(tempfile.gettempdir())
    fake.selected_window=lambda ignored:None
    spec=importlib.util.spec_from_file_location('headless_scanner',ROOT/'shard_scanner.py')
    module=importlib.util.module_from_spec(spec)
    with patch.dict('sys.modules',{'cycler_engine':fake}):
        spec.loader.exec_module(module)
    return module


class Clock:
    def __init__(self):self.tick=0
    def now(self):
        self.tick+=0.9
        return self.tick


class FakeScanner:
    def __init__(self, name, misses=0, menu='characters'):
        self.cfg={'visible_rows':9,'row_spacing':25,
                  'points':{'scroll_down':[200,300], 'first_row':[100,100], 'back':[500,500]}}
        self.window_title='test'
        self.current='servers'
        self.title=None
        self.menu=menu
        self.name=name
        self.misses=misses
        self.shard_clicks=0
        self.down_clicks=0
        self.messages=[]

    def clock(self):return time.monotonic()
    def check(self):pass
    def state(self):return self.current
    def say(self,msg):self.messages.append(msg)
    def sleep(self,t):pass
    def _visible_shard(self):return self.title
    def shard_row_strip(self,row):
        self.pictured_rows=getattr(self,'pictured_rows',[])+[row]
        return 'picture'
    def save_shard_template(self,name,strip):
        self.learned=getattr(self,'learned',[])+[(name,strip)]

    def click(self,xy,**kwargs):
        if list(xy)==[200,300]:
            self.down_clicks+=1
        elif list(xy)==[500,500]:
            self.current='servers'
            self.title=None
        else:
            self.shard_clicks+=1
            if self.shard_clicks>self.misses:
                self.current=self.menu
                self.title=self.name


class ResumableScanTests(unittest.TestCase):
    def setUp(self):
        self.mod=scanner_module()
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'shard_map.json'
        self.cfg={'visible_rows':9,'row_spacing':25}
        self.clock=Clock()
        self.time_patch=patch.object(self.mod.time,'monotonic',side_effect=self.clock.now)
        self.time_patch.start()
        self.addCleanup(self.time_patch.stop)
        self.zone_patch=patch.object(shard_map,'timezone_key',return_value='Test Zone')
        self.zone_patch.start()
        self.addCleanup(self.zone_patch.stop)
        self.path_patch=patch.object(self.mod,'MAP_FILE',self.path)
        self.path_patch.start()
        self.addCleanup(self.path_patch.stop)

    def create(self,name,misses=0,menu='characters'):
        obj=type('SimulatedScanner',(FakeScanner,self.mod.ShardScanner),{})(name,misses,menu)
        return obj

    def test_missed_click_is_retried_and_saved(self):
        worker=self.create('Shard0',misses=1)
        names=worker.scan(1)
        self.assertEqual(names,['Shard0'])
        self.assertEqual(worker.shard_clicks,2)
        self.assertEqual(shard_map.load_map(self.path,self.cfg,require_complete=False)['shards'],['Shard0'])
        self.assertEqual(worker.learned,[('Shard0','picture')])

    def test_after_three_unregistered_clicks_checkpoint_is_not_advanced(self):
        worker=self.create('Shard0',misses=10)
        with self.assertRaisesRegex(RuntimeError,'after 3 attempts'):
            worker.scan(1)
        self.assertEqual(worker.shard_clicks,3)
        self.assertIsNone(shard_map.load_map(self.path,self.cfg,require_complete=False))

    def test_empty_shard_creation_screen_accepted_by_verified_title(self):
        worker=self.create('Shard0',menu='unknown')
        names=worker.scan(1)
        self.assertEqual(names,['Shard0'])
        self.assertEqual(worker.shard_clicks,1)
        self.assertEqual(worker.current,'servers')

    def test_resume_at_row_23_not_row_1(self):
        shard_map.save_map(self.path,self.cfg,[f'Shard{i}' for i in range(22)],complete=False)
        worker=self.create('Shard22')
        names=worker.scan(23,resume=True)
        self.assertEqual(len(names),23)
        self.assertEqual(names[-1],'Shard22')
        self.assertEqual(worker.shard_clicks,1)
        self.assertEqual(worker.down_clicks,14) # index 22 - 8 visible offset

    def test_duplicate_name_fails_closed_and_keeps_prior_rows(self):
        shard_map.save_map(self.path,self.cfg,['Shard0'],complete=False)
        worker=self.create('Shard0')
        with self.assertRaisesRegex(RuntimeError,'Duplicate shard'):
            worker.scan(2,resume=True)
        self.assertEqual(shard_map.load_map(self.path,self.cfg,require_complete=False)['shards'],['Shard0'])


if __name__=='__main__':unittest.main()

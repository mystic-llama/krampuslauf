"""Pure tests for shard-map persistence and Seeder safety rules."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import shard_map
from scan_layout import row_for_index
from seeder_rules import generated_name, name_hash
from recovery_rules import occupied_slots_for


class ShardScanTests(unittest.TestCase):
    def test_top_nine_require_zero_scroll(self):
        for index in range(9):self.assertEqual((index,0),row_for_index(index,9))
        self.assertEqual((8,1),row_for_index(9,9))
        self.assertEqual((8,18),row_for_index(26,9))

    def test_maps_persist_across_timezone_changes(self):
        config={'visible_rows':9,'row_spacing':25}
        names=['Shard '+str(i) for i in range(27)]
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'shard_map.json'
            with patch.object(shard_map,'timezone_key',return_value='Eastern Standard Time'):
                shard_map.save_map(path,config,names,complete=True)
                self.assertEqual(names,shard_map.load_map(path,config)['shards'])
            with patch.object(shard_map,'timezone_key',return_value='Pacific Standard Time'):
                self.assertIsNone(shard_map.load_map(path,config))
                shard_map.save_map(path,config,['Other Shard'],complete=True)
                self.assertEqual(['Other Shard'],shard_map.load_map(path,config)['shards'])
            with patch.object(shard_map,'timezone_key',return_value='Eastern Standard Time'):
                self.assertEqual(names,shard_map.load_map(path,config)['shards'])
                self.assertIsNone(shard_map.load_map(path,{'visible_rows':8,'row_spacing':25}))

    def test_incomplete_map_not_usable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'map.json'
            with patch.object(shard_map,'timezone_key',return_value='Test Zone'):
                shard_map.save_map(path,{'visible_rows':9,'row_spacing':25},['Legends'],complete=False)
                self.assertIsNone(shard_map.load_map(path,{'visible_rows':9,'row_spacing':25}))
                self.assertEqual(['Legends'],shard_map.load_map(path,{'visible_rows':9,'row_spacing':25},require_complete=False)['shards'])


class SeederLogicTests(unittest.TestCase):
    def test_account_cap_and_pvp(self):
        for n in (5,6,7):
            cfg={'account_cap':n}
            self.assertEqual(list(range(1,n+1)),occupied_slots_for(cfg,'Atlantic'))
            self.assertEqual([],occupied_slots_for(cfg,'Mugen'))
            self.assertEqual([],occupied_slots_for(cfg,'Siege Perilous'))
        with self.assertRaises(ValueError):occupied_slots_for({'account_cap':5,'occupied_slots':{'Atlantic':[1,6]}},'Atlantic')

    def test_name_is_deterministic_and_noncredential(self):
        from seeder_rules import SHARD_ABBREVIATIONS
        self.assertEqual(len(SHARD_ABBREVIATIONS), 28)  # 27 official + Isumo alias
        x=generated_name('Llama','Account A',0,0,shard='Legends')
        y=generated_name('Llama','Account B',0,0,shard='Legends')
        self.assertEqual(x,y)  # account ID is intentionally not included
        self.assertEqual(x,'Llama LEG a')
        self.assertEqual(generated_name('Llama','',1,1,shard='Atlantic'),'Llama ATL b')
        self.assertEqual(generated_name('Llama','',2,0,shard='Lake Superior'),'Llama LKS a')
        self.assertLessEqual(len(x),16)
        self.assertEqual(name_hash(' LLAMA LEG1 '),name_hash('llama leg1'))
        with self.assertRaises(ValueError):
            generated_name('AnExtremelyLongPrefix','',0,0,shard='Legends')
        with self.assertRaises(ValueError):
            generated_name('Llama','',0,0,shard='Unknown Shard')
        with self.assertRaises(ValueError):
            generated_name('Llama','',0,7,shard='Atlantic')

    def test_auto_slots_and_manual_skips(self):
        cfg={'auto_detect_slots':True, 'account_cap':5, 'skip_slots':{'Atlantic':[1,3,5]}}
        self.assertEqual(occupied_slots_for(cfg,'Atlantic'),[2,4,6,7])
        self.assertEqual(occupied_slots_for(cfg,'Great Lakes'),list(range(1,8)))
        self.assertEqual(occupied_slots_for(cfg,'Mugen'),[])


if __name__=='__main__':unittest.main()

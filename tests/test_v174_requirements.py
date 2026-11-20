"""Native-display-independent regression tests for the Krampuslauf 1.7.4 UI contract."""
import ast
from pathlib import Path
import unittest
from seeder_rules import generated_name, SHARD_ABBREVIATIONS, shard_abbreviation
from recovery_rules import occupied_slots_for
ROOT=Path(__file__).resolve().parents[1]
GUI=(ROOT/'Krampuslauf.py').read_text(encoding='utf8')
ENGINE=(ROOT/'cycler_engine.py').read_text(encoding='utf8')

class Krampuslauf174Tests(unittest.TestCase):
    def test_every_shard_abbreviation_from_request(self):
        expected={
           'Legends':'LEG','Atlantic':'ATL','Lake Superior':'LKS','Great Lakes':'GRL',
           'Chesapeake':'CHS','Catskills':'CAT','Siege Perilous':'SGP','Origin':'ORG',
           'Pacific':'PAC','Sonoma':'SON','Lake Austin':'LKA','Baja':'BAJ',
           'Napa Valley':'NPV','Drachenfels':'DRC','Europa':'EUR','Oceania':'OCN',
           'Mugen':'MUG','Wakoku':'WAK','Hokuto':'HOK','Formosa':'FOR',
           'Izumo':'IZU','Mizuho':'MIZ','Yamato':'YAM','Asuka':'ASU',
           'Arirang':'ARI','Balhae':'BAL','Sakura':'SAK'}
        self.assertEqual({k:v for k,v in SHARD_ABBREVIATIONS.items() if k!='Isumo'},expected)
        self.assertEqual(shard_abbreviation('Isumo'),'IZU')
        for shard,code in expected.items():
            self.assertEqual(generated_name('Llama','secret',0,0,shard=shard),f'Llama {code} a')
            self.assertEqual(generated_name('Llama','other',20,6,shard=shard),f'Llama {code} g')

    def test_gift_tab_does_not_require_account_code(self):
        from ui_layout import LAYOUTS
        home = LAYOUTS['gift']
        self.assertIn('start_run', [s.get('action') for s in home])
        self.assertIn('new_gift_cycle', [s.get('action') for s in home])
        self.assertNotIn('account_field', [s.get('ref') for s in home])
        self.assertIn('slots_field', [s.get('ref') for s in home])
        self.assertIn('account_field', [s.get('ref') for s in LAYOUTS['seeder']])
        self.assertNotIn('self.event_field', GUI)
        self.assertIn('gift_cycle_id', GUI)

    def test_warning_enter_is_marker_guarded(self):
        s=ENGINE[ENGINE.index('    def acknowledge_warning('):ENGINE.index('    def recover_empty_slot(')]
        self.assertIn('observed != expected',s)
        self.assertIn('self.press("enter")',s)
        self.assertNotIn('self.click(',s)

    def test_normal_gift_slots_need_no_occupied_rule(self):
        cfg={'auto_detect_slots':True,'account_cap':5,'skip_slots':{'Atlantic':[1,2]}}
        self.assertEqual(occupied_slots_for(cfg,'Atlantic'),[3,4,5,6,7])
        self.assertEqual(occupied_slots_for(cfg,'Siege Perilous'),[])

    def test_matching_bridge_directory(self):
        paths=(ROOT/'app_paths.py').read_text(encoding='utf8')
        self.assertIn("APP_FOLDER = 'Krampuslauf'", paths)
        self.assertIn('UOGiftMonkey', paths)
        bridge=(ROOT/'krampuslauf_bridge.py').read_text(encoding='utf8')
        self.assertIn('"Krampuslauf"', bridge)
        self.assertNotIn('UOGiftMonkey', bridge)
        for source in ('cycler_engine.py','bridge_protocol.py'):
            data=(ROOT/source).read_text(encoding='utf8')
            self.assertIn('app_dir()', data)
            self.assertNotIn('UOGiftMonkey', data)

    def test_name_format_kept_and_typing_test_retired(self):
        self.assertIn("self.cfg['name_format_version'] = 'shard_letter_spaced_v1'",GUI)
        self.assertNotIn('pg.write(sample', GUI)
        self.assertNotIn('Name typing not user-tested', (ROOT/'seeder_engine.py').read_text(encoding='utf8'))

if __name__=='__main__': unittest.main()

import unittest
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from recovery_rules import occupied_slots_for


class OccupiedSlotTests(unittest.TestCase):
    def test_default_production(self):
        self.assertEqual(occupied_slots_for({}, 'Atlantic'), list(range(1,8)))

    def test_one_character_veteran_shards(self):
        self.assertEqual(occupied_slots_for({}, 'Siege Perilous'), [])
        self.assertEqual(occupied_slots_for({}, 'Mugen'), [])
        self.assertEqual(occupied_slots_for({'occupied_slots': {'Mugen':[1,2,3]}},'Mugen'), [])

    def test_gaps_and_old_caps(self):
        cfg={'occupied_slots':{'Atlantic':[1,2,4,6],'Lake Superior':5}}
        self.assertEqual(occupied_slots_for(cfg,'Atlantic'),[1,2,4,6])
        self.assertEqual(occupied_slots_for(cfg,'Lake Superior'),[1,2,3,4,5])

    def test_reject_invalid_rules(self):
        for bad in ([0,1], [1,8], ['1'], [1.5]):
            with self.assertRaises(ValueError):
                occupied_slots_for({'occupied_slots': {'Atlantic':bad}}, 'Atlantic')


class PromptSafetyStructureTests(unittest.TestCase):
    def test_confirmation_requires_exact_marker(self):
        engine = (ROOT / 'cycler_engine.py').read_text()
        begin = engine.index('    def acknowledge_warning(')
        end = engine.index('    def recover_empty_slot(', begin)
        body = engine[begin:end]
        self.assertIn('observed != expected', body)
        self.assertIn('self.press("enter")', body)
        self.assertNotIn('self.click(point)', body)


if __name__ == '__main__':
    unittest.main()

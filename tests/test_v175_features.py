"""Display-independent checks for v1.7.5; actual WinForms requires Windows."""
import ast
from pathlib import Path
import unittest
from seeder_rules import generated_name

ROOT=Path(__file__).resolve().parents[1]
GUI=(ROOT/'Krampuslauf.py').read_text(encoding='utf-8')
RE=(ROOT/'krampuslauf_bridge.py').read_text(encoding='utf-8')
ENGINE=(ROOT/'cycler_engine.py').read_text(encoding='utf-8')
PROTOCOL=(ROOT/'bridge_protocol.py').read_text(encoding='utf-8')

class V175Tests(unittest.TestCase):
    def test_tabs_in_requested_order(self):
        from ui_layout import NAVIGATION
        self.assertEqual([name for name, _ in NAVIGATION],
                         ['Setup', 'Automation', 'Help / Status'])
    def test_client_window_shared_from_calibration(self):
        from ui_layout import LAYOUTS
        locations = [key for key, page in LAYOUTS.items() for s in page if s.get('ref') == 'game_pick']
        self.assertEqual(locations, ['client'])
    def test_three_seconds_and_fixed_nine(self):
        self.assertIn('if not 3 <= int(config.get("post_logout_seconds", 7)) <= 60',ENGINE)
        self.assertIn('"visible_rows"] = 9',GUI)
        self.assertNotIn('self.visible_rows = self.numeric(',GUI)
    def test_mini_activity_compact_only_for_runs(self):
        self.assertIn('class ActivityWindow(Form):',GUI)
        self.assertIn('self.run_job(worker.run, compact=True)',GUI)
        self.assertIn('self.run_job(worker.run_seeder, compact=True)',GUI)
        self.assertIn('def restore_full_window(self):',GUI)
        self.assertIn('self.activity_window.status.Text = data',GUI)
    def test_gui_no_longer_requests_gump_cleanup_but_bridge_stays_compatible(self):
        self.assertNotIn("'tidy_gumps'",PROTOCOL)
        self.assertNotIn('cleanup_world_gumps',ENGINE)
        # The unchanged 1.7.6 bridge still understands the command; it is just never sent.
        self.assertIn("'tidy_gumps'",RE)
        self.assertIn('Gumps.AllGumpIDs()',RE)
        self.assertIn('Gumps.CloseGump(gumpid)',RE)
        self.assertIn("'name_sha256'",PROTOCOL)
    def test_names_use_letters(self):
        self.assertEqual(generated_name('Llama','',2,4,shard='Lake Superior'), 'Llama LKS e')

if __name__=='__main__':unittest.main()

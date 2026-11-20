"""Cross-platform checks for v1.7.6's persistent history / separate activity UI."""
import tempfile
import unittest
from pathlib import Path

from activity_history import ActivityHistory

ROOT = Path(__file__).resolve().parent.parent
UI = (ROOT / 'Krampuslauf.py').read_text(encoding='utf8')


class ActivityHistoryTests(unittest.TestCase):
    def test_keeps_prior_lines_between_restarts(self):
        with tempfile.TemporaryDirectory() as t:
            path = Path(t) / 'history.log'
            first = ActivityHistory(path)
            first.append('[01:00:00] HALTED: Test error')
            second = ActivityHistory(path)
            self.assertIn('HALTED: Test error', second.tail())

    def test_rotates_and_clears(self):
        with tempfile.TemporaryDirectory() as t:
            path = Path(t) / 'history.log'
            hist = ActivityHistory(path, max_bytes=35, backups=2)
            for line in ['first event', 'second event', 'third event', 'fourth event']:
                hist.append(line)
            self.assertTrue((Path(t) / 'history.log.1').exists())
            hist.clear()
            self.assertFalse(any(Path(t).iterdir()))

    def test_unicode_tail(self):
        with tempfile.TemporaryDirectory() as t:
            path = Path(t) / 'history.log'
            hist = ActivityHistory(path)
            hist.append('Moonglow → inn')
            self.assertIn('→', hist.tail())


class LayoutTests(unittest.TestCase):
    def test_history_tab_removed_but_saved_logs_remain(self):
        from ui_layout import NAVIGATION
        names = [name for name, _ in NAVIGATION]
        self.assertEqual(names, ['Setup', 'Automation', 'Help / Status'])
        self.assertIn('ActivityHistory(APP_DIR / "activity_history.log")', UI)

    def test_no_main_footer_controls(self):
        section = UI.split('def build_ui(self):', 1)[1].split('def add_title_banner(',1)[0]
        self.assertNotIn('label(self, "ACTIVITY"', section)
        self.assertNotIn('button(self, "PAUSE"', section)
        self.assertNotIn('button(self, "STOP"', section)
        self.assertNotIn('self.Controls.Add(self.log)', section)

    def test_halted_run_requires_acknowledgement(self):
        section = UI.split('elif kind == "done":',1)[1].split('elif kind == "percent":',1)[0]
        self.assertNotIn('self.restore_full_window()', section)
        self.assertIn('ACKNOWLEDGE / RETURN TO MAIN', section)
        self.assertIn('self.activity_window.Activate()', section)

    def test_both_modes_green(self):
        from ui_layout import LAYOUTS
        starts = {s['action']: s.get('tone') for page in LAYOUTS.values() for s in page if s['kind'] == 'button'}
        self.assertEqual(starts['start_run'], 'start')
        self.assertEqual(starts['start_seeder_run'], 'start')

if __name__ == '__main__':
    unittest.main()

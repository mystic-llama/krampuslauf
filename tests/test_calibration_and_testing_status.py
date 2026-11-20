"""Display-independent source and persistence invariants for v1.7.3."""
import ast
import unittest
from pathlib import Path
import setup_checklist

BASE = Path(__file__).resolve().parents[1]
SOURCE = (BASE / 'Krampuslauf.py').read_text(encoding='utf-8')
MODULE = ast.parse(SOURCE)

def method(name):
    main = next(n for n in MODULE.body if isinstance(n, ast.ClassDef) and n.name=='MainWindow')
    return next(n for n in main.body if isinstance(n, ast.FunctionDef) and n.name==name)

class CalibrationStatusTests(unittest.TestCase):
    def test_no_marker_or_point_calibration_controls_remain(self):
        from ui_layout import LAYOUTS
        specs = [s for page in LAYOUTS.values() for s in page]
        self.assertFalse([s for s in specs if str(s.get('action', '')).startswith('marker:')])
        self.assertFalse([s for s in specs if str(s.get('action', '')).startswith('calibrate_')])
        self.assertFalse([s for s in specs if s.get('source') in ('core_points', 'seed_points')])
        for removed in ('calibrate_marker', 'store_point', 'capture_next_point',
                        'calibrate_seeder_point', 'set_marker_status'):
            self.assertNotIn('def ' + removed + '(', SOURCE)
        self.assertIn('verify_screen', {s.get('action') for s in LAYOUTS['client']})

    def test_all_test_buttons_moved_and_tracked(self):
        from ui_layout import LAYOUTS
        refs = {s.get('ref') for page in LAYOUTS.values() for s in page}
        for key in ('bridge','logout','shard_select','game_cursor','desktop_cursor',
                    'focus_check','last_shard','shard_title'):
            self.assertIn('test_buttons.'+key,refs)
        self.assertNotIn('test_buttons.name_typing', refs)
        self.assertNotIn('def test_seed_name_typing(', SOURCE)
        self.assertIn("self.events.put(('test_passed', key))",ast.get_source_segment(SOURCE,method('mark_test_pass')))
        self.assertIn("'manual_test_passes'",ast.get_source_segment(SOURCE,method('update_test_status')))

    def test_status_is_not_set_by_click_alone(self):
        for name in ('test_probe','test_logout','test_desktop_cursor','test_cursor',
                     'test_last_shard','test_scroll'):
            src=ast.get_source_segment(SOURCE,method(name))
            self.assertIn('self.mark_test_pass',src,name)
        self.assertIn('if data in self.test_buttons:',ast.get_source_segment(SOURCE,method('drain_events')))

    def test_setup_requires_re_elevation_confirmation(self):
        steps=dict(setup_checklist.SETUP_STEPS)
        self.assertNotIn('restart_admin', steps)
        self.assertIn('not is_administrator()', ast.get_source_segment(SOURCE, method('require_setup')))

if __name__=='__main__': unittest.main()

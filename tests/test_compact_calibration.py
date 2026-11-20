"""No Windows dependency: geometry, migration, layout-source safety tests."""
import ast
from pathlib import Path
import tempfile
import unittest

from calibration_math import migrate_calibration, character_slot_point
from razor_paths import find_razor_roots

ROOT = Path(__file__).resolve().parents[1]


class CompactCalibration(unittest.TestCase):
    def test_convert_old_points_to_second_slot(self):
        points = {'char_first': [383, 169], 'char_last': [368, 405],
                  'seed_appearance_next': [500, 430]}
        cfg = migrate_calibration({'points': points})
        self.assertIn('char_second', points)
        self.assertEqual(character_slot_point(points, 1), [383,169])
        self.assertEqual(character_slot_point(points, 7), [368,405])
        self.assertEqual(cfg['points']['seed_next'], [500,430])

    def test_new_character_spacing(self):
        points = {'char_first': [380, 168], 'char_second': [380, 208]}
        self.assertEqual([character_slot_point(points, i) for i in range(1,8)],
                         [[380,168+i*40] for i in range(7)])

    def test_built_in_layout_covers_every_engine_point(self):
        from menu_layout import POINTS
        from cycler_engine import SEED_POINTS
        for key in ('first_row', 'scroll_up', 'scroll_down', 'char_first', 'char_second',
                    'back', 'login_button'):
            self.assertIn(key, POINTS)
        for key, _ in SEED_POINTS:
            self.assertIn(key, POINTS)

    def test_gui_no_blocking_folder_dialog_and_no_extra_controls(self):
        from ui_layout import LAYOUTS
        source = (ROOT/'Krampuslauf.py').read_text(encoding='utf-8')
        ast.parse(source)
        self.assertNotIn('picker.ShowDialog()', source)
        for removed in ('creation', 'world', 'warnings'):
            self.assertNotIn(removed, LAYOUTS)

    def test_bounded_folder_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            good=base/'RazorEnhanced'
            (good/'Profiles').mkdir(parents=True)
            (good/'Backup').mkdir()
            roots=find_razor_roots({'APPDATA':str(base)}, cwd=base/'other')
            self.assertEqual(roots, [good.resolve()])


if __name__ == '__main__': unittest.main()

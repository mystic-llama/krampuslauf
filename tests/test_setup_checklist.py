"""Setup checklist and the one-time data-folder move."""
from pathlib import Path
import ast
import unittest
import setup_checklist

ROOT = Path(__file__).resolve().parents[1]

class SetupChecklistTest(unittest.TestCase):
    def test_incomplete_setup_rejected(self):
        self.assertEqual(5, len(setup_checklist.setup_missing({})))
        self.assertEqual([], setup_checklist.setup_missing({'setup_checklist': {
            key: True for key, _ in setup_checklist.SETUP_STEPS}}))
        self.assertEqual([], setup_checklist.setup_missing({'monkey_setup': {
            key: True for key, _ in setup_checklist.SETUP_STEPS}}))
        self.assertEqual('default', setup_checklist.PROFILE_NAME)
        self.assertEqual('krampuslauf_bridge.py', setup_checklist.BRIDGE_FILE)
        self.assertEqual('1.7.4', setup_checklist.VERSION)
        for key, desc in setup_checklist.SETUP_STEPS:
            all_but = {k: True for k, _ in setup_checklist.SETUP_STEPS if k != key}
            self.assertEqual([desc], setup_checklist.setup_missing({'setup_checklist': all_but}))

    def test_files_and_application_renamed(self):
        self.assertTrue((ROOT/'Krampuslauf.py').is_file())
        self.assertTrue((ROOT/'krampuslauf_bridge.py').is_file())
        self.assertFalse((ROOT/'grunt_bridge.py').exists())
        self.assertFalse((ROOT/'UO_Gift_Grunt.py').exists())
        source = (ROOT/'Krampuslauf.py').read_text(encoding='utf-8')
        from ui_layout import NAVIGATION, VERSION
        self.assertIn('self.Text = "Krampuslauf " + VERSION', source)
        self.assertEqual(VERSION, (ROOT / 'VERSION.txt').read_text().strip())
        self.assertTrue({'Setup', 'Automation'} <= {name for name, _ in NAVIGATION})
        for event in ('prepare_profile_mode','restore_profile_mode','require_setup', 'show_bridge_script'):
            self.assertIn('def '+event, source)
        self.assertIn('krampuslauf_bridge.py', source)
        ast.parse(source)
        ast.parse((ROOT/'krampuslauf_bridge.py').read_text(encoding='utf-8'))

    def test_privacy_and_prior_settings(self):
        source = (ROOT/'Krampuslauf.py').read_text()
        self.assertIn('to_disk["window_title"] = ""', source)
        helper = (ROOT/'profile_isolation.py').read_text()
        self.assertNotIn('shutil.rmtree', helper)
        self.assertIn('RazorEnhanced.NewProfiles', helper)
        self.assertNotIn('RazorEnhanced.password', source)
        self.assertIn('ShellExecuteW', (ROOT/'setup_checklist.py').read_text())

    def test_legacy_data_folder_moves_without_touching_other_directories(self):
        import app_paths
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as temporary:
            base = Path(temporary)
            legacy = base / 'UOGiftMonkey'
            legacy.mkdir()
            (legacy / 'settings.json').write_text('{"appearance_theme": "dark"}', encoding='utf8')
            previous = app_paths.data_root
            app_paths.data_root = lambda: base
            try:
                found = app_paths.migrate_app_data()
            finally:
                app_paths.data_root = previous
            self.assertEqual(found, base / 'Krampuslauf')
            self.assertEqual((found / 'settings.json').read_text(encoding='utf8'), '{"appearance_theme": "dark"}')
            self.assertFalse(legacy.exists())


if __name__ == '__main__': unittest.main()

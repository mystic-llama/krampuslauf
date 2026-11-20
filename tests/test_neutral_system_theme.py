"""Cross-platform tests for the theme-followup patch; native WinForms requires Windows."""
from pathlib import Path
import importlib.util
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('gift_theme_neutral_test', ROOT / 'ui_theme.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class NeutralThemeTests(unittest.TestCase):
    def test_dark_surfaces_are_grayscale_not_navy(self):
        for key in ('bg', 'panel', 'card'):
            rgb = module.palette_for('dark')[key]
            self.assertLessEqual(max(rgb) - min(rgb), 8, (key, rgb))
        self.assertLess(sum(module.DARK['bg']), sum(module.DARK['panel']))
        self.assertLess(sum(module.DARK['panel']), sum(module.DARK['card']))

    def test_steel_blue_is_accent_only(self):
        a = module.DARK['accent']
        self.assertGreater(a[2], a[0])
        self.assertGreater(a[2], a[1])

    def test_explicit_and_system_prefs(self):
        with patch.object(module, 'windows_app_theme', return_value='dark'):
            self.assertEqual(module.resolve_theme('system'), 'dark')
            self.assertEqual(module.resolve_theme('light'), 'light')
        with patch.object(module, 'windows_app_theme', return_value='light'):
            self.assertEqual(module.resolve_theme('system'), 'light')
            self.assertEqual(module.resolve_theme('dark'), 'dark')

    def test_title_bar_code_and_tab_draw_is_optional(self):
        gui = (ROOT / 'Krampuslauf.py').read_text(encoding='utf8')
        self.assertIn('class BorderlessTabHost(Panel):', gui)
        self.assertIn('self.tabs = BorderlessTabHost()', gui)
        self.assertIn('nav.FlatAppearance.BorderSize = 0', gui)
        self.assertIn('self.Shown += apply_caption_on_show', gui)
        self.assertIn("set_windows_dark_caption(sender.Handle, ACTIVE_THEME == 'dark')", gui)

    def test_linux_safe_or_windows_unsupported_titlebar(self):
        self.assertFalse(module.set_windows_dark_caption(0, True))

    def test_town_crier_settings_removed(self):
        for name in ('Krampuslauf.py', 'cycler_engine.py', 'seeder_engine.py', 'native_mouse.py'):
            source = (ROOT / name).read_text(encoding='utf8')
            self.assertNotIn('town_crier', source, name)
            self.assertNotIn('right_click', source, name)
        from ui_layout import LAYOUTS
        self.assertNotIn('world', LAYOUTS)

if __name__ == '__main__':
    unittest.main()

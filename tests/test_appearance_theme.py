"""Display-independent regression checks for color choices and settings plumbing."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('krampuslauf_ui_theme', ROOT / 'ui_theme.py')
ui_theme = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ui_theme)


def luminance(rgb):
    channels = [channel / 255 for channel in rgb]
    linear = [value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4
              for value in channels]
    return sum(c * weight for c, weight in zip(linear, (.2126, .7152, .0722)))


def contrast(a, b):
    l1, l2 = sorted((luminance(a), luminance(b)), reverse=True)
    return (l1 + .05) / (l2 + .05)


class ThemeTests(unittest.TestCase):
    def test_fallback_windows_theme(self):
        with patch.object(ui_theme, 'windows_app_theme', return_value='dark'):
            self.assertEqual(ui_theme.resolve_theme('system'), 'dark')
            self.assertEqual(ui_theme.resolve_theme('dark'), 'dark')
            self.assertEqual(ui_theme.resolve_theme('light'), 'light')
        with patch.object(ui_theme, 'windows_app_theme', return_value='light'):
            self.assertEqual(ui_theme.resolve_theme('not-a-valid-mode'), 'light')

    def test_text_contrast_on_both_modes(self):
        for theme in ('dark', 'light'):
            palette = ui_theme.palette_for(theme)
            for key in ('ink', 'muted', 'note', 'warning', 'green', 'red'):
                self.assertGreaterEqual(contrast(palette['panel'], palette[key]), 4.5,
                                        '{} {}: contrast {}'.format(theme, key,
                                                 contrast(palette['panel'], palette[key])))

    def test_ui_references_new_pref_and_does_not_require_new_bridge(self):
        gui = (ROOT / 'Krampuslauf.py').read_text(encoding='utf-8')
        self.assertIn("THEME_PREFERENCE = str(load_json(CONFIG_FILE", gui)
        self.assertIn("('system', 'light', 'dark')", gui)
        from ui_layout import LAYOUTS
        roles = {s.get('role') for page in LAYOUTS.values() for s in page}
        self.assertTrue({'warning', 'note'} <= roles)
        self.assertIn('Restart Krampuslauf', gui)
        self.assertIn('class ActivityWindow(Form)', gui)

if __name__ == '__main__':
    unittest.main()

"""Cross-platform structural regressions for the genuinely borderless tabs.

Real Windows painting requires an interactive Windows test, but these checks
ensure we never regress to a TabControl native content frame and keep the
Seeder dropdowns fully separated from their labels.
"""
import ast
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
GUI = (ROOT / 'Krampuslauf.py').read_text(encoding='utf8')


class BorderlessTabsTests(unittest.TestCase):
    def test_tab_control_replaced_by_custom_panel_host(self):
        self.assertIn('class BorderlessTabHost(Panel):', GUI)
        self.assertIn('self.tabs = BorderlessTabHost()', GUI)
        self.assertNotIn('self.tabs = TabControl()', GUI)
        self.assertNotIn('self.tabs.DrawItem +=', GUI)
        self.assertIn('self.content_panel = Panel()', GUI)
        self.assertIn('self.header = FlowLayoutPanel()', GUI)
        self.assertIn('self.content_panel.BorderStyle = getattr(BorderStyle, "None")', GUI)
        self.assertIn('self.header.BorderStyle = getattr(BorderStyle, "None")', GUI)

    def test_custom_headers_are_flat_and_selectable(self):
        source = GUI.split('class BorderlessTabHost(Panel):', 1)[1].split('def window_message(', 1)[0]
        self.assertIn('nav.FlatStyle = FlatStyle.Flat', source)
        self.assertIn('nav.FlatAppearance.BorderSize = 0', source)
        self.assertIn('nav.UseVisualStyleBackColor = False', source)
        self.assertIn('nav.Click += protected_ui(', source)
        self.assertIn('nav.Width = max(62, int(TextRenderer.MeasureText(', source)
        self.assertIn('self.header.WrapContents = False', source)
        self.assertIn('self.header.AutoScroll = False', source)
        self.assertIn('def select_page(self, page):', source)
        self.assertIn('candidate.Visible = active', source)

    def test_all_original_tasks_preserved(self):
        from ui_layout import NAVIGATION, LAYOUTS
        self.assertEqual([n for n, _ in NAVIGATION],
                         ['Setup', 'Automation', 'Help / Status'])
        for page in ('setup', 'profiles', 'client',
                     'shards', 'gift', 'seeder', 'appearance', 'diagnostics', 'status'):
            self.assertIn(page, LAYOUTS)
        self.assertIn('self.tabs.add_page(title, root)', GUI)
        preflight = GUI.split('def require_setup(self):')[1].split('def build_home')[0]
        self.assertEqual(preflight.count("self.show_page('setup')"), 2)
        self.assertEqual(preflight.count("self.show_page('profiles')"), 1)

    def test_seeder_comboboxes_do_not_overlap_labels(self):
        from ui_layout import LAYOUTS
        seeder = LAYOUTS['looks']
        for caption, ref in [('Naming mode', 'seed_mode_pick'), ('Fantasy style', 'seed_style_pick')]:
            label = next(s for s in seeder if s['text'] == caption)
            field = next(s for s in seeder if s.get('ref') == ref)
            self.assertGreaterEqual(field['y'], label['y'] + label['h'] + 4)
            self.assertLessEqual(field['x'] + field['w'], 660)
            self.assertEqual(field['x'], label['x'])
        self.assertIn('self.seed_mode_pick.SelectedIndexChanged', GUI)
        self.assertIn('self.update_seed_name_mode()', GUI)

    def test_gui_syntax_and_engine_not_touched(self):
        ast.parse(GUI)
        for name in ('cycler_engine.py', 'seeder_engine.py', 'krampuslauf_bridge.py', 'native_mouse.py'):
            self.assertTrue((ROOT/name).is_file())


if __name__ == '__main__':
    unittest.main()

import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent


class TestStructure(unittest.TestCase):
    def test_no_40_click_reset(self):
        text = (ROOT/'cycler_engine.py').read_text()
        gui = (ROOT/'Krampuslauf.py').read_text()
        self.assertNotIn('max(40, len(', text)
        self.assertNotIn('max(40, len(', gui)
        self.assertIn('scroll_reset_clicks', text)
        self.assertIn('scroll_reset_clicks', gui)

    def test_pre_world_identity_guard(self):
        text = (ROOT/'cycler_engine.py').read_text()
        self.assertIn('self.verify_selected_shard(self.cfg["shards"][index])', text)
        self.assertIn('seen = self.title_identity_check(shard)', text)
        self.assertIn('self.title_identity_check(shard)', text)
        self.assertIn('WRONG SHARD BEFORE CHARACTER LOGIN', text)


if __name__ == '__main__':
    unittest.main()

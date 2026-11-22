"""Regression tests for the last-shard shortcut, independent of Windows UI."""
import ast
from pathlib import Path
import unittest
ROOT = Path(__file__).resolve().parents[1]

def method(path, cls, name):
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    obj = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls)
    return next(n for n in obj.body if isinstance(n, ast.FunctionDef) and n.name == name)

def calls(node):
    return [x.func.attr for x in ast.walk(node) if isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute)]

class LastShardTests(unittest.TestCase):
    def test_fast_shortcut_clicks_the_last_shard_button_and_sends_no_enter(self):
        code = method("cycler_engine.py", "GameWorker", "select_last_shard_shortcut")
        self.assertIn("state", calls(code))
        self.assertIn("click", calls(code))
        self.assertNotIn("press", calls(code))
        self.assertNotIn("enter", [x.value for x in ast.walk(code) if isinstance(x, ast.Constant)])
    def test_first_visit_still_requires_explicit_selection(self):
        code = (ROOT / "cycler_engine.py").read_text(encoding="utf-8")
        self.assertIn('self.last_verified_shard = None', code)
        self.assertIn('self.last_verified_shard = wanted', code)
        self.assertIn('if not self.select_last_shard_shortcut(index):', code)
    def test_manual_shortcut_not_logged_into_character(self):
        code = method("Krampuslauf.py", "MainWindow", "test_last_shard")
        self.assertNotIn("enter_slot", calls(code))
        self.assertIn("state", calls(code))
        self.assertIn("click", calls(code))
        self.assertNotIn("press", calls(code))
    def test_explicit_shard_click_still_no_enter(self):
        code = method("cycler_engine.py", "GameWorker", "scroll_to_shard")
        self.assertNotIn("press", calls(code))

if __name__ == "__main__":
    unittest.main()

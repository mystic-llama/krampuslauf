"""Regression checks for unintended post-shard Enter/character login.

Structural assertions are intentionally independent of Windows, WinForms and the
third-party client, so they can run as part of every public beta build.
"""
import ast
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def get_method(path, cls, method):
    tree = ast.parse((ROOT / path).read_text(encoding='utf-8'))
    klass = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls)
    return next(n for n in klass.body if isinstance(n, ast.FunctionDef) and n.name == method)


def call_names(node):
    result = []
    for x in ast.walk(node):
        if isinstance(x, ast.Call):
            f = x.func
            if isinstance(f, ast.Attribute):
                result.append(f.attr)
    return result


class ShardSelectionSafety(unittest.TestCase):
    def test_engine_never_presses_enter_after_shard_click(self):
        method = get_method('cycler_engine.py', 'GameWorker', 'scroll_to_shard')
        self.assertNotIn('press', call_names(method))
        self.assertIn('state', call_names(method))
        self.assertIn('click', call_names(method))

    def test_gui_shard_test_never_sends_keyboard_or_enters_character(self):
        method = get_method('Krampuslauf.py', 'MainWindow', 'test_scroll')
        names = call_names(method)
        self.assertNotIn('press', names)
        self.assertNotIn('enter_slot', names)
        self.assertIn('state', names)

    def test_manual_test_has_explicit_reset_bypass(self):
        method = get_method('Krampuslauf.py', 'MainWindow', 'test_scroll')
        vars_assigned = {
            node.id for node in ast.walk(method) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
        }
        self.assertIn('skip_up_reset', vars_assigned)


if __name__ == '__main__':
    unittest.main()

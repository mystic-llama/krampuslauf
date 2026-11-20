"""Focused RE bridge gump cleanup tests without importing RE or Windows."""
import ast
import types
from pathlib import Path
import unittest
import time

SOURCE = (Path(__file__).resolve().parents[1] / 'krampuslauf_bridge.py').read_text()
node = next(x for x in ast.parse(SOURCE).body if isinstance(x, ast.FunctionDef) and x.name == 'tidy_gumps')
namespace = {}
exec(compile(ast.Module(body=[node], type_ignores=[]), '<gump-test>', 'exec'), namespace)

class MockGumps:
    def __init__(self):
        self.closed=[]
    def AllGumpIDs(self):
        return [400, 401, 402]
    def GetGumpText(self, ident):
        return {400:['Ultima Online Publish 124: Shardfall'], 401:['Runebook'], 402:['Journal']}[ident]
    def CloseGump(self, ident):
        self.closed.append(int(ident))

class GumpCleaning(unittest.TestCase):
    def run_case(self, mode):
        gumps=MockGumps()
        backpack=types.SimpleNamespace(Serial=3456)
        player=types.SimpleNamespace(Connected=True, Backpack=backpack)
        used=[]
        namespace.update({
            'Gumps':gumps, 'Player':player,
            'name_digest':lambda:'a'*64,
            'read_json':lambda path:{'run_id':'b'*32},
            'valid_session':lambda data, now: True,
            'SESSION':'fake-session','time':time,
            'Items':types.SimpleNamespace(UseItem=lambda serial:used.append(serial)),
            'Misc':types.SimpleNamespace(Pause=lambda n:None)
        })
        closed=namespace['tidy_gumps']({'mode':mode,'name_sha256':'a'*64,'run_id':'b'*32})
        self.assertEqual(used,[3456])
        return closed
    def test_town_crier_only(self):
        self.assertEqual(self.run_case('town_crier'), [400])
    def test_advanced_close_all(self):
        self.assertEqual(self.run_case('all'), [400,401,402])
    def test_wrong_character_fails_closed(self):
        namespace.update({'Player':types.SimpleNamespace(Connected=True), 'name_digest':lambda:'a'*64})
        with self.assertRaisesRegex(RuntimeError,'Character changed'):
            namespace['tidy_gumps']({'mode':'town_crier','name_sha256':'z'*64})

if __name__ == '__main__':unittest.main()

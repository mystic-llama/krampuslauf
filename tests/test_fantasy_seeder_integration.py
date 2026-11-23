"""Cross-run fantasy-name reservations without Windows, RE, or a live client."""
import ast
import json
import re
import tempfile
import unittest
from pathlib import Path

from fantasy_name_generator import FantasyNameGenerator, is_valid_name, STYLES
from seeder_rules import generated_name, account_token, shard_abbreviation

ROOT = Path(__file__).resolve().parents[1]
tree = ast.parse((ROOT / 'seeder_engine.py').read_text(encoding='utf-8'))
klass = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'SeederOperations')
methods = [n for n in klass.body if isinstance(n, ast.FunctionDef) and n.name in (
    'seed_init', '_fantasy_generator', 'seed_name_for_slot', 'seed_record', 'seed_update')]
assert len(methods) == 5
class SeedNotReady(RuntimeError):
    pass

def load_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except FileNotFoundError:
        return default

def atomic_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data), encoding='utf-8')

class FantasySeederTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        module = ast.Module(body=[ast.ClassDef(name='SeederOps', bases=[], keywords=[],
                              body=methods, decorator_list=[])], type_ignores=[])
        ns = dict(APP_DIR=self.folder, SEED_PROGRESS_FILE=self.folder/'seeder_progress.json',
                  load_json=load_json, atomic_json=atomic_json, FantasyNameGenerator=FantasyNameGenerator,
                  STYLES=STYLES, is_valid_fantasy_name=is_valid_name,
                  SeedNotReady=SeedNotReady, generated_name=generated_name,
                  account_token=account_token, shard_abbreviation=shard_abbreviation, re=re)
        exec(compile(ast.fix_missing_locations(module), '<seeder-name-methods>', 'exec'), ns)
        self.cls = ns['SeederOps']
    def new_worker(self, mode='fantasy', style='mixed', user='local session'):
        obj = self.cls()
        obj.cfg = dict(seed_naming_mode=mode, seed_fantasy_style=style,
                       seed_name_prefix='Llama')
        obj.messages = []
        obj.say = obj.messages.append
        obj.seed_init(user)
        return obj
    def test_default_format_unchanged(self):
        w = self.new_worker(mode='convention')
        self.assertEqual(w.seed_name_for_slot('Catskills', 0, 1), 'Llama CAT b')
        self.assertFalse((self.folder/'used_fantasy_names.json').exists())
    def test_preview_does_not_reserve_and_name_is_persisted_before_typing(self):
        w = self.new_worker()
        self.assertIsNone(w.seed_name_for_slot('Catskills', 0, 1, assign=False))
        self.assertFalse((self.folder/'used_fantasy_names.json').exists())
        name = w.seed_name_for_slot('Catskills', 0, 1, assign=True)
        self.assertTrue(is_valid_name(name))
        self.assertEqual(w.seed_record('Catskills')[1]['name_assignments']['2'], name)
        self.assertIn(name.lower(), load_json(self.folder/'used_fantasy_names.json', {})['names'])
        self.assertEqual(w.seed_name_for_slot('Catskills', 0, 1, assign=True), name)
    def test_restarted_process_reuses_name_not_a_new_random_one(self):
        w = self.new_worker()
        name = w.seed_name_for_slot('Catskills', 0, 1, assign=True)
        w.seed_update('Catskills', pending=name)
        reboot = self.new_worker()
        self.assertEqual(reboot.seed_name_for_slot('Catskills', 0, 1, assign=False), name)
        self.assertEqual(reboot.seed_name_for_slot('Catskills', 0, 1, assign=True), name)
        self.assertEqual(reboot.seed_record('Catskills')[1]['pending'], name)
    def test_resume_uses_new_style_for_unsubmitted_slots_on_the_same_shard(self):
        w = self.new_worker(style='single')
        created = w.seed_name_for_slot('Catskills', 0, 0, assign=True)
        old_reservation = w.seed_name_for_slot('Catskills', 0, 1, assign=True)
        w.seed_update('Catskills', created=[created], completed=[created], assigned_name_style='single')

        resumed = self.new_worker(style='full')
        self.assertEqual(resumed.seed_name_for_slot('Catskills', 0, 0), created)
        self.assertIsNone(resumed.seed_name_for_slot('Catskills', 0, 1))
        new_name = resumed.seed_name_for_slot('Catskills', 0, 1, assign=True)
        self.assertEqual(len(new_name.split()), 2)
        self.assertIn(old_reservation.lower(), resumed.fantasy_name_generator.used_names)
        record = resumed.seed_record('Catskills')[1]
        self.assertEqual(record['created'], [created])
        self.assertEqual(record['name_assignments'], {'1': created, '2': new_name})

    def test_naming_mode_change_preserves_a_pending_name_and_allows_new_slots(self):
        w = self.new_worker(style='single')
        pending = w.seed_name_for_slot('Catskills', 0, 1, assign=True)
        w.seed_update('Catskills', pending=pending)
        resumed = self.new_worker(mode='convention')
        self.assertEqual(resumed.seed_name_for_slot('Catskills', 0, 1), pending)
        self.assertEqual(resumed.seed_name_for_slot('Catskills', 0, 2), 'Llama CAT c')
        self.assertEqual(resumed.seed_record('Catskills')[1]['pending'], pending)

    def test_unsubmitted_name_is_replaced_when_the_new_race_uses_a_different_pool(self):
        worker = self.new_worker(style='single')
        worker.seed_update('Catskills', name_assignments={'1': 'Aelar', '2': 'Aerin'},
                           created=['Aerin'], completed=['Aerin'])
        gargoyle = {'race': 'gargoyle', 'sex': 'male'}
        name = worker.seed_name_for_slot('Catskills', 0, 0, assign=True, choice=gargoyle)
        self.assertNotEqual(name, 'Aelar')
        self.assertTrue(worker.fantasy_name_generator.matches(name, category='gargoyle_male'))
        self.assertIn('aelar', worker.fantasy_name_generator.used_names)
        self.assertEqual(worker.seed_name_for_slot('Catskills', 0, 0, assign=True, choice=gargoyle), name)
        self.assertEqual(worker.seed_name_for_slot('Catskills', 0, 1, assign=True, choice=gargoyle), 'Aerin')

    def test_previously_reserved_name_with_a_blocked_fragment_is_replaced(self):
        worker = self.new_worker(style='full')
        worker.seed_update('Catskills', name_assignments={'1': 'Shitha Rowan'})
        name = worker.seed_name_for_slot('Catskills', 0, 0, assign=True,
                                         choice={'race': 'human', 'sex': 'female'})
        self.assertNotEqual(name, 'Shitha Rowan')
        self.assertTrue(worker.fantasy_name_generator.matches(name, style='full', category='human_female'))
        self.assertIn('shitha rowan', worker.fantasy_name_generator.used_names)

    def test_unconfirmed_convention_name_gets_a_different_name_for_the_same_slot(self):
        worker = self.new_worker(mode='convention')
        name = worker.seed_name_for_slot('Catskills', 0, 0)
        worker.seed_update('Catskills', unconfirmed_creations=[name],
                           name_assignments={'2': 'Llama CAT b'})
        worker.cfg['seed_fantasy_style'] = 'single'
        worker.fantasy_name_generator = None
        replacement = worker.seed_name_for_slot('Catskills', 0, 0, assign=True)
        self.assertNotEqual(replacement, name)
        self.assertEqual(worker.seed_name_for_slot('Catskills', 0, 0, assign=True), replacement)
        self.assertEqual(worker.seed_name_for_slot('Catskills', 0, 1), 'Llama CAT b')

    def test_legacy_convention_name_is_kept_when_combined_run_changes_to_fantasy(self):
        w = self.new_worker(mode='convention')
        created = 'Former CAT b'
        w.seed_update('Catskills', created=[created], completed=[created],
                      combined_shard={'status': 'in_progress', 'next_slot': 2})
        resumed = self.new_worker(style='full')
        self.assertEqual(resumed.seed_name_for_slot('Catskills', 0, 1), created)
        self.assertEqual(len(resumed.seed_name_for_slot('Catskills', 0, 2, assign=True).split()), 2)
    def test_different_slots_and_accounts_get_distinct_names(self):
        w = self.new_worker(style='full')
        names = [w.seed_name_for_slot('Catskills', 0, n, assign=True) for n in range(6)]
        other = self.new_worker(style='mixed', user='another history')
        names += [other.seed_name_for_slot('Catskills', 0, n, assign=True) for n in range(6)]
        self.assertEqual(len(names), len(set(n.lower() for n in names)))
        self.assertTrue(all(is_valid_name(n) for n in names))
    def test_recovered_ledger_reserves_names_after_history_file_lost(self):
        w = self.new_worker(style='full')
        saved = w.seed_name_for_slot('Catskills', 0, 1, assign=True)
        (self.folder/'used_fantasy_names.json').unlink()
        new = self.new_worker(style='full', user='another account')
        name = new.seed_name_for_slot('Mugen', 1, 0, assign=True)
        self.assertNotEqual(name.lower(), saved.lower())
        self.assertIn(saved.lower(), new.fantasy_name_generator.used_names)
if __name__ == '__main__':
    unittest.main()


def test_seeder_routes_each_race_and_sex_to_its_library():
    from fantasy_name_generator import CATEGORIES, NAME_LIBRARIES
    case = FantasySeederTests()
    case.setUp()
    try:
        for category in CATEGORIES:
            worker = case.new_worker(style='single', user=category)
            race, sex = category.split('_')
            result = worker.seed_name_for_slot('Atlantic', 0, 0, assign=True,
                                              choice={'race': race, 'sex': sex})
            library = NAME_LIBRARIES[category]
            pool = set(library['curated']) | {a+b for a in library['first_syll']
                                             for b in library['last_syll']}
            assert result.casefold() in {n.casefold() for n in pool}
            assert worker.seed_name_for_slot('Atlantic', 0, 0) == result
    finally:
        case.doCleanups()

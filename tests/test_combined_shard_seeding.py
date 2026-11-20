"""No display required: exercise the production combined-mode methods."""
import ast
import tempfile
import threading
import unittest
from pathlib import Path
from seeder_rules import generated_name
from recovery_rules import PVP_SHARDS

ROOT = Path(__file__).resolve().parents[1]
source = ast.parse((ROOT / 'seeder_engine.py').read_text(encoding='utf-8'))
klass = next(n for n in source.body if isinstance(n, ast.ClassDef) and n.name == 'SeederOperations')
methods = [n for n in klass.body if isinstance(n, ast.FunctionDef) and n.name in ('combined_shard_status','complete_combined_shard')]
assert len(methods) == 2
cls = ast.ClassDef(name='CombinedMethodTarget', bases=[], keywords=[], body=methods, decorator_list=[])
ns = {'PVP_SHARDS': PVP_SHARDS, 'generated_name':generated_name}
exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])), '<combined-from-seeder>', 'exec'), ns)

class Harness(ns['CombinedMethodTarget']):
    def __init__(self, shard='Catskills', cap=7, available=None):
        self.cfg={'account_cap': cap, 'seed_name_prefix':'Llama', 'gift_cycle_id':'test-cycle'}
        self.seed_nickname='local history'
        self.shard=shard
        self.saved={}
        self.actions=[]
        self.notices=[]
        self.availability_iter=iter(available or [])
        self.stop=threading.Event()
        self.raise_on_slot=None
    def check_seed_setup(self): pass
    def check(self): pass
    def say(self,message): self.notices.append(message)
    def sleep(self,*args): pass
    def seed_record(self,shard): return None, self.saved.setdefault(shard,{'pending':None,'created':[],'completed':[]})
    def seed_update(self,shard,**kwargs):
        _, rec=self.seed_record(shard)
        rec.update(kwargs)
    def reach_characters(self,index):
        self.actions.append(('reach',index))
        return 'characters'
    def title_identity_check(self,shard,**kwargs): self.actions.append(('title',shard))
    def seed_new_available(self):
        result=next(self.availability_iter, True)
        self.actions.append(('new',result))
        return result
    def refresh_seeded_roster(self,shard): pass
    def seed_one(self,index,shard,already_on_creation=False,slot_number=None):
        if slot_number==self.raise_on_slot: raise RuntimeError('Simulated route interrupted')
        name=generated_name('Llama','ignored',index,slot_number-1,shard=shard)
        self.actions.append(('create',slot_number,already_on_creation,name))
        rec=self.saved.setdefault(shard,{'pending':None,'created':[],'completed':[]})
        rec['created'].append(name)
        rec['completed'].append(name)
        return True

class CombinedShardSeedingTests(unittest.TestCase):
    def test_partly_populated_shard_keeps_seeder_until_cap(self):
        h=Harness(cap=7)
        self.assertTrue(h.complete_combined_shard(0,'Catskills',2))
        self.assertEqual([(a[1],a[3]) for a in h.actions if a[0]=='create'],
                         [(2,'Llama CAT b'),(3,'Llama CAT c'),(4,'Llama CAT d'),
                          (5,'Llama CAT e'),(6,'Llama CAT f'),(7,'Llama CAT g')])
        self.assertEqual(h.saved['Catskills']['combined_shard']['status'],'complete')
        self.assertEqual(h.saved['Catskills']['combined_shard']['next_slot'],8)

    def test_five_slot_account_ends_without_a_seventh_attempt(self):
        h=Harness(cap=5)
        h.complete_combined_shard(0,'Catskills',2)
        self.assertEqual([a[1] for a in h.actions if a[0]=='create'],[2,3,4,5])

    def test_old_cap_without_new_button_ends_at_detected_limit(self):
        h=Harness(cap=7,available=[True,True,True,False,False,False])
        h.complete_combined_shard(0,'Catskills',2)
        self.assertEqual([a[1] for a in h.actions if a[0]=='create'],[2,3,4])
        self.assertEqual(h.saved['Catskills']['combined_shard']['reason'],
                         'new_button_absent_after_three_checks')

    def test_unsupported_shard_never_starts_creation(self):
        h=Harness(shard='Mugen',cap=7)
        h.complete_combined_shard(0,'Mugen',1,on_creation=True)
        self.assertEqual([a for a in h.actions if a[0]=='create'],
                         [])
        self.assertEqual([a for a in h.actions if a[0]=='reach'],[])

    def test_route_failure_is_persisted_and_resume_skips_completed(self):
        h=Harness(cap=5)
        h.raise_on_slot=3
        with self.assertRaisesRegex(RuntimeError,'Simulated route'):
            h.complete_combined_shard(0,'Catskills',2)
        self.assertEqual(h.saved['Catskills']['combined_shard']['next_slot'],3)
        self.assertEqual(h.saved['Catskills']['combined_shard']['status'],'in_progress')
        h.raise_on_slot=None
        h.actions.clear()
        h.complete_combined_shard(0,'Catskills',2)
        self.assertEqual([a[1] for a in h.actions if a[0]=='create'],[3,4,5])
        self.assertEqual(h.saved['Catskills']['combined_shard']['status'],'complete')

    def test_pending_creation_blocks_resume_and_cannot_mark_complete(self):
        h=Harness(cap=5)
        h.seed_update('Catskills',pending='Llama CAT b')
        with self.assertRaisesRegex(RuntimeError,'PENDING'):
            h.complete_combined_shard(0,'Catskills',2)
        self.assertEqual(h.saved['Catskills']['combined_shard']['status'],'in_progress')
        self.assertFalse([a for a in h.actions if a[0]=='create'])

    def test_restart_keeps_created_character_and_skips_abandoned_route(self):
        h = Harness(cap=5)
        name = generated_name('Llama', 'ignored', 0, 1, shard='Catskills')
        h.seed_update('Catskills', created=[name], completed=[], abandoned_routes=[name],
                      combined_shard={'cycle_id': 'test-cycle', 'status': 'in_progress',
                                      'next_slot': 2, 'cap': 5})
        self.assertTrue(h.complete_combined_shard(0, 'Catskills', 2))
        self.assertEqual([a[1] for a in h.actions if a[0] == 'create'], [3, 4, 5])
        self.assertEqual(h.saved['Catskills']['created'].count(name), 1)
        self.assertNotIn(name, h.saved['Catskills']['completed'])
        self.assertEqual(h.saved['Catskills']['combined_shard']['status'], 'complete')

    def test_previous_cycle_checkpoint_does_not_skip_new_cycle(self):
        h = Harness(cap=5)
        h.seed_update('Catskills', combined_shard={'cycle_id': 'previous-cycle',
                                                 'status': 'complete', 'next_slot': 6})
        self.assertEqual(h.combined_shard_status('Catskills'), {})
        h.complete_combined_shard(0, 'Catskills', 2)
        self.assertEqual([a[1] for a in h.actions if a[0] == 'create'], [2, 3, 4, 5])
        self.assertEqual(h.saved['Catskills']['combined_shard']['cycle_id'], 'test-cycle')

    def test_already_completed_shard_is_not_created_twice(self):
        h=Harness(cap=7)
        h.seed_update('Catskills',combined_shard={'cycle_id':'test-cycle','status':'complete','next_slot':8})
        h.complete_combined_shard(0,'Catskills',2)
        self.assertEqual(h.actions,[])

if __name__ == '__main__':unittest.main()

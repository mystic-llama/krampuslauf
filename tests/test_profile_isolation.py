import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import profile_isolation as pi


EXAMPLE = [
    {'Name':'default','Last':False,'Players':[{'PlayerName':'Tester','PlayerSerial':14}], 'Custom':{'x':1}},
    {'Name':'important main','Last':True,'Players':[{'PlayerName':'Main','PlayerSerial':998}]},
    {'Name':'unused profile','Last':False,'Players':[]},
]


class IsolationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)/'RazorEnhanced'
        self.app = Path(self.tmp.name)/'local_appdata'
        (self.root/'Profiles'/'default').mkdir(parents=True)
        (self.root/'Profiles'/'important main').mkdir(parents=True)
        (self.root/'Backup').mkdir(parents=True)
        self.p = self.root/'Profiles'/pi.REGISTRY
        self.b = self.root/'Backup'/pi.REGISTRY
        self.original = json.dumps(EXAMPLE, indent=2).encode('utf-8')
        self.p.write_bytes(self.original)
        self.b.write_bytes(self.original + b'\n')  # preserve divergent backup formatting exactly
        self.boriginal = self.b.read_bytes()
        self.shards = self.root/'Profiles'/'RazorEnhanced.shards'
        self.password = self.root/'Profiles'/'RazorEnhanced.password'
        self.shards.write_bytes(b'keep launcher unchanged')
        self.password.write_bytes(b'private credential data - never read')
        self.sbackup = self.shards.read_bytes()
        self.pbackup = self.password.read_bytes()
        self.closed = patch.object(pi, 'ensure_closed', lambda: None)
        self.closed.start()

    def tearDown(self):
        self.closed.stop()
        self.tmp.cleanup()

    def test_non_destructive_round_trip(self):
        info = pi.prepare(self.root, self.app)
        self.assertTrue(info['active'])
        self.assertEqual(3, info['profiles'])
        self.assertEqual(2, info['links'])
        self.assertEqual(self.p.read_bytes(), self.b.read_bytes())
        data = json.loads(self.p.read_bytes())
        self.assertEqual([x['Name'] for x in data], [x['Name'] for x in EXAMPLE])
        self.assertEqual([x['Last'] for x in data], [True, False, False])
        self.assertTrue(all(x['Players'] == [] for x in data))
        self.assertEqual(data[0]['Custom'], {'x':1})
        self.assertEqual(self.pbackup, self.password.read_bytes())
        self.assertEqual(self.sbackup, self.shards.read_bytes())
        self.assertTrue((self.root/'Profiles'/'important main').is_dir())
        with self.assertRaises(pi.IsolationError):
            pi.prepare(self.root, self.app)
        done = pi.restore(self.app)
        self.assertFalse(done['active'])
        self.assertEqual(self.p.read_bytes(), self.original)
        self.assertEqual(self.b.read_bytes(), self.boriginal)
        self.assertFalse((self.app / pi.ACTIVE_MANIFEST).exists())
        self.assertEqual(len(list((self.app / pi.RECOVERY_DIR).glob('*/RESTORED.json'))), 1)
        # Repeat a session normally, don't overwrite prior backups.
        self.assertTrue(pi.prepare(self.root, self.app)['active'])
        self.assertEqual(len(list((self.app / pi.RECOVERY_DIR).iterdir())), 2)

    def test_changed_temporary_requires_explicit_confirmation(self):
        pi.prepare(self.root, self.app)
        self.p.write_text(self.p.read_text() + '  ', encoding='utf-8')
        self.assertEqual('modified', pi.session_status(self.app)['states'][0])
        with self.assertRaises(pi.IsolationError):
            pi.restore(self.app)
        self.assertEqual(self.b.read_bytes(), self.b.read_bytes())
        pi.restore(self.app, allow_modified=True)
        self.assertEqual(self.p.read_bytes(), self.original)
        self.assertEqual(self.b.read_bytes(), self.boriginal)

    def test_partial_transaction_is_recoverable(self):
        original_atomic = pi._atomic_bytes
        def fail_second(p, data):
            if Path(p) == self.b:
                raise OSError('simulated interrupted second write')
            return original_atomic(p, data)
        with patch.object(pi, '_atomic_bytes', side_effect=fail_second):
            with self.assertRaises(OSError):
                pi.prepare(self.root, self.app)
        self.assertEqual(['temporary', 'original'], pi.session_status(self.app)['states'])
        pi.restore(self.app)
        self.assertEqual(self.p.read_bytes(), self.original)
        self.assertEqual(self.b.read_bytes(), self.boriginal)

    def test_missing_backup_registry_restored_to_missing(self):
        self.b.unlink()
        pi.prepare(self.root, self.app)
        self.assertTrue(self.b.is_file())
        pi.restore(self.app)
        self.assertFalse(self.b.exists())
        self.assertEqual(self.p.read_bytes(), self.original)

    def test_unexpected_format_refused_without_modification(self):
        self.p.write_bytes(b'not json')
        with self.assertRaises(pi.IsolationError):
            pi.prepare(self.root, self.app)
        self.assertEqual(self.p.read_bytes(), b'not json')
        self.assertFalse((self.app/pi.ACTIVE_MANIFEST).exists())

    def test_missing_default_refused_without_modification(self):
        self.p.write_text(json.dumps([{'Name':'Other','Players':[],'Last':True}]))
        with self.assertRaises(pi.IsolationError):
            pi.prepare(self.root, self.app)
        self.assertFalse((self.app/pi.ACTIVE_MANIFEST).exists())

    def test_windows_closed_guard(self):
        with patch.object(pi, 'ensure_closed', side_effect=pi.IsolationError('RE is running')):
            with self.assertRaises(pi.IsolationError):
                pi.prepare(self.root, self.app)
        self.assertEqual(self.p.read_bytes(), self.original)

    def test_reject_corrupt_backup_without_partial_restore(self):
        pi.prepare(self.root,self.app)
        session = pi.get_session(self.app)
        Path(session['files'][1]['backup']).write_bytes(b'corrupt')
        old_temp = self.p.read_bytes()
        with self.assertRaises(pi.IsolationError):
            pi.restore(self.app)
        self.assertEqual(self.p.read_bytes(), old_temp)


if __name__ == '__main__': unittest.main()

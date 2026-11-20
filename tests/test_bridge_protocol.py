"""Run with python -m unittest discover -s tests -v; no Windows dependency."""
import tempfile
import threading
import time
import unittest
from pathlib import Path
import bridge_protocol as bp


class BridgeProtocolTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = {n: getattr(bp, n) for n in ('APP_DIR','SESSION','STATUS','COMMAND','ACK')}
        bp.APP_DIR = Path(self.tmp.name)
        for name, filename in (('SESSION','bridge_session.json'),('STATUS','bridge_status.json'),
                               ('COMMAND','bridge_command.json'),('ACK','bridge_ack.json')):
            setattr(bp, name, bp.APP_DIR / filename)

    def tearDown(self):
        for name, value in self.saved.items():
            setattr(bp, name, value)
        self.tmp.cleanup()

    def test_lifecycle_and_current_status(self):
        with bp.BridgeSession() as s:
            self.assertTrue(bp.read_json(bp.SESSION)['enabled'])
            self.assertIsNone(s.get_status())
            now = time.time()
            bp.atomic_write(bp.STATUS, {'protocol':1,'run_id':s.run_id,'instance_id':'newbridge',
                                       'shard':'Lake Superior','connected':True,'seen_at':now,
                                       'started_at':now})
            self.assertEqual(s.wait_status(.4,expected_shard='Lake Superior')['instance_id'],'newbridge')
            self.assertIsNone(s.get_status(minimum_start=now+10))
        self.assertFalse(bp.SESSION.exists())

    def test_reject_stale_or_wrong_session_status(self):
        with bp.BridgeSession() as s:
            now = time.time()
            for run_id, seen in [('wrong', now), (s.run_id, now-100)]:
                bp.atomic_write(bp.STATUS, {'protocol':1,'run_id':run_id,'instance_id':'b',
                                           'shard':'Atlantic','connected':True,'seen_at':seen,
                                           'started_at':now})
                self.assertIsNone(s.get_status())

    def test_logout_waits_for_matching_ack(self):
        with bp.BridgeSession() as s:
            now=time.time()
            status={'protocol':1,'run_id':s.run_id,'instance_id':'b','shard':'Atlantic',
                    'connected':True,'started_at':now,'seen_at':now}
            bp.atomic_write(bp.STATUS,status)
            def fake_bridge():
                end=time.monotonic()+1.5
                while time.monotonic()<end:
                    command=bp.read_json(bp.COMMAND)
                    if command:
                        bp.atomic_write(bp.ACK,{'run_id':s.run_id, 'instance_id':'b',
                                                'command_id': command['command_id'], 'result':'accepted'})
                        return
                    time.sleep(.02)
            t=threading.Thread(target=fake_bridge);t.start()
            self.assertTrue(s.request_logout(status,timeout=1.5))
            t.join(2)

    def test_old_instance_cannot_logout_new_character(self):
        with bp.BridgeSession() as s:
            now=time.time()
            fresh={'protocol':1,'run_id':s.run_id,'instance_id':'new','shard':'Atlantic',
                   'connected':True,'started_at':now,'seen_at':now}
            bp.atomic_write(bp.STATUS,fresh)
            previous=dict(fresh,instance_id='old')
            with self.assertRaisesRegex(RuntimeError,'instance changed'):
                s.request_logout(previous)
            self.assertFalse(bp.COMMAND.exists())

    def test_second_live_gui_session_is_rejected(self):
        with bp.BridgeSession():
            with self.assertRaisesRegex(RuntimeError,'Another active'):
                bp.BridgeSession().start()


if __name__ == '__main__':
    unittest.main()

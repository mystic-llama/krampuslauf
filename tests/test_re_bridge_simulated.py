"""Exercise the actual RE script in CPython with minimal fake .NET/RE APIs.

Only tests IPC behavior, not actual Razor Enhanced or WinForms compatibility.
"""
import builtins
import os
import runpy
import shutil
import sys
import tempfile
import threading
import time
import types
import unittest
import uuid
from pathlib import Path

import bridge_protocol as bp


class SimulatedRETests(unittest.TestCase):
    def test_auto_start_idle_then_requested_disconnect(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        names = ('APP_DIR','SESSION','STATUS','COMMAND','ACK')
        saved = {n: getattr(bp,n) for n in names}
        saved_modules = {n:sys.modules.get(n) for n in ('System', 'System.IO')}
        # Pretend the IronPython System.IO calls use this temporary directory.
        class Env:
            class SpecialFolder:
                LocalApplicationData = 1
            @staticmethod
            def GetFolderPath(which): return str(root.parent)
        class Guid:
            @staticmethod
            def NewGuid():
                return type('G',(),{'ToString': lambda self,fmt:uuid.uuid4().hex})()
        class Directory:
            @staticmethod
            def CreateDirectory(folder): Path(folder).mkdir(parents=True,exist_ok=True)
        class File:
            @staticmethod
            def Exists(path): return Path(path).exists()
            @staticmethod
            def ReadAllText(path): return Path(path).read_text(encoding='utf8')
            @staticmethod
            def WriteAllText(path, data): Path(path).write_text(data,encoding='utf8')
            @staticmethod
            def Copy(src,dst,overwrite): shutil.copyfile(src,dst)
            @staticmethod
            def Delete(path): Path(path).unlink()
        class FakePath:
            @staticmethod
            def Combine(*a): return os.path.join(*a)
        s_mod=types.ModuleType('System');s_mod.Guid=Guid;s_mod.Environment=Env
        io_mod=types.ModuleType('System.IO');io_mod.File=File;io_mod.Directory=Directory;io_mod.Path=FakePath
        sys.modules['System']=s_mod;sys.modules['System.IO']=io_mod
        bp.APP_DIR=root.parent/'Krampuslauf'
        for n, filename in [('SESSION','bridge_session.json'),('STATUS','bridge_status.json'),
                            ('COMMAND','bridge_command.json'),('ACK','bridge_ack.json')]:
            setattr(bp,n,bp.APP_DIR/filename)
        class Player:
            Connected=True
        class Misc:
            disconnected=0
            @staticmethod
            def ShardName(): return 'Lake Superior'
            @staticmethod
            def Pause(ms): time.sleep(min(ms/1000.0,.04))
            @staticmethod
            def Disconnect():
                Misc.disconnected+=1
                Player.Connected=False
        # Do not inject 'basestring': the bridge must run under Python 3 too.
        globals_={'Player':Player,'Misc':Misc}
        script=str(Path(__file__).resolve().parents[1]/'krampuslauf_bridge.py')
        thread=threading.Thread(target=lambda:runpy.run_path(script, init_globals=globals_),daemon=True)
        try:
            thread.start()
            time.sleep(.16)
            self.assertEqual(0,Misc.disconnected, 'AutoStart must be harmless without GUI')
            with bp.BridgeSession() as bridge:
                status=bridge.wait_status(2)
                self.assertIsNotNone(status,'Autostart bridge did not advertise connected status')
                self.assertEqual('Lake Superior',status['shard'])
                self.assertTrue(bridge.request_logout(status,timeout=2.0))
                thread.join(2)
                self.assertEqual(1,Misc.disconnected)
        finally:
            Player.Connected=False
            thread.join(1)
            for n,v in saved.items():setattr(bp,n,v)
            for n,v in saved_modules.items():
                if v is None:sys.modules.pop(n,None)
                else:sys.modules[n]=v
            temp.cleanup()


if __name__ == '__main__': unittest.main()

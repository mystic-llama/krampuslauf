"""Full simulated persistent Razor bridge: route + logout without hotkeys."""
import hashlib
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


class BridgeRouteTest(unittest.TestCase):
    def test_route_then_logout_and_wrong_character_rejected(self):
        tmp=tempfile.TemporaryDirectory()
        root=Path(tmp.name)
        keys=('APP_DIR','SESSION','STATUS','COMMAND','ACK')
        saved={k:getattr(bp,k) for k in keys}
        saved_modules={k:sys.modules.get(k) for k in ('System','System.IO')}
        class Env:
            class SpecialFolder:LocalApplicationData=1
            @staticmethod
            def GetFolderPath(which):return str(root.parent)
        class Guid:
            @staticmethod
            def NewGuid():return type('G',(),{'ToString':lambda self,fmt:uuid.uuid4().hex})()
        class Dir:
            @staticmethod
            def CreateDirectory(path):Path(path).mkdir(parents=True,exist_ok=True)
        class File:
            @staticmethod
            def Exists(path):return Path(path).exists()
            @staticmethod
            def ReadAllText(path):return Path(path).read_text(encoding='utf8')
            @staticmethod
            def WriteAllText(path,data):Path(path).write_text(data,encoding='utf8')
            @staticmethod
            def Copy(src,dst,overwrite):shutil.copyfile(src,dst)
            @staticmethod
            def Delete(path):Path(path).unlink()
        class FakePath:
            @staticmethod
            def Combine(*parts):return os.path.join(*parts)
        s=types.ModuleType('System');s.Guid=Guid;s.Environment=Env
        sio=types.ModuleType('System.IO');sio.File=File;sio.Directory=Dir;sio.Path=FakePath
        sys.modules['System']=s;sys.modules['System.IO']=sio
        bp.APP_DIR=root.parent/'Krampuslauf'
        for key,filename in [('SESSION','bridge_session.json'),('STATUS','bridge_status.json'),
                             ('COMMAND','bridge_command.json'),('ACK','bridge_ack.json')]:
            setattr(bp,key,bp.APP_DIR/filename)
        class Position:
            X=4403;Y=1170;Z=0
        class Player:
            Connected=True; Name='Llama ABC'
        Player.Position=Position()
        class Misc:
            disconnected=0
            @staticmethod
            def ShardName():return 'Lake Superior'
            @staticmethod
            def Pause(ms):time.sleep(.03)
            @staticmethod
            def Disconnect():Misc.disconnected+=1;Player.Connected=False
        class PathFinding:
            calls=[]
            class Route:pass
            @staticmethod
            def Go(route):
                PathFinding.calls.append((route.X,route.Y))
                Player.Position.X,Player.Position.Y=route.X,route.Y
        script=str(Path(__file__).resolve().parents[1]/'krampuslauf_bridge.py')
        th=threading.Thread(target=lambda:runpy.run_path(script,init_globals={
            'Player':Player,'Misc':Misc,'PathFinding':PathFinding}),daemon=True)
        try:
            th.start()
            with bp.BridgeSession() as bridge:
                status=bridge.wait_status(3)
                self.assertIsNotNone(status)
                digest=hashlib.sha256(b'llama abc').hexdigest()
                self.assertEqual(digest,status.get('name_sha256'))
                with self.assertRaises(RuntimeError):
                    bridge.request_route_inn(status,'0'*64,timeout=1)
                pos=bridge.request_route_inn(status,digest,timeout=4)
                self.assertEqual([4403,1164],pos[:2])
                self.assertEqual([(4403,1164)],PathFinding.calls)
                time.sleep(.15)
                fresh=bridge.wait_status(3)
                self.assertIsNotNone(fresh)
                self.assertTrue(bridge.request_logout(fresh,timeout=3))
                th.join(2)
                self.assertEqual(1,Misc.disconnected)
        finally:
            Player.Connected=False
            th.join(1)
            for k,v in saved.items():setattr(bp,k,v)
            for k,v in saved_modules.items():
                if v is None:sys.modules.pop(k,None)
                else:sys.modules[k]=v
            tmp.cleanup()

if __name__=='__main__':unittest.main()

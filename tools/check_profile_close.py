"""Check native close-dialog choices and shard migration with isolated settings."""
import json
import os
from pathlib import Path
import sys
import tempfile


def main():
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    with tempfile.TemporaryDirectory(prefix='krampuslauf-profile-close-') as temporary:
        os.environ['LOCALAPPDATA']=temporary
        data=Path(temporary)/'Krampuslauf';data.mkdir()
        (data/'settings.json').write_text(json.dumps({'shards':['Legends','Siege Perilous','Origin','Mugen','Pacific'],
                 'excluded':['Mugen'],'skip_slots':{'Mugen':[1],'Origin':[2]}}))
        import Krampuslauf as gui
        from System.ComponentModel import CancelEventArgs
        from System.Windows.Forms import Timer, Application
        from System.Drawing import Bitmap, Rectangle
        from System.Drawing.Imaging import ImageFormat
        from account_profiles import new_catalog
        catalog=new_catalog()
        (data/'account_catalog.json').write_text(json.dumps(catalog))
        key=catalog['accounts']['main']['history_id']
        (data/'account_profiles.json').write_text(json.dumps({'profiles':{key:{
            'skip_slots':{'Mugen':[1],'Origin':[2]},'excluded':['Mugen']}}}))
        gui.game_windows=lambda:[]
        Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(False)
        window=gui.MainWindow();window.Show()
        try:
            assert window.cfg['shards']==['Legends','Origin','Pacific']
            assert window.cfg['navigation_shards']==['Legends','Siege Perilous','Origin','Mugen','Pacific']
            assert list(window.test_shard_pick.Items)==['Legends','Origin','Pacific']
            assert list(window.shard_checks.Items)==['Legends','Origin','Pacific']
            assert 'Mugen' not in str(window.shard_text.Text) and 'Siege' not in str(window.shard_text.Text)
            assert window.cfg['skip_slots']=={'Origin':[2]}
            gui.session_status=lambda _: {'active':True}
            window.update_isolation_state=lambda:None
            for choice,should_cancel in [('x',True),('back',True),('enter',True),('close',False)]:
                window.ui_timer.Start()
                timer=Timer();timer.Interval=75
                acted=[]
                def choose(sender,args):
                    for dialog in list(Application.OpenForms):
                        if str(dialog.Text)!='Restore your original profiles':continue
                        timer.Stop()
                        buttons={str(control.Text):control for control in dialog.Controls
                                 if isinstance(control,gui.Button)}
                        if not acted:
                            output=Path(tempfile.gettempdir())/'krampuslauf-expanded-ui'/'profile-close.png'
                            image=Bitmap(dialog.Width,dialog.Height)
                            try:
                                dialog.DrawToBitmap(image,Rectangle(0,0,dialog.Width,dialog.Height))
                                image.Save(str(output),ImageFormat.Png)
                            finally:image.Dispose()
                        acted.append(choice)
                        if choice=='x':dialog.Close()
                        elif choice=='enter':dialog.AcceptButton.PerformClick()
                        else:buttons['Return to Profiles' if choice=='back' else 'Close anyway'].PerformClick()
                        break
                timer.Tick+=choose;timer.Start()
                event=CancelEventArgs()
                try:window.before_close(None,event)
                finally:timer.Stop();timer.Dispose()
                assert acted==[choice]
                assert bool(event.Cancel)==should_cancel,choice
                assert bool(window.ui_timer.Enabled)==should_cancel,choice
                if should_cancel:assert window.pages['profiles'].Visible
            print(json.dumps({'passed':True,'choices':['X keeps app open','Return to Profiles keeps app open',
                         'Enter returns to Profiles','Close anyway permits close'],
                         'shard_migration':'unsupported choices hidden; physical row positions retained'}))
        finally:
            gui.session_status=lambda _: {'active':False}
            window.Close();window.Dispose();Application.Exit()


if __name__=='__main__':main()

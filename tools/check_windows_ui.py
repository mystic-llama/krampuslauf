"""Windows-only visual smoke check; no game input, bridge commands or real settings.

Run: python tools/check_windows_ui.py --output ui-check --theme dark
Repeat with --theme light and Windows display scaling at 100%, 125%, 150%.
The temporary app-data directory is removed when this process exits.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile


def main():
    if os.name != 'nt':
        raise SystemExit('Native WinForms verification requires Windows.')
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='ui-check')
    parser.add_argument('--theme', choices=('dark', 'light'), default='dark')
    args = parser.parse_args()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    with tempfile.TemporaryDirectory(prefix='krampuslauf-ui-check-') as temporary:
        # Set before importing any application module. Never touch real calibration.
        os.environ['LOCALAPPDATA'] = temporary
        data = Path(temporary) / 'Krampuslauf'
        data.mkdir()
        (data / 'settings.json').write_text(json.dumps({'appearance_theme': args.theme}))
        import Krampuslauf as gui
        from System.Drawing import Bitmap, Rectangle, Size
        from System.Drawing.Imaging import ImageFormat
        from System.Windows.Forms import Label, Button, CheckBox, TextFormatFlags
        from ui_layout import LAYOUTS
        gui.game_windows = lambda: []  # do not even enumerate user's client titles
        gui.Application.EnableVisualStyles()
        gui.Application.SetCompatibleTextRenderingDefault(False)
        window = gui.MainWindow()
        issues = []

        def inspect(sender, event):
            try:
                window.ui_timer.Stop()
                for key in LAYOUTS:
                    window.show_page(key)
                    window.PerformLayout()
                    gui.Application.DoEvents()
                    page = window.pages[key]
                    for ctl in page.Controls:
                        r = ctl.Bounds
                        if r.Left < 0 or r.Top < 0 or r.Right > page.ClientSize.Width or r.Bottom > page.ClientSize.Height:
                            issues.append({'page': key, 'control': str(ctl.Name or ctl.Text), 'issue': 'outside page'})
                        if isinstance(ctl, (Label, Button, CheckBox)) and str(ctl.Text):
                            width = int(ctl.ClientSize.Width) - int(ctl.Padding.Horizontal) - (20 if isinstance(ctl, CheckBox) else 0)
                            flags = (TextFormatFlags.WordBreak if isinstance(ctl, Label) or '\n' in str(ctl.Text)
                                     else TextFormatFlags.SingleLine)
                            measured = gui.TextRenderer.MeasureText(str(ctl.Text), ctl.Font, Size(width, 10000), flags)
                            if measured.Height > ctl.ClientSize.Height or measured.Width > width:
                                issues.append({'page': key, 'control': str(ctl.Name or ctl.Text),
                                               'issue': 'text may clip', 'needed': [int(measured.Width), int(measured.Height)],
                                               'available': [width, int(ctl.ClientSize.Height)]})
                    image = Bitmap(window.Width, window.Height)
                    try:
                        window.DrawToBitmap(image, Rectangle(0, 0, window.Width, window.Height))
                        image.Save(str(output / (key + '.png')), ImageFormat.Png)
                    finally:
                        image.Dispose()
                report = dict(theme=args.theme, size=[int(window.Width), int(window.Height)],
                              dpi=int(getattr(window, 'DeviceDpi', 96)), pages=len(LAYOUTS), issues=issues)
                (output / 'ui-report.json').write_text(json.dumps(report, indent=2), encoding='utf8')
            except Exception as exc:
                issues.append({'issue': 'native check failed', 'error': str(exc)})
                (output / 'ui-report.json').write_text(json.dumps({'issues': issues}, indent=2), encoding='utf8')
            finally:
                window.Close()
                gui.Application.Exit()

        window.Shown += inspect
        gui.Application.Run(window)
        print(json.dumps({'output': str(output), 'issues': issues}, indent=2))
        return 1 if issues else 0


if __name__ == '__main__':
    raise SystemExit(main())

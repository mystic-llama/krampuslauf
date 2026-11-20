"""Exercise native palette controls with temporary data and no game input."""
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace


def main():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    output = Path(tempfile.gettempdir()) / 'krampuslauf-palette-check'
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='krampuslauf-palettes-') as temporary:
        os.environ['LOCALAPPDATA'] = temporary
        import Krampuslauf as gui
        import appearance
        from System.Drawing import Bitmap, Rectangle
        from System.Drawing.Imaging import ImageFormat
        gui.game_windows = lambda: []
        gui.Application.EnableVisualStyles()
        gui.Application.SetCompatibleTextRenderingDefault(False)
        window = gui.MainWindow()
        try:
            window.Show()
            window.ui_timer.Stop()
            window.show_page('looks')
            window.app_enabled.Checked = True
            window.app_mode.SelectedIndex = 0
            window.app_checks['sex_male'].Checked = True
            assert 'history' not in window.pages
            assert len(window.color_palettes) == 5
            for race, parts in appearance.COLOR_ASSETS.items():
                window.app_checks['race_' + race].Checked = True
                for part in parts:
                    window.app_palette_pick.SelectedIndex = 1 if part == 'hair' else 2
                    gui.Application.DoEvents()
                    target, control = window.active_palette()
                    assert target == (appearance.COLOR_FIELDS[part], race)
                    assert control.Visible
                    assert sum(bool(c.Visible) for c in window.color_palettes.values()) == 1
                    xs, ys = appearance.COLOR_BOUNDS[race]
                    assert (control.Image.Width, control.Image.Height) == (xs[-1], ys[-1])
                    cols, rows = appearance.COLOR_GRIDS[race]
                    cell = cols * rows - 1
                    x, y = appearance.color_cell_point(race, cell, (0, 0))
                    window.palette_click(target, control, SimpleNamespace(
                        X=round(x * control.Width / xs[-1]), Y=round(y * control.Height / ys[-1])))
                    assert window.cfg['appearance'][target[0]][race] == [cell]
                    bitmap = Bitmap(window.Width, window.Height)
                    try:
                        window.DrawToBitmap(bitmap, Rectangle(0, 0, window.Width, window.Height))
                        bitmap.Save(str(output / (race + '_' + part + '.png')), ImageFormat.Png)
                    finally:
                        bitmap.Dispose()
            window.app_checks['race_elf'].Checked = True
            window.app_palette_pick.SelectedIndex = 2
            assert window.active_palette() == (None, None)
            assert not any(bool(c.Visible) for c in window.color_palettes.values())
            assert 'Elves have no facial hair' in str(window.skin_status.Text)
            window.app_checks['race_gargoyle'].Checked = True
            window.app_checks['sex_female'].Checked = True
            assert window.active_palette() == (None, None)
            # After Random -> Fixed, the retained Male selection must show facial horns.
            window.app_mode.SelectedIndex = 1
            window.app_checks['sex_male'].Checked = True
            window.app_checks['sex_female'].Checked = False
            window.app_checks['sex_female'].Checked = True
            assert window.active_appearance_sex == 'female'
            window.app_mode.SelectedIndex = 0
            assert window.app_checks['sex_male'].Checked
            assert window.active_appearance_sex == 'male'
            assert window.active_palette()[0] == ('facial_color', 'gargoyle')
            window.save_settings()
            saved = json.loads((Path(temporary) / 'Krampuslauf' / 'settings.json').read_text())
            assert saved['appearance']['hair_color'] == {'human': [47], 'elf': [53], 'gargoyle': [17]}
            assert saved['appearance']['facial_color'] == {'human': [47], 'gargoyle': [17]}
            window.active_compact_run = True
            window.log_line('Palette check: Activity logging still works.')
            assert 'Activity logging still works' in str(window.activity_window.log.Text)
            assert 'Activity logging still works' in window.history_store.tail()
            window.active_compact_run = False
        finally:
            window.Close()
            window.Dispose()
            gui.Application.Exit()
    print(json.dumps({'passed': True, 'screenshots': str(output), 'palettes': 5,
                      'checks': ['race-specific images and selection', 'all final cells',
                                 'elf/female facial colours unavailable', 'random-to-fixed sex refresh',
                                 'saved race-specific colours', 'Activity and disk logs without History']}))


if __name__ == '__main__':
    main()

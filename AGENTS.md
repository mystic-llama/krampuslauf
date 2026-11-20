# Agent notes

- Python dependencies install for `python` on PATH. Use Python 3.12 or newer.
- Tests: `python -m pytest tests -q`
- Native UI smoke check (opens and closes a window with temporary app data, no game input):
  `python tools/check_windows_ui.py --theme dark --output "%TEMP%\gm-ui-check-dark"`
  Pre-existing text-clip warnings on Setup, History and Help pages are known.
- Layout preview: `python tools/build_layout_preview.py` (regenerates `Krampuslauf_Layout_Preview.html`).
- Menu automation uses built-in 640 x 480 game-area coordinates (`client_geometry.py`, `menu_layout.py`, `assets/screen_markers/`). Never reintroduce window-relative (`w.left`/`w.top`) coordinates.
- Saved data lives in `%LOCALAPPDATA%\Krampuslauf`. Tests must point `LOCALAPPDATA` at a temporary directory and must not modify a real data folder.

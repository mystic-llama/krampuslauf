"""Optional file-based branding. No image data is embedded in Python source."""
from pathlib import Path
import sys


def artwork_path(filename='logo.png', executable=None, source_dir=None, bundle_dir=None):
    """Prefer editable art beside the EXE; support PyInstaller's bundled assets."""
    source = Path(source_dir) if source_dir else Path(__file__).resolve().parent
    roots = []
    if executable or getattr(sys, 'frozen', False):
        roots.append(Path(executable or sys.executable).resolve().parent)
    roots.append(source)
    bundled = bundle_dir or getattr(sys, '_MEIPASS', None)
    if bundled:
        roots.append(Path(bundled))
    for root in roots:
        path = root / 'assets' / filename
        if path.is_file():
            return path
    return None


def windows_text(value):
    """Native multiline EDIT controls require CRLF, including loaded LF logs."""
    return str(value).replace('\r\n', '\n').replace('\r', '\n').replace('\n', '\r\n')


def artwork_bounds(filename):
    """Visible pixels of editable artwork, without changing the supplied image."""
    from PIL import Image
    path = artwork_path(filename)
    if path is None:
        return None
    with Image.open(path) as image:
        bounds = (image.getchannel('A').point(lambda alpha: 255 if alpha > 16 else 0).getbbox()
                  if image.mode == 'RGBA' else None)
        left, top, right, bottom = bounds or (0, 0, image.width, image.height)
        return left, top, right - left, bottom - top

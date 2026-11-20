"""Bounded Razor data folder discovery; never reads credentials or launcher files.

Avoid shell modal folder pickers, which can hang/hide behind elevated WinForms.
Users may always paste a custom folder path, including a different drive.
"""
import os
import sys
from pathlib import Path


def _is_root(candidate):
    try:
        return candidate.is_dir() and (candidate / 'Profiles').is_dir() and (candidate / 'Backup').is_dir()
    except OSError:
        return False


def find_razor_roots(environ=None, cwd=None):
    environ = os.environ if environ is None else environ
    bases = []
    for key in ('APPDATA', 'LOCALAPPDATA', 'USERPROFILE', 'PROGRAMDATA'):
        if environ.get(key):
            bases.append(Path(environ[key]))
    if environ.get('USERPROFILE'):
        bases.append(Path(environ['USERPROFILE']) / 'Documents')
    bases.append(Path(cwd) if cwd else Path.cwd())
    # Only named/direct child dirs of likely user-data folders; never recursively scan disks.
    candidates = []
    names = ('RazorEnhanced', 'Razor Enhanced', 'RE', 'Razor')
    for b in bases:
        candidates.append(b)
        candidates.extend(b / name for name in names)
        candidates.append(b / 'Data')
        # One level of direct children if the base is an app-specific folder.
        if b.name.lower() in ('razorenhanced', 'razor enhanced'):
            candidates.append(b / 'Data')
    found = []
    seen = set()
    for p in candidates:
        try:
            resolved = p.resolve(strict=False)
            canonical = str(resolved).casefold()
            if canonical not in seen and _is_root(p):
                seen.add(canonical)
                found.append(resolved)
        except (OSError, RuntimeError):
            continue
    return found

"""Krampuslauf's local Razor setup helpers. No game credentials are read."""
import os
import sys
import subprocess

PROFILE_NAME = 'default'
BRIDGE_FILE = 'krampuslauf_bridge.py'
VERSION = '1.7.4'
CHECKLIST_KEY = 'setup_checklist'
LEGACY_CHECKLIST_KEY = 'monkey_setup'
SETUP_STEPS = (
    ('tooltip_delay', 'In Game Options (Paperdoll), set Tooltip delay to 5000 ms'),
    ('default_profile', 'Technical tab: Profiles dropdown shows default, so the bridge stays loaded'),
    ('script', 'Razor Scripting tab: add krampuslauf_bridge.py and enable AutoStart at Login. Do not run the file with desktop Python'),
    ('doors', 'Options tab: Automatically Open Doors is checked'),
    ('passwords', 'Technical tab: Remember passwords is checked (stored by Razor, not Krampuslauf)'),
)


def checklist_from(settings):
    """Saved boxes, including a checklist written by an older release."""
    current = settings.get(CHECKLIST_KEY) if isinstance(settings, dict) else None
    if isinstance(current, dict):
        return dict(current)
    legacy = settings.get(LEGACY_CHECKLIST_KEY) if isinstance(settings, dict) else None
    return dict(legacy) if isinstance(legacy, dict) else {}


def setup_missing(settings):
    values = checklist_from(settings)
    return [caption for key, caption in SETUP_STEPS if not values.get(key, False)]


def is_administrator():
    if os.name != 'nt':
        return False
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def restart_elevated():
    if os.name != 'nt':
        raise RuntimeError('Administrator restart is Windows-only')
    import ctypes
    from pathlib import Path
    if getattr(sys, 'frozen', False):
        executable = str(Path(sys.executable).resolve())
        arguments = subprocess.list2cmdline(sys.argv[1:])
    else:
        executable = str(Path(sys.executable).resolve())
        arguments = subprocess.list2cmdline([str(Path(sys.argv[0]).resolve())] + sys.argv[1:])
    from ctypes import wintypes
    execute = ctypes.windll.shell32.ShellExecuteW
    execute.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR,
                        wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_int]
    execute.restype = ctypes.c_void_p
    result = execute(None, 'runas', executable, arguments, str(Path(executable).parent), 1)
    if int(result or 0) <= 32:
        raise RuntimeError('Windows declined administrator restart (code {}).'.format(int(result or 0)))
    return True

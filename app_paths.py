"""Local application data directory. No account names or credentials.

The folder name is Krampuslauf. A previous install's folder is moved once,
and only when the new folder does not already exist.
"""
import os
import shutil
from pathlib import Path

APP_FOLDER = 'Krampuslauf'
LEGACY_FOLDER = 'UOGiftMonkey'


def data_root():
    return Path(os.environ.get('LOCALAPPDATA', str(Path.home())))


def app_dir():
    return data_root() / APP_FOLDER


def migrate_app_data():
    """Move the previous data folder forward. Never delete the only copy."""
    current = app_dir()
    legacy = data_root() / LEGACY_FOLDER
    try:
        if legacy.exists() and not current.exists():
            legacy.rename(current)
        elif legacy.is_dir() and current.is_dir():
            for item in list(legacy.iterdir()):
                destination = current / item.name
                if not destination.exists():
                    shutil.move(str(item), str(destination))
            if not any(legacy.iterdir()):
                legacy.rmdir()
    except OSError:
        pass
    return current

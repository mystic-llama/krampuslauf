"""Krampuslauf's local Razor setup helpers. No game credentials are read."""
PROFILE_NAME = 'default'
BRIDGE_FILE = 'krampuslauf_bridge.py'
VERSION = '1.7.4'
CHECKLIST_KEY = 'setup_checklist'
LEGACY_CHECKLIST_KEY = 'monkey_setup'
SETUP_STEPS = (
    ('tooltip_delay', 'In Game Options (Paperdoll), turn off tooltips or set Tooltip delay to 5000 ms'),
    ('default_profile', 'Technical tab: Profiles dropdown shows default, so the bridge stays loaded'),
    ('script', 'Razor Scripting tab: add krampuslauf_bridge.py and set it to AutoStart at Login. Do not run the file with desktop Python'),
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

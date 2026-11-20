"""Minimal Windows app color preference reader / accessible Krampuslauf palettes.

No WinForms imports: safe for standalone tests and in the Python.NET EXE.
Themes apply on the next GUI launch, not while a run is active.
"""


def windows_app_theme():
    """Return 'dark' or 'light' using the current user's Windows Apps setting.

    Windows uses separate modes for application windows and the taskbar;
    AppsUseLightTheme is the correct per-user value for this program.
    Registry may be absent until user customizes colors; light is a safe fallback.
    """
    try:
        import winreg
        key = r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize'
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as handle:
            value, _ = winreg.QueryValueEx(handle, 'AppsUseLightTheme')
        return 'dark' if int(value) == 0 else 'light'
    except (OSError, ImportError, ValueError, TypeError):
        return 'light'


def resolve_theme(preference='system'):
    mode = str(preference or 'system').strip().lower()
    return mode if mode in ('light', 'dark') else windows_app_theme()


# Neutral Windows-style charcoal surfaces, not the older navy/blue scheme.
# Accent buttons and headings remain steel-blue for recognition and clarity.
DARK = {
    'bg': (26, 27, 29),        # Window chrome / background
    'panel': (38, 39, 42),     # Primary tab content panels
    'card': (53, 55, 59),      # Input fields, inactive buttons, log areas
    'ink': (238, 239, 241),
    'muted': (181, 186, 194),
    'accent': (107, 176, 234),
    'green': (108, 218, 160),
    'red': (255, 139, 146),
    'note': (255, 218, 120),
    'warning': (255, 139, 146),
}
LIGHT = {
    'bg': (248, 250, 253),
    'panel': (240, 244, 249),
    'card': (255, 255, 255),
    'ink': (32, 46, 65),
    'muted': (75, 91, 113),
    'accent': (38, 100, 160),
    'green': (31, 122, 79),
    'red': (176, 42, 57),
    'note': (133, 82, 0),
    'warning': (174, 43, 43),
}


def palette_for(mode):
    return dict(DARK if str(mode).lower() == 'dark' else LIGHT)


def set_windows_dark_caption(dotnet_handle, enabled):
    """Ask DWM to make a standard Windows title bar dark, when supported.

    This is only chrome styling. Unsupported Windows versions and non-Windows
    hosts silently retain their system-provided title bar. Never impacts game
    HWNDs or mouse/keyboard automation.
    """
    try:
        import ctypes
        from ctypes import wintypes
        handle_value = (int(dotnet_handle.ToInt64()) if hasattr(dotnet_handle, 'ToInt64')
                        else int(dotnet_handle))
        if not handle_value:
            return False
        dwm = ctypes.WinDLL('dwmapi')
        fn = dwm.DwmSetWindowAttribute
        fn.argtypes = (wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD)
        fn.restype = ctypes.c_long
        dark = wintypes.BOOL(1 if enabled else 0)
        # 20 is the documented modern Windows attribute. 19 is the legacy
        # pre-Windows-11 identifier used by earlier Windows 10 builds.
        for attr in (20, 19):
            hr = fn(wintypes.HWND(handle_value), attr,
                    ctypes.byref(dark), ctypes.sizeof(dark))
            if hr == 0:
                return True
    except (AttributeError, ImportError, OSError, TypeError, ValueError):
        pass
    return False

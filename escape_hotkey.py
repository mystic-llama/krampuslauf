"""Run-scoped Escape shortcut; no keyboard recording or system-wide mouse lock.

RegisterHotKey owns Escape only while a job is active. MOD_NOREPEAT means a
held key produces one signal. Registration and release happen on one thread.
"""
import ctypes
import os
import threading


def escape_action(paused, stopping):
    return None if stopping else 'stop' if paused else 'pause'


class EscapeHotkey:
    def __init__(self, callback):
        self.callback = callback
        self._ending = threading.Event()
        self._ready = threading.Event()
        self._thread = None
        self.available = False
        self.error = ''

    def start(self):
        if os.name != 'nt':
            self.error = 'Escape shortcut requires Windows.'
            return False
        self._thread = threading.Thread(target=self._run, name='KrampuslaufEscape', daemon=True)
        self._thread.start()
        if not self._ready.wait(1.5):
            self.error = 'Escape shortcut registration timed out.'
            self.close()
            return False
        return self.available

    def _run(self):
        from ctypes import wintypes
        user = ctypes.WinDLL('user32', use_last_error=True)
        user.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
        user.RegisterHotKey.restype = wintypes.BOOL
        user.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
        user.UnregisterHotKey.restype = wintypes.BOOL
        user.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND,
                                     wintypes.UINT, wintypes.UINT, wintypes.UINT]
        user.PeekMessageW.restype = wintypes.BOOL
        registered = False
        try:
            registered = bool(user.RegisterHotKey(None, 0x474D, 0x4000, 0x1B))
            self.available = registered
            if not registered:
                self.error = 'Windows could not reserve Escape (error {}).'.format(ctypes.get_last_error())
            self._ready.set()
            if not registered:
                return
            message = wintypes.MSG()
            while not self._ending.wait(.02):
                while user.PeekMessageW(ctypes.byref(message), None, 0x0312, 0x0312, 1):
                    if message.wParam == 0x474D and not self._ending.is_set():
                        self.callback()
        except Exception as exc:
            self.error = str(exc)
        finally:
            if registered:
                user.UnregisterHotKey(None, 0x474D)
            self.available = False
            self._ready.set()

    def close(self):
        self._ending.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=1)

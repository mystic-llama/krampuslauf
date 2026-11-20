"""Windows desktop cursor diagnostics/input for Krampuslauf.

Uses native Win32 APIs; does not inject into or modify the game process.
Does not unclip/release the cursor. Fails closed if a target cannot be reached.
"""
from __future__ import annotations

import ctypes
import os
import time


class PointerInterrupted(RuntimeError):
    """Pointer could not be verified; callers must pause, never click blindly."""
    def __init__(self, message, clicks_sent=0):
        self.clicks_sent = clicks_sent
        super().__init__(message)

if os.name == "nt":
    from ctypes import wintypes

    class POINT(ctypes.Structure):
        _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

    class RECT(ctypes.Structure):
        _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                    ("right", wintypes.LONG), ("bottom", wintypes.LONG)]

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", ctypes.c_int32), ("dy", ctypes.c_int32),
                    ("mouseData", ctypes.c_uint32), ("dwFlags", ctypes.c_uint32),
                    ("time", ctypes.c_uint32), ("dwExtraInfo", ctypes.c_size_t)]

    class _INPUTUNION(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", ctypes.c_uint32), ("union", _INPUTUNION)]

    _user = ctypes.WinDLL("user32", use_last_error=True)
    _user.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
    _user.GetCursorPos.restype = wintypes.BOOL
    _user.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
    _user.SetCursorPos.restype = wintypes.BOOL
    _user.GetClipCursor.argtypes = [ctypes.POINTER(RECT)]
    _user.GetClipCursor.restype = wintypes.BOOL
    _user.GetSystemMetrics.argtypes = [ctypes.c_int]
    _user.GetSystemMetrics.restype = ctypes.c_int
    _user.SendInput.argtypes = [ctypes.c_uint, ctypes.POINTER(INPUT), ctypes.c_int]
    _user.SendInput.restype = ctypes.c_uint


def _win_only():
    if os.name != "nt":
        raise RuntimeError("Native mouse input is supported only on Windows.")


def cursor_position():
    _win_only()
    pt = POINT()
    if not _user.GetCursorPos(ctypes.byref(pt)):
        raise OSError(ctypes.get_last_error(), "GetCursorPos failed")
    return (int(pt.x), int(pt.y))


def clip_rectangle():
    _win_only()
    rect = RECT()
    if not _user.GetClipCursor(ctypes.byref(rect)):
        raise OSError(ctypes.get_last_error(), "GetClipCursor failed")
    return (int(rect.left), int(rect.top), int(rect.right), int(rect.bottom))


def virtual_desktop():
    _win_only()
    return (_user.GetSystemMetrics(76), _user.GetSystemMetrics(77),
            _user.GetSystemMetrics(78), _user.GetSystemMetrics(79))


def _input_mouse(flags, dx=0, dy=0):
    record = INPUT(type=0, union=_INPUTUNION(mi=MOUSEINPUT(
        dx=dx, dy=dy, mouseData=0, dwFlags=flags, time=0, dwExtraInfo=0)))
    ctypes.set_last_error(0)
    sent = _user.SendInput(1, ctypes.byref(record), ctypes.sizeof(INPUT))
    return (int(sent), int(ctypes.get_last_error()))


def _send_absolute(x, y):
    vx, vy, vw, vh = virtual_desktop()
    if vw < 2 or vh < 2:
        return (0, 0)
    dx = round((x - vx) * 65535 / (vw - 1))
    dy = round((y - vy) * 65535 / (vh - 1))
    return _input_mouse(0x0001 | 0x8000 | 0x4000, dx, dy)


def _close(actual, wanted):
    return abs(actual[0] - wanted[0]) <= 3 and abs(actual[1] - wanted[1]) <= 3


_last_placed = None


def _note_pointer(x, y):
    """Remember when and where this module last moved or clicked the pointer."""
    global _last_placed
    _last_placed = (time.monotonic(), int(round(x)), int(round(y)))


def idle_pointer(seconds):
    """Pointer position if it still rests where we last placed it, for `seconds` or more; else None.

    A pointer the user has moved elsewhere is never reported, so callers never
    fight a person for the mouse.
    """
    placed = _last_placed
    if placed is None or time.monotonic() - placed[0] < seconds:
        return None
    here = cursor_position()
    return here if _close(here, placed[1:]) else None


def move_cursor(x, y, settle=.10):
    """SetCursorPos then SendInput fallback; record evidence if either fails.

    Avoid changing the game's cursor clipping. If it doesn't work, halt before clicks.
    """
    _win_only()
    settle = max(0.0, min(.10, float(settle)))
    x, y = int(round(x)), int(round(y))
    target = (x, y)
    before = cursor_position()
    clip = clip_rectangle()
    desktop = virtual_desktop()
    if not (desktop[0] <= x < desktop[0]+desktop[2] and
            desktop[1] <= y < desktop[1]+desktop[3]):
        raise RuntimeError("Mouse target {} is outside virtual desktop {}".format(target, desktop))
    if not (clip[0] <= x < clip[2] and clip[1] <= y < clip[3]):
        raise RuntimeError("Mouse target {} is outside cursor clipping rectangle {}. "
                           "Check whether the client is confining the mouse.".format(target, clip))
    ctypes.set_last_error(0)
    set_ok = bool(_user.SetCursorPos(x, y))
    set_error = ctypes.get_last_error()
    time.sleep(settle)
    after_set = cursor_position()
    # Notify the game's input queue as well as positioning the desktop pointer.
    # SetCursorPos alone does not establish that the game consumed mouse input.
    input_sent, input_error = _send_absolute(x, y)
    time.sleep(settle)
    final = cursor_position()
    result = {"target": target, "before": before, "after_set": after_set,
              "final": final, "set_ok": set_ok, "set_error": set_error,
              "sendinput_sent": input_sent, "sendinput_error": input_error,
              "clip": clip, "desktop": desktop}
    if not _close(final, target):
        raise PointerInterrupted("Native mouse move failed: {}. "
                           "Try desktop test and compare with game-focused test.".format(result))
    _note_pointer(x, y)
    return result


def _before_click(x, y, before_click=None, clicks_sent=0):
    try:
        if before_click is not None:
            before_click(clicks_sent)
        if not _close(cursor_position(), (int(round(x)), int(round(y)))):
            raise PointerInterrupted('Pointer moved before mouse button DOWN.')
    except PointerInterrupted as exc:
        exc.clicks_sent = clicks_sent
        raise


def click_cursor(x, y, before_click=None):
    """Only click after verifying the native desktop pointer reached the target."""
    evidence = move_cursor(x, y)
    _before_click(x, y, before_click)
    down, down_err = _input_mouse(0x0002)
    time.sleep(.045)
    up, up_err = _input_mouse(0x0004)
    if down != 1 or up != 1:
        raise RuntimeError("Windows SendInput click failed at ({}, {}): down={}/{} up={}/{}".
                           format(x, y, down, down_err, up, up_err))
    _note_pointer(x, y)
    return evidence


def wheel_cursor(x, y, events, gap=.06, before_event=None):
    """Scroll the control under (x, y): one wheel notch per event, events < 0 scroll DOWN.

    The Classic Client counts each wheel event as one list row whatever its
    delta, so one notch is sent per row. The pointer is verified before every
    event; no button is pressed. Returns the number of events sent.
    """
    _win_only()
    events = int(events)
    if events == 0:
        return 0
    delta = (120 if events > 0 else -120) & 0xFFFFFFFF
    move_cursor(x, y)
    sent = 0
    for _ in range(abs(events)):
        try:
            if before_event is not None:
                before_event(sent)
            if not _close(cursor_position(), (int(round(x)), int(round(y)))):
                raise PointerInterrupted('Pointer moved during wheel scrolling.')
        except PointerInterrupted as exc:
            exc.clicks_sent = sent
            raise
        record = INPUT(type=0, union=_INPUTUNION(mi=MOUSEINPUT(
            dx=0, dy=0, mouseData=delta, dwFlags=0x0800, time=0, dwExtraInfo=0)))
        ctypes.set_last_error(0)
        if _user.SendInput(1, ctypes.byref(record), ctypes.sizeof(INPUT)) != 1:
            raise RuntimeError("Windows SendInput wheel failed: {}".format(ctypes.get_last_error()))
        sent += 1
        time.sleep(gap)
    _note_pointer(x, y)
    return sent


def double_click_cursor(x, y, interval=0.11, before_click=None, between_clicks=None):
    """Native Win32 double-click for UO Classic Client character selection.

    Move and verify the cursor once, then send two complete down/up pairs with
    a brief gap.  No keyboard Enter is sent and no extra click is performed
    after the character-selection screen disappears.

    `between_clicks`, if given, is asked just before the second click and must
    return True for it to be sent; otherwise only the first click is sent and
    the result says so (`second_click_skipped`).
    """
    _win_only()
    interval = float(interval)
    if not 0.06 <= interval <= 0.25:
        raise ValueError("Double-click interval must be between 0.06 and 0.25 seconds")
    evidence = move_cursor(x, y)
    for click_index in range(2):
        if click_index == 1 and between_clicks is not None and not between_clicks():
            evidence['second_click_skipped'] = True
            _note_pointer(x, y)
            return evidence
        _before_click(x, y, before_click, clicks_sent=click_index)
        down, down_err = _input_mouse(0x0002)
        if down != 1:
            raise RuntimeError("Windows SendInput left-button DOWN failed: {}/{}".format(down, down_err))
        time.sleep(.045)
        up, up_err = _input_mouse(0x0004)
        if up != 1:
            raise RuntimeError("Windows SendInput left-button UP failed: {}/{}".format(up, up_err))
        if click_index == 0:
            time.sleep(interval)
    _note_pointer(x, y)
    return evidence


def click_cursor_many(x, y, count, interval=.02, before_click=None):
    """Scroll-arrow burst: place once, preserve stop/pause and pointer checks."""
    if type(count) is not int or not 1 <= count <= 100:
        raise ValueError('Click count must be between 1 and 100.')
    evidence = move_cursor(x, y)
    for click_index in range(count):
        _before_click(x, y, before_click, clicks_sent=click_index)
        down, down_err = _input_mouse(0x0002)
        time.sleep(.045)
        up, up_err = _input_mouse(0x0004)
        if down != 1 or up != 1:
            raise RuntimeError('Windows scroll click failed: down={}/{} up={}/{}'.format(
                down, down_err, up, up_err))
        if click_index + 1 < count:
            time.sleep(max(.01, float(interval)))
    evidence['clicks_sent'] = count
    _note_pointer(x, y)
    return evidence

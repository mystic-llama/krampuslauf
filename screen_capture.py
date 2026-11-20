"""Capture exactly one small screen region.

Pillow's ImageGrab.grab(bbox) copies the whole primary screen and crops it
afterwards, which costs about 30 ms however small the region is. This copies
only the requested rectangle from the screen with GDI, and works on any monitor
of the virtual desktop. Images are returned in memory and never saved.
"""
from __future__ import annotations

import ctypes
import os

import cv2
import numpy as np

if os.name == 'nt':
    from ctypes import wintypes

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [('biSize', wintypes.DWORD), ('biWidth', wintypes.LONG), ('biHeight', wintypes.LONG),
                    ('biPlanes', wintypes.WORD), ('biBitCount', wintypes.WORD), ('biCompression', wintypes.DWORD),
                    ('biSizeImage', wintypes.DWORD), ('biXPelsPerMeter', wintypes.LONG),
                    ('biYPelsPerMeter', wintypes.LONG), ('biClrUsed', wintypes.DWORD),
                    ('biClrImportant', wintypes.DWORD)]

    _user32 = ctypes.WinDLL('user32', use_last_error=True)
    _gdi32 = ctypes.WinDLL('gdi32', use_last_error=True)
    _user32.GetDC.argtypes = [wintypes.HWND]
    _user32.GetDC.restype = wintypes.HDC
    _user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    _user32.ReleaseDC.restype = ctypes.c_int
    _gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
    _gdi32.CreateCompatibleDC.restype = wintypes.HDC
    _gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
    _gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
    _gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    _gdi32.SelectObject.restype = wintypes.HGDIOBJ
    _gdi32.BitBlt.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                              wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.DWORD]
    _gdi32.BitBlt.restype = wintypes.BOOL
    _gdi32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
                                 ctypes.c_void_p, ctypes.POINTER(BITMAPINFOHEADER), wintypes.UINT]
    _gdi32.GetDIBits.restype = ctypes.c_int
    _gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    _gdi32.DeleteObject.restype = wintypes.BOOL
    _gdi32.DeleteDC.argtypes = [wintypes.HDC]
    _gdi32.DeleteDC.restype = wintypes.BOOL

SRCCOPY = 0x00CC0020
MAX_PIXELS = 4096 * 4096


def grab_bgra(bbox):
    """(height, width, 4) uint8 BGRA copy of the desktop rectangle (left, top, right, bottom)."""
    if os.name != 'nt':
        raise RuntimeError('Screen capture is available only on Windows.')
    left, top, right, bottom = (int(v) for v in bbox)
    width, height = right - left, bottom - top
    if width < 1 or height < 1 or width * height > MAX_PIXELS:
        raise ValueError('Invalid capture rectangle {}.'.format((left, top, right, bottom)))
    screen = _user32.GetDC(None)
    if not screen:
        raise OSError(ctypes.get_last_error(), 'GetDC failed')
    memory = bitmap = previous = None
    try:
        memory = _gdi32.CreateCompatibleDC(screen)
        bitmap = _gdi32.CreateCompatibleBitmap(screen, width, height)
        if not memory or not bitmap:
            raise OSError(ctypes.get_last_error(), 'Could not create a capture bitmap')
        previous = _gdi32.SelectObject(memory, bitmap)
        if not _gdi32.BitBlt(memory, 0, 0, width, height, screen, left, top, SRCCOPY):
            raise OSError(ctypes.get_last_error(), 'BitBlt failed')
        header = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
        buffer = ctypes.create_string_buffer(width * height * 4)
        if _gdi32.GetDIBits(memory, bitmap, 0, height, buffer, ctypes.byref(header), 0) != height:
            raise OSError(ctypes.get_last_error(), 'GetDIBits failed')
        return np.frombuffer(buffer, np.uint8).reshape(height, width, 4).copy()
    finally:
        if previous:
            _gdi32.SelectObject(memory, previous)
        if bitmap:
            _gdi32.DeleteObject(bitmap)
        if memory:
            _gdi32.DeleteDC(memory)
        _user32.ReleaseDC(None, screen)


def grab_gray(bbox):
    return cv2.cvtColor(grab_bgra(bbox), cv2.COLOR_BGRA2GRAY)


def grab_rgb(bbox):
    return cv2.cvtColor(grab_bgra(bbox), cv2.COLOR_BGRA2RGB)


def grab_bgr(bbox):
    return cv2.cvtColor(grab_bgra(bbox), cv2.COLOR_BGRA2BGR)

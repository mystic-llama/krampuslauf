"""Classic Client game-area geometry for the fixed 640 x 480 pre-world menus.

Login, shard list, character list and creation screens are drawn into a
640 x 480 client area. Built-in points and marker regions use that space.
Windows display scaling stretches the area uniformly (125% -> 800 x 600), so
coordinates are scaled by the measured client width. Window borders and the
title bar are never part of a coordinate.
"""
from __future__ import annotations

import os
from typing import NamedTuple

BASE_WIDTH, BASE_HEIGHT = 640, 480
# Non-uniform stretching means the area is not a scaled menu screen.
ASPECT_TOLERANCE = 0.02


def menu_scale(width, height):
    """Uniform scale of a 640 x 480 menu area, or None (e.g. in-world view)."""
    width, height = int(width), int(height)
    if width < BASE_WIDTH // 2 or height < BASE_HEIGHT // 2:
        return None
    sx, sy = width / BASE_WIDTH, height / BASE_HEIGHT
    if abs(sx - sy) > ASPECT_TOLERANCE * max(sx, sy):
        return None
    return sx


class GameArea(NamedTuple):
    left: int
    top: int
    width: int
    height: int

    @property
    def scale(self):
        return menu_scale(self.width, self.height)

    def require_scale(self):
        scale = self.scale
        if scale is None:
            raise RuntimeError(
                'Classic Client game area is {}x{}, not a 640x480 menu screen '
                '(or a uniformly scaled copy). Return the client to a game menu; '
                'no mouse input was sent.'.format(self.width, self.height))
        return scale

    def to_screen(self, x, y):
        """Map a 640 x 480 menu point to desktop pixels; refuse points outside."""
        if not (0 <= float(x) < BASE_WIDTH and 0 <= float(y) < BASE_HEIGHT):
            raise RuntimeError('Menu point ({}, {}) is outside the 640x480 game area.'.format(x, y))
        scale = self.require_scale()
        return (int(round(self.left + float(x) * scale)),
                int(round(self.top + float(y) * scale)))

    def region_to_screen(self, rect, margin=0):
        """Desktop bbox for a 640 x 480 region plus a base-pixel margin, clipped."""
        scale = self.require_scale()
        x0, y0, x1, y1 = (float(v) for v in rect)
        x0, y0 = max(0.0, x0 - margin), max(0.0, y0 - margin)
        x1, y1 = min(float(BASE_WIDTH), x1 + margin), min(float(BASE_HEIGHT), y1 + margin)
        return (int(round(self.left + x0 * scale)), int(round(self.top + y0 * scale)),
                int(round(self.left + x1 * scale)), int(round(self.top + y1 * scale)))


def client_area(hwnd):
    """Desktop position and size of a window's client (game drawing) area."""
    if os.name != 'nt':
        raise RuntimeError('Classic Client geometry is available only on Windows.')
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    rect, origin = wintypes.RECT(), wintypes.POINT()
    if not user32.GetClientRect(wintypes.HWND(int(hwnd)), ctypes.byref(rect)):
        raise RuntimeError('Could not read the Classic Client game area.')
    if not user32.ClientToScreen(wintypes.HWND(int(hwnd)), ctypes.byref(origin)):
        raise RuntimeError('Could not locate the Classic Client game area on screen.')
    return GameArea(int(origin.x), int(origin.y),
                    int(rect.right - rect.left), int(rect.bottom - rect.top))

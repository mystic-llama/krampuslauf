"""Krampuslauf — official Classic Client + Razor Enhanced controller.

The application never requests or stores game usernames/passwords and never
saves screenshots. It compares small regions of the 640 x 480 menu game area
with built-in static marker artwork (assets/screen_markers).

Requires: pyautogui opencv-python pillow pygetwindow psutil
"""
from __future__ import annotations

import hashlib
import json
import os
import queue
import re
import threading
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import pyautogui as pg
import native_mouse
import screen_capture
import shard_rows
import timing_trace
from app_paths import app_dir
from bridge_protocol import BridgeSession
from shard_identity import shard_from_title
from client_geometry import client_area
from ui_assets import artwork_path
from shard_policy import supported_shards, normalize_shards
from menu_layout import MARKER_REGIONS, MARKER_ALTERNATIVES, default_points, marker_path
import pygetwindow as gw
import psutil

if os.name == "nt":
    try:
        import ctypes
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

pg.FAILSAFE = True
pg.PAUSE = .10

APP_DIR = app_dir()
CONFIG_FILE = APP_DIR / "settings.json"
PROGRESS_FILE = APP_DIR / "progress.json"
IDENTITY_PROGRESS_FILE = APP_DIR / "gift_character_identities.json"
ROSTER_CHANGE_FILE = APP_DIR / "gift_roster_changes.json"
ISSUES_FILE = APP_DIR / "issues.json"
SEED_PROGRESS_FILE = APP_DIR / "seeder_progress.json"
# Create an empty timing.enabled file in the data folder to trace step timings.
TIMING_FLAG = APP_DIR / "timing.enabled"
TIMING_LOG = APP_DIR / "timing.log"
TIMED_METHODS = (
    "state", "marker_scores", "seed_visible", "input_context", "pointer_action", "click", "press",
    "sleep", "park_menu_cursor", "park_if_idle", "title_identity_check", "scroll_shard_arrow",
    "read_shard_rows", "wheel_shard_list", "recognized_shard_row_point", "scroll_to_shard",
    "reach_characters", "enter_slot", "bridge_status", "wait_gift", "logout",
    "seed_wait_marker", "seed_new_available", "apply_appearance", "seed_one", "seed_from_empty",
)

# These are the first nine rows in the screenshot that established the layout.
# This is deliberately NOT presented as an authoritative complete shard order.
INITIAL_ORDER = [
    "Legends", "Atlantic", "Lake Superior", "Great Lakes", "Chesapeake",
    "Catskills", "Siege Perilous", "Origin", "Pacific",
]
KNOWN_SHARDS = [
    "Arirang", "Asuka", "Atlantic", "Baja", "Balhae", "Catskills",
    "Chesapeake", "Drachenfels", "Europa", "Formosa", "Great Lakes",
    "Hokuto", "Izumo", "Lake Austin", "Lake Superior", "Legends",
    "Mizuho", "Mugen", "Napa Valley", "Oceania", "Origin", "Pacific",
    "Sakura", "Siege Perilous", "Sonoma", "Wakoku", "Yamato",
]
DEFAULTS = {
    "window_title": "", "shards": supported_shards(INITIAL_ORDER),
    "navigation_shards": list(INITIAL_ORDER),
    "excluded": [], "verified_order": False,
    "points": default_points(), "row_spacing": 25, "visible_rows": 9,
    "gift_wait": 12, "menu_timeout": 150, "world_timeout": 55,
    "match_threshold": .83,
    # Disabled until the user verifies Enter at the shard screen selects the
    # last played shard. No added calibration or credentials are required.
    "fast_last_shard": False,
    # 9 visible, 18 DOWN steps to the last production shard (user-measured).
    # Max UP reset; no more arbitrary 40-click resets.
    "scroll_reset_clicks": 18,
    # See README: configure only occupied character slots for older accounts.
    "occupied_slots": {},  # legacy compatibility, not shown in the primary interface
    "auto_detect_slots": True,
    "skip_slots": {},
    "gift_cycle_id": "",
    "post_logout_seconds": 7,
    "online_cooldown_seconds": 305,
    "sync_retry_seconds": 15,
    "online_retry_limit": 3,
    "require_shard_title": True,
    "account_cap": 7,
    "reserve_transfer_slot": False,
    "create_missing": False,
    "seed_name_prefix": "Llama",
    "seed_naming_mode": "fantasy",  # convention | fantasy
    "seed_profession": "blacksmith",
    "seed_fantasy_style": "mixed",  # single | full | mixed
    "seed_name_input_verified": False,
    "seed_stage_timeout": 35,
    "seed_world_timeout": 100,
    "seed_route_delay_seconds": 5,
    "use_scanned_map": True,

}
SHARD_NAMES_DIR = APP_DIR / "shard_names"
# The client scrolls one row per wheel event; the pointer must be over the rows.
SHARD_WHEEL_POINT = (300, 220)
SHARD_WHEEL_GAP = .06
SHARD_RESET_EVENTS = 24
MAX_LIST_STEPS = 14
# Blank artwork in the top-right of every menu; the pointer rests here when idle.
PARK_POINT = (620, 20)
# A pointer resting this long on a control may bring up a tooltip over a marker.
PARK_IDLE_SECONDS = 4.0
# Minimum match of the hair/facial colour palette picture against the screen.
PALETTE_MATCH = .75
# ...and the largest median colour difference (0-255) allowed at the matched spot.
PALETTE_COLOR_DIFF = 6
# How long the stone panel that matches the Origin error marker may stay up before it
# is reported; the client shows the same panel while it connects.
SYNC_PATIENCE_SECONDS = 30.0
# Gap between the clicks of a double-click, about the speed of a quick human; the
# screen read made before the second click brings the real gap to roughly 0.11 s.
DOUBLE_CLICK_GAP = .09
CORE_MARKERS = ("login", "servers", "characters")
OPTIONAL_MARKERS = ("online_busy", "sync_error", "new_character")
SEED_MARKERS = ("seed_new_button", "seed_appearance", "seed_profession", "seed_city",
                "seed_moonglow_selected")
SEED_POINTS = [
    ("seed_new_button", "New Character button/row"),
    ("seed_name_field", "Character name entry"),
    ("seed_next", "Shared Next / Create button on character creation screens"),
    ("seed_profession_preset", "Profession: stock template"),
    ("seed_city_moonglow", "Starting City: Moonglow"),
]
from recovery_rules import PVP_SHARDS, occupied_slots_for

from calibration_math import character_slot_point


def load_json(path, default):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else default
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def atomic_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(str(temp), str(path))


_WINDOW_CACHE = {"key": None, "hwnd": None}


def game_windows():
    """Only offer official client.exe windows (not browser/ClassicUO)."""
    candidates = []
    if os.name != "nt":
        return candidates
    from ctypes import wintypes
    import ctypes
    GetWindowThreadProcessId = ctypes.windll.user32.GetWindowThreadProcessId
    GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    GetWindowThreadProcessId.restype = wintypes.DWORD
    for w in gw.getAllWindows():
        try:
            if not w.title.strip() or w.width < 400 or w.height < 300:
                continue
            pid = wintypes.DWORD()
            GetWindowThreadProcessId(w._hWnd, ctypes.byref(pid))
            if psutil.Process(pid.value).name().casefold() != "client.exe":
                continue
            candidates.append((w, pid.value))
        except (psutil.Error, OSError, AttributeError):
            continue
    return candidates


def pin_window(hwnd):
    for w, _pid in game_windows():
        if w._hWnd == int(hwnd):
            _WINDOW_CACHE.update(key=w.title, hwnd=w._hWnd)
            return w.title
    raise RuntimeError("Official Classic Client (client.exe) window not found. Start it through Razor Enhanced.")


def selected_window(title):
    """Never silently jump to a different client if the selected HWND disappears."""
    if _WINDOW_CACHE["hwnd"] is not None:
        for w, _pid in game_windows():
            if w._hWnd == _WINDOW_CACHE["hwnd"]:
                return w
        raise RuntimeError("The selected Classic Client window closed; select the game window again.")
    candidates = [w for w, _pid in game_windows() if w.title == title]
    if len(candidates) != 1:
        raise RuntimeError("Select exactly one Classic Client game window using Refresh.")
    _WINDOW_CACHE.update(key=title, hwnd=candidates[0]._hWnd)
    return candidates[0]


def focus_game(title):
    window = selected_window(title)
    if window.isMinimized:
        raise RuntimeError("Restore the Classic Client before running the cycler.")
    active = gw.getActiveWindow()
    if not active or active._hWnd != window._hWnd:
        try:
            window.activate()
        except Exception as exc:
            raise RuntimeError("Could not focus the Classic Client: {}".format(exc))
        time.sleep(.25)
        active = gw.getActiveWindow()
        if not active or active._hWnd != window._hWnd:
            raise RuntimeError("Classic Client did not receive focus; stopping before typing.")
    return window


def game_area(title):
    """Desktop rectangle of the selected client's drawing area (no title bar/borders)."""
    return client_area(selected_window(title)._hWnd)


def point_screen(title, x, y):
    return game_area(title).to_screen(x, y)


def test_config(config):
    issues = []
    if not config.get("window_title"):
        issues.append("Select the official Classic Client window.")
    if not config.get("verified_order"):
        issues.append("Confirm or scan the shard order before running.")
    if not config.get("shards"):
        issues.append("Enter at least one shard in its exact displayed order.")
    for name in CORE_MARKERS:
        if marker_path(name) is None:
            issues.append("Built-in {} screen marker is missing from assets/screen_markers; "
                          "reinstall the complete application folder.".format(name))
    if not set(config.get("excluded", [])) <= set(config.get("shards", [])):
        issues.append("An excluded shard isn't in the ordered list.")
    if len(set(config.get("shards", []))) != len(config.get("shards", [])):
        issues.append("Remove duplicate shard names from the ordered list.")
    for shard in config.get("shards", []):
        try:
            occupied_slots_for(config, shard)
        except ValueError as exc:
            issues.append(str(exc))
    if int(config.get("account_cap", 7)) not in (5, 6, 7):
        issues.append("Choose an account character-slot capacity: 5, 6, or 7.")
    if not 3 <= int(config.get("post_logout_seconds", 7)) <= 60:
        issues.append("Post-logout delay must be from 3 to 60 seconds.")
    route_delay = config.get("seed_route_delay_seconds", 5)
    if type(route_delay) is not int or not 0 <= route_delay <= 120:
        issues.append("Before inn route delay must be a whole number from 0 to 120 seconds.")
    if not 300 <= int(config.get("online_cooldown_seconds", 305)) <= 900:
        issues.append("Online cooldown must be 300–900 seconds.")
    if not 0 <= int(config.get("scroll_reset_clicks", 18)) <= 40:
        issues.append("Scroll reset clicks must be from 0 to 40.")
    if int(config.get("visible_rows", 9)) != 9 or int(config.get("row_spacing", 0)) < 1:
        issues.append("Shard row/spacing setting invalid.")
    return issues


class Cancelled(Exception):
    pass


class SyncScreen(Exception):
    pass


class OnlineBusy(Exception):
    pass


class EmptySlot(Exception):
    pass


class ShardRowsNotFound(RuntimeError):
    """Reading the shard list could not place a shard; callers may use the arrows."""


def shard_template_dirs():
    """Learned name images first, then any shipped with the application."""
    dirs = [SHARD_NAMES_DIR]
    shipped = marker_path("login")
    if shipped is not None:
        dirs.append(shipped.parent.parent / "shard_names")
    return dirs


class GameWorker:
    def __init__(self, config, nickname, event_label, stop, emit, pause=None):
        config = normalize_shards(dict(config))
        self.cfg = config
        self.mode = event_label
        self.stop = stop
        self.pause = pause or threading.Event()
        self.emit = emit
        self.window_title = config["window_title"]
        self.selected_index = None
        # Persist across each logout/login within this RUN, not across app restarts.
        # Only the RE bridge can establish which shard was actually entered.
        self.last_verified_shard = None
        self.fast_shortcut_failed = set()
        self.shard_list_at_top = False
        # The Classic Client sometimes ignores Enter after a modal login error.
        # This flag is armed ONLY when a positively recognized warning returns
        # to the account login screen. Normal logins still use Enter.
        self.login_after_warning = False
        self.bridge = None
        self.last_bridge = None
        # Nickname is used only in memory to derive a pseudonymous progress ID.
        self.progress_id = hashlib.sha256(
            ((config.get('account_history_id') if event_label == 'seeder' and config.get('account_history_id') else nickname).strip().casefold() + "\x00" + event_label.strip().casefold()).encode("utf-8")
        ).hexdigest()[:20]
        self.completed = self._read_progress()
        # Persist anonymous character-name fingerprints rather than assuming a
        # character is permanently associated with the same menu row.
        self.gift_identity_history = self._read_identity_progress()
        self.roster_sensitive_shards = set(load_json(ROSTER_CHANGE_FILE, {}).get(self.progress_id, []))
        self.seeded_character_hashes = {}
        self.markers = {}
        self.seed_markers = {}
        self.regions = dict(MARKER_REGIONS)
        self._scaled_templates = {}
        self._shard_templates = None
        self._learn_candidate = None
        self._row_source = None
        for name in CORE_MARKERS + OPTIONAL_MARKERS:
            im = self._load_marker(name)
            if im is None:
                raise RuntimeError("Built-in {} screen marker is missing or unreadable in assets/screen_markers. "
                                   "Reinstall the complete application folder.".format(name))
            self.markers[name] = im
        # Seed buttons/stage labels are checked only on demand, never allowed to
        # override ordinary login/shard/character screen state recognition.
        for name in SEED_MARKERS:
            im = self._load_marker(name)
            if im is not None:
                self.seed_markers[name] = im
        if TIMING_FLAG.exists() and "PYTEST_CURRENT_TEST" not in os.environ:
            timing_trace.install(self, TIMING_LOG, TIMED_METHODS)

    @staticmethod
    def _load_marker(name):
        path = marker_path(name)
        if path is None:
            return None
        im = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if im is None or im.size < 120 or np.std(im) < 5:
            return None
        return im

    def game_area(self):
        return game_area(self.window_title)

    def _template_for(self, name, template, scale):
        """Built-in markers are 100% captures; Windows scaling stretches the client."""
        if abs(scale - 1.0) < .01:
            return template
        key = (name, round(scale, 3))
        if key not in self._scaled_templates:
            h, w = template.shape[:2]
            self._scaled_templates[key] = cv2.resize(
                template, (max(1, round(w * scale)), max(1, round(h * scale))),
                interpolation=cv2.INTER_LINEAR)
        return self._scaled_templates[key]

    @staticmethod
    def menu_frame(area, rects, margin):
        """One in-memory capture covering `rects`: (gray image, desktop (left, top)).

        A screen copy costs about one display refresh however small it is, so
        several markers are cut from one capture. Nothing is saved or sent.
        """
        union = (min(r[0] for r in rects), min(r[1] for r in rects),
                 max(r[2] for r in rects), max(r[3] for r in rects))
        bbox = area.region_to_screen(union, margin)
        return screen_capture.grab_gray(bbox), (bbox[0], bbox[1])

    def marker_score(self, name, template, area=None, margin=12, region=None, frame=None):
        """Match one marker inside its small region of the game area; None if unusable."""
        area = area or self.game_area()
        scale = area.scale
        if scale is None:
            return None
        template = self._template_for(name, template, scale)
        bbox = area.region_to_screen(region if region is not None else self.regions[name], margin)
        if frame is None:
            gray = screen_capture.grab_gray(bbox)
        else:
            gray = frame[0][bbox[1] - frame[1][1]:bbox[3] - frame[1][1], bbox[0] - frame[1][0]:bbox[2] - frame[1][0]]
        if gray.shape[0] < template.shape[0] or gray.shape[1] < template.shape[1]:
            return None
        score = float(cv2.minMaxLoc(cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED))[1])
        if region is None and score < float(self.cfg.get('match_threshold', .83)):
            if not hasattr(self, '_alternative_templates'):
                self._alternative_templates = {}
            for alternate, alternate_region in MARKER_ALTERNATIVES.get(name, ()):
                if alternate not in self._alternative_templates:
                    self._alternative_templates[alternate] = self._load_marker(alternate)
                alternate_template = self._alternative_templates[alternate]
                if alternate_template is None:
                    continue
                alternate_score = self.marker_score(alternate, alternate_template, area=area,
                                                    margin=margin, region=alternate_region, frame=frame)
                if alternate_score is not None:
                    score = max(score, alternate_score)
                if score >= float(self.cfg.get('match_threshold', .83)):
                    break
        return score

    def seed_visible(self, name):
        """Compare one small built-in marker region of the menu."""
        template = self.seed_markers.get(name)
        if template is None or name not in self.regions:
            return False
        score = self.marker_score(name, template, margin=8)
        return score is not None and score >= float(self.cfg.get('match_threshold', .83))

    def color_palette_template(self, scale, race='human', part='hair'):
        """The hair/facial colour palette picture at the current display scale (cached)."""
        cache = self.__dict__.setdefault('_palette_templates', {})
        import appearance
        filename = appearance.COLOR_ASSETS.get(race, {}).get(part)
        if filename is None:
            raise RuntimeError('No {} colour palette exists for {}.'.format(part, race))
        key = (filename, round(scale, 3))
        if key not in cache:
            path = artwork_path(filename)
            image = cv2.imread(str(path), cv2.IMREAD_COLOR) if path else None
            if image is None:
                raise RuntimeError('assets/{} is missing or unreadable; reinstall the complete application folder.'.format(filename))
            if abs(scale - 1.0) >= .01:
                image = cv2.resize(image, (round(image.shape[1] * scale), round(image.shape[0] * scale)),
                                   interpolation=cv2.INTER_LINEAR)
            cache[key] = image
        return cache[key]

    def find_color_palette(self, timeout=1.5, *, race='human', part='hair'):
        """Top-left corner, in 640 x 480 coordinates, of the opened hair/facial colour palette.

        The palette's position depends on which swatch opened it, so it is
        found by its picture instead of by a recorded point. The pointer is
        moved off first because the game draws its cursor into the frame.
        """
        area = self.game_area()
        scale = area.require_scale()
        template = self.color_palette_template(scale, race, part)
        bbox = area.region_to_screen((0, 0, 640, 480))
        self.park_menu_cursor()
        deadline = self.clock() + float(timeout)
        while True:
            self.check()
            frame = screen_capture.grab_bgr(bbox)
            # Locate in grayscale (fast), then confirm the colours at that spot.
            _, score, _, found = cv2.minMaxLoc(cv2.matchTemplate(
                cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), cv2.cvtColor(template, cv2.COLOR_BGR2GRAY),
                cv2.TM_CCOEFF_NORMED))
            if score >= PALETTE_MATCH:
                x, y = found
                patch = frame[y:y + template.shape[0], x:x + template.shape[1]]
                # The median ignores a cursor or tooltip covering part of the palette.
                if float(np.median(np.abs(patch.astype(np.int16) - template))) <= PALETTE_COLOR_DIFF:
                    return (x / scale, y / scale)
            if self.clock() >= deadline:
                raise RuntimeError('The colour palette did not appear after clicking its swatch (best match {:.2f}); '
                                   'nothing was submitted. Check the swatch click points under '
                                   'Setup > Game Client > Click points.'.format(score))
            self.sleep(.15)

    def visible_seed_marker(self):
        """First creation-screen marker showing, from a single capture of all their regions."""
        area = self.game_area()
        names = [n for n in SEED_MARKERS if n in self.seed_markers and n in self.regions]
        if area.scale is None or not names:
            return None
        frame = self.menu_frame(area, [self.regions[n] for n in names], 8)
        for name in names:
            score = self.marker_score(name, self.seed_markers[name], area, margin=8, frame=frame)
            if score is not None and score >= float(self.cfg.get('match_threshold', .83)):
                return name
        return None

    def _read_progress(self):
        state = load_json(PROGRESS_FILE, {})
        return set(state.get(self.progress_id, []))

    def _save_progress(self):
        state = load_json(PROGRESS_FILE, {})
        state[self.progress_id] = sorted(self.completed)
        atomic_json(PROGRESS_FILE, state)

    def _read_identity_progress(self):
        state = load_json(IDENTITY_PROGRESS_FILE, {})
        record = state.get(self.progress_id, {})
        if not isinstance(record, dict):
            return {}
        return {shard: set(values) for shard, values in record.items()
                if isinstance(shard, str) and isinstance(values, list)
                and all(isinstance(v, str) and len(v) == 64 for v in values)}

    def _save_identity_progress(self, shard, fingerprint):
        if not isinstance(fingerprint, str) or len(fingerprint) != 64:
            raise RuntimeError('RE did not return a usable character fingerprint; cannot record gift safely.')
        state = load_json(IDENTITY_PROGRESS_FILE, {})
        entry = state.setdefault(self.progress_id, {})
        current = set(entry.get(shard, []))
        current.add(fingerprint)
        entry[shard] = sorted(current)
        atomic_json(IDENTITY_PROGRESS_FILE, state)
        self.gift_identity_history.setdefault(shard, set()).add(fingerprint)

    def _mark_roster_changed(self, shard):
        if not shard:
            return
        self.roster_sensitive_shards.add(shard)
        state = load_json(ROSTER_CHANGE_FILE, {})
        changed = set(state.get(self.progress_id, []))
        changed.add(shard)
        state[self.progress_id] = sorted(changed)
        atomic_json(ROSTER_CHANGE_FILE, state)

    def refresh_seeded_roster(self, shard=None):
        """Known creation invalidates old slot-to-character assumptions.

        Existing seeder history is used at startup too, so a new program
        version safely revisits a shard seeded by an earlier version. Only
        the selected local Seeder History is read, not other users/accounts.
        """
        if not hasattr(self, 'seed_account_id'):
            return
        from seeder_rules import name_hash
        from cycle_state import cycle_key, excluded_creation_names
        cycle = cycle_key(self.cfg, getattr(self, 'progress_id', ''))
        state = load_json(SEED_PROGRESS_FILE, {})
        profile = state.get('profiles', {}).get(self.seed_account_id, {})
        if not isinstance(profile, dict):
            return
        for shard_name, record in profile.items():
            if shard is not None and shard_name != shard:
                continue
            if not isinstance(record, dict):
                continue
            names = [n for n in record.get('created', []) if isinstance(n, str)]
            if isinstance(record.get('pending'), str) and record['pending']:
                names.append(record['pending'])
            if names:
                self._mark_roster_changed(shard_name)
                self.seeded_character_hashes[shard_name] = {
                    name_hash(n) for n in excluded_creation_names(record, cycle)}

    def record_issue(self, shard, slot, code):
        """Persistent issue report without character/account names or credentials."""
        state = load_json(ISSUES_FILE, {})
        items = state.get(self.progress_id, [])
        if not isinstance(items, list):
            items = []
        items.append({"at": datetime.now().isoformat(timespec="seconds"),
                      "shard": shard, "slot": slot, "reason": code})
        state[self.progress_id] = items[-500:]
        atomic_json(ISSUES_FILE, state)

    def clock(self):
        """Navigation deadlines exclude time spent waiting for explicit Resume."""
        return time.monotonic() - getattr(self, '_paused_seconds', 0.0)

    def check(self):
        if self.stop.is_set():
            raise Cancelled("Stopped by user")
        if not self.pause.is_set():
            return
        started = time.monotonic()
        self.emit("PAUSED|Leave the game screen unchanged. Click Resume, or press Escape to stop.")
        try:
            while self.pause.is_set():
                if self.stop.wait(.05):
                    raise Cancelled("Stopped while paused")
        finally:
            self._paused_seconds = getattr(self, '_paused_seconds', 0.0) + time.monotonic() - started
        if self.stop.is_set():
            raise Cancelled("Stopped while paused")
        self.emit("RESUMED|Continuing the current operation.")

    def sleep(self, seconds):
        end = self.clock() + seconds
        while self.clock() < end:
            self.check()
            self.park_if_idle()
            time.sleep(min(.12, max(.01, end - self.clock())))

    def say(self, msg):
        self.emit(msg)

    def input_context(self):
        """Small built-in markers and identity only; never capture a full screen."""
        window = selected_window(self.window_title)
        area = client_area(window._hWnd)
        screen = self.state()
        if screen == 'unknown':
            marker = self.visible_seed_marker()
            if marker:
                screen = 'creation:' + marker
        identity = shard_from_title(window.title, KNOWN_SHARDS)
        if screen == 'unknown' and self.bridge is not None:
            status = self.bridge.get_status()
            if status:
                screen = 'world'
                identity = (status.get('instance_id'), status.get('name_sha256'), status.get('shard'))
        return (int(window._hWnd), area.left, area.top,
                area.width, area.height, screen, identity)

    def pointer_action(self, point, operation, *, expected=None, settle=0):
        """Resume a failed move only before any click, on the same verified screen."""
        self.check()
        focus_game(self.window_title)
        context = self.input_context()
        if expected is not None and context[5] != expected:
            raise RuntimeError('Game screen changed before mouse input; no click sent.')
        retried = False
        while True:
            self.check()
            focus_game(self.window_title)
            if self.input_context() != context:
                if retried:
                    raise RuntimeError('Game screen or window changed while paused; no repeated click sent.')
                raise RuntimeError('Game screen changed before mouse input; no click sent.')
            if settle:
                self.sleep(settle)
            def before_click(clicks_sent=0):
                if self.stop.is_set():
                    raise Cancelled('Stopped before mouse click')
                if self.pause.is_set():
                    raise native_mouse.PointerInterrupted('Pause requested before mouse click.')
                if not clicks_sent and self.input_context() != context:
                    raise RuntimeError('Game screen changed before mouse input; no click sent.')
            try:
                return operation(*point_screen(self.window_title, *point), before_click=before_click)
            except native_mouse.PointerInterrupted as exc:
                self.pause.set()
                self.say('MOUSE DETAILS: ' + str(exc))
                self.emit('POINTER_PAUSED|' + ('Mouse moved before clicking. ' if not exc.clicks_sent else
                          'Mouse moved after part of the click. That click will not be repeated. ') +
                          'Leave the game screen unchanged. Click Resume, or press Escape to stop.')
                self.check()
                if exc.clicks_sent:
                    # Let the caller read the resulting menu/world state instead
                    # of blindly replaying a partially completed double-click.
                    return {'clicks_sent': exc.clicks_sent, 'interrupted': True}
                if context[5] == 'unknown':
                    raise RuntimeError('Cannot verify the game screen after mouse pause; no repeated click sent.')
                retried = True

    def click(self, point, *, expected=None, settle=0, double=False):
        """Click once, or double-click at human speed (`double`, which needs `expected`).

        Before the second click of a double-click the screen is read again, and
        the second click is only sent while it is still the expected screen, so
        it can never land on whatever the first click opened.
        """
        operation = native_mouse.click_cursor
        if double:
            if expected is None:
                raise ValueError("A double-click needs the screen it is expected to stay on.")
            operation = lambda x, y, before_click: native_mouse.double_click_cursor(
                x, y, interval=DOUBLE_CLICK_GAP, before_click=before_click,
                between_clicks=lambda: self.second_click_allowed(expected))
        return self.pointer_action(point, operation, expected=expected, settle=settle)

    def wait_out_sync_panel(self, context):
        """Wait, sending no input, for the stone panel that looks like an Origin error to clear.

        The panel shown while the client connects or loads the world matches the
        Origin error marker, and a slow shard keeps it up for a while. A real
        error stays up until dismissed, so it is only reported once the panel
        has been showing for `sync_transient_seconds`.
        """
        patience = self.clock() + float(self.cfg.get("sync_transient_seconds", SYNC_PATIENCE_SECONDS))
        while self.clock() < patience:
            self.sleep(.30)
            if self.state() != "sync_error":
                return
        raise SyncScreen("Origin error {}. Recognition scores: ".format(context) +
                         ", ".join("{}={:.3f}".format(name, score) for score, name in
                                   sorted(getattr(self, "_last_marker_scores", []), reverse=True)))

    def second_click_allowed(self, expected):
        if self.state() == expected:
            return True
        self.say("Screen changed after the first click; the second click was not sent.")
        return False

    def press(self, key):
        self.check()
        focus_game(self.window_title)
        pg.press(key)

    def park_menu_cursor(self):
        """Move the pointer off any control, without clicking or a menu delay."""
        self.check()
        area = self.game_area()
        if area.scale is None:
            return  # Do not reposition the pointer in a non-menu world view.
        # Blank top-right menu artwork, away from arrows, fields and popup lists.
        native_mouse.move_cursor(*area.to_screen(*PARK_POINT), settle=.01)

    def park_if_idle(self):
        """Move the pointer off a control it has rested on for several seconds.

        The game shows a tooltip once the pointer has rested on a control long
        enough, and a tooltip covering a screen marker makes the screen look
        unknown. Only a pointer still where this program left it is moved.
        """
        seconds = float(self.cfg.get("park_idle_seconds", PARK_IDLE_SECONDS))
        if seconds <= 0 or self.pause.is_set():
            return
        try:
            here = native_mouse.idle_pointer(seconds)
            if here is None:
                return
            area = self.game_area()
            if area.scale is None:
                return
            spot = area.to_screen(*PARK_POINT)
            if abs(here[0] - spot[0]) > 3 or abs(here[1] - spot[1]) > 3:
                native_mouse.move_cursor(*spot, settle=.01)
        except (RuntimeError, OSError):
            pass

    def state(self):
        """Recognize the menu screen from the built-in marker regions.

        The marker regions are copied from the screen in one in-memory capture
        of the menu area, matched, and discarded; no window title bar or other
        screen content is read, and nothing is stored or transmitted. A game area
        that is not a (scaled) 640 x 480 menu, such as the world view, is unknown.
        """
        self.check()
        scores = self.marker_scores()
        self._last_marker_scores = list(scores)
        scores.sort(reverse=True)
        # Explicit warning markers override the ordinary login artwork when
        # the game paints a modal dialog on top of the login screen.
        warning = [x for x in scores if x[1] in OPTIONAL_MARKERS
                   and x[0] >= float(self.cfg["match_threshold"])]
        if warning:
            warning.sort(reverse=True)
            return warning[0][1]
        if not scores or scores[0][0] < float(self.cfg["match_threshold"]):
            return "unknown"
        if len(scores) > 1 and scores[1][0] > scores[0][0] - .035:
            return "unknown"
        return scores[0][1]

    def marker_scores(self):
        """(score, name) for each ordinary screen marker in the current game area."""
        area = self.game_area()
        if area.scale is None:
            return []
        rects = [self.regions[name] for name in self.markers]
        rects += [region for name in self.markers for _, region in MARKER_ALTERNATIVES.get(name, ())]
        frame = self.menu_frame(area, rects, 12)
        scores = []
        for name, template in self.markers.items():
            score = self.marker_score(name, template, area, frame=frame)
            if score is not None:
                scores.append((score, name))
        return scores

    def bridge_status(self, timeout, minimum_start=None, expected_shard=None):
        if self.bridge is None:
            raise RuntimeError("RE bridge session not active.")
        deadline = self.clock() + timeout
        while self.clock() < deadline:
            self.check()
            status = self.bridge.get_status(minimum_start=minimum_start)
            if status:
                if expected_shard and status["shard"].strip().casefold() != expected_shard.strip().casefold():
                    raise RuntimeError("RE shard mismatch: expected {!r}, got {!r}.".format(
                        expected_shard, status["shard"]))
                return status
            self.sleep(.2)
        return None

    def title_identity_check(self, wanted, wait_seconds=1.5):
        """Reject a wrong known shard BEFORE any character-slot click.

        Some client versions may not append the shard until the world loads;
        absence of a recognized suffix is not proof of the right shard. RE
        remains the authoritative in-world verification.
        """
        names = list(dict.fromkeys(KNOWN_SHARDS + list(self.cfg["shards"])))
        deadline = self.clock() + wait_seconds
        seen = None
        while True:
            self.check()
            seen = shard_from_title(selected_window(self.window_title).title, names)
            if seen == wanted:
                self.say("Classic Client window title confirms shard: {}.".format(seen))
                return seen
            if self.clock() >= deadline:
                break
            self.sleep(.2)
        if seen is not None:
            raise RuntimeError(
                "WRONG SHARD BEFORE CHARACTER LOGIN: requested {!r}, "
                "Classic Client window title says {!r}. Stopped safely. "
                "Check the shard order/sort; no character was entered.".format(wanted, seen))
        if self.cfg.get("require_shard_title", True):
            raise RuntimeError("Character menu window title had no verified shard suffix. "
                               "Stopped BEFORE entering a character; confirm client/window/title.")
        self.say("Window title has no shard suffix; RE bridge will verify later.")
        return None

    def scroll_shard_arrow(self, key, count):
        """Keep the cursor on one verified arrow while scrolling in a burst."""
        if not count:
            return
        point = self.cfg['points'][key]
        result = self.pointer_action(point,
            lambda x, y, before_click: native_mouse.click_cursor_many(
                x, y, count, before_click=before_click), expected='servers')
        if result.get('interrupted') or result.get('clicks_sent') != count:
            self.shard_list_at_top = False
            raise RuntimeError('Shard scrolling interrupted; row position is unverified. No shard selected.')
        if self.state() != 'servers':
            raise RuntimeError('Shard list changed during scrolling; no shard selected.')

    def shard_templates(self):
        """Learned shard-name images that are usable right now (cached)."""
        if self._shard_templates is None:
            names = list(dict.fromkeys(KNOWN_SHARDS + list(self.cfg["shards"])))
            self._shard_templates = shard_rows.load_templates(shard_template_dirs(), names)
        return self._shard_templates

    def capture_shard_rows(self):
        """Name column of the nine visible rows, normalised to 640 x 480 scale."""
        area = self.game_area()
        scale = area.require_scale()
        gray = screen_capture.grab_gray(area.region_to_screen(shard_rows.NAME_REGION))
        return shard_rows.normalise(gray, scale)

    def read_shard_rows(self, settle=.3):
        """(names per visible row, image). The pointer is parked first so no hover colours the rows."""
        self.park_menu_cursor()
        self.sleep(settle)
        gray = self.capture_shard_rows()
        return shard_rows.identify_rows(gray, self.shard_templates()), gray

    def wheel_shard_list(self, direction, count, verify_screen=True):
        """Scroll the shard list `count` rows ('down' or 'up'), one wheel event per row."""
        self.check()
        focus_game(self.window_title)
        if verify_screen and self.state() != "servers":
            raise RuntimeError("Shard list is not showing; no mouse-wheel input sent.")
        point = self.game_area().to_screen(*SHARD_WHEEL_POINT)

        def guard(sent=0):
            if self.stop.is_set():
                raise Cancelled("Stopped before mouse wheel")
            if self.pause.is_set():
                raise native_mouse.PointerInterrupted("Pause requested while scrolling the shard list.", sent)
        try:
            native_mouse.wheel_cursor(*point, -count if direction == "down" else count,
                                      SHARD_WHEEL_GAP, before_event=guard)
        except native_mouse.PointerInterrupted as exc:
            self.pause.set()
            self.say("MOUSE DETAILS: " + str(exc))
            self.emit("POINTER_PAUSED|Mouse moved while scrolling the shard list. "
                      "Leave the game screen unchanged. Click Resume, or press Escape to stop.")
            self.check()
        self.park_menu_cursor()

    def row_point(self, row):
        first = self.cfg["points"]["first_row"]
        return (first[0], first[1] + row * int(self.cfg["row_spacing"]))

    def recognized_shard_row_point(self, index):
        """Scroll with the wheel, reading row names after every step, until the target is on screen."""
        shard = self.cfg["shards"][index]
        if not self.shard_list_at_top:
            self.say("Initial shard-list position unknown; scrolling to the top with the mouse wheel.")
            self.wheel_shard_list("up", SHARD_RESET_EVENTS)
            self.shard_list_at_top = True
        previous, stalls = None, 0
        for _ in range(MAX_LIST_STEPS):
            visible, gray = self.read_shard_rows()
            move, amount = shard_rows.next_move(visible, shard, self.cfg.get("navigation_shards") or self.cfg["shards"])
            if move == "click":
                self.say("Shard list row {} reads as {}.".format(amount + 1, shard))
                return self.row_point(amount)
            if move == "lost":
                raise ShardRowsNotFound("the saved order disagrees with the names on screen")
            stalls = stalls + 1 if previous is not None and np.array_equal(gray, previous) else 0
            if stalls > 2:
                raise ShardRowsNotFound("the list stopped scrolling")
            previous = gray
            self.say("Shard list: scrolling {} {} row(s) toward {}.".format(move, amount, shard))
            self.wheel_shard_list(move, amount)
        raise ShardRowsNotFound("{} was not found after {} steps".format(shard, MAX_LIST_STEPS))

    def shard_row_strip(self, row):
        """Picture of one visible row's name, or None if it cannot be read right now."""
        try:
            self.park_menu_cursor()
            self.sleep(.2)
            return shard_rows.split_rows(self.capture_shard_rows())[row]
        except (RuntimeError, OSError):
            return None

    def save_shard_template(self, shard, strip):
        """Remember what a title-verified shard looks like in the list."""
        crop = shard_rows.ink_crop(strip) if strip is not None else None
        if crop is None:
            return False
        if shard_rows.identify(strip, self.shard_templates()) is not None:
            return False
        shard_rows.save_template(SHARD_NAMES_DIR, shard, crop)
        self._shard_templates = None
        self.say("Learned the shard-list picture for {}.".format(shard))
        return True

    def forget_shard_template(self, shard):
        path = SHARD_NAMES_DIR / (shard_rows.slug(shard) + ".png")
        if path.is_file():
            path.unlink()
            self._shard_templates = None
            self.say("Forgot the saved shard-list picture for {}; it will be learned again.".format(shard))

    def verify_selected_shard(self, shard):
        """Title-check the shard just opened; learn its list picture or drop a wrong one."""
        try:
            seen = self.title_identity_check(shard)
        except RuntimeError as exc:
            if str(exc).startswith("WRONG SHARD") and self._row_source == "names":
                self.forget_shard_template(shard)
            raise
        candidate, self._learn_candidate = self._learn_candidate, None
        if seen == shard and candidate is not None and candidate[0] == shard:
            self.save_shard_template(shard, candidate[1])
        return seen

    def learn_shard_names(self, order):
        """Save a picture of every shard name, labelled from the verified order.

        Scrolls the list one row at a time and checks every step against the
        names already learned; any surprise stops it before anything is saved.
        Only mouse-wheel input is sent, never a click or a key.
        """
        order = list(order)
        rows = shard_rows.VISIBLE_ROWS
        if len(order) < 2 or len({name.casefold() for name in order}) != len(order):
            raise RuntimeError("Confirm or scan the shard order first; nothing was changed.")
        if self.state() != "servers":
            raise RuntimeError("Open the shard list first; no input sent.")
        self.say("LEARN: scrolling the shard list to the top.")
        self.wheel_shard_list("up", SHARD_RESET_EVENTS)

        def snapshot():
            self.sleep(.3)
            return shard_rows.split_rows(self.capture_shard_rows())

        def crop_of(strip, label):
            crop = shard_rows.ink_crop(strip)
            if crop is None:
                raise RuntimeError("A list row meant for {} shows no readable text; nothing saved.".format(label))
            return crop

        strips = snapshot()
        learned = {order[row]: crop_of(strips[row], order[row]) for row in range(min(rows, len(order)))}
        offset = 0
        while offset + rows < len(order):
            for _attempt in range(3):
                self.wheel_shard_list("down", 1, verify_screen=False)
                strips = snapshot()
                head = shard_rows.identify(strips[0], learned)
                if head == order[offset + 1]:
                    break
                if head != order[offset]:
                    raise RuntimeError("The list showed something unexpected while learning; nothing saved. "
                                       "Check that the saved shard order is right.")
            else:
                raise RuntimeError("The shard list stopped scrolling; nothing saved.")
            offset += 1
            for row in range(rows - 1):
                seen = shard_rows.identify(strips[row], learned)
                if seen is not None and seen != order[offset + row]:
                    raise RuntimeError("Row {} reads as {} but the saved order says {}; nothing saved.".format(
                        row + 1, seen, order[offset + row]))
            learned[order[offset + rows - 1]] = crop_of(strips[rows - 1], order[offset + rows - 1])
            self.say("LEARN: {}/{} names read.".format(len(learned), len(order)))
        for name, crop in learned.items():
            if shard_rows.identify(crop, learned) != name:
                raise RuntimeError("{} looks too much like another shard name to tell apart; nothing saved.".format(name))
        for name, crop in learned.items():
            shard_rows.save_template(SHARD_NAMES_DIR, name, crop)
        self._shard_templates = None
        self.say("LEARN: scrolling back to the top.")
        self.wheel_shard_list("up", SHARD_RESET_EVENTS, verify_screen=False)
        self.shard_list_at_top = True
        self.say("LEARN FINISHED: saved the list pictures of {} shards. Runs will now find shards by reading the list.".format(len(learned)))
        return sorted(learned)

    def arrow_shard_row_point(self, index):
        """Fallback navigation: the scroll arrows, in bursts."""
        from shard_policy import physical_index
        row_index = physical_index(self.cfg, index)
        reset_clicks = int(self.cfg.get("scroll_reset_clicks", 18))
        if self.shard_list_at_top:
            self.say("Shard list known to be at TOP — no UP reset required.")
        else:
            self.say("Initial shard-list position unknown; resetting UP {} times once.".format(reset_clicks))
            self.scroll_shard_arrow("scroll_up", reset_clicks)
            self.shard_list_at_top = True
        # This list ALWAYS returns to top after character-menu Back (user tested).
        # Never repeat full UP reset across 7 characters.
        visible = int(self.cfg["visible_rows"])
        below = max(0, row_index - (visible - 1))
        if below:
            self.scroll_shard_arrow("scroll_down", below)
        row = min(row_index, visible - 1)
        shard = self.cfg["shards"][index]
        if shard not in self.shard_templates():
            self._learn_candidate = (shard, self.shard_row_strip(row))
        return self.row_point(row)

    def shard_row_point(self, index):
        """Click point of the target shard's row, scrolled into view."""
        shard = self.cfg["shards"][index]
        self._learn_candidate = None
        if shard in self.shard_templates():
            try:
                point = self.recognized_shard_row_point(index)
                self._row_source = "names"
                return point
            except ShardRowsNotFound as exc:
                self.say("Reading the shard list could not place {} ({}). Using the scroll arrows.".format(shard, exc))
                self.shard_list_at_top = False
        self._row_source = "arrows"
        return self.arrow_shard_row_point(index)

    def scroll_to_shard(self, index):
        """Select from the user-confirmed order; read row names when learned, else use the arrows."""
        from shard_policy import is_supported
        if not is_supported(self.cfg['shards'][index]):
            raise RuntimeError('This shard is not supported; no input sent.')
        point = self.shard_row_point(index)
        # Menu navigation may be retried only when still positively on the
        # shard list. Never click after a title change or a character screen:
        # an extra click could log into the highlighted character.
        for attempt in range(1,4):
            if self.state()!='servers':
                raise RuntimeError('Cannot retry shard selection: not on shard list.')
            self.say(('Selecting shard {}.' if attempt == 1 else 'Retrying shard {} (attempt '+str(attempt)+'/3).').format(self.cfg['shards'][index]))
            self.click(point, expected='servers', settle=.35, double=True)
            deadline=self.clock()+6.0
            final_state='unknown'
            transition_seen = False
            while self.clock()<deadline:
                self.sleep(.30)
                final_state=self.state()
                if final_state=='characters':
                    self.verify_selected_shard(self.cfg["shards"][index])
                    self.selected_index=index
                    self.say('Shard click opened character selection; no Enter sent.')
                    return
                if final_state=='new_character' or self.seed_visible('seed_appearance'):
                    # Empty shard may open character creation immediately.
                    # Require a matching shard title AND a recognized creation
                    # marker; never click a character slot or press Enter here.
                    self.verify_selected_shard(self.cfg['shards'][index])
                    self.selected_index=index
                    self.say('Shard opened character creation directly; no character was selected.')
                    return
                if final_state=='sync_error':
                    transition_seen = True
                    self.wait_out_sync_panel('while selecting a shard')
                    self.say('Transient Origin marker during shard entry; waiting for the character screen.')
                    deadline = max(deadline, self.clock() + 3.0)
                    continue
                if final_state=='online_busy':
                    raise OnlineBusy('Account is still online during shard selection.')
                if final_state=='login':
                    raise RuntimeError('Returned to login during shard selection.')
                if final_state!='servers' and shard_from_title(
                        selected_window(self.window_title).title,KNOWN_SHARDS):
                    if not transition_seen:
                        self.say('Shard title changed; waiting for the character screen to finish loading. No extra input sent.')
                    transition_seen = True
            if final_state!='servers' or transition_seen:
                raise RuntimeError('Unknown menu after shard selection; refusing extra click.')
            if attempt<3:
                self.say('Shard did not open within 6 seconds; still on the verified shard list. Waiting before retry.')
                self.sleep(1)
        raise RuntimeError('Shard {} was not selected after 3 click attempts; no Enter sent.'.format(
            self.cfg['shards'][index]))

    def select_last_shard_shortcut(self, index):
        """Return to the last RE-confirmed shard without scrolling the list.

        Enter is permitted ONLY on the recognized shard-selection screen.
        Never press Enter after a shard mouse click or while on the character
        list, because that can immediately enter the selected character.
        """
        shard = self.cfg["shards"][index]
        if not self.cfg.get("fast_last_shard", False):
            return False
        if self.last_verified_shard != shard or shard in self.fast_shortcut_failed:
            return False
        if self.state() != "servers":
            raise RuntimeError("Fast last-shard shortcut refused: not on shard list.")

        self.say("FAST RETURN: last RE-verified shard is {}. Sending Enter on shard list ONLY.".format(shard))
        self.press("enter")
        deadline = self.clock() + 6.0
        while self.clock() < deadline:
            self.sleep(.25)
            current = self.state()
            if current == "characters":
                # Provisional until another RE in-world shard verification.
                self.title_identity_check(shard)
                self.selected_index = index
                self.say("FAST RETURN: character menu reached, no character key sent. Shard will be verified by RE.")
                return True
            if current == "login":
                raise RuntimeError("Fast last-shard shortcut returned to login unexpectedly; stopped safely.")
        current = self.state()
        if current == "servers":
            # Enter may not activate the last-shard shortcut in some clients;
            # fall back to the old explicit shard selection just this once.
            self.fast_shortcut_failed.add(shard)
            self.say("FAST RETURN: Enter did not leave shard list. Falling back to shard-list scrolling.")
            return False
        raise RuntimeError("Fast last-shard shortcut produced an unrecognized screen; refusing further clicks.")

    def reach_characters(self, index):
        from shard_policy import is_supported
        if not is_supported(self.cfg["shards"][index]):
            raise RuntimeError("This shard is not supported; no input sent.")
        deadline = self.clock() + float(self.cfg["menu_timeout"])
        last_actions = {}
        while self.clock() < deadline:
            self.check()
            state = self.state()
            now = self.clock()
            if state == "sync_error":
                self.wait_out_sync_panel("while navigating the menus")
                continue
            if state == "online_busy":
                raise OnlineBusy("Another character remains logged in on this shard.")
            if state == "login":
                self.selected_index = None
                self.shard_list_at_top = True  # Login reconstructs list in default TZ order.
                if self.login_after_warning:
                    # After an ONLINE/ORIGIN warning, pressing Enter does NOT
                    # re-submit the saved Razor credentials. Click the game's
                    # actual Login button instead. Never click on unknown pages.
                    point = self.cfg.get("points", {}).get("login_button")
                    if (not isinstance(point, (list, tuple)) or len(point) != 2
                            or not all(isinstance(v, (int, float)) for v in point)):
                        raise RuntimeError(
                            "Built-in Login button position is missing; reinstall the application.")
                    attempts = last_actions.get("login_clicks", 0)
                    if attempts >= 3:
                        raise RuntimeError(
                            "Login screen remained visible after 3 Login-button clicks "
                            "following a warning. Stopped; no more retries.")
                    if now - last_actions.get("login", 0) > 3:
                        self.say("Post-warning login: clicking the Login button "
                                 "(attempt {}/3).".format(attempts + 1))
                        self.click(point)
                        last_actions["login"] = self.clock()
                        last_actions["login_clicks"] = attempts + 1
                elif now - last_actions.get("login", 0) > 8:
                    self.say("Normal login detected. Pressing Enter; Razor owns credentials.")
                    self.press("enter")
                    last_actions["login"] = now
            elif state == "servers":
                # The game accepted the login: clear the special recovery mode.
                self.login_after_warning = False
                self.selected_index = None
                if now - last_actions.get("servers", 0) > 12:
                    if not self.select_last_shard_shortcut(index):
                        self.say("Selecting shard from verified list: " + self.cfg["shards"][index])
                        self.scroll_to_shard(index)
                    last_actions["servers"] = self.clock()
            elif state == 'new_character' or self.seed_visible('seed_appearance'):
                if self.selected_index != index:
                    raise RuntimeError('Creation screen on an unverified shard; no input sent.')
                self.title_identity_check(self.cfg['shards'][index],wait_seconds=.2)
                self.say('Empty shard recognized: character creation is the first screen.')
                return 'creation'
            elif state == "characters":
                if self.selected_index == index:
                    self.title_identity_check(self.cfg["shards"][index], wait_seconds=.2)
                    return
                if now - last_actions.get("characters", 0) > 8:
                    self.say("Returning to shard list to verify selection.")
                    self.click(self.cfg["points"]["back"])
                    self.selected_index = None
                    self.shard_list_at_top = True  # Verified user behavior.
                    last_actions["characters"] = now
            self.sleep(.7)
        raise RuntimeError("Timed out navigating to shard: " + self.cfg["shards"][index])

    def enter_slot(self, index, slot):
        p = self.cfg["points"]
        pt = p.get("char_slot_{}".format(slot + 1))
        if pt is None:
            pt = character_slot_point(p, slot + 1)
        self.click(pt)
        self.sleep(.35)
        # A recognizable new-character screen means this slot is empty.
        # Never press Enter or follow the create-character flow.
        state_after_click = self.state()
        if state_after_click == "new_character" or self.seed_visible('seed_appearance'):
            raise EmptySlot("New Character screen appeared after selecting slot {}.".format(slot+1))
        if state_after_click != 'characters':
            # A click may have opened an uncalibrated creation/menu screen.
            # Do not send Enter on an unknown page: this could advance creation.
            raise RuntimeError("Slot click changed the menu to {}. Refusing Enter without a recognized character list.".format(state_after_click))
        self.last_bridge = None
        # A previous character's still-running bridge must not satisfy this slot.
        # Classic Client requires a DOUBLE-CLICK on the chosen character (or a
        # click followed by the shared Next button). Enter does NOT reliably
        # activate the highlighted character. The first click above intentionally
        # checks for an empty/creation slot before the double-click below.
        self.check()
        focus_game(self.window_title)
        entry_started = time.time()
        self.pointer_action(pt, native_mouse.double_click_cursor, expected='characters')
        self.say("Double-clicked character slot {}. Waiting for AutoStart RE bridge.".format(slot + 1))
        deadline = self.clock() + float(self.cfg["world_timeout"])
        character_screen_seen_after = None
        while self.clock() < deadline:
            self.check()
            state = self.state()
            if state == "online_busy":
                raise OnlineBusy("Another character is still in this world.")
            if state == "sync_error":
                # The panel shown while the world loads matches the Origin error marker.
                self.wait_out_sync_panel("during world entry")
                self.say('Transient Origin marker during world entry; waiting for a stable screen.')
                continue
            if state == "new_character" or self.seed_visible('seed_appearance'):
                raise EmptySlot("Slot {} is empty / new character screen shown.".format(slot+1))
            if state == "login" or state == "servers":
                self.selected_index = None
                return False
            if state == "characters":
                if character_screen_seen_after is None:
                    character_screen_seen_after = self.clock()
                elif self.clock() - character_screen_seen_after > 5:
                    self.say("Slot {} did not advance after 5 seconds; treating as unverified, not complete.".format(slot+1))
                    return False
            else:
                character_screen_seen_after = None
            # Never rely on world screenshots or static character HUD layout.
            # A new RE bridge instance, started after slot selection, proves entry.
            status = self.bridge_status(timeout=.2, minimum_start=entry_started)
            if status:
                wanted = self.cfg["shards"][index]
                if status["shard"].strip().casefold() != wanted.strip().casefold():
                    raise RuntimeError("Shard mismatch! Expected '{}', RE says '{}'. Stopping.".format(
                        wanted, status["shard"]))
                self.last_bridge = status
                # Trust the last-played shard only after RE world verification.
                # Seeder records the same proof after a confirmed creation.
                # Seeing the character menu alone is not proof of shard identity.
                self.last_verified_shard = wanted
                self.say("RE AutoStart bridge confirmed in-world on {}.".format(status["shard"]))
                return True
            self.sleep(.35)
        raise RuntimeError("RE AutoStart bridge missing, world login timed out, or screen unexpected. Stopped safely.")

    def wait_gift(self, shard):
        self.say("Waiting {} seconds for gift on {}.".format(self.cfg["gift_wait"], shard))
        self.sleep(float(self.cfg["gift_wait"]))
        if self.state() in ("login", "servers", "characters"):
            raise RuntimeError("Disconnected during gift wait; character not marked complete.")
        checked = self.bridge_status(timeout=4, expected_shard=shard)
        if not checked or not self.last_bridge or checked['instance_id'] != self.last_bridge['instance_id']:
            raise RuntimeError("RE bridge changed or disconnected during gift wait. Stopped safely.")
        self.last_bridge = checked

    def logout(self):
        self.say("Requesting RE bridge Misc.Disconnect() (no game chat or hotkey).")
        if not self.last_bridge:
            raise RuntimeError("Missing active bridge instance; will not logout.")
        self.bridge.request_logout(self.last_bridge)
        deadline = self.clock() + 30
        while self.clock() < deadline:
            self.check()
            state = self.state()
            if state in ("login", "servers"):
                self.selected_index = None
                return
            self.sleep(.7)
        raise RuntimeError("Logout NOT verified. Stopped; character not marked complete.")

    def acknowledge_warning(self, expected):
        """Dismiss a positively identified warning with Enter, not a calibrated mouse click.

        If no warning marker exists, the state cannot be identified and the
        recovery safely halts rather than blindly pressing Enter.
        """
        observed = self.state()
        if observed != expected:
            # The client may clear a warning itself before the GUI's handler
            # runs. The resulting known menu is safe; don't click or Enter.
            for _ in range(4):
                if observed in ('login', 'servers', expected):
                    break
                self.sleep(.25)
                observed = self.state()
            if observed == 'login':
                self.login_after_warning = True
                self.selected_index = None
                self.say('Warning cleared before acknowledgment; login screen detected. Next login clicks the Login button.')
                return
            if observed == 'servers':
                self.login_after_warning = False
                self.selected_index = None
                self.say('Warning cleared before acknowledgment; shard list detected. No Enter sent.')
                return
            if observed != expected:
                raise RuntimeError('Warning marker changed: expected {}, saw {}. No Enter sent; inspect the Classic Client.'.format(expected, observed))
        self.say("Acknowledging positively recognized {} with one Enter keypress.".format(expected))
        self.press("enter")
        deadline = self.clock() + 12
        while self.clock() < deadline:
            state = self.state()
            if state == "login":
                self.selected_index = None
                # Next login must click the Login button, not press Enter.
                self.login_after_warning = True
                self.say("Warning cleared. Next login will click the Login button, not press Enter.")
                return
            self.sleep(.3)
        raise RuntimeError("Warning confirmation did not return to the login screen; stopped safely.")

    def recover_empty_slot(self):
        """Skip safely when still on character menu, or via a calibrated Cancel button."""
        current = self.state()
        if current == "characters":
            self.say("Character list is still open; skipping unverified slot without another keypress.")
            return
        if current != "new_character" and not self.seed_visible('seed_appearance'):
            raise RuntimeError("Cannot safely recover empty slot: screen is {}.".format(current))
        point = (self.cfg.get("points", {}).get("back") or
                 self.cfg.get("points", {}).get("create_back"))
        if not point:
            raise RuntimeError("New-character screen detected but the Cancel/Back position is missing. "
                               "Cannot safely skip without risking character creation.")
        self.click(point)
        deadline = self.clock() + 10
        while self.clock() < deadline:
            state = self.state()
            if state in ("characters", "login", "servers"):
                if state != "characters":
                    self.selected_index = None
                self.say("Safely exited character creation; empty slot will be skipped.")
                return
            self.sleep(.35)
        raise RuntimeError("Creation Cancel/Back did not return to a known menu.")

    def countdown(self, seconds, reason):
        self.emit("ALERT|{} — waiting {} seconds; use PAUSE to intervene.".format(reason, seconds))
        self.say(reason + ": countdown started. Do not retry login yet.")
        remaining = int(seconds)
        while remaining > 0:
            self.check()
            if remaining == seconds or remaining % 15 == 0 or remaining <= 5:
                mm, ss = divmod(remaining, 60)
                self.emit("COUNTDOWN|{}|{:02d}:{:02d}".format(reason, mm, ss))
            # Pausing must freeze this countdown, and never generate game input.
            self.sleep(1)
            remaining -= 1
        self.emit("COUNTDOWN|{}|00:00".format(reason))
        if self.state() != "login":
            raise RuntimeError("Cooldown complete, but login screen not recognized. "
                               "Return there manually; no blind Enter attempted.")

    def run(self, *, creation_only=False):
        from shard_policy import is_supported
        shards = self.cfg["shards"]
        excluded = set(self.cfg["excluded"])
        self.refresh_seeded_roster()
        if self.roster_sensitive_shards:
            self.say('Roster changes detected on {}. Old slot-number completions on these shards are not trusted; checking character fingerprints instead.'.format(
                ', '.join(sorted(self.roster_sensitive_shards))))
        tasks = [(i, shard, n) for i, shard in enumerate(shards)
                 if is_supported(shard) and shard not in excluded for n in occupied_slots_for(self.cfg, shard)]
        total = len(tasks)
        done = sum(1 for _, shard, slot in tasks
                   if shard not in self.roster_sensitive_shards
                   and "{}|{}".format(shard, slot) in self.completed)
        done += sum(len(self.gift_identity_history.get(shard, set()))
                    for shard in self.roster_sensitive_shards if shard not in excluded)
        done = min(done, total)
        self.emit("PROGRESS|{}|{}".format(done, total))
        self.say("{} candidate slots on {} included shards, {} completed this cycle. Empty slots are not gifts.".format(
            total, len([s for s in shards if s not in excluded]), done))
        with BridgeSession(self.stop) as bridge:
            self.bridge = bridge
            try:
                self.sleep(1)
                if bridge.get_status():
                    raise RuntimeError("A character is already logged in. Start from a menu screen.")
                if self.cfg.get("create_missing") and hasattr(self, "retire_interrupted_routes"):
                    self.retire_interrupted_routes()
                for index, shard in enumerate(shards):
                    self.check()
                    if not is_supported(shard):
                        continue
                    if shard in excluded:
                        self.say("SKIPPED main shard: {}".format(shard))
                        continue
                    if creation_only and hasattr(self, 'seed_record'):
                        from account_profiles import shard_seed_complete
                        _, saved_seed = self.seed_record(shard)
                        full_cap = int(self.cfg.get('account_cap',7))
                        if shard_seed_complete(saved_seed, full_cap):
                            self.say('SEEDER RESUME: {} already full; skipping without opening it.'.format(shard))
                            continue
                    if creation_only and self.cfg.get('reserve_transfer_slot'):
                        from recovery_rules import creation_limit
                        if creation_limit(self.cfg, shard) == 0:
                            self.say('TRANSFER SLOT: {} has one slot; Seeder leaves it unfilled.'.format(shard))
                            continue
                    slots = occupied_slots_for(self.cfg, shard)
                    shard_unavailable = False
                    sync_retries = 0
                    seen_character_hashes = set(self.gift_identity_history.get(shard, set()))
                    slot_index = 0
                    # A previously interrupted combined handoff must resume
                    # as SEEDER, not return to character slot clicks. Newly
                    # created characters may reorder the entire roster.
                    if self.cfg.get('create_missing', False) and hasattr(self, 'combined_shard_status'):
                        combined = self.combined_shard_status(shard)
                        if combined.get('status') == 'in_progress':
                            self.say('Unfinished Seeder handoff on {} found in saved progress. Resuming Seeder only.'.format(shard))
                            self.complete_combined_shard(index, shard, int(combined['next_slot']))
                            self.refresh_seeded_roster(shard)
                            continue
                        if combined.get('status') == 'complete':
                            self.say('Combined Seeder already finished {}; skipping character rows and advancing to next shard.'.format(shard))
                            continue
                    shard_seeded_to_capacity = False
                    while slot_index < len(slots):
                        slot_number = slots[slot_index]
                        key = "{}|{}".format(shard, slot_number)
                        if (not self.cfg.get('create_missing', False)
                                and shard not in self.roster_sensitive_shards
                                and key in self.completed):
                            self.say("Already completed: {} / slot {} (stable legacy roster)".format(shard, slot_number))
                            slot_index += 1
                            continue
                        busy_count = 0
                        transient_count = 0
                        while True:
                            self.check()
                            try:
                                self.say("{} / slot {} / attempt {}".format(
                                    shard, slot_number, busy_count + transient_count + 1))
                                reached=self.reach_characters(index)
                                if reached=='creation':
                                    raise EmptySlot('Shard {} has no characters; creation screen opened directly.'.format(shard))
                                if not self.enter_slot(index, slot_number - 1):
                                    transient_count += 1
                                    # A blank character row can simply leave the character list
                                    # visible; that is NOT an EmptySlot exception. Combined mode
                                    # must explicitly look for a *verified* New Character button.
                                    # Wait for two failed login attempts to avoid interpreting a
                                    # transient input failure as permission to create a character.
                                    if (self.cfg.get('create_missing', False)
                                            and transient_count >= 2
                                            and self.state() == 'characters'):
                                        self.title_identity_check(shard, wait_seconds=.2)
                                        if self.seed_new_available():
                                            self.say('Slot {} did not enter the world after {} tries, '
                                                     'but {} has a verified New Character button. '
                                                     'Starting opted-in Seeder; this slot is NOT '
                                                     'marked gift-complete.'.format(
                                                         slot_number, transient_count, shard))
                                            self.complete_combined_shard(
                                                index, shard, slot_number)
                                            self.refresh_seeded_roster(shard)
                                            shard_seeded_to_capacity = True
                                            self.say('Combined Seeder finished {}. Gift Cycler will skip all remaining character slots on this shard.'.format(shard))
                                            break
                                    if transient_count >= 3:
                                        self.say('SKIPPED (not completed): {} slot {} did not '
                                                 'enter world after three tries.'.format(
                                                     shard, slot_number))
                                        self.record_issue(shard, slot_number,
                                                          'world_entry_not_confirmed')
                                        break
                                    self.sleep(self.cfg['post_logout_seconds'])
                                    continue
                                fingerprint = (self.last_bridge or {}).get('name_sha256')
                                if not fingerprint or len(fingerprint) != 64:
                                    raise RuntimeError('Character entered the world but RE did not supply identity; refusing gift completion.')
                                if creation_only:
                                    self.say('SEEDER SLOT CHECK: existing character verified on {} / row {}. '
                                             'Logging out; gift progress is unchanged.'.format(shard, slot_number))
                                    self.logout()
                                    self.sleep(self.cfg['post_logout_seconds'])
                                    from recovery_rules import creation_limit
                                    if slot_number >= creation_limit(self.cfg, shard):
                                        self.complete_combined_shard(index, shard, slot_number + 1)
                                        shard_seeded_to_capacity = True
                                    break
                                if fingerprint in self.seeded_character_hashes.get(shard, set()):
                                    self.say('NEW CHARACTER at {} / slot {}: ineligible for this holiday gift; logging out without claiming completion.'.format(shard, slot_number))
                                    self.logout()
                                    self.sleep(self.cfg['post_logout_seconds'])
                                    break
                                if fingerprint in seen_character_hashes:
                                    self.say('Already visited this CHARACTER on {} (now row {}); not claiming again.'.format(shard, slot_number))
                                    self.logout()
                                    self.sleep(self.cfg['post_logout_seconds'])
                                    break
                                self.wait_gift(shard)
                                self.logout()
                                # Commit the identity only AFTER verified logout.
                                self._save_identity_progress(shard, fingerprint)
                                seen_character_hashes.add(fingerprint)
                                self.completed.add(key)
                                self._save_progress()
                                done += 1
                                self.emit("PROGRESS|{}|{}".format(done, total))
                                self.say("COMPLETE: {} / slot {}".format(shard, slot_number))
                                self.say("Waiting {}s after logout before next login.".format(
                                    self.cfg["post_logout_seconds"]))
                                self.sleep(self.cfg["post_logout_seconds"])
                                break
                            except OnlineBusy:
                                busy_count += 1
                                self.say("ONLINE CONFLICT: {} / slot {} (occurrence {}).".format(
                                    shard, slot_number, busy_count))
                                self.acknowledge_warning("online_busy")
                                if busy_count == 1:
                                    self.sleep(max(7, self.cfg["post_logout_seconds"]))
                                    continue
                                if busy_count == 2:
                                    self.countdown(int(self.cfg["online_cooldown_seconds"]),
                                                   "Account still online on {}".format(shard))
                                    continue
                                self.emit("ALERT|Still online after cooldown on {}; "
                                          "skipping remainder of shard for safety.".format(shard))
                                shard_unavailable = True
                                self.record_issue(shard, slot_number, "online_conflict_after_cooldown")
                                break
                            except SyncScreen:
                                sync_retries += 1
                                self.say("ORIGIN ERROR on {} ({} of 2).".format(shard, sync_retries))
                                self.acknowledge_warning("sync_error")
                                if sync_retries > 1:
                                    self.emit("ALERT|Repeated Origin communication failures; "
                                              "skipping remainder of {}.".format(shard))
                                    shard_unavailable = True
                                    self.record_issue(shard, slot_number, "repeated_synchronization_error")
                                    break
                                self.sleep(int(self.cfg["sync_retry_seconds"]))
                            except EmptySlot as exc:
                                if self.cfg.get('create_missing',False):
                                    if not hasattr(self,'complete_combined_shard'):
                                        raise RuntimeError('Seeder not installed in this worker.')
                                    self.say('New-character screen on {} slot {}; Seeder opt-in is enabled.'.format(shard,slot_number))
                                    self.complete_combined_shard(
                                        index, shard, slot_number,
                                        on_creation=(self.state() == 'new_character'
                                                     or self.seed_visible('seed_appearance')))
                                    self.refresh_seeded_roster(shard)
                                    shard_seeded_to_capacity = True
                                    self.say('Combined Seeder finished {}. Gift Cycler will advance to the next shard.'.format(shard))
                                    break
                                self.emit("ALERT|{} No automatic character creation was performed.".format(exc))
                                self.recover_empty_slot()
                                self.say("SKIPPED unoccupied/unverified slot {} on {} "
                                         "(not counted complete).".format(slot_number, shard))
                                self.record_issue(shard, slot_number, "empty_or_unverified_slot")
                                break
                        if shard_unavailable:
                            self.say("DEFERRED: {} has unfinished slots; none marked complete.".format(shard))
                            break
                        if shard_seeded_to_capacity:
                            # Creation inserts rows at the top. Never return to
                            # this shard's old slot numbers after the handoff.
                            break
                        slot_index += 1
                self.say("Finished included shards. Review deferred/empty-slot warnings and progress.")
            finally:
                self.bridge = None

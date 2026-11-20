"""Local-file IPC for the Razor Enhanced auto-start companion.

No network, credentials, or chat injection. Every logout is scoped to a
fresh GUI run and a particular instance of the RE bridge script.
"""
from __future__ import annotations

import json
import os
import secrets
import threading
import time
from pathlib import Path

from app_paths import app_dir
APP_DIR = app_dir()
SESSION = APP_DIR / 'bridge_session.json'
STATUS = APP_DIR / 'bridge_status.json'
COMMAND = APP_DIR / 'bridge_command.json'
ACK = APP_DIR / 'bridge_ack.json'
SESSION_TTL = 6.0
STATUS_TTL = 3.5
COMMAND_TTL = 4.0


def read_json(path):
    try:
        obj = json.loads(path.read_text(encoding='utf-8'))
        return obj if isinstance(obj, dict) else None
    except (FileNotFoundError, ValueError, OSError, UnicodeError):
        return None


def atomic_write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.' + secrets.token_hex(5) + '.tmp')
    try:
        temp.write_text(json.dumps(obj, ensure_ascii=False), encoding='utf-8')
        os.replace(str(temp), str(path))
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


def safe_unlink(path):
    try:
        path.unlink()
    except FileNotFoundError:
        pass


class BridgeCancelled(Exception):
    pass


class BridgeSession:
    """Heartbeats an active GUI run and validates specific bridge responses.

    Not an authentication protocol against local malware. Prevents accidental
    stale requests, most restart races, and unintended ordinary-game logouts.
    """
    def __init__(self, stop=None):
        self.stop = stop or threading.Event()
        self.run_id = secrets.token_hex(16)
        self._ending = threading.Event()
        self._thread = None
        self._lock = threading.Lock()
        self._started = False

    def _heartbeat(self):
        while not self._ending.is_set() and not self.stop.is_set():
            try:
                # If another process hijacked the shared session file, fail closed.
                existing = read_json(SESSION)
                if existing and existing.get('run_id') != self.run_id and float(existing.get('expires_at', 0)) > time.time():
                    self._ending.set()
                    return
                now = time.time()
                atomic_write(SESSION, {'protocol': 1, 'enabled': True,
                                       'run_id': self.run_id, 'updated_at': now,
                                       'expires_at': now + SESSION_TTL})
            except Exception:
                # An unavailable shared directory causes status validation to
                # fail; it must never create an automatic logout.
                pass
            self._ending.wait(.9)

    def start(self):
        if self._started:
            return self
        APP_DIR.mkdir(parents=True, exist_ok=True)
        previous = read_json(SESSION)
        if previous and previous.get('enabled') and float(previous.get('expires_at', 0)) > time.time():
            raise RuntimeError('Another active Krampuslauf bridge session was found. Close the other GUI or wait 7 seconds.')
        safe_unlink(COMMAND)
        safe_unlink(ACK)
        safe_unlink(STATUS)
        self._started = True
        now = time.time()
        atomic_write(SESSION, {'protocol': 1, 'enabled': True,
                               'run_id': self.run_id, 'updated_at': now,
                               'expires_at': now + SESSION_TTL})
        self._thread = threading.Thread(target=self._heartbeat, daemon=True, name='HolidayBridgeHeartbeat')
        self._thread.start()
        return self

    def abort(self):
        """Invalidate pending logout commands as quickly as possible on STOP."""
        self._ending.set()
        current = read_json(SESSION)
        if current and current.get('run_id') == self.run_id:
            safe_unlink(SESSION)
            safe_unlink(COMMAND)

    def close(self):
        self._ending.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        # Do not remove another running GUI's session.
        current = read_json(SESSION)
        if current and current.get('run_id') == self.run_id:
            safe_unlink(SESSION)
        safe_unlink(COMMAND) if not current or current.get('run_id') == self.run_id else None
        self._started = False

    def __enter__(self):
        return self.start()

    def __exit__(self, typ, value, traceback):
        self.close()

    def _check(self):
        if self.stop.is_set():
            self.abort()
            raise BridgeCancelled('Stopped by user')
        if self._ending.is_set():
            raise RuntimeError('Bridge session expired or was replaced. Stopped safely.')
        owner = read_json(SESSION)
        if not owner or owner.get('run_id') != self.run_id or float(owner.get('expires_at', 0)) <= time.time():
            raise RuntimeError('GUI bridge heartbeat missing. Stopped safely.')

    def get_status(self, minimum_start=None):
        self._check()
        data = read_json(STATUS)
        if not data or data.get('protocol') != 1 or data.get('run_id') != self.run_id:
            return None
        if not data.get('connected') or not data.get('shard') or not data.get('instance_id'):
            return None
        now = time.time()
        if not (now - STATUS_TTL <= float(data.get('seen_at', 0)) <= now + 1):
            return None
        if minimum_start is not None and float(data.get('started_at', 0)) < minimum_start - 1.5:
            return None
        return data

    def wait_status(self, timeout, minimum_start=None, expected_shard=None):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            data = self.get_status(minimum_start)
            if data:
                if expected_shard and data['shard'].strip().casefold() != expected_shard.strip().casefold():
                    raise RuntimeError('Wrong shard: expected {!r}, Razor Enhanced reports {!r}.'.format(expected_shard, data['shard']))
                return data
            time.sleep(.15)
        return None

    def request_logout(self, status, timeout=5.0):
        """Send single-use disconnect command, return only after bridge ACK."""
        self._check()
        fresh = self.get_status()
        if not fresh or fresh['instance_id'] != status['instance_id'] or fresh['shard'] != status['shard']:
            raise RuntimeError('Bridge instance changed before logout; refusing.')
        cmd_id = secrets.token_hex(12)
        issued = time.time()
        atomic_write(COMMAND, {'protocol': 1, 'action': 'logout',
                               'run_id': self.run_id, 'instance_id': fresh['instance_id'],
                               'shard': fresh['shard'], 'command_id': cmd_id,
                               'issued_at': issued, 'expires_at': issued + COMMAND_TTL})
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self._check()
            ack = read_json(ACK)
            if (ack and ack.get('command_id') == cmd_id and
                    ack.get('instance_id') == fresh['instance_id'] and
                    ack.get('run_id') == self.run_id and ack.get('result') == 'accepted'):
                return True
            time.sleep(.1)
        raise RuntimeError('RE bridge did not acknowledge logout. Do not mark this character complete.')

    def request_route_inn(self, status, expected_name_hash, waypoints=None, timeout=100):
        """RE pathfinding with exact final-tile verification; no independent hotkey.

        Replies are correlated to this bridge instance and this request. A timeout
        is UNKNOWN, never permission to repeat character creation or disconnect.
        """
        self._check()
        fresh=self.get_status()
        if not fresh or fresh['instance_id'] != status['instance_id'] or fresh['shard'] != status['shard']:
            raise RuntimeError('Bridge instance changed before route; refusing.')
        if not expected_name_hash or fresh.get('name_sha256') != expected_name_hash:
            raise RuntimeError('Bridge character fingerprint mismatch. Refusing to route.')
        points=waypoints or [[4403,1170],[4403,1164]]
        if points != [[4403,1170],[4403,1164]]:
            raise RuntimeError('Only the user-tested Moonglow two-point route is enabled.')
        cmd_id=secrets.token_hex(12)
        issued=time.time()
        atomic_write(COMMAND, {'protocol':1,'action':'route_inn',
            'run_id':self.run_id,'instance_id':fresh['instance_id'],
            'shard':fresh['shard'],'command_id':cmd_id,
            'name_sha256':expected_name_hash,'waypoints':points,
            'issued_at':issued,'expires_at':issued+COMMAND_TTL})
        deadline=time.monotonic()+timeout
        started=False
        while time.monotonic()<deadline:
            self._check()
            ack=read_json(ACK)
            if ack and ack.get('command_id')==cmd_id and ack.get('run_id')==self.run_id and ack.get('instance_id')==fresh['instance_id']:
                state=ack.get('result')
                if state=='started':started=True
                elif state=='completed':
                    position=ack.get('position')
                    if position is None or [int(n) for n in position[:2]] != [4403,1164]:
                        raise RuntimeError('Route acknowledged without exact safe-tile coordinates.')
                    return position
                elif state=='failed':
                    raise RuntimeError('RE route failed: {}'.format(ack.get('error','unknown cause')))
            time.sleep(.16)
        raise RuntimeError('Route {} timed out (started={}). Character creation outcome is PENDING; do not resubmit.'.format(cmd_id,started))

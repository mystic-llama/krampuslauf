"""Conservative, recoverable Razor Enhanced character-link isolation.

Only modifies RazorEnhanced.NewProfiles inside RE's Profiles/ and Backup/.
Does not inspect RazorEnhanced.password, RazorEnhanced.shards, or profile folders.
All originals are backed up byte-for-byte outside the RE tree before changes.

Requires RE and Classic Client to be closed. This module has no Windows Forms
imports so that the safety and restoration rules can be tested independently.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import time
import uuid

import psutil

REGISTRY = 'RazorEnhanced.NewProfiles'
ACTIVE_MANIFEST = 'profile_isolation_active.json'
RECOVERY_DIR = 'profile_isolation_recovery'
MAX_REGISTRY_BYTES = 8 * 1024 * 1024
MAX_MANIFEST_BYTES = 64 * 1024
GAME_PROCESSES = {'client.exe', 'razorenhanced.exe', 'razorenhanced64.exe',
                  'razorenhancedlauncher.exe', 'razor enhanced.exe', 'razor.exe'}


class IsolationError(RuntimeError):
    pass


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _checked_path(value, stored=False):
    """Reject redirected paths before resolving them (including Windows junctions).

    Recovery JSON is user-writable input, never authority to select arbitrary
    files. These checks constrain it; they are not a local-malware sandbox.
    """
    if not isinstance(value, (str, Path)) or not str(value):
        raise IsolationError('Profile recovery path is invalid.')
    if str(value).startswith(('\\\\', '//')):
        raise IsolationError('Profile recovery requires local folders, not network or device paths.')
    path = Path(value).expanduser()
    if '..' in path.parts or (stored and not path.is_absolute()):
        raise IsolationError('Profile recovery path is invalid.')
    path = path.absolute()
    # lstat keeps the link itself visible; resolve() first would hide it.
    for part in (*reversed(path.parents), path):
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if (stat.S_ISLNK(info.st_mode) or
                getattr(info, 'st_file_attributes', 0) & 0x400):
            raise IsolationError('Linked profile or recovery paths are unsupported.')
    return path


def _read_limited(path, limit=MAX_REGISTRY_BYTES):
    path = _checked_path(path)
    if not stat.S_ISREG(path.stat().st_mode):
        raise IsolationError('Profile recovery expected a regular file.')
    with path.open('rb') as source:
        data = source.read(limit + 1)
    if len(data) > limit:
        raise IsolationError('Profile recovery file exceeds the safety size limit.')
    return data


def ensure_closed():
    """Fail closed if processes cannot be examined or when UO/RE is running."""
    running = set()
    try:
        for process in psutil.process_iter(attrs=['name']):
            name = str(process.info.get('name') or '').strip().lower()
            if name in GAME_PROCESSES or (name.startswith('razorenhanced') and name.endswith('.exe')):
                running.add(name)
    except (psutil.Error, OSError) as exc:
        raise IsolationError('Unable to check running processes; close RE and Classic Client and retry: ' + str(exc))
    if running:
        raise IsolationError('Close Razor Enhanced AND Classic Client first (running: {}).'.format(
            ', '.join(sorted(running))))


def normalize_root(folder):
    root = _checked_path(folder)
    if root.name.lower() in ('profiles', 'backup'):
        root = root.parent
    if not root.is_dir() or not (root / 'Profiles').is_dir() or not (root / 'Backup').is_dir():
        raise IsolationError('Select the Razor Enhanced data folder containing BOTH Profiles and Backup.')
    for name in ('Profiles', 'Backup'):
        _checked_path(root / name)
    return root


def registry_paths(root):
    root = normalize_root(root)
    # On Windows these names are case-insensitive, but matching them explicitly
    # also supports the test runner's case-sensitive filesystem.
    results = []
    for subdir in ('Profiles', 'Backup'):
        parent = root / subdir
        candidates = [p for p in parent.iterdir() if p.is_file() and p.name.casefold() == REGISTRY.casefold()]
        if len(candidates) > 1:
            raise IsolationError('Ambiguous registry files in {}.'.format(subdir))
        path = candidates[0] if candidates else parent / REGISTRY
        _checked_path(path)
        results.append(path)
    return results


def parse_registry(data):
    if len(data) > MAX_REGISTRY_BYTES:
        raise IsolationError('Razor profile registry exceeds the 8 MB safety limit.')
    try:
        parsed = json.loads(data.decode('utf-8-sig'))
    except (UnicodeError, ValueError) as exc:
        raise IsolationError('Cannot parse RazorEnhanced.NewProfiles as JSON: ' + str(exc))
    if not isinstance(parsed, list) or not parsed:
        raise IsolationError('Expected a non-empty list of Razor profile records.')
    names = set()
    defaults = 0
    for record in parsed:
        if not isinstance(record, dict) or not isinstance(record.get('Name'), str) or not record['Name'].strip():
            raise IsolationError('Registry contains an invalid profile name.')
        if not isinstance(record.get('Players'), list):
            raise IsolationError('Registry contains an invalid Players array.')
        name = record['Name'].strip().casefold()
        if name in names:
            raise IsolationError('Registry contains duplicate profile names.')
        names.add(name)
        defaults += name == 'default'
    if defaults != 1:
        raise IsolationError('Registry must contain exactly one default profile.')
    return parsed


def make_unlinked(data):
    """Preserve ALL registered names and unknown fields; change only links/Last."""
    profiles = parse_registry(data)
    changed = []
    removed_links = 0
    for record in profiles:
        item = dict(record)
        removed_links += len(item['Players'])
        item['Players'] = []
        item['Last'] = item['Name'].strip().casefold() == 'default'
        changed.append(item)
    payload = (json.dumps(changed, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    return payload, len(changed), removed_links


def _atomic_bytes(path, data):
    """Same-directory temporary file + fsync + atomic replace."""
    path = _checked_path(path)
    fd, temp_name = tempfile.mkstemp(prefix='.krampuslauf-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        _checked_path(path)
        os.replace(temp_name, str(path))
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _atomic_json(path, obj):
    _atomic_bytes(path, (json.dumps(obj, indent=2) + '\n').encode('utf-8'))


def _manifest_path(app_dir):
    return _checked_path(Path(app_dir) / ACTIVE_MANIFEST)


def _validate_session(session, app_dir):
    """Bind old schema-1 records to the two registry files and local backups."""
    if (not isinstance(session, dict) or session.get('schema') != 1 or
            session.get('state') not in ('preparing', 'active') or
            not isinstance(session.get('files'), list) or len(session['files']) != 2):
        raise IsolationError('Profile recovery record is invalid. Keep the original backups.')
    root = normalize_root(_checked_path(session.get('root'), stored=True))
    targets = registry_paths(root)
    recovery_parent = _checked_path(Path(app_dir) / RECOVERY_DIR)
    backup_dir = _checked_path(session.get('backup_dir'), stored=True)
    if (backup_dir.parent != recovery_parent or not backup_dir.is_dir() or
            not re.fullmatch(r'\d{8}_\d{6}_[0-9a-f]{10}', backup_dir.name)):
        raise IsolationError('Profile recovery backup folder is invalid.')
    _checked_path(backup_dir / 'RESTORED.json')
    if not re.fullmatch(r'[0-9a-f]{64}', str(session.get('temporary_hash', ''))):
        raise IsolationError('Profile recovery checksum is invalid.')
    for item, target, backup_name in zip(
            session['files'], targets, ('Profiles.original', 'Backup.original')):
        if not isinstance(item, dict) or type(item.get('existed')) is not bool:
            raise IsolationError('Profile recovery file record is invalid.')
        if (_checked_path(item.get('path'), stored=True) != target or
                _checked_path(item.get('backup'), stored=True) != backup_dir / backup_name):
            raise IsolationError('Profile recovery paths do not match the saved Razor folders.')
        digest = item.get('original_hash')
        if ((item['existed'] and not re.fullmatch(r'[0-9a-f]{64}', str(digest))) or
                (not item['existed'] and digest is not None)):
            raise IsolationError('Profile recovery checksum is invalid.')
    if session['files'][0]['existed'] is not True:
        raise IsolationError('Profile recovery requires an original Profiles registry.')
    return session


def get_session(app_dir):
    try:
        path = _manifest_path(app_dir)
        if not path.exists():
            return None
        session = json.loads(_read_limited(path, MAX_MANIFEST_BYTES).decode('utf-8'))
        return _validate_session(session, app_dir)
    except (ValueError, OSError, TypeError) as exc:
        raise IsolationError('Profile isolation recovery record is unreadable. Do NOT prepare again. ' + str(exc))


def session_status(app_dir):
    """Never exposes account names or the content of private Razor settings."""
    session = get_session(app_dir)
    if session is None:
        return {'active': False, 'status': 'Not prepared'}
    states = []
    for item in session['files']:
        path = Path(item['path'])
        content = _read_limited(path) if path.exists() else None
        digest = sha256_bytes(content) if content is not None else None
        if digest == session['temporary_hash']:
            states.append('temporary')
        elif digest == item['original_hash']:
            states.append('original')
        elif digest is None and not item['existed']:
            states.append('original')
        else:
            states.append('modified')
    if states == ['temporary', 'temporary']:
        status = 'Active: all character links isolated'
    elif 'modified' in states:
        status = 'Recovery needed: RE changed the registry during isolation'
    else:
        status = 'Incomplete transaction: restore before continuing'
    return {'active': True, 'status': status, 'states': states,
            'profiles': session.get('profile_count', 0),
            'links': session.get('link_count', 0)}


def prepare(root, app_dir):
    """Backup both originals, then atomically apply one temporary registry to both."""
    ensure_closed()
    app_dir = _checked_path(app_dir)
    app_dir.mkdir(parents=True, exist_ok=True)
    if get_session(app_dir) is not None:
        raise IsolationError('An earlier profile isolation is still active or needs recovery. Restore it first.')
    paths = registry_paths(root)
    if not paths[0].is_file():
        raise IsolationError('Profiles/RazorEnhanced.NewProfiles is missing. Launch RE normally once, close it, and retry.')
    if not (paths[0].parent / 'default').is_dir():
        raise IsolationError('Profiles/default folder is missing. Configure the default profile in Razor first.')
    contents = [_read_limited(p) if p.exists() else None for p in paths]
    template, count, links = make_unlinked(contents[0])
    if contents[1] is not None:
        parse_registry(contents[1])  # Backup may be stale; preserve its original bytes anyway.
    recovery_parent = _checked_path(app_dir / RECOVERY_DIR)
    recovery_parent.mkdir(parents=True, exist_ok=True)
    session_dir = recovery_parent / (time.strftime('%Y%m%d_%H%M%S') + '_' + uuid.uuid4().hex[:10])
    session_dir.mkdir(mode=0o700)
    file_records = []
    for index, (path, content) in enumerate(zip(paths, contents)):
        backup_path = session_dir / ('Profiles.original' if index == 0 else 'Backup.original')
        if content is not None:
            with backup_path.open('xb') as file:
                file.write(content)
                file.flush()
                os.fsync(file.fileno())
            if sha256_bytes(_read_limited(backup_path)) != sha256_bytes(content):
                raise IsolationError('Original backup verification failed; nothing was modified.')
        file_records.append({'path': str(path), 'backup': str(backup_path), 'existed': content is not None,
                             'original_hash': sha256_bytes(content) if content is not None else None})
    manifest = {'schema': 1, 'state': 'preparing', 'created_at': time.time(),
                'root': str(normalize_root(root)), 'backup_dir': str(session_dir),
                'files': file_records, 'temporary_hash': sha256_bytes(template),
                'profile_count': count, 'link_count': links}
    _validate_session(manifest, app_dir)
    # Publishing the manifest BEFORE touching Razor makes a crash recoverable.
    _atomic_json(_manifest_path(app_dir), manifest)
    for item, original in zip(file_records, contents):
        target = Path(item['path'])
        now = _read_limited(target) if target.exists() else None
        if now != original:
            raise IsolationError('Registry changed after backup; restore the saved session before retrying.')
        _atomic_bytes(target, template)
        if sha256_bytes(_read_limited(target)) != manifest['temporary_hash']:
            raise IsolationError('Temporary registry verification failed; use Restore Original Profiles.')
    manifest['state'] = 'active'
    _atomic_json(_manifest_path(app_dir), manifest)
    return session_status(app_dir)


def restore(app_dir, allow_modified=False):
    """Restore exact original bytes; refuse divergence unless user explicitly approves."""
    ensure_closed()
    app_dir = _checked_path(app_dir)
    session = get_session(app_dir)
    if session is None:
        raise IsolationError('There is no active Krampuslauf profile isolation to restore.')
    status = session_status(app_dir)
    if 'modified' in status['states'] and not allow_modified:
        raise IsolationError('Razor has modified one of the temporary registries. ' 
                             'Review and explicitly approve restoring originals; current changes will be replaced.')
    originals = []
    # Validate every backup BEFORE writing either location.
    for item in session['files']:
        if item['existed']:
            backup = Path(item['backup'])
            if not backup.is_file():
                raise IsolationError('An original backup is missing. STOP: restoration was not attempted.')
            original = _read_limited(backup)
            if sha256_bytes(original) != item['original_hash']:
                raise IsolationError('Original backup failed checksum verification. STOP: no files changed.')
            parse_registry(original)
            originals.append(original)
        else:
            originals.append(None)
    _validate_session(session, app_dir)
    for item, original in zip(session['files'], originals):
        target = _checked_path(item['path'])
        if original is None:
            if target.exists():
                if not target.is_file():
                    raise IsolationError('Cannot safely remove non-file registry path.')
                target.unlink()
        else:
            _atomic_bytes(target, original)
    for item, original in zip(session['files'], originals):
        path = Path(item['path'])
        if original is not None and (not path.is_file() or sha256_bytes(_read_limited(path)) != item['original_hash']):
            raise IsolationError('Restoration failed verification. Recovery copies are still available.')
        if original is None and path.exists():
            raise IsolationError('Restoration did not remove the generated registry. Recovery needed.')
    # Immutable originals remain in recovery_dir; archive completed metadata too.
    completed_path = Path(session['backup_dir']) / 'RESTORED.json'
    session['state'] = 'restored'
    session['restored_at'] = time.time()
    _atomic_json(completed_path, session)
    _manifest_path(app_dir).unlink()
    return {'active': False, 'status': 'Restored original Razor profile registries; recovery copies retained'}

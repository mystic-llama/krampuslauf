"""Recovery metadata must never authorize writes outside the two registries.

All targets, including the simulated outside file, live in pytest's temporary
directory. No real Razor settings or privileged OS files are accessed.
"""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import profile_isolation as pi
from ui_guidance import explain_error


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    monkeypatch.setattr(pi, 'ensure_closed', lambda: None)
    root, app = tmp_path / 'Razor', tmp_path / 'appdata'
    (root / 'Profiles' / 'default').mkdir(parents=True)
    (root / 'Backup').mkdir()
    original = b'[{"Name":"default","Players":[{"PlayerName":"Example"}],"Last":true}]'
    targets = [root / part / pi.REGISTRY for part in ('Profiles', 'Backup')]
    for target in targets:
        target.write_bytes(original)
    pi.prepare(root, app)
    return SimpleNamespace(root=root, app=app, targets=targets, original=original,
                           manifest=app / pi.ACTIVE_MANIFEST,
                           session=pi.get_session(app))


def save_record(p):
    p.manifest.write_text(json.dumps(p.session), encoding='utf-8')


@pytest.mark.parametrize('delete', [False, True])
def test_tampered_target_cannot_overwrite_or_delete_an_outside_file(prepared, tmp_path, delete):
    p = prepared
    outside = tmp_path / 'unrelated-file.txt'
    outside.write_bytes(b'keep this file')
    item = p.session['files'][1]
    item['path'] = str(outside)
    if delete:
        item['existed'], item['original_hash'] = False, None
    save_record(p)
    before = [f.read_bytes() for f in p.targets]
    with pytest.raises(pi.IsolationError):
        pi.restore(p.app, allow_modified=True)
    assert outside.read_bytes() == b'keep this file'
    assert [f.read_bytes() for f in p.targets] == before
    assert p.manifest.exists()


@pytest.mark.parametrize('change', ['backup', 'archive', 'swapped', 'relative', 'network', 'traversal'])
def test_recovery_locations_are_constrained(prepared, tmp_path, change):
    p = prepared
    if change == 'backup':
        outside = tmp_path / 'copy.original'
        outside.write_bytes(p.original)
        p.session['files'][0]['backup'] = str(outside)
    elif change == 'archive':
        p.session['backup_dir'] = str(tmp_path)
    elif change == 'swapped':
        p.session['files'].reverse()
    elif change == 'relative':
        p.session['files'][0]['path'] = 'Profiles/' + pi.REGISTRY
    elif change == 'network':
        p.session['root'] = r'\\untrusted-host\share'
    else:
        p.session['files'][0]['path'] = str(p.root / 'Backup' / '..' / 'Profiles' / pi.REGISTRY)
    save_record(p)
    before = [f.read_bytes() for f in p.targets]
    with pytest.raises(pi.IsolationError):
        pi.restore(p.app, allow_modified=True)
    assert [f.read_bytes() for f in p.targets] == before


@pytest.mark.parametrize('record', [[], None, {}, {'schema': 1, 'files': [None, None]},
                                  {'schema': 1, 'files': 'xx', 'state': 'active'}])
def test_malformed_records_fail_with_a_profile_error(prepared, record):
    prepared.session = record
    save_record(prepared)
    with pytest.raises(pi.IsolationError):
        pi.get_session(prepared.app)


def test_tampered_backup_with_matching_checksum_still_requires_registry_format(prepared):
    p = prepared
    item = p.session['files'][1]
    invalid = b'not a Razor profile registry'
    Path(item['backup']).write_bytes(invalid)
    item['original_hash'] = pi.sha256_bytes(invalid)
    save_record(p)
    before = [f.read_bytes() for f in p.targets]
    with pytest.raises(pi.IsolationError):
        pi.restore(p.app)
    assert [f.read_bytes() for f in p.targets] == before


def test_manifest_size_is_bounded(prepared):
    prepared.manifest.write_bytes(b' ' * (pi.MAX_MANIFEST_BYTES + 1))
    with pytest.raises(pi.IsolationError, match='size limit'):
        pi.get_session(prepared.app)


def link_or_skip(link, target, directory=False):
    try:
        link.symlink_to(target, target_is_directory=directory)
    except OSError as error:
        pytest.skip('Test host cannot create symbolic links: ' + str(error))


@pytest.mark.parametrize('location', ['target', 'backup', 'archive', 'manifest', 'directory'])
def test_links_are_rejected_before_restore(prepared, tmp_path, location):
    p = prepared
    if location == 'directory':
        folder = p.root / 'Profiles'
        moved = p.root / 'MovedProfiles'
        folder.rename(moved)
        link_or_skip(folder, moved, True)
        target = moved / pi.REGISTRY
    else:
        target = {'target': p.targets[0], 'backup': Path(p.session['files'][0]['backup']),
                  'archive': Path(p.session['backup_dir']) / 'RESTORED.json',
                  'manifest': p.manifest}[location]
        moved = tmp_path / (location + '-outside')
        moved.write_bytes(target.read_bytes() if target.exists() else b'keep outside')
        target.unlink(missing_ok=True)
        link_or_skip(target, moved)
        target = moved
    before = target.read_bytes()
    with pytest.raises(pi.IsolationError):
        pi.restore(p.app, allow_modified=True)
    assert target.read_bytes() == before


def test_linked_root_is_not_hidden_by_path_resolution(prepared, tmp_path):
    link = tmp_path / 'RazorLink'
    link_or_skip(link, prepared.root, True)
    with pytest.raises(pi.IsolationError, match='Linked'):
        pi.normalize_root(link)


def test_windows_reparse_attribute_is_rejected_without_following_it(prepared, monkeypatch):
    original = Path.lstat
    def lstat(path, *args, **kwargs):
        info = original(path, *args, **kwargs)
        if path == prepared.root / 'Profiles':
            return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400)
        return info
    monkeypatch.setattr(Path, 'lstat', lstat)
    with pytest.raises(pi.IsolationError, match='Linked'):
        pi.restore(prepared.app)


def test_recovery_error_has_a_clear_action_and_preserves_backups():
    advice = explain_error(pi.IsolationError('Profile recovery paths do not match the saved Razor folders.'))
    assert advice.page == 'profiles'
    assert 'Do not delete recovery files or prepare again' in advice.message
    assert 'Setup > Profiles' in advice.message

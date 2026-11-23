"""Read-only, pure recovery candidate selection for Krampuslauf Seeder.

Never infer that a pending final-submit succeeded. Only previously
world-confirmed (created) characters are eligible for route recovery.
"""

import hashlib


def current_seed_candidates(state, account_id):
    """Return validated (shard, character_name) candidates for one local history.

    No account identifiers are shown or stored here. A name's normalized hash
    is used only to identify the manually logged-in character via RE bridge.
    """
    profile = state.get('profiles', {}).get(account_id, {})
    if not isinstance(profile, dict):
        raise ValueError('Seeder progress has an invalid local history record.')
    results = []
    for shard, rec in profile.items():
        if not isinstance(rec, dict):
            continue
        created = rec.get('created', [])
        completed = rec.get('completed', [])
        if not isinstance(created, list) or not isinstance(completed, list):
            raise ValueError('Seeder progress contains invalid creation lists for {}.'.format(shard))
        finished = set(completed)
        for name in created:
            if isinstance(name, str) and name and name not in finished:
                results.append((shard, name))
    return results


def name_fingerprint(name):
    return hashlib.sha256(name.strip().lower().encode('utf-8')).hexdigest()


def candidate_for_status(candidates, status):
    """Match only an actual RE world shard + character fingerprint, never a slot guess."""
    if not status or not status.get('connected'):
        return None
    shard = str(status.get('shard', '')).strip().casefold()
    fingerprint = status.get('name_sha256')
    matches = [(s, n) for s, n in candidates
               if s.strip().casefold() == shard and name_fingerprint(n) == fingerprint]
    if len(matches) > 1:
        raise ValueError('Multiple unfinished records match this character. Resolve saved history first.')
    return matches[0] if matches else None


def finish_seed_record(state, account_id, shard, name):
    """Only mutate an existing world-confirmed character after verified logout."""
    rec = state['profiles'][account_id][shard]
    if name not in rec.get('created', []):
        raise ValueError('Cannot finish a character that was never world-confirmed.')
    if rec.get('pending') == name:
        raise ValueError('Refusing to clear an ambiguous pending creation.')
    completed = rec.setdefault('completed', [])
    if name not in completed:
        completed.append(name)
    return state


def pending_seed_candidates(state, account_id):
    """Return unknown-outcome submits in this Seeder history; do not assume creation."""
    profile = state.get('profiles', {}).get(account_id, {})
    if not isinstance(profile, dict):
        raise ValueError('Invalid Seeder history profile.')
    candidates = []
    for shard, record in profile.items():
        if not isinstance(record, dict):
            continue
        name = record.get('pending')
        if name is None:
            continue
        if not isinstance(name, str) or not name.strip():
            raise ValueError('Invalid pending creation entry for {}.'.format(shard))
        candidates.append((shard, name))
    return candidates


def confirm_pending_not_created(state, account_id, shard, name):
    """Only after the operator manually checked that the named character is absent.

    Never call this from timeout, missing heartbeat, or button-detection logic.
    """
    record = state['profiles'][account_id][shard]
    if record.get('pending') != name:
        raise ValueError('Pending entry changed; refusing to clear.')
    if name in record.get('created', []) or name in record.get('completed', []):
        raise ValueError('Character already recorded as created/completed; refusing to clear.')
    _release_pending_name(record, name)
    record.setdefault('manual_resolutions', []).append({
        'name': name, 'decision': 'not_created', 'source': 'operator_confirmed'})
    return state


def archive_pending_after_menu(record):
    """Keep the attempt without assuming an unverified final submit failed."""
    name = record.get('pending')
    if not name:
        return None
    if name not in record.get('created', []) and name not in record.get('completed', []):
        attempts = record.setdefault('unconfirmed_creations', [])
        if name not in attempts:
            attempts.append(name)
    _release_pending_name(record, name)
    # The attempted submit may have changed the live roster and its next slot.
    record.pop('combined_shard', None)
    record.pop('reserved_seeder_shard', None)
    return name


def _release_pending_name(record, name):
    record['pending'] = None
    assignments = record.get('name_assignments') or {}
    if name not in record.get('created', []) and name not in record.get('completed', []):
        record['name_assignments'] = {slot: value for slot, value in assignments.items() if value != name}


def promote_pending_after_world_proof(state, account_id, shard, name, status):
    """Promote unknown outcome to CREATED only with matching live bridge identity."""
    record = state['profiles'][account_id][shard]
    if record.get('pending') != name:
        raise ValueError('Pending creation changed during recovery.')
    if candidate_for_status([(shard, name)], status) != (shard, name):
        raise ValueError('Live bridge shard or character fingerprint does not match pending name.')
    created = record.setdefault('created', [])
    if name not in created:
        created.append(name)
    record['pending'] = None
    return state


def end_seed_attempt(state, account_id, attempt_id):
    """Archive only this account's run state, retaining all evidence verbatim."""
    from copy import deepcopy
    archives = state.setdefault('archived_attempts', {})
    if attempt_id in archives:
        raise ValueError('Attempt archive already exists.')
    records = state.get('profiles', {}).get(account_id, {})
    archives[attempt_id] = {'account_id': account_id, 'records': deepcopy(records),
                            'decision': 'ended_by_operator'}
    state.setdefault('profiles', {})[account_id] = {}
    return state

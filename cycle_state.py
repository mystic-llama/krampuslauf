"""Cycle-specific progress without deleting permanent character creation history."""


def cycle_key(config, fallback=''):
    return str(config.get('gift_cycle_id') or fallback or '').strip()


def adopt_legacy_creations(state, account_id, cycle):
    """Tag old names once, conservatively treating them as new in this cycle.

    The caller backs up the original before persisting. Old handoff checkpoints
    are deliberately not guessed into a cycle; only explicitly tagged handoffs
    may skip an entire shard. Pending and completed records are never cleared.
    """
    changed = False
    profile = state.get('profiles', {}).get(account_id, {})
    if not cycle or not isinstance(profile, dict):
        return False
    for record in profile.values():
        if not isinstance(record, dict):
            continue
        names = list(record.get('created', [])) + list(record.get('unconfirmed_creations', []))
        names = [name for name in names if isinstance(name, str)]
        if isinstance(record.get('pending'), str) and record['pending']:
            names.append(record['pending'])
        if not names:
            continue
        tags = dict(record.get('creation_cycles') or {})
        for name in names:
            if name not in tags:
                tags[name] = cycle
                changed = True
        record['creation_cycles'] = tags
    return changed


def checkpoint_for_cycle(record, cycle):
    data = record.get('combined_shard', {})
    if cycle and isinstance(data, dict) and data.get('cycle_id') == cycle:
        return data
    return {}


def excluded_creation_names(record, cycle):
    """Exclude current-cycle/unknown-age creations and every unresolved pending name."""
    tags = record.get('creation_cycles') or {}
    attempted = list(record.get('created', [])) + list(record.get('unconfirmed_creations', []))
    names = [name for name in attempted if isinstance(name, str)
             and (name not in tags or not cycle or tags.get(name) == cycle)]
    pending = record.get('pending')
    if isinstance(pending, str) and pending:
        names.append(pending)
    return names

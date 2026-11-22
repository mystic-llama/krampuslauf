"""Stable local account identities and per-account settings; no game credentials."""
from copy import deepcopy
from seeder_rules import account_token

SLOTS = ('main',) + tuple('account{}'.format(number) for number in range(2, 16))
DEFAULT_NAMES = {'main': 'Main Account', **{
    'account{}'.format(number): 'Account {}'.format(number) for number in range(2, 16)}}
NICKNAME_LIMIT = 16
ACCOUNT_SETTINGS = ('excluded', 'shard_group', 'skip_slots', 'occupied_slots', 'account_cap',
                    'reserve_transfer_slot', 'seed_name_prefix', 'seed_naming_mode',
                    'seed_fantasy_style', 'seed_profession', 'seed_route_delay_seconds', 'appearance', 'create_missing',
                    'gift_wait', 'post_logout_seconds', 'online_cooldown_seconds', 'fast_last_shard', 'gift_cycle_id')


def new_catalog():
    # Keep the first three legacy identities; new slots get their own fixed IDs.
    return {'version': 2, 'selected': 'main', 'accounts': {
        slot: {'history_id': account_token('Seeder Session ' + 'ABC'[index]
                                         if index < 3 else 'Krampuslauf account {}'.format(index + 1)),
               'nickname': ''}
        for index, slot in enumerate(SLOTS)}}


def complete_catalog(saved):
    """Add new account slots without replacing existing identities or nicknames."""
    catalog = deepcopy(saved)
    defaults = new_catalog()
    accounts = catalog.setdefault('accounts', {})
    for slot, entry in defaults['accounts'].items():
        accounts.setdefault(slot, entry)
    catalog['version'] = defaults['version']
    if catalog.get('selected') not in SLOTS:
        catalog['selected'] = 'main'
    return catalog


def display_name(catalog, slot):
    return str(catalog['accounts'][slot].get('nickname', '')).strip() or DEFAULT_NAMES[slot]


def settings_snapshot(config):
    return {key: deepcopy(config[key]) for key in ACCOUNT_SETTINGS if key in config}


def shard_seed_complete(record, cap):
    checkpoint = record.get('standalone_seed', {})
    return (checkpoint.get('status') == 'complete' and checkpoint.get('cap') == cap
            and not record.get('pending'))


def migrate_overnight_history(config, profiles, history, log_lines, slot='account2'):
    """Preserve old IDs; restore only shard-completion facts present in logs."""
    import re
    catalog = new_catalog()
    primary = account_token('Seeder Session A')
    other = account_token('Seeder Session B')
    if slot == 'account2':
        catalog['accounts']['main']['history_id'] = other
        catalog['accounts']['account2']['history_id'] = primary
    catalog['selected'] = slot
    cfg, saved, state = deepcopy(config), deepcopy(profiles), deepcopy(history)
    cfg['selected_account_slot'] = slot
    cfg['account_history_id'] = primary
    saved.setdefault('profiles', {}).setdefault(primary, {}).update(settings_snapshot(cfg))
    evidence = {}
    for line in log_lines:
        match = re.search(r'No New button on (.+?)\.', line)
        if match:
            evidence[match.group(1)] = line
    restored = []
    for shard, record in state.get('profiles', {}).get(primary, {}).items():
        cap = 1 if shard.casefold() in ('mugen','siege perilous') else int(cfg.get('account_cap',7))
        if shard in evidence and not record.get('pending'):
            record['standalone_seed'] = {'status':'complete', 'cap':cap,
                'reason':'restored_from_full_shard_log', 'evidence':evidence[shard]}
            restored.append(shard)
    return cfg, saved, state, catalog, restored

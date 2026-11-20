"""Supported destinations, separate from the real client's physical list rows."""
UNSUPPORTED_SHARDS = frozenset(('siege perilous', 'mugen'))


def is_supported(name):
    return isinstance(name, str) and bool(name.strip()) and name.strip().casefold() not in UNSUPPORTED_SHARDS


def supported_shards(names):
    return [name for name in names if is_supported(name)]


def normalize_shards(config):
    """Migrate old full lists without losing row positions or touching history files."""
    listed = list(config.get('shards', []))
    physical = list(config.get('navigation_shards', listed))
    if any(not is_supported(name) for name in listed):
        physical = listed
    elif physical and supported_shards(physical) != listed:
        physical = listed
    config['navigation_shards'] = physical
    config['shards'] = supported_shards(listed)
    if 'excluded' in config:
        config['excluded'] = supported_shards(config['excluded'])
    for key in ('skip_slots', 'occupied_slots'):
        if isinstance(config.get(key), dict):
            config[key] = {name: value for name, value in config[key].items() if is_supported(name)}
    return config


def physical_index(config, index):
    target = config['shards'][index]
    if not is_supported(target):
        raise ValueError('This shard is not supported by Krampuslauf.')
    order = config.get('navigation_shards', config['shards'])
    if target not in order:
        raise ValueError('Client row positions are unknown. Scan the shard list before using scroll-arrow navigation.')
    return order.index(target)

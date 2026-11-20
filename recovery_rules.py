"""Pure slot-cap rules; no GUI/game imports."""
from shard_policy import UNSUPPORTED_SHARDS, is_supported
PVP_SHARDS = UNSUPPORTED_SHARDS  # Compatibility for old imports; these shards have no eligible slots.


def creation_limit(config, shard):
    """Maximum total characters to create up to; never limits gift eligibility."""
    capacity = int(config.get('account_cap', 7))
    if capacity not in (5, 6, 7):
        raise ValueError('Choose the actual account slot capacity: 5, 6 or 7.')
    if shard.strip().casefold() in PVP_SHARDS:
        return 0
    return capacity - int(bool(config.get('reserve_transfer_slot', False)))


def occupied_slots_for(config, shard):
    """Account-local slot selection; unsupported shards have no eligible slots."""
    if not is_supported(shard):
        return []
    # Gift Cycler defaults to trying available slots without a manual occupied map.
    # The opt-in skip list is for deliberately bypassing slots already handled manually.
    if config.get('auto_detect_slots', False):
        skip = set(config.get('skip_slots', {}).get(shard, []))
        if any(type(v) is not int or v < 1 or v > 7 for v in skip):
            raise ValueError('Invalid skip slot on {}'.format(shard))
        return [i for i in range(1, 8) if i not in skip]
    mapping = config.get("occupied_slots", {})
    account_cap = int(config.get("account_cap", 7))
    if account_cap not in (5, 6, 7):
        raise ValueError("Account slot capacity must be 5, 6 or 7")
    value = mapping.get(shard, list(range(1, account_cap + 1)))
    if isinstance(value, int):
        value = list(range(1, value + 1))
    if not isinstance(value, list) or not all(type(v) is int and 1 <= v <= 7 for v in value):
        raise ValueError("Invalid occupied slots for {}: {}".format(shard, value))
    if any(v > account_cap for v in value):
        raise ValueError("Slot rule for {} exceeds account capacity {}".format(shard, account_cap))
    return sorted(set(value))

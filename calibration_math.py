"""Pure, display-independent calibration migration and slot geometry."""

def migrate_calibration(config):
    """Import old six-point layout without losing any existing calibration.

    Old builds measured slots 1 and 7; new builds measure slots 1 and 2.
    We retain floating point precision to reconstruct positions 1..7.
    Creation NEXT stages reuse the existing common button position.
    """
    points = config.setdefault('points', {})
    if ('char_second' not in points and 'char_first' in points and
            'char_last' in points):
        first, last = points['char_first'], points['char_last']
        if len(first) == 2 and len(last) == 2:
            points['char_second'] = [first[n] + (last[n]-first[n])/6.0 for n in range(2)]
    if 'seed_next' not in points:
        for source in ('seed_appearance_next', 'seed_profession_next', 'seed_city_finish'):
            if source in points:
                points['seed_next'] = list(points[source]); break
    return config


def character_slot_point(points, slot_number):
    """Derive the requested 1-based slot from two row-center reference points."""
    if not 1 <= slot_number <= 7:
        raise ValueError('Character slot must be 1 through 7')
    first = points['char_first']
    if 'char_second' in points:
        second = points['char_second']
        return [round(first[n]+(slot_number-1)*(second[n]-first[n])) for n in range(2)]
    if 'char_last' in points:  # Read pre-v1.7.1 configurations safely.
        last = points['char_last']
        return [round(first[n]+(slot_number-1)*(last[n]-first[n])/6.0) for n in range(2)]
    raise ValueError('Calibrate character slots #1 and #2')



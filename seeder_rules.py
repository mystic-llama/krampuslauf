"""Krampuslauf character naming; deterministic, no account tokens in names."""
import hashlib
import re

SHARD_ABBREVIATIONS = {
    'Legends':'LEG', 'Atlantic':'ATL', 'Lake Superior':'LKS',
    'Great Lakes':'GRL', 'Chesapeake':'CHS', 'Catskills':'CAT',
    'Siege Perilous':'SGP', 'Origin':'ORG', 'Pacific':'PAC',
    'Sonoma':'SON', 'Lake Austin':'LKA', 'Baja':'BAJ',
    'Napa Valley':'NPV', 'Drachenfels':'DRC', 'Europa':'EUR',
    'Oceania':'OCN', 'Mugen':'MUG', 'Wakoku':'WAK',
    'Hokuto':'HOK', 'Formosa':'FOR', 'Izumo':'IZU',
    'Mizuho':'MIZ', 'Yamato':'YAM', 'Asuka':'ASU',
    'Arirang':'ARI', 'Balhae':'BAL', 'Sakura':'SAK',
}
# Accept common misspellings in historical/custom stored lists.
SHARD_ABBREVIATIONS['Isumo'] = 'IZU'

def account_token(nickname):
    """A private local key for *seeder progress only*, not a character name."""
    return hashlib.sha256(nickname.strip().casefold().encode('utf-8')).hexdigest()[:20]

def shard_abbreviation(shard):
    for name, abbrev in SHARD_ABBREVIATIONS.items():
        if name.casefold() == str(shard).strip().casefold():
            return abbrev
    raise ValueError('No abbreviation configured for shard {!r}; refusing to create a misnamed character.'.format(shard))

def generated_name(prefix, nickname, shard_index, creation_index, *, shard=None):
    """Format: `Llama LEG a`, `Llama ATL b` (1-10-letter prefix).

    `nickname` is a local seeder-history key, never included in names.
    creation_index is zero-based: 0 -> a, ... 6 -> g.
    """
    if shard is None:
        raise ValueError('A verified shard name is required to generate a character name.')
    prefix = str(prefix).strip()
    if not re.fullmatch(r'[A-Za-z]{1,10}', prefix):
        raise ValueError('Prefix must contain 1 to 10 letters (no spaces or digits).')
    index = int(creation_index)
    if index < 0 or index >= 7:
        raise ValueError('Creation slot must be A-G (creation_index 0-6).')
    name = '{} {} {}'.format(prefix, shard_abbreviation(shard), chr(ord('a') + index))
    if len(name) > 16:
        raise ValueError('Generated name exceeds 16 characters.')
    return name

def name_hash(name):
    return hashlib.sha256(name.strip().lower().encode('utf-8')).hexdigest()

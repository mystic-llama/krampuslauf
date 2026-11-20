"""Character-creation appearance options: pure rules, no GUI or game input.

Settings live in cfg['appearance']:
    enabled: bool             - off keeps the game's default appearance
    mode: 'fixed' | 'random'  - fixed: at most one tick per group
    sex, race: [names]        - none ticked = Male / Human
    styles: {group: [index]}  - none ticked = keep the game's default style
    skin: {race: [cell]}      - no cells = random; cell = row * columns + column
    hair_color, facial_color: {race: [cell]}
                              - no cells = keep the game's default colour
"""
from __future__ import annotations

import math
import random

SEXES = ('male', 'female')
RACES = ('human', 'elf', 'gargoyle')
PARTS = ('hair', 'facial')
PROFESSIONS = ('samurai', 'ninja', 'paladin', 'necromancer', 'warrior', 'mage', 'blacksmith')

def choose_profession(cfg, rng=None):
    value = cfg.get('seed_profession', 'blacksmith')
    if value == 'random':
        return (rng or random).choice(PROFESSIONS)
    if value not in PROFESSIONS:
        raise AppearanceError('Choose a supported profession or Randomize.')
    return value


_HORNS8 = tuple('Horn Style {}'.format(n) for n in range(1, 9))
STYLE_OPTIONS = {
    'human_male_hair': ('NONE', 'Short', 'Long', 'Pony Tail', 'Mohawk', 'Pageboy',
                        'Topknot', 'Curly', 'Receding', '2 Tails'),
    'human_male_facial': ('NONE', 'Goatee', 'Long Beard', 'Short Beard', 'Moustache',
                          'Short Beard & Moustache', 'Long Beard & Moustache', 'Vandyke'),
    'human_female_hair': ('NONE', 'Short', 'Long', 'Pony Tail', 'Mohawk', 'Pageboy',
                          'Topknot', 'Curly', '2 Tails', 'Buns'),
    'elf_male_hair': ('None', 'Mid Long', 'Long Feather', 'Short', 'Mullet', 'Long',
                      'Topknot', 'Long Braid', 'Spiked'),
    'elf_female_hair': ('None', 'Long Feather', 'Short', 'Mullet', 'Flower', 'Topknot',
                        'Long Braid', 'Buns', 'Spiked'),
    'gargoyle_male_hair': _HORNS8,
    'gargoyle_male_facial': tuple('Horn Style {}'.format(n) for n in range(1, 5)),
    'gargoyle_female_hair': _HORNS8,
}
STYLE_LABELS = {
    'human_male_hair': 'Male human · hair style',
    'human_male_facial': 'Male human · facial hair style',
    'human_female_hair': 'Female human · hair style',
    'elf_male_hair': 'Male elf · hair style',
    'elf_female_hair': 'Female elf · hair style',
    'gargoyle_male_hair': 'Male gargoyle · horn style',
    'gargoyle_male_facial': 'Male gargoyle · facial horn style',
    'gargoyle_female_hair': 'Female gargoyle · horn style',
}
# (columns, rows) of each in-game skin palette, matching assets/<race>_skin.png.
SKIN_GRIDS = {'human': (8, 8), 'elf': (4, 8), 'gargoyle': (4, 7)}
# Bounds are measured from the supplied palette crops, in the 640 x 480 game area.
# Gargoyle artwork trims a few pixels from the outside cells; keep those edges exact.
COLOR_BOUNDS = {
    'human': (tuple(range(0, 121, 20)), tuple(range(0, 281, 35))),
    'elf': (tuple(range(0, 121, 20)), tuple(range(0, 280, 31))),
    'gargoyle': ((0, 18, 38, 58, 78, 98, 117), (0, 91, 184, 273)),
}
COLOR_GRIDS = {race: (len(x) - 1, len(y) - 1) for race, (x, y) in COLOR_BOUNDS.items()}
COLOR_ASSETS = {
    'human': {'hair': 'hair_palette.png', 'facial': 'hair_palette.png'},
    'elf': {'hair': 'elf_hair.png'},
    'gargoyle': {'hair': 'gargoyle_horn.png', 'facial': 'gargoyle_facial_horn.png'},
}
COLOR_FIELDS = {'hair': 'hair_color', 'facial': 'facial_color'}
# Human cell size retained for compatibility; other races use COLOR_BOUNDS.
COLOR_CELL = (20, 35)

DEFAULT_APPEARANCE = {'enabled': False, 'mode': 'fixed', 'sex': [], 'race': [],
                      'styles': {}, 'skin': {}, 'hair_color': {}, 'facial_color': {}}


class AppearanceError(ValueError):
    pass


def settings(cfg):
    raw = cfg.get('appearance') if isinstance(cfg, dict) else None
    raw = raw if isinstance(raw, dict) else {}
    return {**DEFAULT_APPEARANCE, **raw,
            'styles': dict(raw.get('styles') or {}), 'skin': dict(raw.get('skin') or {}),
            'hair_color': dict(raw.get('hair_color') or {}), 'facial_color': dict(raw.get('facial_color') or {})}


def style_group(race, sex, part):
    """Style list for a combination, or None when it has no such list."""
    key = '{}_{}_{}'.format(race, sex, part)
    return key if key in STYLE_OPTIONS else None


def validate(cfg):
    """Problems that must be fixed before a creation run; [] when ready."""
    look = settings(cfg)
    if not look['enabled']:
        return []
    issues = []
    if look['mode'] not in ('fixed', 'random'):
        issues.append('Appearance mode must be Fixed or Random.')
    fixed = look['mode'] == 'fixed'
    for field, allowed in (('sex', SEXES), ('race', RACES)):
        values = look[field]
        if not isinstance(values, list) or any(v not in allowed for v in values):
            issues.append('Appearance {} selection is invalid.'.format(field))
        elif fixed and len(values) > 1:
            issues.append('Fixed appearance mode allows one {} only.'.format(field))
    for key, values in look['styles'].items():
        options = STYLE_OPTIONS.get(key)
        if options is None or not isinstance(values, list) or any(
                type(v) is not int or not 0 <= v < len(options) for v in values):
            issues.append('Appearance style list {} is invalid.'.format(key))
        elif fixed and len(values) > 1:
            issues.append('Fixed appearance mode allows one choice in {}.'.format(STYLE_LABELS[key]))
    for race, cells in look['skin'].items():
        grid = SKIN_GRIDS.get(race)
        if grid is None or not isinstance(cells, list) or any(
                type(c) is not int or not 0 <= c < grid[0] * grid[1] for c in cells):
            issues.append('Skin tone selection for {} is invalid.'.format(race))
        elif fixed and len(cells) > 1:
            issues.append('Fixed appearance mode allows one {} skin tone.'.format(race))
    for part, field in COLOR_FIELDS.items():
        for race, cells in look[field].items():
            grid = COLOR_GRIDS.get(race) if part in COLOR_ASSETS.get(race, {}) else None
            if grid is None or not isinstance(cells, list) or any(
                    type(c) is not int or not 0 <= c < grid[0] * grid[1] for c in cells):
                issues.append('{} selection for {} is invalid.'.format(field.replace('_', ' ').capitalize(), race))
            elif fixed and len(cells) > 1:
                issues.append('Fixed appearance mode allows one {} {}.'.format(race, field.replace('_', ' ')))
    return issues


def choose(cfg, rng=None):
    """The appearance for one new character, or None when customization is off.

    Returns race, sex, hair/facial list indices (None = keep the game default)
    and the skin cell (unselected shades are randomized).
    """
    look = settings(cfg)
    if not look['enabled']:
        return None
    issues = validate(cfg)
    if issues:
        raise AppearanceError(' '.join(issues))
    rng = rng or random.Random()
    pick = lambda values: rng.choice(values) if values else None
    race = pick(look['race']) or 'human'
    sex = pick(look['sex']) or 'male'
    result = {'race': race, 'sex': sex, 'hair': None, 'facial': None, 'skin': None,
              'hair_color': None, 'facial_color': None}
    for part in PARTS:
        key = style_group(race, sex, part)
        if key:
            result[part] = pick(look['styles'].get(key, []))
            # A bald or beardless choice has nothing to colour.
            bare = result[part] == 0 and STYLE_OPTIONS[key][0].lower() == 'none'
            if part in COLOR_ASSETS.get(race, {}) and not bare:
                result[COLOR_FIELDS[part]] = pick(look[COLOR_FIELDS[part]].get(race, []))
    result['skin'] = pick(look['skin'].get(race, []))
    if result['skin'] is None:
        cols, rows = SKIN_GRIDS[race]
        result['skin'] = rng.randrange(cols * rows)
    return result


def describe(choice):
    if not choice:
        return 'game default appearance'
    words = [choice['sex'].title(), choice['race'].title()]
    for part in PARTS:
        key = style_group(choice['race'], choice['sex'], part)
        if key and choice[part] is not None:
            words.append('{}: {}'.format(part, STYLE_OPTIONS[key][choice[part]]))
    if choice['skin'] is not None:
        words.append('skin cell {}'.format(choice['skin'] + 1))
    for part, field in COLOR_FIELDS.items():
        if choice.get(field) is not None:
            words.append('{} colour cell {}'.format(part, choice[field] + 1))
    return ', '.join(words)


def skin_cell_point(race, cell, first, last):
    """Centre of a palette cell from the recorded first and last cell centres."""
    cols, rows = SKIN_GRIDS[race]
    if not 0 <= cell < cols * rows:
        raise AppearanceError('Skin cell {} is outside the {} palette.'.format(cell, race))
    col, row = cell % cols, cell // cols
    fx = (last[0] - first[0]) / (cols - 1) if cols > 1 else 0
    fy = (last[1] - first[1]) / (rows - 1) if rows > 1 else 0
    return [round(first[0] + col * fx), round(first[1] + row * fy)]


def color_cell_bounds(race, cell):
    """Measured bounds within the supplied hair/horn palette crop."""
    cols, rows = COLOR_GRIDS[race]
    if type(cell) is not int or not 0 <= cell < cols * rows:
        raise AppearanceError('Colour cell {} is outside the {} palette.'.format(cell, race))
    x, y = COLOR_BOUNDS[race]
    col, row = cell % cols, cell // cols
    return x[col], y[row], x[col + 1], y[row + 1]


def color_cell_point(race, cell, origin):
    """Cell centre from the matched crop origin, in 640 x 480 game-area coordinates."""
    left, top, right, bottom = color_cell_bounds(race, cell)
    return [math.floor(origin[0] + (left + right) / 2 + .5),
            math.floor(origin[1] + (top + bottom) / 2 + .5)]


def list_item_point(index, first, spacing):
    """Dropdown row centre; every list shares the hair list's row spacing."""
    return [first[0], round(first[1] + index * spacing)]


def required_points(cfg):
    """Click points this appearance configuration needs, keyed by reason."""
    look = settings(cfg)
    if not look['enabled']:
        return []
    keys = ['app_sex_' + s for s in SEXES] + ['app_race_' + r for r in RACES]
    keys += ['app_hair_open', 'app_hair_item1', 'app_hair_item2',
             'app_facial_open', 'app_facial_item1']
    for race in (look['race'] or ['human']):
        if race in SKIN_GRIDS:
            keys += ['app_skin_open', 'app_skin_{}_first'.format(race),
                     'app_skin_{}_last'.format(race)]
    for part, field in COLOR_FIELDS.items():
        if any(look[field].get(race) and part in COLOR_ASSETS.get(race, {})
               and any(style_group(race, sex, part) for sex in (look['sex'] or ['male']))
               for race in (look['race'] or ['human'])):
            keys.append('app_{}_color_open'.format(part))
    return list(dict.fromkeys(keys))

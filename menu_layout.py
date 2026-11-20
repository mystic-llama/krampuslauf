"""Built-in Classic Client menu layout in 640 x 480 game-area coordinates.

Measured on the official Classic Client at 100% Windows scaling. Points are
click targets; regions are (left, top, right, bottom) marker search areas.
Marker images live in assets/screen_markers and are captured at 100% scale.
"""
from ui_assets import artwork_path

MARKER_FOLDER = 'screen_markers'

POINTS = {
    'first_row': (377, 114),
    'scroll_up': (537, 99),
    'scroll_down': (537, 354),
    'char_first': (477, 139),
    'char_second': (477, 179),
    'back': (592, 444),
    'login_button': (325, 381),
    'seed_new_button': (252, 405),
    'seed_name_field': (266, 81),
    'seed_next': (622, 444),
    'seed_profession_preset': (294, 393),
    'seed_profession_samurai': (294, 185),
    'seed_profession_ninja': (490, 185),
    'seed_profession_paladin': (294, 254),
    'seed_profession_necromancer': (490, 254),
    'seed_profession_warrior': (294, 324),
    'seed_profession_mage': (490, 324),
    'seed_city_moonglow': (402, 165),
    # Appearance screen: estimated from a screenshot; verify or record them.
    'app_race_gargoyle': (127, 443),
    'app_race_human': (236, 443),
    'app_race_elf': (236, 464),
    'app_sex_male': (482, 443),
    'app_sex_female': (482, 464),
    'app_hair_open': (205, 160),
    'app_hair_item1': (115, 160),
    'app_hair_item2': (115, 174),
    'app_facial_open': (205, 208),
    'app_facial_item1': (115, 208),
    'app_skin_open': (545, 163),
    # Colour swatches below Skin Tone, Shirt and Pants (45 px apart); estimated from a
    # screenshot. The opened palette itself is located on screen, not by a point.
    'app_hair_color_open': (550, 300),
    'app_facial_color_open': (550, 345),
    # Cell centres measured from open palettes, normalized to 640 x 480.
    'app_skin_human_first': (498, 155),
    'app_skin_human_last': (603, 400),
    'app_skin_elf_first': (504, 155),
    'app_skin_elf_last': (597, 400),
    'app_skin_gargoyle_first': (504, 158),
    'app_skin_gargoyle_last': (597, 398),
}

# Every recordable click point, in display order. Palette corners ship as
# built-in cell centres; recorded overrides remain available for missed clicks.
POINT_LABELS = (
    ('first_row', 'Shard list · first shard row (list at top)'),
    ('scroll_up', 'Shard list · scrollbar UP arrow'),
    ('scroll_down', 'Shard list · scrollbar DOWN arrow'),
    ('char_first', 'Characters · slot 1'),
    ('char_second', 'Characters · slot 2 (sets row spacing)'),
    ('back', 'Characters · Back button'),
    ('login_button', 'Login · Login button'),
    ('seed_new_button', 'Characters · New button'),
    ('seed_name_field', 'Creation · character name field'),
    ('seed_next', 'Creation · Next / Create arrow'),
    ('seed_profession_preset', 'Creation · profession template'),
    ('seed_city_moonglow', 'Creation · Moonglow on the city map'),
    ('app_race_human', 'Appearance · HUMAN button'),
    ('app_race_elf', 'Appearance · ELF button'),
    ('app_race_gargoyle', 'Appearance · GARGOYLE button'),
    ('app_sex_male', 'Appearance · MALE button'),
    ('app_sex_female', 'Appearance · FEMALE button'),
    ('app_hair_open', 'Appearance · hair / horn style dropdown arrow'),
    ('app_hair_item1', 'Appearance · open hair list, first row'),
    ('app_hair_item2', 'Appearance · open hair list, second row (row spacing)'),
    ('app_facial_open', 'Appearance · facial hair / horn dropdown arrow'),
    ('app_facial_item1', 'Appearance · open facial list, first row'),
    ('app_skin_open', 'Appearance · Skin Tone swatch (opens palette)'),
    ('app_hair_color_open', 'Appearance · Hair Color swatch (opens palette)'),
    ('app_facial_color_open', 'Appearance · Facial Hair Color swatch (opens palette)'),
    ('app_skin_human_first', 'Skin palette · human, top-left cell'),
    ('app_skin_human_last', 'Skin palette · human, bottom-right cell'),
    ('app_skin_elf_first', 'Skin palette · elf, top-left cell'),
    ('app_skin_elf_last', 'Skin palette · elf, bottom-right cell'),
    ('app_skin_gargoyle_first', 'Skin palette · gargoyle, top-left cell'),
    ('app_skin_gargoyle_last', 'Skin palette · gargoyle, bottom-right cell'),
)
POINT_LABELS += tuple(('seed_profession_' + key, 'Creation: ' + key.title() + ' profession')
                      for key in ('samurai', 'ninja', 'paladin', 'necromancer', 'warrior', 'mage'))
RECORDABLE = frozenset(key for key, _ in POINT_LABELS)

MARKER_REGIONS = {
    'login': (1, 1, 124, 335),
    'servers': (133, 360, 529, 416),
    'characters': (439, 401, 633, 461),
    'new_character': (19, 118, 263, 142),
    'online_busy': (103, 83, 530, 400),
    'sync_error': (108, 321, 530, 394),
    'seed_new_button': (212, 389, 293, 426),
    'seed_appearance': (19, 118, 263, 142),
    'seed_profession': (270, 37, 388, 134),
    'seed_city': (58, 51, 448, 441),
    'seed_moonglow_selected': (317, 133, 416, 193),
}


# Alternative crops are OR matches for the same screen, never new click targets.
# The header stays visible when Back/Start tooltips cover the corner crop.
MARKER_ALTERNATIVES = {
    'characters': (('characters_header', (144, 68, 577, 124)),),
}


def default_points():
    return {key: list(value) for key, value in POINTS.items()}


def valid_point(value):
    return (isinstance(value, (list, tuple)) and len(value) == 2
            and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in value)
            and 0 <= value[0] < 640 and 0 <= value[1] < 480)


def merged_points(overrides):
    """Built-in points with valid recorded overrides applied (640 x 480 space)."""
    points = default_points()
    for key, value in (overrides or {}).items():
        if key in RECORDABLE and valid_point(value):
            points[key] = [int(round(value[0])), int(round(value[1]))]
    return points


def marker_path(name):
    return artwork_path('{}/{}.png'.format(MARKER_FOLDER, name))

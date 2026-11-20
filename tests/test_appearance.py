"""Appearance rules, recorded click points and the engine's click sequence."""
import random

import pytest
from PIL import Image

import appearance
from appearance import (AppearanceError, STYLE_OPTIONS, SKIN_GRIDS, choose, describe,
                        list_item_point, required_points, skin_cell_point, validate)
from menu_layout import POINTS, POINT_LABELS, merged_points
from ui_assets import artwork_path


def cfg(**look):
    return {'appearance': {'enabled': True, **look}}


def test_style_lists_match_the_requested_options():
    assert len(STYLE_OPTIONS['human_male_hair']) == 10
    assert STYLE_OPTIONS['human_male_facial'][-1] == 'Vandyke'
    assert STYLE_OPTIONS['human_female_hair'][-1] == 'Buns'
    assert len(STYLE_OPTIONS['elf_male_hair']) == 9 and len(STYLE_OPTIONS['elf_female_hair']) == 9
    assert len(STYLE_OPTIONS['gargoyle_male_hair']) == 8 == len(STYLE_OPTIONS['gargoyle_female_hair'])
    assert len(STYLE_OPTIONS['gargoyle_male_facial']) == 4
    assert 'elf_male_facial' not in STYLE_OPTIONS and 'human_female_facial' not in STYLE_OPTIONS


def test_disabled_appearance_keeps_game_defaults():
    assert choose({}) is None and validate({}) == []
    assert required_points({}) == []


def test_fixed_mode_uses_the_single_choice_every_time():
    config = cfg(mode='fixed', sex=['female'], race=['elf'],
                 styles={'elf_female_hair': [4], 'human_male_hair': [2]}, skin={'elf': [9]})
    for seed in range(5):
        result = choose(config, random.Random(seed))
        assert result == {'race': 'elf', 'sex': 'female', 'hair': 4, 'facial': None, 'skin': 9,
                          'hair_color': None, 'facial_color': None}
    assert 'Flower' in describe(result)


def test_fixed_mode_rejects_more_than_one_choice_per_group():
    issues = validate(cfg(mode='fixed', race=['elf', 'human'], styles={'human_male_hair': [1, 2]},
                          skin={'human': [1, 2]}))
    assert len(issues) == 3
    with pytest.raises(AppearanceError):
        choose(cfg(mode='fixed', sex=['male', 'female']))


def test_random_mode_only_picks_ticked_options_and_skips_invalid_parts():
    config = cfg(mode='random', sex=['male', 'female'], race=['human', 'gargoyle'],
                 styles={'human_male_hair': [1, 3], 'human_male_facial': [7],
                         'gargoyle_male_facial': [0, 3]}, skin={'gargoyle': [27]})
    rng = random.Random(3)
    seen = set()
    for _ in range(200):
        r = choose(config, rng)
        seen.add((r['race'], r['sex']))
        if r['sex'] == 'female':
            assert r['facial'] is None
        if (r['race'], r['sex']) == ('human', 'male'):
            assert r['hair'] in (1, 3) and r['facial'] == 7
        if r['race'] == 'gargoyle':
            assert r['skin'] == 27 and r['hair'] is None
        else:
            assert 0 <= r['skin'] < 64
    assert len(seen) == 4


def test_no_ticks_means_male_human_with_default_styles():
    result = choose(cfg(mode='random'))
    assert 0 <= result.pop('skin') < 64
    assert result == {'race': 'human', 'sex': 'male', 'hair': None, 'facial': None,
                      'hair_color': None, 'facial_color': None}


def test_skin_cells_interpolate_between_recorded_corners():
    first, last = [500, 150], [570, 395]
    assert skin_cell_point('human', 0, first, last) == first
    assert skin_cell_point('human', 63, first, last) == last
    assert skin_cell_point('human', 9, first, last) == [510, 185]
    assert skin_cell_point('elf', 31, first, last) == last
    cols, rows = SKIN_GRIDS['gargoyle']
    assert skin_cell_point('gargoyle', cols * rows - 1, first, last) == last
    with pytest.raises(AppearanceError):
        skin_cell_point('elf', 32, first, last)


def test_skin_grids_match_the_supplied_palette_images():
    for race, (cols, rows) in SKIN_GRIDS.items():
        image = Image.open(artwork_path('{}_skin.png'.format(race)))
        width, height = image.size
        assert abs(width / cols - round(width / cols)) < 1 and height / rows > 30, race


def test_list_rows_use_the_hair_list_spacing():
    assert list_item_point(0, [115, 160], 14) == [115, 160]
    assert list_item_point(9, [115, 208], 14) == [115, 334]


def test_required_points_include_skin_corners_only_for_selected_races():
    keys = required_points(cfg(race=['elf'], skin={'elf': [1], 'human': []}))
    assert 'app_skin_elf_first' in keys and 'app_skin_human_first' not in keys
    assert 'app_race_gargoyle' in keys and 'app_hair_item2' in keys


def test_recorded_points_override_built_ins_and_bad_values_are_ignored():
    labels = dict(POINT_LABELS)
    assert set(POINTS) <= set(labels)
    points = merged_points({'first_row': [380.4, 116.6], 'back': [900, 10], 'unknown': [1, 1],
                            'app_skin_human_first': [500, 150]})
    assert points['first_row'] == [380, 117]
    assert points['back'] == list(POINTS['back'])
    assert 'unknown' not in points and points['app_skin_human_first'] == [500, 150]


def test_engine_clicks_race_sex_styles_then_skin(monkeypatch):
    import seeder_engine
    clicks, said = [], []
    points = {**merged_points({'app_skin_elf_first': [500, 150], 'app_skin_elf_last': [590, 395]})}
    worker = type('W', (seeder_engine.SeederOperations,), {})()
    worker.cfg = {'points': points, **cfg(mode='fixed', sex=['female'], race=['elf'],
                                          styles={'elf_female_hair': [2]}, skin={'elf': [5]})}
    worker.click = clicks.append
    worker.sleep = lambda s: None
    worker.say = said.append
    worker.apply_appearance()
    spacing = points['app_hair_item2'][1] - points['app_hair_item1'][1]
    assert clicks == [points['app_race_elf'], points['app_sex_female'], points['app_hair_open'],
                      [points['app_hair_item1'][0], points['app_hair_item1'][1] + 2 * spacing],
                      points['app_skin_open'], skin_cell_point('elf', 5, [500, 150], [590, 395])]
    assert 'Short' in said[-1]


def test_seed_one_selects_appearance_before_typing_the_name():
    source = open(appearance.__file__.replace('appearance.py', 'seeder_engine.py'), encoding='utf-8').read()
    body = source[source.index('    def seed_one('):]
    assert body.index('self.apply_appearance()') < body.index("self.click(self.cfg['points']['seed_name_field'])")


@pytest.mark.parametrize('race', appearance.RACES)
def test_unselected_skin_randomizes_within_each_races_palette(race):
    rng = random.Random(7)
    config = cfg(race=[race])
    cells = {choose(config, rng)['skin'] for _ in range(300)}
    cols, rows = SKIN_GRIDS[race]
    assert cells <= set(range(cols * rows))
    assert len(cells) > cols * rows // 2
    assert 'app_skin_' + race + '_first' in required_points(config)


def test_profession_choices_and_randomize():
    for profession in appearance.PROFESSIONS:
        assert appearance.choose_profession({'seed_profession': profession}) == profession
        key = 'seed_profession_preset' if profession == 'blacksmith' else 'seed_profession_' + profession
        assert 0 <= POINTS[key][0] < 640 and 0 <= POINTS[key][1] < 480
    rng = random.Random(5)
    assert {appearance.choose_profession({'seed_profession': 'random'}, rng)
            for _ in range(100)} == set(appearance.PROFESSIONS)
    with pytest.raises(AppearanceError):
        appearance.choose_profession({'seed_profession': 'advanced'})


@pytest.mark.parametrize('race,cols,rows,left,top,cell_width,cell_height', [
    ('human', 8, 8, 491, 138, 15, 35),
    ('elf', 4, 8, 489, 138, 31, 35),
    ('gargoyle', 4, 7, 489, 138, 31, 40),
])
def test_built_in_skin_targets_land_inside_every_measured_cell(
        race, cols, rows, left, top, cell_width, cell_height):
    from client_geometry import GameArea
    points = merged_points({})
    assert set(required_points(cfg(race=[race]))) <= set(points)
    first = points['app_skin_' + race + '_first']
    last = points['app_skin_' + race + '_last']
    for cell in range(cols * rows):
        col, row = cell % cols, cell // cols
        x, y = skin_cell_point(race, cell, first, last)
        x0, y0 = left + col * cell_width, top + row * cell_height
        assert x0 + 3 <= x <= x0 + cell_width - 3
        assert y0 + 3 <= y <= y0 + cell_height - 3
        for scale in (1, 1.25, 1.5):
            area = GameArea(100, 200, round(640 * scale), round(480 * scale))
            sx, sy = area.to_screen(x, y)
            assert 100 + x0 * scale < sx < 100 + (x0 + cell_width) * scale
            assert 200 + y0 * scale < sy < 200 + (y0 + cell_height) * scale


# --- hair and facial hair colours -------------------------------------------

def test_colour_palette_picture_matches_its_six_by_eight_grid():
    import cv2
    cols, rows = appearance.COLOR_GRIDS['human']
    image = cv2.imread(str(artwork_path('hair_palette.png')))
    cell_w, cell_h = appearance.COLOR_CELL
    assert image.shape[:2] == (rows * cell_h, cols * cell_w)
    for r in range(rows):
        for c in range(cols):
            cell = image[r * cell_h:(r + 1) * cell_h, c * cell_w:(c + 1) * cell_w].reshape(-1, 3)
            assert int((cell != cell[0]).any(axis=1).sum()) == 0, (c, r)


def test_colour_cell_points_come_from_the_palette_corner():
    assert appearance.color_cell_point('human', 0, (401, 137)) == [411, 155]
    assert appearance.color_cell_point('human', 47, (401, 137)) == [401 + 5 * 20 + 10, 137 + 7 * 35 + 18]
    assert appearance.color_cell_point('human', 7, (0, 0)) == [30, 53]
    with pytest.raises(AppearanceError):
        appearance.color_cell_point('human', 48, (0, 0))
    assert appearance.color_cell_point('elf', 0, (0, 0)) == [10, 16]
    assert appearance.color_cell_point('elf', 53, (0, 0)) == [110, 264]
    assert appearance.color_cell_point('gargoyle', 17, (0, 0)) == [108, 229]


def test_fixed_colours_are_used_for_every_character_and_described():
    config = cfg(mode='fixed', styles={'human_male_hair': [1], 'human_male_facial': [3]},
                 hair_color={'human': [10]}, facial_color={'human': [21]}, skin={'human': [5]})
    for seed in range(4):
        result = choose(config, random.Random(seed))
        assert result['hair_color'] == 10 and result['facial_color'] == 21
    assert 'hair colour cell 11' in describe(result) and 'facial colour cell 22' in describe(result)


def test_random_colours_come_only_from_the_ticked_cells():
    config = cfg(mode='random', hair_color={'human': [2, 9, 40]}, facial_color={'human': [5]})
    rng = random.Random(1)
    seen = {choose(config, rng)['hair_color'] for _ in range(200)}
    assert seen == {2, 9, 40}
    assert {choose(config, rng)['facial_color'] for _ in range(50)} == {5}


def test_no_colour_ticked_keeps_the_game_default():
    result = choose(cfg(mode='random', styles={'human_male_hair': [1]}))
    assert result['hair_color'] is None and result['facial_color'] is None


def test_colours_are_skipped_where_there_is_nothing_to_colour():
    # No facial list for women or elves, nothing to colour on a bald or beardless choice,
    # including race-specific palettes.
    config = cfg(mode='fixed', sex=['female'], hair_color={'human': [3]}, facial_color={'human': [4]})
    result = choose(config, random.Random(0))
    assert result['hair_color'] == 3 and result['facial_color'] is None
    bald = choose(cfg(mode='fixed', styles={'human_male_hair': [0], 'human_male_facial': [0]},
                      hair_color={'human': [3]}, facial_color={'human': [4]}), random.Random(0))
    assert bald['hair_color'] is None and bald['facial_color'] is None
    elf = choose(cfg(mode='fixed', race=['elf'], hair_color={'human': [3]}), random.Random(0))
    assert elf['hair_color'] is None and elf['facial_color'] is None


def test_colour_selections_are_validated():
    assert validate(cfg(mode='fixed', hair_color={'human': [47]}, facial_color={'human': [0]})) == []
    assert validate(cfg(mode='random', hair_color={'human': [0, 1, 2]})) == []
    for bad in ({'human': [48]}, {'human': [-1]}, {'human': ['3']}, {'elf': [54]}, {'gargoyle': [18]}, {'human': 'x'}):
        assert validate(cfg(mode='random', hair_color=bad)), bad
        assert validate(cfg(mode='random', facial_color=bad)), bad
    assert validate(cfg(mode='fixed', hair_color={'human': [1, 2]}))


def test_colour_swatch_points_are_required_only_when_a_colour_is_chosen():
    assert 'app_hair_color_open' not in required_points(cfg())
    keys = required_points(cfg(hair_color={'human': [1]}))
    assert 'app_hair_color_open' in keys and 'app_facial_color_open' not in keys
    keys = required_points(cfg(facial_color={'human': [1]}))
    assert 'app_facial_color_open' in keys
    assert 'app_hair_color_open' not in required_points(cfg(race=['elf'], hair_color={'human': [1]}))


def test_colour_swatches_ship_as_recordable_built_in_points():
    labels = dict(POINT_LABELS)
    for key in ('app_hair_color_open', 'app_facial_color_open'):
        assert key in POINTS and key in labels
        x, y = POINTS[key]
        assert 480 < x < 620 and 280 < y < 380
    assert merged_points({'app_hair_color_open': [551, 301]})['app_hair_color_open'] == [551, 301]


def seeding_worker(look, origin=(405, 120)):
    import seeder_engine
    clicks, said, searches = [], [], []
    worker = type('W', (seeder_engine.SeederOperations,), {})()
    worker.cfg = {'points': merged_points({}), **look}
    worker.click = clicks.append
    worker.sleep = lambda s: None
    worker.say = said.append
    worker.find_color_palette = lambda **kwargs: searches.append(kwargs) or origin
    return worker, clicks, said, searches


def test_engine_picks_hair_then_facial_colour_after_skin_by_finding_the_palette():
    worker, clicks, said, searches = seeding_worker(cfg(
        mode='fixed', styles={'human_male_hair': [1], 'human_male_facial': [3]}, skin={'human': [7]},
        hair_color={'human': [8]}, facial_color={'human': [30]}))
    worker.apply_appearance()
    p = merged_points({})
    assert clicks[-4:] == [p['app_hair_color_open'], appearance.color_cell_point('human', 8, (405, 120)),
                           p['app_facial_color_open'], appearance.color_cell_point('human', 30, (405, 120))]
    assert clicks.index(p['app_skin_open']) < clicks.index(p['app_hair_color_open'])
    assert len(searches) == 2 and 'hair colour cell 9' in said[-1]


def test_engine_makes_no_colour_clicks_when_none_is_chosen():
    worker, clicks, _, searches = seeding_worker(cfg(mode='fixed', styles={'human_male_hair': [1]}, skin={'human': [7]}))
    worker.apply_appearance()
    p = merged_points({})
    assert p['app_hair_color_open'] not in clicks and p['app_facial_color_open'] not in clicks and not searches


def test_engine_stops_before_naming_if_the_palette_never_opens():
    worker, clicks, _, _ = seeding_worker(cfg(mode='fixed', hair_color={'human': [8]}))
    def missing(**kwargs):
        raise RuntimeError('The colour palette did not appear')
    worker.find_color_palette = missing
    with pytest.raises(RuntimeError, match='palette did not appear'):
        worker.apply_appearance()
    assert clicks[-1] == merged_points({})['app_hair_color_open']


class FakeScreen:
    """Feeds find_color_palette a frame in which the palette picture sits at a known spot."""
    def __init__(self, monkeypatch, scale, with_palette=True, other=None, asset='hair_palette.png'):
        import cv2
        import numpy as np
        import threading
        import cycler_engine
        from client_geometry import GameArea
        rng = np.random.default_rng(3)
        w, h = round(640 * scale), round(480 * scale)
        frame = rng.integers(0, 255, (h, w, 3), dtype=np.uint8)
        image = cv2.imread(str(artwork_path(other or asset)))
        if scale != 1:
            image = cv2.resize(image, (round(image.shape[1] * scale), round(image.shape[0] * scale)),
                               interpolation=cv2.INTER_LINEAR)
        if with_palette or other:
            x, y = round(401 * scale), round(137 * scale)
            frame[y:y + image.shape[0], x:x + image.shape[1]] = image
        monkeypatch.setattr(cycler_engine.screen_capture, 'grab_bgr', lambda bbox: frame.copy())
        self.worker = cycler_engine.GameWorker.__new__(cycler_engine.GameWorker)
        self.worker.stop, self.worker.pause = threading.Event(), threading.Event()
        self.worker.game_area = lambda: GameArea(50, 40, w, h)
        self.worker.park_menu_cursor = lambda: None
        self.now = [0.0]
        self.worker.clock = lambda: self.now[0]
        self.worker.sleep = lambda s: self.now.__setitem__(0, self.now[0] + s)


@pytest.mark.parametrize('scale', [1.0, 1.25, 1.5])
def test_palette_is_found_where_it_opens_at_any_display_scale(monkeypatch, scale):
    screen = FakeScreen(monkeypatch, scale)
    x, y = screen.worker.find_color_palette()
    assert abs(x - 401) <= 1 and abs(y - 137) <= 1


@pytest.mark.parametrize('kind', ['absent', 'skin'])
def test_missing_or_wrong_palette_fails_closed_without_clicking(monkeypatch, kind):
    screen = FakeScreen(monkeypatch, 1.0, with_palette=False, other='human_skin.png' if kind == 'skin' else None)
    with pytest.raises(RuntimeError, match='palette did not appear'):
        screen.worker.find_color_palette(timeout=.5)


@pytest.mark.parametrize('race,grid', [('human', (6, 8)), ('elf', (6, 9)), ('gargoyle', (6, 3))])
def test_every_colour_click_lands_inside_its_measured_swatch(race, grid):
    import cv2
    from client_geometry import GameArea
    assert appearance.COLOR_GRIDS[race] == grid
    image = cv2.imread(str(artwork_path(appearance.COLOR_ASSETS[race]['hair'])))
    xs, ys = appearance.COLOR_BOUNDS[race]
    assert image.shape[:2] == (ys[-1], xs[-1])
    for cell in range(grid[0] * grid[1]):
        left, top, right, bottom = appearance.color_cell_bounds(race, cell)
        x, y = appearance.color_cell_point(race, cell, (401, 137))
        assert 401 + left < x < 401 + right
        assert 137 + top < y < 137 + bottom
        # Each crop cell is a solid swatch except for a few supplied cursor pixels.
        pixels = image[top:bottom, left:right].reshape(-1, 3)
        center = image[y - 137, x - 401]
        assert ((pixels == center).all(axis=1).mean()) > .97
        for scale in (1, 1.25, 1.5):
            sx, sy = GameArea(30, 40, round(640 * scale), round(480 * scale)).to_screen(x, y)
            assert 30 + (401 + left) * scale < sx < 30 + (401 + right) * scale
            assert 40 + (137 + top) * scale < sy < 40 + (137 + bottom) * scale


@pytest.mark.parametrize('race,sex,hair,facial', [
    ('elf', 'male', 53, None), ('elf', 'female', 40, None),
    ('gargoyle', 'male', 17, 11), ('gargoyle', 'female', 15, None)])
def test_creation_uses_the_selected_race_and_part_palette(race, sex, hair, facial):
    worker, clicks, _, searches = seeding_worker(cfg(
        mode='fixed', race=[race], sex=[sex], hair_color={race: [hair]},
        facial_color={'gargoyle': [11]}, skin={race: [0]}))
    choice = worker.apply_appearance()
    assert choice['hair_color'] == hair and choice['facial_color'] == facial
    assert searches == ([{'race': race, 'part': 'hair'}] +
                        ([{'race': race, 'part': 'facial'}] if facial is not None else []))
    assert appearance.color_cell_point(race, hair, (405, 120)) in clicks
    if facial is None:
        assert merged_points({})['app_facial_color_open'] not in clicks
    else:
        assert clicks[-1] == appearance.color_cell_point(race, facial, (405, 120))


def test_random_races_use_only_their_own_colour_choices():
    config = cfg(mode='random', race=['human', 'elf', 'gargoyle'], sex=['male', 'female'],
                 hair_color={'human': [1, 2], 'elf': [50, 53], 'gargoyle': [15, 17]},
                 facial_color={'human': [4], 'gargoyle': [11]})
    rng = random.Random(3)
    seen = set()
    for _ in range(200):
        choice = choose(config, rng)
        race = choice['race']; seen.add(race)
        assert choice['hair_color'] in config['appearance']['hair_color'][race]
        if choice['sex'] == 'female' or race == 'elf':
            assert choice['facial_color'] is None
        else:
            assert choice['facial_color'] in config['appearance']['facial_color'][race]
    assert seen == {'human', 'elf', 'gargoyle'}
    assert validate(cfg(facial_color={'elf': [0]}))
    assert validate(cfg(mode='fixed', hair_color={'elf': [1, 2]}))


@pytest.mark.parametrize('scale', [1.0, 1.25, 1.5])
@pytest.mark.parametrize('race,part', [('elf', 'hair'), ('gargoyle', 'hair'), ('gargoyle', 'facial')])
def test_new_palettes_are_located_at_each_display_scale(monkeypatch, scale, race, part):
    screen = FakeScreen(monkeypatch, scale, asset=appearance.COLOR_ASSETS[race][part])
    x, y = screen.worker.find_color_palette(race=race, part=part)
    assert abs(x - 401) <= 1 and abs(y - 137) <= 1


@pytest.mark.parametrize('wanted,shown', [('elf', 'human'), ('human', 'elf'),
                                         ('gargoyle', 'human'), ('elf', 'gargoyle')])
def test_a_different_races_palette_cannot_be_used(monkeypatch, wanted, shown):
    screen = FakeScreen(monkeypatch, 1, asset=appearance.COLOR_ASSETS[shown]['hair'])
    with pytest.raises(RuntimeError, match='palette did not appear'):
        screen.worker.find_color_palette(timeout=.3, race=wanted)


def test_template_cache_keeps_race_and_part_separate(monkeypatch):
    import numpy as np
    screen = FakeScreen(monkeypatch, 1)
    worker = screen.worker
    human = worker.color_palette_template(1, 'human', 'hair')
    elf = worker.color_palette_template(1, 'elf', 'hair')
    gargoyle = worker.color_palette_template(1, 'gargoyle', 'hair')
    facial = worker.color_palette_template(1, 'gargoyle', 'facial')
    assert human.shape == (280, 120, 3) and elf.shape == (279, 120, 3)
    assert gargoyle.shape == (273, 117, 3)
    assert np.array_equal(gargoyle, facial)
    assert worker.color_palette_template(1, 'human', 'hair') is human
    assert worker.color_palette_template(1, 'human', 'facial') is human
    with pytest.raises(RuntimeError, match='No facial colour palette'):
        worker.color_palette_template(1, 'elf', 'facial')

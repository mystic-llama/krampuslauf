"""Game-area coordinates, built-in menu layout and scaled marker recognition."""
import threading

import cv2
import numpy as np
import pytest
from PIL import Image

import cycler_engine
from client_geometry import BASE_HEIGHT, BASE_WIDTH, GameArea, menu_scale
from cycler_engine import CORE_MARKERS, OPTIONAL_MARKERS, SEED_MARKERS, GameWorker
from menu_layout import MARKER_REGIONS, POINTS, marker_path


@pytest.mark.parametrize('size,scale', [((640, 480), 1.0), ((800, 600), 1.25),
                                        ((960, 720), 1.5), ((1280, 960), 2.0)])
def test_uniformly_scaled_menu_areas_are_recognized(size, scale):
    assert menu_scale(*size) == pytest.approx(scale)


@pytest.mark.parametrize('size', [(656, 519), (652, 511), (1280, 720), (1920, 1080), (200, 150)])
def test_outer_window_sizes_and_non_menu_views_are_rejected(size):
    # 656 x 519 / 652 x 511 are the measured outer window, including frame and title bar.
    assert menu_scale(*size) is None


def test_game_area_reproduces_the_original_window_relative_calibration():
    # Measured client offset was (8, 31) with the window at the desktop origin.
    area = GameArea(8, 31, 640, 480)
    assert area.to_screen(*POINTS['first_row']) == (385, 145)
    assert area.to_screen(*POINTS['back']) == (600, 475)
    assert area.to_screen(*POINTS['login_button']) == (333, 412)


def test_points_scale_with_display_scaling_and_window_position():
    area = GameArea(1000, 200, 800, 600)
    assert area.to_screen(100, 100) == (1125, 325)
    assert area.to_screen(0, 0) == (1000, 200)


def test_clicks_refuse_non_menu_areas_and_points_outside_the_menu():
    with pytest.raises(RuntimeError, match='not a 640x480 menu screen'):
        GameArea(0, 0, 1280, 720).to_screen(10, 10)
    with pytest.raises(RuntimeError, match='outside the 640x480 game area'):
        GameArea(0, 0, 640, 480).to_screen(640, 10)


def test_region_bbox_is_scaled_and_clipped_to_the_game_area():
    area = GameArea(10, 20, 800, 600)
    assert area.region_to_screen((0, 0, 100, 40)) == (10, 20, 135, 70)
    assert area.region_to_screen((0, 0, 100, 40), margin=12) == (10, 20, 150, 85)
    assert area.region_to_screen((600, 460, 640, 480), margin=12) == (745, 580, 810, 620)


def test_built_in_points_and_regions_fit_inside_the_menu():
    for key, (x, y) in POINTS.items():
        assert 0 <= x < BASE_WIDTH and 0 <= y < BASE_HEIGHT, key
    for key, (x0, y0, x1, y1) in MARKER_REGIONS.items():
        assert 0 <= x0 < x1 <= BASE_WIDTH and 0 <= y0 < y1 <= BASE_HEIGHT, key


def test_every_marker_ships_and_matches_its_region_size():
    for name in CORE_MARKERS + OPTIONAL_MARKERS + SEED_MARKERS:
        path = marker_path(name)
        assert path is not None, name
        image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        x0, y0, x1, y1 = MARKER_REGIONS[name]
        assert image.shape == (y1 - y0, x1 - x0), name


def synthetic_menu(marker):
    """A noisy 640 x 480 game area with one built-in marker painted in place."""
    rng = np.random.default_rng(7)
    screen = rng.integers(0, 255, (BASE_HEIGHT, BASE_WIDTH), dtype=np.uint8)
    x0, y0, x1, y1 = MARKER_REGIONS[marker]
    screen[y0:y1, x0:x1] = cv2.imread(str(marker_path(marker)), cv2.IMREAD_GRAYSCALE)
    return screen


def recognizer(monkeypatch, screen, area):
    captures = []

    def grab(bbox):
        left, top, right, bottom = bbox
        captures.append(bbox)
        return screen[top - area.top:bottom - area.top, left - area.left:right - area.left].copy()
    monkeypatch.setattr(cycler_engine.screen_capture, 'grab_gray', grab)
    worker = GameWorker.__new__(GameWorker)
    worker.cfg = {'match_threshold': .83}
    worker.regions = dict(MARKER_REGIONS)
    worker._scaled_templates = {}
    worker.markers = {n: GameWorker._load_marker(n) for n in CORE_MARKERS + OPTIONAL_MARKERS}
    worker.seed_markers = {n: GameWorker._load_marker(n) for n in SEED_MARKERS}
    worker.stop, worker.pause = threading.Event(), threading.Event()
    worker.game_area = lambda: area
    worker.captures = captures
    return worker


@pytest.mark.parametrize('marker', ['login', 'servers', 'characters'])
def test_menu_is_recognized_at_100_percent(monkeypatch, marker):
    worker = recognizer(monkeypatch, synthetic_menu(marker), GameArea(8, 31, 640, 480))
    assert worker.state() == marker


@pytest.mark.parametrize('marker', ['servers', 'characters'])
def test_menu_is_recognized_at_125_percent_display_scaling(monkeypatch, marker):
    scaled = cv2.resize(synthetic_menu(marker), (800, 600), interpolation=cv2.INTER_LINEAR)
    worker = recognizer(monkeypatch, scaled, GameArea(100, 50, 800, 600))
    assert worker.state() == marker


def test_seed_marker_is_recognized_at_150_percent(monkeypatch):
    scaled = cv2.resize(synthetic_menu('seed_new_button'), (960, 720), interpolation=cv2.INTER_LINEAR)
    worker = recognizer(monkeypatch, scaled, GameArea(0, 0, 960, 720))
    assert worker.seed_visible('seed_new_button')
    assert not worker.seed_visible('seed_city')


def test_world_view_is_unknown_without_any_capture(monkeypatch):
    worker = recognizer(monkeypatch, None, GameArea(0, 0, 1280, 720))
    monkeypatch.setattr(cycler_engine.screen_capture, 'grab_gray', lambda bbox: pytest.fail('captured'))
    assert worker.state() == 'unknown'
    assert not worker.seed_visible('seed_new_button')
    assert worker.visible_seed_marker() is None


@pytest.mark.parametrize('scale', [1.0, 1.25])
def test_a_screen_read_is_one_capture_inside_the_game_area(monkeypatch, scale):
    screen = synthetic_menu('characters')
    if scale != 1:
        screen = cv2.resize(screen, (800, 600), interpolation=cv2.INTER_LINEAR)
    area = GameArea(100, 50, round(640 * scale), round(480 * scale))
    worker = recognizer(monkeypatch, screen, area)
    assert worker.state() == 'characters'
    assert len(worker.captures) == 1
    left, top, right, bottom = worker.captures[0]
    assert left >= area.left and top >= area.top
    assert right <= area.left + area.width and bottom <= area.top + area.height


def test_creation_screen_search_is_one_capture_and_finds_the_same_marker(monkeypatch):
    worker = recognizer(monkeypatch, synthetic_menu('seed_profession'), GameArea(8, 31, 640, 480))
    assert worker.visible_seed_marker() == 'seed_profession'
    assert len(worker.captures) == 1


@pytest.mark.parametrize('scale', [1.0, 1.25, 1.5])
def test_appearance_marker_is_independent_of_race_button_tooltips(monkeypatch, scale):
    screen = synthetic_menu('seed_appearance')
    # A tooltip obscures the old bottom race/sex recognition area entirely.
    screen[420:480, 40:560] = 220
    if scale != 1:
        screen = cv2.resize(screen, (round(640 * scale), round(480 * scale)),
                            interpolation=cv2.INTER_LINEAR)
    area = GameArea(100, 50, round(640 * scale), round(480 * scale))
    worker = recognizer(monkeypatch, screen, area)
    assert worker.seed_visible('seed_appearance')
    assert worker.state() == 'new_character'
    assert not worker.seed_visible('seed_profession')


@pytest.mark.parametrize('scale', [1.0, 1.25, 1.5])
def test_appearance_border_marker_survives_name_and_race_tooltips(monkeypatch, scale):
    screen = synthetic_menu('seed_appearance')
    screen[49:115, 227:484] = 220  # name header / entry area
    screen[420:480, 40:560] = 220  # bottom race and sex controls
    if scale != 1:
        screen = cv2.resize(screen, (round(640 * scale), round(480 * scale)),
                            interpolation=cv2.INTER_LINEAR)
    worker = recognizer(monkeypatch, screen,
                        GameArea(0, 0, round(640 * scale), round(480 * scale)))
    assert worker.seed_visible('seed_appearance')
    assert worker.state() == 'new_character'


@pytest.mark.parametrize('scale', [1.0, 1.25, 1.5])
def test_character_corner_marker_ignores_all_seven_character_rows(monkeypatch, scale):
    screen = synthetic_menu('characters')
    screen[120:400, 200:520] = 120
    if scale != 1:
        screen = cv2.resize(screen, (round(640 * scale), round(480 * scale)),
                            interpolation=cv2.INTER_LINEAR)
    worker = recognizer(monkeypatch, screen,
                        GameArea(0, 0, round(640 * scale), round(480 * scale)))
    assert worker.state() == 'characters'


@pytest.mark.parametrize('covered', ['corner', 'header', 'both'])
@pytest.mark.parametrize('scale', [1.0, 1.25, 1.5])
def test_character_screen_alternative_crops_survive_tooltips(monkeypatch, covered, scale):
    screen = synthetic_menu('characters')
    x0, y0, x1, y1 = (144, 68, 577, 124)
    screen[y0:y1, x0:x1] = cv2.imread(str(marker_path('characters_header')), 0)
    if covered in ('header', 'both'):
        screen[y0:y1, x0:x1] = 220
    if covered in ('corner', 'both'):
        x0, y0, x1, y1 = MARKER_REGIONS['characters']
        screen[y0:y1, x0:x1] = 220
    if scale != 1:
        screen = cv2.resize(screen, (round(640 * scale), round(480 * scale)),
                            interpolation=cv2.INTER_LINEAR)
    worker = recognizer(monkeypatch, screen,
                        GameArea(0, 0, round(640 * scale), round(480 * scale)))
    assert (worker.state() == 'characters') == (covered != 'both')

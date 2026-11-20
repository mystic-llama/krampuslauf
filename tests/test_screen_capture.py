"""Region capture and the faster New-button check."""
import ast
import os
from pathlib import Path

import numpy as np
import pytest

import screen_capture

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(os.name != 'nt', reason='GDI capture is Windows-only')
def test_region_capture_matches_pillow_pixel_for_pixel():
    from PIL import ImageGrab
    bbox = (20, 20, 220, 120)
    ours = screen_capture.grab_gray(bbox).astype(int)
    theirs = np.asarray(ImageGrab.grab(bbox=bbox).convert('L')).astype(int)
    assert ours.shape == theirs.shape == (100, 200)
    assert np.abs(ours - theirs).mean() < 2


@pytest.mark.skipif(os.name != 'nt', reason='GDI capture is Windows-only')
def test_region_capture_returns_exactly_the_requested_size_in_each_format():
    assert screen_capture.grab_bgra((10, 10, 13, 12)).shape == (2, 3, 4)
    assert screen_capture.grab_rgb((10, 10, 13, 12)).shape == (2, 3, 3)
    assert screen_capture.grab_gray((10, 10, 11, 11)).shape == (1, 1)


@pytest.mark.parametrize('bbox', [(5, 5, 5, 9), (5, 5, 9, 5), (9, 9, 5, 5), (0, 0, 10 ** 5, 10 ** 5)])
@pytest.mark.skipif(os.name != 'nt', reason='GDI capture is Windows-only')
def test_invalid_rectangles_are_refused_before_touching_the_screen(bbox):
    with pytest.raises(ValueError):
        screen_capture.grab_gray(bbox)


def new_button_check(sightings):
    tree = ast.parse((ROOT / 'seeder_engine.py').read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and
               any(isinstance(m, ast.FunctionDef) and m.name == 'seed_new_available' for m in n.body))
    node = next(m for m in cls.body if isinstance(m, ast.FunctionDef) and m.name == 'seed_new_available')
    ns = dict(SeedNotReady=RuntimeError)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), '<seeder>', 'exec'), ns)

    class Worker:
        seed_markers = {'seed_new_button': object()}
        reads, sleeps = 0, 0
        def state(self): return 'characters'
        def seed_visible(self, marker):
            Worker.reads += 1
            return sightings[Worker.reads - 1]
        def sleep(self, seconds): Worker.sleeps += 1
    worker = Worker()
    return ns['seed_new_available'](worker), Worker


@pytest.mark.parametrize('sightings,expected,reads', [
    ([True, True, False], True, 2),
    ([True, False, True], True, 3),
    ([False, False, True], False, 2),
    ([False, True, False], False, 3),
    ([True, False, False], False, 3),
])
def test_new_button_decision_is_unchanged_but_stops_when_it_is_settled(sightings, expected, reads):
    result, worker = new_button_check(sightings)
    assert result is expected
    assert worker.reads == reads
    assert worker.sleeps == reads - 1 or (reads == 3 and worker.sleeps == 2)

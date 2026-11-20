"""Seeder preflight: no typing test gate; appearance choices and click points are checked."""
import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

import appearance
from fantasy_name_generator import STYLES
from menu_layout import default_points

ROOT = Path(__file__).resolve().parents[1]


def check_seed_setup():
    tree = ast.parse((ROOT / 'seeder_engine.py').read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'SeederOperations')
    func = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'check_seed_setup')
    ns = dict(STYLES=STYLES, SEED_MARKERS=['appearance'], SEED_POINTS=[('seed_name_field', 'Name')],
              SeedNotReady=RuntimeError, appearance=appearance)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[func], type_ignores=[])), '<production>', 'exec'), ns)
    return ns['check_seed_setup']


def worker(**cfg):
    return SimpleNamespace(cfg={'seed_naming_mode': 'fantasy', 'seed_fantasy_style': 'full',
                                'points': default_points(), **cfg},
                           seed_markers={'appearance': True})


@pytest.mark.parametrize('mode,style', [('convention', 'mixed'), ('fantasy', 'single'),
                                        ('fantasy', 'full'), ('fantasy', 'mixed')])
def test_creation_needs_no_typing_test(mode, style):
    check_seed_setup()(worker(seed_naming_mode=mode, seed_fantasy_style=style))


def test_skin_tones_use_built_in_corners_and_reject_missing_points():
    check = check_seed_setup()
    look = {'enabled': True, 'mode': 'fixed', 'race': ['elf'], 'skin': {'elf': [5]}}
    check(worker(appearance=look))
    incomplete = default_points()
    del incomplete['app_skin_elf_first']
    with pytest.raises(RuntimeError, match='app_skin_elf_first'):
        check(worker(appearance=look, points=incomplete))
    points = {**default_points(), 'app_skin_elf_first': [500, 150], 'app_skin_elf_last': [590, 400]}
    check(worker(appearance=look, points=points))


def test_invalid_fixed_appearance_blocks_creation():
    look = {'enabled': True, 'mode': 'fixed', 'race': ['elf', 'human']}
    with pytest.raises(RuntimeError, match='one race only'):
        check_seed_setup()(worker(appearance=look))

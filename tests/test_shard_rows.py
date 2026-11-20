"""Reading shard names from the list: recorded screenshots and a simulated scrolling list."""
import ast
import random
from pathlib import Path

import cv2
import numpy as np
import pytest

import shard_rows as sr

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / 'fixtures' / 'shard_list'
TOP = ['Legends', 'Atlantic', 'Lake Superior', 'Great Lakes', 'Chesapeake',
       'Catskills', 'Siege Perilous', 'Origin', 'Pacific']


def fixture(name):
    return cv2.imread(str(FIXTURES / name), cv2.IMREAD_GRAYSCALE)


@pytest.fixture(scope='module')
def templates():
    rows = sr.split_rows(fixture('top_clean.png'))
    return {name: sr.ink_crop(strip) for name, strip in zip(TOP, rows)}


def test_all_visible_rows_are_read_from_a_clean_capture(templates):
    assert sr.identify_rows(fixture('top_clean.png'), templates) == TOP


@pytest.mark.parametrize('scale', [1.25, 1.5, 2.0])
def test_scaled_captures_are_read_after_normalising(templates, scale):
    big = cv2.resize(fixture('top_clean.png'), None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
    assert sr.identify_rows(sr.normalise(big, scale), templates) == TOP


def test_scrolled_list_with_the_cursor_in_view_never_misreads(templates):
    for name, expected in (('scrolled_1_cursor.png', TOP[1:]), ('scrolled_5_cursor.png', TOP[5:])):
        seen = sr.identify_rows(fixture(name), templates)
        for row, got in enumerate(seen):
            assert got is None or got == expected[row]
    first = sr.identify_rows(fixture('scrolled_1_cursor.png'), templates)
    assert first[:4] == TOP[1:5] and first[6:8] == TOP[7:9]
    assert sr.identify_rows(fixture('scrolled_5_cursor.png'), templates)[:4] == TOP[5:]


def test_names_without_a_picture_and_blank_rows_are_unknown(templates):
    partial = {k: v for k, v in templates.items() if k != 'Origin'}
    seen = sr.identify_rows(fixture('top_clean.png'), partial)
    assert seen[7] is None and seen[:7] == TOP[:7] and seen[8] == 'Pacific'
    assert sr.identify(np.full((25, 175), 200, np.uint8), templates) is None


def test_template_files_round_trip(tmp_path, templates):
    path = sr.save_template(tmp_path / 'learned', 'Siege Perilous', templates['Siege Perilous'])
    assert path.name == 'siege_perilous.png'
    loaded = sr.load_templates([tmp_path / 'missing', tmp_path / 'learned'], ['Siege Perilous', 'Baja'])
    assert list(loaded) == ['Siege Perilous']
    assert np.array_equal(loaded['Siege Perilous'], templates['Siege Perilous'])


def test_next_move_clicks_only_a_row_read_as_the_target():
    assert sr.next_move(TOP, 'Origin') == ('click', 7)
    assert sr.next_move([None] * 9, 'Origin') == ('down', sr.MAX_STEP)


def test_next_move_uses_the_saved_order_for_direction_and_distance():
    order = ['S%d' % i for i in range(27)]
    top = order[:9]
    assert sr.next_move(top, 'S12', order) == ('down', 4)
    assert sr.next_move(top, 'S26', order) == ('down', sr.MAX_STEP)
    bottom = order[18:]
    assert sr.next_move(bottom, 'S3', order) == ('up', sr.MAX_STEP)
    assert sr.next_move(order[5:14], 'S2', order) == ('up', 3)
    # The order says it should be on screen, but it was not read there.
    assert sr.next_move([None] + order[1:9], 'S0', order) == ('lost', 0)


# --- engine navigation against a simulated scrolling list --------------------

def engine_methods(*names):
    tree = ast.parse((ROOT / 'cycler_engine.py').read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'GameWorker')
    nodes = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in nodes} == set(names)

    class NotFound(RuntimeError):
        pass
    ns = dict(shard_rows=sr, np=np, ShardRowsNotFound=NotFound, SHARD_RESET_EVENTS=24,
              MAX_LIST_STEPS=14, SHARD_NAMES_DIR=None)
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), '<engine>', 'exec'), ns)
    return ns


def render(order, offset):
    image = np.full((225, 175), 190, np.uint8)
    for row in range(9):
        if offset + row < len(order):
            cv2.putText(image, order[offset + row], (10, 25 * row + 18), cv2.FONT_HERSHEY_SIMPLEX, .55, 10, 1, cv2.LINE_AA)
    return image


class FakeList:
    """A shard list that scrolls one row per wheel event and may drop events."""
    def __init__(self, order, drop_first=0, learned=None):
        self.cfg = {'shards': order, 'points': {'first_row': (377, 114)}, 'row_spacing': 25}
        self.order, self.offset, self.drop = order, 0, drop_first
        self.shard_list_at_top = False
        self.said, self.wheel_log = [], []
        self.templates = dict(learned or {})
        self._shard_templates = None

    def say(self, text): self.said.append(text)
    def sleep(self, seconds): pass
    def state(self): return 'servers'
    def shard_templates(self): return self.templates
    def capture_shard_rows(self): return render(self.order, self.offset)
    def park_menu_cursor(self): pass

    def wheel_shard_list(self, direction, count, verify_screen=True):
        self.wheel_log.append((direction, count))
        if self.drop:
            self.drop -= 1
            return
        self.offset = max(0, min(len(self.order) - 9, self.offset + (count if direction == 'down' else -count)))


def order27():
    rng = random.Random(7)
    names = set()
    while len(names) < 27:
        names.add(''.join(rng.choice('abcdefghijklmnopqrstuvwxyz') for _ in range(rng.randint(6, 11))).capitalize())
    return sorted(names, key=lambda n: rng.random())


def bind(fake, ns, *names):
    for name in names:
        setattr(fake, name, ns[name].__get__(fake))


def learned_templates(order):
    return {name: sr.ink_crop(strip) for name, strip in zip(order, sr.split_rows(render(order, 0)))}


@pytest.mark.parametrize('target', [0, 8, 9, 13, 26])
def test_recognized_navigation_ends_on_the_target_row(target):
    order = order27()
    ns = engine_methods('recognized_shard_row_point', 'row_point', 'read_shard_rows')
    fake = FakeList(order)
    fake.offset = 7
    fake.shard_list_at_top = False
    fake.templates = {n: sr.ink_crop(s) for off in range(19) for n, s in zip(order[off:off + 9], sr.split_rows(render(order, off)))}
    bind(fake, ns, 'recognized_shard_row_point', 'row_point', 'read_shard_rows')
    point = fake.recognized_shard_row_point(target)
    row = (point[1] - 114) // 25
    assert order[fake.offset + row] == order[target]
    assert fake.wheel_log[0] == ('up', 24)
    assert len(fake.wheel_log) <= 4


def test_dropped_wheel_events_are_corrected_by_reading_again():
    order = order27()
    ns = engine_methods('recognized_shard_row_point', 'row_point', 'read_shard_rows')
    fake = FakeList(order, drop_first=2)
    fake.shard_list_at_top = True
    fake.templates = {n: sr.ink_crop(s) for off in range(19) for n, s in zip(order[off:off + 9], sr.split_rows(render(order, off)))}
    bind(fake, ns, 'recognized_shard_row_point', 'row_point', 'read_shard_rows')
    point = fake.recognized_shard_row_point(20)
    assert order[fake.offset + (point[1] - 114) // 25] == order[20]


def test_a_list_that_will_not_scroll_is_reported_not_clicked():
    order = order27()
    ns = engine_methods('recognized_shard_row_point', 'row_point', 'read_shard_rows')
    fake = FakeList(order, drop_first=99)
    fake.shard_list_at_top = True
    fake.templates = learned_templates(order)
    bind(fake, ns, 'recognized_shard_row_point', 'row_point', 'read_shard_rows')
    with pytest.raises(ns['ShardRowsNotFound'], match='stopped scrolling'):
        fake.recognized_shard_row_point(20)


def learn_fixture(drop_first=0, order=None):
    order = order or order27()
    ns = engine_methods('learn_shard_names')
    fake = FakeList(order, drop_first=drop_first)
    saved = {}
    ns['shard_rows'] = type('Rows', (), {
        **{k: getattr(sr, k) for k in ('VISIBLE_ROWS', 'split_rows', 'ink_crop', 'identify')},
        'save_template': staticmethod(lambda directory, name, crop: saved.__setitem__(name, crop))})
    bind(fake, ns, 'learn_shard_names')
    return fake, saved, order


def test_learning_reads_every_name_in_order_and_returns_to_the_top():
    fake, saved, order = learn_fixture()
    assert fake.learn_shard_names(order) == sorted(order)
    assert sorted(saved) == sorted(order)
    assert fake.offset == 0 and fake.shard_list_at_top is True
    assert fake.wheel_log[0] == ('up', 24) and fake.wheel_log[-1] == ('up', 24)


def test_learning_retries_a_dropped_event_and_still_labels_correctly():
    fake, saved, order = learn_fixture(drop_first=0)
    fake.drop = 0
    original = fake.wheel_shard_list

    def flaky(direction, count, verify_screen=True):
        flaky.calls += 1
        if direction == 'down' and flaky.calls % 5 == 0:
            return
        original(direction, count, verify_screen)
    flaky.calls = 0
    fake.wheel_shard_list = flaky
    fake.learn_shard_names(order)
    assert sorted(saved) == sorted(order)


def test_learning_needs_a_verified_order():
    fake, saved, _ = learn_fixture()
    with pytest.raises(RuntimeError, match='order'):
        fake.learn_shard_names(['Only'])
    assert saved == {}

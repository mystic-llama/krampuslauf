"""Read shard names from the Classic Client shard list by image matching.

The client draws every name in one fixed font, so a small stored image of each
name identifies a row almost exactly. Everything here works in the 640 x 480
base space: captures from a scaled game area are normalised before use.
Only the narrow name column of the list is ever captured, and only in memory.
"""
from __future__ import annotations

import re

import cv2
import numpy as np

# Name column of the nine visible rows, in 640 x 480 game-area coordinates.
NAME_REGION = (215, 103, 390, 328)
ROW_PITCH = 25
VISIBLE_ROWS = 9
REGION_SIZE = (NAME_REGION[2] - NAME_REGION[0], NAME_REGION[3] - NAME_REGION[1])

DARK = 100
MIN_INK = 40
MATCH_MIN = .80
MATCH_GAP = .20
SIZE_TOLERANCE = (2, 3)
MAX_STEP = 6


def slug(name):
    return re.sub(r'[^a-z0-9]+', '_', str(name).casefold()).strip('_')


def normalise(gray, scale):
    """Bring a capture of NAME_REGION taken at `scale` to base size."""
    if abs(float(scale) - 1.0) < .01 and gray.shape[1] == REGION_SIZE[0] and gray.shape[0] == REGION_SIZE[1]:
        return gray
    return cv2.resize(gray, REGION_SIZE, interpolation=cv2.INTER_AREA)


def split_rows(gray):
    """The nine row strips of a base-size NAME_REGION image."""
    return [gray[ROW_PITCH * i:ROW_PITCH * (i + 1)] for i in range(VISIBLE_ROWS)]


def ink_crop(strip):
    """Tight crop of a row's text, or None when the row holds no usable text."""
    mask = strip < DARK
    if int(mask.sum()) < MIN_INK:
        return None
    ys, xs = np.where(mask)
    crop = strip[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    if crop.shape[0] < 8 or crop.shape[1] < 20:
        return None
    return crop


def score(crop, template):
    """Best normalised correlation of two same-sized text crops (0 if sizes differ)."""
    dh, dw = abs(crop.shape[0] - template.shape[0]), abs(crop.shape[1] - template.shape[1])
    if dw > SIZE_TOLERANCE[0] or dh > SIZE_TOLERANCE[1]:
        return 0.0
    pad = 3
    canvas = cv2.copyMakeBorder(crop, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=int(np.median(crop)))
    if canvas.shape[0] < template.shape[0] or canvas.shape[1] < template.shape[1]:
        return 0.0
    result = cv2.matchTemplate(canvas, template, cv2.TM_CCOEFF_NORMED)
    value = float(result.max())
    return value if np.isfinite(value) else 0.0


def identify(strip, templates):
    """Shard name shown in a row, or None if blank, unknown or ambiguous."""
    crop = ink_crop(strip)
    if crop is None or not templates:
        return None
    scores = sorted(((score(crop, t), name) for name, t in templates.items()), reverse=True)
    best, name = scores[0]
    runner_up = scores[1][0] if len(scores) > 1 else 0.0
    if best >= MATCH_MIN and best - runner_up >= MATCH_GAP:
        return name
    return None


def identify_rows(gray, templates):
    return [identify(strip, templates) for strip in split_rows(gray)]


def encode_png(image):
    ok, data = cv2.imencode('.png', image)
    if not ok:
        raise ValueError('Could not encode image.')
    return data.tobytes()


def save_template(directory, name, crop):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (slug(name) + '.png')
    temp = path.with_suffix('.png.tmp')
    temp.write_bytes(encode_png(crop))
    temp.replace(path)
    return path


def load_template(path):
    try:
        image = cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8), cv2.IMREAD_GRAYSCALE)
    except OSError:
        return None
    if image is None or image.shape[0] < 8 or image.shape[1] < 20:
        return None
    return image


def load_templates(directories, names):
    """First usable image per name, searching `directories` in priority order."""
    found = {}
    for name in names:
        for directory in directories:
            image = load_template(directory / (slug(name) + '.png'))
            if image is not None:
                found[name] = image
                break
    return found


def next_move(visible, target, order=(), max_step=MAX_STEP):
    """Decide the next list action from the names currently on screen.

    Returns ('click', row), ('down', events) or ('up', events). The saved order
    only decides direction and distance; a click is only ever returned for a row
    whose name was read as the target.
    """
    if target in visible:
        return ('click', visible.index(target))
    order = list(order)
    if target in order:
        known = [(row, order.index(name)) for row, name in enumerate(visible) if name in order]
        if known:
            row, index = known[0]
            first, wanted = index - row, order.index(target)
            if wanted > first + VISIBLE_ROWS - 1:
                return ('down', max(1, min(wanted - (first + VISIBLE_ROWS - 1), max_step)))
            if wanted < first:
                return ('up', max(1, min(first - wanted, max_step)))
            return ('lost', 0)
    return ('down', max_step)

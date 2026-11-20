"""Opt-in timing trace of the automation steps.

Create the empty file `timing.enabled` in the Krampuslauf data folder to turn it
on. Each traced method call appends one line to `timing.log` in the same
folder: when it ran, how long it took, how deeply it was nested inside other
traced calls, and which function called it. Only method names, durations and
screen names are written; never account, character or credential data.
"""
from __future__ import annotations

import sys
import threading
import time
from datetime import datetime

MAX_LOG_BYTES = 5 * 1024 * 1024


def install(worker, path, names, clock=time.perf_counter):
    """Wrap the named bound methods of `worker` so each call is timed and logged."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if path.exists() and path.stat().st_size > MAX_LOG_BYTES:
            path.replace(path.with_suffix('.old'))
    except OSError:
        pass
    lock = threading.Lock()
    depth = [0]

    def write(line):
        try:
            with lock, path.open('a', encoding='utf-8') as handle:
                handle.write(line)
        except OSError:
            pass

    write('=== timing trace started {} ===\n'.format(datetime.now().isoformat(timespec='seconds')))

    def wrap(name, original):
        def timed(*args, **kwargs):
            frame = sys._getframe(1)
            where = '{}:{}'.format(frame.f_code.co_name, frame.f_lineno)
            level = depth[0]
            depth[0] += 1
            started = clock()
            result = None
            try:
                result = original(*args, **kwargs)
                return result
            finally:
                depth[0] -= 1
                detail = ''
                if name == 'sleep' and args:
                    detail = ' requested={:.2f}s'.format(float(args[0]))
                elif name == 'state' and isinstance(result, str):
                    detail = ' -> ' + result
                write('{} {}{:<26} {:8.1f} ms  from {}{}\n'.format(
                    datetime.now().strftime('%H:%M:%S.%f')[:-3], '  ' * level, name,
                    (clock() - started) * 1000, where, detail))
        timed.__name__ = name
        return timed

    wrapped = []
    for name in names:
        original = getattr(worker, name, None)
        if callable(original):
            setattr(worker, name, wrap(name, original))
            wrapped.append(name)
    return wrapped

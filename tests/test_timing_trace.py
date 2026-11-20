"""The opt-in timing trace records durations and names only."""
import timing_trace


class Worker:
    def __init__(self):
        self.ticks = 0

    def state(self):
        return 'servers'

    def sleep(self, seconds):
        self.ticks += 1

    def click(self, point):
        self.state()
        self.sleep(.3)
        return point


def test_traced_calls_are_timed_nested_and_attributed(tmp_path):
    log = tmp_path / 'logs' / 'timing.log'
    worker = Worker()
    wrapped = timing_trace.install(worker, log, ('state', 'sleep', 'click', 'missing_method'))
    assert wrapped == ['state', 'sleep', 'click']
    assert worker.click((10, 20)) == (10, 20)
    lines = log.read_text(encoding='utf-8').splitlines()
    assert lines[0].startswith('=== timing trace started')
    body = lines[1:]
    assert [l.split()[1] for l in body] == ['state', 'sleep', 'click']
    assert body[0].split('ms')[0].strip().split()[-1].replace('.', '').isdigit()
    assert ' -> servers' in body[0] and 'requested=0.30s' in body[1]
    assert body[0].split()[1] == 'state' and body[0].index('state') > body[2].index('click')
    assert all('from test_traced_calls_are_timed_nested_and_attributed' in l or 'from click' in l for l in body)


def test_arguments_other_than_sleep_length_are_never_logged(tmp_path):
    log = tmp_path / 'timing.log'
    worker = Worker()
    timing_trace.install(worker, log, ('click',))
    worker.click(('secret-name', 'secret-password'))
    assert 'secret' not in log.read_text(encoding='utf-8')


def test_an_oversized_log_is_rolled_over(tmp_path, monkeypatch):
    log = tmp_path / 'timing.log'
    log.write_text('x' * 100, encoding='utf-8')
    monkeypatch.setattr(timing_trace, 'MAX_LOG_BYTES', 10)
    timing_trace.install(Worker(), log, ())
    assert (tmp_path / 'timing.old').read_text(encoding='utf-8') == 'x' * 100
    assert log.read_text(encoding='utf-8').startswith('=== timing trace started')

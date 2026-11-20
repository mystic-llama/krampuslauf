"""Persistent local Krampuslauf activity history (no GUI dependency)."""
from pathlib import Path


class ActivityHistory:
    def __init__(self, path, max_bytes=3 * 1024 * 1024, backups=3):
        self.path = Path(path)
        self.max_bytes = max_bytes
        self.backups = backups
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, line):
        data = (str(line).rstrip('\r\n') + '\n').encode('utf-8', errors='replace')
        if self.path.exists() and self.path.stat().st_size + len(data) > self.max_bytes:
            for n in range(self.backups, 0, -1):
                old = self.path.with_name(self.path.name + '.' + str(n))
                previous = self.path if n == 1 else self.path.with_name(self.path.name + '.' + str(n-1))
                if old.exists():
                    old.unlink()
                if previous.exists():
                    previous.replace(old)
        with self.path.open('ab') as stream:
            stream.write(data)

    def tail(self, chars=55000):
        if not self.path.exists():
            return ''
        with self.path.open('rb') as stream:
            stream.seek(0, 2)
            stream.seek(max(0, stream.tell() - chars * 4))
            data = stream.read()
        return data.decode('utf-8', errors='replace')[-chars:]

    def clear(self):
        for n in range(self.backups + 1):
            path = self.path if n == 0 else self.path.with_name(self.path.name + '.' + str(n))
            if path.exists():
                path.unlink()

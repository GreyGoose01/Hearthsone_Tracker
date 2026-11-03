"""Follow the newest ``Power.log`` below ``<game_dir>/Logs``.

Recent Hearthstone versions create one sub folder per session
(``Logs/Hearthstone_2026_11_02_18_51_00/Power.log``); older versions wrote
``Logs/Power.log`` directly. Both layouts are supported. Polling keeps the
tracker free of extra dependencies and works on every file system.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable


def find_power_logs(logs_dir: Path) -> list[Path]:
    """All Power.log files, oldest first."""
    if not logs_dir.is_dir():
        return []
    found = [p for p in logs_dir.glob("Power.log") if p.is_file()]
    found += [p for p in logs_dir.glob("*/Power.log") if p.is_file()]

    def mtime(p: Path) -> float:
        try:
            return p.stat().st_mtime
        except OSError:
            return 0.0

    return sorted(found, key=mtime)


def newest_power_log(logs_dir: Path) -> Path | None:
    logs = find_power_logs(logs_dir)
    return logs[-1] if logs else None


class LogFollower:
    """Read complete lines from a growing file; detect truncation/replacement."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._fh = None
        self._buffer = ""
        self._inode: int | None = None

    def close(self) -> None:
        if self._fh:
            self._fh.close()
        self._fh = None

    def read_lines(self) -> list[str]:
        try:
            st = self.path.stat()
        except OSError:
            return []
        if self._fh is None or st.st_ino != self._inode or st.st_size < self._fh.tell():
            self.close()
            self._fh = self.path.open("r", encoding="utf-8", errors="replace")
            self._inode = st.st_ino
            self._buffer = ""
        chunk = self._fh.read()
        if not chunk:
            return []
        data = self._buffer + chunk
        lines = data.split("\n")
        self._buffer = lines.pop()  # incomplete last line (or "")
        return lines


class LogWatcher(threading.Thread):
    """Background thread: feeds new Power.log lines to ``on_lines``.

    ``on_new_file(path)`` is called whenever a different log file is
    followed (new game session). The file is then read from its start so the
    current game can be reconstructed. ``on_scan(path)`` runs every ~2 s with
    the followed file (or None), e.g. to check whether it is still current.
    """

    def __init__(
        self,
        logs_dir: Path,
        on_lines: Callable[[list[str]], None],
        on_new_file: Callable[[Path], None] | None = None,
        interval: float = 0.25,
        on_scan: Callable[[Path | None], None] | None = None,
    ) -> None:
        super().__init__(daemon=True, name="hearthwatch-logwatcher")
        self.logs_dir = logs_dir
        self.on_lines = on_lines
        self.on_new_file = on_new_file
        self.on_scan = on_scan
        self.interval = interval
        self._stop = threading.Event()
        self._follower: LogFollower | None = None
        self._last_scan = 0.0

    def stop(self) -> None:
        self._stop.set()

    @property
    def current_file(self) -> Path | None:
        return self._follower.path if self._follower else None

    def poll_once(self) -> None:
        now = time.monotonic()
        scanned = False
        if self._follower is None or now - self._last_scan > 2.0:
            self._last_scan = now
            scanned = True
            newest = newest_power_log(self.logs_dir)
            if newest is not None and (self._follower is None or newest != self._follower.path):
                if self._follower:
                    # drain the old file before switching
                    rest = self._follower.read_lines()
                    if rest:
                        self.on_lines(rest)
                    self._follower.close()
                self._follower = LogFollower(newest)
                if self.on_new_file:
                    self.on_new_file(newest)
        if self._follower is not None:
            lines = self._follower.read_lines()
            if lines:
                self.on_lines(lines)
        if scanned and self.on_scan:
            self.on_scan(self.current_file)

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                self.poll_once()
            except Exception:  # keep the thread alive; errors show up in the next poll
                import logging

                logging.getLogger(__name__).exception("log watcher poll failed")
            self._stop.wait(self.interval)
        if self._follower:
            self._follower.close()

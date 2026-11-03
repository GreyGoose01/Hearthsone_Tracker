import os
import time

from hearthwatch.logwatcher import LogFollower, LogWatcher, newest_power_log


def test_follower_returns_complete_lines_only(tmp_path):
    f = tmp_path / "Power.log"
    f.write_text("a\nb")
    fol = LogFollower(f)
    assert fol.read_lines() == ["a"]
    with f.open("a") as fh:
        fh.write("c\n")
    assert fol.read_lines() == ["bc"]
    f.write_text("new\n")  # truncated / rewritten
    assert fol.read_lines() == ["new"]


def test_newest_power_log_in_session_folders(tmp_path):
    old = tmp_path / "Hearthstone_2026_11_01_10_00_00" / "Power.log"
    new = tmp_path / "Hearthstone_2026_11_02_10_00_00" / "Power.log"
    for p in (old, new):
        p.parent.mkdir()
        p.write_text("x\n")
    past = time.time() - 100
    os.utime(old, (past, past))
    assert newest_power_log(tmp_path) == new


def test_watcher_switches_files(tmp_path):
    got, files = [], []
    a = tmp_path / "s1" / "Power.log"
    a.parent.mkdir()
    a.write_text("one\n")
    w = LogWatcher(tmp_path, got.extend, files.append)
    w.poll_once()
    assert got == ["one"] and files == [a]
    b = tmp_path / "s2" / "Power.log"
    b.parent.mkdir()
    b.write_text("two\n")
    future = time.time() + 10
    os.utime(b, (future, future))
    w._last_scan = 0
    w.poll_once()
    assert files == [a, b] and got == ["one", "two"]

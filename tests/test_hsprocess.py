from hearthwatch.hsprocess import hearthstone_running


def proc(tmp_path, procs):
    root = tmp_path / "proc"
    (root / "self").mkdir(parents=True)
    for pid, (comm, cmdline) in procs.items():
        d = root / str(pid)
        d.mkdir()
        (d / "comm").write_text(comm + "\n")
        (d / "cmdline").write_bytes(cmdline)
    return root


def test_detects_the_unity_player_by_comm(tmp_path):
    root = proc(tmp_path, {1: ("systemd", b"/sbin/init\0"), 42: ("Hearthstone.x86", b"")})
    assert hearthstone_running(root) is True


def test_detects_the_player_started_through_a_loader(tmp_path):
    root = proc(tmp_path, {
        7: ("ld-linux-x86-64", b"/lib64/ld-linux-x86-64.so.2\0/home/u/game/Bin/Hearthstone.x86_64\0-logFile\0"),
    })
    assert hearthstone_running(root) is True


def test_not_running(tmp_path):
    root = proc(tmp_path, {1: ("systemd", b"/sbin/init\0"), 9: ("hearthwatch", b"python3\0-m\0hearthwatch\0")})
    assert hearthstone_running(root) is False


def test_unknown_without_proc(tmp_path):
    assert hearthstone_running(tmp_path / "missing") is None
    (tmp_path / "empty").mkdir()
    assert hearthstone_running(tmp_path / "empty") is None

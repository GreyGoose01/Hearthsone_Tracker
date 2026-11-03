import os
import time

import pytest

from hearthwatch import cli, diagnose, logconfig, paths

PREFS = "Library/Preferences/Blizzard/Hearthstone"
GAME = ".local/share/hearthstone-linux-gui/game"
FLATPAK = ".var/app/io.github.hearthstone_linux_gui"


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    for var in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME",
                "BGTRACKER_GAME_DIR", "HEARTHWATCH_GAME_DIR"):
        monkeypatch.delenv(var, raising=False)
    return tmp_path


def install_game(home, size_limit_lifted=True):
    game = home / GAME
    (game / "Bin").mkdir(parents=True)
    (game / "Bin/Hearthstone.x86_64").write_text("")
    (game / "Logs").mkdir()
    # client.config as written by hearthstone-linux-gui
    lines = ["Aurora.ClientCheck=false", "Aurora.Env.Override=1", "Aurora.Env=eu.actual.battle.net",
             "Localization.Locale=deDE"]
    if size_limit_lifted:
        lines.append("Log.FileSizeLimit.Int=-1")
    (game / "client.config").write_text("\n".join(lines) + "\n")
    return game


def start_game(home, game, power=False, when=None):
    """Simulate a game start: options.txt + a new session folder (+ Power.log)."""
    (home / PREFS).mkdir(parents=True, exist_ok=True)
    (home / PREFS / "options.txt").write_text("graphicsquality=1\n")
    session = game / "Logs" / f"Hearthstone_{len(list((game / 'Logs').iterdir()))}"
    session.mkdir()
    (session / "BattleNet.log").write_text("x\n")
    if power:
        (session / "Power.log").write_text("D 20:00:00.0 GameState.DebugPrintPower() - CREATE_GAME\n")
    if when is not None:
        for p in [session, *session.iterdir()]:
            os.utime(p, (when, when))
    return session


def statuses(checks):
    return {c.key: c.status for c in checks}


def test_nothing_installed(home):
    checks = diagnose.run_checks()
    s = statuses(checks)
    assert s["game"] == "error" and s["started"] == "warn" and s["logconfig"] == "error"
    assert diagnose.first_problem(checks).key == "game"


def test_started_but_no_logconfig(home):
    game = install_game(home)
    start_game(home, game)
    checks = diagnose.run_checks()
    s = statuses(checks)
    assert s["game"] == "ok" and s["started"] == "ok" and s["logconfig"] == "error"
    problem = diagnose.first_problem(checks)
    assert problem.key == "logconfig" and problem.action == "setup-logs"


def test_logconfig_written_needs_restart(home):
    game = install_game(home)
    start_game(home, game, when=time.time() - 3600)
    logconfig.ensure(paths.log_config_path())
    checks = diagnose.run_checks()
    problem = diagnose.first_problem(checks)
    assert problem.key == "powerlog" and "neu starten" in problem.hint


def test_restarted_but_no_power_log_yet(home):
    game = install_game(home)
    logconfig.ensure(home / PREFS / "log.config")
    os.utime(home / PREFS / "log.config", (time.time() - 3600,) * 2)
    start_game(home, game)  # newer than log.config, no Power.log
    problem = diagnose.first_problem(diagnose.run_checks())
    assert problem.key == "powerlog" and "Partie" in problem.hint


def test_everything_ok(home):
    game = install_game(home)
    logconfig.ensure(home / PREFS / "log.config")
    start_game(home, game, power=True)
    checks = diagnose.run_checks()
    assert diagnose.first_problem(checks) is None
    assert "Power.log" in diagnose.format_checks(checks)


def test_options_only_in_flatpak_folder(home):
    prefs = home / FLATPAK / PREFS
    prefs.mkdir(parents=True)
    (prefs / "options.txt").write_text("x\n")
    # the multi-GB game folder must not be searched
    deep = home / FLATPAK / "data/hearthstone-linux-gui/game/Hearthstone"
    deep.mkdir(parents=True)
    (deep / "options.txt").write_text("x\n")
    assert paths.find_options_files() == [prefs / "options.txt"]
    assert paths.log_config_path() == prefs / "log.config"
    assert cli.main(["--setup-logs", "--lang", "de"]) == 0
    assert logconfig.is_configured(prefs / "log.config")
    assert not (home / PREFS / "log.config").exists()


def test_check_command_output(home, capsys):
    game = install_game(home)
    start_game(home, game)
    assert cli.main(["--check", "--lang", "de"]) == 1
    out = capsys.readouterr().out
    assert "✗ log.config" in out and "Nächster Schritt" in out


def test_log_size_limit_is_checked_and_fixed(home, capsys):
    game = install_game(home, size_limit_lifted=False)
    logconfig.ensure(home / PREFS / "log.config")
    start_game(home, game, power=True)
    problem = diagnose.first_problem(diagnose.run_checks())
    assert problem.key == "clientconfig" and problem.action == "setup-logs"
    assert cli.main(["--setup-logs", "--lang", "de"]) == 0
    assert "Log-Größenlimit abgeschaltet" in capsys.readouterr().out
    assert diagnose.first_problem(diagnose.run_checks()) is None
    # the launcher's own lines are untouched
    assert (game / "client.config").read_text().startswith("Aurora.ClientCheck=false\n")

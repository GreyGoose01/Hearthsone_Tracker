"""Broken log.config files, stale / non-verbose Power.logs and reconnects."""

import os
import time

import pytest

from hearthwatch import cli, diagnose, logconfig
from hearthwatch.bg.tracker import BattlegroundsTracker
from hearthwatch.power.game_state import GameState

from test_diagnose import GAME, PREFS, home, install_game, start_game  # noqa: F401

GOOD = (
    "[Power]\nLogLevel=1\nFilePrinting=true\nConsolePrinting=false\nScreenPrinting=false\nVerbose=true\n"
    "[LoadingScreen]\nLogLevel=1\nFilePrinting=true\nConsolePrinting=false\nScreenPrinting=false\n"
)


# -- log.config ---------------------------------------------------------------
@pytest.mark.parametrize("content, reason", [
    ("LogLevel=1\n[Power]\nVerbose=true\n", "vor dem ersten"),
    ("[Power]\nnur text ohne gleichheitszeichen\n", "ohne „=“"),
    (b"\xff\xfe[\x00P\x00", "UTF-8"),  # UTF-16 from a Windows editor
])
def test_broken_logconfig_is_reported_and_replaced(tmp_path, content, reason):
    path = tmp_path / "log.config"
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content)
    assert reason in logconfig.problem(path)
    assert logconfig.missing_entries(path) == logconfig.ALL_ENTRIES
    assert logconfig.ensure(path) is True
    assert logconfig.problem(path) is None and logconfig.is_configured(path)
    backup = tmp_path / "log.config.bak"
    assert backup.exists()
    if isinstance(content, bytes):
        assert backup.read_bytes() == content
    else:
        assert backup.read_text() == content


def test_bom_is_accepted(tmp_path):
    path = tmp_path / "log.config"
    path.write_bytes(b"\xef\xbb\xbf" + GOOD.encode())
    assert logconfig.problem(path) is None
    assert logconfig.is_configured(path)


def test_folder_instead_of_file(tmp_path):
    path = tmp_path / "log.config"
    path.mkdir()
    (path / "inside.txt").write_text("keep me")
    assert "Ordner" in logconfig.problem(path)
    assert logconfig.ensure(path)
    assert path.is_file() and logconfig.is_configured(path)
    assert (tmp_path / "log.config.bak" / "inside.txt").read_text() == "keep me"


def test_existing_backup_is_not_overwritten(tmp_path):
    path = tmp_path / "log.config"
    (tmp_path / "log.config.bak").write_text("old backup")
    path.write_text("garbage line\n")
    logconfig.ensure(path)
    assert (tmp_path / "log.config.bak").read_text() == "old backup"
    assert (tmp_path / "log.config.bak1").read_text() == "garbage line\n"


def test_check_and_setup_with_broken_logconfig(home, capsys):  # noqa: F811
    game = install_game(home)
    start_game(home, game)
    (home / PREFS / "log.config").write_text("kaputt\n[Power]\n")
    assert cli.main(["--check", "--lang", "de"]) == 1
    out = capsys.readouterr().out
    assert "beschädigt" in out and "Zeile 1" in out
    assert cli.main(["--setup-logs", "--lang", "de"]) == 0
    assert logconfig.is_configured(home / PREFS / "log.config")


# -- Power.log ------------------------------------------------------------------
def test_power_log_from_older_session_is_not_ok(home):  # noqa: F811
    game = install_game(home)
    logconfig.ensure(home / PREFS / "log.config")
    old = time.time() - 7200
    os.utime(home / PREFS / "log.config", (old - 100, old - 100))
    start_game(home, game, power=True, when=old)  # yesterday's session with Power.log
    latest = start_game(home, game)  # today's session without one
    problem = diagnose.first_problem(diagnose.run_checks())
    assert problem.key == "powerlog"
    assert latest.name in problem.detail and "Partie" in problem.hint


def test_power_log_without_verbose(home):  # noqa: F811
    game = install_game(home)
    logconfig.ensure(home / PREFS / "log.config")
    session = start_game(home, game)
    (session / "Power.log").write_text(
        "D 20:00:00.0 GameState.DebugPrintPower() - CREATE_GAME\n"
        "D 20:00:00.1 GameState.DebugPrintPower() -     FULL_ENTITY - Creating ID=4 CardID=X\n"
        "D 20:00:00.2 GameState.DebugPrintPower() - TAG_CHANGE Entity=GameEntity tag=TURN value=1\n"
    )
    problem = diagnose.first_problem(diagnose.run_checks())
    assert problem.key == "powerlog" and "Verbose" in problem.detail


def test_verbose_power_log_is_ok(home, bg_log):  # noqa: F811
    game = install_game(home)
    logconfig.ensure(home / PREFS / "log.config")
    session = start_game(home, game)
    (session / "Power.log").write_text(bg_log.read_text())
    assert diagnose.first_problem(diagnose.run_checks()) is None


# -- reconnect ------------------------------------------------------------------
def test_unfinished_game_is_not_saved_on_reconnect(bg_log, cards):
    lines = bg_log.read_text().splitlines()
    cut = next(i for i, line in enumerate(lines) if "tag=TURN value=3" in line)
    # first attempt breaks off in round 2 (place 1 at that moment!), then the
    # game reconnects: the log starts over with CREATE_GAME and runs to the end
    replay = lines[:cut] + lines
    results, states = [], []
    tracker = BattlegroundsTracker(cards, on_state=states.append, on_match_end=results.append)
    game = GameState([tracker])
    for line in replay:
        game.feed_line(line)
        tracker.batch_done(game)
    assert [r.placement for r in results] == [3]
    assert game.games_started == 2

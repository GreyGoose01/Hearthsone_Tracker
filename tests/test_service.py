import os
import threading
import time

from hearthwatch.db import MatchDB
from hearthwatch.service import Callbacks, TrackerService, import_logs


def test_service_follows_log_saves_match_and_simulates(tmp_path, bg_log, cards):
    logs = tmp_path / "Logs"
    session = logs / "Hearthstone_2026_11_02_20_00_00"
    session.mkdir(parents=True)
    power = session / "Power.log"
    lines = bg_log.read_text().splitlines(keepends=True)
    cut = next(i for i, l in enumerate(lines) if "tag=STATE value=COMPLETE" in l)
    power.write_text("".join(lines[:cut]))  # tracker starts mid-game

    states, sims, saved = [], [], []
    done = threading.Event()

    def on_sim(c, r):
        sims.append((c, r))
        done.set()

    db = MatchDB(tmp_path / "m.db")
    svc = TrackerService(logs, db, cards, Callbacks(
        on_state=states.append, on_sim=on_sim, on_match_saved=saved.append), sim_runs=200,
        hs_running=lambda: True)
    svc.watcher.poll_once()
    assert done.wait(10), "latest combat of the running game should be simulated"
    assert sims[0][1].loss == 1.0
    assert states[-1].in_game and states[-1].round == 2

    with power.open("a") as fh:
        fh.writelines(lines[cut:])
    svc.watcher.poll_once()
    svc.stop()
    assert [r.placement for r in saved] == [3]
    assert db.summary().games == 1

    # importing the same log again must not create duplicates
    assert import_logs(logs, db, cards) == 0


def session(logs, name, lines=None, age=0.0):
    folder = logs / name
    folder.mkdir(parents=True)
    if lines is not None:
        (folder / "Power.log").write_text("".join(lines))
    when = time.time() - age
    os.utime(folder, (when, when))
    return folder


def unfinished(bg_log):
    lines = bg_log.read_text().splitlines(keepends=True)
    cut = next(i for i, l in enumerate(lines) if "tag=STATE value=COMPLETE" in l)
    return lines[:cut]


def make_service(tmp_path, logs, cards, running, states):
    return TrackerService(logs, MatchDB(tmp_path / "m.db"), cards,
                          Callbacks(on_state=states.append), sim_runs=50,
                          hs_running=lambda: running[0])


def test_old_game_is_not_live_when_hearthstone_is_closed(tmp_path, bg_log, cards):
    logs = tmp_path / "Logs"
    session(logs, "Hearthstone_old", unfinished(bg_log), age=3600)
    states, running = [], [False]
    svc = make_service(tmp_path, logs, cards, running, states)
    svc.watcher.poll_once()
    assert not svc.live
    assert not any(s.in_game for s in states)


def test_old_game_is_not_live_in_the_main_menu(tmp_path, bg_log, cards):
    logs = tmp_path / "Logs"
    session(logs, "Hearthstone_old", unfinished(bg_log), age=3600)
    session(logs, "Hearthstone_new")  # Hearthstone started, no game yet -> no Power.log
    states, running = [], [True]
    svc = make_service(tmp_path, logs, cards, running, states)
    svc.watcher.poll_once()
    assert not svc.live
    assert not any(s.in_game for s in states)

    # first game of the new session: its Power.log appears and becomes live
    (logs / "Hearthstone_new" / "Power.log").write_text("".join(unfinished(bg_log)))
    os.utime(logs / "Hearthstone_new", None)
    svc.watcher._last_scan = 0
    svc.watcher.poll_once()
    assert svc.live
    assert states[-1].in_game and states[-1].round == 2


def test_closing_hearthstone_ends_the_live_view(tmp_path, bg_log, cards):
    logs = tmp_path / "Logs"
    session(logs, "Hearthstone_now", unfinished(bg_log))
    states, running = [], [True]
    svc = make_service(tmp_path, logs, cards, running, states)
    svc.watcher.poll_once()
    assert svc.live and states[-1].in_game
    running[0] = False
    svc.watcher._last_scan = 0
    svc.watcher.poll_once()
    assert not svc.live
    assert states[-1].in_game is False


def test_old_games_combat_is_not_shown_in_a_new_game(tmp_path, bg_log, cards):
    logs = tmp_path / "Logs"
    session(logs, "Hearthstone_old", unfinished(bg_log), age=3600)  # has a round-1 combat
    states, combats, running = [], [], [False]
    svc = TrackerService(logs, MatchDB(tmp_path / "m.db"), cards,
                         Callbacks(on_state=states.append, on_combat=combats.append),
                         sim_runs=20, hs_running=lambda: running[0])
    svc.watcher.poll_once()
    # Hearthstone starts, new game: only up to the combat phase, no attack yet
    running[0] = True
    lines = bg_log.read_text().splitlines(keepends=True)
    attack = next(i for i, l in enumerate(lines) if "BlockType=ATTACK" in l and "PowerTaskList" in l)
    session(logs, "Hearthstone_new", lines[:attack])
    svc.watcher._last_scan = 0
    svc.watcher.poll_once()
    svc.stop()
    assert svc.live and states[-1].in_game and states[-1].phase == "combat"
    assert states[-1].last_combat is None
    assert combats == []


def test_stalled_power_log_is_reported(tmp_path, bg_log, cards):
    logs = tmp_path / "Logs"
    session(logs, "Hearthstone_now", unfinished(bg_log))
    now = [1000.0]
    stalls = []
    svc = TrackerService(logs, MatchDB(tmp_path / "m.db"), cards,
                         Callbacks(on_log_stalled=stalls.append), sim_runs=20,
                         hs_running=lambda: True, clock=lambda: now[0])
    svc.watcher.poll_once()
    assert svc.live and stalls == []
    now[0] += 60
    svc.watcher._last_scan = 0
    svc.watcher.poll_once()
    assert stalls == []  # a minute without lines is normal
    now[0] += 200
    svc.watcher._last_scan = 0
    svc.watcher.poll_once()
    assert stalls == [True]
    # Hearthstone writes again -> cleared
    with (logs / "Hearthstone_now" / "Power.log").open("a") as fh:
        fh.write("D 20:59:00.0 PowerTaskList.DebugPrintPower() - BLOCK_END\n")
    svc.watcher.poll_once()
    svc.stop()
    assert stalls == [True, False]


def loading_screen(folder, *transitions):
    lines = [f"D 20:00:0{i}.0 LoadingScreen.OnSceneLoaded() - prevMode={a} currMode={b}\n"
             for i, (a, b) in enumerate(transitions)]
    with (folder / "LoadingScreen.log").open("a") as fh:
        fh.writelines(lines)


def test_leaving_a_game_whose_log_stopped_ends_the_live_view(tmp_path, bg_log, cards):
    logs = tmp_path / "Logs"
    folder = session(logs, "Hearthstone_now", unfinished(bg_log))
    loading_screen(folder, ("HUB", "BACON"), ("BACON", "GAMEPLAY"))
    now = [1000.0]
    states = []
    svc = TrackerService(logs, MatchDB(tmp_path / "m.db"), cards, Callbacks(on_state=states.append),
                         sim_runs=20, hs_running=lambda: True, clock=lambda: now[0])
    svc.watcher.poll_once()
    assert states[-1].in_game  # still in the game scene

    # Power.log has stopped (size limit); the player concedes and is back in the lobby
    loading_screen(folder, ("GAMEPLAY", "BACON"))
    now[0] += 2
    svc.watcher._last_scan = 0
    svc.watcher.poll_once()
    assert states[-1].in_game  # grace period: Power.log may still report the end

    now[0] += 10
    svc.watcher._last_scan = 0
    svc.watcher.poll_once()
    svc.stop()
    assert states[-1].in_game is False
    assert "nicht bis zum Ende" in states[-1].notice
    assert svc.db.summary().games == 0  # unknown placement: nothing saved


def test_a_properly_finished_game_is_not_abandoned(tmp_path, bg_log, cards):
    logs = tmp_path / "Logs"
    folder = session(logs, "Hearthstone_now", bg_log.read_text().splitlines(keepends=True))
    loading_screen(folder, ("BACON", "GAMEPLAY"), ("GAMEPLAY", "BACON"))
    now = [1000.0]
    states = []
    svc = TrackerService(logs, MatchDB(tmp_path / "m.db"), cards, Callbacks(on_state=states.append),
                         sim_runs=20, hs_running=lambda: True, clock=lambda: now[0])
    svc.watcher.poll_once()
    now[0] += 30
    svc.watcher._last_scan = 0
    svc.watcher.poll_once()
    svc.stop()
    assert states[-1].summary is not None and states[-1].summary.placement == 3
    assert states[-1].notice == ""


def test_size_limit_message_is_reported_at_once(tmp_path, bg_log, cards):
    logs = tmp_path / "Logs"
    lines = unfinished(bg_log) + [
        "Truncating log, which has reached the size limit of 10000KB\n",
        "==================================================================\n",
    ]
    session(logs, "Hearthstone_now", lines)
    stalls = []
    svc = TrackerService(logs, MatchDB(tmp_path / "m.db"), cards,
                         Callbacks(on_log_stalled=stalls.append), sim_runs=20,
                         hs_running=lambda: True, clock=lambda: 1000.0)
    svc.watcher.poll_once()  # no waiting for the 3-minute stall timeout
    svc.stop()
    assert stalls == [True]


def test_card_data_in_another_language_reads_the_log_again(tmp_path, bg_log, cards):
    from hearthwatch.cards import CardDB
    from hearthwatch.service import _other_language

    logs = tmp_path / "Logs"
    session(logs, "Hearthstone_2026_11_02_20_00_00", unfinished(bg_log))
    files = []
    svc = TrackerService(logs, MatchDB(tmp_path / "m.db"), CardDB(),
                         Callbacks(on_file=files.append), sim_runs=20, hs_running=lambda: True)
    svc.watcher.poll_once()  # read without any card data (first start, still downloading)
    assert len(files) == 1
    svc.set_cards(cards)  # the card data arrives: texts and buffs need the log again
    svc.watcher.poll_once()
    assert len(files) == 2
    svc.set_cards(cards)  # same data again: nothing to read again
    svc.watcher.poll_once()
    assert len(files) == 2
    svc.stop()
    assert _other_language(CardDB(), cards) and not _other_language(cards, cards)
    assert not _other_language(cards, CardDB())

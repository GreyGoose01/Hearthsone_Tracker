"""Glue between the log watcher, the parser, the tracker, the database and
the simulator. UI-agnostic: callbacks run on background threads, the GUI
re-dispatches them to the GTK main loop."""

from __future__ import annotations

import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from hearthwatch.bg.models import CombatSnapshot, LiveState, MatchResult
from hearthwatch.bg.tracker import BattlegroundsTracker
from hearthwatch.cards import CardDB
from hearthwatch.db import MatchDB
from hearthwatch.hsprocess import hearthstone_running
from hearthwatch.i18n import N_, _
from hearthwatch.logwatcher import LogFollower, LogWatcher, find_power_logs
from hearthwatch.power.game_state import GameState
from hearthwatch.sim.montecarlo import SimResult, simulate_combat

log = logging.getLogger(__name__)


@dataclass
class Callbacks:
    on_state: Callable[[LiveState], None] = lambda s: None
    on_combat: Callable[[CombatSnapshot], None] = lambda c: None
    on_combat_result: Callable[[CombatSnapshot], None] = lambda c: None
    on_sim: Callable[[CombatSnapshot, SimResult], None] = lambda c, r: None
    on_match_saved: Callable[[MatchResult], None] = lambda r: None
    on_file: Callable[[Path], None] = lambda p: None
    on_unknown_cards: Callable[[set[str]], None] = lambda ids: None
    on_log_stalled: Callable[[bool], None] = lambda stalled: None


# LoadingScreen.log: "... prevMode=GAMEPLAY currMode=BACON" when a game is left
MODE_RE = re.compile(r"prevMode=(\w+).*currMode=(\w+)")
GAMEPLAY = "GAMEPLAY"
# after leaving a game, wait this long for Power.log to report the end itself
LEFT_GAME_GRACE = 5.0
INCOMPLETE_NOTICE = N_(
    "You left the last game, but Hearthstone did not log it to the end – usually because "
    "of the log size limit. Restart Hearthstone completely and the next game will be logged in full."
)

# written by Hearthstone as the last line before it stops logging
TRUNCATED_MARKER = "has reached the size limit"

# A running Battlegrounds game writes Power.log all the time (timers, shop,
# combat). This long without a new line means Hearthstone stopped logging -
# usually its log size limit (see hearthwatch.clientconfig).
STALL_SECONDS = 180.0


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _other_language(old: CardDB, new: CardDB) -> bool:
    """Do two card databases name cards differently (one empty, or another language)?"""
    if not len(new):
        return False
    if not len(old):
        return True
    sample = [c.id for c in new.bg_minions()[:30]] or ["TB_BaconShopBob"]
    return any(old.name(cid) != new.name(cid) for cid in sample)


class TrackerService:
    """Follows the newest Power.log and reports the game in it as *live* only
    while it belongs to the running Hearthstone session.

    Hearthstone creates a new Power.log only with the first game of a
    session. Until then (main menu, or the game is not even running) the
    newest file is an old one whose last game may look unfinished - that game
    must not be shown as running.
    """

    def __init__(
        self,
        logs_dir: Path,
        db: MatchDB,
        cards: CardDB,
        callbacks: Callbacks,
        sim_runs: int = 2000,
        hs_running: Callable[[], bool | None] = hearthstone_running,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.logs_dir = logs_dir
        self._clock = clock
        self._last_growth = clock()
        self._stalled = False
        self._truncated = False  # Power.log ended with Hearthstone's size-limit message
        self._modes: LogFollower | None = None  # LoadingScreen.log of the session
        self._left_game = False  # LoadingScreen says the game scene was left
        self.db = db
        self.cards = cards
        self.cb = callbacks
        self.sim_runs = sim_runs
        self._hs_running = hs_running
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="hearthwatch-sim")
        self._replaying = False
        self._live = False
        self._unknown_reported: set[str] = set()
        self._pending_combat: CombatSnapshot | None = None
        self.tracker = BattlegroundsTracker(
            cards, on_state=self._state, on_combat=self._combat, on_match_end=self._match_end,
            on_combat_result=self._combat_result,
        )
        self.game = GameState([self.tracker])
        self.watcher = LogWatcher(logs_dir, self._lines, self._new_file, on_scan=self._scan)

    @property
    def live(self) -> bool:
        return self._live

    def is_current(self, path: Path | None) -> bool:
        """Does ``path`` belong to the Hearthstone session that is running now?"""
        if path is None:
            return False
        if self._hs_running() is False:  # None = unknown (no /proc): only check folders
            return False
        try:
            sessions = [d for d in self.logs_dir.iterdir() if d.is_dir()]
        except OSError:
            sessions = []
        if path.parent == self.logs_dir or not sessions:
            return True
        newest = max(sessions, key=lambda d: (_mtime(d), d.name))
        return path.parent == newest

    # -- lifecycle -----------------------------------------------------------
    def start(self) -> None:
        self.watcher.start()

    def stop(self) -> None:
        self.watcher.stop()
        self._executor.shutdown(wait=False, cancel_futures=True)

    def set_cards(self, cards: CardDB) -> None:
        """Use new card data and fix names that were shown as card IDs. Texts and buffs
        of a game read with other card data (none yet, or another language) are only
        right after reading the log again."""
        with self._lock:
            reread = _other_language(self.cards, cards)
            self.cards = cards
            self.tracker.cards = cards
            self.tracker.relabel()
            self.tracker.batch_done(self.game)
        if reread and self.watcher.current_file is not None:
            log.info("card data changed language: reading the log again")
            self.watcher.reread()
        if len(cards):
            try:
                fixed = self.db.fix_names(cards.name)
            except Exception:  # the history is not worth crashing for
                log.exception("could not fix stored names")
            else:
                if fixed:
                    log.info("filled in names of %d stored games", fixed)

    # -- watcher callbacks (watcher thread) -------------------------------------
    def _new_file(self, path: Path) -> None:
        with self._lock:
            self.tracker.source = str(path)
            self.game = GameState([self.tracker])
            # the file is read from its beginning: rebuild silently, then go live
            self._replaying = True
            self._pending_combat = None
            screen = path.parent / "LoadingScreen.log"
            self._modes = LogFollower(screen) if path.parent != self.logs_dir else None
            self._left_game = False
            self._truncated = False
        self.cb.on_file(path)

    def _lines(self, lines: list[str]) -> None:
        self._last_growth = self._clock()
        if any(TRUNCATED_MARKER in line for line in lines):
            # Hearthstone's own last words before it stops writing Power.log
            log.warning("Power.log reached Hearthstone's log size limit - no more game data")
            self._truncated = True
        if self._stalled and not self._truncated:
            self._stalled = False
            self.cb.on_log_stalled(False)
        elif self._truncated and not self._stalled and self._live:
            self._stalled = True
            self.cb.on_log_stalled(True)
        with self._lock:
            for line in lines:
                self.game.feed_line(line)
            self._replaying = False
            self.tracker.batch_done(self.game)
            unknown = set(self.tracker.unknown_cards) - self._unknown_reported
        if unknown:
            # e.g. a new Battlegrounds season: the card data may need a refresh
            self._unknown_reported |= unknown
            self.cb.on_unknown_cards(unknown)
        if self._live:
            self._flush_pending()

    def _flush_pending(self) -> None:
        """Caught up with a running game: still show and simulate its latest combat."""
        with self._lock:
            pending, self._pending_combat = self._pending_combat, None
            current = self.tracker.state.last_combat
        # only if it is the running game's latest combat (not one of an older game)
        if (
            pending is not None and self.tracker.state.in_game
            and current is not None and current.round == pending.round
        ):
            self._combat(pending)

    def _check_stall(self) -> None:
        idle = self._clock() - self._last_growth
        # after the size-limit message nothing more is logged in this Hearthstone session
        stalled = self._live and (
            self._truncated or (self.tracker.state.in_game and idle > STALL_SECONDS)
        )
        if stalled and not self._stalled:
            log.warning("Power.log has not grown for %.0f s during a game - log size limit?",
                        self._clock() - self._last_growth)
            self._stalled = True
            self.cb.on_log_stalled(True)
        elif not stalled and self._stalled and (
            not self._live or not self.tracker.state.in_game or self._truncated
        ):
            self._stalled = False
            self.cb.on_log_stalled(False)

    def _scan(self, path: Path | None) -> None:
        live = self.is_current(path)
        if live != self._live and live:
            self._last_growth = self._clock()  # don't count the time before the game was live
        self._update_live(live)
        self._check_stall()
        self._check_left_game()

    def _check_left_game(self) -> None:
        """Power.log may stop (log size limit) - then the game end never arrives.
        LoadingScreen.log still reports leaving the game scene."""
        if self._modes is not None:
            for line in self._modes.read_lines():
                m = MODE_RE.search(line)
                if not m:
                    continue
                prev, curr = m.groups()
                if curr == GAMEPLAY:
                    self._left_game = False
                elif prev == GAMEPLAY:
                    self._left_game = True
        if not (self._left_game and self.tracker.state.in_game):
            return
        if self._clock() - self._last_growth < LEFT_GAME_GRACE:
            return  # Power.log is still catching up with the end of the game
        log.warning("game scene left but Power.log never reported the end of the game")
        with self._lock:
            self.tracker.abandon(_(INCOMPLETE_NOTICE))
        self._left_game = False
        if self._stalled:
            self._stalled = False
            self.cb.on_log_stalled(False)

    def _update_live(self, live: bool) -> None:
        if live == self._live:
            return
        self._live = live
        if live:
            with self._lock:
                state = self.tracker.snapshot()
            self.cb.on_state(state)
            self._flush_pending()
        else:
            # old session or Hearthstone closed: nothing is running
            self.cb.on_state(LiveState())

    # -- tracker callbacks ---------------------------------------------------
    def _state(self, state: LiveState) -> None:
        if not self._replaying and self._live:
            self.cb.on_state(state)

    def _combat(self, combat: CombatSnapshot) -> None:
        if self._replaying or not self._live:
            self._pending_combat = combat
            return
        self.cb.on_combat(combat)
        health = self.tracker.state.health + self.tracker.state.armor or None
        self._executor.submit(self._simulate, combat, health)

    def _combat_result(self, combat: CombatSnapshot) -> None:
        if self._replaying or not self._live:
            if self._pending_combat is not None and self._pending_combat.round == combat.round:
                self._pending_combat = combat
            return
        self.cb.on_combat_result(combat)

    def _simulate(self, combat: CombatSnapshot, health: int | None) -> None:
        try:
            result = simulate_combat(
                combat, player_health=health, en_names=self.cards.en_name, runs=self.sim_runs
            )
        except Exception:
            log.exception("simulation failed")
            return
        self.cb.on_sim(combat, result)

    def _match_end(self, result: MatchResult) -> None:
        # also store games found while catching up on an existing file
        if result.placement > 0 and self.db.add(result) is not None:
            self.cb.on_match_saved(result)


def import_logs(logs_dir: Path, db: MatchDB, cards: CardDB) -> int:
    """Import every finished Battlegrounds game from all Power.log files."""
    saved = 0

    def store(result: MatchResult) -> None:
        nonlocal saved
        if result.placement > 0 and db.add(result) is not None:
            saved += 1

    for path in find_power_logs(logs_dir):
        tracker = BattlegroundsTracker(cards, on_match_end=store)
        tracker.source = str(path)
        game = GameState([tracker])
        with path.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                game.feed_line(line)
    return saved

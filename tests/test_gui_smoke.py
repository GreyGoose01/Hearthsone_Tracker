"""Builds every window of the GUI with the real GTK/libadwaita of this system.

Skipped where PyGObject or a display is missing (e.g. plain CI runners);
the distribution jobs in CI set HEARTHWATCH_REQUIRE_GUI=1 and run it under Xvfb,
so it fails there instead of being skipped.
"""

import os

import pytest

from hearthwatch.bg.models import CombatOutcome
from hearthwatch.bg.tracker import BattlegroundsTracker
from hearthwatch.power.game_state import GameState
from hearthwatch.sim.montecarlo import SimResult

REQUIRED = os.environ.get("HEARTHWATCH_REQUIRE_GUI") == "1"


def _gtk():
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        if REQUIRED:
            pytest.fail("HEARTHWATCH_REQUIRE_GUI=1 but no DISPLAY/WAYLAND_DISPLAY")
        pytest.skip("no display")
    try:
        import gi

        gi.require_version("Gtk", "4.0")
        gi.require_version("Adw", "1")
        from gi.repository import Adw, GLib, Gtk
    except (ImportError, ValueError) as exc:
        if REQUIRED:
            raise
        pytest.skip(f"no PyGObject/GTK 4/libadwaita: {exc}")
    if not Gtk.init_check():
        if REQUIRED:
            pytest.fail("GTK could not open a display")
        pytest.skip("no display")
    Adw.init()
    return Gtk, GLib


def _children(widget):
    child = widget.get_first_child()
    while child is not None:
        yield child
        child = child.get_next_sibling()


def _replay(bg_log, cards):
    states, combats, results = [], [], []
    tracker = BattlegroundsTracker(cards, states.append, combats.append, results.append)
    game = GameState([tracker])
    for line in bg_log.read_text().splitlines():
        game.feed_line(line)
        tracker.batch_done(game)
    return states, combats, results


@pytest.mark.parametrize("language", ["de", "en"])
def test_all_windows_build(bg_log, cards, pool_cards, tmp_path, language):
    Gtk, GLib = _gtk()
    from hearthwatch import i18n, versions
    from hearthwatch.db import MatchDB
    from hearthwatch.settings import Settings
    from hearthwatch.ui.history_page import HistoryPage
    from hearthwatch.ui.main_view import MainView
    from hearthwatch.ui.minions_window import MinionsPage
    from hearthwatch.ui.settings_window import SettingsDialog
    from hearthwatch.ui.widgets import install_css, set_font_scale

    assert versions.runtime_problems() == []
    i18n.set_language(language)
    install_css()
    set_font_scale(110)

    states, combats, results = _replay(bg_log, cards)
    view = MainView()
    view.set_wide(True)
    view.apply_settings(Settings())
    live = next(s for s in states if s.in_game and s.phase == "combat")
    view.update_state(live)
    combat = combats[0]
    view.update_combat(combat)
    view.update_sim(combat, SimResult(runs=10, win=0.5, draw=0.2, loss=0.3, avg_damage_dealt=4.0,
                                      avg_damage_taken=3.0, lethal_risk=0.1, unsupported=["X"]))
    combat.actual = CombatOutcome("loss", 4)
    view.update_result(combat)
    for s in states:
        view.update_state(s)
    assert view.get_visible_child_name() == "summary"
    view.show_waiting("notice")

    db = MatchDB(tmp_path / "matches.db")
    db.add(results[0])
    HistoryPage(db)
    minions = MinionsPage()
    minions.update_state(None)
    minions.set_cards(pool_cards)
    minions.update_state(live)
    for button in list(_children(minions.tier_buttons))[-1:]:
        button.set_active(True)

    changes = []
    SettingsDialog(Settings(), changes.append)
    win = Gtk.Window(child=view)
    win.present()
    ctx = GLib.MainContext.default()
    while ctx.pending():
        ctx.iteration(False)
    win.destroy()

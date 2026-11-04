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


def test_minion_popup_and_fitting(bg_log, cards):
    Gtk, _GLib = _gtk()
    from hearthwatch.bg.models import Minion
    from hearthwatch.ui import widgets
    from hearthwatch.ui.main_view import MainView

    widgets.install_css()
    m = Minion("BG_X", 12, 13, name="Volumizer", golden=True, taunt=True, tribes=("MECHANICAL",),
               text="Magnetic.", buffs=["Well Repaired (4/8)", "Volumized (5/2)"],
               buff_texts=["+4/+8.", ""])
    tip = widgets.minion_tooltip(m)
    texts = []
    child = tip
    stack = [child]
    while stack:  # every label in the popup
        w = stack.pop()
        if isinstance(w, Gtk.Label):
            texts.append(w.get_label())
        c = w.get_first_child()
        while c is not None:
            stack.append(c)
            c = c.get_next_sibling()
    assert "★ Volumizer" in texts and "✦ Well Repaired (4/8)" in texts and "+4/+8." in texts

    # a view that is much too narrow for the wanted scale steps down until it fits (or to 1.0)
    states = []
    tracker = BattlegroundsTracker(cards, states.append)
    game = GameState([tracker])
    game.feed_lines(bg_log.read_text().splitlines())
    view = MainView()
    view.update_state(next(s for s in reversed(states) if s.in_game))
    view._width, view._target = 300, 1.6
    view._apply_scale()
    assert view._scale == 1.0
    widgets.set_ui_scale(1.0)


def test_white_bars_are_cut_off_the_art(tmp_path):
    _gtk()
    from gi.repository import GdkPixbuf

    from hearthwatch.ui import widgets

    # 256x256: white bars of 40 px left and right around a dark picture
    pix = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 256, 256)
    pix.fill(0xFFFFFFFF)
    pix.new_subpixbuf(40, 0, 176, 256).fill(0x303030FF)
    assert widgets._light_border(pix) == (40, 0, 40, 0)
    out = widgets._crop_art(pix)
    assert out.get_width() == out.get_height()
    assert widgets._light_border(out) == (0, 0, 0, 0)  # only the picture is left

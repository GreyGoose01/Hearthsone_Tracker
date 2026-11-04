"""GTK application: the live main window plus history, setup check and settings."""

from __future__ import annotations

import logging
import sys
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from hearthwatch import __version__, clientconfig, i18n, logconfig, paths  # noqa: E402
from hearthwatch.cards import CardDB  # noqa: E402
from hearthwatch.db import MatchDB  # noqa: E402
from hearthwatch.diagnose import Check, banner_key, banner_problem, run_checks  # noqa: E402
from hearthwatch.i18n import _  # noqa: E402
from hearthwatch.service import Callbacks, TrackerService  # noqa: E402
from hearthwatch.ui.diagnose_window import DiagnoseWindow  # noqa: E402
from hearthwatch.ui.history_page import HistoryWindow  # noqa: E402
from hearthwatch.ui.minions_window import MinionsWindow  # noqa: E402
from hearthwatch import settings as app_settings  # noqa: E402
from hearthwatch.art import ArtCache  # noqa: E402
from hearthwatch.ui.main_view import MainView  # noqa: E402
from hearthwatch.ui.settings_window import SettingsDialog  # noqa: E402
from hearthwatch.ui.widgets import install_css, set_art_provider, set_font_scale  # noqa: E402

APP_ID = "io.github.greygoose01.hearthwatch"
APP_NAME = "Hearthwatch"
WEBSITE = "https://github.com/GreyGoose01/hearthwatch"
UNKNOWN_CARDS_REFRESH_AGE = 6 * 3600  # re-download card data for unknown cards if older


def _idle(fn):
    """Wrap a callback so it runs on the GTK main loop."""

    def wrapper(*args):
        GLib.idle_add(lambda: (fn(*args), False)[1])

    return wrapper


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application, db: MatchDB) -> None:
        super().__init__(application=app, title=APP_NAME)
        self.set_default_size(460, 900)
        self.set_size_request(360, 420)

        # everything live on one page; the history has its own window
        self.live = MainView()

        header = Adw.HeaderBar()
        header.set_title_widget(Adw.WindowTitle(title=APP_NAME))
        history = Gtk.Button(icon_name="document-open-recent-symbolic", tooltip_text=_("History & statistics"))
        history.set_action_name("app.history")
        header.pack_start(history)
        minions = Gtk.Button(icon_name="view-grid-symbolic", tooltip_text=_("Minions by tier"))
        minions.set_action_name("app.minions")
        header.pack_start(minions)
        menu = Gio.Menu()
        menu.append(_("Check setup"), "app.diagnose")
        menu.append(_("Set up logging"), "app.setup-logs")
        menu.append(_("Settings"), "app.settings")
        menu.append(_("About Hearthwatch"), "app.about")
        header.pack_end(Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu))

        self.banner = Adw.Banner(button_label=_("Details"))
        self._banner_action = "diagnose"
        self._banner_key = ""
        self._dismissed: set[str] = set()  # problems already opened from the banner
        self.banner.connect("button-clicked", self._on_banner_button)

        self.toasts = Adw.ToastOverlay()
        self.toasts.set_child(self.live)

        # wide window: lobby in a second column
        if hasattr(Adw, "Breakpoint"):  # libadwaita >= 1.4
            bp = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("min-width: 860sp"))
            bp.connect("apply", lambda *_: self.live.set_wide(True))
            bp.connect("unapply", lambda *_: self.live.set_wide(False))
            self.add_breakpoint(bp)

        view = Adw.ToolbarView()
        view.add_top_bar(header)
        view.add_top_bar(self.banner)
        view.set_content(self.toasts)
        self.set_content(view)
        self.update_banner()

    def set_log_stalled(self, stalled: bool) -> None:
        """Hearthstone stopped writing Power.log during a game (size limit?)."""
        self._log_stalled = stalled
        self.update_banner()

    def _on_banner_button(self, *_args) -> None:
        if self._banner_key:
            self._dismissed.add(self._banner_key)  # seen - do not keep showing it
        self.get_application().activate_action(self._banner_action)
        self.update_banner()

    def update_banner(self) -> list[Check]:
        checks = run_checks()
        if getattr(self, "_log_stalled", False):
            self.banner.set_title(_(
                "Hearthstone stopped writing the Power.log (10 MB log size limit reached). "
                "Click “Set up”, then restart Hearthstone completely."
            ))
            self._banner_action = "setup-logs"
            self.banner.set_button_label(_("Set up"))
            self.banner.set_revealed(True)
            return checks
        self._banner_key = ""
        problem = banner_problem(checks, self.live.in_game, self._dismissed)
        if problem is None:
            self.banner.set_revealed(False)
            return checks
        self._banner_key = banner_key(problem)
        self.banner.set_title(problem.banner or f"{problem.title}: {problem.hint or problem.detail}")
        if problem.action == "setup-logs":
            self._banner_action = "setup-logs"
            self.banner.set_button_label(_("Set up"))
        else:
            self._banner_action = "diagnose"
            self.banner.set_button_label(_("Details"))
        self.banner.set_revealed(True)
        return checks

    def toast(self, text: str) -> None:
        self.toasts.add_toast(Adw.Toast(title=text, timeout=4))


class TrackerApp(Adw.Application):
    def __init__(self, language: str | None = None, offline: bool = False) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.settings = app_settings.load()
        i18n.set_language(language or self.settings.language)  # --lang overrides the setting
        self.locale = i18n.card_locale()
        # last values shown, replayed into a rebuilt window after a language switch
        self._last: dict[str, object] = {}
        self.offline = offline
        self.art: ArtCache | None = None
        self.window: MainWindow | None = None
        self.service: TrackerService | None = None
        self._add_action("setup-logs", self._on_setup_logs)
        self._add_action("diagnose", self._on_diagnose)
        self._add_action("history", self._on_history)
        self._add_action("minions", self._on_minions)
        self._minions_window: MinionsWindow | None = None
        self.cards = CardDB()
        self._add_action("settings", self._on_settings)
        self._forced_card_refresh = False
        self._diagnose_window: DiagnoseWindow | None = None
        self._settings_dialog = None
        self._history_window: HistoryWindow | None = None
        self.db: MatchDB | None = None
        self._add_action("about", self._on_about)

    def _add_action(self, name: str, callback) -> None:
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", lambda *_: callback())
        self.add_action(action)

    def do_activate(self) -> None:
        if self.window is not None:
            self.window.present()
            return
        install_css()
        Gtk.Window.set_default_icon_name(APP_ID)
        tp = paths.tracker_paths()
        tp.ensure()
        db = MatchDB(tp.database)
        self.db = db
        self.art = ArtCache(tp.cache_dir, enabled=self.settings.show_art and not self.offline)
        set_art_provider(self.art)
        set_font_scale(self.settings.font_scale)
        win = self._build_window()

        callbacks = Callbacks(
            on_state=_idle(lambda v: self._forward("state", v)),
            on_combat=_idle(lambda v: self._forward("combat", v)),
            on_combat_result=_idle(lambda v: self._forward("result", v)),
            on_sim=_idle(lambda c, r: self._forward("sim", (c, r))),
            on_match_saved=_idle(self._on_match_saved),
            on_file=_idle(lambda p: None),
            on_unknown_cards=self._on_unknown_cards,
            on_log_stalled=_idle(lambda v: self._forward("stalled", v)),
        )
        logs_dir = paths.find_game_dir() / "Logs"
        if not logs_dir.is_dir():
            win.live.show_waiting(_(
                "No log folder found ({path}). Is Hearthstone installed with "
                "hearthstone-linux-gui? Hearthwatch keeps waiting."
            ).format(path=logs_dir))
        # local card cache first (fast), so names are right from the start
        cards = CardDB.load(tp.cache_dir, self.locale, download=False)
        self._set_cards(cards)
        self.service = TrackerService(logs_dir, db, cards, callbacks, sim_runs=self.settings.sim_runs)
        self.service.start()
        if not self.offline:
            self._refresh_cards_async(force=False)
        elif not len(cards):
            win.toast(_("Card data not available – showing card IDs."))
        GLib.timeout_add_seconds(5, self._recheck)
        win.present()

    def _build_window(self) -> MainWindow:
        self.window = MainWindow(self, self.db)
        win = self.window
        win.set_default_size(self.settings.window_width, self.settings.window_height)
        win.live.apply_settings(self.settings)
        win.connect("close-request", self._remember_size)
        return win

    def _forward(self, kind: str, value) -> None:
        """Send a service update to the current window (and remember it)."""
        self._last[kind] = value
        if self.window is None:
            return
        if kind == "state" and self._minions_window is not None:
            self._minions_window.page.update_state(value)
        live = self.window.live
        {
            "state": live.update_state,
            "combat": live.update_combat,
            "sim": lambda v: live.update_sim(*v),
            "result": live.update_result,
            "stalled": self.window.set_log_stalled,
        }[kind](value)

    def _rebuild_window(self) -> None:
        """Language switch: build the window again with the new texts."""
        old = self.window
        if old is None:
            return
        width, height = old.get_width(), old.get_height()
        maximized = old.is_maximized()
        self._remember_size(old)
        self.window = None
        win = self._build_window()
        if width > 0 and height > 0:
            win.set_default_size(width, height)
        if maximized:
            win.maximize()
        # state first (starts the game view), then the combat, then state again for the focus
        for kind in ("stalled", "state", "combat", "sim", "result", "state"):
            if kind in self._last:
                self._forward(kind, self._last[kind])
            if kind == "state":
                win.live.keep_predictions(old.live)
        reopen_settings = self._settings_dialog is not None
        for attr in ("_diagnose_window", "_history_window", "_minions_window", "_settings_dialog"):
            child = getattr(self, attr)
            setattr(self, attr, None)
            if child is None:
                continue
            if isinstance(child, getattr(Adw, "Dialog", ())):
                child.force_close()
            else:
                child.destroy()
        win.present()
        old.destroy()
        if reopen_settings:
            self._on_settings()

    def _recheck(self) -> bool:
        """Re-run the setup checks so the banner follows Hearthstone restarts."""
        try:
            if self.window is not None:
                checks = self.window.update_banner()
                if self._diagnose_window is not None:
                    self._diagnose_window.show_checks(checks)
        except Exception:  # never let one failed check stop the 5 s timer
            logging.getLogger(__name__).exception("setup check failed")
        return True

    def _refresh_cards_async(self, force: bool) -> None:
        threading.Thread(
            target=self._refresh_cards, args=(force,), daemon=True, name="hearthwatch-cards"
        ).start()

    def _refresh_cards(self, force: bool) -> None:
        """Download card data if stale (or forced) and fix names shown so far."""
        cache_dir = paths.tracker_paths().cache_dir
        before = CardDB.cache_age(cache_dir, self.locale)
        cards = CardDB.load(cache_dir, self.locale, download=True, force=force)
        after = CardDB.cache_age(cache_dir, self.locale)
        updated = after is not None and (before is None or after < before)
        if len(cards) and (updated or force or not len(self.cards)):
            GLib.idle_add(lambda: (self._set_cards(cards), False)[1])
        if self.service is not None and len(cards) and (updated or force):
            self.service.set_cards(cards)
        elif not len(cards):
            GLib.idle_add(lambda: (self.window and self.window.toast(
                _("Card data not available – showing card IDs.")), False)[1])

    def _on_unknown_cards(self, card_ids: set[str]) -> None:
        """Unknown cards (e.g. a new season): refresh the card data once per session."""
        if self.offline or self._forced_card_refresh:
            return
        age = CardDB.cache_age(paths.tracker_paths().cache_dir, self.locale)
        if age is not None and age < UNKNOWN_CARDS_REFRESH_AGE:
            return
        self._forced_card_refresh = True
        logging.getLogger(__name__).info("unknown cards %s - refreshing card data", sorted(card_ids))
        self._refresh_cards_async(force=True)

    def _on_match_saved(self, result) -> None:
        if self.window is None:
            return
        if self._history_window is not None:
            self._history_window.refresh()
        self.window.toast(_("Game saved: place {place} with {hero}").format(
            place=result.placement, hero=result.hero_name))

    def _on_setup_logs(self) -> None:
        if self.window is None:
            return
        files: list[str] = []
        try:
            if logconfig.ensure(paths.log_config_path()):
                files.append("log.config")
            files += [p.name for p in clientconfig.ensure()]
        except OSError as exc:
            self.window.toast(_("Setup failed: {error}").format(error=exc))
            logging.getLogger(__name__).exception("setup failed")
            return
        logging.getLogger(__name__).info("setup changed: %s", files or "nothing")
        self.window.set_log_stalled(False)
        self._recheck()
        if files:
            self.window.toast(_("Changed: {files} – please restart Hearthstone completely.").format(
                files=", ".join(files)))
        elif clientconfig.is_configured():
            self.window.toast(_("Everything is already set up."))
        else:
            self.window.toast(_("client.config not found – see “Check setup” for details."))

    def _on_history(self) -> None:
        if self.window is None or self.db is None:
            return
        if self._history_window is None:
            self._history_window = HistoryWindow(self, self.window, self.db)

            def closed(*_):
                self._history_window = None
                return False

            self._history_window.connect("close-request", closed)
        else:
            self._history_window.refresh()
        self._history_window.present()

    def _set_cards(self, cards: CardDB) -> None:
        """New card data (main loop): keep it for the minion browser."""
        self.cards = cards
        if self._minions_window is not None:
            self._minions_window.page.set_cards(cards)

    def _on_minions(self) -> None:
        if self.window is None:
            return
        if self._minions_window is None:
            self._minions_window = MinionsWindow(self, self.window)
            self._minions_window.page.set_cards(self.cards)
            self._minions_window.page.update_state(self._last.get("state"))

            def closed(*_):
                self._minions_window = None
                return False

            self._minions_window.connect("close-request", closed)
        self._minions_window.present()

    def _on_diagnose(self) -> None:
        if self.window is None:
            return
        if self._diagnose_window is None:
            self._diagnose_window = DiagnoseWindow(self, self.window)

            def closed(*_):
                self._diagnose_window = None
                return False

            self._diagnose_window.connect("close-request", closed)
        self._diagnose_window.show_checks(run_checks())
        self._diagnose_window.present()

    def _on_about(self) -> None:
        props = dict(
            application_name=APP_NAME,
            application_icon=APP_ID,
            version=__version__,
            comments=_("Battlegrounds tracker for Hearthstone on Linux (hearthstone-linux-gui).\n"
                       "Card data: HearthstoneJSON. Not affiliated with Blizzard Entertainment."),
            website=WEBSITE,
        )
        if hasattr(Adw, "AboutDialog"):  # libadwaita >= 1.5
            Adw.AboutDialog(**props).present(self.window)
        else:
            Adw.AboutWindow(transient_for=self.window, **props).present()

    # -- settings ---------------------------------------------------------------
    def _on_settings(self) -> None:
        if self.window is None:
            return
        dialog = SettingsDialog(self.settings, self._apply_settings)
        self._settings_dialog = dialog

        def closed(*_):
            if self._settings_dialog is dialog:
                self._settings_dialog = None
            return False

        if isinstance(dialog, getattr(Adw, "Dialog", ())):
            dialog.connect("closed", closed)
            dialog.present(self.window)
        else:
            dialog.connect("close-request", closed)
            dialog.set_transient_for(self.window)
            dialog.present()

    def _apply_settings(self, new: app_settings.Settings) -> None:
        old, self.settings = self.settings, new
        try:
            app_settings.save(new)
        except OSError as exc:
            logging.getLogger(__name__).warning("could not save settings: %s", exc)
        set_font_scale(new.font_scale)
        if self.art is not None:
            self.art.enabled = new.show_art and not self.offline
        if self.service is not None:
            self.service.sim_runs = new.sim_runs
        language_changed = new.language != old.language
        if language_changed:
            i18n.set_language(new.language)
            locale = i18n.card_locale()
            if locale != self.locale:
                self.locale = locale
                threading.Thread(target=self._reload_cards, daemon=True, name="hearthwatch-cards").start()
        if self.window is not None:
            self.window.live.apply_settings(new)
        if language_changed:
            # after the settings dialog has closed its signal handler
            GLib.idle_add(lambda: (self._rebuild_window(), False)[1])

    def _reload_cards(self) -> None:
        cards = CardDB.load(paths.tracker_paths().cache_dir, self.locale, download=not self.offline)
        if len(cards):
            GLib.idle_add(lambda: (self._set_cards(cards), False)[1])
        if self.service is not None and len(cards):
            self.service.set_cards(cards)

    def _remember_size(self, window) -> bool:
        width, height = window.get_width(), window.get_height()
        if width > 0 and height > 0 and not window.is_maximized():
            self.settings.window_width, self.settings.window_height = width, height
            try:
                app_settings.save(self.settings.normalized())
            except OSError:
                pass
        return False

    def do_shutdown(self) -> None:
        if self.art is not None:
            self.art.shutdown()
        if self.service is not None:
            self.service.stop()
        Adw.Application.do_shutdown(self)


def run(language: str | None = None, offline: bool = False) -> int:
    app = TrackerApp(language=language, offline=offline)
    return app.run([sys.argv[0]])

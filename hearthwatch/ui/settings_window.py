"""Settings dialog: changes apply at once and are saved."""

from __future__ import annotations

from dataclasses import replace
from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk  # noqa: E402

from hearthwatch.i18n import _  # noqa: E402
from hearthwatch.settings import LANGUAGES, SIM_RUNS, Settings  # noqa: E402

_Base = Adw.PreferencesDialog if hasattr(Adw, "PreferencesDialog") else Adw.PreferencesWindow


class SettingsDialog(_Base):
    def __init__(self, settings: Settings, on_change: Callable[[Settings], None]) -> None:
        super().__init__(title=_("Settings"))
        self._settings = settings
        self._on_change = on_change

        page = Adw.PreferencesPage(title=_("Settings"), icon_name="preferences-system-symbolic")

        general = Adw.PreferencesGroup()
        languages = list(LANGUAGES)
        names = {"auto": _("Automatic (system)"), "en": "English", "de": "Deutsch"}
        lang = Adw.ComboRow(title=_("Language"), subtitle=_("Interface and card names"),
                            model=Gtk.StringList.new([names[c] for c in languages]))
        lang.set_selected(languages.index(settings.language))
        lang.connect("notify::selected", lambda r, _p: self._set("language", languages[r.get_selected()]))
        general.add(lang)
        page.add(general)

        view = Adw.PreferencesGroup(title=_("Display"))
        view.add(self._switch(_("Card art"), _("Pictures of heroes and minions (downloaded once)"),
                              "show_art"))
        scale = Adw.SpinRow.new_with_range(80, 150, 10)
        scale.set_title(_("Font size"))
        scale.set_subtitle(_("in percent"))
        scale.set_value(settings.font_scale)
        scale.connect("notify::value", lambda r, _p: self._set("font_scale", int(r.get_value())))
        view.add(scale)
        view.add(self._switch(_("Grow with the window"), _("Bigger pictures and text in a big window"),
                              "scale_with_window"))
        page.add(view)

        sections = Adw.PreferencesGroup(title=_("Sections"), description=_("What the live view shows"))
        sections.add(self._switch(_("Your buffs"), _("Game-wide buffs and your current board"), "show_buffs"))
        sections.add(self._switch(_("Results"), _("Result dots of all combats in this game"), "show_history"))
        sections.add(self._switch(_("Minion types"), _("Types seen and missing in this lobby"), "show_tribes"))
        sections.add(self._switch(_("Boards in the lobby"), _("Last board of every opponent as small cards"),
                                  "show_lobby_boards"))
        page.add(sections)

        data = Adw.PreferencesGroup(title=_("Simulation"))
        runs = Adw.ComboRow(title=_("Simulations per combat"), subtitle=_("more = more accurate, but slower"),
                            model=Gtk.StringList.new([str(n) for n in SIM_RUNS]))
        runs.set_selected(SIM_RUNS.index(settings.sim_runs))
        runs.connect("notify::selected", lambda r, _p: self._set("sim_runs", SIM_RUNS[r.get_selected()]))
        data.add(runs)
        page.add(data)
        self.add(page)

    def _switch(self, title: str, subtitle: str, field: str) -> Adw.SwitchRow:
        row = Adw.SwitchRow(title=title, subtitle=subtitle)
        row.set_active(getattr(self._settings, field))
        row.connect("notify::active", lambda r, _p: self._set(field, r.get_active()))
        return row

    def _set(self, field: str, value) -> None:
        if getattr(self._settings, field) == value:
            return
        self._settings = replace(self._settings, **{field: value})
        self._on_change(self._settings)

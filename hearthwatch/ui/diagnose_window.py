"""Window listing the setup checks with a hint for each open step."""

from __future__ import annotations

from gi.repository import Adw, Gdk, Gtk

from hearthwatch.diagnose import ERROR, OK, Check, format_checks, run_checks
from hearthwatch.i18n import _

ICONS = {
    OK: ("emblem-ok-symbolic", "success"),
    "warn": ("dialog-warning-symbolic", "warning"),
    ERROR: ("dialog-error-symbolic", "error"),
}


class DiagnoseWindow(Adw.Window):
    def __init__(self, app: Adw.Application, parent: Gtk.Window) -> None:
        super().__init__(application=app, transient_for=parent, title=_("Check setup"))
        self.set_default_size(520, 560)
        self._checks: list[Check] = []

        header = Adw.HeaderBar()
        refresh = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text=_("Check again"))
        refresh.connect("clicked", lambda *_: self.show_checks(run_checks()))
        header.pack_start(refresh)
        copy = Gtk.Button(label=_("Copy report"), tooltip_text=_("Copy the result to the clipboard"))
        copy.connect("clicked", self._copy)
        header.pack_end(copy)

        self.group = Adw.PreferencesGroup(
            title=_("So Hearthwatch can read along"),
            description=_("Hearthstone only writes the Power.log if a matching log.config sits next to "
                          "its options.txt. This list shows which step is still missing."),
        )
        self.setup_button = Gtk.Button(label=_("Set up log.config"), valign=Gtk.Align.CENTER)
        self.setup_button.add_css_class("suggested-action")
        self.setup_button.connect("clicked", lambda *_: app.activate_action("setup-logs"))
        self.group.set_header_suffix(self.setup_button)
        self._rows: list[Gtk.Widget] = []

        page = Adw.PreferencesPage()
        page.add(self.group)
        self.toasts = Adw.ToastOverlay(child=page)
        view = Adw.ToolbarView()
        view.add_top_bar(header)
        view.set_content(self.toasts)
        self.set_content(view)

    def show_checks(self, checks: list[Check]) -> None:
        self._checks = checks
        for row in self._rows:
            self.group.remove(row)
        self._rows.clear()
        for c in checks:
            row = Adw.ActionRow(title=c.title)
            subtitle = c.detail + (f"\n→ {c.hint}" if c.hint else "")
            row.set_subtitle(subtitle)
            row.set_subtitle_selectable(True)
            icon_name, css = ICONS.get(c.status, ICONS[ERROR])
            icon = Gtk.Image(icon_name=icon_name)
            icon.add_css_class(css)
            row.add_prefix(icon)
            self.group.add(row)
            self._rows.append(row)
        self.setup_button.set_visible(any(c.action == "setup-logs" for c in checks))

    def _copy(self, *_args) -> None:
        display = Gdk.Display.get_default()
        if display is None:
            return
        display.get_clipboard().set(format_checks(self._checks))
        self.toasts.add_toast(Adw.Toast(title=_("Report copied"), timeout=2))

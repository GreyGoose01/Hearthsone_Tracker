"""History window: statistics and finished matches, nothing to expand."""

from __future__ import annotations

from datetime import datetime

from gi.repository import Adw, Gtk, Pango

from hearthwatch.db import MatchDB, StoredMatch
from hearthwatch.i18n import _
from hearthwatch.ui.widgets import board_flow, card, clear, pill, stat_tile, tribe_names

MAX_HERO_ROWS = 15
MAX_MATCHES = 50


def _date(text: str) -> str:
    try:
        return datetime.fromisoformat(text).strftime(_("%Y-%m-%d %H:%M"))
    except ValueError:
        return text


def _place_badge(place: int, duo: bool) -> Gtk.Label:
    badge = Gtk.Label(label=str(place or "–"), valign=Gtk.Align.START)
    badge.add_css_class("place-badge")
    if place:
        badge.add_css_class("top" if place <= (2 if duo else 4) else "bottom")
    return badge


class HistoryPage(Gtk.ScrolledWindow):
    def __init__(self, db: MatchDB) -> None:
        super().__init__(hscrollbar_policy=Gtk.PolicyType.NEVER)
        self.db = db
        clamp = Adw.Clamp(maximum_size=760, margin_top=12, margin_bottom=18,
                          margin_start=12, margin_end=12)
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        clamp.set_child(self.box)
        self.set_child(clamp)
        self.refresh()

    def refresh(self) -> None:
        clear(self.box)
        summary = self.db.summary()

        outer, body = card(_("Statistics"))
        tiles = Gtk.Box(spacing=6, homogeneous=True)
        values = (
            (_("Games"), str(summary.games)),
            (_("Avg. place"), f"{summary.avg_place:.2f}" if summary.games else "–"),
            ("Top 4", f"{summary.top4_rate:.0%}" if summary.games else "–"),
            (_("Wins"), str(summary.wins)),
            ("MMR", str(summary.last_mmr) if summary.last_mmr else "–"),
        )
        for caption, value in values:
            tile, label = stat_tile(caption)
            label.set_text(value)
            tiles.append(tile)
        body.append(tiles)
        self.box.append(outer)

        heroes = self.db.hero_stats()
        if heroes:
            outer, body = card(_("Heroes"))
            for h in heroes[:MAX_HERO_ROWS]:
                row = Gtk.Box(spacing=10)
                name = Gtk.Label(label=h.hero_name, xalign=0, hexpand=True,
                                 ellipsize=Pango.EllipsizeMode.END)
                name.add_css_class("heading")
                info = Gtk.Label(label=_("{games} games · Top 4: {top4} · Wins: {wins}").format(games=h.games, top4=h.top4, wins=h.wins))
                info.add_css_class("caption")
                info.add_css_class("dim-label")
                avg = Gtk.Label(label=_("Avg. {place:.2f}").format(place=h.avg_place), width_chars=7, xalign=1)
                avg.add_css_class("numeric")
                avg.add_css_class("heading")
                avg.add_css_class("place-top" if h.avg_place <= 4 else "place-bottom")
                for w in (name, info, avg):
                    row.append(w)
                body.append(row)
            self.box.append(outer)

        outer, body = card(_("Games"))
        matches = self.db.matches(MAX_MATCHES)
        if not matches:
            empty = Gtk.Label(
                label=_("No games saved yet. Finished Battlegrounds games show up here "
                        "automatically; older logs can be added with “hearthwatch --import-logs”."),
                xalign=0, wrap=True,
            )
            empty.add_css_class("dim-label")
            body.append(empty)
        for i, stored in enumerate(matches):
            if i:
                body.append(Gtk.Separator())
            body.append(self._match_row(stored))
        self.box.append(outer)

    def _match_row(self, stored: StoredMatch) -> Gtk.Widget:
        r = stored.result
        row = Gtk.Box(spacing=10)
        row.append(_place_badge(r.placement, r.is_duo))
        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True)
        title = Gtk.Label(label=r.hero_name, xalign=0, ellipsize=Pango.EllipsizeMode.END)
        title.add_css_class("heading")
        mode = " · Duo" if r.is_duo else ""
        sub = Gtk.Label(
            label=_("{date} · Round {round} · Tier {tier}").format(
                date=_date(r.ended_at), round=r.rounds, tier=r.tavern_tier) + f"{mode} · {tribe_names(r.tribes)}",
            xalign=0, wrap=True,
        )
        sub.add_css_class("caption")
        sub.add_css_class("dim-label")
        main.append(title)
        main.append(sub)
        main.append(board_flow(r.final_board, _("no final board saved")))
        row.append(main)

        side = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, valign=Gtk.Align.START)
        spin = Gtk.SpinButton.new_with_range(0, 30000, 1)
        spin.set_value(stored.mmr_after or 0)
        spin.set_tooltip_text(_("MMR after the game (0 = empty)"))
        spin.connect("value-changed", lambda b: self.db.set_mmr(stored.id, int(b.get_value()) or None))
        mmr = Gtk.Box(spacing=4)
        mmr.append(pill("MMR", "stat-caption"))
        mmr.append(spin)
        side.append(mmr)
        delete = Gtk.Button(icon_name="user-trash-symbolic", halign=Gtk.Align.END,
                            tooltip_text=_("Delete game from history"))
        delete.add_css_class("flat")
        delete.connect("clicked", lambda *_: (self.db.delete(stored.id), self.refresh()))
        side.append(delete)
        row.append(side)
        return row


class HistoryWindow(Adw.Window):
    def __init__(self, app: Adw.Application, parent: Gtk.Window, db: MatchDB) -> None:
        super().__init__(application=app, transient_for=parent, title=_("History"))
        self.set_default_size(720, 820)
        self.page = HistoryPage(db)
        view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        refresh = Gtk.Button(icon_name="view-refresh-symbolic", tooltip_text=_("Refresh"))
        refresh.connect("clicked", lambda *_: self.refresh())
        header.pack_start(refresh)
        view.add_top_bar(header)
        view.set_content(self.page)
        self.set_content(view)

    def refresh(self) -> None:
        self.page.refresh()

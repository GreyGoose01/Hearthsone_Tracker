"""Minion browser: the tavern pool of this lobby by tier and minion type."""

from __future__ import annotations

from gi.repository import Adw, Gtk, Pango

from hearthwatch.bg import pool
from hearthwatch.bg.models import LiveState
from hearthwatch.cards import CardDB, CardInfo, card_text
from hearthwatch.i18n import _
from hearthwatch.ui.widgets import card_art, clear, pill, tribe_names

CARD_WIDTH = 168


class MinionCard(Gtk.Box):
    """One tavern minion: art, stats, name and text."""

    def __init__(self, c: CardInfo) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        self.add_css_class("minion")
        self.add_css_class("pool-card")
        self.set_size_request(CARD_WIDTH, -1)
        top = Gtk.Box(spacing=8)
        art = card_art(c.id, 44, round_=True)
        if art is not None:
            top.append(art)
        head = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER, hexpand=True)
        name = Gtk.Label(label=c.name, xalign=0, ellipsize=Pango.EllipsizeMode.END, max_width_chars=14)
        name.add_css_class("heading")
        stats = Gtk.Box(spacing=2)
        atk = Gtk.Label(label=str(c.attack))
        atk.add_css_class("minion-atk")
        hp = Gtk.Label(label=str(c.health))
        hp.add_css_class("minion-hp")
        stats.append(atk)
        stats.append(Gtk.Label(label="/"))
        stats.append(hp)
        head.append(name)
        head.append(stats)
        top.append(head)
        self.append(top)
        text = card_text(c.text)
        if text:
            body = Gtk.Label(label=text, xalign=0, wrap=True, max_width_chars=22, lines=5,
                             ellipsize=Pango.EllipsizeMode.END, valign=Gtk.Align.START)
            body.add_css_class("pool-text")
            self.append(body)
        self.set_tooltip_text(f"{c.name}  {c.attack}/{c.health}\n{text}" if text else c.name)


class MinionsPage(Gtk.Box):
    """Tier buttons on top, the minions of the selected tier below."""

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self._cards = CardDB()
        self._state: LiveState | None = None
        self._tier = 1
        self._follow = True  # follow the current tavern tier until the user picks one
        self._shown: tuple | None = None

        bar = Gtk.Box(spacing=6, margin_top=10, margin_bottom=6, margin_start=12, margin_end=12)
        self.tier_buttons = Gtk.Box(css_classes=["linked"], halign=Gtk.Align.START)
        bar.append(self.tier_buttons)
        self.status = Gtk.Label(xalign=0, hexpand=True, wrap=True)
        self.status.add_css_class("caption")
        self.status.add_css_class("dim-label")
        bar.append(self.status)
        self.append(bar)

        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        clamp = Adw.Clamp(maximum_size=1100, child=self.box, margin_top=6, margin_bottom=16,
                          margin_start=12, margin_end=12)
        self.append(Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True, child=clamp))
        self.refresh()

    # -- inputs ---------------------------------------------------------------------------
    def set_cards(self, cards: CardDB) -> None:
        self._cards = cards
        self.refresh()

    def update_state(self, state: LiveState | None) -> None:
        if state is not None and self._state is not None and state.in_game and not self._state.in_game:
            self._follow = True  # a new game: start at its tavern tier again
        self._state = state
        self.refresh()

    # -- view ----------------------------------------------------------------------------
    def _lobby(self) -> tuple[list[str], list[str], bool, int]:
        s = self._state
        if s is None or not s.in_game:
            return [], [], False, 0
        return list(s.tribes_seen), list(s.tribes_banned), "DUO" in s.game_type, s.tavern_tier

    def refresh(self) -> None:
        seen, banned, duos, current = self._lobby()
        minions = pool.lobby_minions(self._cards, seen, banned, duos)
        tiers = pool.tiers(minions)
        if self._follow and current:
            self._tier = current
        if tiers and self._tier not in tiers:
            self._tier = min(tiers, key=lambda t: abs(t - self._tier))
        key = (id(self._cards), tuple(seen), tuple(banned), duos, current, self._tier)
        if key == self._shown:
            return
        self._shown = key
        self._build_tier_buttons(tiers, current)
        self._build_status(seen, banned)
        clear(self.box)
        if not minions:
            empty = Gtk.Label(label=_("No card data yet – it is downloaded at the first start."),
                              xalign=0, wrap=True)
            empty.add_css_class("dim-label")
            self.box.append(empty)
            return
        for group in pool.groups(minions, self._tier, seen, banned):
            self.box.append(self._group(group))

    def _build_tier_buttons(self, tiers: list[int], current: int) -> None:
        clear(self.tier_buttons)
        first = None
        for t in tiers:
            b = Gtk.ToggleButton(label=str(t), active=(t == self._tier))
            b.set_tooltip_text(_("Tavern tier {tier}").format(tier=t)
                               + (" · " + _("your tier") if t == current else ""))
            if t == current:
                b.add_css_class("accent")
            if first is None:
                first = b
            else:
                b.set_group(first)
            b.connect("toggled", self._on_tier, t)
            self.tier_buttons.append(b)

    def _on_tier(self, button: Gtk.ToggleButton, tier: int) -> None:
        if not button.get_active() or tier == self._tier:
            return
        self._tier = tier
        self._follow = tier == self._lobby()[3]
        self.refresh()

    def _build_status(self, seen: list[str], banned: list[str]) -> None:
        if self._state is None or not self._state.in_game:
            self.status.set_text(_("Not in a game: all minions are shown."))
        elif banned:
            self.status.set_text(_("Minion types in this lobby: {types}").format(types=tribe_names(seen)))
        else:
            self.status.set_text(_("Not all minion types are known yet – faded types may not be in this game."))

    def _group(self, group: pool.PoolGroup) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        title = group.title or _("Neutral")
        head = Gtk.Box(spacing=8)
        label = Gtk.Label(label=title, xalign=0)
        label.add_css_class("heading")
        head.append(label)
        head.append(pill(str(len(group.cards)), "tribe-chip"))
        if group.available is None:
            head.append(pill(_("not seen yet"), "tribe-chip", "banned"))
            box.set_opacity(0.55)
        box.append(head)
        flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, column_spacing=6, row_spacing=6,
                           min_children_per_line=1, max_children_per_line=6, homogeneous=True,
                           valign=Gtk.Align.START)
        for c in group.cards:
            flow.append(MinionCard(c))
        box.append(flow)
        return box


class MinionsWindow(Adw.Window):
    def __init__(self, app: Adw.Application, parent: Gtk.Window) -> None:
        super().__init__(application=app, transient_for=parent, title=_("Minions by tier"))
        self.set_default_size(820, 760)
        self.page = MinionsPage()
        view = Adw.ToolbarView()
        view.add_top_bar(Adw.HeaderBar())
        view.set_content(self.page)
        self.set_content(view)

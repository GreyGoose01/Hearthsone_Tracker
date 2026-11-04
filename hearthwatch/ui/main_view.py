"""Single-page live view, arranged by game phase.

* Header: hero, phase, round/tier/place/health, result dots, tribes.
* Focus: during recruit the **next opponent** (last seen board, health,
  tier, main tribe, your record); during combat the **current fight**
  (opponent board, odds, then the real outcome). The previous combat is a
  single line during recruit.
* "Your buffs": game-wide buffs/counters and your live board.
* Lobby: one compact row per player with health bar and mini board.

Narrow windows stack everything; wide windows put the lobby in a second
column (breakpoint in ``MainWindow``).
"""

from __future__ import annotations

from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, Gtk, Pango  # noqa: E402

from hearthwatch.bg.models import CombatSnapshot, LiveState, OpponentInfo
from hearthwatch.bg.tracker import TRIBES_PER_LOBBY
from hearthwatch.cards import tribe_name
from hearthwatch.i18n import N_, _
from hearthwatch.settings import Settings
from hearthwatch.sim.montecarlo import SimResult
from hearthwatch.ui.widgets import (
    HealthBar,
    OddsBar,
    board_flow,
    card,
    card_art,
    chip_box,
    clear,
    pill,
    result_dot,
    scale_for_width,
    scaled,
    set_board_art,
    set_ui_scale,
    stat_tile,
    ui_scale,
)

MASCOT = Path(__file__).resolve().parent.parent / "assets" / "dwarf-thumbs-up.png"
WAITING_TEXT = N_("Start Hearthstone with hearthstone-linux-gui and join a Battlegrounds game.")
PHASES = {"recruit": (N_("Recruit"), "phase-recruit"), "combat": (N_("Combat"), "phase-combat")}
RESULT_TEXT = {"win": N_("Win"), "draw": N_("Draw"), "loss": N_("Loss")}
XWIDE = 1500  # from this window width on, lobby boards sit beside the players
XWIDE_LEFT = 680  # width of the left column then (grows with the scale)
LOBBY_INFO_WIDTH = 280  # player info beside a lobby board


def _mascot() -> Gdk.Texture | None:
    """The thumbs-up dwarf for the waiting page (None if the file is missing)."""
    try:
        return Gdk.Texture.new_from_filename(str(MASCOT))
    except GLib.Error:
        return None


def tribe_label(tribe: str) -> str:
    return tribe_name(tribe)


def result_text(result: str) -> str:
    return _(RESULT_TEXT[result])


def triples_text(o: OpponentInfo) -> str:
    if not o.triples:
        return ""
    return (_("{n} triple") if o.triples == 1 else _("{n} triples")).format(n=o.triples)


def trinkets_text(o: OpponentInfo) -> str:
    return _("Trinkets: {names}").format(names=", ".join(o.trinkets)) if o.trinkets else ""


def record_text(o: OpponentInfo) -> str:
    """Your record against a player, e.g. "2 W · 1 L" (W/D/L = win/draw/loss)."""
    if not (o.wins or o.draws or o.losses):
        return ""
    parts = [_("{n} W").format(n=o.wins), _("{n} L").format(n=o.losses)]
    if o.draws:
        parts.insert(1, _("{n} D").format(n=o.draws))
    return " · ".join(parts)


class MainView(Gtk.Stack):
    def __init__(self) -> None:
        super().__init__(transition_type=Gtk.StackTransitionType.CROSSFADE)
        self.add_css_class("hearthwatch-root")
        set_board_art(False)  # narrow until the window's breakpoint says otherwise
        self.settings = Settings()
        self.waiting = Adw.StatusPage(
            title=_("Waiting for a Battlegrounds game"),
            description=_(WAITING_TEXT),
        )
        mascot = _mascot()
        if mascot is not None:
            self.waiting.set_paintable(mascot)
            self.waiting.add_css_class("mascot")
        else:
            self.waiting.set_icon_name("applications-games-symbolic")
        self.add_named(self.waiting, "waiting")

        self.columns = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.left = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14, hexpand=True)
        self.right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14, hexpand=True)
        # the left column is limited in very wide windows: the lobby gets the rest
        self.left_clamp = Adw.Clamp(maximum_size=100000, tightening_threshold=100000, child=self.left,
                                    hexpand=True)
        self.columns.append(self.left_clamp)
        self.columns.append(self.right)
        # wide enough to use big screens; the content itself grows with the window
        clamp = Adw.Clamp(maximum_size=2600, tightening_threshold=2200, child=self.columns,
                          margin_top=10, margin_bottom=14, margin_start=10, margin_end=10)
        # a horizontal scrollbar only as a last resort: never cut the content off
        self.add_named(Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.AUTOMATIC, child=clamp), "game")

        self._build_header()
        self.lethal = Gtk.Label(xalign=0, wrap=True, visible=False)
        self.lethal.add_css_class("lethal")
        self.left.append(self.lethal)
        self._build_focus()
        self._build_buffs()
        self._build_lobby()

        self.summary_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        summary_clamp = Adw.Clamp(maximum_size=1500, tightening_threshold=1100, child=self.summary_box,
                                  margin_top=12, margin_bottom=18, margin_start=12, margin_end=12)
        self.add_named(Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
                                          child=summary_clamp), "summary")

        self._state: LiveState | None = None
        self._combat: CombatSnapshot | None = None
        self._predictions: dict[int, tuple[float, float, float]] = {}
        self._signatures: dict[str, object] = {}
        self._summary_shown = False
        self._in_game = False
        self._notice = ""
        self._wide = False
        self._xwide = False  # very wide: lobby boards beside the players, not below
        self._scale = 1.0
        self._target: float | None = None  # scale wanted for the window width
        self._width = 0
        self._fit_pending = False
        self.show_waiting()

    # -- settings / layout ------------------------------------------------------
    def set_wide(self, wide: bool) -> None:
        self._wide = wide
        self._target = None  # pick the scale for the new layout
        self._set_xwide(False)
        GLib.idle_add(lambda: (self._rebuild(), False)[1])  # boards with the new card size
        self.columns.set_orientation(Gtk.Orientation.HORIZONTAL if wide else Gtk.Orientation.VERTICAL)

    def _set_xwide(self, xwide: bool) -> None:
        self._xwide = xwide
        set_board_art(self._wide, xwide)
        self.columns.set_homogeneous(self._wide and not xwide)
        # very wide: the left column keeps a comfortable width, the lobby takes the rest
        limit = int(XWIDE_LEFT * ui_scale()) if xwide else 100000
        self.left_clamp.set_maximum_size(limit)
        self.left_clamp.set_tightening_threshold(limit)
        self.left_clamp.set_hexpand(not xwide)

    def do_size_allocate(self, width: int, height: int, baseline: int) -> None:
        Gtk.Stack.do_size_allocate(self, width, height, baseline)
        self._width = width
        target = scale_for_width(width, self._wide) if self.settings.scale_with_window else 1.0
        xwide = self._wide and width >= XWIDE
        if xwide != self._xwide:
            self._xwide = xwide
            self._target = None
        if target != self._target or (self._scale > 1.0 and not self._fits()):
            self._target = target
            self._schedule_scale()

    def _schedule_scale(self) -> None:
        if not self._fit_pending:
            self._fit_pending = True
            GLib.idle_add(self._apply_scale)  # never change widgets while they are laid out

    def _fits(self) -> bool:
        """Does the page fit the window at the current scale?"""
        page = self.get_visible_child_name()
        if page == "game":
            need = self.columns.measure(Gtk.Orientation.HORIZONTAL, -1)[0] + 20
        elif page == "summary":
            need = self.summary_box.measure(Gtk.Orientation.HORIZONTAL, -1)[0] + 24
        else:
            return True
        return need <= self._width

    def _apply_scale(self) -> bool:
        """Grow to the scale the window width asks for, but only as far as everything still fits
        (fonts and themes differ: measure instead of guessing)."""
        self._fit_pending = False
        scale = self._target or 1.0
        first = True
        while True:
            if scale != self._scale or first:
                first = False
                self._scale = scale
                set_ui_scale(scale)
                self._set_xwide(self._xwide)
                self._rebuild()
            if scale <= 1.0 or self._fits():
                break
            scale = round(scale - 0.1, 1)
        return False

    def _rebuild(self) -> None:
        """Build everything again (new card sizes, settings or layout)."""
        self._signatures.clear()
        if self._state is not None and self._in_game:
            self.update_state(self._state)
            if self._combat is not None and self.focus.get_visible_child_name() == "combat":
                combat, actual = self._combat, self._combat.actual
                self.update_combat(combat)
                if combat.round in self._predictions and getattr(self, "_last_sim", None):
                    self.update_sim(*self._last_sim)
                if actual is not None:
                    self.update_result(combat)
        elif self._summary_shown and self._state is not None:
            self.show_summary(self._state)

    @property
    def in_game(self) -> bool:
        """A Battlegrounds game is being followed right now."""
        return self._in_game

    def keep_predictions(self, other: "MainView") -> None:
        """Take over the simulated odds of a previous view (window rebuilt)."""
        self._predictions.update(other._predictions)

    def apply_settings(self, settings: Settings) -> None:
        self.settings = settings
        if not settings.scale_with_window and self._scale != 1.0:
            self._scale = 1.0
            set_ui_scale(1.0)
        self._target = None
        self.queue_allocate()
        self._rebuild()  # everything with the new options

    # -- header -------------------------------------------------------------------
    def _build_header(self) -> None:
        outer, body = card()
        top = Gtk.Box(spacing=10)
        self.hero_art = Gtk.Box()
        top.append(self.hero_art)
        self.hero_label = Gtk.Label(xalign=0, hexpand=True, ellipsize=Pango.EllipsizeMode.END)
        self.hero_label.add_css_class("hero-name")
        top.append(self.hero_label)
        self.phase_pill = pill("", "phase-pill")
        self.phase_pill.set_valign(Gtk.Align.CENTER)
        top.append(self.phase_pill)
        body.append(top)

        tiles = Gtk.Box(spacing=6, homogeneous=True)
        t_round, self.round_value = stat_tile(_("Round"))
        t_tier, self.tier_value = stat_tile(_("Tier"))
        t_tier.set_tooltip_text(_("Tavern tier"))
        t_place, self.place_value = stat_tile(_("Place"))
        t_health, self.health_value = stat_tile(_("Health"))
        self.health_bar = HealthBar(4)
        self.health_bar.set_margin_start(8)
        self.health_bar.set_margin_end(8)
        t_health.append(self.health_bar)
        for t in (t_round, t_tier, t_place, t_health):
            tiles.append(t)
        body.append(tiles)

        self.dots = chip_box()
        body.append(self.dots)
        # minion types: two full-width rows of equal cells (in the lobby / banned)
        self.tribes = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        body.append(self.tribes)
        self.left.append(outer)

    # -- focus: next opponent (recruit) / current combat ------------------------------
    def _build_focus(self) -> None:
        self.focus_outer, body = card()
        self.focus = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE, vhomogeneous=False)
        body.append(self.focus)
        # recruit: next opponent
        self.next_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.focus.add_named(self.next_box, "next")
        # combat
        combat = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.combat_title = Gtk.Label(xalign=0)
        self.combat_title.add_css_class("focus-title")
        self.combat_sub = Gtk.Label(xalign=0, wrap=True)
        self.combat_sub.add_css_class("meta")
        combat.append(self.combat_title)
        combat.append(self.combat_sub)
        odds = Gtk.Box(spacing=6, homogeneous=True)
        self.odds_values = {}
        for key, caption, css in (("win", _("Win"), "sim-win"), ("draw", _("Draw"), "sim-draw"),
                                  ("loss", _("Loss"), "sim-loss")):
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            value = Gtk.Label(label="…")
            value.add_css_class("odds-value")
            value.add_css_class(css)
            cap = Gtk.Label(label=caption)
            cap.add_css_class("stat-caption")
            box.append(value)
            box.append(cap)
            odds.append(box)
            self.odds_values[key] = value
        combat.append(odds)
        self.odds_bar = OddsBar()
        combat.append(self.odds_bar)
        self.odds_note = Gtk.Label(xalign=0, wrap=True)
        self.odds_note.add_css_class("caption")
        self.odds_note.add_css_class("dim-label")
        combat.append(self.odds_note)
        self.result_pill = pill("", "result-pill")
        self.result_pill.set_halign(Gtk.Align.START)
        self.result_pill.set_visible(False)
        combat.append(self.result_pill)
        self.combat_board = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        combat.append(self.combat_board)
        self.focus.add_named(combat, "combat")
        self.last_line = Gtk.Label(xalign=0, wrap=True, visible=False)
        self.last_line.add_css_class("last-line")
        body.append(self.last_line)
        self.left.append(self.focus_outer)

    # -- your buffs ------------------------------------------------------------------
    def _build_buffs(self) -> None:
        self.buffs_outer, body = card(_("Your buffs"))
        self.buff_chips = chip_box()
        body.append(self.buff_chips)
        self.my_board = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        body.append(self.my_board)
        self.left.append(self.buffs_outer)

    # -- lobby ---------------------------------------------------------------------------
    def _build_lobby(self) -> None:
        outer, body = card("Lobby")
        self.lobby = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        body.append(self.lobby)
        self.right.append(outer)

    # -- helpers ---------------------------------------------------------------------------
    def _changed(self, key: str, signature) -> bool:
        if key in self._signatures and self._signatures[key] == signature:
            return False
        self._signatures[key] = signature
        return True

    @staticmethod
    def _board_sig(minions) -> tuple:
        return tuple((m.card_id, m.attack, m.health, m.golden, tuple(m.buffs)) for m in minions)

    # -- public updates ------------------------------------------------------------------
    def show_waiting(self, text: str | None = None) -> None:
        """Waiting page; ``text`` (e.g. why the last game was incomplete) stays
        until the next game begins."""
        if text:
            self._notice = text
        self.waiting.set_description(self._notice or _(WAITING_TEXT))
        self.set_visible_child_name("waiting")
        self._summary_shown = False
        self._reset_combat()

    def _reset_combat(self) -> None:
        self._combat = None
        self.lethal.set_visible(False)
        clear(self.combat_board)

    def update_state(self, s: LiveState) -> None:
        self._state = s
        if not (s.in_game and s.is_battlegrounds):
            self._in_game = False
            if s.summary is not None and s.is_battlegrounds:
                self.show_summary(s)
            elif s.notice:
                self.show_waiting(s.notice)
            elif not self._summary_shown:  # keep the summary until the next game
                self.show_waiting()
            return
        if not self._in_game:  # a new game begins
            self._in_game = True
            self._summary_shown = False
            self._notice = ""
            self._predictions.clear()
            self._signatures.clear()
            self._reset_combat()
        self.set_visible_child_name("game")
        self._update_header(s)
        self._update_focus(s)
        self._update_buffs(s)
        self._update_lobby(s)

    def _update_header(self, s: LiveState) -> None:
        duo = "DUO" in s.game_type
        if self._changed("hero", (s.hero_card_id, self.settings.show_art)):
            clear(self.hero_art)
            art = card_art(s.hero_card_id, 44, round_=True)
            if art is not None:
                self.hero_art.append(art)
        self.hero_label.set_text(_("Choosing a hero…") if s.choosing_hero else s.hero_name or "–")
        text, css = PHASES.get(s.phase, ("", ""))
        text = _(text) if text else ""
        for c in ("phase-recruit", "phase-combat"):
            self.phase_pill.remove_css_class(c)
        if css:
            self.phase_pill.add_css_class(css)
        self.phase_pill.set_text(text)
        self.phase_pill.set_visible(bool(text))
        self.round_value.set_text(str(s.round or "–"))
        self.tier_value.set_text(str(s.tavern_tier or "–"))
        self.place_value.set_text(str(s.place or "–"))
        for c in ("place-top", "place-bottom"):
            self.place_value.remove_css_class(c)
        if s.place:
            self.place_value.add_css_class("place-top" if s.place <= (2 if duo else 4) else "place-bottom")
        self.health_value.set_text(f"{s.health}+{s.armor}" if s.armor else str(s.health or "–"))
        self.health_bar.set_fraction(s.health / max(s.max_health or 30, 1))

        results = tuple((c.round, c.actual.result if c.actual else "", c.actual.damage if c.actual else None,
                         c.opponent.hero_name) for c in s.combat_log)
        if self._changed("dots", (results, self.settings.show_history)):
            clear(self.dots)
            for rnd, result, damage, name in results:
                if not result:
                    continue
                tip = _("Round {round} against {hero}: {result}").format(
                    round=rnd, hero=name, result=result_text(result))
                if damage:
                    tip += ", " + _("{damage} damage").format(damage=damage)
                self.dots.append(result_dot(result, str(rnd), tip))
        self.dots.set_visible(self.settings.show_history and any(r[1] for r in results))

        if self._changed("tribes", (tuple(s.tribes_seen), tuple(s.tribes_banned), s.anomaly,
                                    self.settings.show_tribes)):
            clear(self.tribes)
            if s.anomaly:
                chip = pill("✦ " + _("Anomaly: {name}").format(name=s.anomaly), "tribe-chip", "anomaly")
                chip.set_tooltip_text(s.anomaly_text or s.anomaly)
                chip.set_ellipsize(Pango.EllipsizeMode.END)
                self.tribes.append(chip)
            if self.settings.show_tribes and (s.tribes_seen or s.tribes_banned):
                self.tribes.append(self._tribe_cells([tribe_label(t) for t in s.tribes_seen]))
                if s.tribes_banned:
                    out = Gtk.Label(label=_("Not in this lobby: {types}").format(
                        types=" · ".join(tribe_label(t) for t in s.tribes_banned)), wrap=True,
                        justify=Gtk.Justification.CENTER)
                    out.add_css_class("caption")
                    out.add_css_class("dim-label")
                    self.tribes.append(out)
        self.tribes.set_visible(bool(s.anomaly) or (self.settings.show_tribes and bool(s.tribes_seen or s.tribes_banned)))

    @staticmethod
    def _tribe_cells(names: list[str]) -> Gtk.Widget:
        """The lobby's minion types as equally wide cells (5 in a row, or 3 + 2 when
        narrow); types not seen yet as "?"."""
        flow = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
                           min_children_per_line=3, max_children_per_line=TRIBES_PER_LOBBY,
                           column_spacing=4, row_spacing=4)
        for i in range(max(TRIBES_PER_LOBBY, len(names))):
            known = i < len(names)
            chip = pill(names[i] if known else "?", "tribe-chip", *([] if known else ["banned"]))
            chip.set_tooltip_text(_("In this lobby") if known else _("not seen yet"))
            flow.append(chip)
        return flow

    def _update_focus(self, s: LiveState) -> None:
        if s.choosing_hero:
            self.lethal.set_visible(False)
            self.last_line.set_visible(False)
            self.focus.set_visible_child_name("next")
            if self._changed("next", ("choose", tuple(s.hero_options), self.settings.show_art)):
                self._build_hero_choice(s.hero_options)
            return
        last = s.last_combat
        if s.phase == "combat" and last is not None and last.round == s.round:
            if self._combat is None or self._combat.round != last.round:
                self.update_combat(last)
            elif last.actual is not None:
                self.update_result(last)
            self.focus.set_visible_child_name("combat")
            self.last_line.set_visible(False)
            return
        if s.phase == "combat":
            # combat phase, first attack not yet seen: still show who it is against
            self.focus.set_visible_child_name("next")
        else:
            self.lethal.set_visible(False)
            self.focus.set_visible_child_name("next")
        nxt = next((o for o in s.opponents if o.is_next_opponent), None)
        sig = (nxt.lobby_player_id, nxt.hero_name, nxt.health, nxt.armor, nxt.tavern_tier,
               nxt.tier_up_round, nxt.main_tribe, record_text(nxt), nxt.triples, tuple(nxt.trinkets),
               self._board_sig(nxt.last_board.minions) if nxt.last_board else None,
               self.settings.show_art) if nxt else None
        if self._changed("next", sig):
            self._build_next(nxt)
        # previous combat as one line
        if last is not None and last.actual is not None:
            line = _("Last combat (round {round}) against {hero}: {result}").format(
                round=last.round, hero=last.opponent.hero_name, result=last.actual.text())
            if last.round in self._predictions:
                likely = self._most_likely(last.round)
                chance = dict(zip(("win", "draw", "loss"), self._predictions[last.round]))[likely]
                line += " · " + _("predicted {chance:.0%} {result}").format(
                    chance=chance, result=result_text(likely))
                line += " ✓" if likely == last.actual.result else " ✗"
            self.last_line.set_text(line)
            self.last_line.set_visible(True)
        else:
            self.last_line.set_visible(False)

    def _build_hero_choice(self, options: list[tuple[str, str]]) -> None:
        clear(self.next_box)
        title = Gtk.Label(label=_("Your heroes to choose from"), xalign=0)
        title.add_css_class("stat-caption")
        self.next_box.append(title)
        if not options:
            label = Gtk.Label(label=_("not known yet"), xalign=0)
            label.add_css_class("dim-label")
            self.next_box.append(label)
            return
        row = Gtk.Box(spacing=6, homogeneous=True)
        for card_id, name in options:
            cell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            cell.add_css_class("hero-option")
            art = card_art(card_id, 64, round_=True)
            if art is not None:
                art.set_halign(Gtk.Align.CENTER)
                cell.append(art)
            label = Gtk.Label(label=name, wrap=True, justify=Gtk.Justification.CENTER,
                              max_width_chars=14, lines=2, ellipsize=Pango.EllipsizeMode.END)
            label.add_css_class("heading")
            cell.append(label)
            row.append(cell)
        self.next_box.append(row)

    def _build_next(self, o: OpponentInfo | None) -> None:
        clear(self.next_box)
        title = Gtk.Label(label=_("Next opponent"), xalign=0)
        title.add_css_class("stat-caption")
        self.next_box.append(title)
        if o is None:
            label = Gtk.Label(label=_("not known yet"), xalign=0)
            label.add_css_class("dim-label")
            self.next_box.append(label)
            return
        row = Gtk.Box(spacing=10)
        art = card_art(o.hero_card_id, 52, round_=True)
        if art is not None:
            row.append(art)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3, hexpand=True,
                       valign=Gtk.Align.CENTER)
        name = Gtk.Label(label=o.hero_name, xalign=0, ellipsize=Pango.EllipsizeMode.END)
        name.add_css_class("focus-title")
        text.append(name)
        bar = HealthBar(6)
        bar.set_fraction(o.health_fraction)
        text.append(bar)
        meta = [f"♥ {o.health}" + (f"+{o.armor}" if o.armor else "")]
        if o.tavern_tier:
            tier = _("Tier {tier}").format(tier=o.tavern_tier)
            if o.tier_up_round:
                tier += " " + _("(↑ round {round})").format(round=o.tier_up_round)
            meta.append(tier)
        if o.main_tribe:
            meta.append(tribe_label(o.main_tribe))
        if triples_text(o):
            meta.append(triples_text(o) + (" " + _("(last in round {round})").format(round=o.triple_round)
                                            if o.triple_round else ""))
        if record_text(o):
            meta.append(_("Record {record}").format(record=record_text(o)))
        meta_label = Gtk.Label(label=" · ".join(meta), xalign=0, wrap=True)
        meta_label.add_css_class("meta")
        text.append(meta_label)
        if o.trinkets:
            trinkets = Gtk.Label(label=trinkets_text(o), xalign=0, wrap=True)
            trinkets.add_css_class("meta")
            text.append(trinkets)
        row.append(text)
        self.next_box.append(row)
        if o.last_board is not None:
            cap = Gtk.Label(label=_("Board from round {round}").format(round=o.last_board.round), xalign=0)
            cap.add_css_class("stat-caption")
            self.next_box.append(cap)
            self.next_box.append(board_flow(o.last_board.minions))
        else:
            hint = Gtk.Label(label=_("Board not seen yet"), xalign=0)
            hint.add_css_class("dim-label")
            self.next_box.append(hint)

    def update_combat(self, c: CombatSnapshot) -> None:
        self._combat = c
        self.combat_title.set_text(_("Combat · round {round}").format(round=c.round))
        self.combat_sub.set_text(_("against {hero} · tier {tier}").format(
            hero=c.opponent.hero_name, tier=c.opponent.tavern_tier))
        for v in self.odds_values.values():
            v.set_text("…")
        self.odds_bar.set_values(0, 0, 0)
        self.odds_note.set_text(_("Simulating …"))
        self.result_pill.set_visible(False)
        self.lethal.set_visible(False)
        clear(self.combat_board)
        self.combat_board.append(board_flow(c.opponent.minions))
        self.focus.set_visible_child_name("combat")
        self.last_line.set_visible(False)
        if c.actual is not None:
            self.update_result(c)

    def update_result(self, c: CombatSnapshot) -> None:
        if self._combat is None or c.round != self._combat.round or c.actual is None:
            return
        self._combat.actual = c.actual
        for css in ("sim-win", "sim-draw", "sim-loss"):
            self.result_pill.remove_css_class(css)
        self.result_pill.add_css_class(f"sim-{c.actual.result}")
        self.result_pill.set_text(_("Actual: {result}").format(result=c.actual.text()))
        self.result_pill.set_visible(True)

    def update_sim(self, c: CombatSnapshot, r: SimResult) -> None:
        self._predictions[c.round] = (r.win, r.draw, r.loss)
        self._last_sim = (c, r)
        if self._combat is None or c.round != self._combat.round:
            return
        self.odds_values["win"].set_text(f"{r.win:.0%}")
        self.odds_values["draw"].set_text(f"{r.draw:.0%}")
        self.odds_values["loss"].set_text(f"{r.loss:.0%}")
        self.odds_bar.set_values(r.win, r.draw, r.loss)
        notes = []
        if r.win:
            notes.append(_("avg. {damage:.1f} damage dealt").format(damage=r.avg_damage_dealt))
        if r.loss:
            notes.append(_("avg. {damage:.1f} damage taken").format(damage=r.avg_damage_taken))
        if r.unsupported:
            notes.append(_("rough – not modelled: {cards}").format(cards=", ".join(r.unsupported)))
        self.odds_note.set_text(" · ".join(notes) or _("{runs} simulations").format(runs=r.runs))
        self.odds_note.set_tooltip_text(
            _("Simulated with AutoTavern ({runs} combats)").format(runs=r.runs) if r.engine == "autotavern"
            else _("Built-in simulator – it knows only some card effects"))
        if r.lethal_risk > 0 and c.actual is None:
            self.lethal.set_text(_("Careful: this combat is lethal in {risk:.0%} of the simulations!").format(
                risk=r.lethal_risk))
            self.lethal.set_visible(True)

    # -- your buffs ------------------------------------------------------------------------
    def _update_buffs(self, s: LiveState) -> None:
        show = self.settings.show_buffs and not s.choosing_hero
        self.buffs_outer.set_visible(show)
        if not show:
            return
        if self._changed("buff_chips", (tuple(s.player_buffs), tuple(s.counters))):
            clear(self.buff_chips)
            for text in s.counters:
                self.buff_chips.append(pill(text, "chip", "counter"))
            texts = s.player_buff_texts if len(s.player_buff_texts) == len(s.player_buffs) else []
            for i, text in enumerate(s.player_buffs):
                chip = pill(text, "chip")
                if texts and texts[i]:
                    chip.set_tooltip_text(texts[i])
                self.buff_chips.append(chip)
            if not (s.counters or s.player_buffs):
                self.buff_chips.append(pill(_("no game-wide buffs yet"), "tribe-chip", "banned"))
        # your board as of the recruit phase (kept during combat)
        if s.phase != "combat" and self._changed("my_board", (self._board_sig(s.my_board), self.settings.show_art)):
            clear(self.my_board)
            cap = Gtk.Label(label=_("Your board"), xalign=0)
            cap.add_css_class("stat-caption")
            self.my_board.append(cap)
            self.my_board.append(board_flow(s.my_board, _("no minions yet"), compact=True))

    # -- lobby -------------------------------------------------------------------------------
    def _update_lobby(self, s: LiveState) -> None:
        duo = "DUO" in s.game_type
        sig = tuple(
            (o.lobby_player_id, o.hero_name, o.place, o.health, o.armor, o.max_health, o.tavern_tier,
             o.tier_up_round, o.main_tribe, record_text(o), o.is_me, o.is_next_opponent,
             o.triples, tuple(o.trinkets),
             (o.last_board.round, self._board_sig(o.last_board.minions)) if o.last_board else None)
            for o in s.opponents
        ) + ((self.settings.show_art, self.settings.show_lobby_boards, self._xwide),)
        if not self._changed("lobby", sig):
            return
        clear(self.lobby)
        if not s.opponents:
            label = Gtk.Label(label=_("No players known yet"), xalign=0)
            label.add_css_class("dim-label")
            self.lobby.append(label)
            return
        alive = [o for o in s.opponents if not o.dead]
        dead = [o for o in s.opponents if o.dead]
        for o in alive + dead:
            self.lobby.append(self._lobby_row(o, duo))

    def _lobby_row(self, o: OpponentInfo, duo: bool) -> Gtk.Widget:
        row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        row.add_css_class("lobby-row")
        if o.is_me:
            row.add_css_class("me")
        elif o.is_next_opponent:
            row.add_css_class("next")
        if o.dead:
            row.add_css_class("dead")
        top = Gtk.Box(spacing=8)
        badge = Gtk.Label(label=str(o.place or "–"), valign=Gtk.Align.CENTER)
        badge.add_css_class("place-badge")
        if o.place:
            badge.add_css_class("top" if o.place <= (2 if duo else 4) else "bottom")
        top.append(badge)
        art = card_art(o.hero_card_id, 32, round_=True)
        if art is not None:
            top.append(art)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True,
                       valign=Gtk.Align.CENTER)
        head = Gtk.Box(spacing=6)
        name = Gtk.Label(label=o.hero_name, xalign=0, hexpand=True, ellipsize=Pango.EllipsizeMode.END)
        name.add_css_class("heading")
        head.append(name)
        if o.is_me:
            head.append(pill(_("You"), "tag-pill"))
        elif o.is_next_opponent:
            head.append(pill(_("Next"), "tag-pill"))
        text.append(head)
        if not o.dead:
            bar = HealthBar(4)
            bar.set_fraction(o.health_fraction)
            text.append(bar)
        meta = [_("out")] if o.dead else [f"♥ {o.health}" + (f"+{o.armor}" if o.armor else "")]
        if o.tavern_tier and not o.dead:
            tier = _("Tier {tier}").format(tier=o.tavern_tier)
            if o.tier_up_round:
                tier += " " + _("↑R{round}").format(round=o.tier_up_round)
            meta.append(tier)
        if o.main_tribe and not o.dead:
            meta.append(tribe_label(o.main_tribe))
        if triples_text(o) and not o.dead:
            meta.append(triples_text(o))
        if record_text(o):
            meta.append(record_text(o))
        if not o.is_me and not o.dead and o.last_board is None:
            meta.append(_("not seen yet"))
        sub = Gtk.Label(label=" · ".join(meta), xalign=0, ellipsize=Pango.EllipsizeMode.END)
        sub.add_css_class("meta")
        text.append(sub)
        if o.trinkets and not o.dead:
            trinkets = Gtk.Label(label=trinkets_text(o), xalign=0, ellipsize=Pango.EllipsizeMode.END)
            trinkets.add_css_class("meta")
            trinkets.set_tooltip_text(", ".join(o.trinkets))
            text.append(trinkets)
        top.append(text)
        row.append(top)
        if (self.settings.show_lobby_boards and o.last_board is not None
                and not o.is_me and not o.dead):
            # very wide: names only on hover, so all eight players fit on one screen
            board = board_flow(o.last_board.minions, compact=True, names=not self._xwide)
            board.set_tooltip_text(_("Board from round {round}").format(round=o.last_board.round))
            if self._xwide:  # beside the player: eight players fit on one screen
                text.set_hexpand(False)
                text.set_size_request(scaled(LOBBY_INFO_WIDTH), -1)
                board.set_hexpand(True)
                board.set_valign(Gtk.Align.CENTER)
                top.append(board)
            else:
                board.set_margin_start(36)
                row.append(board)
        elif self._xwide:
            text.set_hexpand(True)
        return row

    # -- end of game ---------------------------------------------------------------
    def show_summary(self, s: LiveState) -> None:
        """Game over: placement, final board and every combat with prediction vs. outcome."""
        r = s.summary
        if r is None:
            return
        self._summary_shown = True
        self._reset_combat()
        clear(self.summary_box)
        duo = r.is_duo
        players = 4 if duo else 8

        outer, body = card()
        top = Gtk.Box(spacing=14)
        badge = Gtk.Label(label=str(r.placement or "–"), valign=Gtk.Align.CENTER)
        badge.add_css_class("summary-place")
        if r.placement:
            badge.add_css_class("top" if r.placement <= (2 if duo else 4) else "bottom")
        top.append(badge)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER, hexpand=True)
        title = Gtk.Label(label=_("Place {place} of {players}").format(place=r.placement, players=players)
                          if r.placement else _("Game over"), xalign=0)
        title.add_css_class("hero-name")
        hero = Gtk.Label(label=r.hero_name or "–", xalign=0, ellipsize=Pango.EllipsizeMode.END)
        hero.add_css_class("heading")
        sub = Gtk.Label(label=_("Round {round} · Tier {tier}").format(round=r.rounds, tier=r.tavern_tier)
                        + (" · Duo" if duo else ""), xalign=0)
        sub.add_css_class("dim-label")
        for w in (title, hero, sub):
            text.append(w)
        top.append(text)
        body.append(top)

        combats = [c for c in s.combat_log if c.actual is not None]
        counts = {k: sum(c.actual.result == k for c in combats) for k in ("win", "draw", "loss")}
        hits = [
            self._most_likely(c.round) == c.actual.result
            for c in combats if c.round in self._predictions
        ]
        tiles = Gtk.Box(spacing=6, homogeneous=True)
        for caption, value, css in (
            (_("Wins"), counts["win"], "sim-win"), (_("Draws"), counts["draw"], "sim-draw"),
            (_("Losses"), counts["loss"], "sim-loss"),
            (_("Predicted"), f"{sum(hits)}/{len(hits)}" if hits else "–", None),
        ):
            tile, label = stat_tile(caption)
            label.set_text(str(value))
            if css:
                label.add_css_class(css)
            tiles.append(tile)
        body.append(tiles)
        tribes = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, column_spacing=4,
                             row_spacing=4, max_children_per_line=10)
        for t in r.tribes:
            tribes.append(pill(tribe_name(t), "tribe-chip"))
        body.append(tribes)
        self.summary_box.append(outer)

        outer, body = card(_("Final board"))
        body.append(board_flow(r.final_board, _("no board saved")))
        self.summary_box.append(outer)

        outer, body = card(_("Combats"))
        if not s.combat_log:
            empty = Gtk.Label(label=_("No combats recorded"), xalign=0)
            empty.add_css_class("dim-label")
            body.append(empty)
        for c in s.combat_log:
            body.append(self._combat_row(c))
        self.summary_box.append(outer)

        hint = Gtk.Label(label=_("The next game starts a new view automatically. "
                                 "All games are in the history (button at the top left)."),
                         wrap=True, xalign=0)
        hint.add_css_class("dim-label")
        hint.add_css_class("caption")
        self.summary_box.append(hint)
        self.set_visible_child_name("summary")

    def _most_likely(self, round_: int) -> str:
        win, draw, loss = self._predictions[round_]
        return max((("win", win), ("draw", draw), ("loss", loss)), key=lambda x: x[1])[0]

    def _combat_row(self, c: CombatSnapshot) -> Gtk.Widget:
        row = Gtk.Box(spacing=10)
        rnd = Gtk.Label(label=f"R{c.round}", width_chars=3, xalign=0)
        rnd.add_css_class("heading")
        rnd.add_css_class("numeric")
        row.append(rnd)
        text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
        name = Gtk.Label(label=c.opponent.hero_name, xalign=0, ellipsize=Pango.EllipsizeMode.END)
        text.append(name)
        if c.round in self._predictions:
            likely = self._most_likely(c.round)
            chance = dict(zip(("win", "draw", "loss"), self._predictions[c.round]))[likely]
            hit = c.actual is not None and c.actual.result == likely
            pred = Gtk.Label(label=_("Predicted: {chance:.0%} {result}").format(
                chance=chance, result=result_text(likely)) + (" ✓" if hit else ""), xalign=0, wrap=True)
            win, draw, loss = self._predictions[c.round]
            pred.set_tooltip_text(_("Win {win:.0%} · Draw {draw:.0%} · Loss {loss:.0%}").format(
                win=win, draw=draw, loss=loss))
            pred.add_css_class("caption")
            pred.add_css_class("dim-label")
            text.append(pred)
        row.append(text)
        if c.actual is not None:
            result = pill(c.actual.text(), "result-pill", f"sim-{c.actual.result}")
        else:
            result = pill(_("unknown"), "result-pill", "sim-draw")
        result.set_valign(Gtk.Align.CENTER)
        row.append(result)
        return row

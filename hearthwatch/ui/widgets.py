"""Small shared GTK helpers."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, Gtk, Pango  # noqa: E402

from hearthwatch.bg.models import Minion  # noqa: E402
from hearthwatch.cards import tribe_name  # noqa: E402
from hearthwatch.i18n import N_, _  # noqa: E402

CSS = """
.sim-win { color: @success_color; font-weight: bold; }
.sim-draw { opacity: 0.7; font-weight: bold; }
.sim-loss { color: @error_color; font-weight: bold; }
.next-opponent { color: @accent_color; font-weight: bold; }
.place-top { color: @success_color; font-weight: bold; }
.place-bottom { color: @error_color; font-weight: bold; }
.big-number { font-size: 1.6em; font-weight: 800; }

/* --- single-page live view ------------------------------------------- */
.section { padding: 14px 16px; }
.hero-name { font-size: 1.45em; font-weight: 800; }
.phase-pill { border-radius: 999px; padding: 2px 10px; font-weight: 700; font-size: 0.85em; }
.phase-recruit { background: alpha(@accent_bg_color, 0.18); color: @accent_color; }
.phase-combat { background: alpha(@error_bg_color, 0.18); color: @error_color; }
.stat-value { font-size: 1.5em; font-weight: 800; }
.stat-caption { font-size: 0.78em; opacity: 0.65; }
.stat-tile { background: alpha(currentColor, 0.05); border-radius: 10px; padding: 6px 4px; }
.tribe-chip { border-radius: 999px; padding: 2px 9px; font-size: 0.85em; font-weight: 600;
              background: alpha(@success_bg_color, 0.16); color: @success_color; }
.tribe-chip.banned { background: alpha(currentColor, 0.06); color: alpha(currentColor, 0.45); }
.minion { background: alpha(currentColor, 0.06); border-radius: 10px; padding: 5px 6px;
          border: 1px solid transparent; }
.minion.golden { border-color: #e5a50a; background: alpha(#e5a50a, 0.10); }
.minion-atk { font-weight: 800; font-size: 1.15em; color: #e5a50a; }
.minion-hp { font-weight: 800; font-size: 1.15em; color: @error_color; }
.minion-name { font-size: 0.78em; }
.minion-kw { font-size: 0.7em; opacity: 0.7; }
.minion-buff { font-size: 0.7em; font-weight: 700; color: @accent_color; }
.place-badge { min-width: 28px; min-height: 28px; border-radius: 999px; font-weight: 800;
               background: alpha(currentColor, 0.08); }
.place-badge.top { background: alpha(@success_bg_color, 0.22); color: @success_color; }
.place-badge.bottom { background: alpha(@error_bg_color, 0.16); color: @error_color; }
.lobby-row { padding: 8px 4px; }
.lobby-row.me { background: alpha(@accent_bg_color, 0.08); border-radius: 10px; }
.lobby-row.next { background: alpha(@accent_bg_color, 0.14); border-radius: 10px; }
.lobby-row.dead { opacity: 0.45; }
.tag-pill { border-radius: 999px; padding: 1px 8px; font-size: 0.75em; font-weight: 700;
            background: @accent_bg_color; color: @accent_fg_color; }
.odds-value { font-size: 1.35em; font-weight: 800; }
.result-pill { border-radius: 8px; padding: 4px 10px; font-weight: 700; }
.result-pill.sim-win { background: alpha(@success_bg_color, 0.18); }
.result-pill.sim-loss { background: alpha(@error_bg_color, 0.16); }
.result-pill.sim-draw { background: alpha(currentColor, 0.08); }
.summary-place { min-width: 64px; min-height: 64px; border-radius: 999px; font-size: 2em;
                 font-weight: 800; background: alpha(currentColor, 0.08); }
.summary-place.top { background: alpha(@success_bg_color, 0.22); color: @success_color; }
.summary-place.bottom { background: alpha(@error_bg_color, 0.16); color: @error_color; }

/* --- v2: art, bars, compact rows ---------------------------------------- */
.art { border-radius: 10px; background: alpha(currentColor, 0.10); }
.art.round { border-radius: 999px; }
.minion.compact { padding: 3px 4px; }
.minion.compact .minion-atk, .minion.compact .minion-hp { font-size: 1.0em; }
.focus-title { font-size: 1.15em; font-weight: 800; }
.meta { font-size: 0.85em; opacity: 0.75; }
.chip { border-radius: 999px; padding: 2px 9px; font-size: 0.82em; font-weight: 600;
        background: alpha(@accent_bg_color, 0.16); color: @accent_color; }
.chip.counter { background: alpha(#e5a50a, 0.16); color: #c88800; }
.dot { min-width: 14px; min-height: 14px; border-radius: 999px; font-size: 0.7em; font-weight: 800; }
.dot.win { background: @success_bg_color; color: @success_fg_color; }
.dot.loss { background: @error_bg_color; color: @error_fg_color; }
.dot.draw { background: alpha(currentColor, 0.35); }
.lethal { border-radius: 10px; padding: 8px 12px; font-weight: 800;
          background: @error_bg_color; color: @error_fg_color; }
.last-line { font-size: 0.9em; }
.pool-card { padding: 8px; }
.tribe-chip.anomaly { background: alpha(@accent_bg_color, 0.18); color: @accent_color; font-weight: 700; }
.pool-text { font-size: 0.8em; opacity: 0.85; }
statuspage.mascot image.icon { -gtk-icon-size: 220px; }
"""

KEYWORD_SHORT = {
    "Taunt": N_("Taunt"),
    "Divine Shield": N_("Shield"),
    "Reborn": N_("Reborn"),
    "Poisonous": N_("Poison"),
    "Windfury": N_("Wind"),
    "Mega-Windfury": N_("Mega-Wind"),
    "Cleave": N_("Cleave"),
    "Deathrattle": N_("DR"),
}


def install_css() -> None:
    provider = Gtk.CssProvider()
    if hasattr(provider, "load_from_string"):  # GTK >= 4.12
        provider.load_from_string(CSS)
    else:
        provider.load_from_data(CSS.encode())
    from gi.repository import Gdk

    display = Gdk.Display.get_default()
    if display is not None:
        Gtk.StyleContext.add_provider_for_display(
            display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )


_scale_provider: Gtk.CssProvider | None = None


def set_font_scale(percent: int) -> None:
    """Scale all text of the tracker (``.hearthwatch-root``) - settings font size."""
    global _scale_provider
    display = Gdk.Display.get_default()
    if display is None:
        return
    if _scale_provider is None:
        _scale_provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(
            display, _scale_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1
        )
    css = f".hearthwatch-root {{ font-size: {percent / 100:.2f}em; }}"
    if hasattr(_scale_provider, "load_from_string"):
        _scale_provider.load_from_string(css)
    else:
        _scale_provider.load_from_data(css.encode())


# card art provider (hearthwatch.art.ArtCache), set by the app; None = no images
_art = None


def set_art_provider(provider) -> None:
    global _art
    _art = provider


def card_art(card_id: str, size: int, round_: bool = False) -> Gtk.Widget | None:
    """A small square picture of the card's art, loaded in the background;
    None if images are disabled. Fixed size, so layouts do not jump."""
    if _art is None or not getattr(_art, "enabled", False) or not card_id:
        return None
    image = Gtk.Image(pixel_size=size)
    frame = Gtk.Box(halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER, hexpand=False, vexpand=False)
    frame.set_size_request(size, size)
    frame.set_overflow(Gtk.Overflow.HIDDEN)
    frame.add_css_class("art")
    if round_:
        frame.add_css_class("round")
    frame.append(image)

    def show(path) -> None:
        GLib.idle_add(lambda: (image.set_from_file(str(path)), False)[1])

    hit = _art.request(card_id, show)
    if hit is not None:
        image.set_from_file(str(hit))
    return frame


def chip_box() -> Gtk.Widget:
    """Container that wraps chips like text (Adw.WrapBox, libadwaita >= 1.7),
    falling back to a FlowBox. Fill it with ``append``, empty it with ``clear``."""
    if hasattr(Adw, "WrapBox"):
        return Adw.WrapBox(child_spacing=4, line_spacing=4)
    return Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, column_spacing=4, row_spacing=4,
                       max_children_per_line=10)


def tribe_names(tribes: list[str]) -> str:
    return ", ".join(tribe_name(t) for t in tribes) or "–"


def clear(box: Gtk.Widget) -> None:
    child = box.get_first_child()
    while child is not None:
        nxt = child.get_next_sibling()
        box.remove(child)
        child = nxt


class OddsBar(Gtk.Widget):
    """Horizontal stacked bar: win (green) / draw (grey) / loss (red).

    Drawn with GtkSnapshot, so no pycairo/gi-cairo is needed.
    """

    COLORS = ("#2ec27e", "#9a9996", "#e01b24")

    def __init__(self) -> None:
        super().__init__()
        self.set_hexpand(True)
        self.set_size_request(-1, 14)
        self._values = (0.0, 0.0, 0.0)

    def set_values(self, win: float, draw: float, loss: float) -> None:
        self._values = (win, draw, loss)
        self.queue_draw()

    def do_snapshot(self, snapshot) -> None:
        from gi.repository import Gdk, Graphene

        width, height = self.get_width(), self.get_height()
        x = 0.0
        for value, color in zip(self._values, self.COLORS):
            w = width * value
            if w <= 0:
                continue
            rgba = Gdk.RGBA()
            rgba.parse(color)
            rect = Graphene.Rect().init(x, 0, w, height)
            snapshot.append_color(rgba, rect)
            x += w


# --- building blocks of the single-page view -----------------------------------
class MinionChip(Gtk.Box):
    """Compact minion: attack/health big, name and keywords small."""

    def __init__(self, m: Minion, compact: bool = False) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        self.add_css_class("minion")
        if compact:
            self.add_css_class("compact")
        if m.golden:
            self.add_css_class("golden")
        art = card_art(m.card_id, 30 if compact else 44)
        if art is not None:
            self.append(art)
        stats = Gtk.Box(spacing=4, halign=Gtk.Align.CENTER)
        atk = Gtk.Label(label=str(m.attack))
        atk.add_css_class("minion-atk")
        hp = Gtk.Label(label=str(m.health))
        hp.add_css_class("minion-hp")
        sep = Gtk.Label(label="/")
        sep.add_css_class("dim-label")
        for w in (atk, sep, hp):
            stats.append(w)
        self.append(stats)
        name = Gtk.Label(label=("★ " if m.golden else "") + (m.name or m.card_id),
                         ellipsize=Pango.EllipsizeMode.END, max_width_chars=8 if compact else 11,
                         width_chars=5)
        name.add_css_class("minion-name")
        self.append(name)
        kws = " · ".join(_(KEYWORD_SHORT.get(k, k)) for k in m.keywords())
        if kws and not compact:
            kw = Gtk.Label(label=kws, ellipsize=Pango.EllipsizeMode.END, max_width_chars=12)
            kw.add_css_class("minion-kw")
            self.append(kw)
        buffs = getattr(m, "buffs", None) or []
        if buffs:
            count = sum(int(b.rsplit("×", 1)[1]) if "×" in b else 1 for b in buffs)
            text = _("{count} buff") if count == 1 else _("{count} buffs")
            buff = Gtk.Label(label=f"✦ {count}" if compact else "✦ " + text.format(count=count))
            buff.add_css_class("minion-buff")
            self.append(buff)
        self.set_tooltip_text(m.tooltip())


def board_flow(minions: list[Minion], empty_text: str = "",
               compact: bool = False) -> Gtk.Widget:
    """All minions of a warband side by side (wraps when narrow)."""
    if not minions:
        empty_text = empty_text or _("empty board")
        label = Gtk.Label(label=empty_text, xalign=0)
        label.add_css_class("dim-label")
        label.add_css_class("caption")
        return label
    flow = Gtk.FlowBox(
        selection_mode=Gtk.SelectionMode.NONE, homogeneous=True,
        min_children_per_line=4 if compact else 3, max_children_per_line=7,
        column_spacing=4, row_spacing=4, valign=Gtk.Align.START,
    )
    for m in minions:
        flow.append(MinionChip(m, compact))
    return flow


class HealthBar(Gtk.Widget):
    """Thin bar: health relative to the starting health (green/yellow/red)."""

    def __init__(self, height: int = 6) -> None:
        super().__init__()
        self.set_hexpand(True)
        self.set_size_request(-1, height)
        self._fraction = 1.0

    def set_fraction(self, fraction: float) -> None:
        self._fraction = max(0.0, min(1.0, fraction))
        self.queue_draw()

    def do_snapshot(self, snapshot) -> None:
        from gi.repository import Graphene

        width, height = self.get_width(), self.get_height()
        track = Gdk.RGBA()
        track.parse("rgba(128,128,128,0.25)")
        snapshot.append_color(track, Graphene.Rect().init(0, 0, width, height))
        f = self._fraction
        color = Gdk.RGBA()
        color.parse("#2ec27e" if f > 0.6 else "#e5a50a" if f > 0.3 else "#e01b24")
        snapshot.append_color(color, Graphene.Rect().init(0, 0, width * f, height))


def result_dot(result: str, text: str = "", tooltip: str = "") -> Gtk.Label:
    dot = Gtk.Label(label=text)
    dot.add_css_class("dot")
    dot.add_css_class({"win": "win", "loss": "loss"}.get(result, "draw"))
    if tooltip:
        dot.set_tooltip_text(tooltip)
    return dot


def stat_tile(caption: str) -> tuple[Gtk.Box, Gtk.Label]:
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0, hexpand=True)
    box.add_css_class("stat-tile")
    value = Gtk.Label(label="–")
    value.add_css_class("stat-value")
    value.add_css_class("numeric")
    cap = Gtk.Label(label=caption)
    cap.add_css_class("stat-caption")
    box.append(value)
    box.append(cap)
    return box, value


def pill(text: str, *css: str) -> Gtk.Label:
    label = Gtk.Label(label=text)
    for c in css:
        label.add_css_class(c)
    return label


def card(title: str | None = None) -> tuple[Gtk.Box, Gtk.Box]:
    """A libadwaita card with an optional heading; returns (outer, body)."""
    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
    if title:
        heading = Gtk.Label(label=title, xalign=0)
        heading.add_css_class("heading")
        outer.append(heading)
    body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    body.add_css_class("card")
    body.add_css_class("section")
    outer.append(body)
    return outer, body

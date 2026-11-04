"""Small shared GTK helpers."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GdkPixbuf, GLib, Gtk, Pango  # noqa: E402

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
.minion:hover { border-color: alpha(@accent_color, 0.55); }
.minion-atk { font-weight: 800; font-size: 1.15em; color: #e5a50a; }
.minion-hp { font-weight: 800; font-size: 1.15em; color: @error_color; }
.minion-name { font-size: 0.78em; }
.minion-kw { font-size: 0.7em; opacity: 0.7; }
.minion-buff { font-size: 0.7em; font-weight: 700; color: @accent_color; }
.minion-tip { padding: 4px; }
.minion-tip .tip-name { font-weight: 800; font-size: 1.1em; }
.minion-tip .tip-text { font-size: 0.95em; }
.minion-tip .tip-caption { font-size: 0.8em; font-weight: 700; opacity: 0.7; }
.minion-tip .tip-buff-name { font-weight: 700; }
.minion-tip .tip-buff-text { font-size: 0.9em; opacity: 0.85; }
.place-badge { min-width: 28px; min-height: 28px; border-radius: 999px; font-weight: 800;
               background: alpha(currentColor, 0.08); }
.place-badge.top { background: alpha(@success_bg_color, 0.22); color: @success_color; }
.place-badge.bottom { background: alpha(@error_bg_color, 0.16); color: @error_color; }
.lobby-row { padding: 8px 4px; }
.lobby-row.me { background: alpha(@accent_bg_color, 0.08); border-radius: 10px; }
.lobby-row.next { background: alpha(@accent_bg_color, 0.14); border-radius: 10px; }
.lobby-row.dead { opacity: 0.45; }
.hero-option { padding: 8px 4px; border-radius: 10px; background: alpha(currentColor, 0.05); }
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
.art { border-radius: 10px; }
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
    """Scale all text of the tracker (``.hearthwatch-root``) - settings font size,
    times the window scale."""
    global _scale_provider, _user_font
    _user_font = percent
    percent = percent * _ui_scale
    display = Gdk.Display.get_default()
    if display is None:
        return
    if _scale_provider is None:
        _scale_provider = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(
            display, _scale_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1
        )
    # libadwaita gives headings and captions fixed sizes: make them relative so they grow too
    css = (f".hearthwatch-root {{ font-size: {percent / 100:.2f}em; }}"
           ".hearthwatch-root .heading { font-size: 1.0em; }"
           ".hearthwatch-root .caption { font-size: 0.85em; }")
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
    size = scaled(size)
    image = Gtk.Image(pixel_size=size)
    frame = Gtk.Box(halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER, hexpand=False, vexpand=False)
    frame.set_size_request(size, size)
    frame.set_overflow(Gtk.Overflow.HIDDEN)
    frame.add_css_class("art")
    if round_:
        frame.add_css_class("round")
    frame.append(image)

    def show(path) -> None:
        GLib.idle_add(lambda: (_set_art(image, path), False)[1])

    hit = _art.request(card_id, show)
    if hit is not None:
        _set_art(image, hit)
    return frame


# the art images have a light rim; cut this share off every side before showing them
ART_CROP = 0.07
_textures: dict[str, Gdk.Texture] = {}


def _set_art(image: Gtk.Image, path) -> None:
    key = str(path)
    texture = _textures.get(key)
    if texture is None:
        try:
            pix = GdkPixbuf.Pixbuf.new_from_file(key)
            cut_w, cut_h = int(pix.get_width() * ART_CROP), int(pix.get_height() * ART_CROP)
            pix = pix.new_subpixbuf(cut_w, cut_h, pix.get_width() - 2 * cut_w, pix.get_height() - 2 * cut_h)
            texture = Gdk.Texture.new_for_pixbuf(pix)
        except GLib.Error:
            image.set_from_file(key)  # unreadable image: let GTK show what it can
            return
        if len(_textures) > 400:
            _textures.clear()
        _textures[key] = texture
    image.set_from_paintable(texture)


# art sizes of minion cards (normal, compact); smaller in a narrow window so a
# full board of 7 always fits one row - set by the main view's layout
_board_art = {"normal": 56, "compact": 40}


def set_board_art(wide: bool) -> None:
    _board_art.update(normal=64 if wide else 44, compact=40 if wide else 30)


# everything grows with the window: art sizes and text are multiplied by this
_ui_scale = 1.0
_user_font = 100


def scaled(px: int) -> int:
    return int(round(px * _ui_scale))


def ui_scale() -> float:
    return _ui_scale


def set_ui_scale(factor: float) -> None:
    global _ui_scale
    _ui_scale = factor
    set_font_scale(_user_font)


def scale_for_width(width: int, wide: bool) -> float:
    """How much bigger than normal everything may be at this window width: 1.0 up to
    a comfortable width (about 1100 px wide, 480 px narrow), then growing in 10 %
    steps, at most 1.6."""
    base = 1100 if wide else 480
    factor = max(1.0, min(1.6, width / base))
    return round(factor * 10) / 10


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
        art = card_art(m.card_id, _board_art["compact" if compact else "normal"])
        if art is not None:
            self.append(art)
        stats = Gtk.Box(spacing=2, halign=Gtk.Align.CENTER)
        atk = Gtk.Label(label=str(m.attack))
        atk.add_css_class("minion-atk")
        hp = Gtk.Label(label=str(m.health))
        hp.add_css_class("minion-hp")
        sep = Gtk.Label(label="/")
        sep.add_css_class("dim-label")
        for w in (atk, sep, hp):
            stats.append(w)
        self.append(stats)
        # the full name on up to two lines (ellipsized only if it is longer still)
        name = Gtk.Label(label=("★ " if m.golden else "") + (m.name or m.card_id),
                         wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR, lines=2,
                         ellipsize=Pango.EllipsizeMode.END, justify=Gtk.Justification.CENTER,
                         max_width_chars=9 if compact else 12, width_chars=3)
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
        # a card-like popup with art, text and buffs; built only when first shown
        self._minion = m
        self._tip: Gtk.Widget | None = None
        self.set_has_tooltip(True)
        self.connect("query-tooltip", self._on_query_tooltip)

    def _on_query_tooltip(self, _w, _x, _y, _keyboard, tooltip: Gtk.Tooltip) -> bool:
        if self._tip is None:
            self._tip = minion_tooltip(self._minion)
        tooltip.set_custom(self._tip)
        return True


def minion_tooltip(m: Minion) -> Gtk.Widget:
    """Hover popup for a minion: art, name, stats, keywords, card text and every buff."""
    box = Gtk.Box(spacing=12)
    box.add_css_class("minion-tip")
    art = card_art(m.card_id, 96)
    if art is not None:
        art.set_valign(Gtk.Align.START)
        box.append(art)
    info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
    box.append(info)

    def label(text: str, css: str, **kw) -> Gtk.Label:
        lab = Gtk.Label(label=text, xalign=0, wrap=True, max_width_chars=42, **kw)
        lab.add_css_class(css)
        info.append(lab)
        return lab

    head = Gtk.Box(spacing=8)
    name = Gtk.Label(label=("★ " if m.golden else "") + (m.name or m.card_id), xalign=0, wrap=True,
                     max_width_chars=30, hexpand=True)
    name.add_css_class("tip-name")
    head.append(name)
    stats = Gtk.Box(spacing=2, valign=Gtk.Align.CENTER)
    for text, css in ((str(m.attack), "minion-atk"), ("/", "dim-label"), (str(m.health), "minion-hp")):
        part = Gtk.Label(label=text)
        part.add_css_class(css)
        stats.append(part)
    head.append(stats)
    info.append(head)
    meta = [tribe_name(t) for t in m.tribes]
    meta += [_(k) for k in m.keywords()]
    if meta:
        label(" · ".join(meta), "tip-caption")
    if m.text:
        label(m.text, "tip-text")
    if m.buffs:
        info.append(Gtk.Separator(margin_top=4, margin_bottom=2))
        label(_("Buffs:").rstrip(":"), "tip-caption")
        texts = m.buff_texts if len(m.buff_texts) == len(m.buffs) else [""] * len(m.buffs)
        for buff, text in zip(m.buffs, texts):
            label("✦ " + buff, "tip-buff-name")
            if text:
                lab = label(text, "tip-buff-text")
                lab.set_margin_start(14)
    return box


BOARD_SLOTS = 7


def board_flow(minions: list[Minion], empty_text: str = "",
               compact: bool = False) -> Gtk.Widget:
    """All minions of a warband side by side (wraps when narrow)."""
    if not minions:
        empty_text = empty_text or _("empty board")
        label = Gtk.Label(label=empty_text, xalign=0)
        label.add_css_class("dim-label")
        label.add_css_class("caption")
        return label
    # 7 equal slots (a board holds at most 7 minions): always one row, and every
    # board lines up with the others; cards shrink in narrow windows
    row = Gtk.Box(spacing=4, homogeneous=True, valign=Gtk.Align.START)
    for m in minions:
        row.append(MinionChip(m, compact))
    for _i in range(BOARD_SLOTS - len(minions)):
        row.append(Gtk.Box())
    return row


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

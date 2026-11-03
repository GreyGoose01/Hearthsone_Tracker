"""Minimum versions of Python, GTK and libadwaita, checked before the GUI starts.

The GUI uses Adw.ToolbarView, Adw.SwitchRow and Adw.SpinRow (libadwaita 1.4,
which needs GTK 4.12). Newer widgets (Adw.Breakpoint, Adw.PreferencesDialog,
Adw.AboutDialog, Adw.WrapBox) are optional and have fallbacks. The CI runs the
GUI tests on Fedora 39, which ships exactly these minimums.
"""

from __future__ import annotations

import sys

from hearthwatch.i18n import _

MIN_PYTHON = (3, 12)
MIN_GTK = (4, 12)
MIN_ADW = (1, 4)


def _fmt(version: tuple[int, ...]) -> str:
    return ".".join(str(v) for v in version)


def problems(python: tuple[int, ...], gtk: tuple[int, ...] | None, adw: tuple[int, ...] | None) -> list[str]:
    """Human-readable problems for the given versions (empty: all fine)."""
    found = []
    for name, have, need in (("Python", python, MIN_PYTHON), ("GTK", gtk, MIN_GTK),
                             ("libadwaita", adw, MIN_ADW)):
        if have is not None and tuple(have[:2]) < need:
            found.append(_("{name} {have} is too old, Hearthwatch needs {need} or newer.").format(
                name=name, have=_fmt(have), need=_fmt(need)))
    return found


def runtime() -> tuple[tuple[int, ...], tuple[int, ...], tuple[int, ...]]:
    """Versions of the running Python, GTK and libadwaita (imports gi)."""
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Adw, Gtk

    gtk = (Gtk.get_major_version(), Gtk.get_minor_version(), Gtk.get_micro_version())
    adw = (Adw.get_major_version(), Adw.get_minor_version(), Adw.get_micro_version())
    return tuple(sys.version_info[:3]), gtk, adw


def runtime_problems() -> list[str]:
    return problems(*runtime())

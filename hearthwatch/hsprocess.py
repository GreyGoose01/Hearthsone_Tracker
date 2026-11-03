"""Is Hearthstone running right now?

The Linux Unity player of hearthstone-linux-gui runs as ``Hearthstone.x86_64``
(``comm`` is cut to 15 characters: ``Hearthstone.x86``). Some setups start it
through a loader (e.g. the Nix FHS wrapper), so the command line is checked
as well. Reading ``/proc`` needs no special rights and works for the DEB,
AppImage and Flatpak versions alike.
"""

from __future__ import annotations

import os
from pathlib import Path

PROC = Path("/proc")
EXECUTABLE = "Hearthstone.x86_64"
COMM_PREFIX = EXECUTABLE[:15]


def _read(path: Path, limit: int = 4096) -> bytes:
    try:
        with path.open("rb") as fh:
            return fh.read(limit)
    except OSError:
        return b""


def hearthstone_running(proc_root: Path = PROC) -> bool | None:
    """True/False, or None when it cannot be determined (no /proc, e.g. macOS)."""
    try:
        entries = list(os.scandir(proc_root))
    except OSError:
        return None
    if not any(e.name == "self" or e.name.isdigit() for e in entries):
        return None
    for entry in entries:
        if not entry.name.isdigit():
            continue
        pdir = Path(entry.path)
        comm = _read(pdir / "comm", 64).decode("utf-8", "replace").strip()
        if comm.startswith(COMM_PREFIX):
            return True
        args = _read(pdir / "cmdline").split(b"\0")[:3]
        if any(os.path.basename(a.decode("utf-8", "replace")) == EXECUTABLE for a in args if a):
            return True
    return False

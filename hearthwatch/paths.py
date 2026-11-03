"""Locate the Hearthstone installation of hearthstone-linux-gui and our own files.

The launcher (https://github.com/DawnMagnet/hearthstone-linux-gui) keeps:

* its config at ``$XDG_CONFIG_HOME/hearthstone-linux-gui/config.toml``
  (optional ``game_dir`` entry),
* the game at ``$XDG_DATA_HOME/hearthstone-linux-gui/game`` by default,
* the game's own logs in ``<game_dir>/Logs/`` (one sub folder per session).

The Linux Unity player runs a converted macOS payload and therefore reads its
settings from the macOS location below ``$HOME``:
``~/Library/Preferences/Blizzard/Hearthstone/`` - that is where ``log.config``
has to go.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

LAUNCHER_APP_DIR = "hearthstone-linux-gui"
FLATPAK_APP_ID = "io.github.hearthstone_linux_gui"
APP_NAME = "hearthwatch"
LEGACY_APP_NAME = "bgtracker"  # name before the rename; data is moved over once


def _home() -> Path:
    return Path(os.environ.get("HOME") or Path.home())


def _xdg(var: str, fallback: str) -> Path:
    value = os.environ.get(var)
    if value and os.path.isabs(value):
        return Path(value)
    return _home() / fallback


def xdg_config_home() -> Path:
    return _xdg("XDG_CONFIG_HOME", ".config")


def xdg_data_home() -> Path:
    return _xdg("XDG_DATA_HOME", ".local/share")


def xdg_cache_home() -> Path:
    return _xdg("XDG_CACHE_HOME", ".cache")


def xdg_state_home() -> Path:
    return _xdg("XDG_STATE_HOME", ".local/state")


def log_file() -> Path:
    """The tracker's own log (errors and combat events) for bug reports."""
    return xdg_state_home() / APP_NAME / "hearthwatch.log"


def migrate_legacy_dirs() -> list[Path]:
    """Rename our old ``bgtracker`` folders (history, settings, cache, log) once.

    Only moves a folder when the new one does not exist yet. Returns the new
    paths that were created; errors are ignored (the app then starts fresh).
    """
    moved = []
    for base in (xdg_data_home(), xdg_config_home(), xdg_cache_home(), xdg_state_home()):
        old, new = base / LEGACY_APP_NAME, base / APP_NAME
        if not old.is_dir() or new.exists():
            continue
        try:
            old.rename(new)
        except OSError:
            continue
        legacy_log = new / f"{LEGACY_APP_NAME}.log"
        if legacy_log.exists() and not (new / f"{APP_NAME}.log").exists():
            try:
                legacy_log.rename(new / f"{APP_NAME}.log")
            except OSError:
                pass
        moved.append(new)
    return moved


def flatpak_root() -> Path:
    return _home() / ".var/app" / FLATPAK_APP_ID


def launcher_config_files() -> list[Path]:
    """Possible locations of the launcher's ``config.toml`` (native first)."""
    return [
        xdg_config_home() / LAUNCHER_APP_DIR / "config.toml",
        flatpak_root() / "config" / LAUNCHER_APP_DIR / "config.toml",
    ]


def _game_dir_from_config(path: Path) -> Path | None:
    try:
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError):
        return None
    value = data.get("game_dir")
    if isinstance(value, str) and value:
        return Path(value).expanduser()
    return None


def game_dir_candidates() -> list[Path]:
    """All plausible game directories, most specific first, without duplicates."""
    candidates: list[Path] = []
    override = os.environ.get("HEARTHWATCH_GAME_DIR") or os.environ.get("BGTRACKER_GAME_DIR")
    if override:
        candidates.append(Path(override).expanduser())
    for cfg in launcher_config_files():
        configured = _game_dir_from_config(cfg)
        if configured:
            candidates.append(configured)
    candidates.append(xdg_data_home() / LAUNCHER_APP_DIR / "game")
    candidates.append(flatpak_root() / "data" / LAUNCHER_APP_DIR / "game")
    seen: set[Path] = set()
    unique = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    return unique


def find_game_dir() -> Path:
    """Return the first candidate that looks like an installation.

    Falls back to the first candidate so callers always get a path to show.
    """
    candidates = game_dir_candidates()
    for c in candidates:
        if (c / "Bin" / "Hearthstone.x86_64").exists() or (c / "Logs").is_dir():
            return c
    return candidates[0]


PREFS_REL = Path("Library/Preferences/Blizzard/Hearthstone")
_FLATPAK_SEARCH_DEPTH = 7  # .var/app/<id>/ + Library/Preferences/Blizzard/Hearthstone/options.txt


def log_config_candidates() -> list[Path]:
    """Where the Unity player may look for ``log.config`` (native, then Flatpak)."""
    return [_home() / PREFS_REL / "log.config", flatpak_root() / PREFS_REL / "log.config"]


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def find_options_files() -> list[Path]:
    """``options.txt`` files written by the game, newest first.

    The game writes ``options.txt`` into its settings folder on first start;
    ``log.config`` has to live in the same folder. Only the native location
    and the launcher's Flatpak folder are searched (no full home scan).
    """
    found: list[Path] = []
    native = _home() / PREFS_REL / "options.txt"
    if native.is_file():
        found.append(native)
    root = flatpak_root()
    if root.is_dir():
        for dirpath, dirnames, filenames in os.walk(root):
            here = Path(dirpath)
            depth = len(here.relative_to(root).parts)
            # never descend into the multi-GB game folder or caches
            dirnames[:] = [
                d for d in dirnames
                if depth + 1 < _FLATPAK_SEARCH_DEPTH and d not in ("game", "cache", "ngdp", "unity")
            ]
            if "options.txt" in filenames and here.name == "Hearthstone":
                found.append(here / "options.txt")
    unique = list(dict.fromkeys(found))
    return sorted(unique, key=_mtime, reverse=True)


def settings_dir() -> tuple[Path, bool]:
    """The game's settings folder and whether it was confirmed by an options.txt."""
    options = find_options_files()
    if options:
        return options[0].parent, True
    return _home() / PREFS_REL, False


def log_config_path() -> Path:
    """``log.config`` next to the game's ``options.txt`` (default: native path)."""
    return settings_dir()[0] / "log.config"


@dataclass(frozen=True)
class TrackerPaths:
    data_dir: Path
    cache_dir: Path

    @property
    def database(self) -> Path:
        return self.data_dir / "matches.db"

    @property
    def cards_cache(self) -> Path:
        return self.cache_dir / "cards.json"

    def ensure(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)


def tracker_paths() -> TrackerPaths:
    return TrackerPaths(
        data_dir=xdg_data_home() / APP_NAME,
        cache_dir=xdg_cache_home() / APP_NAME,
    )

"""Lift Hearthstone's log size limit in ``client.config``.

Without ``[Log] FileSizeLimit.Int=-1`` Hearthstone stops writing Power.log
once it reaches a size limit - in Battlegrounds (with Verbose logging) often
in the middle of a game. Hearthstone Deck Tracker sets the same value.

hearthstone-linux-gui writes ``<game_dir>/client.config`` itself (it holds the
Battle.net settings) as flat ``Key=value`` lines and re-creates it on
Install / Update, adding the user's lines from
``~/.config/hearthstone-linux-gui/client.config.overrides``. So the setting is
added in its flat form ``Log.FileSizeLimit.Int=-1`` to

* the overrides file - survives Install / Update, and
* the current ``client.config`` - takes effect at the next game start,

without touching any other line.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from hearthwatch import paths

KEY = "Log.FileSizeLimit.Int"
VALUE = "-1"
LINE = f"{KEY}={VALUE}"


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return ""


def has_setting(text: str) -> bool:
    """Flat ``Log.FileSizeLimit.Int=-1`` or ``[Log]`` + ``FileSizeLimit.Int=-1``."""
    section = ""
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            continue
        if "=" not in line or line.startswith("#"):
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        full = f"{section}.{key}" if section else key
        if full.lower() == KEY.lower() and value == VALUE:
            return True
    return False


def _with_setting(text: str) -> str:
    """``text`` with exactly one top-level ``Log.FileSizeLimit.Int=-1`` line.

    The line goes *before* the first ``[Section]`` header - appended after
    one it would belong to that section (``Log.Log.FileSizeLimit.Int``).
    Any other value for the setting is removed (flat or under ``[Log]``), as
    are our own lines that earlier versions appended inside a section.
    """
    out: list[str] = []
    section = ""
    inserted = False
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("[") and line.endswith("]"):
            if not inserted:
                while out and not out[-1].strip():
                    out.pop()
                out.append(LINE)
                inserted = True
            section = line[1:-1].strip()
            out.append(raw)
            continue
        if "=" in line and not line.startswith("#"):
            key = line.split("=", 1)[0].strip()
            full = f"{section}.{key}" if section else key
            if KEY.lower() in (key.lower(), full.lower()):
                continue
        out.append(raw)
    if not inserted:
        while out and not out[-1].strip():
            out.pop()
        out.append(LINE)
    return "\n".join(out) + "\n"


def overrides_path() -> Path:
    """The launcher's ``client.config.overrides`` (next to its config.toml)."""
    candidates = [cfg.parent / "client.config.overrides" for cfg in paths.launcher_config_files()]
    for cfg, candidate in zip(paths.launcher_config_files(), candidates):
        if cfg.exists():
            return candidate
    return candidates[0]


def client_config_path(game_dir: Path | None = None) -> Path:
    return (game_dir or paths.find_game_dir()) / "client.config"


def is_configured(game_dir: Path | None = None) -> bool:
    return has_setting(_read(client_config_path(game_dir)))


def ensure(game_dir: Path | None = None) -> list[Path]:
    """Add the setting where it is missing; returns the files that changed.

    ``client.config`` is only edited if it exists (the launcher creates it on
    installation); a backup ``client.config.bak`` is made once.
    """
    changed: list[Path] = []
    overrides = overrides_path()
    if not has_setting(_read(overrides)):
        overrides.parent.mkdir(parents=True, exist_ok=True)
        overrides.write_text(_with_setting(_read(overrides)), encoding="utf-8")
        changed.append(overrides)
    client = client_config_path(game_dir)
    if client.is_file() and not has_setting(_read(client)):
        backup = client.with_name("client.config.bak")
        if not backup.exists():
            shutil.copy2(client, backup)
        client.write_text(_with_setting(_read(client)), encoding="utf-8")
        changed.append(client)
    return changed


def status(game_dir: Path | None = None) -> dict:
    """Where the setting is present - for a precise diagnosis."""
    client = client_config_path(game_dir)
    overrides = overrides_path()
    return {
        "client": client,
        "client_exists": client.is_file(),
        "client_ok": has_setting(_read(client)),
        "overrides": overrides,
        "overrides_ok": has_setting(_read(overrides)),
    }

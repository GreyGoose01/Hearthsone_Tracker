"""Check and write Hearthstone's ``log.config`` so that ``Power.log`` is written.

Hearthstone only writes ``Power.log`` when ``log.config`` enables the
``[Power]`` section. Changes take effect after the game is restarted.

Broken files (text before the first section, lines without ``=``, wrong
encoding, a folder instead of a file) never raise: they are reported by
:func:`problem` and replaced by :func:`ensure`, which moves the old file
aside as a backup first.
"""

from __future__ import annotations

import configparser
import io
import shutil
from pathlib import Path

from hearthwatch.i18n import _

REQUIRED: dict[str, dict[str, str]] = {
    "Power": {
        "LogLevel": "1",
        "FilePrinting": "true",
        "ConsolePrinting": "false",
        "ScreenPrinting": "false",
        "Verbose": "true",
    },
    "LoadingScreen": {
        "LogLevel": "1",
        "FilePrinting": "true",
        "ConsolePrinting": "false",
        "ScreenPrinting": "false",
    },
}

ALL_ENTRIES = [f"{s}.{k}" for s, keys in REQUIRED.items() for k in keys]


class BrokenLogConfig(Exception):
    """The file exists but cannot be read as a log.config."""


def _parser() -> configparser.ConfigParser:
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str  # keep the game's key spelling
    return parser


def _read(path: Path) -> configparser.ConfigParser:
    """Parse the file; raises :class:`BrokenLogConfig` with a German reason."""
    parser = _parser()
    if not path.exists() and not path.is_symlink():
        return parser
    if path.is_dir():
        raise BrokenLogConfig("ist ein Ordner statt einer Datei")
    try:
        text = path.read_text(encoding="utf-8-sig")  # tolerate a BOM
    except UnicodeDecodeError:
        raise BrokenLogConfig("ist keine Textdatei in UTF-8") from None
    except OSError as exc:
        raise BrokenLogConfig(f"nicht lesbar ({exc.strerror or exc})") from None
    try:
        parser.read_string(text, source=str(path))
    except configparser.MissingSectionHeaderError as exc:
        raise BrokenLogConfig(_("line {line} comes before the first [section]").format(line=exc.lineno)) from None
    except configparser.ParsingError as exc:
        lines = ", ".join(str(lineno) for lineno, _ in exc.errors[:3])
        raise BrokenLogConfig(_("invalid line(s) {lines} (without “=”)").format(lines=lines)) from None
    except configparser.Error as exc:
        raise BrokenLogConfig(_("malformed ({error})").format(error=exc.message)) from None
    return parser


def problem(path: Path) -> str | None:
    """Why the file is broken, or None when it is readable (or missing)."""
    try:
        _read(path)
    except BrokenLogConfig as exc:
        return str(exc)
    return None


def missing_entries(path: Path) -> list[str]:
    """Return ``Section.Key`` entries that differ from what the tracker needs."""
    try:
        parser = _read(path)
    except BrokenLogConfig:
        return list(ALL_ENTRIES)
    missing = []
    for section, keys in REQUIRED.items():
        for key, value in keys.items():
            current = parser.get(section, key, fallback=None)
            if current is None or current.strip().lower() != value:
                missing.append(f"{section}.{key}")
    return missing


def is_configured(path: Path) -> bool:
    return not missing_entries(path)


def _free_backup_name(path: Path) -> Path:
    candidate = path.with_name(path.name + ".bak")
    n = 1
    while candidate.exists() or candidate.is_symlink():
        candidate = path.with_name(f"{path.name}.bak{n}")
        n += 1
    return candidate


def ensure(path: Path) -> bool:
    """Write the required entries, keeping all other sections.

    Returns True when the file was changed. A readable file is backed up to
    ``log.config.bak`` once before the first change; a broken file (or a
    folder in its place) is moved to a free ``log.config.bak*`` name and
    replaced by a clean file.
    """
    if is_configured(path):
        return False
    try:
        parser = _read(path)
    except BrokenLogConfig:
        path.rename(_free_backup_name(path))
        parser = _parser()
    else:
        backup = path.with_name(path.name + ".bak")
        if path.exists() and not backup.exists():
            shutil.copy2(path, backup)
    for section, keys in REQUIRED.items():
        if not parser.has_section(section):
            parser.add_section(section)
        for key, value in keys.items():
            parser.set(section, key, value)
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    parser.write(buf, space_around_delimiters=False)
    path.write_text(buf.getvalue(), encoding="utf-8")
    return True

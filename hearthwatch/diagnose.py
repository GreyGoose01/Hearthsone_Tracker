"""Step-by-step check of the setup: game installed -> started once ->
log.config in place -> Power.log written. Each step says what to do next."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from hearthwatch import clientconfig, logconfig, paths
from hearthwatch.i18n import _
from hearthwatch.logwatcher import newest_power_log

OK, WARN, ERROR = "ok", "warn", "error"
SYMBOLS = {OK: "✓", WARN: "!", ERROR: "✗"}


@dataclass
class Check:
    key: str
    title: str
    status: str
    detail: str = ""
    hint: str = ""
    action: str = ""  # "setup-logs" when the tracker can fix it itself
    banner: str = ""  # short text for the GUI banner (defaults to the hint)


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def short(path: Path | str) -> str:
    """Show paths below the home directory as ``~/...``."""
    text = str(path)
    home = str(paths._home())
    if home and home != "/" and (text == home or text.startswith(home + "/")):
        return "~" + text[len(home):]
    return text


def _when(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime(_("%Y-%m-%d %H:%M"))


def _sessions(logs_dir: Path) -> list[Path]:
    if not logs_dir.is_dir():
        return []
    return sorted((p for p in logs_dir.iterdir() if p.is_dir()), key=_mtime)


def run_checks() -> list[Check]:
    checks: list[Check] = []

    # 1. game installed by the launcher
    game_dir = paths.find_game_dir()
    flatpak = paths.flatpak_root() in game_dir.parents
    kind = _("Flatpak version") if flatpak else _("DEB/AppImage version")
    title = _("Hearthstone installed")
    if (game_dir / "Bin" / "Hearthstone.x86_64").exists():
        checks.append(Check("game", title, OK,
                            _("{path} ({kind} of the launcher)").format(path=short(game_dir), kind=kind)))
    elif (game_dir / "Logs").is_dir():
        checks.append(Check("game", title, OK, _("{path} (log folder found)").format(path=short(game_dir))))
    else:
        checks.append(Check(
            "game", title, ERROR, _("Not found, looked in {path} and others").format(path=short(game_dir)),
            _("Install Hearthstone in the launcher (hearthstone-linux-gui) with “Install / Update”. "
              "If it lives somewhere else, set HEARTHWATCH_GAME_DIR=/path/to/game."),
        ))

    # 2. game started at least once (it then writes options.txt)
    settings, confirmed = paths.settings_dir()
    title = _("Game settings folder")
    if confirmed:
        checks.append(Check("started", title, OK, _("{path} (options.txt found)").format(path=short(settings))))
    else:
        checks.append(Check(
            "started", title, WARN,
            _("No options.txt yet – probably {path}").format(path=short(settings)),
            _("Start Hearthstone once from the launcher and quit it again; "
              "then Hearthwatch knows for sure where log.config belongs."),
        ))

    # 3. log.config next to options.txt
    cfg = settings / "log.config"
    missing = logconfig.missing_entries(cfg)
    broken = logconfig.problem(cfg)
    if broken:
        checks.append(Check(
            "logconfig", "log.config", ERROR,
            _("{path} is broken: {problem}").format(path=short(cfg), problem=broken),
            _("“Set up” or “hearthwatch --setup-logs” renames the old file to log.config.bak "
              "and writes a new one; then restart Hearthstone."),
            action="setup-logs",
            banner=_("log.config is broken ({problem}). “Set up” replaces it and keeps a backup.").format(
                problem=broken),
        ))
    elif not missing:
        checks.append(Check("logconfig", "log.config", OK,
                            _("{path} (set up {when})").format(path=short(cfg), when=_when(_mtime(cfg)))))
    else:
        if not cfg.exists():
            detail = _("{path} is missing").format(path=short(cfg))
        else:
            detail = _("{path}: incomplete ({entries})").format(path=short(cfg), entries=", ".join(missing))
        checks.append(Check(
            "logconfig", "log.config", ERROR, detail,
            _("Create it with “Set up” or “hearthwatch --setup-logs”, then restart Hearthstone."),
            action="setup-logs",
            banner=(_("log.config is missing – without it Hearthstone writes no Power.log.") if not cfg.exists()
                    else _("log.config is incomplete – without it Hearthstone writes no Power.log.")),
        ))

    # 4. log size limit lifted in client.config (else Power.log stops mid-game)
    st = clientconfig.status(game_dir)
    client, overrides = st["client"], st["overrides"]
    title = _("Log size limit")
    if st["client_ok"]:
        checks.append(Check("clientconfig", title, OK, f"{short(client)} ({clientconfig.LINE})"))
    elif st["client_exists"]:
        if st["overrides_ok"]:
            detail = _("{path}: {line} is missing – it is in {overrides} though; "
                       "the launcher probably rewrote client.config").format(
                path=short(client), line=clientconfig.LINE, overrides=short(overrides))
        else:
            detail = _("{path}: {line} is missing (not in {overrides} either)").format(
                path=short(client), line=clientconfig.LINE, overrides=short(overrides))
        checks.append(Check(
            "clientconfig", title, ERROR, detail,
            _("Otherwise Hearthstone stops writing the Power.log in the middle of a game. "
              "“Set up” or “hearthwatch --setup-logs” adds the line; then restart Hearthstone."),
            action="setup-logs",
            banner=_("Log size limit active – Hearthstone would stop logging in the middle of a game."),
        ))
    else:
        in_overrides = _("yes") if st["overrides_ok"] else _("no")
        checks.append(Check(
            "clientconfig", title, WARN,
            _("{path} is missing (game not installed?); in launcher overrides: {state}").format(
                path=short(client), state=in_overrides),
            _("Run “hearthwatch --setup-logs” after the launcher installed the game."),
        ))

    # 5. Power.log written by the current session, with details (Verbose)
    checks.append(_power_log_check(game_dir / "Logs", cfg, bool(missing)))
    return checks


def restart_hint() -> str:
    return _("Quit Hearthstone completely and start it again from the launcher – "
             "log.config is only read when the game starts.")


def play_hint() -> str:
    return _("Start a game – the Power.log only appears in a match. If it is still missing afterwards, "
             "the game does not read log.config at this place: please report the output of "
             "“hearthwatch --check”.")


def _power_log_check(logs_dir: Path, cfg: Path, cfg_missing: bool) -> Check:
    title = "Power.log"
    power = newest_power_log(logs_dir)
    sessions = _sessions(logs_dir)
    cfg_time = _mtime(cfg)

    if power is None:
        if cfg_missing:
            return Check("powerlog", title, WARN, _("None yet – set up log.config first."))
        newer = [s for s in sessions if _mtime(s) > cfg_time]
        if newer:
            return Check(
                "powerlog", title, WARN,
                _("Hearthstone ran since the setup ({session}), but there is no Power.log yet.").format(
                    session=newer[-1].name),
                play_hint(),
            )
        return Check(
            "powerlog", title, WARN,
            _("Hearthstone has not been started since log.config was set up."), restart_hint(),
        )

    # a Power.log exists - but is it from the latest session?
    latest = sessions[-1] if sessions else None
    if latest is not None and power.parent != logs_dir and power.parent != latest:
        hint = play_hint() if _mtime(latest) > cfg_time else restart_hint()
        return Check(
            "powerlog", title, WARN,
            _("The current session ({session}) has no Power.log yet; the last one is from {old}.").format(
                session=latest.name, old=power.parent.name),
            hint,
        )

    info = inspect_power_log(power)
    size_kb = max(1, (info.size + 1023) // 1024)
    where = f"{short(power)} ({size_kb} KB, {_when(_mtime(power))})"
    if info.full_entities and not info.initial_tags:
        return Check(
            "powerlog", title, WARN,
            _("{where} – without details (Verbose off): boards and minions cannot be read.").format(where=where),
            _("Check log.config (Verbose=true). ") + restart_hint(),
        )
    return Check("powerlog", title, OK, where)


@dataclass
class PowerLogInfo:
    size: int
    power_lines: int
    full_entities: int
    initial_tags: int


def inspect_power_log(path: Path, max_bytes: int = 4 * 1024 * 1024) -> PowerLogInfo:
    """Count a few line types at the start of a Power.log (cheap sanity check)."""
    power_lines = full_entities = initial_tags = 0
    try:
        size = path.stat().st_size
        with path.open(encoding="utf-8", errors="replace") as fh:
            data = fh.read(max_bytes)
    except OSError:
        return PowerLogInfo(0, 0, 0, 0)
    for line in data.splitlines():
        marker = line.find("DebugPrintPower() -")
        if marker < 0:
            continue
        power_lines += 1
        rest = line[marker + len("DebugPrintPower() -"):].lstrip()
        if rest.startswith("FULL_ENTITY"):
            full_entities += 1
        elif rest.startswith("tag="):
            initial_tags += 1
    return PowerLogInfo(size, power_lines, full_entities, initial_tags)


def first_problem(checks: list[Check]) -> Check | None:
    for status in (ERROR, WARN):
        for c in checks:
            if c.status == status:
                return c
    return None


def format_checks(checks: list[Check]) -> str:
    lines = []
    for c in checks:
        lines.append(f"{SYMBOLS[c.status]} {c.title}: {c.detail}")
        if c.hint:
            lines.append(f"    → {c.hint}")
    return "\n".join(lines)

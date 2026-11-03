"""Command line entry point: ``hearthwatch`` starts the GUI, options run tools."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from hearthwatch import __version__, i18n, logconfig, paths
from hearthwatch.i18n import N_, _

RESTART = N_("Next step: quit Hearthstone completely and start it again from the launcher.")


def _cmd_check() -> int:
    from hearthwatch.diagnose import first_problem, format_checks, run_checks

    checks = run_checks()
    print(format_checks(checks))
    print("\n" + _("Database: {path}").format(path=paths.tracker_paths().database))
    print(_("Log file: {path}").format(path=paths.log_file()))
    problem = first_problem(checks)
    if problem is None:
        print("\n" + _("All set – Hearthwatch can read along."))
        return 0
    print("\n" + _("Next step: {hint}").format(hint=problem.hint or problem.detail))
    return 1 if problem.status == "error" else 0


def _cmd_setup_logs() -> int:
    settings, confirmed = paths.settings_dir()
    path = settings / "log.config"
    broken = logconfig.problem(path)
    try:
        changed = logconfig.ensure(path)
    except OSError as exc:
        print(_("Could not write {path}: {error}").format(path=path, error=exc), file=sys.stderr)
        return 1
    where = (_("next to the game's options.txt") if confirmed
             else _("at the default place (game never started?)"))
    if changed:
        print(_("log.config created: {path}").format(path=path) + f"\n  ({where})")
        if broken:
            backups = sorted(p.name for p in path.parent.glob("log.config.bak*"))
            print("  " + _("The old file was broken ({problem}); it is kept next to it as {backup}").format(
                problem=broken, backup=backups[-1] if backups else "log.config.bak"))
        print(_(RESTART))
    else:
        print(_("log.config is already set up: {path}").format(path=path))
    if not confirmed:
        print(_("Note: run “hearthwatch --check” after the first game start – if options.txt "
                "is somewhere else, just run --setup-logs again."))

    from hearthwatch import clientconfig

    try:
        updated = clientconfig.ensure()
    except OSError as exc:
        print(_("Could not lift the log size limit: {error}").format(error=exc), file=sys.stderr)
        return 1
    for file in updated:
        print(_("Log size limit lifted ({line}): {path}").format(line=clientconfig.LINE, path=file))
    if updated:
        print(_(RESTART))
    elif clientconfig.is_configured():
        print(_("Log size limit is already lifted: {path}").format(path=clientconfig.client_config_path()))
    else:
        print(_("client.config is missing (game not installed?) – run “hearthwatch --setup-logs” "
                "again after the installation."))
    return 0


def _load_cards(offline: bool):
    from hearthwatch.cards import CardDB

    tp = paths.tracker_paths()
    tp.ensure()
    return CardDB.load(tp.cache_dir, locale=i18n.card_locale(), download=not offline)


def _cmd_replay(file: Path, simulate: bool, offline: bool, details: bool = False) -> int:
    from hearthwatch.bg.tracker import BattlegroundsTracker
    from hearthwatch.cards import tribe_name
    from hearthwatch.power.game_state import GameState
    from hearthwatch.sim.montecarlo import simulate_combat

    cards = _load_cards(offline)
    predictions: dict[int, str] = {}  # round -> most likely simulated outcome
    hits: list[bool] = []

    def on_combat(c):
        def fmt(ms):
            return ", ".join(
                f"{m.name} {m.attack}/{m.health}" + (f" [{'; '.join(m.buffs)}]" if m.buffs else "")
                for m in ms
            ) or "-"

        print("\n" + _("[Round {round}] Combat against {hero} (tier {tier})").format(
            round=c.round, hero=c.opponent.hero_name, tier=c.opponent.tavern_tier))
        print("  " + _("You      : {board}").format(board=fmt(c.player.minions)))
        print("  " + _("Opponent : {board}").format(board=fmt(c.opponent.minions)))
        if details and tracker.last_details:
            print(tracker.last_details)
        if simulate:
            r = simulate_combat(c, en_names=cards.en_name, runs=1000, seed=1)
            predictions[c.round] = max(
                (("win", r.win), ("draw", r.draw), ("loss", r.loss)), key=lambda x: x[1]
            )[0]
            line = "  " + _("Simulation: win {win:.0%}  draw {draw:.0%}  loss {loss:.0%}").format(
                win=r.win, draw=r.draw, loss=r.loss)
            if r.unsupported:
                line += "  " + _("(not modelled: {cards})").format(cards=", ".join(r.unsupported))
            print(line)

    def on_result(c):
        print("  " + _("Actual: {result}").format(result=c.actual.text()))
        if c.round in predictions:
            hits.append(predictions.pop(c.round) == c.actual.result)

    def on_end(r):
        print("\n== " + _("Game over: {hero} – place {place}, round {round}, tier {tier}, types: {types}").format(
            hero=r.hero_name, place=r.placement, round=r.rounds, tier=r.tavern_tier,
            types=", ".join(tribe_name(t) for t in r.tribes) or "?"))

    tracker = BattlegroundsTracker(
        cards, on_combat=on_combat, on_match_end=on_end, on_combat_result=on_result
    )
    tracker.source = str(file)
    tracker.collect_details = details
    game = GameState([tracker])
    with file.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            game.feed_line(line)
    if game.games_started == 0:
        print(_("No games found in this file (is it a Power.log?)."))
    if hits:
        print("\n" + _("Simulator: most likely result matched in {hits} of {total} combats ({rate:.0%}).").format(
            hits=sum(hits), total=len(hits), rate=sum(hits) / len(hits)))
    return 0


def _cmd_import(offline: bool) -> int:
    from hearthwatch.db import MatchDB
    from hearthwatch.service import import_logs

    logs_dir = paths.find_game_dir() / "Logs"
    db = MatchDB(paths.tracker_paths().database)
    n = import_logs(logs_dir, db, _load_cards(offline))
    print(_("Imported {count} new games from {path}.").format(count=n, path=logs_dir))
    return 0


def _setup_logging(verbose: bool, to_file: bool) -> None:
    """Console: warnings (all with -v). GUI: also INFO and errors to a file."""
    root = logging.getLogger()
    for h in [h for h in root.handlers if getattr(h, "_hearthwatch", False)]:
        root.removeHandler(h)
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG if verbose else logging.WARNING)
    console.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    console._hearthwatch = True
    root.addHandler(console)
    if not to_file:
        return
    from logging.handlers import RotatingFileHandler

    path = paths.log_file()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(path, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    except OSError:
        return
    handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    handler._hearthwatch = True
    root.addHandler(handler)
    logging.getLogger(__name__).info("hearthwatch %s started", __version__)


def _language_from_args(argv: list[str] | None) -> str | None:
    """Pick ``--lang`` before argparse runs, so ``--help`` is translated too."""
    args = sys.argv[1:] if argv is None else argv
    for i, arg in enumerate(args):
        for flag in ("--lang", "--locale"):
            if arg == flag and i + 1 < len(args):
                return args[i + 1]
            if arg.startswith(flag + "="):
                return arg.split("=", 1)[1]
    return None


def main(argv: list[str] | None = None) -> int:
    moved = paths.migrate_legacy_dirs()
    from hearthwatch import settings as settings_mod

    lang_arg = _language_from_args(argv)
    i18n.set_language(lang_arg or settings_mod.load().language)

    ap = argparse.ArgumentParser(
        prog="hearthwatch",
        description=_("Hearthstone Battlegrounds tracker for hearthstone-linux-gui"),
    )
    ap.add_argument("--version", action="version", version=f"hearthwatch {__version__}")
    ap.add_argument("--check", action="store_true", help=_("check the setup and show the next step"))
    ap.add_argument("--setup-logs", action="store_true",
                    help=_("set up Hearthstone's logging (log.config, log size limit)"))
    ap.add_argument("--replay", type=Path, metavar="POWER_LOG", help=_("read a Power.log (without GUI)"))
    ap.add_argument("--simulate", action="store_true",
                    help=_("with --replay: simulate combats and compare with the result"))
    ap.add_argument("--details", action="store_true",
                    help=_("with --replay: show the game objects, stats and buffs of every combat"))
    ap.add_argument("--import-logs", action="store_true", help=_("add games from existing logs to the history"))
    ap.add_argument("--offline", action="store_true", help=_("do not download card data or images"))
    ap.add_argument("--lang", choices=("auto", "en", "de"), default=None,
                    help=_("language of the interface and card names (default: settings, else system)"))
    ap.add_argument("--locale", dest="lang", choices=("deDE", "enUS"), help=argparse.SUPPRESS)
    ap.add_argument("-v", "--verbose", action="store_true", help=_("more messages"))
    args = ap.parse_args(argv)
    if args.lang:
        i18n.set_language(args.lang)
    gui = not (args.check or args.setup_logs or args.replay or args.import_logs)
    _setup_logging(args.verbose, to_file=gui)
    for path in moved:
        logging.getLogger(__name__).info("moved old bgtracker data to %s", path)

    if args.check:
        return _cmd_check()
    if args.setup_logs:
        return _cmd_setup_logs()
    if args.replay:
        return _cmd_replay(args.replay, args.simulate, args.offline, args.details)
    if args.import_logs:
        return _cmd_import(args.offline)

    try:
        from hearthwatch.versions import runtime_problems

        too_old = runtime_problems()
        if too_old:
            print("\n".join(too_old), file=sys.stderr)
            return 1
        from hearthwatch.ui.app import run
    except (ImportError, ValueError) as exc:
        print(
            _("GTK 4 / libadwaita could not be loaded ({error}).").format(error=exc)
            + "\n" + _("Install them with: {command}").format(
                command="sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1"),
            file=sys.stderr,
        )
        return 1
    return run(language=args.lang, offline=args.offline)

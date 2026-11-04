"""Combat odds from AutoTavern (https://github.com/MCG-NJU/AutoTavern, MIT).

AutoTavern's TavernGym is a Rust simulator of the whole Battlegrounds rule set
(all tavern minions, heroes, trinkets ...). We only use its combat preview: put
both boards on two seats of a game, let it fight ``runs`` times and read the
result. Measured on real games it predicts far better than the small built-in
simulator, which stays as the fallback.

Where it comes from, first match wins:

* ``hearthwatch._vendor.taverngym_core._core`` - the compiled module shipped in
  the .deb (only the extension, no numpy needed),
* ``taverngym._core`` - a normal ``pip install`` of AutoTavern.

Without either, or for cards it does not know, :func:`simulate_combat` returns
None and the caller uses the built-in simulator.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any

from hearthwatch.bg.models import CombatSnapshot, Minion
from hearthwatch.cards import hero_base_id

log = logging.getLogger(__name__)

# no damage cap inside AutoTavern: we apply the cap the game itself reports
CONFIG = json.dumps({"damage_caps": []})
MAX_RUNS = 5000  # AutoTavern clamps previews to this
HEALTH = 999  # both seats; lethal is judged against the real health afterwards
HERO_CHOICES = 4  # pending choices to resolve after picking heroes (Finley, Denathrius ...)

_lock = threading.Lock()
_core: Any = None
_template: Any = None  # a game in its first recruit phase, copied for every preview
_failed = False


def _load_core():
    global _core, _failed
    if _failed:
        return None
    if _core is not None:
        return _core
    for name in ("hearthwatch._vendor.taverngym_core._core", "taverngym._core"):
        try:
            module = __import__(name, fromlist=["Game"])
            module.Game  # noqa: B018
        except (ImportError, AttributeError):
            continue
        _core = module
        log.info("combat simulator: AutoTavern %s (%s)", getattr(module, "game_version", lambda: "?")(), name)
        return _core
    _failed = True
    log.info("combat simulator: built-in (AutoTavern not installed)")
    return None


def available() -> bool:
    return _load_core() is not None


def version() -> str:
    core = _load_core()
    return core.game_version() if core is not None and hasattr(core, "game_version") else ""


def _recruit_game(core) -> Any:
    """A fresh game in round 1: every seat has picked its first hero offer."""
    g = core.Game(1, CONFIG)
    players = g.num_players() if callable(g.num_players) else g.num_players
    for p in range(players):
        g.step(p, json.loads(g.view(p))["actions"]["CHOOSE"])
    for p in range(players):
        for _ in range(HERO_CHOICES):
            view = json.loads(g.view(p))
            if view["me"]["pending"] is None:
                break
            g.step(p, view["actions"]["CHOOSE"])
    return g


def _keywords(m: Minion) -> list[str]:
    kw = []
    if m.taunt:
        kw.append("TAUNT")
    if m.divine_shield:
        kw.append("DIVINE_SHIELD")
    if m.reborn:
        kw.append("REBORN")
    if m.venomous:
        kw.append("VENOMOUS")
    if m.windfury == 1:
        kw.append("WINDFURY")
    elif m.windfury >= 3:
        kw.append("MEGA_WINDFURY")
    if m.cleave:
        kw.append("CLEAVE")
    return kw


BEETLE_BASE = (2, 2)  # a Beetle without any bonus


class UnknownCard(Exception):
    pass


def _setup(game, snapshot: CombatSnapshot) -> None:
    def cmd(**c):
        return json.loads(game.debug(json.dumps(c)))

    cmd(cmd="set_turn", turn=max(snapshot.round, 1))
    for seat, board in ((0, snapshot.player), (1, snapshot.opponent)):
        for zone in ("board", "hand"):
            cmd(cmd="clear_zone", p=seat, zone=zone)
        if board.hero_card_id:
            try:
                cmd(cmd="set_hero", p=seat, hero=hero_base_id(board.hero_card_id))
            except ValueError:
                pass  # an unknown hero only loses its hero power
        # plenty of health: we want the raw damage and judge lethal ourselves
        cmd(cmd="set_player", p=seat, tier=max(board.tavern_tier, 1), health=HEALTH, armor=0)
        # "this game" strength (before the minions, which take it as already applied)
        stats = {}
        if board.beetle != (0, 0):
            stats.update(beetle_atk=board.beetle[0] - BEETLE_BASE[0], beetle_hp=board.beetle[1] - BEETLE_BASE[1])
        if board.undead_attack:
            stats["undead_atk"] = board.undead_attack
        if board.lobster_bonus:
            stats["lobster_bonus"] = board.lobster_bonus
        if stats:
            try:
                cmd(cmd="set_stats", p=seat, stats=stats)
            except ValueError:
                log.debug("this AutoTavern build cannot set %s", sorted(stats))
        for index, m in enumerate(board.minions):
            for card, golden in ((m.card_id, m.golden), (m.card_id.removesuffix("_G"), True)):
                try:
                    cmd(cmd="add_minion", p=seat, zone="board", card=card, golden=golden)
                    break
                except ValueError:
                    continue
            else:
                raise UnknownCard(m.card_id)
            # the log's values already contain every buff: take them as they are
            cmd(cmd="edit_minion", p=seat, zone="board", index=index,
                atk=m.attack, hp=max(m.health, 1), keywords=_keywords(m))


def simulate_combat(snapshot: CombatSnapshot, player_health: int | None = None,
                    runs: int = 2000, damage_cap: int | None = None):
    """Odds for ``snapshot`` from AutoTavern, or None if it cannot simulate it."""
    from hearthwatch.sim.montecarlo import SimResult

    core = _load_core()
    if core is None:
        return None
    cap = snapshot.damage_cap if damage_cap is None else damage_cap
    global _template, _failed
    with _lock:
        if _template is None:
            try:
                _template = _recruit_game(core)
            except Exception:
                log.exception("AutoTavern could not start a game - using the built-in simulator")
                _failed = True
                return None
        game = _template.copy()
    try:
        _setup(game, snapshot)
        result = json.loads(game.debug(json.dumps(
            {"cmd": "combat_preview", "a": 0, "b": 1, "n": max(1, min(runs, MAX_RUNS)), "details": True})))
    except UnknownCard as exc:
        log.info("AutoTavern does not know %s - using the built-in simulator", exc)
        return None
    except Exception:  # never let the simulator break the tracker
        log.exception("AutoTavern failed - using the built-in simulator")
        return None

    trials = result.get("trials") or []
    n = len(trials) or 1
    wins = draws = losses = lethal = 0
    dealt = taken = 0
    for t in trials:
        winner = t.get("winner")
        if winner == 0:
            wins += 1
            dealt += min(t.get("damage_dealt", 0), cap) if cap else t.get("damage_dealt", 0)
        elif winner == 1:
            losses += 1
            damage = min(t.get("damage_taken", 0), cap) if cap else t.get("damage_taken", 0)
            taken += damage
            if player_health is not None and damage >= player_health:
                lethal += 1
        else:
            draws += 1
    return SimResult(
        runs=len(trials),
        win=wins / n,
        draw=draws / n,
        loss=losses / n,
        avg_damage_dealt=dealt / wins if wins else 0.0,
        avg_damage_taken=taken / losses if losses else 0.0,
        lethal_risk=lethal / n,
        engine="autotavern",
    )

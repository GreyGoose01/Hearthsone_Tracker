"""Run many randomized combats and aggregate the odds."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Callable

from hearthwatch.bg.models import CombatSnapshot, Minion
from hearthwatch.sim.effects import DEATHRATTLES
from hearthwatch.sim.engine import simulate_once


@dataclass
class SimResult:
    runs: int
    win: float
    draw: float
    loss: float
    avg_damage_dealt: float  # average over wins
    avg_damage_taken: float  # average over losses
    lethal_risk: float  # share of runs in which the player would die
    unsupported: list[str] = field(default_factory=list)

    @property
    def exact(self) -> bool:
        return not self.unsupported


def simulate(
    player: list[Minion],
    opponent: list[Minion],
    player_tier: int,
    opponent_tier: int,
    runs: int = 2000,
    seed: int | None = None,
    time_budget: float = 2.0,
    player_health: int | None = None,
    en_names: Callable[[str], str] | None = None,
    damage_cap: int = 0,
) -> SimResult:
    """Monte Carlo over random targets/order. ``damage_cap`` (> 0) limits the hero
    damage of one combat, as the game does in the early rounds."""
    rng = random.Random(seed)
    wins = draws = losses = 0
    dealt = taken = lethal = 0
    deadline = time.monotonic() + time_budget
    done = 0
    for done in range(1, runs + 1):
        out = simulate_once(player, opponent, player_tier, opponent_tier, rng,
                            DEATHRATTLES, en_names)
        damage = min(out.damage, damage_cap) if damage_cap > 0 else out.damage
        if out.result == "win":
            wins += 1
            dealt += damage
        elif out.result == "loss":
            losses += 1
            taken += damage
            if player_health is not None and damage >= player_health:
                lethal += 1
        else:
            draws += 1
        if done % 100 == 0 and time.monotonic() > deadline:
            break

    def name_of(m: Minion) -> str:
        return en_names(m.card_id) if en_names else m.name

    unsupported = sorted({
        m.name or m.card_id for m in player + opponent
        if m.deathrattle and name_of(m) not in DEATHRATTLES
    })
    return SimResult(
        runs=done,
        win=wins / done,
        draw=draws / done,
        loss=losses / done,
        avg_damage_dealt=dealt / wins if wins else 0.0,
        avg_damage_taken=taken / losses if losses else 0.0,
        lethal_risk=lethal / done,
        unsupported=unsupported,
    )


def simulate_combat(snapshot: CombatSnapshot, player_health: int | None = None,
                    en_names: Callable[[str], str] | None = None, **kw) -> SimResult:
    return simulate(
        snapshot.player.minions,
        snapshot.opponent.minions,
        snapshot.player.tavern_tier,
        snapshot.opponent.tavern_tier,
        player_health=player_health,
        en_names=en_names,
        damage_cap=getattr(snapshot, "damage_cap", 0),
        **kw,
    )

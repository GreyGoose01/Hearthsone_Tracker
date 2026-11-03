"""A small Battlegrounds combat engine.

The tracker snapshots both warbands right before the first attack, i.e.
*after* start-of-combat effects already happened in the real game. The
engine therefore models:

* attack order (bigger warband starts, ties random; left-to-right pointer
  that skips minions summoned to the left of it),
* targeting (random, Taunt first), simultaneous damage, Cleave,
* Divine Shield, Venomous/Poisonous, Windfury/Mega-Windfury, Reborn,
* deathrattles registered in :mod:`hearthwatch.sim.effects`,
* hero damage = winner's tavern tier + tiers of surviving minions.

Not modelled: auras that end when their source dies, Avenge, "after a
friendly minion ..." triggers, hero powers, trinkets, quests. Minions with
an unmodelled deathrattle are reported so the UI can flag the result.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field, replace
from typing import Callable

from hearthwatch.bg.models import Minion

MAX_BOARD = 7
MAX_STEPS = 500  # guards against endless loops (e.g. 0-attack stalemates)


@dataclass
class Unit:
    """A minion during simulation (mutable copy of :class:`Minion`)."""

    card_id: str
    name: str
    attack: int
    health: int
    golden: bool = False
    taunt: bool = False
    divine_shield: bool = False
    reborn: bool = False
    venomous: bool = False
    windfury: int = 0
    cleave: bool = False
    deathrattle: bool = False
    tribes: tuple[str, ...] = ()
    tech_level: int = 1
    en_name: str = ""

    @classmethod
    def from_minion(cls, m: Minion, en_name: str = "") -> "Unit":
        return cls(
            card_id=m.card_id, name=m.name, attack=m.attack, health=m.health,
            golden=m.golden, taunt=m.taunt, divine_shield=m.divine_shield,
            reborn=m.reborn, venomous=m.venomous, windfury=m.windfury,
            cleave=m.cleave, deathrattle=m.deathrattle, tribes=m.tribes,
            tech_level=m.tech_level, en_name=en_name or m.name,
        )

    @property
    def dead(self) -> bool:
        return self.health <= 0


@dataclass
class Side:
    units: list[Unit]
    tier: int
    pointer: int = 0

    def remove(self, index: int) -> Unit:
        unit = self.units.pop(index)
        if index < self.pointer:
            self.pointer -= 1
        return unit

    def insert(self, index: int, unit: Unit) -> bool:
        if len(self.units) >= MAX_BOARD:
            return False
        index = max(0, min(index, len(self.units)))
        self.units.insert(index, unit)
        if index < self.pointer:
            self.pointer += 1
        return True

    def next_attacker(self) -> int | None:
        n = len(self.units)
        if n == 0:
            return None
        if self.pointer >= n:
            self.pointer = 0
        for k in range(n):
            i = (self.pointer + k) % n
            if self.units[i].attack > 0:
                return i
        return None


DeathrattleFn = Callable[["Combat", Side, int, Unit], None]


@dataclass
class Outcome:
    result: str  # "win" | "loss" | "draw" (from the player's perspective)
    damage: int  # damage dealt to the loser's hero


@dataclass
class Combat:
    player: Side
    opponent: Side
    rng: random.Random
    deathrattles: dict[str, DeathrattleFn] = field(default_factory=dict)

    def enemy_of(self, side: Side) -> Side:
        return self.opponent if side is self.player else self.player

    # -- damage ------------------------------------------------------------
    def deal(self, source: Unit | None, target: Unit, amount: int) -> None:
        if amount <= 0 or target.dead:
            return
        if target.divine_shield:
            target.divine_shield = False
            return
        target.health -= amount
        if source is not None and source.venomous:
            target.health = min(target.health, 0)

    def summon(self, side: Side, index: int, unit: Unit) -> bool:
        return side.insert(index, unit)

    # -- deaths --------------------------------------------------------------
    def resolve_deaths(self, first: Side) -> None:
        for _ in range(50):
            pending = []
            for side in (first, self.enemy_of(first)):
                for idx, unit in enumerate(side.units):
                    if unit.dead:
                        pending.append((side, unit))
            if not pending:
                return
            # remove first (positions are taken at removal time)
            removed = []
            for side, unit in pending:
                idx = next(i for i, u in enumerate(side.units) if u is unit)
                side.remove(idx)
                removed.append((side, idx, unit))
            for side, idx, unit in removed:
                fn = self.deathrattles.get(unit.en_name) if unit.deathrattle else None
                if fn is not None:
                    fn(self, side, idx, unit)
                if unit.reborn:
                    back = replace(unit, health=1, reborn=False)
                    self.summon(side, idx, back)

    # -- attacks -------------------------------------------------------------
    def attack(self, side: Side, index: int) -> None:
        attacker = side.units[index]
        enemy = self.enemy_of(side)
        targets = [u for u in enemy.units if not u.dead]
        if not targets:
            return
        taunts = [u for u in targets if u.taunt]
        target = self.rng.choice(taunts or targets)
        t_index = enemy.units.index(target)
        neighbours = []
        if attacker.cleave:
            if t_index > 0:
                neighbours.append(enemy.units[t_index - 1])
            if t_index + 1 < len(enemy.units):
                neighbours.append(enemy.units[t_index + 1])
        atk, def_atk = attacker.attack, target.attack
        self.deal(attacker, target, atk)
        for n in neighbours:
            self.deal(attacker, n, atk)
        self.deal(target, attacker, def_atk)
        self.resolve_deaths(side)

    def run(self) -> Outcome:
        p, o = self.player, self.opponent
        if len(p.units) > len(o.units):
            current = p
        elif len(o.units) > len(p.units):
            current = o
        else:
            current = p if self.rng.random() < 0.5 else o
        idle = 0
        for _ in range(MAX_STEPS):
            if not p.units or not o.units:
                break
            index = current.next_attacker()
            if index is None:
                idle += 1
                if idle >= 2:
                    break
                current = self.enemy_of(current)
                continue
            idle = 0
            attacker = current.units[index]
            current.pointer = index + 1
            attacks = 1 + (1 if attacker.windfury == 1 else 3 if attacker.windfury >= 3 else 0)
            for _ in range(attacks):
                if attacker not in current.units or attacker.dead:
                    break
                if not self.enemy_of(current).units:
                    break
                self.attack(current, current.units.index(attacker))
            current = self.enemy_of(current)
        return self._outcome()

    def _outcome(self) -> Outcome:
        p, o = self.player, self.opponent
        if p.units and not o.units:
            return Outcome("win", p.tier + sum(u.tech_level for u in p.units))
        if o.units and not p.units:
            return Outcome("loss", o.tier + sum(u.tech_level for u in o.units))
        return Outcome("draw", 0)


def simulate_once(
    player: list[Minion],
    opponent: list[Minion],
    player_tier: int,
    opponent_tier: int,
    rng: random.Random,
    deathrattles: dict[str, DeathrattleFn] | None = None,
    en_names: Callable[[str], str] | None = None,
) -> Outcome:
    def units(ms: list[Minion]) -> list[Unit]:
        return [Unit.from_minion(m, en_names(m.card_id) if en_names else "") for m in ms]

    combat = Combat(
        player=Side(units(player), player_tier),
        opponent=Side(units(opponent), opponent_tier),
        rng=rng,
        deathrattles=deathrattles or {},
    )
    return combat.run()

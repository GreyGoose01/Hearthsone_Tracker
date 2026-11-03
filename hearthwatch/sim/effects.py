"""Deathrattle effects known to the simulator, keyed by English card name.

Battlegrounds cards are rebalanced often, so the numbers below are a best
effort and easy to adjust: every entry is a tiny function. Golden minions
double the effect. Add new cards with :func:`register`.
"""

from __future__ import annotations

from hearthwatch.sim.engine import Combat, DeathrattleFn, Side, Unit

DEATHRATTLES: dict[str, DeathrattleFn] = {}


def register(name: str):
    def wrap(fn: DeathrattleFn) -> DeathrattleFn:
        DEATHRATTLES[name] = fn
        return fn

    return wrap


def _mult(unit: Unit) -> int:
    return 2 if unit.golden else 1


def _token(name: str, attack: int, health: int, tribes: tuple[str, ...] = (), **kw) -> Unit:
    return Unit(card_id="", name=name, en_name=name, attack=attack, health=health,
                tribes=tribes, tech_level=1, **kw)


def summon_tokens(name: str, attack: int, health: int, count: int = 1,
                  tribes: tuple[str, ...] = (), **kw) -> DeathrattleFn:
    """Deathrattle: summon ``count`` tokens; golden doubles the stats."""

    def fn(combat: Combat, side: Side, index: int, unit: Unit) -> None:
        m = _mult(unit)
        for i in range(count):
            combat.summon(side, index + i, _token(name, attack * m, health * m, tribes, **kw))

    return fn


for _name, _fn in {
    "Harvest Golem": summon_tokens("Damaged Golem", 2, 1, tribes=("MECHANICAL",)),
    "Imprisoner": summon_tokens("Imp", 1, 1, tribes=("DEMON",)),
    "Scallywag": summon_tokens("Sky Pirate", 1, 1, tribes=("PIRATE",)),
    "Infested Wolf": summon_tokens("Spider", 1, 1, count=2, tribes=("BEAST",)),
    "Mecharoo": summon_tokens("Jo-E Bot", 1, 1, tribes=("MECHANICAL",)),
    "Replicating Menace": summon_tokens("Microbot", 1, 1, count=3, tribes=("MECHANICAL",)),
}.items():
    DEATHRATTLES[_name] = _fn


@register("Rat Pack")
def _rat_pack(combat: Combat, side: Side, index: int, unit: Unit) -> None:
    m = _mult(unit)
    for i in range(max(0, unit.attack)):
        if not combat.summon(side, index + i, _token("Rat", m, m, ("BEAST",))):
            break


@register("Kaboom Bot")
def _kaboom_bot(combat: Combat, side: Side, index: int, unit: Unit) -> None:
    enemy = combat.enemy_of(side)
    for _ in range(_mult(unit)):
        alive = [u for u in enemy.units if not u.dead]
        if alive:
            combat.deal(None, combat.rng.choice(alive), 4)


@register("Selfless Hero")
def _selfless_hero(combat: Combat, side: Side, index: int, unit: Unit) -> None:
    for _ in range(_mult(unit)):
        options = [u for u in side.units if not u.dead and not u.divine_shield]
        if options:
            combat.rng.choice(options).divine_shield = True


@register("Spawn of N'Zoth")
def _spawn_of_nzoth(combat: Combat, side: Side, index: int, unit: Unit) -> None:
    m = _mult(unit)
    for u in side.units:
        u.attack += m
        u.health += m


@register("Fiendish Servant")
def _fiendish_servant(combat: Combat, side: Side, index: int, unit: Unit) -> None:
    for _ in range(_mult(unit)):
        alive = [u for u in side.units if not u.dead]
        if alive:
            combat.rng.choice(alive).attack += unit.attack


@register("Unstable Ghoul")
def _unstable_ghoul(combat: Combat, side: Side, index: int, unit: Unit) -> None:
    for _ in range(_mult(unit)):
        for u in list(side.units) + list(combat.enemy_of(side).units):
            combat.deal(None, u, 1)


@register("Goldrinn, the Great Wolf")
def _goldrinn(combat: Combat, side: Side, index: int, unit: Unit) -> None:
    m = _mult(unit)
    for u in side.units:
        if "BEAST" in u.tribes or "ALL" in u.tribes:
            u.attack += 4 * m
            u.health += 4 * m

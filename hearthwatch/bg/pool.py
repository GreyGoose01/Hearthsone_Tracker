"""Which tavern minions can show up in this lobby, grouped by minion type.

Hearthwatch does not read the game's memory, so the lobby's minion types are
derived from the minions seen so far (see ``BattlegroundsTracker``). Until five
types are known, types not seen yet are kept but marked as uncertain.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from hearthwatch.cards import BG_TRIBES, CardDB, CardInfo, tribe_name

NEUTRAL = ""  # group key for minions without a type (and "all types" minions)


@dataclass
class PoolGroup:
    tribe: str  # BG tribe, or NEUTRAL
    available: bool | None  # True: in this lobby, None: not known yet
    cards: list[CardInfo] = field(default_factory=list)

    @property
    def title(self) -> str:
        return tribe_name(self.tribe) if self.tribe else ""


def _tribes(card: CardInfo) -> list[str]:
    return [r for r in card.races if r in BG_TRIBES]


def lobby_minions(cards: CardDB, tribes_seen: list[str] | tuple[str, ...] = (),
                  tribes_banned: list[str] | tuple[str, ...] = (), duos: bool = False) -> list[CardInfo]:
    """Pool minions possible in this lobby (all tiers)."""
    banned = set(tribes_banned)
    out = []
    for c in cards.bg_minions():
        if c.duos_only and not duos:
            continue
        types = _tribes(c)
        if types and banned and all(t in banned for t in types):
            continue
        out.append(c)
    return out


def tiers(minions: list[CardInfo]) -> list[int]:
    return sorted({c.tech_level for c in minions})


def groups(minions: list[CardInfo], tier: int, tribes_seen: list[str] | tuple[str, ...] = (),
           tribes_banned: list[str] | tuple[str, ...] = ()) -> list[PoolGroup]:
    """Minions of one tavern tier, grouped by type (dual types appear twice).

    Order: neutral first, then the types known to be in the lobby, then the
    ones not known yet; cards by name.
    """
    seen, banned = set(tribes_seen), set(tribes_banned)
    by_tribe: dict[str, PoolGroup] = {}
    for c in minions:
        if c.tech_level != tier:
            continue
        types = [t for t in _tribes(c) if t not in banned] or [NEUTRAL]
        for t in types:
            available = True if (t == NEUTRAL or t in seen or banned) else None
            by_tribe.setdefault(t, PoolGroup(t, available)).cards.append(c)
    for g in by_tribe.values():
        g.cards.sort(key=lambda c: c.name.casefold())

    def order(g: PoolGroup) -> tuple:
        return (g.tribe != NEUTRAL, g.available is None, BG_TRIBES.index(g.tribe) if g.tribe in BG_TRIBES else 99)

    return sorted(by_tribe.values(), key=order)

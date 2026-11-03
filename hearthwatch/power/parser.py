"""Turn raw ``Power.log`` lines into small event objects.

Power.log contains the same game twice:

* ``GameState.*`` - written as soon as the server's data arrives. In
  Battlegrounds a whole combat arrives at once, so this runs ahead of the
  screen. Only ``GameState.DebugPrintGame()`` (game type, player names) is
  used from here.
* ``PowerTaskList.DebugPrintPower()`` - written while the client plays the
  data back, in sync with what the player sees. The game state is rebuilt
  from these lines (Hearthstone Deck Tracker does the same).

The line formats follow the long-standing Power.log layout (see HearthSim's
MIT-licensed ``hslog`` for reference). Unknown lines are skipped silently so
new game versions do not break the tracker.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

GAME_STATE = "GameState"
POWER_TASK_LIST = "PowerTaskList"

LINE_RE = re.compile(
    r"^(?:[DWE] )?([\d:.]+) (GameState|PowerTaskList)\.(DebugPrint\w+)\(\) - (.*)$"
)

_E = r"(GameEntity|\[.+?\]|\d+|.+?)"
CREATE_GAME_RE = re.compile(r"^CREATE_GAME$")
GAME_ENTITY_RE = re.compile(r"^GameEntity EntityID=(\d+)")
PLAYER_RE = re.compile(r"^Player EntityID=(\d+) PlayerID=(\d+) GameAccountId=\[hi=(\d+) lo=(\d+)\]")
FULL_ENTITY_CREATE_RE = re.compile(r"^FULL_ENTITY - Creating ID=(\d+) CardID=(\w*)$")
FULL_ENTITY_UPDATE_RE = re.compile(r"^FULL_ENTITY - Updating %s CardID=(\w*)$" % _E)
SHOW_ENTITY_RE = re.compile(r"^SHOW_ENTITY - Updating Entity=%s CardID=(\w*)$" % _E)
CHANGE_ENTITY_RE = re.compile(r"^CHANGE_ENTITY - Updating Entity=%s CardID=(\w*)$" % _E)
HIDE_ENTITY_RE = re.compile(r"^HIDE_ENTITY - Entity=%s tag=(\w+) value=(\w+)$" % _E)
TAG_CHANGE_RE = re.compile(r"^TAG_CHANGE Entity=%s tag=(\w+) value=(-?\w+)" % _E)
BLOCK_START_RE = re.compile(r"^BLOCK_START BlockType=(\w+) Entity=%s EffectCardId=" % _E)
BLOCK_END_RE = re.compile(r"^BLOCK_END$")
INITIAL_TAG_RE = re.compile(r"^tag=(\w+) value=(-?\w+)$")
GAME_META_PLAYER_RE = re.compile(r"^PlayerID=(\d+), PlayerName=(.*)$")
GAME_META_KV_RE = re.compile(r"^(\w+)=(.*)$")
ENTITY_ID_RE = re.compile(r"\bid=(\d+)")


def parse_value(value: str) -> int | str:
    """Tag values are ints or enum names (``PLAY``, ``MINION`` ...)."""
    try:
        return int(value)
    except ValueError:
        return value


@dataclass(frozen=True)
class CreateGame:
    ts: str


@dataclass(frozen=True)
class GameEntityDef:
    ts: str
    entity_id: int


@dataclass(frozen=True)
class PlayerDef:
    ts: str
    entity_id: int
    player_id: int
    account_hi: int
    account_lo: int


@dataclass(frozen=True)
class FullEntity:
    ts: str
    entity: str  # id as text for "Creating", entity reference for "Updating"
    card_id: str


@dataclass(frozen=True)
class ShowEntity:
    ts: str
    entity: str
    card_id: str


@dataclass(frozen=True)
class ChangeEntity:
    ts: str
    entity: str
    card_id: str


@dataclass(frozen=True)
class HideEntity:
    ts: str
    entity: str
    tag: str
    value: int | str


@dataclass(frozen=True)
class InitialTag:
    ts: str
    tag: str
    value: int | str


@dataclass(frozen=True)
class TagChange:
    ts: str
    entity: str
    tag: str
    value: int | str


@dataclass(frozen=True)
class BlockStart:
    ts: str
    block_type: str
    entity: str


@dataclass(frozen=True)
class BlockEnd:
    ts: str


@dataclass(frozen=True)
class GamePlayerName:
    ts: str
    player_id: int
    name: str


@dataclass(frozen=True)
class GameMeta:
    ts: str
    key: str
    value: str


PowerEvent = (
    CreateGame | GameEntityDef | PlayerDef | FullEntity | ShowEntity | ChangeEntity
    | HideEntity | InitialTag | TagChange | BlockStart | BlockEnd | GamePlayerName | GameMeta
)


def entity_id_from_ref(ref: str) -> int | None:
    """``[entityName=X id=12 ...]`` or ``12`` -> 12; other references -> None."""
    if ref.isdigit():
        return int(ref)
    if ref.startswith("["):
        m = ENTITY_ID_RE.search(ref)
        if m:
            return int(m.group(1))
    return None


def parse(line: str) -> tuple[str, PowerEvent] | None:
    """Parse a line into ``(source, event)``; source is GAME_STATE or POWER_TASK_LIST."""
    m = LINE_RE.match(line.rstrip("\r\n"))
    if not m:
        return None
    ts, source, method, data = m.groups()
    data = data.strip()
    event: PowerEvent | None = None
    if method == "DebugPrintGame":
        event = _parse_game(ts, data)
    elif method == "DebugPrintPower":
        event = _parse_power(ts, data)
    return (source, event) if event is not None else None


def parse_line(line: str) -> PowerEvent | None:
    """Parse a line into an event, regardless of its source."""
    parsed = parse(line)
    return parsed[1] if parsed else None


def _parse_game(ts: str, data: str) -> PowerEvent | None:
    m = GAME_META_PLAYER_RE.match(data)
    if m:
        return GamePlayerName(ts, int(m.group(1)), m.group(2).strip())
    m = GAME_META_KV_RE.match(data)
    if m:
        return GameMeta(ts, m.group(1), m.group(2).strip())
    return None


def _parse_power(ts: str, data: str) -> PowerEvent | None:
    if data.startswith("tag="):
        m = INITIAL_TAG_RE.match(data)
        return InitialTag(ts, m.group(1), parse_value(m.group(2))) if m else None
    if data.startswith("TAG_CHANGE"):
        m = TAG_CHANGE_RE.match(data)
        return TagChange(ts, m.group(1), m.group(2), parse_value(m.group(3))) if m else None
    if data.startswith("FULL_ENTITY"):
        m = FULL_ENTITY_CREATE_RE.match(data)
        if m:
            return FullEntity(ts, m.group(1), m.group(2))
        m = FULL_ENTITY_UPDATE_RE.match(data)
        return FullEntity(ts, m.group(1), m.group(2)) if m else None
    if data.startswith("SHOW_ENTITY"):
        m = SHOW_ENTITY_RE.match(data)
        return ShowEntity(ts, m.group(1), m.group(2)) if m else None
    if data.startswith("CHANGE_ENTITY"):
        m = CHANGE_ENTITY_RE.match(data)
        return ChangeEntity(ts, m.group(1), m.group(2)) if m else None
    if data.startswith("HIDE_ENTITY"):
        m = HIDE_ENTITY_RE.match(data)
        return HideEntity(ts, m.group(1), m.group(2), parse_value(m.group(3))) if m else None
    if data.startswith("BLOCK_START"):
        m = BLOCK_START_RE.match(data)
        return BlockStart(ts, m.group(1), m.group(2)) if m else None
    if BLOCK_END_RE.match(data):
        return BlockEnd(ts)
    if CREATE_GAME_RE.match(data):
        return CreateGame(ts)
    m = GAME_ENTITY_RE.match(data)
    if m:
        return GameEntityDef(ts, int(m.group(1)))
    m = PLAYER_RE.match(data)
    if m:
        return PlayerDef(ts, *(int(g) for g in m.groups()))
    return None

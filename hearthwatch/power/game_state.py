"""Rebuild the game's entities from Power.log events and notify listeners."""

from __future__ import annotations

import logging
from typing import Iterable

from hearthwatch.power import parser as p
from hearthwatch.power.entities import Entity

log = logging.getLogger(__name__)


class GameListener:
    """Override the hooks you need. All hooks run on the parsing thread."""

    def on_game_start(self, game: "GameState") -> None: ...

    def on_game_meta(self, game: "GameState", key: str, value: str) -> None: ...

    def on_entity_created(self, game: "GameState", entity: Entity) -> None: ...

    def on_tag_change(
        self, game: "GameState", entity: Entity, tag: str, old: int | str | None, new: int | str
    ) -> None: ...

    def on_block_start(self, game: "GameState", block_type: str, entity: Entity | None) -> None: ...

    def on_block_end(self, game: "GameState") -> None: ...

    def on_game_end(self, game: "GameState") -> None: ...

    def on_game_abort(self, game: "GameState") -> None:
        """A new game started before the previous one ended (reconnect,
        crash, spectating). The unfinished game must not be recorded."""


class GameState:
    """Game state rebuilt from ``PowerTaskList`` lines.

    ``GameState.DebugPrintGame`` lines (game type, player names) are kept in
    :attr:`meta` / :attr:`player_names`; they are reset by the ``GameState``
    CREATE_GAME and survive the ``PowerTaskList`` CREATE_GAME, because they
    may appear before or after it. All other ``GameState`` lines are ignored
    (they run ahead of the screen), as in Hearthstone Deck Tracker.
    """

    def __init__(self, listeners: Iterable[GameListener] = ()) -> None:
        self.listeners = list(listeners)
        self.meta: dict[str, str] = {}
        self.player_names: dict[str, int] = {}  # name -> player_id
        self.games_started = 0
        self.seq = 0  # grows with every applied event; see Entity.tag_seq
        self.reset()

    def reset(self) -> None:
        self.entities: dict[int, Entity] = {}
        self.game_entity_id: int | None = None
        self.player_entities: dict[int, int] = {}  # player_id -> entity id
        self.account_lo: dict[int, int] = {}  # player_id -> account lo
        self.active = False
        self.ended = False
        self.start_ts = ""
        self._pending: Entity | None = None
        self._pending_is_new = False
        self.block_depth = 0

    # -- entity helpers -------------------------------------------------
    @property
    def game_entity(self) -> Entity | None:
        return self.entities.get(self.game_entity_id) if self.game_entity_id is not None else None

    def player_entity(self, player_id: int) -> Entity | None:
        eid = self.player_entities.get(player_id)
        return self.entities.get(eid) if eid is not None else None

    def resolve(self, ref: str, create: bool = False) -> Entity | None:
        if ref == "GameEntity":
            return self.game_entity
        eid = p.entity_id_from_ref(ref)
        if eid is None:
            player_id = self.player_names.get(ref)
            if player_id is None:
                return None
            eid = self.player_entities.get(player_id)
            if eid is None:
                return None
        entity = self.entities.get(eid)
        if entity is None and create:
            entity = Entity(eid)
            self.entities[eid] = entity
        return entity

    # -- feeding --------------------------------------------------------
    def feed_lines(self, lines: Iterable[str]) -> None:
        for line in lines:
            self.feed_line(line)

    def feed_line(self, line: str) -> None:
        parsed = p.parse(line)
        if parsed is not None:
            self.apply(parsed[1], parsed[0])

    def _notify(self, hook: str, *args) -> None:
        """Call ``hook`` on every listener; one failing listener never stops
        the game state (it is logged instead of silently losing the game)."""
        for listener in self.listeners:
            try:
                getattr(listener, hook)(self, *args)
            except Exception:
                log.exception("listener %s.%s failed (seq %d)", type(listener).__name__, hook, self.seq)

    def _flush_pending(self) -> None:
        if self._pending is not None and self._pending_is_new:
            self._notify("on_entity_created", self._pending)
        self._pending = None
        self._pending_is_new = False

    def _set_tag(self, entity: Entity, tag: str, value: int | str) -> None:
        old = entity.tags.get(tag)
        entity.tags[tag] = value
        entity.tag_seq[tag] = self.seq
        if old != value:
            self._notify("on_tag_change", entity, tag, old, value)

    def _name_of(self, player_id: int) -> str:
        for name, pid in self.player_names.items():
            if pid == player_id:
                return name
        return ""

    def _apply_game_info(self, event: p.PowerEvent) -> None:
        if isinstance(event, p.GamePlayerName):
            self.player_names[event.name] = event.player_id
            ent = self.player_entity(event.player_id)
            if ent is not None:
                ent.name = event.name
        elif isinstance(event, p.GameMeta):
            self.meta[event.key] = event.value
            self._notify("on_game_meta", event.key, event.value)

    def apply(self, event: p.PowerEvent, source: str = p.POWER_TASK_LIST) -> None:
        self.seq += 1
        if isinstance(event, (p.GamePlayerName, p.GameMeta)):
            self._apply_game_info(event)
            return
        if source == p.GAME_STATE:
            if isinstance(event, p.CreateGame):
                self.meta = {}  # the game info lines of the new game follow
            return  # the state comes from PowerTaskList (in sync with the screen)

        if isinstance(event, p.InitialTag):
            if self._pending is None:
                return
            if self._pending_is_new:
                self._pending.tags[event.tag] = event.value
                self._pending.tag_seq[event.tag] = self.seq
            else:
                self._set_tag(self._pending, event.tag, event.value)
            return

        self._flush_pending()

        if isinstance(event, p.CreateGame):
            if self.active and not self.ended:
                self._notify("on_game_abort")
            self.reset()
            self.active = True
            self.start_ts = event.ts
            self.games_started += 1
            self._notify("on_game_start")
            return
        if not self.active:
            return

        if isinstance(event, p.GameEntityDef):
            self.game_entity_id = event.entity_id
            entity = Entity(event.entity_id, name="GameEntity")
            self.entities[event.entity_id] = entity
            self._pending, self._pending_is_new = entity, True
        elif isinstance(event, p.PlayerDef):
            entity = Entity(event.entity_id, name=self._name_of(event.player_id))
            self.entities[event.entity_id] = entity
            self.player_entities[event.player_id] = event.entity_id
            self.account_lo[event.player_id] = event.account_lo
            self._pending, self._pending_is_new = entity, True
        elif isinstance(event, p.FullEntity):
            eid = p.entity_id_from_ref(event.entity)
            if eid is None:
                return
            existing = self.entities.get(eid)
            if existing is None:
                entity = Entity(eid, card_id=event.card_id)
                self.entities[eid] = entity
                self._pending, self._pending_is_new = entity, True
            else:
                if event.card_id:
                    existing.card_id = event.card_id
                self._pending, self._pending_is_new = existing, False
        elif isinstance(event, (p.ShowEntity, p.ChangeEntity)):
            entity = self.resolve(event.entity, create=True)
            if entity is None:
                return
            if event.card_id:
                entity.card_id = event.card_id
            self._pending, self._pending_is_new = entity, False
        elif isinstance(event, p.HideEntity):
            entity = self.resolve(event.entity)
            if entity is not None:
                self._set_tag(entity, event.tag, event.value)
        elif isinstance(event, p.TagChange):
            entity = self.resolve(event.entity)
            if entity is None:
                return
            self._set_tag(entity, event.tag, event.value)
            if (
                entity.id == self.game_entity_id
                and event.tag == "STATE"
                and event.value == "COMPLETE"
                and not self.ended
            ):
                self._end_game()
        elif isinstance(event, p.BlockStart):
            self.block_depth += 1
            entity = self.resolve(event.entity)
            self._notify("on_block_start", event.block_type, entity)
        elif isinstance(event, p.BlockEnd):
            self.block_depth = max(0, self.block_depth - 1)
            self._notify("on_block_end")

    def _end_game(self) -> None:
        self.ended = True
        self._notify("on_game_end")

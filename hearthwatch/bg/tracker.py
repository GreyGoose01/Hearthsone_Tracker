"""Battlegrounds-specific interpretation of the game state.

The rules follow what Hearthstone Deck Tracker does (open source, HearthSim):

* ``GameEntity.TURN`` - odd turns are the recruit phase, even turns combat;
  round = (TURN + 1) // 2. Tags ``2022`` / ``3533`` switching from 1 to 0
  also mark the start of a combat.
* Every lobby player is identified by the ``PLAYER_ID`` tag (1-8) on hero
  entities. A player can have several hero entities (leaderboard entry,
  combat copies ...); for each value the most recently updated entity wins.
* ``Player.NEXT_OPPONENT_PLAYER_ID`` names the next opponent's ``PLAYER_ID``.
* During combat the opponent is the hero in zone PLAY that is not ours and
  has ``PLAYER_ID`` > 0 - Bob's hero (``PLAYER_ID`` 0) never counts.
* Minions in zone PLAY controlled by the second player (Bob) are the shop
  during the recruit phase and the opponent's warband during combat.
* ``GameEntity.STATE=COMPLETE`` - game over; the placement is the local
  hero's ``PLAYER_LEADERBOARD_PLACE``.
"""

from __future__ import annotations

import copy
import logging
from datetime import datetime
from typing import Callable

from hearthwatch.bg.models import (
    BoardSnapshot,
    CombatOutcome,
    CombatSnapshot,
    LiveState,
    MatchResult,
    Minion,
    OpponentInfo,
)
from hearthwatch.cards import BG_TRIBES, CardDB, hero_base_id
from hearthwatch.power.entities import Entity
from hearthwatch.power.game_state import GameListener, GameState
from hearthwatch.i18n import N_, _

log = logging.getLogger(__name__)

COMBAT_START_BLOCKS = {"ATTACK"}
COMBAT_SETUP_TAGS = {"2022", "3533"}  # 1 -> 0: combat begins (see HDT TagChangeActions)
COMBAT_SETUP_BEGIN_TAG = "3533"  # 0 -> 1: combat setup begins
RESULT_BLOCKS = {"ATTACK", "DEATHS"}  # board counts after these decide the winner
IGNORED_RACES = {"", "INVALID", "ALL", "BLANK", "0"}
TRIBES_PER_LOBBY = 5
# game-wide counters shown under "Your buffs": tag(s) -> label (values from your own entities)
COUNTERS = (
    (("TAVERN_SPELL_ATTACK_INCREASE", "TAVERN_SPELL_HEALTH_INCREASE"), N_("Tavern spells")),
    (("BACON_BLOODGEMBUFFATKVALUE", "BACON_BLOODGEMBUFFHEALTHVALUE"), N_("Blood Gems")),
    (("BACON_ELEMENTAL_BUFFATKVALUE", "BACON_ELEMENTAL_BUFFHEALTHVALUE"), N_("Elementals")),
    (("BACON_PLAYER_EXTRA_GOLD_NEXT_TURN",), N_("Gold next turn")),
    (("BACON_FREE_REFRESH_COUNT",), N_("Free refreshes")),
)
BLOOD_GEM_TAG = "BACON_BLOODGEMBUFFATKVALUE"
GOLD_TAG = "BACON_PLAYER_EXTRA_GOLD_NEXT_TURN"
# internal enchantments on the player that are no buffs worth showing
INTERNAL_ENCHANTMENTS = ("TB_BaconShop", "Bacon_", "TB_Bacon", "BG_ShopBuff")

# Hero damage = winner's tavern tier + tiers of the surviving minions: at most
# 7 + 7 * 7 = 56. Hero powers, trinkets etc. can add more, hence a generous buffer;
# only clearly impossible values (a misread log) are discarded.
MAX_SURVIVORS, MAX_TIER, DAMAGE_BUFFER = 7, 7, 20


def max_plausible_damage(winner_tier: int) -> int:
    return max(winner_tier, 1) + MAX_SURVIVORS * MAX_TIER + DAMAGE_BUFFER


def _latest(entities: list[Entity], *tags: str) -> Entity:
    """The entity whose ``tags`` were changed most recently."""
    return max(entities, key=lambda e: (e.last_change(*tags), e.id))


class BattlegroundsTracker(GameListener):
    def __init__(
        self,
        cards: CardDB | None = None,
        on_state: Callable[[LiveState], None] | None = None,
        on_combat: Callable[[CombatSnapshot], None] | None = None,
        on_match_end: Callable[[MatchResult], None] | None = None,
        on_combat_result: Callable[[CombatSnapshot], None] | None = None,
    ) -> None:
        self.cards = cards or CardDB()
        self.on_state = on_state
        self.on_combat = on_combat
        self.on_match_end = on_match_end
        self.on_combat_result = on_combat_result
        self.source = ""
        self.unknown_cards: set[str] = set()  # IDs missing from the card data
        self.collect_details = False  # --replay --details: explain which entities were used
        self.last_details = ""
        self._reset()

    # -- card data -----------------------------------------------------------
    def _card_name(self, card_id: str) -> str:
        if card_id and len(self.cards) and self.cards.get(card_id) is None:
            self.unknown_cards.add(card_id)
        return self.cards.name(card_id)

    def relabel(self) -> None:
        """Re-resolve names after new card data arrived (snapshots store names)."""

        def fix(board: BoardSnapshot | None) -> None:
            if board is None:
                return
            if board.hero_card_id:
                board.hero_name = self._card_name(board.hero_card_id)
            for m in board.minions:
                info = self.cards.get(m.card_id)
                if info is not None:
                    m.name = info.name
                    m.cleave = m.cleave or "CLEAVE" in info.mechanics
                elif m.card_id and len(self.cards):
                    self.unknown_cards.add(m.card_id)

        self.unknown_cards = {c for c in self.unknown_cards if self.cards.get(c) is None}
        for board in self._boards.values():
            fix(board)
        for combat in (self._current, self.state.last_combat, *self.state.combat_log):
            if combat is not None:
                fix(combat.player)
                fix(combat.opponent)
        if self.state.hero_card_id:
            self.state.hero_name = self._card_name(self.state.hero_card_id)
        for o in self.state.opponents:
            o.hero_name = self._card_name(o.hero_card_id)
        self._dirty = True

    # -- state -----------------------------------------------------------
    def _reset(self) -> None:
        self.state = LiveState()
        self._local_player_id: int | None = None
        self._combat_pending = False
        self._combat_phase_round = 0
        self._expected_opponent = 0  # NEXT_OPPONENT_PLAYER_ID when the combat began
        self._boards: dict[str, BoardSnapshot] = {}  # lobby key -> last seen board
        self._tribes_seen: set[str] = set()
        self._last_my_board: list[Minion] = []
        self._combat_ids: set[int] = set()  # opponent minions that entered play this combat
        # tracking of the running combat's real outcome
        self._current: CombatSnapshot | None = None
        self._my_pid = 0
        self._my_hero_ids: set[int] = set()
        self._opp_hero_ids: set[int] = set()
        self._opp_controller: int | None = None
        self._damage: dict[str, dict[int, int]] = {"me": {}, "opp": {}}
        self._counts: tuple[int, int] | None = None
        self._hp_keys: dict[str, str | None] = {}
        self._hp_exclude: set[int] = set()
        self._hp_before: dict[str, int | None] = {}
        self._tier_up: dict[str, int] = {}  # lobby key -> round of the last tier increase
        self._blocks: list[str] = []
        self._dirty = False

    def snapshot(self) -> LiveState:
        return copy.deepcopy(self.state)

    def _emit(self) -> None:
        if self.on_state:
            self.on_state(self.snapshot())
        self._dirty = False

    def flush(self) -> None:
        """Emit the live state if it changed since the last emit (batching)."""
        if self._dirty:
            self._emit()

    # -- identity helpers -----------------------------------------------------
    def local_player_id(self, game: GameState) -> int | None:
        if self._local_player_id is not None:
            return self._local_player_id
        players = [(pid, game.player_entity(pid)) for pid in game.player_entities]
        players = [(pid, e) for pid, e in players if e is not None]
        if not players:
            return None
        real = [(pid, e) for pid, e in players if not e.int_tag("BACON_DUMMY_PLAYER")]
        if len(real) == 1:
            self._local_player_id = real[0][0]
            return self._local_player_id
        tagged = [(pid, e) for pid, e in players if "#" in e.name]
        if len(tagged) == 1:
            self._local_player_id = tagged[0][0]
            return self._local_player_id
        with_account = [pid for pid, _ in players if game.account_lo.get(pid)]
        if len(with_account) == 1:
            self._local_player_id = with_account[0]
            return self._local_player_id
        return min(pid for pid, _ in players)

    def _opponent_player_id(self, game: GameState) -> int | None:
        local = self.local_player_id(game)
        others = [pid for pid in game.player_entities if pid != local]
        return others[0] if others else None

    def _local_player(self, game: GameState) -> Entity | None:
        pid = self.local_player_id(game)
        return game.player_entity(pid) if pid is not None else None

    def _hero_of(self, game: GameState, player: Entity | None) -> Entity | None:
        if player is None:
            return None
        return game.entities.get(player.int_tag("HERO_ENTITY"))

    @staticmethod
    def _lobby_key(e: Entity) -> str:
        pid = e.int_tag("PLAYER_ID")
        return f"p{pid}" if pid > 0 else f"c{hero_base_id(e.card_id)}"

    def _lobby(self, game: GameState) -> dict[str, list[Entity]]:
        """Hero entities per lobby player (key ``p<PLAYER_ID>``)."""
        groups: dict[str, list[Entity]] = {}
        for e in game.entities.values():
            if e.is_hero and e.card_id and e.int_tag("PLAYER_LEADERBOARD_PLACE") > 0:
                groups.setdefault(self._lobby_key(e), []).append(e)
        # combat copies etc. without a leaderboard place still carry PLAYER_ID
        for e in game.entities.values():
            if e.is_hero and e.card_id and not e.int_tag("PLAYER_LEADERBOARD_PLACE"):
                key = self._lobby_key(e)
                if key.startswith("p") and key in groups:
                    groups[key].append(e)
        return groups

    def _key_for(self, lobby: dict[str, list[Entity]], hero: Entity | None) -> str | None:
        if hero is None:
            return None
        key = self._lobby_key(hero)
        if key in lobby:
            return key
        base = hero_base_id(hero.card_id)
        for k, ents in lobby.items():
            if any(hero_base_id(e.card_id) == base for e in ents):
                return k
        return None

    def _races(self, entity: Entity) -> tuple[str, ...]:
        races = self.cards.races(entity.card_id)
        if not races:
            race = entity.tag("CARDRACE", "")
            races = (str(race),) if race else ()
        return tuple(r for r in races if r not in IGNORED_RACES)

    @staticmethod
    def _attachments(game: GameState) -> dict[int, list[Entity]]:
        """Enchantments (buffs) per minion id - entities with ``ATTACHED=<id>``."""
        result: dict[int, list[Entity]] = {}
        for e in game.entities.values():
            target = e.int_tag("ATTACHED")
            if target and e.card_type == "ENCHANTMENT" and e.zone in ("PLAY", "SETASIDE"):
                result.setdefault(target, []).append(e)
        return result

    def _buff_text(self, enchantment: Entity) -> str:
        name = self.cards.name(enchantment.card_id) if enchantment.card_id else "?"
        n1 = enchantment.int_tag("TAG_SCRIPT_DATA_NUM_1")
        n2 = enchantment.int_tag("TAG_SCRIPT_DATA_NUM_2")
        if n1 or n2:
            return f"{name} ({n1}/{n2})" if n2 else f"{name} ({n1})"
        return name

    def _buffs(self, enchantments: list[Entity]) -> list[str]:
        counts: dict[str, int] = {}
        for e in sorted(enchantments, key=lambda x: x.id):
            text = self._buff_text(e)
            counts[text] = counts.get(text, 0) + 1
        return [f"{t} ×{n}" if n > 1 else t for t, n in counts.items()]

    def _minion(self, entity: Entity, attachments: dict[int, list[Entity]] | None = None) -> Minion:
        info = self.cards.get(entity.card_id)
        if info is None and entity.card_id and len(self.cards):
            self.unknown_cards.add(entity.card_id)
        return Minion(
            buffs=self._buffs((attachments or {}).get(entity.id, [])),
            card_id=entity.card_id,
            name=info.name if info else entity.card_id,
            attack=entity.int_tag("ATK"),
            health=entity.health,
            golden=entity.int_tag("PREMIUM") > 0,
            taunt=entity.int_tag("TAUNT") > 0,
            divine_shield=entity.int_tag("DIVINE_SHIELD") > 0,
            reborn=entity.int_tag("REBORN") > 0,
            venomous=entity.int_tag("POISONOUS") > 0 or entity.int_tag("VENOMOUS") > 0,
            windfury=3 if entity.int_tag("MEGA_WINDFURY") else (1 if entity.int_tag("WINDFURY") else 0),
            cleave=bool(info and "CLEAVE" in info.mechanics),
            deathrattle=entity.int_tag("DEATHRATTLE") > 0,
            tribes=self._races(entity),
            tech_level=entity.int_tag("TECH_LEVEL") or (info.tech_level if info else 0) or 1,
        )

    def _board_entities(
        self, game: GameState, controller: int | None, only: set[int] | None = None
    ) -> list[Entity]:
        if controller is None:
            return []
        minions = [
            e for e in game.entities.values()
            if e.is_minion and e.is_in_play and e.controller == controller
            and (not only or e.id in only)
        ]
        minions.sort(key=lambda e: e.int_tag("ZONE_POSITION"))
        return minions

    def _board(self, game: GameState, controller: int | None, only: set[int] | None = None) -> list[Minion]:
        attachments = self._attachments(game)
        return [self._minion(e, attachments) for e in self._board_entities(game, controller, only)]

    # -- GameListener ------------------------------------------------------
    def on_game_start(self, game: GameState) -> None:
        self._reset()
        self.state.in_game = True
        game_type = game.meta.get("GameType")
        if game_type:  # the game info lines may come before the game itself
            self.on_game_meta(game, "GameType", game_type)
        self._dirty = True

    def on_game_meta(self, game: GameState, key: str, value: str) -> None:
        if key == "GameType":
            self.state.game_type = value
            self.state.is_battlegrounds = value.startswith("GT_BATTLEGROUNDS")
            self._dirty = True

    def on_entity_created(self, game: GameState, entity: Entity) -> None:
        if not self.state.is_battlegrounds:
            return
        if entity.is_minion and entity.is_in_play:
            self._note_minion(game, entity)
        if entity.is_hero or entity.is_minion:
            self._dirty = True

    def on_tag_change(self, game, entity, tag, old, new) -> None:
        if not self.state.is_battlegrounds:
            return
        if entity.id == game.game_entity_id and tag == "TURN" and isinstance(new, int):
            self._on_turn(game, new)
        elif tag in COMBAT_SETUP_TAGS and (
            (old == 1 and new == 0) or (tag == COMBAT_SETUP_BEGIN_TAG and new == 1 and not old)
        ):
            # 3533 goes 0 -> 1 while the combat is being set up (the opponent's
            # minions are created then) and 1 -> 0 when it starts
            self._start_combat_phase(game, f"tag {tag} {old}->{new}")
        elif tag in ("ZONE", "CONTROLLER") and entity.is_minion and entity.is_in_play:
            self._note_minion(game, entity)
        elif tag in ("DAMAGE", "ARMOR") and entity.is_hero:
            self._note_hero_damage(entity, tag, old, new)
        elif tag == "PLAYER_TECH_LEVEL" and entity.is_hero and isinstance(new, int) and isinstance(old, int):
            if new > old and entity.int_tag("PLAYER_ID") > 0:
                self._tier_up[self._lobby_key(entity)] = self.state.round
        if entity.is_minion or entity.card_type == "ENCHANTMENT" or entity.card_type == "PLAYER":
            if self.state.phase != "combat":
                self._dirty = True  # your live board and buffs
        if tag in (
            "PLAYER_LEADERBOARD_PLACE", "HEALTH", "DAMAGE", "ARMOR", "PLAYER_TECH_LEVEL",
            "HERO_ENTITY", "NEXT_OPPONENT_PLAYER_ID", "TURN", "PLAYER_ID",
        ):
            self._dirty = True

    def on_block_start(self, game, block_type, entity) -> None:
        if not self.state.is_battlegrounds:
            return
        self._blocks.append(block_type)
        if self._combat_pending and block_type in COMBAT_START_BLOCKS:
            try:
                self._take_combat_snapshot(game)
            except Exception:
                # keep the combat pending: the next attack tries again
                log.exception("combat snapshot failed in round %s", self.state.round)
                return
            self._combat_pending = False

    def on_block_end(self, game) -> None:
        if not self.state.is_battlegrounds or not self._blocks:
            return
        block_type = self._blocks.pop()
        if block_type in RESULT_BLOCKS and self._current is not None and self._current.actual is None:
            local = self.local_player_id(game)
            mine = len(self._board_entities(game, local))
            theirs = len(self._opponent_combat_minions(game))
            self._counts = (mine, theirs)

    def abandon(self, notice: str) -> bool:
        """The game was left but the log never reported its end (e.g. Power.log
        stopped at the log size limit): stop showing it as running. Nothing is
        saved - the placement is unknown."""
        if not self.state.in_game:
            return False
        log.info("abandoning the game in round %s: %s", self.state.round, notice)
        self._reset()
        self.state.notice = notice
        self._emit()
        return True

    def on_game_abort(self, game: GameState) -> None:
        # Unfinished game (e.g. reconnect: the log replays the game after a
        # new CREATE_GAME). Nothing is saved; on_game_start resets the state.
        self.state.in_game = False
        self._dirty = True

    def on_game_end(self, game: GameState) -> None:
        if not self.state.is_battlegrounds:
            self.state.in_game = False
            self._emit()
            return
        self._finish_combat(game)
        self._refresh(game)
        result = MatchResult(
            source_key=f"{self.source}#{game.games_started}@{game.start_ts}",
            started_at=game.start_ts,
            ended_at=datetime.now().isoformat(timespec="seconds"),
            game_type=self.state.game_type,
            hero_card_id=hero_base_id(self.state.hero_card_id),
            hero_name=self.state.hero_name,
            placement=self.state.place,
            rounds=self.state.round,
            tavern_tier=self.state.tavern_tier,
            tribes=sorted(self._tribes_seen),
            final_board=self._last_my_board or self._board(game, self.local_player_id(game)),
        )
        self.state.in_game = False
        self.state.summary = result  # shown as end-of-game summary until the next game
        log.info("game over: %s, place %s after %s rounds", result.hero_name, result.placement,
                 result.rounds)
        self._emit()
        if self.on_match_end:
            self.on_match_end(result)

    # -- phases ---------------------------------------------------------------
    def _on_turn(self, game: GameState, turn: int) -> None:
        self.state.round = (turn + 1) // 2
        if turn % 2 == 0:
            self._start_combat_phase(game, f"TURN {turn}")
        else:
            if self._combat_pending:
                log.warning("round %s: combat ended without an attack being seen - no snapshot",
                            self.state.round - 1)
            self._finish_combat(game)
            self.state.phase = "recruit"
            self._combat_pending = False
        self._dirty = True

    def _start_combat_phase(self, game: GameState, reason: str = "") -> None:
        if self._combat_phase_round == self.state.round and self.state.phase == "combat":
            return  # already started by the setup tag or the TURN change
        log.info("round %s: combat phase begins (%s)", self.state.round, reason)
        self._combat_phase_round = self.state.round
        self.state.phase = "combat"
        self._combat_pending = True
        self._combat_ids = set()
        player = self._local_player(game)
        self._expected_opponent = player.int_tag("NEXT_OPPONENT_PLAYER_ID") if player else 0
        self._dirty = True

    def _note_minion(self, game: GameState, entity: Entity) -> None:
        if entity.controller != self._opponent_player_id(game):
            return
        if self.state.phase == "combat":
            self._combat_ids.add(entity.id)
        else:
            self._note_tribes(entity)

    def _note_tribes(self, entity: Entity) -> None:
        before = len(self._tribes_seen)
        self._tribes_seen.update(r for r in self._races(entity) if r in BG_TRIBES)
        if len(self._tribes_seen) != before:
            self._dirty = True

    # -- combat -----------------------------------------------------------------
    def _opponent_combat_hero(self, game: GameState) -> Entity | None:
        local = self.local_player_id(game)
        candidates = [
            e for e in game.entities.values()
            if e.is_hero and e.is_in_play and e.controller != local and e.int_tag("PLAYER_ID") > 0
        ]
        return max(candidates, key=lambda e: e.id) if candidates else None

    def _opponent_combat_minions(self, game: GameState) -> list[Entity]:
        controller = self._opp_controller
        if controller is None:
            controller = self._opponent_player_id(game)
        return self._board_entities(game, controller, self._combat_ids)

    def _take_combat_snapshot(self, game: GameState) -> None:
        local = self.local_player_id(game)
        lobby = self._lobby(game)
        my_hero = self._hero_of(game, self._local_player(game))

        opp_hero = self._opponent_combat_hero(game)
        opp_pid = opp_hero.int_tag("PLAYER_ID") if opp_hero is not None else self._expected_opponent
        opp_key = f"p{opp_pid}" if opp_pid > 0 else self._key_for(lobby, opp_hero)
        opp_entities = lobby.get(opp_key, []) if opp_key else []
        if opp_hero is None and opp_entities:
            opp_hero = _latest(opp_entities, "PLAYER_LEADERBOARD_PLACE")
        self._opp_controller = opp_hero.controller if opp_hero is not None and opp_hero.is_in_play else None

        opp_card = opp_hero.card_id if opp_hero is not None else ""
        opp_tier = opp_hero.int_tag("PLAYER_TECH_LEVEL") if opp_hero is not None else 0
        if not opp_tier and opp_entities:
            opp_tier = _latest(opp_entities, "PLAYER_TECH_LEVEL").int_tag("PLAYER_TECH_LEVEL")

        my_board = self._board(game, local)
        opp_entities_board = self._opponent_combat_minions(game)
        attachments = self._attachments(game)
        opp_board = [self._minion(e, attachments) for e in opp_entities_board]
        if self.collect_details:
            self.last_details = self.describe_combat(game, local, opp_entities_board)
        me = BoardSnapshot(
            round=self.state.round,
            hero_card_id=my_hero.card_id if my_hero else "",
            hero_name=self._card_name(my_hero.card_id) if my_hero else "",
            tavern_tier=self.state.tavern_tier or 1,
            minions=my_board,
        )
        them = BoardSnapshot(
            round=self.state.round,
            hero_card_id=opp_card,
            hero_name=self._card_name(opp_card) if opp_card else "?",
            tavern_tier=opp_tier or 1,
            minions=opp_board,
        )
        if opp_key:
            self._boards[opp_key] = them
        self._last_my_board = my_board

        # remember who is who to read the real outcome later
        my_key = self._key_for(lobby, my_hero)
        self._my_pid = my_hero.int_tag("PLAYER_ID") if my_hero is not None else 0
        self._my_hero_ids = {e.id for e in lobby.get(my_key, [])} if my_key else set()
        if my_hero is not None:
            self._my_hero_ids.add(my_hero.id)
        self._opp_hero_ids = {e.id for e in opp_entities}
        if opp_hero is not None:
            self._opp_hero_ids.add(opp_hero.id)
        self._damage = {"me": {}, "opp": {}}
        self._counts = None
        # effective health (health + armor) of both lobby entries before the fight;
        # the opponent's combat copy is left out - it is reset when the board is cleared
        self._hp_keys = {"me": my_key, "opp": opp_key}
        self._hp_exclude = {opp_hero.id} if opp_hero is not None and opp_hero.is_in_play else set()
        self._hp_before = {side: self._effective_hp(game, side) for side in ("me", "opp")}

        combat = CombatSnapshot(
            round=self.state.round, player=me, opponent=them, opponent_player_id=max(opp_pid, 0)
        )
        self._current = combat
        self.state.last_combat = combat
        self.state.combat_log.append(combat)  # same object: gets its outcome later
        log.info("round %s: combat vs %s (PLAYER_ID %s): %d vs %d minions", combat.round,
                 them.hero_name, opp_pid, len(my_board), len(opp_board))
        self._refresh(game)
        self._emit()
        if self.on_combat:
            self.on_combat(copy.deepcopy(combat))

    def _note_hero_damage(self, entity: Entity, tag: str, old, new) -> None:
        if self._current is None or self._current.actual is not None:
            return
        if not isinstance(new, int):
            return
        old = old if isinstance(old, int) else 0
        delta = new - old if tag == "DAMAGE" else old - new  # armor goes down
        if delta <= 0:
            return
        if tag == "ARMOR" and new == 0 and (
            entity.id in self._hp_exclude or not entity.int_tag("PLAYER_LEADERBOARD_PLACE")
        ):
            return  # a combat copy being reset, not a hit
        pid = entity.int_tag("PLAYER_ID")
        if entity.id in self._my_hero_ids or (self._my_pid and pid == self._my_pid):
            side = "me"
        elif entity.id in self._opp_hero_ids or (
            self._current.opponent_player_id and pid == self._current.opponent_player_id
        ):
            side = "opp"
        else:
            return
        self._damage[side][entity.id] = self._damage[side].get(entity.id, 0) + delta

    def _effective_hp(self, game: GameState, side: str) -> int | None:
        """Health + armor of a lobby entry (as the leaderboard shows it)."""
        key = self._hp_keys.get(side)
        ents = self._lobby(game).get(key, []) if key else []
        ents = [e for e in ents if e.id not in self._hp_exclude] or ents
        if not ents:
            return None
        placed = [e for e in ents if e.int_tag("PLAYER_LEADERBOARD_PLACE") > 0] or ents
        health_e = _latest(placed, "HEALTH", "DAMAGE")
        armor_e = _latest(placed, "ARMOR")
        return health_e.health + armor_e.int_tag("ARMOR")

    def _hp_loss(self, game: GameState | None, side: str) -> int | None:
        if game is None:
            return None
        before = self._hp_before.get(side)
        after = self._effective_hp(game, side)
        if before is None or after is None:
            return None
        return max(0, before - after)

    def _finish_combat(self, game: GameState | None = None) -> None:
        combat = self._current
        if combat is None or combat.actual is not None:
            return
        # preferred: health lost according to the lobby; fallback: summed tag changes
        lost_me, lost_opp = self._hp_loss(game, "me"), self._hp_loss(game, "opp")
        taken = lost_me if lost_me is not None else max(self._damage["me"].values(), default=0)
        dealt = lost_opp if lost_opp is not None else max(self._damage["opp"].values(), default=0)
        log.info("round %s: health before %s, after me=%s opp=%s (tag sums me=%s opp=%s)",
                 combat.round, self._hp_before, lost_me, lost_opp,
                 max(self._damage["me"].values(), default=0),
                 max(self._damage["opp"].values(), default=0))
        result = None
        if self._counts is not None:
            mine, theirs = self._counts
            if mine and not theirs:
                result = "win"
            elif theirs and not mine:
                result = "loss"
            elif not mine and not theirs:
                result = "draw"
        if result is None:
            result = "loss" if taken else "win" if dealt else "draw"
        damage = dealt if result == "win" else taken if result == "loss" else 0
        winner = combat.player if result == "win" else combat.opponent
        limit = max_plausible_damage(winner.tavern_tier)
        if damage > limit:
            log.warning("round %s: implausible damage %s (> %s) ignored - lobby %s/%s, tag sums %s/%s",
                        combat.round, damage, limit, lost_me, lost_opp,
                        max(self._damage["me"].values(), default=0),
                        max(self._damage["opp"].values(), default=0))
            damage = 0
        combat.actual = CombatOutcome(result, damage or None)
        log.info("round %s: outcome %s (counts %s, damage taken %s dealt %s)",
                 combat.round, combat.actual.text(), self._counts, taken, dealt)
        self.state.last_combat = combat
        self._dirty = True
        if self.on_combat_result:
            self.on_combat_result(copy.deepcopy(combat))

    # -- diagnostics ----------------------------------------------------------------
    def describe_combat(self, game: GameState, local: int | None, opp_entities: list[Entity]) -> str:
        """Which entities a combat snapshot used, with their tags and buffs
        (``--replay --details``) - to find wrong or stale minion stats."""
        attachments = self._attachments(game)

        def line(e: Entity) -> str:
            t = e.int_tag
            extra = []
            for tag in ("CREATOR", "COPIED_FROM_ENTITY_ID", "LINKED_ENTITY"):
                if t(tag):
                    extra.append(f"{tag}={t(tag)}")
            stats = f"ATK={t('ATK')} HEALTH={t('HEALTH')} DAMAGE={t('DAMAGE')}"
            when = f"changed@{e.last_change('ATK', 'HEALTH', 'DAMAGE')}"
            return (f"    #{e.id} {self.cards.name(e.card_id)} [{e.card_id}] zone={e.zone} "
                    f"ctrl={e.controller} pos={t('ZONE_POSITION')} {stats} {when} {' '.join(extra)}")

        def side(title: str, entities: list[Entity]) -> list[str]:
            out = [f"  {title}:"]
            if not entities:
                out.append("    " + _("(none)"))
            for e in entities:
                out.append(line(e))
                for ench in attachments.get(e.id, []):
                    out.append(f"        Buff: {self._buff_text(ench)} [{ench.card_id}] zone={ench.zone}")
                same = [
                    o for o in game.entities.values()
                    if o.id != e.id and o.card_id == e.card_id and o.is_minion and o.controller == e.controller
                ]
                for o in sorted(same, key=lambda x: x.id):
                    out.append("        " + _("same card:") + line(o)[3:])
            return out

        mine = self._board_entities(game, local)
        others = [
            e for e in game.entities.values()
            if e.is_minion and e.controller == local and e.zone not in ("PLAY", "GRAVEYARD", "REMOVEDFROMGAME")
        ]
        lines = side(_("Your minions in combat"), mine) + side(_("Opponent minions in combat"), opp_entities)
        if others:
            lines.append("  " + _("Your minions in other zones:"))
            lines += [line(e) for e in sorted(others, key=lambda x: x.id)]
        return "\n".join(lines)

    # -- derived state ------------------------------------------------------------
    @staticmethod
    def _main_tribe(board: BoardSnapshot | None) -> str:
        if board is None:
            return ""
        counts: dict[str, int] = {}
        for m in board.minions:
            for t in m.tribes:
                if t in BG_TRIBES:
                    counts[t] = counts.get(t, 0) + 1
        if not counts:
            return ""
        best = max(counts.values())
        return next(t for t in BG_TRIBES if counts.get(t) == best)

    def _player_buffs(self, game: GameState, player: Entity | None, hero: Entity | None) -> list[str]:
        """Game-wide buffs: enchantments attached to your player or hero."""
        targets = {e.id for e in (player, hero) if e is not None}
        if not targets:
            return []
        enchantments = [
            e for e in game.entities.values()
            if e.card_type == "ENCHANTMENT" and e.zone == "PLAY" and e.int_tag("ATTACHED") in targets
            and e.card_id and not e.card_id.startswith(INTERNAL_ENCHANTMENTS)
        ]
        return self._buffs(enchantments)

    def _counters(self, game: GameState) -> list[str]:
        local = self.local_player_id(game)
        if local is None:
            return []
        player = game.player_entity(local)
        mine = [
            e for e in game.entities.values()
            if e.controller == local and (e is player or e.zone == "PLAY")
        ]
        out = []
        for tags, label in COUNTERS:
            with_tag = [e for e in mine if any(t in e.tags for t in tags)]
            if not with_tag:
                continue
            src = _latest(with_tag, *tags)
            values = [src.int_tag(t) for t in tags]
            if not any(values):
                continue
            if tags[0] == BLOOD_GEM_TAG:  # a blood gem is +1/+1 plus the bonus
                values = [v + 1 for v in values]
            text = _(label)
            if len(values) == 2:
                out.append(f"{text} +{values[0]}/+{values[1]}")
            elif tags[0] == GOLD_TAG:
                out.append(f"{text} +{values[0]}")
            else:
                out.append(f"{text}: {values[0]}")
        return out

    def _refresh(self, game: GameState) -> None:
        """Recompute derived values of ``self.state`` from the entities."""
        s = self.state
        player = self._local_player(game)
        hero = self._hero_of(game, player)
        if player is not None:
            s.tavern_tier = player.int_tag("PLAYER_TECH_LEVEL") or s.tavern_tier
        if hero is not None and hero.card_id:
            s.hero_card_id = hero.card_id
            s.hero_name = self._card_name(hero.card_id)
        lobby = self._lobby(game)
        my_key = self._key_for(lobby, hero)
        next_id = player.int_tag("NEXT_OPPONENT_PLAYER_ID") if player is not None else 0
        opponents = []
        s.next_opponent = ""
        for key, ents in lobby.items():
            placed = [e for e in ents if e.int_tag("PLAYER_LEADERBOARD_PLACE") > 0] or ents
            main = _latest(placed, "PLAYER_LEADERBOARD_PLACE")
            health_e = _latest(ents, "HEALTH", "DAMAGE")
            armor_e = _latest(ents, "ARMOR")
            tier_e = _latest(ents, "PLAYER_TECH_LEVEL")
            last_board = self._boards.get(key)
            info = OpponentInfo(
                hero_card_id=hero_base_id(main.card_id),
                hero_name=self._card_name(main.card_id),
                lobby_player_id=main.int_tag("PLAYER_ID"),
                place=main.int_tag("PLAYER_LEADERBOARD_PLACE"),
                health=health_e.health,
                armor=armor_e.int_tag("ARMOR"),
                tavern_tier=tier_e.int_tag("PLAYER_TECH_LEVEL"),
                is_me=key == my_key,
                last_board=last_board,
                max_health=health_e.int_tag("HEALTH"),
                tier_up_round=self._tier_up.get(key, 0),
                main_tribe=self._main_tribe(last_board),
            )
            for c in s.combat_log:  # your record against this player
                if c.actual is not None and c.opponent_player_id and f"p{c.opponent_player_id}" == key:
                    counter = {"win": "wins", "draw": "draws", "loss": "losses"}[c.actual.result]
                    setattr(info, counter, getattr(info, counter) + 1)
            if next_id and info.lobby_player_id == next_id and not info.is_me:
                info.is_next_opponent = True
                s.next_opponent = info.hero_name
            if info.is_me:
                s.place = info.place
                s.health = info.health
                s.armor = info.armor
                s.max_health = info.max_health
                if not s.tavern_tier:
                    s.tavern_tier = info.tavern_tier
            opponents.append(info)
        if my_key is None and hero is not None:
            s.health = hero.health
            s.armor = hero.int_tag("ARMOR")
            s.place = hero.int_tag("PLAYER_LEADERBOARD_PLACE") or s.place
        opponents.sort(key=lambda o: (o.place or 99, o.hero_name))
        s.opponents = opponents
        if s.phase != "combat":
            s.my_board = self._board(game, self.local_player_id(game))
        s.player_buffs = self._player_buffs(game, player, hero)
        s.counters = self._counters(game)
        s.tribes_seen = sorted(self._tribes_seen)
        if len(self._tribes_seen) >= TRIBES_PER_LOBBY:
            s.tribes_banned = sorted(set(BG_TRIBES) - self._tribes_seen)
        else:
            s.tribes_banned = []

    def batch_done(self, game: GameState) -> None:
        """Call after feeding a batch of lines; emits one update if needed."""
        if self._dirty and self.state.is_battlegrounds:
            self._refresh(game)
            self._emit()
        elif self._dirty:
            self._emit()

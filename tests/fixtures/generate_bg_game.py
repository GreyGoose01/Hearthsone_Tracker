"""Generate ``bg_game.log``: a small synthetic Battlegrounds game in the layout
of a real Power.log.

Run ``python tests/fixtures/generate_bg_game.py`` after changing it.

What it contains (and what the tests rely on):

* ``GameState`` lines first (they run ahead of the screen in real logs),
  including ``DebugPrintGame`` (game type, player names) and a few misleading
  power lines that must be ignored because ``PowerTaskList`` lines exist.
* ``PowerTaskList`` lines with the actual game, entities written as
  ``FULL_ENTITY - Updating [entityName=... id=N ...] CardID=X``.
* Bob's hero (PLAYER_ID 0) in play the whole game - must never be taken as
  the opponent.
* A stale copy of hero D (lower entity id) that is never updated - health and
  place must come from the newer leaderboard entity.
* Round 1: shop, buying a minion, combat setup via tag 3533 (0 -> 1 -> 0),
  combat against hero C (lobby PLAYER_ID 3) which we lose for 4 damage. One
  shop minion stays in play during combat and must not count as C's board.
  C's combat copy has 18 armor that is reset to 0 on cleanup - not damage.
* Round 2: recruit, tavern tier 2, next opponent PLAYER_ID 5 (hero E), E tiers
  up, a game-wide buff on our player, 2 extra gold next turn, our beast buffed
  to 3/3 by an enchantment.
  E also makes a triple and gets a trinket; our trinket uses the numeric tag
  id 3741. The game entity carries an anomaly (BACON_GLOBAL_ANOMALY_DBID).
  The game entity carries the early damage cap (5, enabled).
* Game over: placement 3.
"""

from __future__ import annotations

from pathlib import Path

OUT = Path(__file__).with_name("bg_game.log")

ME, BOB = 5, 13  # player ids (CONTROLLER values)
ME_NAME, BOB_NAME = "Tester#2345", "Bartender Bob"


class Log:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.t = 0

    def _ts(self) -> str:
        self.t += 1
        s = self.t
        return f"20:{(s // 3600) % 60:02d}:{(s // 60) % 60:02d}.{s % 60:02d}00000"

    def gs(self, data: str, indent: int = 0) -> None:
        self.lines.append(f"D {self._ts()} GameState.DebugPrintPower() - " + "    " * indent + data)

    def game(self, data: str) -> None:
        self.lines.append(f"D {self._ts()} GameState.DebugPrintGame() - {data}")

    def ptl(self, data: str, indent: int = 0) -> None:
        self.lines.append(f"D {self._ts()} PowerTaskList.DebugPrintPower() - " + "    " * indent + data)


def ref(eid: int, card: str, player: int, zone: str = "PLAY", pos: int = 0) -> str:
    return f"[entityName={card} id={eid} zone={zone} zonePos={pos} cardId={card} player={player}]"


def build() -> list[str]:
    log = Log()

    # --- GameState: ahead of the screen; only DebugPrintGame is used -------------
    log.gs("CREATE_GAME")
    log.gs("GameEntity EntityID=1", 1)
    log.gs("tag=TURN value=0", 2)
    log.gs(f"Player EntityID=2 PlayerID={ME} GameAccountId=[hi=144115198130930503 lo=12345678]", 1)
    log.gs(f"Player EntityID=3 PlayerID={BOB} GameAccountId=[hi=0 lo=0]", 1)
    log.game("GameType=GT_BATTLEGROUNDS")
    log.game("FormatType=FT_WILD")
    log.game("ScenarioID=3459")
    log.game(f"PlayerID={ME}, PlayerName={ME_NAME}")
    log.game(f"PlayerID={BOB}, PlayerName={BOB_NAME}")
    # misleading: GameState is ahead - these must not change the tracked state
    log.gs("TAG_CHANGE Entity=GameEntity tag=TURN value=99")
    log.gs(f"TAG_CHANGE Entity={ME_NAME} tag=NEXT_OPPONENT_PLAYER_ID value=7")

    p = log.ptl
    # --- PowerTaskList: the game as shown on screen ---------------------------
    p("CREATE_GAME")
    p("GameEntity EntityID=1", 1)
    p("tag=TURN value=0", 2)
    p("tag=STATE value=RUNNING", 2)
    p("tag=BACON_GLOBAL_ANOMALY_DBID value=90001", 2)
    p("tag=BACON_COMBAT_DAMAGE_CAP value=5", 2)
    p("tag=BACON_COMBAT_DAMAGE_CAP_ENABLED value=1", 2)
    p(f"Player EntityID=2 PlayerID={ME} GameAccountId=[hi=144115198130930503 lo=12345678]", 1)
    p(f"tag=CONTROLLER value={ME}", 2)
    p("tag=CARDTYPE value=PLAYER", 2)
    p("tag=PLAYER_TECH_LEVEL value=1", 2)
    p(f"Player EntityID=3 PlayerID={BOB} GameAccountId=[hi=0 lo=0]", 1)
    p(f"tag=CONTROLLER value={BOB}", 2)
    p("tag=CARDTYPE value=PLAYER", 2)
    p("tag=BACON_DUMMY_PLAYER value=1", 2)

    def hero(eid, card, controller, zone, pid=None, place=None, tier=1, health=30):
        p(f"FULL_ENTITY - Updating {ref(eid, card, controller, zone)} CardID={card}")
        p(f"tag=CONTROLLER value={controller}", 1)
        p("tag=CARDTYPE value=HERO", 1)
        p(f"tag=ZONE value={zone}", 1)
        p(f"tag=HEALTH value={health}", 1)
        if pid is not None:
            p(f"tag=PLAYER_ID value={pid}", 1)
        if place is not None:
            p(f"tag=PLAYER_LEADERBOARD_PLACE value={place}", 1)
        p(f"tag=PLAYER_TECH_LEVEL value={tier}", 1)

    def minion(eid, card, controller, atk, hp, pos, race=None, extra=()):
        p(f"FULL_ENTITY - Updating {ref(eid, card, controller, 'PLAY', pos)} CardID={card}")
        p(f"tag=CONTROLLER value={controller}", 1)
        p("tag=CARDTYPE value=MINION", 1)
        p("tag=ZONE value=PLAY", 1)
        p(f"tag=ATK value={atk}", 1)
        p(f"tag=HEALTH value={hp}", 1)
        p(f"tag=ZONE_POSITION value={pos}", 1)
        if race:
            p(f"tag=CARDRACE value={race}", 1)
        for tag, val in extra:
            p(f"tag={tag} value={val}", 1)

    def tag(eid, card, controller, name, value, zone="PLAY", indent=0):
        p(f"TAG_CHANGE Entity={ref(eid, card, controller, zone)} tag={name} value={value}", indent)

    # Bob's hero: in play all game, PLAYER_ID 0, and Bob's HERO_ENTITY
    hero(9, "TB_BaconShopBob", BOB, "PLAY", health=40)
    p(f"TAG_CHANGE Entity={BOB_NAME} tag=HERO_ENTITY value=9")
    # stale early copy of hero D - never updated again
    hero(8, "BG_HERO_D", BOB, "SETASIDE", pid=4, place=4)
    # leaderboard heroes, lobby PLAYER_ID 1..8, we are A (1)
    for i, card in enumerate("ABCDEFGH"):
        pid = i + 1
        hero(10 + i, f"BG_HERO_{card}", ME if pid == 1 else BOB, "PLAY" if pid == 1 else "SETASIDE",
             pid=pid, place=pid)
    p(f"TAG_CHANGE Entity={ME_NAME} tag=HERO_ENTITY value=10")
    p(f"TAG_CHANGE Entity={ME_NAME} tag=NEXT_OPPONENT_PLAYER_ID value=3")

    # --- round 1: recruit ----------------------------------------------------------
    p("TAG_CHANGE Entity=GameEntity tag=TURN value=1")
    minion(30, "BG_SHOP_MURLOC", BOB, 2, 1, 1, "MURLOC")
    minion(31, "BG_SHOP_BEAST", BOB, 1, 1, 2, "BEAST")
    minion(32, "BG_SHOP_MECH", BOB, 1, 2, 3, "MECHANICAL")
    p(f"BLOCK_START BlockType=PLAY Entity={ref(31, 'BG_SHOP_BEAST', BOB, 'PLAY', 2)} "
      "EffectCardId=System.Collections.Generic.List`1[System.String] EffectIndex=0 Target=0 SubOption=-1 ")
    tag(31, "BG_SHOP_BEAST", BOB, "CONTROLLER", ME, indent=1)
    tag(31, "BG_SHOP_BEAST", ME, "ZONE_POSITION", 1, indent=1)
    p("BLOCK_END")
    minion(33, "BG_SHOP_DEMON", BOB, 1, 3, 1, "DEMON")
    minion(34, "BG_SHOP_PIRATE", BOB, 3, 1, 2, "PIRATE")

    # --- round 1: combat setup (tag 3533 0 -> 1), board appears ------------------
    p("TAG_CHANGE Entity=GameEntity tag=3533 value=1")
    for eid, card in ((32, "BG_SHOP_MECH"), (33, "BG_SHOP_DEMON"), (34, "BG_SHOP_PIRATE")):
        tag(eid, card, BOB, "ZONE", "SETASIDE")
    # shop murloc 30 stays in play on purpose (must not count as C's board)
    hero(50, "BG_HERO_C", BOB, "PLAY", pid=3, place=3, tier=2)
    p("tag=ARMOR value=18", 1)  # combat copy with armor - reset to 0 when the board is cleared
    minion(51, "BG_OPP_1", BOB, 1, 2, 1, "MURLOC", extra=[("TAUNT", 1)])
    minion(52, "BG_OPP_2", BOB, 3, 3, 2, "DEMON", extra=[("DIVINE_SHIELD", 1)])
    # a buff on C's demon: enchantment entity attached to minion 52
    p(f"FULL_ENTITY - Updating {ref(53, 'BG_ENCH_BUFF', BOB, 'PLAY')} CardID=BG_ENCH_BUFF")
    p(f"tag=CONTROLLER value={BOB}", 1)
    p("tag=CARDTYPE value=ENCHANTMENT", 1)
    p("tag=ZONE value=PLAY", 1)
    p("tag=ATTACHED value=52", 1)
    p("tag=TAG_SCRIPT_DATA_NUM_1 value=1", 1)
    p("tag=TAG_SCRIPT_DATA_NUM_2 value=1", 1)
    p("TAG_CHANGE Entity=GameEntity tag=3533 value=0")
    p("TAG_CHANGE Entity=GameEntity tag=TURN value=2")

    # --- round 1: combat - our 1/1 attacks the taunt, then dies ---------------------
    p(f"BLOCK_START BlockType=ATTACK Entity={ref(31, 'BG_SHOP_BEAST', ME, 'PLAY', 1)} "
      "EffectCardId=System.Collections.Generic.List`1[System.String] EffectIndex=0 "
      f"Target={ref(51, 'BG_OPP_1', BOB, 'PLAY', 1)} SubOption=-1 ")
    tag(51, "BG_OPP_1", BOB, "DAMAGE", 1, indent=1)
    tag(31, "BG_SHOP_BEAST", ME, "DAMAGE", 1, indent=1)
    p("BLOCK_END")
    p("BLOCK_START BlockType=DEATHS Entity=GameEntity EffectCardId=System.Collections.Generic.List`1"
      "[System.String] EffectIndex=0 Target=0 SubOption=-1 ")
    tag(31, "BG_SHOP_BEAST", ME, "ZONE", "GRAVEYARD", indent=1)
    p("BLOCK_END")
    # hero damage: we lose for 4; elsewhere in the lobby D took 7 and fell to 6th
    tag(10, "BG_HERO_A", ME, "DAMAGE", 4)
    tag(13, "BG_HERO_D", BOB, "DAMAGE", 7, zone="SETASIDE")
    tag(13, "BG_HERO_D", BOB, "PLAYER_LEADERBOARD_PLACE", 6, zone="SETASIDE")
    tag(15, "BG_HERO_F", BOB, "PLAYER_LEADERBOARD_PLACE", 4, zone="SETASIDE")
    # combat board is cleared
    for eid, card in ((51, "BG_OPP_1"), (52, "BG_OPP_2")):
        tag(eid, card, BOB, "ZONE", "SETASIDE")
    tag(50, "BG_HERO_C", BOB, "ARMOR", 0)  # must not count as damage dealt
    tag(50, "BG_HERO_C", BOB, "ZONE", "SETASIDE")
    tag(31, "BG_SHOP_BEAST", ME, "ZONE", "PLAY", zone="GRAVEYARD")
    tag(31, "BG_SHOP_BEAST", ME, "DAMAGE", 0)

    # --- round 2: recruit ------------------------------------------------------------
    p("TAG_CHANGE Entity=GameEntity tag=TURN value=3")
    p(f"TAG_CHANGE Entity={ME_NAME} tag=PLAYER_TECH_LEVEL value=2")
    tag(10, "BG_HERO_A", ME, "PLAYER_TECH_LEVEL", 2)
    p(f"TAG_CHANGE Entity={ME_NAME} tag=NEXT_OPPONENT_PLAYER_ID value=5")
    # hero E levels up; a game-wide buff on our player; gold next turn; our beast gets a buff
    tag(14, "BG_HERO_E", BOB, "PLAYER_TECH_LEVEL", 2, zone="SETASIDE")
    # E makes a triple and has a trinket; our trinket arrives with its numeric tag id
    tag(14, "BG_HERO_E", BOB, "PLAYER_TRIPLES", 1, zone="SETASIDE")
    tag(14, "BG_HERO_E", BOB, "BACON_FIRST_TRINKET_DATABASE_ID", 90002, zone="SETASIDE")
    tag(10, "BG_HERO_A", ME, "3741", 90003)
    p(f"FULL_ENTITY - Updating {ref(70, 'BG_PLAYER_BUFF', ME, 'PLAY')} CardID=BG_PLAYER_BUFF")
    p(f"tag=CONTROLLER value={ME}", 1)
    p("tag=CARDTYPE value=ENCHANTMENT", 1)
    p("tag=ZONE value=PLAY", 1)
    p("tag=ATTACHED value=2", 1)
    p("tag=TAG_SCRIPT_DATA_NUM_1 value=2", 1)
    p("tag=TAG_SCRIPT_DATA_NUM_2 value=1", 1)
    p(f"TAG_CHANGE Entity={ME_NAME} tag=BACON_PLAYER_EXTRA_GOLD_NEXT_TURN value=2")
    p(f"FULL_ENTITY - Updating {ref(71, 'BG_ENCH_BUFF', ME, 'PLAY')} CardID=BG_ENCH_BUFF")
    p(f"tag=CONTROLLER value={ME}", 1)
    p("tag=CARDTYPE value=ENCHANTMENT", 1)
    p("tag=ZONE value=PLAY", 1)
    p("tag=ATTACHED value=31", 1)
    p("tag=TAG_SCRIPT_DATA_NUM_1 value=2", 1)
    p("tag=TAG_SCRIPT_DATA_NUM_2 value=2", 1)
    tag(31, "BG_SHOP_BEAST", ME, "ATK", 3)
    tag(31, "BG_SHOP_BEAST", ME, "HEALTH", 3)

    # --- game over: we finished 3rd ----------------------------------------------------
    tag(10, "BG_HERO_A", ME, "PLAYER_LEADERBOARD_PLACE", 3)
    p("TAG_CHANGE Entity=GameEntity tag=STATE value=COMPLETE")
    return log.lines


if __name__ == "__main__":
    lines = build()
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{OUT}: {len(lines)} lines")

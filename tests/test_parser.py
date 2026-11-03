from hearthwatch.power import parser as p
from hearthwatch.power.game_state import GameListener, GameState


def test_parse_tag_change_with_player_name():
    ev = p.parse_line(
        "D 20:00:01.0000000 GameState.DebugPrintPower() - TAG_CHANGE Entity=Some Name#1234 tag=HERO_ENTITY value=10 "
    )
    assert ev == p.TagChange("20:00:01.0000000", "Some Name#1234", "HERO_ENTITY", 10)


def test_parse_full_entity_and_initial_tags():
    ev = p.parse_line("D 20:00:01.0 GameState.DebugPrintPower() -     FULL_ENTITY - Creating ID=31 CardID=BG_X")
    assert ev == p.FullEntity("20:00:01.0", "31", "BG_X")
    tag = p.parse_line("D 20:00:01.0 GameState.DebugPrintPower() -         tag=ZONE value=PLAY")
    assert tag == p.InitialTag("20:00:01.0", "ZONE", "PLAY")


def test_parse_bracket_entity_reference():
    ref = "[entityName=Shop Beast id=31 zone=PLAY zonePos=2 cardId=BG_SHOP_BEAST player=13]"
    assert p.entity_id_from_ref(ref) == 31
    assert p.entity_id_from_ref("42") == 42
    assert p.entity_id_from_ref("Bartender Bob") is None


def test_parse_reports_the_source():
    line = "D 20:00:01.0 PowerTaskList.DebugPrintPower() - TAG_CHANGE Entity=GameEntity tag=TURN value=3"
    assert p.parse(line) == (p.POWER_TASK_LIST, p.TagChange("20:00:01.0", "GameEntity", "TURN", 3))
    line = "D 20:00:01.0 GameState.DebugPrintGame() - GameType=GT_BATTLEGROUNDS"
    assert p.parse(line) == (p.GAME_STATE, p.GameMeta("20:00:01.0", "GameType", "GT_BATTLEGROUNDS"))


def test_parse_task_list_entity_with_nested_brackets():
    line = ("D 20:00:01.0 PowerTaskList.DebugPrintPower() -     FULL_ENTITY - Updating "
            "[entityName=UNKNOWN ENTITY [cardType=INVALID] id=4 zone=DECK zonePos=0 cardId= player=1] CardID=")
    source, ev = p.parse(line)
    assert source == p.POWER_TASK_LIST
    assert isinstance(ev, p.FullEntity) and p.entity_id_from_ref(ev.entity) == 4 and ev.card_id == ""
    line = ("D 20:00:01.0 PowerTaskList.DebugPrintPower() - TAG_CHANGE Entity="
            "[entityName=UNKNOWN ENTITY [cardType=INVALID] id=4 zone=DECK zonePos=0 cardId= player=1] "
            "tag=ZONE value=HAND ")
    assert p.parse_line(line).tag == "ZONE"


def test_unknown_lines_are_skipped():
    assert p.parse_line("garbage") is None
    assert p.parse_line("D 20:00:01.0 GameState.DebugPrintPower() - SOMETHING_NEW foo") is None
    assert p.parse_line("D 20:00:01.0 PowerTaskList.DebugPrintPower() - SOMETHING_NEW foo") is None


def ptl(data):
    return f"D 20:00:00.0 PowerTaskList.DebugPrintPower() - {data}"


def gs_game(data):
    return f"D 20:00:00.0 GameState.DebugPrintGame() - {data}"


def test_game_info_before_and_after_the_task_list_game_start():
    for game_info_first in (True, False):
        info = [gs_game("GameType=GT_BATTLEGROUNDS"), gs_game("PlayerID=5, PlayerName=Me#1")]
        body = [
            ptl("CREATE_GAME"),
            ptl("    GameEntity EntityID=1"),
            ptl("    Player EntityID=2 PlayerID=5 GameAccountId=[hi=1 lo=2]"),
            ptl("TAG_CHANGE Entity=Me#1 tag=HERO_ENTITY value=10"),
        ]
        lines = [*info, *body] if game_info_first else [body[0], *info, *body[1:]]
        game = GameState()
        game.feed_lines(lines)
        assert game.meta["GameType"] == "GT_BATTLEGROUNDS"
        assert game.player_entity(5).name == "Me#1"
        assert game.player_entity(5).int_tag("HERO_ENTITY") == 10


def test_game_state_from_fixture(bg_log):
    events = []

    class Rec(GameListener):
        def on_game_start(self, game):
            events.append("start")

        def on_game_end(self, game):
            events.append("end")

    game = GameState([Rec()])
    game.feed_lines(bg_log.read_text().splitlines())
    assert events == ["start", "end"]
    assert game.meta["GameType"] == "GT_BATTLEGROUNDS"
    assert game.player_names == {"Tester#2345": 5, "Bartender Bob": 13}
    assert game.player_entity(5).int_tag("HERO_ENTITY") == 10
    # GameState power lines (TURN=99, next opponent 7) run ahead and must be ignored
    assert game.game_entity.int_tag("TURN") == 3
    assert game.player_entity(5).int_tag("NEXT_OPPONENT_PLAYER_ID") == 5
    assert game.entities[31].controller == 5

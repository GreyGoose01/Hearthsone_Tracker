from hearthwatch.bg.models import MatchResult, Minion
from hearthwatch.db import MatchDB


def result(key, hero, place, game_type="GT_BATTLEGROUNDS", ended="2026-11-02T20:00:00"):
    return MatchResult(
        source_key=key, started_at="20:00", ended_at=ended, game_type=game_type,
        hero_card_id=hero, hero_name=hero.title(), placement=place, rounds=10, tavern_tier=5,
        tribes=["BEAST"], final_board=[Minion("X", 5, 5, name="X", taunt=True)],
    )


def test_add_and_stats(tmp_path):
    db = MatchDB(tmp_path / "m.db")
    assert db.add(result("a", "h1", 1)) is not None
    assert db.add(result("a", "h1", 1)) is None  # duplicate source_key is ignored
    db.add(result("b", "h1", 5, ended="2026-11-02T21:00:00"))
    db.add(result("c", "h2", 2, game_type="GT_BATTLEGROUNDS_DUO", ended="2026-11-02T22:00:00"))
    matches = db.matches()
    assert [m.result.source_key for m in matches] == ["c", "b", "a"]
    assert matches[0].result.final_board[0].taunt
    s = db.summary()
    assert s.games == 3 and s.wins == 1
    assert abs(s.avg_place - 8 / 3) < 1e-9
    assert abs(s.top4_rate - 2 / 3) < 1e-9  # duo 2nd counts as top
    stats = {h.hero_card_id: h for h in db.hero_stats()}
    assert stats["h1"].games == 2 and stats["h1"].avg_place == 3
    db.set_mmr(matches[0].id, 6543)
    assert db.summary().last_mmr == 6543
    db.delete(matches[0].id)
    assert db.summary().games == 2

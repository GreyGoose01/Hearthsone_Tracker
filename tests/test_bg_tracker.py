from hearthwatch.bg.tracker import BattlegroundsTracker, max_plausible_damage
from hearthwatch.power.game_state import GameState


def run(bg_log, cards, stop_after=None, outcomes=None):
    states, combats, results = [], [], []
    tracker = BattlegroundsTracker(
        cards, states.append, combats.append, results.append,
        on_combat_result=outcomes.append if outcomes is not None else None,
    )
    tracker.source = "test"
    game = GameState([tracker])
    lines = bg_log.read_text().splitlines()
    if stop_after:
        lines = [l for l in lines][: stop_after]
    for line in lines:
        game.feed_line(line)
        tracker.batch_done(game)
    return tracker, game, states, combats, results


def test_match_result(bg_log, cards):
    _, _, states, combats, results = run(bg_log, cards)
    assert len(results) == 1
    r = results[0]
    assert r.hero_card_id == "BG_HERO_A"
    assert r.hero_name == "Held A"
    assert r.placement == 3
    assert r.rounds == 2
    assert r.tavern_tier == 2
    assert r.game_type == "GT_BATTLEGROUNDS"
    assert set(r.tribes) == {"MURLOC", "BEAST", "MECHANICAL", "DEMON", "PIRATE"}
    assert [m.card_id for m in r.final_board] == ["BG_SHOP_BEAST"]
    assert states[-1].in_game is False


def test_combat_snapshot_and_opponent_board(bg_log, cards):
    _, _, states, combats, _ = run(bg_log, cards)
    assert len(combats) == 1
    c = combats[0]
    assert c.round == 1
    assert c.opponent.hero_card_id == "BG_HERO_C"
    assert c.opponent.hero_name == "Held C"
    opp = c.opponent.minions
    assert [m.card_id for m in opp] == ["BG_OPP_1", "BG_OPP_2"]
    assert opp[0].taunt and opp[1].divine_shield
    assert opp[1].name == "Dämonchen" and opp[1].tech_level == 2
    assert c.opponent.tavern_tier == 2
    assert c.opponent_player_id == 3
    assert [m.card_id for m in c.player.minions] == ["BG_SHOP_BEAST"]
    # the opponent list remembers the board for that lobby player
    final = states[-1]
    hero_c = next(o for o in final.opponents if o.hero_card_id == "BG_HERO_C")
    assert hero_c.last_board is not None
    assert len(hero_c.last_board.minions) == 2


def test_bob_is_never_the_opponent(bg_log, cards):
    _, _, states, combats, _ = run(bg_log, cards)
    assert all("Bob" not in c.opponent.hero_name for c in combats)
    assert all("Bob" not in o.hero_name for s in states for o in s.opponents)
    # Bob's shop minion that stayed in play is not part of the opponent's board
    assert "BG_SHOP_MURLOC" not in [m.card_id for m in combats[0].opponent.minions]


def test_phase_is_combat_during_the_fight(bg_log, cards):
    _, _, states, _, _ = run(bg_log, cards)
    phases = [(s.round, s.phase) for s in states if s.in_game and s.round]
    assert (1, "combat") in phases
    assert phases[-1] == (2, "recruit")


def test_real_combat_outcome(bg_log, cards):
    outcomes = []
    _, _, states, combats, _ = run(bg_log, cards, outcomes=outcomes)
    assert len(outcomes) == 1
    assert outcomes[0].round == 1
    assert outcomes[0].actual.result == "loss" and outcomes[0].actual.damage == 4
    assert outcomes[0].actual.text() == "Niederlage, 4 Schaden"
    assert states[-1].last_combat.actual.result == "loss"
    assert combats[0].actual is None  # at combat start the outcome is unknown


def test_lobby_uses_the_newest_hero_entity(bg_log, cards):
    _, _, states, _, _ = run(bg_log, cards)
    s = [s for s in states if s.in_game and s.round == 2][-1]
    d = next(o for o in s.opponents if o.hero_card_id == "BG_HERO_D")
    # entity 8 is a stale copy (place 4, 30 health); entity 13 got 7 damage and fell to 6th
    assert (d.place, d.health, d.lobby_player_id) == (6, 23, 4)
    assert len({o.lobby_player_id for o in s.opponents}) == 8
    e = next(o for o in s.opponents if o.hero_card_id == "BG_HERO_E")
    assert e.is_next_opponent and not d.is_next_opponent


def test_live_state_during_game(bg_log, cards):
    _, _, states, _, _ = run(bg_log, cards)
    live = [s for s in states if s.in_game and s.round == 2]
    assert live, "expected live updates in round 2"
    s = live[-1]
    assert s.is_battlegrounds
    assert s.phase == "recruit"
    assert s.tavern_tier == 2
    assert s.health == 26
    assert s.next_opponent == "BG_HERO_E"  # lobby player id 5, no card data -> id
    assert len(s.opponents) == 8
    assert sum(o.is_me for o in s.opponents) == 1
    assert sorted(s.tribes_banned) == ["DRAGON", "ELEMENTAL", "NAGA", "QUILBOAR", "UNDEAD"]


def test_names_are_fixed_when_card_data_arrives_later(bg_log, cards):
    from hearthwatch.cards import CardDB

    states = []
    tracker = BattlegroundsTracker(CardDB(), on_state=states.append)
    game = GameState([tracker])
    lines = bg_log.read_text().splitlines()
    cut = next(i for i, l in enumerate(lines) if "tag=STATE value=COMPLETE" in l)
    for line in lines[:cut]:
        game.feed_line(line)
    tracker.batch_done(game)
    assert states[-1].last_combat.opponent.hero_name == "BG_HERO_C"  # no card data yet
    assert not tracker.unknown_cards  # empty card data is not "unknown cards"

    tracker.cards = cards
    tracker.relabel()
    tracker.batch_done(game)
    s = states[-1]
    assert s.last_combat.opponent.hero_name == "Held C"
    assert [m.name for m in s.last_combat.opponent.minions] == ["BG_OPP_1", "Dämonchen"]
    hero_c = next(o for o in s.opponents if o.hero_card_id == "BG_HERO_C")
    assert hero_c.hero_name == "Held C"
    assert hero_c.last_board.minions[1].name == "Dämonchen"
    assert s.hero_name == "Held A"
    # cards missing from the (partial) card data are reported
    assert "BG_OPP_1" in tracker.unknown_cards and "BG_OPP_2" not in tracker.unknown_cards


def test_non_battlegrounds_game_is_ignored(cards):
    lines = [
        "D 20:00:00.0 GameState.DebugPrintPower() - CREATE_GAME",
        "D 20:00:00.2 GameState.DebugPrintGame() - GameType=GT_RANKED",
        "D 20:00:00.3 PowerTaskList.DebugPrintPower() - CREATE_GAME",
        "D 20:00:00.4 PowerTaskList.DebugPrintPower() -     GameEntity EntityID=1",
        "D 20:00:00.5 PowerTaskList.DebugPrintPower() - TAG_CHANGE Entity=GameEntity tag=STATE value=COMPLETE",
    ]
    results, ended = [], []

    class Ended(BattlegroundsTracker):
        def on_game_end(self, game):
            ended.append(True)
            super().on_game_end(game)

    tracker = Ended(cards, on_match_end=results.append)
    game = GameState([tracker])
    game.feed_lines(lines)
    assert ended == [True]  # the game was followed to its end ...
    assert results == []  # ... but is not a Battlegrounds game


def test_a_failing_snapshot_is_retried_and_logged(bg_log, cards, caplog, monkeypatch):
    outcomes = []
    calls = {"n": 0}
    real = BattlegroundsTracker._take_combat_snapshot

    def flaky(self, game):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")
        return real(self, game)

    monkeypatch.setattr(BattlegroundsTracker, "_take_combat_snapshot", flaky)
    with caplog.at_level("INFO"):
        _, _, states, combats, results = run(bg_log, cards, outcomes=outcomes)
    # the game goes on: placement saved, and the snapshot was retried at the next attack block
    assert [r.placement for r in results] == [3]
    assert calls["n"] >= 1
    assert "combat snapshot failed" in caplog.text


def test_listener_errors_do_not_stop_the_game_state(bg_log):
    from hearthwatch.power.game_state import GameListener

    class Broken(GameListener):
        def on_tag_change(self, game, entity, tag, old, new):
            raise ValueError("listener bug")

    ended = []

    class Ok(GameListener):
        def on_game_end(self, game):
            ended.append(True)

    game = GameState([Broken(), Ok()])
    game.feed_lines(bg_log.read_text().splitlines())
    assert ended == [True]


def test_game_over_summary(bg_log, cards):
    _, _, states, _, _ = run(bg_log, cards)
    final = states[-1]
    assert final.in_game is False
    assert final.summary is not None and final.summary.placement == 3
    assert [c.round for c in final.combat_log] == [1]
    assert final.combat_log[0].actual.result == "loss"


def test_buffs_are_attached_to_minions(bg_log, cards):
    _, _, states, combats, _ = run(bg_log, cards)
    opp = combats[0].opponent.minions
    assert opp[0].buffs == []
    assert opp[1].buffs == ["Teufelsstärke (1/1)"]
    hero_c = next(o for o in states[-1].opponents if o.hero_card_id == "BG_HERO_C")
    assert hero_c.last_board.minions[1].buffs == ["Teufelsstärke (1/1)"]


def test_identical_buffs_are_grouped(cards):
    from hearthwatch.power.entities import Entity

    tracker = BattlegroundsTracker(cards)
    e = lambda i: Entity(i, "BG_ENCH_BUFF", {"TAG_SCRIPT_DATA_NUM_1": 2, "TAG_SCRIPT_DATA_NUM_2": 2})
    assert tracker._buffs([e(1), e(2), Entity(3, "BG_ENCH_BUFF")]) == ["Teufelsstärke (2/2) ×2", "Teufelsstärke"]


def test_details_explain_the_snapshot(bg_log, cards):
    tracker = BattlegroundsTracker(cards)
    tracker.collect_details = True
    game = GameState([tracker])
    game.feed_lines(bg_log.read_text().splitlines())
    text = tracker.last_details
    assert "Deine Diener im Kampf" in text and "#31 Wildschwein" in text
    assert "Buff: Teufelsstärke (1/1)" in text


def test_resetting_a_combat_copy_is_not_damage(bg_log, cards, caplog):
    tracker = BattlegroundsTracker(cards)
    game = GameState([tracker])
    with caplog.at_level("INFO"):
        game.feed_lines(bg_log.read_text().splitlines())
    combat = tracker.state.combat_log[0]
    assert combat.actual.result == "loss" and combat.actual.damage == 4
    # health lost according to the lobby: we lost 4, C lost nothing (its copy's armor reset is ignored)
    assert "after me=4 opp=0" in caplog.text
    assert "tag sums me=4 opp=0" in caplog.text


def _outcome_with_damage(cards, damage):
    """Finish a fake combat in which we lost ``damage`` health according to the lobby."""
    from hearthwatch.bg.models import BoardSnapshot, CombatSnapshot

    tracker = BattlegroundsTracker(cards)
    combat = CombatSnapshot(
        round=12,
        player=BoardSnapshot(12, "BG_HERO_A", "Held A", 6),
        opponent=BoardSnapshot(12, "BG_HERO_C", "Held C", 7),
    )
    tracker._current = combat
    tracker._counts = (0, 7)  # we lost
    tracker._hp_loss = lambda game, side: damage if side == "me" else 0
    tracker._finish_combat(game=object())
    return combat.actual


def test_high_late_game_damage_is_kept(cards):
    assert max_plausible_damage(7) > 56
    actual = _outcome_with_damage(cards, 52)
    assert actual.result == "loss" and actual.damage == 52


def test_impossible_damage_is_discarded(cards):
    actual = _outcome_with_damage(cards, 200)
    assert actual.result == "loss" and actual.damage is None


def test_live_board_buffs_and_counters(bg_log, cards):
    _, _, states, _, _ = run(bg_log, cards)
    s = [s for s in states if s.in_game and s.round == 2 and s.phase == "recruit"][-1]
    assert [(m.card_id, m.attack, m.health) for m in s.my_board] == [("BG_SHOP_BEAST", 3, 3)]
    assert s.my_board[0].buffs == ["Teufelsstärke (2/2)"]
    assert s.player_buffs == ["Blutedelstein-Bonus (2/1)"]
    assert s.counters == ["Gold nächste Runde +2"]


def test_lobby_details(bg_log, cards):
    _, _, states, _, _ = run(bg_log, cards)
    s = [s for s in states if s.in_game and s.round == 2][-1]
    by_card = {o.hero_card_id: o for o in s.opponents}
    e, c, d = by_card["BG_HERO_E"], by_card["BG_HERO_C"], by_card["BG_HERO_D"]
    assert e.tier_up_round == 2 and e.tavern_tier == 2
    assert (c.wins, c.draws, c.losses) == (0, 0, 1)  # we lost round 1 against C
    assert c.main_tribe in ("MURLOC", "DEMON")
    assert d.max_health == 30 and abs(d.health_fraction - 23 / 30) < 1e-9

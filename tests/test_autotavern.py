"""The AutoTavern adapter with a stand-in for the compiled module (CI has no Rust build)."""

import json

import pytest

from hearthwatch.bg.models import BoardSnapshot, CombatSnapshot, Minion
from hearthwatch.sim import autotavern
from hearthwatch.sim.montecarlo import simulate_combat


class FakeGame:
    """Records the debug commands; knows a few cards; answers previews."""

    known = {"BG_KNOWN", "BG_GOLD"}

    def __init__(self, seed=1, config=None, log=None, trials=None):
        self.config = config
        self.log = log if log is not None else []
        self.trials = trials or []
        self.pending = {p: 0 for p in range(8)}

    @property
    def num_players(self):
        return 8

    def view(self, p):
        return json.dumps({"actions": {"CHOOSE": 0}, "me": {"pending": None}})

    def step(self, p, action):
        pass

    def copy(self):
        return FakeGame(log=self.log, trials=self.trials)

    def debug(self, cmd_json):
        cmd = json.loads(cmd_json)
        self.log.append(cmd)
        if cmd["cmd"] == "add_minion" and cmd["card"] not in self.known:
            raise ValueError(f"unknown card id {cmd['card']}")
        if cmd["cmd"] == "combat_preview":
            return json.dumps({"n": len(self.trials), "trials": self.trials})
        return json.dumps({"ok": True})


@pytest.fixture
def fake(monkeypatch):
    log = []
    trials = (
        [{"winner": 0, "damage_dealt": 30, "damage_taken": 0}] * 2
        + [{"winner": 1, "damage_dealt": 0, "damage_taken": 20}] * 1
        + [{"winner": 2, "damage_dealt": 0, "damage_taken": 0}] * 1
    )

    class Core:
        @staticmethod
        def Game(seed, config):
            return FakeGame(seed, config, log, trials)

        @staticmethod
        def game_version():
            return "36.6.3"

    monkeypatch.setattr(autotavern, "_core", Core)
    monkeypatch.setattr(autotavern, "_failed", False)
    monkeypatch.setattr(autotavern, "_template", None)
    return log


def snapshot(minions, cap=10):
    me = BoardSnapshot(round=4, hero_card_id="TB_BaconShop_HERO_28_SKIN_A", hero_name="Me", tavern_tier=3,
                       minions=minions)
    them = BoardSnapshot(round=4, hero_card_id="H2", hero_name="Them", tavern_tier=2,
                         minions=[Minion("BG_KNOWN", 2, 2)])
    return CombatSnapshot(round=4, player=me, opponent=them, damage_cap=cap)


def test_boards_are_set_up_with_stats_keywords_and_golden_fallback(fake):
    mine = [Minion("BG_KNOWN", 7, 9, taunt=True, divine_shield=True, windfury=3),
            Minion("BG_GOLD_G", 4, 4, golden=True)]
    r = autotavern.simulate_combat(snapshot(mine), player_health=15)
    assert r.engine == "autotavern"
    turn = next(c for c in fake if c["cmd"] == "set_turn")
    assert turn["turn"] == 4
    heroes = [c["hero"] for c in fake if c["cmd"] == "set_hero"]
    assert heroes[0] == "TB_BaconShop_HERO_28"  # skin stripped
    edits = [c for c in fake if c["cmd"] == "edit_minion" and c["p"] == 0]
    assert edits[0] == {"cmd": "edit_minion", "p": 0, "zone": "board", "index": 0, "atk": 7, "hp": 9,
                        "keywords": ["TAUNT", "DIVINE_SHIELD", "MEGA_WINDFURY"]}
    adds = [c for c in fake if c["cmd"] == "add_minion" and c["p"] == 0]
    assert adds[-1]["card"] == "BG_GOLD" and adds[-1]["golden"] is True  # "_G" id -> base + golden
    preview = next(c for c in fake if c["cmd"] == "combat_preview")
    assert preview["details"] is True


def test_odds_damage_cap_and_lethal(fake):
    r = autotavern.simulate_combat(snapshot([Minion("BG_KNOWN", 1, 1)], cap=10), player_health=10)
    assert (r.win, r.loss, r.draw) == (0.5, 0.25, 0.25)
    assert r.avg_damage_dealt == 10 and r.avg_damage_taken == 10  # 30 / 20 capped at 10
    assert r.lethal_risk == 0.25  # the capped 10 damage kills at 10 health
    r = autotavern.simulate_combat(snapshot([Minion("BG_KNOWN", 1, 1)], cap=0), player_health=25)
    assert r.avg_damage_taken == 20 and r.lethal_risk == 0.0


def test_unknown_card_falls_back_to_the_builtin_simulator(fake):
    snap = snapshot([Minion("BG_NEW_SEASON", 3, 3)])
    assert autotavern.simulate_combat(snap) is None
    result = simulate_combat(snap, runs=20, seed=1)
    assert result.engine == "builtin"


def test_without_autotavern_the_builtin_simulator_runs(monkeypatch):
    monkeypatch.setattr(autotavern, "_core", None)
    monkeypatch.setattr(autotavern, "_failed", True)
    assert not autotavern.available()
    assert simulate_combat(snapshot([Minion("BG_KNOWN", 1, 1)]), runs=10, seed=1).engine == "builtin"


def test_beetle_and_undead_strength_are_set_before_the_minions(fake):
    snap = snapshot([Minion("BG_KNOWN", 1, 1)])
    snap.player.beetle = (6, 4)
    snap.player.undead_attack = 3
    snap.player.lobster_bonus = 2
    autotavern.simulate_combat(snap, player_health=40)
    cmds = [c["cmd"] for c in fake]
    stats = [c for c in fake if c["cmd"] == "set_stats"]
    assert stats == [{"cmd": "set_stats", "p": 0, "stats": {"beetle_atk": 4, "beetle_hp": 2, "undead_atk": 3,
                                                               "lobster_bonus": 2}}]
    assert cmds.index("set_stats") < cmds.index("add_minion")  # the opponent (unknown Beetles) gets none

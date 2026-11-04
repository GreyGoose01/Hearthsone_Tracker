import random

from hearthwatch.bg.models import Minion
from hearthwatch.sim.effects import DEATHRATTLES
from hearthwatch.sim.engine import Combat, Side, Unit, simulate_once
from hearthwatch.sim.montecarlo import simulate


def m(atk, hp, **kw):
    return Minion(card_id=kw.pop("card_id", "X"), name=kw.pop("name", "X"), attack=atk, health=hp, **kw)


def test_bigger_minion_wins_and_damage():
    res = simulate([m(5, 5, tech_level=3)], [m(1, 1)], 2, 1, runs=50, seed=1)
    assert res.win == 1.0
    assert res.avg_damage_dealt == 2 + 3


def test_mirror_is_draw():
    res = simulate([m(2, 2)], [m(2, 2)], 1, 1, runs=50, seed=1)
    assert res.draw == 1.0


def test_divine_shield_beats_equal_minion():
    res = simulate([m(2, 2, divine_shield=True)], [m(2, 2)], 1, 1, runs=100, seed=2)
    assert res.win == 1.0


def test_venomous_kills_big_minion():
    res = simulate([m(1, 1, venomous=True)], [m(1, 10)], 1, 1, runs=100, seed=3)
    assert res.draw == 1.0  # both die: 1 damage kills the venomous minion too


def test_reborn_comes_back():
    res = simulate([m(3, 3, reborn=True)], [m(3, 3), m(1, 1)], 1, 1, runs=200, seed=4)
    assert res.loss < 1.0


def test_taunt_is_attacked_first():
    for seed in range(20):
        combat = Combat(
            player=Side([Unit("A", "A", 1, 10)], 1),
            opponent=Side([Unit("T", "T", 0, 1, taunt=True), Unit("B", "B", 0, 5)], 1),
            rng=random.Random(seed),
        )
        combat.attack(combat.player, 0)
        assert [u.card_id for u in combat.opponent.units] == ["B"]


def test_windfury_attacks_twice():
    res = simulate([m(2, 10, windfury=1)], [m(0, 2), m(0, 2)], 1, 1, runs=50, seed=5)
    assert res.win == 1.0


def test_cleave_hits_neighbours():
    out = simulate_once([m(2, 10, cleave=True)], [m(0, 2), m(0, 2, taunt=True), m(0, 2)], 1, 1, random.Random(0))
    assert out.result == "win"


def test_registered_deathrattle_summons_token():
    assert "Harvest Golem" in DEATHRATTLES
    golem = m(2, 3, deathrattle=True, name="Harvest Golem")
    res = simulate([golem], [m(3, 3)], 1, 1, runs=100, seed=6)
    # golem dies, its 2/1 token trades with the damaged 3/3 -> draw
    assert res.draw == 1.0
    assert res.exact
    plain = simulate([m(2, 3)], [m(3, 3)], 1, 1, runs=100, seed=6)
    assert plain.loss == 1.0


def test_unknown_deathrattle_is_reported():
    res = simulate([m(1, 1, deathrattle=True, name="Mystery")], [m(1, 1)], 1, 1, runs=10, seed=7)
    assert res.unsupported == ["Mystery"]
    assert not res.exact


def test_lethal_risk():
    res = simulate([m(1, 1)], [m(5, 5, tech_level=6)], 1, 6, runs=20, seed=8, player_health=10)
    assert res.loss == 1.0 and res.lethal_risk == 1.0


def test_damage_cap_limits_damage_and_lethal_risk():
    # 6 tier-6 minions against an empty board: 6 + 6*6 = 42 damage without the cap
    big = [m(10, 10, tech_level=6) for _ in range(6)]
    uncapped = simulate([], big, 1, 6, runs=20, seed=1, player_health=20)
    assert uncapped.avg_damage_taken == 42 and uncapped.lethal_risk == 1.0
    capped = simulate([], big, 1, 6, runs=20, seed=1, player_health=20, damage_cap=15)
    assert capped.avg_damage_taken == 15 and capped.lethal_risk == 0.0

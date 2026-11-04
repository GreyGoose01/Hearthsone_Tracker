from hearthwatch.bg import pool
from hearthwatch.cards import card_text


def names(groups):
    return [(g.tribe, g.available, [c.name for c in g.cards]) for g in groups]


def test_unknown_lobby_keeps_everything_but_marks_unseen_types(pool_cards):
    minions = pool.lobby_minions(pool_cards, tribes_seen=["BEAST"])
    assert {c.id for c in minions} == {"P_NEUTRAL", "P_BEAST1", "P_DEMON1", "P_DUAL", "P_NAGA", "P_ALL"}
    assert pool.tiers(minions) == [1, 2, 3]
    assert names(pool.groups(minions, 1, tribes_seen=["BEAST"])) == [
        ("", True, ["Zauberlehrling"]),
        ("BEAST", True, ["Alleykatze"]),
        ("DEMON", None, ["Wichtel"]),
    ]


def test_known_lobby_drops_banned_types(pool_cards):
    seen, banned = ["BEAST", "MURLOC", "PIRATE", "UNDEAD", "DRAGON"], ["DEMON", "NAGA", "MECHANICAL"]
    minions = pool.lobby_minions(pool_cards, seen, banned)
    assert "P_DEMON1" not in {c.id for c in minions} and "P_NAGA" not in {c.id for c in minions}
    tier2 = names(pool.groups(minions, 2, seen, banned))
    assert tier2 == [("BEAST", True, ["Mischling"]), ("UNDEAD", True, ["Mischling"])]
    assert names(pool.groups(minions, 3, seen, banned)) == [("", True, ["Amalgam"])]


def test_duos_only_minions_only_in_duos(pool_cards):
    assert "P_DUOS" in {c.id for c in pool.lobby_minions(pool_cards, duos=True)}
    assert "P_DUOS" not in {c.id for c in pool.lobby_minions(pool_cards)}


def test_card_text_is_plain():
    raw = "<b>Kampfschrei:</b> Erhaltet 2_<b>Blutedelsteine</b>.\n[x]Verursacht $3 Schaden."
    assert card_text(raw) == "Kampfschrei: Erhaltet 2 Blutedelsteine. Verursacht 3 Schaden."


def test_card_text_drops_game_placeholders():
    raw = "Verleiht +{0}/+{1}, wenn Ihr einen Gasthaus[d]zauber wirkt. {0} |4(Zug, Züge) früher.@(Noch {0}!)"
    assert card_text(raw) == "Verleiht +X/+X, wenn Ihr einen Gasthauszauber wirkt. X Züge früher."
    assert card_text("Kostet Leben statt Gold. (@Noch {0}!)") == "Kostet Leben statt Gold."

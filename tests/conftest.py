from pathlib import Path

import pytest

from hearthwatch.cards import CardDB

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def bg_log() -> Path:
    return FIXTURES / "bg_game.log"


@pytest.fixture
def cards() -> CardDB:
    return CardDB([
        {"id": "BG_HERO_A", "name": "Held A", "type": "HERO"},
        {"id": "BG_HERO_C", "name": "Held C", "type": "HERO"},
        {"id": "TB_BaconShopBob", "name": "Bob der Braumeister", "type": "HERO"},
        {"id": "BG_ENCH_BUFF", "name": "Teufelsstärke", "type": "ENCHANTMENT"},
        {"id": "BG_PLAYER_BUFF", "name": "Blutedelstein-Bonus", "type": "ENCHANTMENT"},
        {"id": "BG_SHOP_BEAST", "name": "Wildschwein", "type": "MINION", "races": ["BEAST"], "techLevel": 1},
        {"id": "BG_OPP_2", "name": "Dämonchen", "type": "MINION", "races": ["DEMON"], "techLevel": 2},
        {"id": "BG_ANOMALY_X", "dbfId": 90001, "name": "Große Anomalie", "type": "BATTLEGROUND_ANOMALY",
         "text": "<b>Alle</b> Diener haben +1/+1."},
        {"id": "BG_TRINKET_X", "dbfId": 90002, "name": "Glücksmünze", "type": "BATTLEGROUND_TRINKET"},
        {"id": "BG_TRINKET_Y", "dbfId": 90003, "name": "Kristallkugel", "type": "BATTLEGROUND_TRINKET"},
    ])


@pytest.fixture(autouse=True)
def german():
    """Most tests check the German texts; language is reset afterwards."""
    from hearthwatch import i18n

    i18n.set_language("de")
    yield
    i18n.set_language("en")


@pytest.fixture
def pool_cards() -> CardDB:
    """A tiny tavern pool: neutral, single and dual types, a duos-only and a non-pool card."""
    def m(cid, name, tier, races=(), **extra):
        return {"id": cid, "dbfId": abs(hash(cid)) % 100000, "name": name, "type": "MINION", "races": list(races),
                "techLevel": tier, "attack": tier, "health": tier, "isBattlegroundsPoolMinion": True, **extra}
    return CardDB([
        m("P_NEUTRAL", "Zauberlehrling", 1),
        m("P_BEAST1", "Alleykatze", 1, ["BEAST"]),
        m("P_DEMON1", "Wichtel", 1, ["DEMON"]),
        m("P_DUAL", "Mischling", 2, ["BEAST", "UNDEAD"]),
        m("P_NAGA", "Seelenfänger", 2, ["NAGA"]),
        m("P_ALL", "Amalgam", 3, ["ALL"]),
        m("P_DUOS", "Duo-Diener", 1, ["BEAST"], isBattlegroundsDuosExclusive=True),
        {"id": "P_TOKEN", "name": "Token", "type": "MINION", "races": ["BEAST"], "techLevel": 1},
    ])

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
    ])


@pytest.fixture(autouse=True)
def german():
    """Most tests check the German texts; language is reset afterwards."""
    from hearthwatch import i18n

    i18n.set_language("de")
    yield
    i18n.set_language("en")

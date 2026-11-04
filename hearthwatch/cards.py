"""Card data from HearthstoneJSON (https://hearthstonejson.com).

The full card list is downloaded once, reduced to the fields the tracker
needs and cached in ``~/.cache/hearthwatch/cards-<locale>-v<N>.json``. Everything
works without card data too: names then fall back to card IDs and tribes to
the ``CARDRACE`` tag from the log.
"""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from hearthwatch.i18n import N_, _

log = logging.getLogger(__name__)

CARDS_URL = "https://api.hearthstonejson.com/v1/latest/{locale}/cards.json"
MAX_AGE = 3 * 24 * 3600  # refresh after a few days (patches)
CACHE_VERSION = 2  # bump when _KEEP changes, so old caches are downloaded again

BG_TRIBES = (
    "BEAST", "DEMON", "DRAGON", "ELEMENTAL", "MECHANICAL",
    "MURLOC", "NAGA", "PIRATE", "QUILBOAR", "UNDEAD", "ABERRATION",
)

TRIBE_NAMES = {
    "BEAST": N_("Beast"),
    "DEMON": N_("Demon"),
    "DRAGON": N_("Dragon"),
    "ELEMENTAL": N_("Elemental"),
    "MECHANICAL": N_("Mech"),
    "MURLOC": N_("Murloc"),
    "NAGA": N_("Naga"),
    "PIRATE": N_("Pirate"),
    "QUILBOAR": N_("Quilboar"),
    "UNDEAD": N_("Undead"),
    "ABERRATION": N_("Aberration"),
    "ALL": N_("All"),
}


def tribe_name(tribe: str) -> str:
    """Display name of a minion type (``BEAST`` -> "Beast" / "Wildtier")."""
    if not tribe:
        return ""
    return _(TRIBE_NAMES[tribe]) if tribe in TRIBE_NAMES else tribe.title()


_TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")
_INTERNAL_RE = re.compile(r"\s*[\[(]DNT[\])]\s*")
_ENCHANT_SUFFIX_RE = re.compile(r"\s+Player\s+Ench(ant(ment)?)?\b.*$|\s+Ench(ant(ment)?)?$", re.I)


def is_internal_name(name: str) -> bool:
    """Blizzard's internal helper cards are marked "[DNT]" (do not translate)."""
    return bool(_INTERNAL_RE.search(name or ""))


def buff_name(name: str) -> str:
    """Readable name of an enchantment: without "[DNT]" and "Player Enchant" parts.

    "Persistent Poet Player Enchant [DNT]" -> "Persistent Poet",
    "Spielerverzauberung: Blutedelstein" -> "Blutedelstein".
    """
    text = _INTERNAL_RE.sub(" ", name or "").strip()
    text = re.sub(r"^Spielerverzauberung:\s*", "", text)
    text = text.replace("_", " ")
    return _ENCHANT_SUFFIX_RE.sub("", text).strip() or (name or "").strip()


def card_text(text: str, values: tuple[int, ...] | list[int] = ()) -> str:
    """Card text as plain text: no markup, no layout markers, one line.

    ``values`` fill the game's ``{0}``, ``{1}`` ... (TAG_SCRIPT_DATA_NUM_1, _2 ...);
    without them the numbers show as "X".
    """
    if not text:
        return ""
    text = text.split("@", 1)[0]  # "@" starts an alternative text the game swaps in
    text = _TAG_RE.sub("", text).replace("[x]", "")
    text = re.sub(r"\[[a-z]\]", "", text)  # grammar markers, e.g. "Gasthaus[d]zauber"
    text = re.sub(r"\|4\(([^,()]*),\s*([^()]*)\)", r"\2", text)  # "|4(Zug, Züge)" -> plural
    def value(m: re.Match) -> str:
        i = int(m.group(1))
        return str(values[i]) if i < len(values) else "X"

    text = re.sub(r"\{(\d+)\}", value, text)  # values the game fills in during a match
    text = re.sub(r"[$#](\d)", r"\1", text)  # $3 / #3: spell damage / healing markers
    text = text.replace("_", " ").replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()
    if text.count("(") > text.count(")"):  # "(" whose ")" was in the alternative text
        text = text[:text.rindex("(")].rstrip()
    return text


_KEEP = (
    "id", "dbfId", "name", "type", "race", "races", "techLevel", "attack", "health",
    "mechanics", "text", "isBattlegroundsPoolMinion", "battlegroundsPremiumDbfId",
    "battlegroundsNormalDbfId", "isBattlegroundsDuosExclusive",
)

_SKIN_RE = re.compile(r"_SKIN_[A-Z0-9]+$")


def hero_base_id(card_id: str) -> str:
    """Strip hero skin suffixes so statistics group skins with their hero."""
    return _SKIN_RE.sub("", card_id)


def is_placeholder_hero(card_id: str) -> bool:
    """The stand-in hero (Bob, ``TB_BaconShop_HERO_PH``) you have while picking a hero."""
    return hero_base_id(card_id).startswith("TB_BaconShop_HERO_PH")


@dataclass(frozen=True)
class CardInfo:
    id: str
    name: str
    card_type: str = ""
    races: tuple[str, ...] = ()
    tech_level: int = 0
    attack: int = 0
    health: int = 0
    mechanics: frozenset[str] = field(default_factory=frozenset)
    text: str = ""
    dbf_id: int = 0
    bg_pool: bool = False  # minion in the Battlegrounds tavern pool
    duos_only: bool = False


class CardDB:
    def __init__(self, cards: list[dict] | None = None, en_names: dict[str, str] | None = None,
                 en_texts: dict[str, str] | None = None) -> None:
        self._by_id: dict[str, CardInfo] = {}
        self._by_dbf: dict[int, CardInfo] = {}
        self._en: dict[str, str] = dict(en_names or {})
        self._en_text: dict[str, str] = dict(en_texts or {})
        if cards:
            self._load(cards)
            if en_names is None:
                self._en = {cid: info.name for cid, info in self._by_id.items()}

    def __len__(self) -> int:
        return len(self._by_id)

    def _load(self, cards: list[dict]) -> None:
        for raw in cards:
            cid = raw.get("id")
            if not cid:
                continue
            races = raw.get("races") or ([raw["race"]] if raw.get("race") else [])
            self._by_id[cid] = CardInfo(
                id=cid,
                name=raw.get("name") or cid,
                card_type=raw.get("type", ""),
                races=tuple(races),
                tech_level=int(raw.get("techLevel") or 0),
                attack=int(raw.get("attack") or 0),
                health=int(raw.get("health") or 0),
                mechanics=frozenset(raw.get("mechanics") or ()),
                text=raw.get("text") or "",
                dbf_id=int(raw.get("dbfId") or 0),
                bg_pool=bool(raw.get("isBattlegroundsPoolMinion")),
                duos_only=bool(raw.get("isBattlegroundsDuosExclusive")),
            )
            if self._by_id[cid].dbf_id:
                self._by_dbf[self._by_id[cid].dbf_id] = self._by_id[cid]

    def get(self, card_id: str) -> CardInfo | None:
        return self._by_id.get(card_id) or self._by_id.get(hero_base_id(card_id))

    def by_dbf(self, dbf_id: int) -> CardInfo | None:
        return self._by_dbf.get(dbf_id)

    def bg_minions(self) -> list[CardInfo]:
        """All minions of the Battlegrounds tavern pool."""
        return [c for c in self._by_id.values() if c.bg_pool and c.tech_level > 0]

    def name(self, card_id: str) -> str:
        info = self.get(card_id)
        return info.name if info else (card_id or "?")

    def en_name(self, card_id: str) -> str:
        """English name - the simulator's effect registry is keyed by it."""
        return self._en.get(card_id) or self._en.get(hero_base_id(card_id)) or self.name(card_id)

    def text(self, card_id: str) -> str:
        """Card text in this language; the English one if it has none here."""
        info = self.get(card_id)
        return (info.text if info else "") or self._en_text.get(card_id, "")

    def races(self, card_id: str) -> tuple[str, ...]:
        info = self.get(card_id)
        return info.races if info else ()

    def tech_level(self, card_id: str) -> int:
        info = self.get(card_id)
        return info.tech_level if info else 0

    # -- loading -------------------------------------------------------
    @classmethod
    def from_file(cls, path: Path, en_path: Path | None = None) -> "CardDB":
        with path.open(encoding="utf-8") as fh:
            cards = json.load(fh)
        en_names = en_texts = None
        if en_path is not None and en_path != path and en_path.exists():
            with en_path.open(encoding="utf-8") as fh:
                en_cards = [c for c in json.load(fh) if "id" in c]
            en_names = {c["id"]: c.get("name", c["id"]) for c in en_cards}
            en_texts = {c["id"]: c["text"] for c in en_cards if c.get("text")}
        return cls(cards, en_names, en_texts)

    @staticmethod
    def cache_file(cache_dir: Path, locale: str) -> Path:
        return cache_dir / f"cards-{locale}-v{CACHE_VERSION}.json"

    @staticmethod
    def cache_age(cache_dir: Path, locale: str = "deDE") -> float | None:
        """Seconds since the card data for ``locale`` was downloaded (None: no cache)."""
        cache = CardDB.cache_file(cache_dir, locale)
        try:
            return time.time() - cache.stat().st_mtime
        except OSError:
            return None

    @classmethod
    def load(
        cls, cache_dir: Path, locale: str = "deDE", download: bool = True, force: bool = False
    ) -> "CardDB":
        """Load cached data, refreshing it from HearthstoneJSON when stale.

        ``download=False`` only reads the local cache (fast, for the start);
        ``force=True`` downloads even if the cache is fresh (e.g. unknown
        cards of a new season). English data is always fetched as well: the
        simulator matches card effects by English name.
        """
        locales = ["enUS"] if locale == "enUS" else [locale, "enUS"]
        files = {loc: cls.cache_file(cache_dir, loc) for loc in locales}
        for loc, cache in files.items():
            fresh = cache.exists() and time.time() - cache.stat().st_mtime < MAX_AGE
            if download and (force or not fresh):
                try:
                    cls.download(cache, loc)
                except Exception as exc:  # offline etc. - fall back to the old cache
                    log.warning("could not download card data (%s): %s", loc, exc)
        main = files[locale] if files[locale].exists() else files["enUS"]
        if main.exists():
            try:
                return cls.from_file(main, files["enUS"])
            except (OSError, ValueError, KeyError) as exc:
                log.warning("broken card cache %s: %s", main, exc)
        return cls()

    @staticmethod
    def download(target: Path, locale: str = "deDE", timeout: float = 60.0) -> None:
        url = CARDS_URL.format(locale=locale)
        req = urllib.request.Request(url, headers={"User-Agent": "hearthwatch/0.4"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            cards = json.load(resp)
        reduced = [{k: c[k] for k in _KEEP if k in c} for c in cards]
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".tmp")
        tmp.write_text(json.dumps(reduced, ensure_ascii=False), encoding="utf-8")
        tmp.replace(target)

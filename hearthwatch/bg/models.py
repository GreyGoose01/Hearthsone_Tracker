"""Plain data objects handed from the parsing thread to the UI and database."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from hearthwatch.i18n import N_, _


@dataclass
class Minion:
    card_id: str
    attack: int
    health: int
    name: str = ""
    golden: bool = False
    taunt: bool = False
    divine_shield: bool = False
    reborn: bool = False
    venomous: bool = False  # poisonous and venomous behave the same in combat
    windfury: int = 0  # 0 = none, 1 = windfury, 3 = mega-windfury
    cleave: bool = False
    deathrattle: bool = False
    tribes: tuple[str, ...] = ()
    tech_level: int = 1
    buffs: list[str] = field(default_factory=list)  # enchantments on the minion, e.g. "Mrglmrgl! ×2"
    buff_texts: list[str] = field(default_factory=list)  # what each buff does (same order as buffs)
    text: str = ""  # card text, plain, with this minion's values

    def to_dict(self) -> dict:
        d = asdict(self)
        d["tribes"] = list(self.tribes)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Minion":
        d = dict(d)
        d["tribes"] = tuple(d.get("tribes") or ())
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})

    def tooltip(self) -> str:
        """Everything about this minion for a hover tooltip: stats, keywords, text, buffs."""
        lines = [f"{self.name or self.card_id}  {self.attack}/{self.health}"]
        if self.keywords():
            lines.append(", ".join(_(k) for k in self.keywords()))
        if self.text:
            lines.append(self.text)
        if self.buffs:
            lines.append(_("Buffs:"))
            texts = self.buff_texts if len(self.buff_texts) == len(self.buffs) else [""] * len(self.buffs)
            for name, text in zip(self.buffs, texts):
                lines.append(f"• {name}" + (f": {text}" if text else ""))
        return "\n".join(lines)

    def keywords(self) -> list[str]:
        """English keyword names (translate with ``_()`` for display)."""
        words = []
        if self.taunt:
            words.append(N_("Taunt"))
        if self.divine_shield:
            words.append(N_("Divine Shield"))
        if self.reborn:
            words.append(N_("Reborn"))
        if self.venomous:
            words.append(N_("Poisonous"))
        if self.windfury == 1:
            words.append(N_("Windfury"))
        elif self.windfury >= 3:
            words.append(N_("Mega-Windfury"))
        if self.cleave:
            words.append(N_("Cleave"))
        if self.deathrattle:
            words.append(N_("Deathrattle"))
        return words


@dataclass
class BoardSnapshot:
    round: int
    hero_card_id: str
    hero_name: str
    tavern_tier: int
    minions: list[Minion] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "round": self.round,
            "hero_card_id": self.hero_card_id,
            "hero_name": self.hero_name,
            "tavern_tier": self.tavern_tier,
            "minions": [m.to_dict() for m in self.minions],
        }


@dataclass
class CombatOutcome:
    """What really happened in a combat (from the player's perspective)."""

    result: str  # "win" | "loss" | "draw"
    damage: int | None = None  # hero damage dealt (win) or taken (loss), if seen

    def text(self) -> str:
        label = {"win": _("Win"), "loss": _("Loss"), "draw": _("Draw")}[self.result]
        if self.result != "draw" and self.damage:
            return _("{result}, {damage} damage").format(result=label, damage=self.damage)
        return label


@dataclass
class CombatSnapshot:
    """Both boards right before the first attack of a combat round."""

    round: int
    player: BoardSnapshot
    opponent: BoardSnapshot
    opponent_player_id: int = 0  # lobby PLAYER_ID of the opponent
    actual: CombatOutcome | None = None  # filled in when the combat is over
    damage_cap: int = 0  # most hero damage this combat can deal (0 = no cap)


@dataclass
class OpponentInfo:
    hero_card_id: str
    hero_name: str
    lobby_player_id: int = 0  # PLAYER_ID tag (1-8); entries are keyed by it
    place: int = 0
    health: int = 0
    armor: int = 0
    tavern_tier: int = 0
    is_me: bool = False
    is_next_opponent: bool = False
    last_board: BoardSnapshot | None = None
    max_health: int = 0  # HEALTH tag: starting health, for the health bar
    tier_up_round: int = 0  # round of the last tavern tier increase (0 = never)
    main_tribe: str = ""  # most common tribe in the last seen board
    triples: int = 0  # PLAYER_TRIPLES
    triple_round: int = 0  # round of the last triple (0 = none seen)
    trinkets: list[str] = field(default_factory=list)  # names of the player's trinkets
    wins: int = 0  # your combats against this player in this game
    draws: int = 0
    losses: int = 0

    @property
    def dead(self) -> bool:
        return self.place > 0 and self.health + self.armor <= 0

    @property
    def health_fraction(self) -> float:
        """Health (without armor) relative to the starting health, for a bar."""
        return max(0.0, min(1.0, self.health / max(self.max_health, 1)))


@dataclass
class LiveState:
    in_game: bool = False
    is_battlegrounds: bool = False
    game_type: str = ""
    hero_card_id: str = ""
    hero_name: str = ""
    round: int = 0
    phase: str = ""  # "recruit" | "combat"
    tavern_tier: int = 0
    place: int = 0
    health: int = 0
    armor: int = 0
    tribes_seen: list[str] = field(default_factory=list)
    anomaly: str = ""  # name of the lobby's anomaly (or deity with Aberrations)
    anomaly_text: str = ""  # its card text, plain
    tribes_banned: list[str] = field(default_factory=list)
    opponents: list[OpponentInfo] = field(default_factory=list)
    next_opponent: str = ""
    last_combat: CombatSnapshot | None = None
    combat_log: list[CombatSnapshot] = field(default_factory=list)  # all combats of the game
    summary: MatchResult | None = None  # set when the game is over
    notice: str = ""  # e.g. why the last game could not be followed to its end
    max_health: int = 0
    my_board: list[Minion] = field(default_factory=list)  # your board right now (recruit phase)
    player_buff_texts: list[str] = field(default_factory=list)  # what each player buff does
    player_buffs: list[str] = field(default_factory=list)  # game-wide buffs, e.g. "Blood Gems +2/+1"
    counters: list[str] = field(default_factory=list)  # e.g. "Gold next turn +2"


@dataclass
class MatchResult:
    source_key: str
    started_at: str
    ended_at: str
    game_type: str
    hero_card_id: str
    hero_name: str
    placement: int
    rounds: int
    tavern_tier: int
    tribes: list[str] = field(default_factory=list)
    final_board: list[Minion] = field(default_factory=list)

    @property
    def is_duo(self) -> bool:
        return "DUO" in self.game_type

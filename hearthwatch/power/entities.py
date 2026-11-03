"""Entity model shared by the game state and the Battlegrounds tracker."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Entity:
    id: int
    card_id: str = ""
    tags: dict[str, int | str] = field(default_factory=dict)
    name: str = ""
    # When each tag was last set (a counter that grows with every log event);
    # several entities can describe the same lobby player, the newest wins.
    tag_seq: dict[str, int] = field(default_factory=dict)

    def last_change(self, *tags: str) -> int:
        """Sequence number of the newest change of any of ``tags`` (-1 if never)."""
        return max((self.tag_seq.get(t, -1) for t in tags), default=-1)

    def tag(self, name: str, default: int | str = 0) -> int | str:
        return self.tags.get(name, default)

    def int_tag(self, name: str, default: int = 0) -> int:
        value = self.tags.get(name, default)
        return value if isinstance(value, int) else default

    @property
    def zone(self) -> str:
        return str(self.tags.get("ZONE", ""))

    @property
    def controller(self) -> int:
        return self.int_tag("CONTROLLER")

    @property
    def card_type(self) -> str:
        return str(self.tags.get("CARDTYPE", ""))

    @property
    def is_minion(self) -> bool:
        return self.card_type == "MINION"

    @property
    def is_hero(self) -> bool:
        return self.card_type == "HERO"

    @property
    def is_in_play(self) -> bool:
        return self.zone == "PLAY"

    @property
    def health(self) -> int:
        return self.int_tag("HEALTH") - self.int_tag("DAMAGE")

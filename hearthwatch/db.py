"""SQLite storage for finished Battlegrounds matches."""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path

from hearthwatch.bg.models import MatchResult, Minion

SCHEMA = """
CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_key TEXT NOT NULL UNIQUE,
    started_at TEXT NOT NULL,
    ended_at TEXT NOT NULL,
    game_type TEXT NOT NULL,
    hero_card_id TEXT NOT NULL,
    hero_name TEXT NOT NULL,
    placement INTEGER NOT NULL,
    rounds INTEGER NOT NULL,
    tavern_tier INTEGER NOT NULL,
    tribes TEXT NOT NULL,
    final_board TEXT NOT NULL,
    mmr_after INTEGER,
    note TEXT
);
"""


@dataclass
class StoredMatch:
    id: int
    result: MatchResult
    mmr_after: int | None
    note: str | None


@dataclass
class HeroStats:
    hero_card_id: str
    hero_name: str
    games: int
    avg_place: float
    top4: int
    wins: int


@dataclass
class Summary:
    games: int
    avg_place: float
    top4_rate: float
    wins: int
    last_mmr: int | None


def _is_top(result_placement: int, game_type: str) -> bool:
    return result_placement <= (2 if "DUO" in game_type else 4)


def _is_win(result_placement: int) -> bool:
    return result_placement == 1


class MatchDB:
    def __init__(self, path: Path | str) -> None:
        if isinstance(path, Path):
            path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def add(self, r: MatchResult) -> int | None:
        """Insert a match; returns its id, or None when it already exists."""
        with self._lock, self._conn:
            cur = self._conn.execute(
                """INSERT OR IGNORE INTO matches
                (source_key, started_at, ended_at, game_type, hero_card_id, hero_name,
                 placement, rounds, tavern_tier, tribes, final_board)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    r.source_key, r.started_at, r.ended_at, r.game_type, r.hero_card_id,
                    r.hero_name, r.placement, r.rounds, r.tavern_tier, json.dumps(r.tribes),
                    json.dumps([m.to_dict() for m in r.final_board]),
                ),
            )
            return cur.lastrowid if cur.rowcount else None

    def set_mmr(self, match_id: int, mmr: int | None) -> None:
        with self._lock, self._conn:
            self._conn.execute("UPDATE matches SET mmr_after=? WHERE id=?", (mmr, match_id))

    def delete(self, match_id: int) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM matches WHERE id=?", (match_id,))

    def matches(self, limit: int = 200) -> list[StoredMatch]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM matches ORDER BY ended_at DESC, id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._row(r) for r in rows]

    @staticmethod
    def _row(row: sqlite3.Row) -> StoredMatch:
        result = MatchResult(
            source_key=row["source_key"],
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            game_type=row["game_type"],
            hero_card_id=row["hero_card_id"],
            hero_name=row["hero_name"],
            placement=row["placement"],
            rounds=row["rounds"],
            tavern_tier=row["tavern_tier"],
            tribes=json.loads(row["tribes"]),
            final_board=[Minion.from_dict(m) for m in json.loads(row["final_board"])],
        )
        return StoredMatch(row["id"], result, row["mmr_after"], row["note"])

    def hero_stats(self) -> list[HeroStats]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT hero_card_id, hero_name, placement, game_type FROM matches"
            ).fetchall()
        agg: dict[str, dict] = {}
        for r in rows:
            a = agg.setdefault(
                r["hero_card_id"],
                {"name": r["hero_name"], "places": [], "top": 0, "wins": 0},
            )
            a["places"].append(r["placement"])
            a["top"] += _is_top(r["placement"], r["game_type"])
            a["wins"] += _is_win(r["placement"])
        stats = [
            HeroStats(
                hero_card_id=k,
                hero_name=v["name"],
                games=len(v["places"]),
                avg_place=sum(v["places"]) / len(v["places"]),
                top4=v["top"],
                wins=v["wins"],
            )
            for k, v in agg.items()
        ]
        stats.sort(key=lambda s: (-s.games, s.avg_place))
        return stats

    def summary(self) -> Summary:
        with self._lock:
            rows = self._conn.execute("SELECT placement, game_type FROM matches").fetchall()
            mmr = self._conn.execute(
                "SELECT mmr_after FROM matches WHERE mmr_after IS NOT NULL "
                "ORDER BY ended_at DESC, id DESC LIMIT 1"
            ).fetchone()
        games = len(rows)
        if not games:
            return Summary(0, 0.0, 0.0, 0, mmr[0] if mmr else None)
        return Summary(
            games=games,
            avg_place=sum(r["placement"] for r in rows) / games,
            top4_rate=sum(_is_top(r["placement"], r["game_type"]) for r in rows) / games,
            wins=sum(_is_win(r["placement"]) for r in rows),
            last_mmr=mmr[0] if mmr else None,
        )

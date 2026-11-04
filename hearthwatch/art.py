"""Card art from HearthstoneJSON, downloaded once and cached on disk.

``https://art.hearthstonejson.com/v1/256x/<CARD_ID>.jpg`` has art for heroes
and minions. Downloads run in a small thread pool; callers get a callback with
the file path (or nothing when the art does not exist / the network is off).
"""

from __future__ import annotations

import logging
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

from hearthwatch.cards import hero_base_id

log = logging.getLogger(__name__)

ART_URL = "https://art.hearthstonejson.com/v1/256x/{card_id}.jpg"


def _candidates(card_id: str) -> list[str]:
    """Golden/skin variants often have no own art: fall back to the base card."""
    ids = [card_id]
    base = hero_base_id(card_id)
    if base != card_id:
        ids.append(base)
    for suffix in ("_G", "_SKIN_A"):
        if card_id.endswith(suffix):
            ids.append(card_id[: -len(suffix)])
    return list(dict.fromkeys(ids))


class ArtCache:
    def __init__(self, cache_dir: Path, enabled: bool = True,
                 fetch: Callable[[str, Path], bool] | None = None) -> None:
        self.dir = cache_dir / "art"
        self.enabled = enabled
        self._fetch = fetch or self._download
        self._pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="hearthwatch-art")
        self._lock = threading.Lock()
        self._missing: set[str] = set()  # not available this session
        self._waiting: dict[str, list[Callable[[Path], None]]] = {}

    def path(self, card_id: str) -> Path:
        return self.dir / f"{card_id}.jpg"

    def cached(self, card_id: str) -> Path | None:
        for cid in _candidates(card_id):
            p = self.path(cid)
            if p.is_file() and p.stat().st_size > 0:
                return p
        return None

    def request(self, card_id: str, callback: Callable[[Path], None]) -> Path | None:
        """Return the cached file, or download it and call ``callback(path)`` later
        (on the download thread). Nothing happens for unknown art."""
        if not card_id or not self.enabled:
            return None
        hit = self.cached(card_id)
        if hit is not None:
            return hit
        with self._lock:
            if card_id in self._missing:
                return None
            if card_id in self._waiting:
                self._waiting[card_id].append(callback)
                return None
            self._waiting[card_id] = [callback]
        self._pool.submit(self._load, card_id)
        return None

    def _load(self, card_id: str) -> None:
        found: Path | None = None
        for cid in _candidates(card_id):
            target = self.path(cid)
            try:
                if self._fetch(cid, target):
                    found = target
                    break
            except Exception as exc:  # offline, 404, ...
                log.debug("no art for %s: %s", cid, exc)
        with self._lock:
            callbacks = self._waiting.pop(card_id, [])
            if found is None:
                self._missing.add(card_id)
        if found is not None:
            for cb in callbacks:
                cb(found)

    @staticmethod
    def _download(card_id: str, target: Path) -> bool:
        req = urllib.request.Request(ART_URL.format(card_id=card_id),
                                     headers={"User-Agent": "hearthwatch/0.3"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
        if not data:
            return False
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.replace(target)
        return True

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)

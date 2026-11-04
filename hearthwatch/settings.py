"""User settings (JSON in ~/.config/hearthwatch/settings.json)."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from hearthwatch import paths

log = logging.getLogger(__name__)

LANGUAGES = ("auto", "en", "de")
SIM_RUNS = (500, 1000, 2000, 5000)


@dataclass
class Settings:
    language: str = "auto"  # "auto" (system), "en" or "de": interface and card names
    show_art: bool = True
    font_scale: int = 100  # percent
    scale_with_window: bool = True  # art and text grow when the window is made bigger
    sim_runs: int = 2000
    show_buffs: bool = True  # "Your buffs" with your live board
    show_history: bool = True  # result dots of this game
    show_tribes: bool = True
    show_lobby_boards: bool = True
    window_width: int = 460
    window_height: int = 900

    def normalized(self) -> "Settings":
        if self.language not in LANGUAGES:
            self.language = "auto"
        self.font_scale = max(80, min(150, int(self.font_scale)))
        if self.sim_runs not in SIM_RUNS:
            self.sim_runs = 2000
        self.window_width = max(360, int(self.window_width))
        self.window_height = max(420, int(self.window_height))
        return self


def settings_path() -> Path:
    return paths.xdg_config_home() / paths.APP_NAME / "settings.json"


def load(path: Path | None = None) -> Settings:
    path = path or settings_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return Settings()
    except (OSError, ValueError) as exc:
        log.warning("ignoring broken settings %s: %s", path, exc)
        return Settings()
    known = {f.name for f in fields(Settings)}
    values = {k: v for k, v in raw.items() if k in known} if isinstance(raw, dict) else {}
    if isinstance(raw, dict) and "language" not in raw and raw.get("locale") in ("deDE", "enUS"):
        values["language"] = raw["locale"][:2]  # card language setting from before 0.2
    try:
        return Settings(**values).normalized()
    except (TypeError, ValueError):
        return Settings()


def save(settings: Settings, path: Path | None = None) -> None:
    path = path or settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
    tmp.replace(path)

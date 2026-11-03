"""Tiny translation layer: English source texts, German translations in a dict.

``_("Round {n}").format(n=3)`` returns the text in the active language.
``N_()`` only marks a text for translation (for module level constants that
are translated later with ``_()`` at display time). No gettext and no
compiled catalogs, so installing stays a plain ``pipx install``.

Language values: ``"auto"`` (from the environment), ``"de"`` or ``"en"``.
Card names follow the same language (``deDE`` / ``enUS``).
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from hearthwatch.locale.de import DE

LANGUAGES = {"auto": "Automatic", "en": "English", "de": "Deutsch"}
CARD_LOCALES = {"en": "enUS", "de": "deDE"}

_language = "en"


def detect(env: Mapping[str, str] | None = None) -> str:
    """Language of the desktop session: ``"de"`` for German, else ``"en"``."""
    env = os.environ if env is None else env
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = env.get(var, "")
        if not value or value in ("C", "POSIX", "C.UTF-8"):
            continue
        first = value.split(":")[0].lower()
        return "de" if first.startswith("de") else "en"
    return "en"


def resolve(language: str | None) -> str:
    """Turn a setting (``auto``/``de``/``en``, also old ``deDE``/``enUS``) into ``de``/``en``."""
    value = (language or "auto").strip()
    if value in ("deDE", "enUS"):
        value = value[:2]
    if value not in CARD_LOCALES:
        return detect()
    return value


def set_language(language: str | None) -> str:
    global _language
    _language = resolve(language)
    return _language


def language() -> str:
    return _language


def card_locale(language: str | None = None) -> str:
    return CARD_LOCALES[resolve(language) if language else _language]


def _(text: str) -> str:
    if _language == "de":
        return DE.get(text, text)
    return text


def N_(text: str) -> str:
    return text

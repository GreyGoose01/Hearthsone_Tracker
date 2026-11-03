"""Every text marked with _() / N_() has a German translation, and no extra ones."""

import ast
from pathlib import Path

import pytest

from hearthwatch import i18n
from hearthwatch.locale.de import DE

PACKAGE = Path(__file__).resolve().parent.parent / "hearthwatch"


def marked_texts() -> dict[str, str]:
    texts: dict[str, str] = {}
    for path in PACKAGE.rglob("*.py"):
        if "locale" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id in ("_", "N_") and node.args):
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    texts[arg.value] = f"{path.relative_to(PACKAGE)}:{node.lineno}"
    return texts


def test_every_text_has_a_german_translation():
    missing = {t: where for t, where in marked_texts().items() if t not in DE}
    assert not missing, "\n".join(f"{where}: {t!r}" for t, where in missing.items())


def test_no_unused_translations():
    used = marked_texts()
    unused = [t for t in DE if t not in used]
    assert not unused, unused


def test_placeholders_match():
    import string

    def fields(text):
        return sorted(f for _lit, f, _spec, _conv in string.Formatter().parse(text) if f is not None)

    wrong = [en for en, de in DE.items() if fields(en) != fields(de)]
    assert not wrong, wrong


@pytest.mark.parametrize("env, expected", [
    ({"LANG": "de_DE.UTF-8"}, "de"),
    ({"LANG": "en_US.UTF-8"}, "en"),
    ({"LANG": "de_AT.UTF-8", "LC_ALL": "en_GB.UTF-8"}, "en"),
    ({"LANGUAGE": "de:en", "LANG": "en_US.UTF-8"}, "de"),
    ({"LANG": "C.UTF-8"}, "en"),
    ({}, "en"),
])
def test_detect(env, expected):
    assert i18n.detect(env) == expected


def test_switch_language():
    try:
        assert i18n.set_language("de") == "de"
        assert i18n._("Next opponent") == "Nächster Gegner"
        assert i18n.card_locale() == "deDE"
        assert i18n.set_language("en") == "en"
        assert i18n._("Next opponent") == "Next opponent"
        assert i18n.card_locale() == "enUS"
        assert i18n.resolve("deDE") == "de"  # setting from before 0.2
    finally:
        i18n.set_language("en")

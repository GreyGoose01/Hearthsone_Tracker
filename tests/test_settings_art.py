import threading

from hearthwatch import settings as st
from hearthwatch.art import ArtCache


def test_settings_roundtrip_and_defaults(tmp_path):
    path = tmp_path / "settings.json"
    assert st.load(path) == st.Settings()
    s = st.Settings(language="en", show_art=False, font_scale=120, sim_runs=5000)
    st.save(s, path)
    assert st.load(path) == s


def test_broken_or_odd_settings_fall_back(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{not json")
    assert st.load(path) == st.Settings()
    path.write_text('{"language": "xx", "font_scale": 999, "sim_runs": 7, "unknown": 1}')
    s = st.load(path)
    assert (s.language, s.font_scale, s.sim_runs) == ("auto", 150, 2000)


def test_old_card_language_setting_becomes_the_language(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"locale": "deDE", "font_scale": 110}')
    assert st.load(path).language == "de"
    path.write_text('{"locale": "enUS"}')
    assert st.load(path).language == "en"
    path.write_text('{"locale": "deDE", "language": "auto"}')
    assert st.load(path).language == "auto"


def test_art_cache_downloads_once_and_falls_back(tmp_path):
    calls = []

    def fetch(card_id, target):
        calls.append(card_id)
        if card_id != "BG_X":  # golden variant has no art, base card has
            raise OSError("404")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"jpg")
        return True

    cache = ArtCache(tmp_path, fetch=fetch)
    done = threading.Event()
    got = []
    assert cache.request("BG_X_G", lambda p: (got.append(p), done.set())) is None
    assert done.wait(5)
    assert got[0].name == "BG_X.jpg" and calls == ["BG_X_G", "BG_X"]
    assert cache.request("BG_X_G", lambda p: None) == got[0]  # cached now


def test_missing_art_is_not_retried(tmp_path):
    calls = []

    def fetch(card_id, target):
        calls.append(card_id)
        raise OSError("offline")

    cache = ArtCache(tmp_path, fetch=fetch)
    cache.request("NOPE", lambda p: None)
    cache._pool.shutdown(wait=True)
    assert cache.request("NOPE", lambda p: None) is None
    assert calls == ["NOPE"]
    assert ArtCache(tmp_path, enabled=False).request("NOPE", lambda p: None) is None

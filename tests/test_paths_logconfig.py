from hearthwatch import logconfig, paths


def test_game_dir_from_launcher_config(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.delenv("BGTRACKER_GAME_DIR", raising=False)
    monkeypatch.delenv("HEARTHWATCH_GAME_DIR", raising=False)
    custom = tmp_path / "games" / "hs"
    (custom / "Logs").mkdir(parents=True)
    cfg = tmp_path / ".config/hearthstone-linux-gui/config.toml"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(f'region = "eu"\ngame_dir = "{custom}"\n')
    assert paths.find_game_dir() == custom


def test_game_dir_default(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.delenv("BGTRACKER_GAME_DIR", raising=False)
    monkeypatch.delenv("HEARTHWATCH_GAME_DIR", raising=False)
    assert paths.find_game_dir() == tmp_path / ".local/share/hearthstone-linux-gui/game"
    assert paths.log_config_path() == tmp_path / "Library/Preferences/Blizzard/Hearthstone/log.config"


def test_logconfig_ensure_keeps_other_sections(tmp_path):
    path = tmp_path / "log.config"
    path.write_text("[Zone]\nLogLevel=1\nFilePrinting=true\n\n[Power]\nLogLevel=1\nVerbose=false\n")
    assert not logconfig.is_configured(path)
    assert logconfig.ensure(path) is True
    text = path.read_text()
    assert "[Zone]" in text and "Verbose=true" in text and "FilePrinting=true" in text
    assert (tmp_path / "log.config.bak").exists()
    assert logconfig.is_configured(path)
    assert logconfig.ensure(path) is False


def test_logconfig_creates_file(tmp_path):
    path = tmp_path / "a/b/log.config"
    assert logconfig.ensure(path)
    assert logconfig.missing_entries(path) == []


def test_old_bgtracker_folders_are_moved_once(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    for var in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME"):
        monkeypatch.delenv(var, raising=False)
    old_data = tmp_path / ".local/share/bgtracker"
    old_data.mkdir(parents=True)
    (old_data / "matches.sqlite3").write_text("history")
    old_state = tmp_path / ".local/state/bgtracker"
    old_state.mkdir(parents=True)
    (old_state / "bgtracker.log").write_text("log")
    new_config = tmp_path / ".config/hearthwatch"
    new_config.mkdir(parents=True)
    (tmp_path / ".config/bgtracker").mkdir()  # new folder exists already: keep both

    moved = paths.migrate_legacy_dirs()

    assert set(moved) == {tmp_path / ".local/share/hearthwatch", tmp_path / ".local/state/hearthwatch"}
    assert (tmp_path / ".local/share/hearthwatch/matches.sqlite3").read_text() == "history"
    assert (tmp_path / ".local/state/hearthwatch/hearthwatch.log").read_text() == "log"
    assert not old_data.exists()
    assert (tmp_path / ".config/bgtracker").exists()
    assert paths.migrate_legacy_dirs() == []


def test_game_dir_env_var(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("HEARTHWATCH_GAME_DIR", str(tmp_path / "hs"))
    assert paths.game_dir_candidates()[0] == tmp_path / "hs"
    monkeypatch.delenv("HEARTHWATCH_GAME_DIR")
    monkeypatch.setenv("BGTRACKER_GAME_DIR", str(tmp_path / "old"))
    assert paths.game_dir_candidates()[0] == tmp_path / "old"

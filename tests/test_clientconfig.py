from hearthwatch import clientconfig

LAUNCHER = "Aurora.ClientCheck=false\nAurora.Env.Override=1\nAurora.Env=eu.actual.battle.net\nLocalization.Locale=deDE\n"


def setup_home(tmp_path, monkeypatch, client=LAUNCHER, overrides=None):
    monkeypatch.setenv("HOME", str(tmp_path))
    for var in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "BGTRACKER_GAME_DIR", "HEARTHWATCH_GAME_DIR"):
        monkeypatch.delenv(var, raising=False)
    game = tmp_path / ".local/share/hearthstone-linux-gui/game"
    (game / "Logs").mkdir(parents=True)
    if client is not None:
        (game / "client.config").write_text(client)
    cfg_dir = tmp_path / ".config/hearthstone-linux-gui"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "config.toml").write_text('region = "eu"\n')
    if overrides is not None:
        (cfg_dir / "client.config.overrides").write_text(overrides)
    return game, cfg_dir


def test_has_setting_flat_and_section_forms():
    assert clientconfig.has_setting("Log.FileSizeLimit.Int=-1\n")
    assert clientconfig.has_setting("[Log]\nFileSizeLimit.Int=-1\n")
    assert not clientconfig.has_setting("[Log]\nFileSizeLimit.Int=10000\n")
    assert not clientconfig.has_setting(LAUNCHER)


def test_ensure_adds_the_line_to_client_config_and_launcher_overrides(tmp_path, monkeypatch):
    game, cfg_dir = setup_home(tmp_path, monkeypatch, overrides="Graphics.Foo=1\n")
    changed = clientconfig.ensure()
    assert set(changed) == {game / "client.config", cfg_dir / "client.config.overrides"}
    assert (game / "client.config").read_text() == LAUNCHER + "Log.FileSizeLimit.Int=-1\n"
    assert (cfg_dir / "client.config.overrides").read_text() == "Graphics.Foo=1\nLog.FileSizeLimit.Int=-1\n"
    assert (game / "client.config.bak").read_text() == LAUNCHER
    assert clientconfig.is_configured()
    assert clientconfig.ensure() == []  # idempotent


def test_wrong_value_is_replaced(tmp_path, monkeypatch):
    game, _ = setup_home(tmp_path, monkeypatch, client=LAUNCHER + "Log.FileSizeLimit.Int=5000\n")
    clientconfig.ensure()
    text = (game / "client.config").read_text()
    assert text.count("Log.FileSizeLimit.Int") == 1 and text.endswith("Log.FileSizeLimit.Int=-1\n")


def test_missing_client_config_only_writes_overrides(tmp_path, monkeypatch):
    game, cfg_dir = setup_home(tmp_path, monkeypatch, client=None)
    assert clientconfig.ensure() == [cfg_dir / "client.config.overrides"]
    assert not (game / "client.config").exists()
    assert not clientconfig.is_configured()


def test_status_and_diagnosis_when_the_launcher_rewrote_client_config(tmp_path, monkeypatch):
    from hearthwatch import diagnose

    game, cfg_dir = setup_home(tmp_path, monkeypatch, overrides="Log.FileSizeLimit.Int=-1\n")
    st = clientconfig.status()
    assert st["client_exists"] and not st["client_ok"] and st["overrides_ok"]
    check = next(c for c in diagnose.run_checks() if c.key == "clientconfig")
    assert check.status == "error" and "neu geschrieben" in check.detail
    clientconfig.ensure()
    check = next(c for c in diagnose.run_checks() if c.key == "clientconfig")
    assert check.status == "ok"


def test_line_goes_before_the_first_section_and_old_values_are_removed(tmp_path, monkeypatch):
    client = LAUNCHER + "[Log]\nFileSizeLimit.Int=10000\nOther=1\nLog.FileSizeLimit.Int=-1\n"
    game, cfg_dir = setup_home(tmp_path, monkeypatch, client=client,
                               overrides="[Log]\nFileSizeLimit.Int=10000\n")
    assert not clientconfig.is_configured()
    clientconfig.ensure()
    text = (game / "client.config").read_text()
    assert text == LAUNCHER + "Log.FileSizeLimit.Int=-1\n[Log]\nOther=1\n"
    assert (cfg_dir / "client.config.overrides").read_text() == "Log.FileSizeLimit.Int=-1\n[Log]\n"
    assert clientconfig.is_configured()
    assert clientconfig.ensure() == []  # no endless "abgeschaltet"

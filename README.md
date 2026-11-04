<p align="center"><img src="data/logo.png" alt="Hearthwatch" width="560"></p>

<p align="center"><b>English</b> | <a href="README.de.md">Deutsch</a></p>

# Hearthwatch

A live Battlegrounds tracker for Hearthstone on Linux. Made for
[hearthstone-linux-gui](https://github.com/DawnMagnet/hearthstone-linux-gui), in English and German.

## Features

- **Next opponent** during recruit: health, tavern tier, main minion type, your record against
  them and their last board.
- **Combat odds** from a built-in simulator, a warning when a fight could be lethal, then the real
  result and damage.
- **Your buffs:** Blood Gems, tavern spells, extra gold and your board with every buff.
- **Minions by tier:** every tavern minion that can show up in your lobby, grouped by minion type.
- **Lobby** with places, health bars, triples, trinkets and the last board of every player, plus the
  lobby's anomaly.
- **Summary** at the end of a game, plus a **history** with stats per hero.

Hearthwatch only reads the log files Hearthstone writes. It does not touch the game or its memory.

## Install

You need Hearthstone installed with hearthstone-linux-gui, plus Python 3.12, GTK 4.12 and
libadwaita 1.4 or newer. Every change is tested on Ubuntu 24.04 and 26.04, Debian 13, Fedora and
Arch Linux.

**Ubuntu, Debian, Linux Mint, Pop!_OS:**

Download `hearthwatch_<version>_all.deb` from the
[latest release](https://github.com/GreyGoose01/hearthwatch/releases/latest) and install it:

```bash
sudo apt install ./hearthwatch_*_all.deb
```

apt pulls in GTK and everything else. Uninstall with `sudo apt remove hearthwatch`.

<details>
<summary>Install from source instead</summary>

```bash
git clone https://github.com/GreyGoose01/hearthwatch.git && cd hearthwatch
```

```bash
./install.sh
```

The script installs the missing packages, Hearthwatch (via `pipx`) and a menu entry, then sets up
the logging. Uninstall with `./install.sh --remove`. If you switch to the .deb later, run that first.
</details>

**Fedora, Arch and others:** install PyGObject, GTK 4, libadwaita and pipx with your package
manager (Fedora: `python3-gobject gtk4 libadwaita pipx`, Arch: `python-gobject gtk4 libadwaita
python-pipx`), then from the cloned repo:

```bash
pipx install --system-site-packages . && hearthwatch --setup-logs
```

## Setup

1. Start Hearthstone once from the launcher and quit it.
2. Run `hearthwatch --setup-logs`. It creates `log.config` and lifts Hearthstone's 10 MB log limit.
3. Start Hearthstone again. Done.

`hearthwatch --check` shows whether everything is in place and what to do next. The app shows the
same as a banner.

## Usage

Start Hearthwatch from the app menu or with `hearthwatch`. It waits until you join a
Battlegrounds game. Language, card art, font size and visible sections are in the settings.

| Command | What it does |
|---|---|
| `hearthwatch --check` | check the setup |
| `hearthwatch --setup-logs` | set up Hearthstone's logging |
| `hearthwatch --import-logs` | add games from old logs to the history |
| `hearthwatch --replay <Power.log> --simulate` | read a log without the window |
| `hearthwatch --lang en` | pick the language (`auto`, `en`, `de`) |

## Troubleshooting

- **Nothing happens:** run `hearthwatch --check` and follow the hint.
- **Hearthwatch stops in the middle of a game:** Hearthstone hit its log limit. Run
  `hearthwatch --setup-logs` and restart Hearthstone.
- **Found a bug?** Open an issue and attach `~/.local/state/hearthwatch/hearthwatch.log`. A
  `Power.log` helps too, but it contains your BattleTag, so remove that first.

## Limitations

- The simulator does not know every card effect yet. Such fights are marked as rough.
- MMR is not in the logs. You can type it into the history yourself.

## Development

```bash
python3 -m venv --system-site-packages .venv && .venv/bin/pip install -e '.[dev]' && .venv/bin/python -m pytest
```

Translations live in `hearthwatch/locale/de.py`; a test checks that every text has one.
`packaging/build-deb.sh` builds the .deb. The *Release* workflow (Actions → Run workflow) builds it
on GitHub and publishes a release for the version in `hearthwatch/__init__.py`.
See [CONTRIBUTING.md](CONTRIBUTING.md) for the branch and release workflow.

## Credits

Thanks to [hearthstone-linux-gui](https://github.com/DawnMagnet/hearthstone-linux-gui) for
Hearthstone on Linux, [HearthSim](https://github.com/HearthSim) (`hslog` and Hearthstone Deck
Tracker showed the way through the logs) and [HearthstoneJSON](https://hearthstonejson.com) for
card data and art.

Hearthwatch is released under the [MIT License](LICENSE). The artwork in `data/` and
`hearthwatch/assets/` is part of the project and covered by it too.

Hearthstone is a trademark of Blizzard Entertainment. Hearthwatch is a fan project and not
affiliated with Blizzard.

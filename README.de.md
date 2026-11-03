<p align="center"><img src="data/logo.png" alt="Hearthwatch" width="560"></p>

<p align="center"><a href="README.md">English</a> | <b>Deutsch</b></p>

# Hearthwatch

Ein Live-Tracker für den Hearthstone-Modus Schlachtfeld unter Linux. Gemacht für
[hearthstone-linux-gui](https://github.com/DawnMagnet/hearthstone-linux-gui), auf Deutsch und Englisch.

## Funktionen

- **Nächster Gegner** in der Rekrutierung: Leben, Gasthausstufe, Haupt-Dienertyp, deine Bilanz gegen
  ihn und sein letztes Board.
- **Gewinnchance** im Kampf aus einem eingebauten Simulator, eine Warnung bei tödlichem Risiko,
  danach das echte Ergebnis mit Schaden.
- **Deine Buffs:** Blutedelsteine, Gasthauszauber, Extra-Gold und dein Board mit allen Buffs.
- **Lobby** mit Platz, Lebensbalken und dem letzten Board jedes Spielers.
- **Zusammenfassung** am Spielende und eine **Historie** mit Statistik pro Held.

Hearthwatch liest nur die Log-Dateien, die Hearthstone selbst schreibt. Es greift weder ins Spiel
noch in dessen Speicher ein.

## Installation

Du brauchst Hearthstone, installiert über hearthstone-linux-gui, außerdem Python 3.12, GTK 4.12 und
libadwaita 1.4 oder neuer. Jede Änderung wird auf Ubuntu 24.04 und 26.04, Debian 13, Fedora und
Arch Linux getestet.

**Ubuntu, Debian, Linux Mint, Pop!_OS:**

Lade `hearthwatch_<version>_all.deb` aus dem
[neuesten Release](https://github.com/GreyGoose01/hearthwatch/releases/latest) und installiere es:

```bash
sudo apt install ./hearthwatch_*_all.deb
```

apt holt GTK und alles Weitere automatisch. Deinstallieren mit `sudo apt remove hearthwatch`.

<details>
<summary>Stattdessen aus dem Quellcode installieren</summary>

```bash
git clone https://github.com/GreyGoose01/hearthwatch.git && cd hearthwatch
```

```bash
./install.sh
```

Das Skript installiert fehlende Pakete, Hearthwatch (über `pipx`) und einen Menüeintrag und richtet
danach das Logging ein. Deinstallieren mit `./install.sh --remove`. Wechselst du später zum .deb,
führ das vorher aus.
</details>

**Fedora, Arch und andere:** PyGObject, GTK 4, libadwaita und pipx über den Paketmanager installieren
(Fedora: `python3-gobject gtk4 libadwaita pipx`, Arch: `python-gobject gtk4 libadwaita
python-pipx`), dann im geklonten Repo:

```bash
pipx install --system-site-packages . && hearthwatch --setup-logs
```

## Einrichtung

1. Hearthstone einmal über den Launcher starten und wieder beenden.
2. `hearthwatch --setup-logs` ausführen. Das legt die `log.config` an und hebt das 10-MB-Limit für
   Logs auf.
3. Hearthstone neu starten. Fertig.

`hearthwatch --check` zeigt, ob alles passt und was als Nächstes zu tun ist. Die App zeigt das
Gleiche als Banner.

## Benutzung

Starte Hearthwatch über das Anwendungsmenü oder mit `hearthwatch`. Es wartet, bis du ein
Schlachtfeld-Spiel betrittst. Sprache, Kartenbilder, Schriftgröße und sichtbare Bereiche stellst du
in den Einstellungen ein.

| Befehl | Was er tut |
|---|---|
| `hearthwatch --check` | Einrichtung prüfen |
| `hearthwatch --setup-logs` | Logging von Hearthstone einrichten |
| `hearthwatch --import-logs` | Spiele aus alten Logs in die Historie übernehmen |
| `hearthwatch --replay <Power.log> --simulate` | ein Log ohne Fenster auswerten |
| `hearthwatch --lang de` | Sprache wählen (`auto`, `en`, `de`) |

## Wenn etwas nicht klappt

- **Es passiert nichts:** `hearthwatch --check` ausführen und dem Hinweis folgen.
- **Hearthwatch bleibt mitten im Spiel stehen:** Hearthstone hat sein Log-Limit erreicht.
  `hearthwatch --setup-logs` ausführen und Hearthstone neu starten.
- **Fehler gefunden?** Mach ein Issue auf und häng `~/.local/state/hearthwatch/hearthwatch.log` an.
  Eine `Power.log` hilft auch, enthält aber deinen BattleTag. Den also vorher entfernen.

## Grenzen

- Der Simulator kennt noch nicht jeden Karteneffekt. Solche Kämpfe sind als ungenau markiert.
- Die MMR steht nicht im Log. Du kannst sie in der Historie selbst eintragen.

## Entwicklung

```bash
python3 -m venv --system-site-packages .venv && .venv/bin/pip install -e '.[dev]' && .venv/bin/python -m pytest
```

Die Übersetzungen liegen in `hearthwatch/locale/de.py`; ein Test prüft, dass jeder Text eine hat.
`packaging/build-deb.sh` baut das .deb. Der Workflow *Release* (Actions → Run workflow) baut es auf
GitHub und veröffentlicht ein Release für die Version aus `hearthwatch/__init__.py`.
Ablauf mit Branches und Releases: [CONTRIBUTING.md](CONTRIBUTING.md).

## Danke an

[hearthstone-linux-gui](https://github.com/DawnMagnet/hearthstone-linux-gui) für Hearthstone unter
Linux, [HearthSim](https://github.com/HearthSim) (`hslog` und Hearthstone Deck Tracker haben den Weg
durch die Logs gezeigt) und [HearthstoneJSON](https://hearthstonejson.com) für Kartendaten und
-bilder.

Hearthstone ist eine Marke von Blizzard Entertainment. Hearthwatch ist ein Fan-Projekt und steht in
keiner Verbindung zu Blizzard.

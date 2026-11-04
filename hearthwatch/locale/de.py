"""German translations. Keys are the English source texts used with ``_()``.

Game terms follow the German Hearthstone client: Gasthausstufe, Gasthauszauber,
Diener, Dienertypen, Blutedelsteine, Untote, Stacheleber.
"""

DE: dict[str, str] = {
    # --- shared ---
    "%Y-%m-%d %H:%M": "%d.%m.%Y %H:%M",
    "yes": "ja",
    "no": "nein",

    # --- diagnose ---
    "Flatpak version": "Flatpak-Version",
    "DEB/AppImage version": "DEB/AppImage-Version",
    "Hearthstone installed": "Hearthstone installiert",
    "{path} ({kind} of the launcher)": "{path} ({kind} des Launchers)",
    "{path} (log folder found)": "{path} (Log-Ordner gefunden)",
    "Not found, looked in {path} and others": "Nicht gefunden, gesucht u.a. in {path}",
    "Install Hearthstone in the launcher (hearthstone-linux-gui) with “Install / Update”. "
    "If it lives somewhere else, set HEARTHWATCH_GAME_DIR=/path/to/game.":
        "Hearthstone im Launcher (hearthstone-linux-gui) mit „Install / Update“ installieren. "
        "Liegt es woanders, HEARTHWATCH_GAME_DIR=/pfad/zum/game setzen.",
    "Game settings folder": "Spiel-Einstellungsordner",
    "{path} (options.txt found)": "{path} (options.txt vorhanden)",
    "No options.txt yet – probably {path}": "Noch keine options.txt – vermutlich {path}",
    "Start Hearthstone once from the launcher and quit it again; "
    "then Hearthwatch knows for sure where log.config belongs.":
        "Hearthstone einmal über den Launcher starten und wieder beenden; "
        "dann weiß Hearthwatch sicher, wohin die log.config gehört.",
    "{path} is broken: {problem}": "{path} ist beschädigt: {problem}",
    "“Set up” or “hearthwatch --setup-logs” renames the old file to log.config.bak "
    "and writes a new one; then restart Hearthstone.":
        "„Einrichten“ bzw. „hearthwatch --setup-logs“ benennt die alte Datei in log.config.bak um "
        "und schreibt eine neue; danach Hearthstone neu starten.",
    "log.config is broken ({problem}). “Set up” replaces it and keeps a backup.":
        "log.config ist beschädigt ({problem}). „Einrichten“ ersetzt sie, die alte Datei wird gesichert.",
    "{path} (set up {when})": "{path} (eingerichtet {when})",
    "{path} is missing": "{path} fehlt",
    "{path}: incomplete ({entries})": "{path}: unvollständig ({entries})",
    "Create it with “Set up” or “hearthwatch --setup-logs”, then restart Hearthstone.":
        "Mit „Einrichten“ bzw. „hearthwatch --setup-logs“ anlegen, danach Hearthstone neu starten.",
    "log.config is missing – without it Hearthstone writes no Power.log.":
        "log.config fehlt – ohne sie schreibt Hearthstone keine Power.log.",
    "log.config is incomplete – without it Hearthstone writes no Power.log.":
        "log.config ist unvollständig – ohne sie schreibt Hearthstone keine Power.log.",
    "Log size limit": "Log-Größenlimit",
    "{path}: {line} is missing – it is in {overrides} though; "
    "the launcher probably rewrote client.config":
        "{path}: {line} fehlt – in {overrides} steht sie aber; "
        "der Launcher hat client.config wohl neu geschrieben",
    "{path}: {line} is missing (not in {overrides} either)":
        "{path}: {line} fehlt (auch nicht in {overrides})",
    "Otherwise Hearthstone stops writing the Power.log in the middle of a game. "
    "“Set up” or “hearthwatch --setup-logs” adds the line; then restart Hearthstone.":
        "Sonst hört Hearthstone mitten im Spiel auf, die Power.log zu schreiben. "
        "„Einrichten“ bzw. „hearthwatch --setup-logs“ ergänzt die Zeile, danach Hearthstone neu starten.",
    "Log size limit active – Hearthstone would stop logging in the middle of a game.":
        "Log-Größenlimit aktiv – Hearthstone hört sonst mitten im Spiel auf zu protokollieren.",
    "{path} is missing (game not installed?); in launcher overrides: {state}":
        "{path} fehlt (Spiel nicht installiert?); in Launcher-Overrides: {state}",
    "Run “hearthwatch --setup-logs” after the launcher installed the game.":
        "Nach der Installation durch den Launcher „hearthwatch --setup-logs“ ausführen.",
    "Quit Hearthstone completely and start it again from the launcher – "
    "log.config is only read when the game starts.":
        "Hearthstone komplett beenden und über den Launcher neu starten – "
        "die log.config wird nur beim Spielstart gelesen.",
    "Start a game – the Power.log only appears in a match. If it is still missing afterwards, "
    "the game does not read log.config at this place: please report the output of "
    "“hearthwatch --check”.":
        "Eine Partie starten – die Power.log entsteht erst im Spiel. Fehlt sie danach immer noch, "
        "liest das Spiel die log.config an diesem Ort nicht: bitte die Ausgabe von "
        "„hearthwatch --check“ melden.",
    "None yet – set up log.config first.": "Noch keine – erst die log.config einrichten.",
    "Hearthstone ran since the setup ({session}), but there is no Power.log yet.":
        "Hearthstone lief seit dem Einrichten ({session}), aber es gibt noch keine Power.log.",
    "Hearthstone has not been started since log.config was set up.":
        "Hearthstone wurde seit dem Einrichten der log.config noch nicht gestartet.",
    "The current session ({session}) has no Power.log yet; the last one is from {old}.":
        "Die aktuelle Sitzung ({session}) hat noch keine Power.log; die letzte stammt aus {old}.",
    "{where} – without details (Verbose off): boards and minions cannot be read.":
        "{where} – ohne Details (Verbose aus): Boards und Diener können nicht erkannt werden.",
    "Check log.config (Verbose=true). ": "log.config prüfen (Verbose=true). ",

    # --- command line ---
    "Next step: quit Hearthstone completely and start it again from the launcher.":
        "Nächster Schritt: Hearthstone komplett beenden und über den Launcher neu starten.",
    "Database: {path}": "Datenbank: {path}",
    "Log file: {path}": "Protokoll: {path}",
    "All set – Hearthwatch can read along.": "Alles eingerichtet – Hearthwatch kann mitlesen.",
    "Next step: {hint}": "Nächster Schritt: {hint}",
    "Could not write {path}: {error}": "Konnte {path} nicht schreiben: {error}",
    "next to the game's options.txt": "neben der options.txt des Spiels",
    "at the default place (game never started?)": "am Standardort (Spiel noch nie gestartet?)",
    "log.config created: {path}": "log.config angelegt: {path}",
    "The old file was broken ({problem}); it is kept next to it as {backup}":
        "Die alte Datei war beschädigt ({problem}) und liegt jetzt als Sicherung daneben: {backup}",
    "log.config is already set up: {path}": "log.config ist bereits eingerichtet: {path}",
    "Note: run “hearthwatch --check” after the first game start – if options.txt "
    "is somewhere else, just run --setup-logs again.":
        "Hinweis: Nach dem ersten Spielstart „hearthwatch --check“ ausführen – liegt die "
        "options.txt woanders, einfach --setup-logs erneut aufrufen.",
    "Could not lift the log size limit: {error}": "Konnte das Log-Größenlimit nicht abschalten: {error}",
    "Log size limit lifted ({line}): {path}": "Log-Größenlimit abgeschaltet ({line}): {path}",
    "Log size limit is already lifted: {path}": "Log-Größenlimit ist bereits abgeschaltet: {path}",
    "client.config is missing (game not installed?) – run “hearthwatch --setup-logs” "
    "again after the installation.":
        "client.config fehlt noch (Spiel nicht installiert?) – nach der Installation "
        "„hearthwatch --setup-logs“ erneut ausführen.",
    "[Round {round}] Combat against {hero} (tier {tier})":
        "[Runde {round}] Kampf gegen {hero} (Gasthausstufe {tier})",
    "You      : {board}": "Du       : {board}",
    "Opponent : {board}": "Gegner   : {board}",
    "Simulation: win {win:.0%}  draw {draw:.0%}  loss {loss:.0%}":
        "Simulation: Sieg {win:.0%}  Unentschieden {draw:.0%}  Niederlage {loss:.0%}",
    "(not modelled: {cards})": "(nicht modelliert: {cards})",
    "Actual: {result}": "Tatsächlich: {result}",
    "Game over: {hero} – place {place}, round {round}, tier {tier}, types: {types}":
        "Spielende: {hero} – Platz {place}, Runde {round}, Gasthausstufe {tier}, Dienertypen: {types}",
    "No games found in this file (is it a Power.log?).":
        "Keine Spiele in dieser Datei gefunden (ist es eine Power.log?).",
    "Simulator: most likely result matched in {hits} of {total} combats ({rate:.0%}).":
        "Simulator: wahrscheinlichstes Ergebnis in {hits} von {total} Kämpfen getroffen ({rate:.0%}).",
    "Imported {count} new games from {path}.": "{count} neue Spiele aus {path} importiert.",
    "Hearthstone Battlegrounds tracker for hearthstone-linux-gui":
        "Hearthstone-Schlachtfeld-Tracker für hearthstone-linux-gui",
    "check the setup and show the next step": "Einrichtung prüfen und den nächsten Schritt anzeigen",
    "set up Hearthstone's logging (log.config, log size limit)":
        "Logging von Hearthstone einrichten (log.config, Log-Größenlimit)",
    "read a Power.log (without GUI)": "eine Power.log auswerten (ohne GUI)",
    "with --replay: simulate combats and compare with the result":
        "mit --replay: Kämpfe simulieren und mit dem Ergebnis vergleichen",
    "with --replay: show the game objects, stats and buffs of every combat":
        "mit --replay: pro Kampf die benutzten Spiel-Objekte, Werte und Buffs zeigen",
    "add games from existing logs to the history": "Spiele aus vorhandenen Logs in die Historie übernehmen",
    "do not download card data or images": "keine Kartendaten oder Bilder herunterladen",
    "language of the interface and card names (default: settings, else system)":
        "Sprache der Oberfläche und Kartennamen (Standard: Einstellungen, sonst System)",
    "more messages": "ausführliche Meldungen",
    "GTK 4 / libadwaita could not be loaded ({error}).": "GTK 4 / libadwaita konnten nicht geladen werden ({error}).",
    "Install them with: {command}": "Installation: {command}",

    # --- minion types (as on the German cards) ---
    "Beast": "Wildtier",
    "Demon": "Dämon",
    "Dragon": "Drache",
    "Elemental": "Elementar",
    "Mech": "Mech",
    "Murloc": "Murloc",
    "Naga": "Naga",
    "Pirate": "Pirat",
    "Quilboar": "Stacheleber",
    "Undead": "Untot",
    "All": "Alle",

    # --- combat results, keywords, widgets ---
    "Win": "Sieg",
    "Loss": "Niederlage",
    "Draw": "Unentschieden",
    "{result}, {damage} damage": "{result}, {damage} Schaden",
    "Taunt": "Spott",
    "Divine Shield": "Gottesschild",
    "Reborn": "Wiederkehr",
    "Poisonous": "Giftig",
    "Windfury": "Windzorn",
    "Mega-Windfury": "Mega-Windzorn",
    "Cleave": "Spaltangriff",
    "Deathrattle": "Todesröcheln",
    "Shield": "Schild",
    "Poison": "Gift",
    "Wind": "Wind",
    "Mega-Wind": "Mega-Wind",
    "DR": "Todesr.",
    "{count} buff": "{count} Buff",
    "{count} buffs": "{count} Buffs",
    "empty board": "leeres Board",

    # --- tracker / service ---
    "Tavern spells": "Gasthauszauber",
    "Blood Gems": "Blutedelsteine",
    "Elementals": "Elementare",
    "Gold next turn": "Gold nächste Runde",
    "Free refreshes": "Gratis-Aktualisierungen",
    "same card:": "gleiche Karte:",
    "Your minions in combat": "Deine Diener im Kampf",
    "Opponent minions in combat": "Gegner-Diener im Kampf",
    "Your minions in other zones:": "Deine Diener in anderen Zonen:",
    "You left the last game, but Hearthstone did not log it to the end – usually because "
    "of the log size limit. Restart Hearthstone completely and the next game will be logged in full.":
        "Das letzte Spiel wurde verlassen, aber Hearthstone hat es nicht bis zum Ende "
        "protokolliert – meist wegen des Log-Größenlimits. Hearthstone komplett neu starten, "
        "dann wird das nächste Spiel vollständig mitgeschrieben.",
    "(none)": "(keine)",
    "line {line} comes before the first [section]": "Zeile {line} steht vor dem ersten [Abschnitt]",
    "invalid line(s) {lines} (without “=”)": "ungültige Zeile(n) {lines} (ohne „=“)",
    "malformed ({error})": "fehlerhaft ({error})",

    # --- app window ---
    "History & statistics": "Historie & Statistik",
    "Check setup": "Einrichtung prüfen",
    "Set up logging": "Logging einrichten",
    "Settings": "Einstellungen",
    "About Hearthwatch": "Über Hearthwatch",
    "Details": "Details",
    "Set up": "Einrichten",
    "Hearthstone stopped writing the Power.log (10 MB log size limit reached). "
    "Click “Set up”, then restart Hearthstone completely.":
        "Hearthstone schreibt keine Power.log mehr (Log-Größenlimit von 10 MB erreicht). "
        "„Einrichten“, dann Hearthstone komplett neu starten.",
    "No log folder found ({path}). Is Hearthstone installed with "
    "hearthstone-linux-gui? Hearthwatch keeps waiting.":
        "Kein Log-Ordner gefunden ({path}). Ist Hearthstone über "
        "hearthstone-linux-gui installiert? Hearthwatch wartet weiter.",
    "Card data not available – showing card IDs.": "Kartendaten nicht verfügbar – es werden Karten-IDs angezeigt.",
    "Game saved: place {place} with {hero}": "Spiel gespeichert: Platz {place} mit {hero}",
    "Setup failed: {error}": "Einrichten fehlgeschlagen: {error}",
    "Changed: {files} – please restart Hearthstone completely.":
        "Geändert: {files} – bitte Hearthstone komplett neu starten.",
    "Everything is already set up.": "Alles ist bereits eingerichtet.",
    "client.config not found – see “Check setup” for details.":
        "client.config wurde nicht gefunden – Details unter „Einrichtung prüfen“.",
    "Battlegrounds tracker for Hearthstone on Linux (hearthstone-linux-gui).\n"
    "Card data: HearthstoneJSON. Not affiliated with Blizzard Entertainment.":
        "Schlachtfeld-Tracker für Hearthstone unter Linux (hearthstone-linux-gui).\n"
        "Kartendaten: HearthstoneJSON. Nicht mit Blizzard Entertainment verbunden.",

    # --- settings ---
    "Automatic (system)": "Automatisch (System)",
    "Language": "Sprache",
    "Interface and card names": "Oberfläche und Kartennamen",
    "Display": "Anzeige",
    "Card art": "Kartenbilder",
    "Pictures of heroes and minions (downloaded once)": "Bilder von Helden und Dienern (werden einmal geladen)",
    "Font size": "Schriftgröße",
    "in percent": "in Prozent",
    "Sections": "Bereiche",
    "What the live view shows": "Was in der Live-Ansicht erscheint",
    "Your buffs": "Deine Buffs",
    "Game-wide buffs and your current board": "Spielweite Buffs und dein aktuelles Board",
    "Results": "Verlauf",
    "Result dots of all combats in this game": "Ergebnis-Punkte aller Kämpfe dieses Spiels",
    "Minion types": "Dienertypen",
    "Types seen and missing in this lobby": "Gesehene und fehlende Dienertypen dieser Lobby",
    "Boards in the lobby": "Boards in der Lobby",
    "Last board of every opponent as small cards": "Letztes Board jedes Gegners als Mini-Kärtchen",
    "Simulation": "Simulation",
    "Simulations per combat": "Simulationen pro Kampf",
    "more = more accurate, but slower": "mehr = genauer, aber langsamer",

    # --- setup check window ---
    "Check again": "Erneut prüfen",
    "Copy report": "Bericht kopieren",
    "Copy the result to the clipboard": "Ergebnis in die Zwischenablage kopieren",
    "So Hearthwatch can read along": "Damit Hearthwatch mitlesen kann",
    "Hearthstone only writes the Power.log if a matching log.config sits next to "
    "its options.txt. This list shows which step is still missing.":
        "Hearthstone schreibt die Power.log nur, wenn neben seiner options.txt "
        "eine passende log.config liegt. Diese Liste zeigt, welcher Schritt noch fehlt.",
    "Set up log.config": "log.config einrichten",
    "Report copied": "Bericht kopiert",

    # --- history ---
    "Statistics": "Statistik",
    "Games": "Spiele",
    "Avg. place": "Ø Platz",
    "Wins": "Siege",
    "Heroes": "Helden",
    "{games} games · Top 4: {top4} · Wins: {wins}": "{games} Spiele · Top 4: {top4} · Siege: {wins}",
    "Avg. {place:.2f}": "Ø {place:.2f}",
    "No games saved yet. Finished Battlegrounds games show up here "
    "automatically; older logs can be added with “hearthwatch --import-logs”.":
        "Noch keine Spiele gespeichert. Fertige Schlachtfeld-Spiele erscheinen hier "
        "automatisch; ältere Logs lassen sich mit „hearthwatch --import-logs“ übernehmen.",
    "{date} · Round {round} · Tier {tier}": "{date} · Runde {round} · Gasthausstufe {tier}",
    "no final board saved": "kein Endboard gespeichert",
    "MMR after the game (0 = empty)": "MMR nach dem Spiel (0 = leer)",
    "Delete game from history": "Spiel aus der Historie löschen",
    "History": "Historie",
    "Refresh": "Aktualisieren",

    # --- live view ---
    "Start Hearthstone with hearthstone-linux-gui and join a Battlegrounds game.":
        "Starte Hearthstone über hearthstone-linux-gui und betritt ein Schlachtfeld-Spiel.",
    "Recruit": "Rekrutierung",
    "Combat": "Kampf",
    "{n} W": "{n} S",
    "{n} L": "{n} N",
    "{n} D": "{n} U",
    "Waiting for a Battlegrounds game": "Warte auf ein Schlachtfeld-Spiel",
    "Round": "Runde",
    "Tier": "Stufe",
    "Tavern tier": "Gasthausstufe",
    "Place": "Platz",
    "Health": "Leben",
    "Round {round} against {hero}: {result}": "Runde {round} gegen {hero}: {result}",
    "{damage} damage": "{damage} Schaden",
    "Last combat (round {round}) against {hero}: {result}":
        "Letzter Kampf (Runde {round}) gegen {hero}: {result}",
    "predicted {chance:.0%} {result}": "Vorhersage {chance:.0%} {result}",
    "Next opponent": "Nächster Gegner",
    "not known yet": "noch unbekannt",
    "Tier {tier}": "Stufe {tier}",
    "(↑ round {round})": "(↑ Runde {round})",
    "Record {record}": "Bilanz {record}",
    "Board from round {round}": "Board aus Runde {round}",
    "Board not seen yet": "Board noch nicht gesehen",
    "Combat · round {round}": "Kampf · Runde {round}",
    "against {hero} · tier {tier}": "gegen {hero} · Gasthausstufe {tier}",
    "Simulating …": "Simuliere …",
    "avg. {damage:.1f} damage dealt": "Ø {damage:.1f} Schaden verursacht",
    "avg. {damage:.1f} damage taken": "Ø {damage:.1f} Schaden erhalten",
    "rough – not modelled: {cards}": "ungenau – nicht modelliert: {cards}",
    "{runs} simulations": "{runs} Simulationen",
    "Careful: this combat is lethal in {risk:.0%} of the simulations!":
        "Achtung: Dieser Kampf ist in {risk:.0%} der Simulationen tödlich!",
    "no game-wide buffs yet": "noch keine spielweiten Buffs",
    "Your board": "Dein Board",
    "no minions yet": "noch keine Diener",
    "No players known yet": "Noch keine Mitspieler bekannt",
    "You": "Du",
    "Next": "Nächster",
    "out": "ausgeschieden",
    "↑R{round}": "↑R{round}",
    "not seen yet": "noch nicht gesehen",
    "Place {place} of {players}": "Platz {place} von {players}",
    "Game over": "Spiel beendet",
    "Round {round} · Tier {tier}": "Runde {round} · Gasthausstufe {tier}",
    "Draws": "Unentschieden",
    "Losses": "Niederlagen",
    "Predicted": "Vorhersage",
    "Final board": "Endboard",
    "no board saved": "kein Board gespeichert",
    "Combats": "Kämpfe",
    "No combats recorded": "Keine Kämpfe erfasst",
    "The next game starts a new view automatically. "
    "All games are in the history (button at the top left).":
        "Mit dem nächsten Spiel beginnt automatisch eine neue Ansicht. "
        "Alle Spiele findest du in der Historie (Knopf oben links).",
    "Predicted: {chance:.0%} {result}": "Vorhersage: {chance:.0%} {result}",
    "Win {win:.0%} · Draw {draw:.0%} · Loss {loss:.0%}":
        "Sieg {win:.0%} · Unentschieden {draw:.0%} · Niederlage {loss:.0%}",
    "unknown": "unbekannt",

    # --- version check ---
    "{name} {have} is too old, Hearthwatch needs {need} or newer.":
        "{name} {have} ist zu alt, Hearthwatch braucht {need} oder neuer.",
    "Aberration": "Abscheulichkeit",

    # --- minion browser ---
    "Minions by tier": "Diener nach Gasthausstufe",
    "No card data yet – it is downloaded at the first start.":
        "Noch keine Kartendaten – sie werden beim ersten Start heruntergeladen.",
    "Tavern tier {tier}": "Gasthausstufe {tier}",
    "your tier": "deine Stufe",
    "Not in a game: all minions are shown.": "Kein laufendes Spiel: alle Diener werden gezeigt.",
    "Minion types in this lobby: {types}": "Dienertypen in dieser Lobby: {types}",
    "Not all minion types are known yet – faded types may not be in this game.":
        "Noch nicht alle Dienertypen bekannt – blasse Typen sind vielleicht nicht im Spiel.",
    "Neutral": "Neutral",

    # --- anomaly, triples, trinkets ---
    "{n} triple": "{n} Drilling",
    "{n} triples": "{n} Drillinge",
    "Trinkets: {names}": "Schmuckstücke: {names}",
    "Anomaly: {name}": "Anomalie: {name}",
    "(last in round {round})": "(zuletzt Runde {round})",
    "Buffs:": "Buffs:",
    "In this lobby": "In dieser Lobby",
    "Not in this lobby: {types}": "Nicht in dieser Lobby: {types}",
    "Hearthstone was not found. Install it with hearthstone-linux-gui.":
        "Hearthstone wurde nicht gefunden. Installiere es mit hearthstone-linux-gui.",
    "Simulated with AutoTavern ({runs} combats)": "Simuliert mit AutoTavern ({runs} Kämpfe)",
    "Built-in simulator – it knows only some card effects": "Eingebauter Simulator – kennt nur einen Teil der Karteneffekte",
    "Grow with the window": "Mit dem Fenster wachsen",
    "Bigger pictures and text in a big window": "Größere Bilder und Schrift in einem großen Fenster",
    "Choosing a hero…": "Heldenwahl …",
    "Your heroes to choose from": "Deine Helden zur Auswahl",
    "Beetles {attack}/{health}": "Käfer {attack}/{health}",
    "Undead +{attack} Attack": "Untote +{attack} Angriff",
}

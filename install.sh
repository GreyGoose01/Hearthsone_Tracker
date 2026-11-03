#!/usr/bin/env bash
# Installs Hearthwatch on Ubuntu (tested on 24.04/26.04).
#   ./install.sh            install / update
#   ./install.sh --remove   uninstall
set -euo pipefail
cd "$(dirname "$0")"

APP_ID=io.github.greygoose01.hearthwatch
OLD_ID=io.github.greygoose01.bgtracker   # name before the rename
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICON_ROOT="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor"
ICONS="$ICON_ROOT/256x256/apps"
OLD_ICONS="$ICON_ROOT/scalable/apps"   # svg icons before 0.2.1

remove_old() {
    pipx uninstall bgtracker >/dev/null 2>&1 || true
    rm -f "$APPS/$OLD_ID.desktop" "$OLD_ICONS/$OLD_ID.svg" "$OLD_ICONS/$APP_ID.svg"
}

if [[ "${1:-}" == "--remove" ]]; then
    pipx uninstall hearthwatch || true
    remove_old
    rm -f "$APPS/$APP_ID.desktop" "$ICONS/$APP_ID.png"
    echo "Removed. Your match history stays in ~/.local/share/hearthwatch."
    exit 0
fi

missing=()
for pkg in python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 pipx; do
    dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q "install ok installed" || missing+=("$pkg")
done
if ((${#missing[@]})); then
    echo "Missing packages: ${missing[*]}"
    sudo apt install -y "${missing[@]}"
fi

remove_old
# Use the system Python with the apt packages (PyGObject). Reinstall cleanly,
# because pipx ignores --python together with --force.
pipx uninstall hearthwatch >/dev/null 2>&1 || true
pipx install --python /usr/bin/python3 --system-site-packages .

BIN="$(pipx environment --value PIPX_BIN_DIR 2>/dev/null || echo "$HOME/.local/bin")/hearthwatch"

mkdir -p "$APPS" "$ICONS"
sed "s|@HEARTHWATCH@|$BIN|" "data/$APP_ID.desktop" > "$APPS/$APP_ID.desktop"
cp "data/$APP_ID.png" "$ICONS/$APP_ID.png"
update-desktop-database "$APPS" >/dev/null 2>&1 || true
gtk-update-icon-cache -q -t "$ICON_ROOT" >/dev/null 2>&1 || true

"$BIN" --setup-logs
echo
"$BIN" --check || true
echo
echo "Done. Start Hearthwatch from the app menu or with: $BIN"
echo "Important: restart Hearthstone once after setting up the logs."

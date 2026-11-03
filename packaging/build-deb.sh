#!/usr/bin/env bash
# Builds dist/hearthwatch_<version>_all.deb - pure Python, nothing to compile.
#   packaging/build-deb.sh
# Install it with: sudo apt install ./dist/hearthwatch_<version>_all.deb
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' hearthwatch/__init__.py)
APP_ID=io.github.greygoose01.hearthwatch
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
PKG="$WORK/hearthwatch_${VERSION}_all"
SITE="$PKG/usr/lib/python3/dist-packages"
SHARE="$PKG/usr/share"

mkdir -p "$PKG/DEBIAN" "$PKG/usr/bin" "$SITE" "$SHARE/applications" \
         "$SHARE/icons/hicolor/256x256/apps" "$SHARE/metainfo" "$SHARE/doc/hearthwatch"

tar --exclude='__pycache__' --exclude='*.pyc' -cf - hearthwatch | tar -xf - -C "$SITE"
cat > "$PKG/usr/bin/hearthwatch" <<'EOF'
#!/usr/bin/python3
import sys

from hearthwatch.cli import main

sys.exit(main())
EOF
sed "s|@HEARTHWATCH@|hearthwatch|" "data/$APP_ID.desktop" > "$SHARE/applications/$APP_ID.desktop"
cp "data/$APP_ID.png" "$SHARE/icons/hicolor/256x256/apps/$APP_ID.png"
cp "data/$APP_ID.metainfo.xml" "$SHARE/metainfo/$APP_ID.metainfo.xml"
cp README.md README.de.md "$SHARE/doc/hearthwatch/"

cat > "$PKG/DEBIAN/control" <<EOF
Package: hearthwatch
Version: $VERSION
Section: games
Priority: optional
Architecture: all
Depends: python3 (>= 3.12), python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1
Installed-Size: $(du -sk "$PKG/usr" | cut -f1)
Maintainer: GreyGoose01 <GreyGoose01@users.noreply.github.com>
Homepage: https://github.com/GreyGoose01/hearthwatch
Description: Battlegrounds tracker for Hearthstone on Linux
 Hearthwatch is a live tracker for Hearthstone Battlegrounds, made for
 hearthstone-linux-gui: next opponent, combat odds from a built-in
 simulator, your buffs, the lobby and a match history. It only reads the
 log files Hearthstone writes. Not affiliated with Blizzard Entertainment.
EOF
cat > "$PKG/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
if [ "$1" = "configure" ]; then
    python3 -m compileall -q /usr/lib/python3/dist-packages/hearthwatch >/dev/null 2>&1 || true
fi
EOF
cat > "$PKG/DEBIAN/prerm" <<'EOF'
#!/bin/sh
set -e
find /usr/lib/python3/dist-packages/hearthwatch -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
EOF

find "$PKG" -type d -exec chmod 755 {} +
find "$PKG" -type f -exec chmod 644 {} +
chmod 755 "$PKG/usr/bin/hearthwatch" "$PKG/DEBIAN/postinst" "$PKG/DEBIAN/prerm"

mkdir -p dist
dpkg-deb --root-owner-group -Zxz --build "$PKG" "dist/hearthwatch_${VERSION}_all.deb" >/dev/null
echo "dist/hearthwatch_${VERSION}_all.deb"

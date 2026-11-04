#!/usr/bin/env bash
# Builds dist/hearthwatch_<version>_<arch>.deb.
#   packaging/build-deb.sh
#   AUTOTAVERN_DIR=dist/autotavern packaging/build-deb.sh   (with the AutoTavern simulator,
#                                                            see packaging/build-autotavern.sh)
# Without AutoTavern the package is pure Python ("all"); with it, it is built for
# this machine's architecture. Install it with: sudo apt install ./dist/hearthwatch_*.deb
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION=$(sed -n 's/^__version__ = "\(.*\)"/\1/p' hearthwatch/__init__.py)
APP_ID=io.github.greygoose01.hearthwatch
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
ARCH=all
DEPENDS="python3 (>= 3.12), python3-gi, gir1.2-gtk-4.0 (>= 4.12), gir1.2-adw-1 (>= 1.4)"
if [ -n "${AUTOTAVERN_DIR:-}" ]; then
    ARCH=$(dpkg --print-architecture)
    DEPENDS="$DEPENDS, libc6 (>= 2.34), libgcc-s1"
fi
PKG="$WORK/hearthwatch_${VERSION}_${ARCH}"
SITE="$PKG/usr/lib/python3/dist-packages"
SHARE="$PKG/usr/share"

mkdir -p "$PKG/DEBIAN" "$PKG/usr/bin" "$SITE" "$SHARE/applications" \
         "$SHARE/icons/hicolor/256x256/apps" "$SHARE/metainfo" "$SHARE/doc/hearthwatch"

tar --exclude='__pycache__' --exclude='*.pyc' --exclude='hearthwatch/_vendor' -cf - hearthwatch | tar -xf - -C "$SITE"
if [ -n "${AUTOTAVERN_DIR:-}" ]; then
    VENDOR="$SITE/hearthwatch/_vendor/taverngym_core"
    mkdir -p "$VENDOR"
    printf '"""Bundled third-party code."""\n' > "$SITE/hearthwatch/_vendor/__init__.py"
    printf '"""AutoTavern (MIT, github.com/MCG-NJU/AutoTavern) - its compiled simulator only."""\n' \
        > "$VENDOR/__init__.py"
    cp "$AUTOTAVERN_DIR/_core.abi3.so" "$VENDOR/_core.abi3.so"
fi
cat > "$PKG/usr/bin/hearthwatch" <<'EOF'
#!/usr/bin/python3
import sys

from hearthwatch.cli import main

sys.exit(main())
EOF
sed "s|@HEARTHWATCH@|hearthwatch|" "data/$APP_ID.desktop" > "$SHARE/applications/$APP_ID.desktop"
cp "data/$APP_ID.png" "$SHARE/icons/hicolor/256x256/apps/$APP_ID.png"
cp "data/$APP_ID.metainfo.xml" "$SHARE/metainfo/$APP_ID.metainfo.xml"
cp README.md README.de.md LICENSE "$SHARE/doc/hearthwatch/"
cp LICENSE "$SHARE/doc/hearthwatch/copyright"
if [ -n "${AUTOTAVERN_DIR:-}" ]; then
    {
        printf '\n\nThis package includes AutoTavern (TavernGym), revision %s:\n\n' "$(cat "$AUTOTAVERN_DIR/REVISION")"
        cat "$AUTOTAVERN_DIR/LICENSE"
        printf '\n'
        cat "$AUTOTAVERN_DIR/NOTICE"
    } >> "$SHARE/doc/hearthwatch/copyright"
fi

cat > "$PKG/DEBIAN/control" <<EOF
Package: hearthwatch
Version: $VERSION
Section: games
Priority: optional
Architecture: $ARCH
Depends: $DEPENDS
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
dpkg-deb --root-owner-group -Zxz --build "$PKG" "dist/hearthwatch_${VERSION}_${ARCH}.deb" >/dev/null
echo "dist/hearthwatch_${VERSION}_${ARCH}.deb"

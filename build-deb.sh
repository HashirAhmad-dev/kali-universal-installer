#!/usr/bin/env bash
# Build dist/kupi_<version>_all.deb from the source tree.
#
# Pure-Python payload -> Architecture: all. No root needed to build.
# Requires: dpkg-deb (dpkg-dev). Lints with lintian if present.
set -euo pipefail

here="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
version="${1:-1.0.0}"
arch="all"

stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT
root="$stage/kupi_${version}_${arch}"

pydir="$root/usr/lib/python3/dist-packages"
mkdir -p \
    "$root/DEBIAN" \
    "$root/usr/bin" \
    "$pydir" \
    "$root/usr/share/applications" \
    "$root/usr/share/doc/kupi" \
    "$root/usr/share/man/man1" \
    "$root/usr/share/icons/hicolor/scalable/apps"

# --- application code (standard Debian Python module location) -------------
cp -r "$here/kupi" "$pydir/kupi"
find "$pydir/kupi" -name '__pycache__' -type d -exec rm -rf {} +
find "$pydir/kupi" -name '*.pyc' -delete

# --- launcher ------------------------------------------------------------
cat > "$root/usr/bin/kupi" <<'EOF'
#!/bin/sh
exec python3 -m kupi "$@"
EOF

# --- desktop entry + icon ----------------------------------------------------
cp "$here/packaging/kupi.desktop" "$root/usr/share/applications/kupi.desktop"
cp "$here/packaging/kupi.svg" "$root/usr/share/icons/hicolor/scalable/apps/kupi.svg"

# --- docs ------------------------------------------------------------------
cp "$here/packaging/copyright" "$root/usr/share/doc/kupi/copyright"
cp "$here/README.md" "$root/usr/share/doc/kupi/README.md"
# Native package (version has no Debian revision) -> changelog.gz, not .Debian.
sed -e "s/@VERSION@/$version/" -e "s/@DATE@/$(date -R)/" \
    "$here/packaging/changelog" \
    | gzip -9 -n > "$root/usr/share/doc/kupi/changelog.gz"
gzip -9 -n < "$here/packaging/kupi.1" > "$root/usr/share/man/man1/kupi.1.gz"

# --- permissions -------------------------------------------------------------
find "$root" -type d -exec chmod 0755 {} +
find "$pydir/kupi" -type f -exec chmod 0644 {} +
chmod 0644 \
    "$root/usr/share/applications/kupi.desktop" \
    "$root/usr/share/icons/hicolor/scalable/apps/kupi.svg" \
    "$root/usr/share/man/man1/kupi.1.gz" \
    "$root/usr/share/doc/kupi/"*
chmod 0755 "$root/usr/bin/kupi"

# --- control + maintainer scripts -----------------------------------------
installed_kb="$(du -sk "$root/usr" | cut -f1)"
sed -e "s/@VERSION@/$version/" -e "s/@INSTALLED_SIZE@/$installed_kb/" \
    "$here/packaging/control" > "$root/DEBIAN/control"
cp "$here/packaging/postinst" "$root/DEBIAN/postinst"
chmod 0755 "$root/DEBIAN/postinst"

# --- md5sums (recommended) ------------------------------------------------
( cd "$root" && find usr -type f -exec md5sum {} + | sort -k2 > DEBIAN/md5sums )
chmod 0644 "$root/DEBIAN/md5sums"

# --- build -----------------------------------------------------------------
mkdir -p "$here/dist"
out="$here/dist/kupi_${version}_${arch}.deb"
dpkg-deb --root-owner-group --build "$root" "$out"

echo
echo "=== $out ==="
dpkg-deb --info "$out"
echo "--- contents ---"
dpkg-deb --contents "$out"
if command -v lintian >/dev/null 2>&1; then
    echo "--- lintian ---"
    lintian "$out" || true
fi

#!/usr/bin/env bash
# Register the installer in your application menu (and as an "Open With" target
# for .deb / .rpm files). Re-run any time; it just rewrites the entry.
#
#   ./install-desktop.sh            install for the current user
#   ./install-desktop.sh --remove   uninstall
set -euo pipefail

here="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
apps_dir="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
desktop="$apps_dir/kali-universal-installer.desktop"

if [[ "${1:-}" == "--remove" ]]; then
    rm -f "$desktop"
    update-desktop-database "$apps_dir" 2>/dev/null || true
    echo "Removed $desktop"
    exit 0
fi

mkdir -p "$apps_dir"
cat > "$desktop" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Kali Universal Package Installer
Comment=Drag-and-drop installer for .deb, .rpm, .AppImage, .run, .sh, archives, .snap, .flatpak
Exec=$here/run.sh %f
Icon=system-software-install
Terminal=false
Categories=System;PackageManager;
MimeType=application/vnd.debian.binary-package;application/x-rpm;application/x-shellscript;
StartupNotify=true
EOF
chmod +x "$desktop"
update-desktop-database "$apps_dir" 2>/dev/null || true

echo "Installed $desktop"
echo "Launch it from the application menu, or pin it to the panel."
echo "Right-click a .deb in your file manager -> Open With -> Kali Universal Package Installer."

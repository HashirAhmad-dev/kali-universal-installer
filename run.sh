#!/usr/bin/env bash
# Launch the Kali Universal Package Installer.
#
# Self-bootstrapping: on first run it creates .venv and installs dependencies,
# then every run just execs the GUI. Safe to call from anywhere (a menu entry,
# a keyboard shortcut, a symlink on $PATH).
#
#   ./run.sh                 launch
#   ./run.sh some-package.deb launch with that file preloaded
set -euo pipefail

here="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
venv_py="$here/.venv/bin/python"

if [[ ! -x "$venv_py" ]]; then
    echo "First run: creating virtualenv in $here/.venv ..." >&2
    python3 -m venv "$here/.venv"
    "$here/.venv/bin/pip" install --upgrade --quiet pip
    "$here/.venv/bin/pip" install --quiet -r "$here/requirements.txt"
    echo "Dependencies installed." >&2
fi

exec "$venv_py" "$here/main.py" "$@"

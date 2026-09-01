"""``.AppImage`` -- no system install; ``chmod +x`` then run, or "install".

Preflight is one choice:

* **Run once** -- ``chmod +x`` then execute in place (attached, so output
  streams and Cancel works; the process ends when you close the app).
* **Install to ~/Applications** -- move the file there, make it executable, and
  write a ``.desktop`` launcher into ``~/.local/share/applications`` so it shows
  up in the menu. The launcher is tagged ``X-KUPI-Managed=true`` for later
  cleanup tooling.

No icon is extracted (that needs unpacking the AppImage); the launcher uses a
generic icon. AppImages self-mount via FUSE -- if a run fails with a
``libfuse.so.2`` error, ``libfuse2``/``libfuse2t64`` is missing.
"""
from __future__ import annotations

import os
import re

from ..model import Command, InstallPlan, Preflight
from .base import PackageHandler

_MODE_ID = "mode"
_RUN = "Run once"
_INSTALL = "Install to ~/Applications"


class AppImageHandler(PackageHandler):
    package_type = "appimage"
    extensions = (".appimage",)

    def describe(self, filepath: str) -> str:
        return "AppImage -- run in place, or install to ~/Applications with a menu entry"

    def preflight(self, filepath: str) -> list[Preflight]:
        return [
            Preflight(
                id=_MODE_ID,
                kind="choice",
                message="What do you want to do with this AppImage?",
                options=[_RUN, _INSTALL],
            )
        ]

    def build_plan(self, filepath: str, answers: dict[str, str]) -> InstallPlan:
        src = os.path.abspath(filepath)

        if answers.get(_MODE_ID) == _INSTALL:
            return self._install_plan(src)
        return self._run_plan(src)

    # ------------------------------------------------------------------ modes
    def _run_plan(self, src: str) -> InstallPlan:
        return InstallPlan(
            commands=[
                Command(["chmod", "+x", src], label="make AppImage executable"),
                Command(
                    # If the direct launch fails (commonly: no libfuse2 to
                    # self-mount), retry unpacked so it still runs.
                    ["sh", "-c", '"$1" || exec "$1" --appimage-extract-and-run', "sh", src],
                    label="run AppImage (close the app to finish)",
                    cwd=os.path.dirname(src),
                ),
            ],
            note="If no window opened, the AppImage was retried with --appimage-extract-and-run.",
        )

    def _install_plan(self, src: str) -> InstallPlan:
        apps_bin = os.path.expanduser("~/Applications")
        launchers = os.path.expanduser("~/.local/share/applications")
        dest = os.path.join(apps_bin, os.path.basename(src))
        display = re.sub(r"\.appimage$", "", os.path.basename(src), flags=re.I)
        slug = re.sub(r"[^a-z0-9]+", "-", display.lower()).strip("-") or "appimage"
        desktop_path = os.path.join(launchers, f"kupi-{slug}.desktop")

        desktop = "\n".join(
            [
                "[Desktop Entry]",
                "Type=Application",
                f"Name={display}",
                f'Exec="{dest}" %U',
                "Icon=application-x-executable",
                "Terminal=false",
                "Categories=Utility;",
                "X-KUPI-Managed=true",
                "",
            ]
        )

        return InstallPlan(
            commands=[
                Command(["mkdir", "-p", apps_bin, launchers], label="ensure target dirs"),
                Command(["mv", "-n", src, dest], label=f"move AppImage to {apps_bin}"),
                Command(["chmod", "+x", dest], label="make AppImage executable"),
                Command(
                    # $1 = desktop file content, $2 = destination path.
                    ["sh", "-c", 'printf %s "$1" > "$2"', "sh", desktop, desktop_path],
                    label="write .desktop launcher",
                ),
            ],
            note=f"Installed. Launcher: {desktop_path} (appears in the app menu).",
        )

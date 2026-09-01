"""``.snap`` -- install a local snap with ``snap install --dangerous``.

If the ``snap`` CLI is missing, preflight offers to install ``snapd`` via apt.
``--dangerous`` is required for a local, unsigned snap file. A freshly installed
snapd often needs ``systemctl enable --now snapd.socket`` and a re-login before
it works -- that surfaces in the log if so.
"""
from __future__ import annotations

import os

from ..model import Command, InstallPlan, Preflight
from .base import PackageHandler, which

_INSTALL_SNAPD = "install_snapd"


class SnapHandler(PackageHandler):
    package_type = "snap"
    extensions = (".snap",)

    def describe(self, filepath: str) -> str:
        if which("snap") is not None:
            return "Snap package -- installed locally with snap --dangerous"
        return "Snap package -- needs snapd (will offer to install it)"

    def preflight(self, filepath: str) -> list[Preflight]:
        if which("snap") is not None:
            return []
        return [
            Preflight(
                id=_INSTALL_SNAPD,
                kind="confirm",
                message=(
                    "snapd is not installed. Install it now with apt? A fresh "
                    "snapd may still need 'systemctl enable --now snapd.socket' "
                    "and a re-login."
                ),
            )
        ]

    def build_plan(self, filepath: str, answers: dict[str, str]) -> InstallPlan:
        path = os.path.abspath(filepath)

        commands: list[Command] = []
        if which("snap") is None:
            commands.append(
                Command(
                    ["apt", "install", "-y", "snapd"],
                    label="install snapd (apt)",
                    use_pkexec=True,
                )
            )
        commands.append(
            Command(
                ["snap", "install", "--dangerous", path],
                label="snap install --dangerous",
                use_pkexec=True,
            )
        )
        return InstallPlan(commands=commands)

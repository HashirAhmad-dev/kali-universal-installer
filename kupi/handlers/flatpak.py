"""``.flatpak`` / ``.flatpakref`` -- ``flatpak install --user -y <file>``.

Per-user install, so the install itself needs no root. If the ``flatpak`` CLI is
missing, preflight offers to install it via apt (that step does need root). A
``.flatpakref`` may pull dependencies from a remote; if the install fails about a
missing remote, add Flathub:

    flatpak remote-add --if-not-exists --user flathub \\
        https://flathub.org/repo/flathub.flatpakrepo
"""
from __future__ import annotations

import os

from ..model import Command, InstallPlan, Preflight
from .base import PackageHandler, which

_INSTALL_FLATPAK = "install_flatpak"


class FlatpakHandler(PackageHandler):
    package_type = "flatpak"
    extensions = (".flatpak", ".flatpakref")

    def describe(self, filepath: str) -> str:
        if which("flatpak") is not None:
            return "Flatpak -- installed per-user (flatpak install --user)"
        return "Flatpak -- needs the flatpak CLI (will offer to install it)"

    def preflight(self, filepath: str) -> list[Preflight]:
        if which("flatpak") is not None:
            return []
        return [
            Preflight(
                id=_INSTALL_FLATPAK,
                kind="confirm",
                message="The flatpak CLI is not installed. Install it now with apt?",
            )
        ]

    def build_plan(self, filepath: str, answers: dict[str, str]) -> InstallPlan:
        path = os.path.abspath(filepath)

        commands: list[Command] = []
        if which("flatpak") is None:
            commands.append(
                Command(
                    ["apt", "install", "-y", "flatpak"],
                    label="install flatpak (apt)",
                    use_pkexec=True,
                )
            )
        commands.append(
            Command(
                ["flatpak", "install", "--user", "-y", path],
                label="flatpak install --user",
            )
        )
        return InstallPlan(commands=commands)

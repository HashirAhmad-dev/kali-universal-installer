"""``.rpm`` -- convert to ``.deb`` and install with ``alien``.

``alien`` is not installed by default on Kali. If it is missing, preflight asks
to install it (``pkexec apt install -y alien``); declining aborts. The
conversion+install runs as root (``pkexec alien --install <file>``), wrapped so
it executes in the RPM's own directory -- alien writes an intermediate ``.deb``
to the working directory, installs it, then removes it.
"""
from __future__ import annotations

import os

from ..model import Command, InstallPlan, Preflight
from .base import PackageHandler, exec_step, which

_INSTALL_ALIEN = "install_alien"


class RpmHandler(PackageHandler):
    package_type = "rpm"
    extensions = (".rpm",)

    def describe(self, filepath: str) -> str:
        if which("alien") is not None:
            return "RPM package -- converted and installed with alien"
        return "RPM package -- needs 'alien' (will offer to install it), then converts"

    def preflight(self, filepath: str) -> list[Preflight]:
        if which("alien") is not None:
            return []
        return [
            Preflight(
                id=_INSTALL_ALIEN,
                kind="confirm",
                message=(
                    "Converting an RPM needs the 'alien' tool, which is not "
                    "installed. Install it now with apt?"
                ),
            )
        ]

    def build_plan(self, filepath: str, answers: dict[str, str]) -> InstallPlan:
        path = os.path.abspath(filepath)
        workdir = os.path.dirname(path)

        commands: list[Command] = []
        if which("alien") is None:
            commands.append(
                Command(
                    ["apt", "install", "-y", "alien"],
                    label="install alien (apt)",
                    use_pkexec=True,
                )
            )
        commands.append(
            exec_step(
                ["alien", "--install", path],
                workdir,
                as_root=True,
                label="convert RPM and install (alien)",
            )
        )
        return InstallPlan(
            commands=commands,
            note=(
                "alien does not run RPM maintainer scripts -- if the app needs "
                "post-install setup, check its documentation."
            ),
        )

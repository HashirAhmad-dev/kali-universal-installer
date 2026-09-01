"""``.deb`` -- install through apt so dependencies are resolved.

We deliberately use ``apt install`` rather than ``dpkg -i``: dpkg does not pull
in dependencies, apt does. The file is passed as an absolute path (which apt
recognises as a local package because it contains a ``/``); this is more robust
than ``./name`` because ``pkexec`` does not guarantee the child's working
directory.
"""
from __future__ import annotations

import os

from ..model import Command, InstallPlan
from .base import PackageHandler


class DebHandler(PackageHandler):
    package_type = "deb"
    extensions = (".deb",)

    def describe(self, filepath: str) -> str:
        return "Debian package -- installed with apt (resolves dependencies)"

    def build_plan(self, filepath: str, answers: dict[str, str]) -> InstallPlan:
        path = os.path.abspath(filepath)
        return InstallPlan(
            commands=[
                Command(
                    argv=["apt", "install", "-y", path],
                    label="apt install (with dependency resolution)",
                    use_pkexec=True,
                )
            ]
        )

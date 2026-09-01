"""``.run`` / ``.bin`` -- arbitrary self-extracting installers.

Opaque blobs (Makeself archives, NVIDIA/Unity/vendor installers, ...). There is
nothing to inspect: ``chmod +x`` then execute. Two preflights:

* a **risk acknowledgement** -- the payload is unknown and runs with whatever
  privileges are chosen;
* the same **normal user / root** choice as ``.sh`` (many of these write to
  ``/opt`` or ``/usr``).

Run attached (output streams, Cancel works), working directory = the file's own
folder.
"""
from __future__ import annotations

import os

from ..model import Command, InstallPlan, Preflight
from .base import PackageHandler, exec_step

_ACK_ID = "ack"
_PRIV_ID = "privilege"
_AS_USER = "Normal user"
_AS_ROOT = "Root (pkexec)"


class RunBinHandler(PackageHandler):
    package_type = "run_bin"
    extensions = (".run", ".bin")

    def describe(self, filepath: str) -> str:
        return "Self-extracting installer -- opaque; chmod +x then execute"

    def preflight(self, filepath: str) -> list[Preflight]:
        name = os.path.basename(filepath)
        return [
            Preflight(
                id=_ACK_ID,
                kind="warning",
                message=(
                    f"{name} is an arbitrary self-extracting installer. It "
                    "cannot be inspected first and will run with the privileges "
                    "you choose next. Continue?"
                ),
            ),
            Preflight(
                id=_PRIV_ID,
                kind="choice",
                message="Run it as which user?",
                options=[_AS_USER, _AS_ROOT],
            ),
        ]

    def build_plan(self, filepath: str, answers: dict[str, str]) -> InstallPlan:
        path = os.path.abspath(filepath)
        workdir = os.path.dirname(path)
        as_root = answers.get(_PRIV_ID) == _AS_ROOT

        chmod = Command(["chmod", "+x", path], label="make installer executable")
        run = exec_step(
            [path],
            workdir,
            as_root=as_root,
            label="run installer" + (" as root" if as_root else ""),
        )
        return InstallPlan(commands=[chmod, run])

"""``.sh`` -- vendor installer script.

``chmod +x`` then ``bash <file>``, with the working directory set to the
script's own folder (these scripts routinely reference bundled files by relative
path -- e.g. Xtreme Download Manager's ``install.sh`` beside its payload).

Privilege: many vendor installers write to ``/opt`` and ``/usr`` and refuse to
run as a normal user (XDM's ``install.sh`` prints "Only root can do this" and
exits 1). So there is one preflight choice -- normal user (default) or root via
``pkexec``. For the root case we wrap the call in ``sh -c 'cd ... && exec bash'``
because ``pkexec`` does not reliably preserve the working directory.
"""
from __future__ import annotations

import os

from ..model import Command, InstallPlan, Preflight
from .base import PackageHandler, exec_step

_PRIV_ID = "privilege"
_AS_USER = "Normal user"
_AS_ROOT = "Root (pkexec)"


class ShellHandler(PackageHandler):
    package_type = "shell"
    extensions = (".sh",)

    def describe(self, filepath: str) -> str:
        return "Shell installer script -- run with bash"

    def preflight(self, filepath: str) -> list[Preflight]:
        return [
            Preflight(
                id=_PRIV_ID,
                kind="choice",
                message=(
                    "How should this script run?\n\n"
                    "Vendor installers that write to /opt or /usr (XDM, many "
                    "others) need root -- pick that if a normal-user run fails "
                    "with a permissions error."
                ),
                options=[_AS_USER, _AS_ROOT],
            )
        ]

    def build_plan(self, filepath: str, answers: dict[str, str]) -> InstallPlan:
        path = os.path.abspath(filepath)
        workdir = os.path.dirname(path)
        as_root = answers.get(_PRIV_ID) == _AS_ROOT

        chmod = Command(["chmod", "+x", path], label="make script executable")
        run = exec_step(
            ["bash", path],
            workdir,
            as_root=as_root,
            label="run installer script" + (" as root" if as_root else ""),
        )
        return InstallPlan(commands=[chmod, run])

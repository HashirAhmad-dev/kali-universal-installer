"""``.tar.*`` / ``.tgz`` / ``.zip`` -- extract, then let app.py re-dispatch.

This handler only knows how to *extract*. The plan is a single command that
unpacks the archive into a fresh temp directory, with ``rescan_dir`` set on the
plan. :class:`kupi.runner.ProcessRunner` emits ``rescan_requested`` on success
and ``MainWindow`` takes over: it scans the tree for ``install.sh`` /
``setup.sh`` or a ``.deb`` and runs that through the matching handler, or -- if
nothing is found -- offers to move the files somewhere and tells the user it is
manual.

GNU tar auto-detects the compression from ``-xf``, so every tar variant uses the
same command.
"""
from __future__ import annotations

import os
import tempfile

from ..model import Command, InstallPlan
from .base import PackageHandler, which


class ArchiveHandler(PackageHandler):
    package_type = "archive"
    extensions = (
        ".tar.gz",
        ".tar.xz",
        ".tar.bz2",
        ".tar.zst",
        ".tgz",
        ".txz",
        ".tbz2",
        ".zip",
    )

    def describe(self, filepath: str) -> str:
        return (
            "Archive -- extracted, then scanned for an install.sh / setup.sh "
            "script or a .deb"
        )

    def build_plan(self, filepath: str, answers: dict[str, str]) -> InstallPlan:
        path = os.path.abspath(filepath)
        tmpdir = tempfile.mkdtemp(prefix="kupi-extract-")

        if path.lower().endswith(".zip"):
            if which("unzip"):
                argv = ["unzip", "-o", path, "-d", tmpdir]
            else:
                # Always-present fallback; quieter but works with no extra deps.
                argv = ["python3", "-m", "zipfile", "-e", path, tmpdir]
        else:
            argv = ["tar", "-xvf", path, "-C", tmpdir]

        return InstallPlan(
            commands=[Command(argv=argv, label=f"extract to {tmpdir}")],
            rescan_dir=tmpdir,
        )

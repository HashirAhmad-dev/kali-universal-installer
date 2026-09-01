"""The shared package-handler contract.

One concrete subclass per package type. Adding a new type is: write a subclass,
add one line to the registry in :mod:`kupi.handlers`.

A handler is pure: it inspects the file and the environment and returns data
(``Preflight`` list, ``InstallPlan``). It never spawns a process itself -- that
is :class:`kupi.runner.ProcessRunner`'s job.
"""
from __future__ import annotations

import shutil
from abc import ABC, abstractmethod

from ..model import Command, InstallPlan, Preflight


class PackageHandler(ABC):
    #: Short identifier, matches the PackageType value.
    package_type: str = ""
    #: Extensions this handler is responsible for (informational).
    extensions: tuple[str, ...] = ()
    #: False for Phase-2 stubs so the UI can grey out Install.
    implemented: bool = True

    @abstractmethod
    def describe(self, filepath: str) -> str:
        """One-line, human-readable summary shown before installing."""

    def preflight(self, filepath: str) -> list[Preflight]:
        """Questions/warnings the UI must resolve before :meth:`build_plan`.

        Default: nothing to ask.
        """
        return []

    @abstractmethod
    def build_plan(self, filepath: str, answers: dict[str, str]) -> InstallPlan:
        """Return the ordered commands to run.

        ``answers`` is keyed by ``Preflight.id``; a declined ``confirm`` means
        the install was aborted and this is never called.
        """


def which(name: str) -> str | None:
    """``shutil.which`` re-exported so handlers don't each import it."""
    return shutil.which(name)


def exec_step(
    argv: list[str],
    workdir: str,
    *,
    as_root: bool,
    label: str,
) -> Command:
    """A Command that runs *argv* with *workdir* as the working directory.

    Non-root: a plain Command with ``cwd`` set. Root: wrapped as
    ``pkexec sh -c 'cd "$1"; shift; exec "$@"' sh <workdir> <argv...>`` -- the
    wrapper is needed because ``pkexec`` does not preserve the caller's working
    directory, and vendor installers routinely depend on it.
    """
    if not as_root:
        return Command(list(argv), label=label, cwd=workdir)
    return Command(
        ["sh", "-c", 'cd "$1"; shift; exec "$@"', "sh", workdir, *argv],
        label=label,
        use_pkexec=True,
    )

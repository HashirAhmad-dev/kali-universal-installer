"""Plain data structures shared between handlers, the runner, and the UI.

A handler never touches ``QProcess`` directly. It declares:

* ``Preflight`` items  -- questions/warnings the UI must resolve first, and
* an ``InstallPlan``   -- an ordered list of ``Command`` objects.

``ProcessRunner`` is the only thing that turns a ``Command`` into a live
``QProcess``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

PreflightKind = Literal["confirm", "choice", "warning"]


@dataclass
class Command:
    """A single process invocation within an install plan."""

    argv: list[str]
    label: str
    cwd: str | None = None
    use_pkexec: bool = False

    def resolved_argv(self) -> list[str]:
        """The argv actually handed to QProcess, with ``pkexec`` prepended."""
        if self.use_pkexec:
            return ["pkexec", *self.argv]
        return list(self.argv)


@dataclass
class Preflight:
    """A question or warning the UI must resolve before building the plan.

    The answer is passed back to ``PackageHandler.build_plan`` in an ``answers``
    dict keyed by ``id``:

    * ``confirm`` -> ``"yes"`` (there is no entry if the user declined; the
      install is aborted instead)
    * ``warning`` -> ``"ok"``
    * ``choice``  -> the chosen string from ``options``
    """

    id: str
    kind: PreflightKind
    message: str
    options: list[str] = field(default_factory=list)


@dataclass
class InstallPlan:
    """An ordered list of commands plus optional post-processing hints."""

    commands: list[Command]
    # Set by the archive handler: after every command succeeds, the app
    # re-runs detection inside this directory and dispatches a fresh plan.
    rescan_dir: str | None = None
    # Free-text note surfaced in the log on success (e.g. where an AppImage
    # was moved).
    note: str | None = None

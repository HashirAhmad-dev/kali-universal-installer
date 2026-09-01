"""Decide whether an install actually succeeded.

Exit code 0 is necessary but not sufficient: ``apt``/``dpkg`` can finish with
status 0 while printing lines like ``E: Sub-process ... returned an error`` or
``Errors were encountered while processing:``. We surface that as a distinct
``SUCCESS_WITH_WARNINGS`` state rather than a green checkmark.
"""
from __future__ import annotations

import enum
import re


class InstallOutcome(enum.Enum):
    SUCCESS = "success"
    SUCCESS_WITH_WARNINGS = "success_with_warnings"
    FAILED = "failed"
    CANCELLED = "cancelled"


# "0 errors", "no errors found", "errors: 0" -- present but benign.
_BENIGN_ERROR = re.compile(r"\b(0|no)\s+errors?\b|errors?\s*[:=]\s*0", re.IGNORECASE)
_ERROR_WORD = re.compile(r"errors?\b", re.IGNORECASE)


def analyze(
    output: str,
    exit_codes: list[int],
    *,
    cancelled: bool = False,
) -> InstallOutcome:
    if cancelled:
        return InstallOutcome.CANCELLED
    if any(code != 0 for code in exit_codes) or not exit_codes:
        return InstallOutcome.FAILED
    if has_error_signal(output):
        return InstallOutcome.SUCCESS_WITH_WARNINGS
    return InstallOutcome.SUCCESS


def has_error_signal(output: str) -> bool:
    """True if any output line looks like a real error rather than a count."""
    for raw in output.splitlines():
        line = raw.strip()
        if not line:
            continue
        # apt's own error prefix.
        if line.startswith("E: "):
            return True
        if _ERROR_WORD.search(line) and not _BENIGN_ERROR.search(line):
            return True
    return False

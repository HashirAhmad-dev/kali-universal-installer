"""Outcome-scanner tests: exit code 0 is necessary but not sufficient.

Run with:  python -m pytest   (or)   python tests/test_outcome.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from kupi.outcome import InstallOutcome, analyze, has_error_signal  # noqa: E402


def test_clean_success():
    assert analyze("Reading package lists...\ndone", [0]) is InstallOutcome.SUCCESS


def test_error_counts_are_benign():
    for line in ("0 errors, 0 warnings", "no errors found", "errors: 0"):
        assert not has_error_signal(line), line
        assert analyze(line, [0]) is InstallOutcome.SUCCESS


def test_apt_error_prefix_is_a_warning():
    out = "Setting up foo ...\nE: Sub-process /usr/bin/dpkg returned an error code (1)"
    assert analyze(out, [0]) is InstallOutcome.SUCCESS_WITH_WARNINGS


def test_dpkg_errors_encountered_is_a_warning():
    out = "Errors were encountered while processing:\n foo"
    assert analyze(out, [0]) is InstallOutcome.SUCCESS_WITH_WARNINGS


def test_nonzero_exit_is_failure():
    assert analyze("all good", [0, 3]) is InstallOutcome.FAILED
    assert analyze("", []) is InstallOutcome.FAILED


def test_cancelled_wins():
    assert analyze("E: broken", [1], cancelled=True) is InstallOutcome.CANCELLED


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"ok    {t.__name__}")
        except AssertionError as exc:
            failures += 1
            print(f"FAIL  {t.__name__}: {exc}")
    print(f"\n{failures} failure(s)")
    sys.exit(1 if failures else 0)

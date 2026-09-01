"""Extension-routing tests for the detector. No GUI, no PySide6 required.

Run with:  python -m pytest   (or)   python tests/test_detector.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from kupi.detector import PackageType, detect  # noqa: E402


def _make(dir_path: str, name: str) -> str:
    path = os.path.join(dir_path, name)
    with open(path, "wb") as fh:
        fh.write(b"\x00\x00\x00\x00")
    return path


CASES = {
    "app_1.0_amd64.deb": PackageType.DEB,
    "pkg-2.fc39.x86_64.rpm": PackageType.RPM,
    "Cool-App-x86_64.AppImage": PackageType.APPIMAGE,
    "installer.run": PackageType.RUN_BIN,
    "blob.bin": PackageType.RUN_BIN,
    "setup.sh": PackageType.SHELL,
    "src-1.2.tar.gz": PackageType.ARCHIVE,
    "src-1.2.tar.xz": PackageType.ARCHIVE,
    "src-1.2.tar.bz2": PackageType.ARCHIVE,
    "src.tgz": PackageType.ARCHIVE,
    "bundle.zip": PackageType.ARCHIVE,
    "core.snap": PackageType.SNAP,
    "app.flatpak": PackageType.FLATPAK,
    "app.flatpakref": PackageType.FLATPAK,
}


def test_extension_routing(tmp_path):
    for name, expected in CASES.items():
        result = detect(_make(str(tmp_path), name))
        assert result.package_type is expected, (name, result)
        assert result.method == "extension"


def test_unknown_extension(tmp_path):
    result = detect(_make(str(tmp_path), "README.md"))
    assert result.package_type is PackageType.UNKNOWN


def test_case_insensitive(tmp_path):
    assert detect(_make(str(tmp_path), "X.TAR.GZ")).package_type is PackageType.ARCHIVE


if __name__ == "__main__":
    import tempfile

    failures = 0
    with tempfile.TemporaryDirectory() as d:
        for name, expected in CASES.items():
            got = detect(_make(d, name)).package_type
            ok = got is expected
            failures += not ok
            print(f"{'ok  ' if ok else 'FAIL'}  {name:32}  -> {got.value}")
        got = detect(_make(d, "README.md")).package_type
        ok = got is PackageType.UNKNOWN
        failures += not ok
        print(f"{'ok  ' if ok else 'FAIL'}  {'README.md':32}  -> {got.value}")
    print(f"\n{failures} failure(s)")
    sys.exit(1 if failures else 0)

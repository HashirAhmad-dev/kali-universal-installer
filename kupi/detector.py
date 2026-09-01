"""Map a file on disk to a :class:`PackageType`.

Primary signal is the file extension. If that is ambiguous or missing we fall
back to ``file --mime-type``, and finally to ``file -b`` text (which is the only
reliable way to spot an AppImage, whose mime type is just an ELF executable).
"""
from __future__ import annotations

import enum
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class PackageType(enum.Enum):
    DEB = "deb"
    RPM = "rpm"
    APPIMAGE = "appimage"
    RUN_BIN = "run_bin"
    SHELL = "shell"
    ARCHIVE = "archive"
    SNAP = "snap"
    FLATPAK = "flatpak"
    UNKNOWN = "unknown"


# Checked with ``str.endswith`` in order, so multi-part extensions such as
# ``.tar.gz`` must appear before any single-part suffix they contain.
_EXTENSION_MAP: tuple[tuple[str, PackageType], ...] = (
    (".deb", PackageType.DEB),
    (".rpm", PackageType.RPM),
    (".appimage", PackageType.APPIMAGE),
    (".run", PackageType.RUN_BIN),
    (".bin", PackageType.RUN_BIN),
    (".sh", PackageType.SHELL),
    (".tar.gz", PackageType.ARCHIVE),
    (".tar.xz", PackageType.ARCHIVE),
    (".tar.bz2", PackageType.ARCHIVE),
    (".tar.zst", PackageType.ARCHIVE),
    (".tgz", PackageType.ARCHIVE),
    (".txz", PackageType.ARCHIVE),
    (".tbz2", PackageType.ARCHIVE),
    (".zip", PackageType.ARCHIVE),
    (".snap", PackageType.SNAP),
    (".flatpakref", PackageType.FLATPAK),
    (".flatpak", PackageType.FLATPAK),
)

_MIME_MAP: dict[str, PackageType] = {
    "application/vnd.debian.binary-package": PackageType.DEB,
    "application/x-debian-package": PackageType.DEB,
    "application/x-rpm": PackageType.RPM,
    "application/x-redhat-package-manager": PackageType.RPM,
    "application/vnd.appimage": PackageType.APPIMAGE,
    "application/x-iso9660-appimage": PackageType.APPIMAGE,
    "application/gzip": PackageType.ARCHIVE,
    "application/x-gzip": PackageType.ARCHIVE,
    "application/x-xz": PackageType.ARCHIVE,
    "application/x-bzip2": PackageType.ARCHIVE,
    "application/zstd": PackageType.ARCHIVE,
    "application/x-tar": PackageType.ARCHIVE,
    "application/zip": PackageType.ARCHIVE,
    "application/vnd.squashfs": PackageType.SNAP,
    "application/x-shellscript": PackageType.SHELL,
    "text/x-shellscript": PackageType.SHELL,
}


@dataclass
class Detection:
    package_type: PackageType
    method: str  # "extension" | "content" | "none"
    detail: str  # matched extension, mime string, or a short message


def detect(filepath: str) -> Detection:
    name = Path(filepath).name.lower()

    for ext, ptype in _EXTENSION_MAP:
        if name.endswith(ext):
            return Detection(ptype, "extension", ext)

    mime = _mime_type(filepath)
    if mime and mime in _MIME_MAP:
        return Detection(_MIME_MAP[mime], "content", mime)

    description = _file_description(filepath)
    if description and "appimage" in description.lower():
        return Detection(PackageType.APPIMAGE, "content", "AppImage (ELF)")

    if mime:
        return Detection(PackageType.UNKNOWN, "none", mime)
    return Detection(PackageType.UNKNOWN, "none", "type could not be determined")


def _mime_type(filepath: str) -> str | None:
    return _run_file(["--mime-type", "-b", filepath])


def _file_description(filepath: str) -> str | None:
    return _run_file(["-b", filepath])


def _run_file(args: list[str]) -> str | None:
    if not shutil.which("file"):
        return None
    try:
        result = subprocess.run(
            ["file", *args],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (subprocess.SubprocessError, OSError):
        return None
    out = result.stdout.strip()
    return out or None

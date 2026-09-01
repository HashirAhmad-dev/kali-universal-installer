"""Registry mapping :class:`PackageType` to a handler instance.

Every package type has a real handler. Adding a new type: write a
``PackageHandler`` subclass in its own module, import it here, add one line to
``_REGISTRY``.
"""
from __future__ import annotations

from ..detector import PackageType
from .appimage import AppImageHandler
from .archive import ArchiveHandler
from .base import PackageHandler
from .deb import DebHandler
from .flatpak import FlatpakHandler
from .rpm import RpmHandler
from .run_bin import RunBinHandler
from .shell import ShellHandler
from .snap import SnapHandler

_REGISTRY: dict[PackageType, PackageHandler] = {
    PackageType.DEB: DebHandler(),
    PackageType.RPM: RpmHandler(),
    PackageType.APPIMAGE: AppImageHandler(),
    PackageType.RUN_BIN: RunBinHandler(),
    PackageType.SHELL: ShellHandler(),
    PackageType.ARCHIVE: ArchiveHandler(),
    PackageType.SNAP: SnapHandler(),
    PackageType.FLATPAK: FlatpakHandler(),
}


def get_handler(package_type: PackageType) -> PackageHandler | None:
    return _REGISTRY.get(package_type)


__all__ = ["PackageHandler", "get_handler"]

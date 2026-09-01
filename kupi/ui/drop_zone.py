"""A drag-and-drop target that emits the path of a single dropped file."""
from __future__ import annotations

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

_HINT = (
    "Drop a package file here\n"
    ".deb  .rpm  .AppImage  .run  .bin  .sh  .tar.gz/.xz/.bz2  .zip  .snap  .flatpak"
)


class DropZone(QFrame):
    file_dropped = Signal(str)
    # Emitted the instant a valid drag payload enters the zone, so the window
    # can raise itself above the file manager you dragged from.
    drag_entered = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(130)

        layout = QVBoxLayout(self)
        self._label = QLabel(_HINT)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setWordWrap(True)
        layout.addWidget(self._label)

        self._set_active(False)

    def _set_active(self, active: bool) -> None:
        self.setProperty("dragActive", "true" if active else "false")
        # Re-evaluate the stylesheet now that the dynamic property changed.
        self.style().unpolish(self)
        self.style().polish(self)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self._path_from(event) is not None:
            self.drag_entered.emit()
            event.acceptProposedAction()
            self._set_active(True)
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self._set_active(False)

    def dropEvent(self, event: QDropEvent) -> None:
        self._set_active(False)
        path = self._path_from(event)
        if path is None:
            event.ignore()
            return
        event.acceptProposedAction()
        self.file_dropped.emit(path)

    @staticmethod
    def _path_from(event) -> str | None:
        mime = event.mimeData()
        if not mime.hasUrls():
            return None
        for url in mime.urls():
            if url.isLocalFile():
                path = url.toLocalFile()
                if os.path.isfile(path):
                    return path
        return None

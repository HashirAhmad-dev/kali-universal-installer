"""A small coloured pill showing Idle / Running / Success / Failed."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

_STYLES: dict[str, tuple[str, str]] = {
    "idle": ("Idle", "#6b7280"),
    "running": ("Running", "#2563eb"),
    "success": ("Success", "#16a34a"),
    "warnings": ("Success (with warnings)", "#d97706"),
    "failed": ("Failed", "#dc2626"),
    "cancelled": ("Cancelled", "#6b7280"),
    "manual": ("Extracted -- manual", "#0891b2"),
}


class StatusBadge(QLabel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_state("idle")

    def set_state(self, state: str) -> None:
        text, color = _STYLES.get(state, _STYLES["idle"])
        self.setText(text)
        self.setStyleSheet(
            "QLabel {"
            f" background: {color}; color: white;"
            " border-radius: 4px; padding: 4px 12px; font-weight: 600;"
            "}"
        )

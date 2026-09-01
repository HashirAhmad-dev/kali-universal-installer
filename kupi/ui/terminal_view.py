"""Read-only, monospace, auto-scrolling output pane.

Text is appended incrementally as the runner emits it. The view stays pinned to
the bottom *unless* the user has scrolled up to read something, in which case it
leaves the scrollbar alone.
"""
from __future__ import annotations

from PySide6.QtGui import QFontDatabase, QTextCursor
from PySide6.QtWidgets import QPlainTextEdit


class TerminalView(QPlainTextEdit):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        # Cap memory on very chatty installs.
        self.setMaximumBlockCount(20000)

        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        font.setPointSize(10)
        self.setFont(font)

    def append_text(self, text: str) -> None:
        scrollbar = self.verticalScrollBar()
        stick_to_bottom = scrollbar.value() >= scrollbar.maximum() - 4

        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)

        if stick_to_bottom:
            scrollbar.setValue(scrollbar.maximum())

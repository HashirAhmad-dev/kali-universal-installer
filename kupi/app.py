"""The single installer window: drop -> detect -> confirm -> install -> watch."""
from __future__ import annotations

import os
import shutil

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .detector import Detection, PackageType, detect
from .handlers import get_handler
from .model import Preflight
from .outcome import InstallOutcome
from .runner import ProcessRunner
from .ui.drop_zone import DropZone
from .ui.status_badge import StatusBadge
from .ui.terminal_view import TerminalView

_OUTCOME_UI: dict[InstallOutcome, tuple[str, str]] = {
    InstallOutcome.SUCCESS: (
        "success",
        "Installation completed successfully.",
    ),
    InstallOutcome.SUCCESS_WITH_WARNINGS: (
        "warnings",
        "Process exited 0 but the output contains error lines -- the install "
        "may be incomplete. Review the log above.",
    ),
    InstallOutcome.FAILED: (
        "failed",
        "Installation failed. See the log above.",
    ),
    InstallOutcome.CANCELLED: (
        "cancelled",
        "Installation cancelled.",
    ),
}

_STYLESHEET = """
QFrame#dropZone {
    border: 2px dashed #9ca3af;
    border-radius: 8px;
}
QFrame#dropZone[dragActive="true"] {
    border-color: #2563eb;
    background: rgba(37, 99, 235, 0.10);
}
"""


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Kali Universal Package Installer")
        self.resize(840, 640)
        self.setStyleSheet(_STYLESHEET)
        # Default to staying above the file manager -- see the "Keep window on
        # top" checkbox. Set before the first show() so it takes effect cleanly.
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

        self._path: str | None = None
        self._detection: Detection | None = None
        self._handler = None
        self._pending_note: str | None = None
        # Temp dirs created by the archive handler, removed once the whole
        # extract -> dispatch -> install chain concludes.
        self._temp_dirs: list[str] = []

        self._runner = ProcessRunner(self)
        self._runner.output.connect(self._append)
        self._runner.command_started.connect(self._on_command_started)
        self._runner.running_changed.connect(self._on_running_changed)
        self._runner.finished.connect(self._on_finished)
        self._runner.rescan_requested.connect(self._on_rescan_requested)

        self._build_ui()
        self._set_target(None)

    # --------------------------------------------------------------- UI setup
    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        self._drop = DropZone()
        self._drop.file_dropped.connect(self._on_file_dropped)
        self._drop.drag_entered.connect(self._bring_to_front)
        root.addWidget(self._drop)

        self._file_label = QLabel()
        self._type_label = QLabel()
        self._type_label.setWordWrap(True)
        browse = QPushButton("Browse...")
        browse.clicked.connect(self._on_browse)

        meta = QVBoxLayout()
        meta.addWidget(self._file_label)
        meta.addWidget(self._type_label)
        meta_row = QHBoxLayout()
        meta_row.addLayout(meta, 1)
        meta_row.addWidget(browse, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(meta_row)

        self._terminal = TerminalView()
        root.addWidget(self._terminal, 1)

        clear_btn = QPushButton("Clear log")
        clear_btn.clicked.connect(self._terminal.clear)
        copy_btn = QPushButton("Copy log")
        copy_btn.clicked.connect(self._on_copy_log)

        self._on_top = QCheckBox("Keep window on top")
        # Match the flag set in __init__; connect *after* setChecked so the slot
        # (which calls show()) doesn't fire during construction.
        self._on_top.setChecked(True)
        self._on_top.toggled.connect(self._apply_on_top)

        self._status = StatusBadge()

        log_row = QHBoxLayout()
        log_row.addWidget(clear_btn)
        log_row.addWidget(copy_btn)
        log_row.addWidget(self._on_top)
        log_row.addStretch(1)
        log_row.addWidget(self._status)
        root.addLayout(log_row)

        self._install_btn = QPushButton("Install")
        self._install_btn.setDefault(True)
        self._install_btn.clicked.connect(self._on_install)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self._runner.cancel)
        self._cancel_btn.setEnabled(False)

        action_row = QHBoxLayout()
        action_row.addStretch(1)
        action_row.addWidget(self._install_btn)
        action_row.addWidget(self._cancel_btn)
        root.addLayout(action_row)

        self.setCentralWidget(central)

    # ------------------------------------------------------------ window focus
    def _bring_to_front(self) -> None:
        """Raise above the file manager as soon as a drag reaches the zone."""
        self.raise_()
        self.activateWindow()

    def _apply_on_top(self, enabled: bool) -> None:
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, enabled)
        # Changing window flags detaches the native window; show() re-realises it.
        self.show()

    # ------------------------------------------------------------ target state
    def load_file(self, path: str) -> None:
        """Public entry point: preload a file passed on the command line."""
        self._set_target(os.path.abspath(path))

    def _on_file_dropped(self, path: str) -> None:
        self._set_target(path)

    def _on_browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose a package file")
        if path:
            self._set_target(path)

    def _set_target(self, path: str | None) -> None:
        self._path = path

        if not path:
            self._detection = None
            self._handler = None
            self._file_label.setText("File:  (none)")
            self._type_label.setText("Type:  drop or browse to a package to detect it")
            self._install_btn.setEnabled(False)
            return

        self._detection = detect(path)
        self._handler = get_handler(self._detection.package_type)
        self._file_label.setText(f"File:  {os.path.basename(path)}")

        if self._detection.package_type is PackageType.UNKNOWN or self._handler is None:
            self._type_label.setText(
                f"Type:  unrecognised ({self._detection.detail}) -- cannot install"
            )
            self._install_btn.setEnabled(False)
            return

        how = (
            "by extension"
            if self._detection.method == "extension"
            else f"by content: {self._detection.detail}"
        )
        note = "" if self._handler.implemented else "   [NOT YET IMPLEMENTED -- Phase 2]"
        self._type_label.setText(
            f"Type:  {self._handler.describe(path)}   (detected {how}){note}"
        )
        self._install_btn.setEnabled(self._can_install())

    def _can_install(self) -> bool:
        return bool(
            self._path
            and self._handler is not None
            and self._handler.implemented
            and not self._runner.is_running
        )

    # ---------------------------------------------------------------- install
    def _on_install(self) -> None:
        if not self._can_install() or self._handler is None or self._path is None:
            return

        plan = self._prepare_plan(self._handler, self._path)
        if plan is None:
            return

        self._append(
            f"\n########## Installing {os.path.basename(self._path)} "
            f"({len(plan.commands)} step(s)) ##########\n"
        )
        self._pending_note = plan.note
        self._runner.run(plan)

    def _prepare_plan(self, handler, path: str):
        """Run the handler's preflight prompts, then build its plan.

        Returns the ``InstallPlan``, or ``None`` if the user cancelled a prompt
        or plan construction failed (the reason is already shown/logged). Shared
        by the drop-and-Install path and the archive re-dispatch path.
        """
        try:
            prompts = handler.preflight(path)
        except Exception as exc:  # noqa: BLE001 -- surface anything to the user
            QMessageBox.critical(self, "Preflight check failed", str(exc))
            return None

        answers: dict[str, str] = {}
        for prompt in prompts:
            answer = self._ask(prompt)
            if answer is None:
                self._append("\n[aborted at preflight]\n")
                return None
            answers[prompt.id] = answer

        try:
            return handler.build_plan(path, answers)
        except NotImplementedError as exc:
            QMessageBox.information(self, "Not implemented yet", str(exc))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Could not build the install plan", str(exc))
        return None

    def _ask(self, prompt: Preflight) -> str | None:
        if prompt.kind == "warning":
            clicked = QMessageBox.warning(
                self,
                "Warning",
                prompt.message,
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            )
            return "ok" if clicked == QMessageBox.StandardButton.Ok else None

        if prompt.kind == "confirm":
            clicked = QMessageBox.question(self, "Confirm", prompt.message)
            return "yes" if clicked == QMessageBox.StandardButton.Yes else None

        if prompt.kind == "choice" and prompt.options:
            choice, ok = QInputDialog.getItem(
                self, "Choose", prompt.message, prompt.options, 0, False
            )
            return choice if ok else None

        return None

    # ----------------------------------------------------------- runner slots
    def _on_command_started(self, label: str, index: int, total: int) -> None:
        if total > 1:
            self._status.set_state("running")
            self.setWindowTitle(
                f"Kali Universal Package Installer  --  step {index}/{total}"
            )

    def _on_running_changed(self, running: bool) -> None:
        self._install_btn.setEnabled(not running and self._can_install())
        self._cancel_btn.setEnabled(running)
        self._drop.setEnabled(not running)
        if running:
            self._status.set_state("running")

    def _on_finished(self, outcome: InstallOutcome) -> None:
        state, message = _OUTCOME_UI.get(outcome, ("idle", ""))
        note = self._pending_note
        if note and outcome in (
            InstallOutcome.SUCCESS,
            InstallOutcome.SUCCESS_WITH_WARNINGS,
        ):
            self._append(f"\n[note] {note}\n")
        self._conclude(state, message)

    def _conclude(self, state: str, message: str) -> None:
        """End of the whole flow: reset the UI and clean up temp dirs."""
        self._pending_note = None
        self._status.set_state(state)
        self.setWindowTitle("Kali Universal Package Installer")
        if message:
            self._append(f"\n[{message}]\n")
        self._cleanup_temp()
        self._install_btn.setEnabled(self._can_install())
        self._cancel_btn.setEnabled(False)
        self._drop.setEnabled(True)

    # -------------------------------------------------- archive rescan/dispatch
    def _on_rescan_requested(self, extract_dir: str) -> None:
        self._temp_dirs.append(extract_dir)

        found = _scan_extracted(extract_dir)
        if found is None:
            self._append(
                "\n[no install.sh / setup.sh / .deb found in the archive]\n"
            )
            dest = QFileDialog.getExistingDirectory(
                self, "Keep the extracted files where?"
            )
            if dest:
                try:
                    landed = _move_tree(extract_dir, dest)
                    self._conclude(
                        "manual",
                        f"No installer in the archive. Files are in {landed} -- "
                        "install manually.",
                    )
                    return
                except OSError as exc:
                    self._append(f"[could not move files: {exc}]\n")
            self._conclude(
                "manual",
                f"No installer in the archive. Extracted files are in {extract_dir}.",
            )
            return

        package_type, target = found
        handler = get_handler(package_type)
        assert handler is not None
        rel = os.path.relpath(target, extract_dir)
        self._append(f"\n[archive contains {rel} -- running it]\n")

        # Same preflight prompts as a direct drop (e.g. the .sh root/user choice).
        plan = self._prepare_plan(handler, target)
        if plan is None:
            self._conclude("failed", f"No plan built for {rel}.")
            return

        self._pending_note = plan.note
        # Defer: we are currently inside the runner's completion callstack.
        QTimer.singleShot(0, lambda: self._runner.run(plan))

    def _cleanup_temp(self) -> None:
        for path in self._temp_dirs:
            shutil.rmtree(path, ignore_errors=True)
        self._temp_dirs.clear()

    # ---------------------------------------------------------------- helpers
    def _append(self, text: str) -> None:
        self._terminal.append_text(text)

    def _on_copy_log(self) -> None:
        QApplication.clipboard().setText(self._terminal.toPlainText())

    def closeEvent(self, event) -> None:  # noqa: N802 -- Qt override
        if self._runner.is_running:
            confirm = QMessageBox.question(
                self,
                "Install in progress",
                "An installation is still running. Quit anyway?",
            )
            if confirm != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._runner.cancel()
        self._cleanup_temp()
        event.accept()


def _scan_extracted(root: str) -> tuple[PackageType, str] | None:
    """Look for an installer inside an extracted archive.

    Priority: ``install.sh`` > ``setup.sh`` > first ``.deb``; shallower paths
    win ties. Returns ``(PackageType, absolute path)`` or ``None``.
    """
    scripts: list[tuple[int, int, str]] = []
    debs: list[tuple[int, str]] = []

    for dirpath, dirnames, filenames in os.walk(root):
        depth = dirpath[len(root):].count(os.sep)
        if depth > 4:
            dirnames[:] = []
            continue
        for name in filenames:
            lower = name.lower()
            full = os.path.join(dirpath, name)
            if lower in ("install.sh", "setup.sh"):
                scripts.append((depth, 0 if lower == "install.sh" else 1, full))
            elif lower.endswith(".deb"):
                debs.append((depth, full))

    if scripts:
        scripts.sort()
        return PackageType.SHELL, scripts[0][2]
    if debs:
        debs.sort()
        return PackageType.DEB, debs[0][1]
    return None


def _move_tree(src: str, dst: str) -> str:
    """Move everything under *src* into *dst*; return where it landed."""
    entries = os.listdir(src)
    if len(entries) == 1 and os.path.isdir(os.path.join(src, entries[0])):
        landed = os.path.join(dst, entries[0])
        shutil.move(os.path.join(src, entries[0]), landed)
        return landed
    for entry in entries:
        shutil.move(os.path.join(src, entry), os.path.join(dst, entry))
    return dst

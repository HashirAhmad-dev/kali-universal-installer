"""Execute an :class:`InstallPlan` one command at a time with live output.

Design notes
------------
* One ``QProcess`` per command, created fresh, ``MergedChannels`` so stdout and
  stderr interleave in the true order.
* Output is emitted on every ``readyReadStandardOutput`` -- never buffered and
  dumped at the end. A copy is also accumulated so :mod:`kupi.outcome` can scan
  it once the plan finishes.
* The plan stops at the first non-zero exit code.
* Cancel: ``QProcess.kill()`` only signals the ``pkexec`` wrapper, not the
  privileged child it spawned. For the MVP we kill what we can and log a note
  that a root process may still be finishing.
* Stale signals from an already-replaced process are ignored via a ``sender()``
  identity check.
"""
from __future__ import annotations

from PySide6.QtCore import QObject, QProcess, Signal

from .model import Command, InstallPlan
from .outcome import InstallOutcome, analyze


class ProcessRunner(QObject):
    # A chunk of merged stdout/stderr text, ready to append to the pane.
    output = Signal(str)
    # (label, step_index, step_total) -- 1-based index.
    command_started = Signal(str, int, int)
    # Emitted with True when a plan starts, False when it ends.
    running_changed = Signal(bool)
    # Emitted once per plan with an InstallOutcome...
    finished = Signal(object)
    # ...unless the plan carried a rescan_dir and succeeded, in which case this
    # fires instead and app.py continues the flow (scan + dispatch a new plan).
    rescan_requested = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._proc: QProcess | None = None
        self._queue: list[Command] = []
        self._index = 0
        self._total = 0
        self._exit_codes: list[int] = []
        self._chunks: list[str] = []
        self._cancelled = False
        self._rescan_dir: str | None = None

    @property
    def is_running(self) -> bool:
        return self._proc is not None or bool(self._queue)

    # ------------------------------------------------------------------ API
    def run(self, plan: InstallPlan) -> None:
        if self.is_running:
            raise RuntimeError("a plan is already running")
        self._queue = list(plan.commands)
        self._index = 0
        self._total = len(self._queue)
        self._exit_codes = []
        self._chunks = []
        self._cancelled = False
        self._rescan_dir = plan.rescan_dir
        self.running_changed.emit(True)
        self._start_next()

    def cancel(self) -> None:
        if not self.is_running:
            return
        self._cancelled = True
        self._queue.clear()
        if self._proc is not None:
            self.output.emit("\n[cancel requested -- killing current step]\n")
            self._proc.kill()  # -> _on_proc_finished -> _complete
        else:
            self._complete()

    # -------------------------------------------------------------- internals
    def _start_next(self) -> None:
        if not self._queue:
            self._complete()
            return

        command = self._queue.pop(0)
        self._index += 1
        argv = command.resolved_argv()

        self.command_started.emit(command.label, self._index, self._total)
        self.output.emit(
            f"\n=== Step {self._index} of {self._total}: {command.label} ===\n"
            f"$ {' '.join(argv)}\n"
        )

        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        if command.cwd:
            proc.setWorkingDirectory(command.cwd)
        proc.readyReadStandardOutput.connect(self._on_ready_read)
        proc.finished.connect(self._on_proc_finished)
        proc.errorOccurred.connect(self._on_proc_error)
        self._proc = proc
        proc.start(argv[0], argv[1:])

    def _on_ready_read(self) -> None:
        proc = self.sender()
        if proc is not self._proc or proc is None:
            return
        self._drain(proc)

    def _drain(self, proc: QProcess) -> None:
        data = bytes(proc.readAllStandardOutput()).decode("utf-8", "replace")
        if data:
            self._chunks.append(data)
            self.output.emit(data)

    def _on_proc_error(self, error: QProcess.ProcessError) -> None:
        if self.sender() is not self._proc:
            return
        if error == QProcess.ProcessError.FailedToStart:
            program = self._proc.program() if self._proc else "?"
            self.output.emit(
                f"\n[failed to start '{program}' -- not found or not executable]\n"
            )
            self._finish_current(127)

    def _on_proc_finished(
        self,
        exit_code: int,
        exit_status: QProcess.ExitStatus,
    ) -> None:
        if self.sender() is not self._proc:
            return
        self._drain(self._proc)
        if (
            exit_status == QProcess.ExitStatus.CrashExit
            and not self._cancelled
        ):
            self.output.emit("\n[process crashed]\n")
            self._finish_current(exit_code or 139)
        else:
            self._finish_current(exit_code)

    def _finish_current(self, code: int) -> None:
        if self._proc is None:
            return
        self._proc.deleteLater()
        self._proc = None
        self._exit_codes.append(code)

        if self._cancelled:
            self._complete()
            return
        if code != 0:
            self.output.emit(
                f"\n[step failed with exit code {code} -- stopping the plan]\n"
            )
            self._queue.clear()
            self._complete()
            return
        self._start_next()

    def _complete(self) -> None:
        output = "".join(self._chunks)
        outcome = analyze(output, self._exit_codes, cancelled=self._cancelled)
        rescan_dir = self._rescan_dir
        do_rescan = (
            rescan_dir is not None
            and not self._cancelled
            and outcome
            in (InstallOutcome.SUCCESS, InstallOutcome.SUCCESS_WITH_WARNINGS)
        )

        if self._cancelled:
            self.output.emit(
                "\n[cancelled -- a privileged child started via pkexec may still "
                "be finishing in the background]\n"
            )
        self._queue.clear()
        self._rescan_dir = None
        self.running_changed.emit(False)

        # Keep this the last statement: app.py may synchronously start the next
        # plan from the rescan_requested handler.
        if do_rescan:
            self.output.emit(
                "\n[extraction complete -- scanning the archive for an installer]\n"
            )
            self.rescan_requested.emit(rescan_dir)
        else:
            self.finished.emit(outcome)

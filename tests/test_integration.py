"""End-to-end tests that drive the real widgets and a real QProcess, offscreen.

Covers the execution engine (live streaming, stop-on-failure, cancel), the
archive extract -> scan -> dispatch chain, and window behaviours.

Run with:  python -m pytest   (or)   python tests/test_integration.py
Requires PySide6; forces the offscreen Qt platform.
"""
from __future__ import annotations

import os
import sys
import tarfile
import tempfile
import textwrap
import zipfile
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtCore import Qt, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox  # noqa: E402

from kupi.app import MainWindow  # noqa: E402
from kupi.detector import PackageType, detect  # noqa: E402
from kupi.model import Command, InstallPlan  # noqa: E402
from kupi.outcome import InstallOutcome  # noqa: E402
from kupi.runner import ProcessRunner  # noqa: E402

_app = QApplication.instance() or QApplication([])


# --------------------------------------------------------------------- helpers
def _run(runner: ProcessRunner, plan: InstallPlan, timeout_ms: int = 15000) -> dict:
    """Run a plan to completion (or rescan), pumping the event loop."""
    result: dict = {}
    buf: list[str] = []
    runner.output.connect(buf.append)
    runner.finished.connect(lambda o: (result.update(outcome=o), _app.quit()))
    runner.rescan_requested.connect(lambda d: (result.update(rescan=d), _app.quit()))
    QTimer.singleShot(0, lambda: runner.run(plan))
    guard = QTimer()
    guard.setSingleShot(True)
    guard.timeout.connect(_app.quit)
    guard.start(timeout_ms)
    _app.exec()
    result["text"] = "".join(buf)
    for sig in (runner.output, runner.finished, runner.rescan_requested):
        try:
            sig.disconnect()
        except (TypeError, RuntimeError):
            pass
    return result


def _drive(window: MainWindow, timeout_ms: int = 15000) -> dict:
    """Click Install and run the whole flow; capture the _conclude() call."""
    result: dict = {}
    original = window._conclude

    def spy(state: str, message: str) -> None:
        original(state, message)
        result.update(state=state, message=message)
        _app.quit()

    window._conclude = spy  # type: ignore[method-assign]
    QTimer.singleShot(0, window._on_install)
    guard = QTimer()
    guard.setSingleShot(True)
    guard.timeout.connect(_app.quit)
    guard.start(timeout_ms)
    _app.exec()
    result["text"] = window._terminal.toPlainText()
    return result


# ------------------------------------------------------------------ the engine
def test_runner_streams_and_labels_steps():
    res = _run(ProcessRunner(), InstallPlan(commands=[
        Command(["sh", "-c", "echo one; sleep 0.15; echo two"], "a"),
        Command(["sh", "-c", "echo err >&2; echo three"], "b"),
    ]))
    assert res["outcome"] is InstallOutcome.SUCCESS
    assert "one" in res["text"] and "three" in res["text"] and "err" in res["text"]
    assert "Step 1 of 2" in res["text"] and "Step 2 of 2" in res["text"]


def test_runner_stops_on_first_failure():
    res = _run(ProcessRunner(), InstallPlan(commands=[
        Command(["sh", "-c", "echo boom; exit 4"], "boom"),
        Command(["sh", "-c", "echo SHOULD_NOT_RUN"], "never"),
    ]))
    assert res["outcome"] is InstallOutcome.FAILED
    assert "SHOULD_NOT_RUN" not in res["text"]
    assert "exit code 4" in res["text"]


def test_runner_cancel():
    runner = ProcessRunner()
    res: dict = {}
    buf: list[str] = []
    runner.output.connect(buf.append)
    runner.finished.connect(lambda o: (res.update(outcome=o), _app.quit()))
    QTimer.singleShot(0, lambda: runner.run(InstallPlan(commands=[
        Command(["sh", "-c", "echo go; sleep 30"], "long")])))
    QTimer.singleShot(400, runner.cancel)
    QTimer.singleShot(8000, _app.quit)
    _app.exec()
    assert res["outcome"] is InstallOutcome.CANCELLED
    assert "background" in "".join(buf)


# ---------------------------------------------------------- archive dispatch
def _tar(dirpath: str, arcname: str, dest: str) -> str:
    with tarfile.open(dest, "w:gz") as t:
        t.add(dirpath, arcname=arcname)
    return dest


def test_archive_dispatches_nested_install_script(tmp_path=None):
    work = tmp_path or tempfile.mkdtemp()
    pkg = os.path.join(work, "vendor-1.0")
    os.makedirs(pkg, exist_ok=True)
    open(os.path.join(pkg, "payload.dat"), "w").write("d")
    open(os.path.join(pkg, "install.sh"), "w").write(textwrap.dedent("""\
        #!/bin/sh
        echo "in $(pwd)"
        test -f payload.dat && echo payload-ok
        echo done
    """))
    archive = _tar(pkg, "vendor-1.0", os.path.join(work, "vendor-1.0.tar.gz"))

    win = MainWindow()
    win.load_file(archive)
    assert "scanned for" in win._type_label.text()
    with patch.object(QInputDialog, "getItem", return_value=("Normal user", True)):
        res = _drive(win)
    assert res["state"] == "success"
    assert "archive contains" in res["text"] and "payload-ok" in res["text"]
    assert win._temp_dirs == []


def test_archive_dispatches_bundled_deb(tmp_path=None):
    work = tmp_path or tempfile.mkdtemp()
    pkg = os.path.join(work, "hasdeb")
    os.makedirs(pkg, exist_ok=True)
    open(os.path.join(pkg, "thing_1_amd64.deb"), "wb").write(b"!<arch>\n")
    archive = _tar(pkg, "hasdeb", os.path.join(work, "hasdeb.tar.gz"))

    win = MainWindow()
    win.load_file(archive)
    captured: dict = {}
    real = win._runner.run
    calls = {"n": 0}

    def spy(plan):
        calls["n"] += 1
        if calls["n"] == 1:
            real(plan)
        else:
            captured["plan"] = plan
            _app.quit()

    win._runner.run = spy  # type: ignore[method-assign]
    QTimer.singleShot(0, win._on_install)
    QTimer.singleShot(12000, _app.quit)
    _app.exec()
    argv = captured["plan"].commands[0].resolved_argv()
    assert argv[:4] == ["pkexec", "apt", "install", "-y"]
    assert argv[4].endswith("thing_1_amd64.deb")


def test_archive_no_installer_moves_to_chosen_folder(tmp_path=None):
    work = tmp_path or tempfile.mkdtemp()
    src = os.path.join(work, "plain")
    os.makedirs(src, exist_ok=True)
    open(os.path.join(src, "a.txt"), "w").write("a")
    archive = os.path.join(work, "plain.zip")
    with zipfile.ZipFile(archive, "w") as z:
        z.write(os.path.join(src, "a.txt"), "plain/a.txt")
    dest = os.path.join(work, "chosen")
    os.makedirs(dest, exist_ok=True)

    win = MainWindow()
    win.load_file(archive)
    with patch("kupi.app.QFileDialog.getExistingDirectory", return_value=dest):
        res = _drive(win)
    assert res["state"] == "manual"
    assert os.path.isfile(os.path.join(dest, "plain", "a.txt"))
    assert win._temp_dirs == []


# ------------------------------------------------------------- run/bin gate
def test_run_installer_aborts_when_warning_declined(tmp_path=None):
    work = tmp_path or tempfile.mkdtemp()
    marker = os.path.join(work, "SHOULD_NOT_EXIST")
    binf = os.path.join(work, "danger.bin")
    open(binf, "w").write(f'#!/bin/sh\ntouch "{marker}"\n')

    win = MainWindow()
    win.load_file(binf)
    with patch.object(QMessageBox, "warning",
                      return_value=QMessageBox.StandardButton.Cancel):
        win._on_install()
    _app.processEvents()
    assert not os.path.exists(marker)
    assert "aborted at preflight" in win._terminal.toPlainText()


# ---------------------------------------------------------- window behaviour
def test_keep_on_top_toggles_both_ways():
    win = MainWindow()
    win.show()
    flag = Qt.WindowType.WindowStaysOnTopHint
    assert bool(win.windowFlags() & flag)
    win._on_top.setChecked(False)
    assert not bool(win.windowFlags() & flag)
    win._on_top.setChecked(True)
    assert bool(win.windowFlags() & flag)


def test_load_file_enables_and_disables_install():
    win = MainWindow()
    d = tempfile.mkdtemp()
    ok = os.path.join(d, "x.deb")
    open(ok, "wb").write(b"\0")
    win.load_file(ok)
    assert win._install_btn.isEnabled()
    unknown = os.path.join(d, "x.unknownext")
    open(unknown, "wb").write(b"\0")
    win.load_file(unknown)
    assert not win._install_btn.isEnabled()


def test_detection_smoke():
    d = tempfile.mkdtemp()
    for name, exp in {
        "a.deb": PackageType.DEB, "b.rpm": PackageType.RPM,
        "c.AppImage": PackageType.APPIMAGE, "d.run": PackageType.RUN_BIN,
        "e.sh": PackageType.SHELL, "f.tar.xz": PackageType.ARCHIVE,
        "g.zip": PackageType.ARCHIVE, "h.snap": PackageType.SNAP,
        "i.flatpakref": PackageType.FLATPAK, "j.txt": PackageType.UNKNOWN,
    }.items():
        p = os.path.join(d, name)
        open(p, "wb").write(b"\0")
        assert detect(p).package_type is exp, name


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"ok    {t.__name__}")
        except AssertionError as exc:
            failures += 1
            print(f"FAIL  {t.__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"ERROR {t.__name__}: {exc!r}")
    print(f"\n{failures} failure(s)")
    sys.exit(1 if failures else 0)

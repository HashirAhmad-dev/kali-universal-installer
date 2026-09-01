"""Plan-shape tests for implemented handlers. No GUI, no PySide6 required.

Run with:  python -m pytest   (or)   python tests/test_handlers.py
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from kupi.detector import PackageType  # noqa: E402
from kupi.handlers import get_handler  # noqa: E402
from kupi.handlers.base import which  # noqa: E402


def _make(dir_path: str, name: str, body: bytes = b"\x00") -> str:
    path = os.path.join(dir_path, name)
    with open(path, "wb") as fh:
        fh.write(body)
    return path


def test_deb_plan(tmp_path):
    path = _make(str(tmp_path), "app_1.0_amd64.deb")
    plan = get_handler(PackageType.DEB).build_plan(path, {})
    assert len(plan.commands) == 1
    argv = plan.commands[0].resolved_argv()
    assert argv[:4] == ["pkexec", "apt", "install", "-y"]
    assert os.path.isabs(argv[4]) and argv[4].endswith(".deb")


def test_shell_plan_user(tmp_path):
    path = _make(str(tmp_path), "install.sh", b"#!/bin/sh\n")
    handler = get_handler(PackageType.SHELL)
    assert handler.implemented
    assert [p.id for p in handler.preflight(path)] == ["privilege"]
    plan = handler.build_plan(path, {"privilege": "Normal user"})
    assert [c.argv[0] for c in plan.commands] == ["chmod", "bash"]
    assert plan.commands[1].cwd == str(tmp_path)
    assert not any(c.use_pkexec for c in plan.commands)


def test_shell_plan_root(tmp_path):
    path = _make(str(tmp_path), "install.sh", b"#!/bin/sh\n")
    plan = get_handler(PackageType.SHELL).build_plan(path, {"privilege": "Root (pkexec)"})
    run = plan.commands[1]
    assert run.use_pkexec
    argv = run.resolved_argv()
    assert argv[:2] == ["pkexec", "sh"]
    assert 'cd "$1"' in argv[3] and 'exec "$@"' in argv[3]
    assert str(tmp_path) in argv and "bash" in argv and path in argv


def test_run_bin_plan(tmp_path):
    path = _make(str(tmp_path), "vendor-sdk.run")
    handler = get_handler(PackageType.RUN_BIN)
    assert handler.implemented
    kinds = [(p.id, p.kind) for p in handler.preflight(path)]
    assert kinds == [("ack", "warning"), ("privilege", "choice")]

    user_plan = handler.build_plan(path, {"ack": "ok", "privilege": "Normal user"})
    assert [c.argv[0] for c in user_plan.commands] == ["chmod", path]
    assert user_plan.commands[1].cwd == str(tmp_path)
    assert not any(c.use_pkexec for c in user_plan.commands)

    root_plan = handler.build_plan(path, {"ack": "ok", "privilege": "Root (pkexec)"})
    run = root_plan.commands[1]
    assert run.use_pkexec and run.resolved_argv()[0] == "pkexec"
    assert str(tmp_path) in run.argv and path in run.argv


def test_appimage_run_plan(tmp_path):
    path = _make(str(tmp_path), "Cool-x86_64.AppImage")
    handler = get_handler(PackageType.APPIMAGE)
    assert handler.implemented
    assert [p.id for p in handler.preflight(path)] == ["mode"]
    plan = handler.build_plan(path, {"mode": "Run once"})
    assert plan.commands[0].argv == ["chmod", "+x", path]
    run = plan.commands[1]
    assert path in run.argv and "--appimage-extract-and-run" in run.argv[2]
    assert run.cwd == str(tmp_path)
    assert not any(c.use_pkexec for c in plan.commands)


def test_appimage_install_plan(tmp_path):
    path = _make(str(tmp_path), "Cool-1.2-x86_64.AppImage")
    plan = get_handler(PackageType.APPIMAGE).build_plan(path, {"mode": "Install to ~/Applications"})
    verbs = [c.argv[0] for c in plan.commands]
    assert verbs == ["mkdir", "mv", "chmod", "sh"]
    apps = os.path.expanduser("~/Applications")
    assert plan.commands[1].argv[-1] == os.path.join(apps, "Cool-1.2-x86_64.AppImage")
    desktop_cmd = plan.commands[3].argv
    assert desktop_cmd[-1].endswith("kupi-cool-1-2-x86-64.desktop")
    assert "[Desktop Entry]" in desktop_cmd[-2] and "X-KUPI-Managed=true" in desktop_cmd[-2]


def test_archive_plan_tar(tmp_path):
    path = _make(str(tmp_path), "src-1.2.tar.xz")
    handler = get_handler(PackageType.ARCHIVE)
    assert handler.implemented
    plan = handler.build_plan(path, {})
    assert len(plan.commands) == 1
    argv = plan.commands[0].argv
    assert argv[0] == "tar" and "-C" in argv
    assert plan.rescan_dir and os.path.isdir(plan.rescan_dir)
    os.rmdir(plan.rescan_dir)


def test_archive_plan_zip(tmp_path):
    path = _make(str(tmp_path), "bundle.zip")
    plan = get_handler(PackageType.ARCHIVE).build_plan(path, {})
    argv = plan.commands[0].argv
    assert argv[0] in ("unzip", "python3")
    assert plan.rescan_dir
    os.rmdir(plan.rescan_dir)


def _bootstrap_answers(handler, path):
    """Answer every preflight 'yes'/first-option so build_plan can run."""
    answers = {}
    for p in handler.preflight(path):
        answers[p.id] = "yes" if p.kind != "choice" else p.options[0]
    return answers


def test_rpm_plan(tmp_path):
    path = _make(str(tmp_path), "pkg-2.fc39.x86_64.rpm")
    handler = get_handler(PackageType.RPM)
    assert handler.implemented
    plan = handler.build_plan(path, _bootstrap_answers(handler, path))
    last = plan.commands[-1]
    assert last.use_pkexec and "alien" in last.resolved_argv()
    assert path in last.argv
    if which("alien") is None:
        assert handler.preflight(path)[0].id == "install_alien"
        assert plan.commands[0].resolved_argv()[:5] == ["pkexec", "apt", "install", "-y", "alien"]
    else:
        assert handler.preflight(path) == []


def test_snap_plan(tmp_path):
    path = _make(str(tmp_path), "core.snap")
    handler = get_handler(PackageType.SNAP)
    plan = handler.build_plan(path, _bootstrap_answers(handler, path))
    last = plan.commands[-1].resolved_argv()
    assert last[:4] == ["pkexec", "snap", "install", "--dangerous"]
    assert last[-1] == path
    if which("snap") is None:
        assert plan.commands[0].resolved_argv()[:5] == ["pkexec", "apt", "install", "-y", "snapd"]


def test_flatpak_plan(tmp_path):
    path = _make(str(tmp_path), "app.flatpakref")
    handler = get_handler(PackageType.FLATPAK)
    plan = handler.build_plan(path, _bootstrap_answers(handler, path))
    last = plan.commands[-1]
    assert last.argv[:4] == ["flatpak", "install", "--user", "-y"]
    assert not last.use_pkexec  # per-user install needs no root
    if which("flatpak") is None:
        assert plan.commands[0].resolved_argv()[:5] == ["pkexec", "apt", "install", "-y", "flatpak"]


def test_every_type_has_a_handler():
    for ptype in PackageType:
        if ptype is PackageType.UNKNOWN:
            continue
        handler = get_handler(ptype)
        assert handler is not None and handler.implemented, ptype


if __name__ == "__main__":
    failures = 0
    per_dir = (
        test_deb_plan,
        test_shell_plan_user,
        test_shell_plan_root,
        test_run_bin_plan,
        test_archive_plan_tar,
        test_archive_plan_zip,
        test_appimage_run_plan,
        test_appimage_install_plan,
        test_rpm_plan,
        test_snap_plan,
        test_flatpak_plan,
    )
    with tempfile.TemporaryDirectory() as d:
        for fn in per_dir:
            try:
                fn(d)  # type: ignore[arg-type]
                print(f"ok    {fn.__name__}")
            except AssertionError as exc:
                failures += 1
                print(f"FAIL  {fn.__name__}: {exc}")
    try:
        test_every_type_has_a_handler()
        print("ok    test_every_type_has_a_handler")
    except AssertionError as exc:
        failures += 1
        print(f"FAIL  test_every_type_has_a_handler: {exc}")
    print(f"\n{failures} failure(s)")
    sys.exit(1 if failures else 0)

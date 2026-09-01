# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] — 2026-09-01

Initial release.

### Added

- Single-window PySide6 app: drag-and-drop zone, detected-type preview, explicit
  **Install** button, live auto-scrolling output pane, clear/copy log, **Cancel**,
  and an Idle / Running / Success / Success-with-warnings / Failed / Manual status
  pill.
- `ProcessRunner`: one `QProcess` per command, merged stdout/stderr, output
  streamed live (never buffered), stop-on-first-failure, cancel.
- Outcome analysis on **both** exit code and error-line scan — `apt`/`dpkg`
  exiting 0 while printing `E:` / `Errors were encountered` is reported as
  *Success (with warnings)*.
- Package handlers, one per format:
  - `.deb` — `pkexec apt install -y`
  - `.rpm` — offer to install `alien`, then `pkexec alien --install`
  - `.AppImage` — run in place (with `--appimage-extract-and-run` fallback) or
    install to `~/Applications` with a generated `.desktop` launcher
  - `.run` / `.bin` — risk prompt + user/root choice, then execute
  - `.sh` — `bash` in the script's directory, user/root choice
  - `.tar.*` / `.tgz` / `.zip` — extract, scan for `install.sh`/`setup.sh` or a
    bundled `.deb` and re-dispatch, else move to a chosen folder
  - `.snap` — offer to install `snapd`, then `pkexec snap install --dangerous`
  - `.flatpak` / `.flatpakref` — offer to install `flatpak`, then
    `flatpak install --user -y`
- Privilege escalation via `pkexec`; root steps wrapped to preserve the working
  directory.
- Window stays above the file manager (toggle) and raises itself when a drag
  enters the drop zone.
- Launch with a file argument / "Open With" support; `python3 -m kupi` entry point.
- Debian packaging (`build-deb.sh` → lintian-clean `kupi_*_all.deb`), `.desktop`
  entry, icon, man page.
- Test suites: `test_detector`, `test_handlers`, `test_outcome`, `test_integration`.

[Unreleased]: https://github.com/HashirAhmad-dev/kali-universal-installer/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/HashirAhmad-dev/kali-universal-installer/releases/tag/v1.0.0

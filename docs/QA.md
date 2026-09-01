# KUPI — QA Report

Date: 2026-09-01 · Version: 1.0.0 · Platform: Kali Linux (rolling), Python 3.14, PySide6 6.11

## Summary

| Area | Result |
|---|---|
| Automated unit tests (`test_detector.py`, `test_handlers.py`) | **PASS** — 0 failures |
| Headless integration sweep (`tests/test_integration.py`) | **PASS** — 45/45 |
| `.deb` package build + `lintian` | **PASS** — lintian clean (0 E, 0 W) |
| Installed-layout launch (`python3 -m kupi`) | **PASS** |
| Real GUI install of a `.deb` (winboat) | **PASS** (user-verified, screenshot) |
| Real archive → `install.sh` (root) install (XDM `.tar.xz`) | **PASS** (user-verified, screenshot) |
| Real privileged/interactive installs of `.rpm` / `.snap` / `.flatpak` | **NOT RUN** — needs those tools + real packages; see below |

## 1. Detection (15 checks — PASS)

Extension routing for every supported type (`.deb .rpm .AppImage .run .bin .sh
.tar.gz .tar.xz .tar.bz2 .tgz .zip .snap .flatpak .flatpakref`), unknown → `UNKNOWN`,
and `file --mime-type` fallback for an extensionless shell script.

## 2. Outcome scanner (7 checks — PASS)

- clean output + exit 0 → `SUCCESS`
- `0 errors` / `no errors found` → still `SUCCESS` (no false positive)
- `E: …` / `Errors were encountered while processing:` at exit 0 → `SUCCESS_WITH_WARNINGS`
- any non-zero exit → `FAILED`
- cancelled → `CANCELLED`

## 3. Handlers (8 checks — PASS)

Every registered handler returns a non-empty `describe()` and a valid
`InstallPlan` from `build_plan()` after its preflight answers are supplied.
Plan-shape assertions per handler:

| Handler | Verified |
|---|---|
| deb | `pkexec apt install -y <abs .deb>` |
| rpm | `pkexec apt install -y alien` (if missing) → root `alien --install <abs .rpm>` |
| appimage | run: `chmod +x` → `sh -c '"$1" \|\| exec "$1" --appimage-extract-and-run'`; install: `mkdir` → `mv` → `chmod +x` → write `~/.local/share/applications/kupi-<slug>.desktop` |
| run_bin | preflight `[ack:warning, privilege:choice]`; `chmod +x` → exec (user) or pkexec-wrapped (root) |
| shell | preflight `[privilege:choice]`; `chmod +x` → `bash` (user, cwd=folder) or `pkexec sh -c 'cd…;exec bash'` (root) |
| archive | single `tar -xvf`/`unzip -o` to `/tmp/kupi-extract-*`, `rescan_dir` set |
| snap | `pkexec apt install -y snapd` (if missing) → `pkexec snap install --dangerous <abs .snap>` |
| flatpak | `pkexec apt install -y flatpak` (if missing) → `flatpak install --user -y <abs>` (no root) |

## 4. Runner (7 checks — PASS)

- Two-step plan: output streams incrementally (not buffered), stdout+stderr
  interleave, steps labelled `Step 1 of 2` / `Step 2 of 2`, → `SUCCESS`.
- First non-zero exit stops the plan (step 2 never runs), `exit code N` logged, → `FAILED`.
- `cancel()` mid-run → process killed, `CANCELLED`, background-pkexec caveat logged.

## 5. Archive rescan → dispatch chain (4 checks — PASS)

- Nested `install.sh` found → shell handler dispatched (its privilege preflight
  runs) → script executes with cwd = its own folder → temp dir cleaned on conclude.
- Bundled `.deb` found → `pkexec apt install -y <extracted path>` dispatched.
- No installer → prompts for a folder, moves the tree there, badge → **Manual**.

## 6. Window behaviour (4 checks — PASS)

- "Keep window on top" defaults **on**, toggles the `WindowStaysOnTopHint` flag
  both directions without losing the window.
- `drag_entered` → `raise_()` + `activateWindow()` (raises above the file manager).
- `load_file()` preloads and enables Install; unknown type disables it.

## 7. Packaging (PASS)

- `./build-deb.sh` → `dist/kupi_1.0.0_all.deb` (~21 KB, `Architecture: all`).
- `lintian`: **clean** — no errors, no warnings (one `I:` md5sums note resolved;
  one `P:` pedantic path-segment note is cosmetic).
- Layout: code at `/usr/lib/python3/dist-packages/kupi/`, launcher `/usr/bin/kupi`
  (`exec python3 -m kupi "$@"`), `kupi.desktop`, scalable icon, man page,
  changelog, copyright.
- `desktop-file-validate` OK; man page renders; `python3 -m kupi` launches from
  the extracted install tree.
- Depends resolve to real Kali repo packages (`python3-pyside6.qtwidgets` 6.10.3-3,
  `pkexec`, `file`).

## Not covered by automation (manual checklist)

These need a real desktop session, the external tools, and real packages — run
them once after `sudo apt install ./dist/kupi_1.0.0_all.deb`:

- [ ] `.rpm`: drop one with `alien` absent → confirm the install-alien prompt →
      two polkit prompts → converted & installed.
- [ ] `.snap`: drop a local snap with `snapd` absent → snapd install prompt →
      `snap install --dangerous` (may need `systemctl enable --now snapd.socket`).
- [ ] `.flatpak` / `.flatpakref`: drop one → installs per-user, no root prompt.
- [ ] `.AppImage`: both "Run once" and "Install to ~/Applications" (check the
      menu entry appears).
- [ ] `.run` / `.bin`: decline the warning (nothing runs), then accept + root.
- [ ] Cancel a long real install; confirm the log note about the pkexec child.
- [ ] Drag from the file manager with "Keep window on top" off — window should
      still raise as the drag enters.

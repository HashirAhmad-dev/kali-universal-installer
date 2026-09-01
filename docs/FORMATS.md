# Supported formats

KUPI decides the type from the file extension first, falling back to
`file --mime-type` (and then `file -b`, which is the only reliable way to spot an
AppImage). Each type is handled by one `PackageHandler` in `kupi/handlers/`.

A handler contributes two things:

- **preflight** — zero or more prompts the UI must resolve before building the plan
  (`confirm` → Yes/No, `warning` → Ok/Cancel, `choice` → pick one).
- **plan** — an ordered list of commands. The runner executes them one at a time,
  stops at the first non-zero exit, and streams everything live.

`<file>` below is always the absolute path. `pkexec` = the step runs as root via a
polkit prompt.

---

## `.deb` — Debian package

| | |
|---|---|
| Preflight | none |
| Plan | `pkexec apt install -y <file>` |

`apt` is used rather than `dpkg -i` so dependencies are resolved. An absolute path
is passed (apt treats a path containing `/` as a local file).

## `.rpm` — RPM package

| | |
|---|---|
| Preflight | if `alien` is not installed: **confirm** "install alien with apt?" |
| Plan | *(if alien missing)* `pkexec apt install -y alien` → `pkexec alien --install <file>` |

`alien --install` runs as root, wrapped as `sh -c 'cd "$1"; shift; exec "$@"'` so it
runs in the RPM's own directory (pkexec does not preserve the working directory).
alien does not execute RPM maintainer scripts — that is noted in the log.

## `.AppImage`

| | |
|---|---|
| Preflight | **choice**: `Run once` / `Install to ~/Applications` |
| Plan (run) | `chmod +x <file>` → `sh -c '"$1" \|\| exec "$1" --appimage-extract-and-run' sh <file>` |
| Plan (install) | `mkdir -p ~/Applications ~/.local/share/applications` → `mv -n <file> ~/Applications/` → `chmod +x` → write `~/.local/share/applications/kupi-<slug>.desktop` |

"Run once" executes attached, so output streams and **Cancel** works; it ends when
you close the app. The direct launch is retried unpacked if it fails (commonly: no
`libfuse2` on the system). "Install" **moves** the file — it leaves your Downloads
folder. The generated launcher is tagged `X-KUPI-Managed=true` and uses a generic
icon (KUPI does not unpack the AppImage to extract its real one).

## `.run` / `.bin` — self-extracting installers

| | |
|---|---|
| Preflight | **warning** "arbitrary installer, cannot be inspected — continue?" + **choice** `Normal user` / `Root (pkexec)` |
| Plan | `chmod +x <file>` → execute (attached, cwd = the file's folder; pkexec-wrapped for root) |

## `.sh` — shell installer script

| | |
|---|---|
| Preflight | **choice**: `Normal user` / `Root (pkexec)` |
| Plan | `chmod +x <file>` → `bash <file>` (cwd = the script's folder) |

Vendor scripts that write to `/opt` or `/usr` need root (XDM's `install.sh` prints
"Only root can do this" and exits 1 otherwise). The root path is wrapped so the
script still starts in its own directory.

## `.tar.*` / `.tgz` / `.zip` — archives

| | |
|---|---|
| Preflight | none |
| Plan | `tar -xvf <file> -C <tmp>` (all tar variants) or `unzip -o <file> -d <tmp>` |
| Then | on success the runner emits `rescan_requested(<tmp>)` instead of finishing |

`MainWindow` then scans the extracted tree (≤ 4 directories deep) for
`install.sh` → `setup.sh` → the first `*.deb`, shallowest path first, and runs the
match through its handler (**including that handler's own preflight**). If nothing is
found, it asks for a destination folder and moves the files there — status
**Extracted — manual**. The temp directory is removed once the whole chain concludes.

> `unzip` exits non-zero on benign warnings, which currently counts as a failed
> extraction. `tar` archives are unaffected.

## `.snap`

| | |
|---|---|
| Preflight | if `snap` is not on `PATH`: **confirm** "install snapd with apt?" |
| Plan | *(if missing)* `pkexec apt install -y snapd` → `pkexec snap install --dangerous <file>` |

`--dangerous` is required for a local, unsigned snap. A freshly installed snapd may
still need `systemctl enable --now snapd.socket` and a re-login.

## `.flatpak` / `.flatpakref`

| | |
|---|---|
| Preflight | if `flatpak` is not on `PATH`: **confirm** "install flatpak with apt?" |
| Plan | *(if missing)* `pkexec apt install -y flatpak` → `flatpak install --user -y <file>` |

The install itself is per-user and needs **no root**. A `.flatpakref` may require a
configured remote (e.g. Flathub) for its dependencies.

# Packaging & releases

KUPI ships as a single architecture-independent Debian package,
`kupi_<version>_all.deb`.

## Build

```bash
./build-deb.sh            # version defaults to 1.0.0
./build-deb.sh 1.1.0      # or pass one
```

Output: `dist/kupi_<version>_all.deb`. No root required (`dpkg-deb --root-owner-group`).

**Needs:** `dpkg-deb` (from `dpkg-dev`). If `lintian` is installed, the script runs
it on the result — a clean build reports no errors and no warnings.

## What the script does

1. Copies `kupi/` to `usr/lib/python3/dist-packages/kupi/` (the standard Debian
   location for a Python module — importable as `kupi` system-wide), stripping
   `__pycache__`.
2. Writes `usr/bin/kupi`:
   ```sh
   #!/bin/sh
   exec python3 -m kupi "$@"
   ```
3. Installs `packaging/kupi.desktop`, `packaging/kupi.svg`
   (`hicolor/scalable/apps/kupi.svg`), and a gzipped man page from `packaging/kupi.1`.
4. Renders `packaging/changelog` (→ `changelog.gz`, native package) and copies
   `packaging/copyright` and `README.md` into `usr/share/doc/kupi/`.
5. Fills `@VERSION@` / `@INSTALLED_SIZE@` in `packaging/control`, copies
   `packaging/postinst` (refreshes the desktop and icon caches).
6. Generates `DEBIAN/md5sums`.
7. `dpkg-deb --build`, then `dpkg-deb --info` / `--contents` / `lintian`.

## Installed layout

```
/usr/bin/kupi                                  launcher
/usr/lib/python3/dist-packages/kupi/           the package
/usr/share/applications/kupi.desktop           menu entry + Open-With handler
/usr/share/icons/hicolor/scalable/apps/kupi.svg
/usr/share/man/man1/kupi.1.gz
/usr/share/doc/kupi/{README.md,changelog.gz,copyright}
```

## Dependencies (`packaging/control`)

| Field | Packages |
|---|---|
| `Depends` | `python3 (>= 3.10)`, `python3-pyside6.qtwidgets`, `python3-pyside6.qtgui`, `python3-pyside6.qtcore`, `pkexec`, `file` |
| `Recommends` | `unzip` |
| `Suggests` | `alien`, `snapd`, `flatpak` |

`alien` / `snapd` / `flatpak` are *Suggests* on purpose — the handlers offer to
install them on first use.

## Install / uninstall

```bash
sudo apt install ./dist/kupi_1.0.0_all.deb
sudo apt remove kupi
```

## Cutting a release

1. Bump the version in `pyproject.toml`, `packaging/kupi.1`, and add a section to
   `CHANGELOG.md`.
2. `./build-deb.sh <version>` and smoke-test the `.deb`.
3. Commit, tag: `git tag -a v<version> -m "KUPI <version>" && git push --follow-tags`.
4. The **release** workflow (`.github/workflows/release.yml`) builds the `.deb` on
   the tag and attaches it to the GitHub Release. Or attach `dist/kupi_<version>_all.deb`
   by hand.

## Manual build without the script

```bash
mkdir -p pkgroot/DEBIAN pkgroot/usr/lib/python3/dist-packages
cp -r kupi pkgroot/usr/lib/python3/dist-packages/
install -Dm755 /dev/stdin pkgroot/usr/bin/kupi <<'EOF'
#!/bin/sh
exec python3 -m kupi "$@"
EOF
sed 's/@VERSION@/1.0.0/;s/@INSTALLED_SIZE@/200/' packaging/control > pkgroot/DEBIAN/control
dpkg-deb --root-owner-group --build pkgroot kupi_1.0.0_all.deb
```

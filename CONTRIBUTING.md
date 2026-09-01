# Contributing to KUPI

Thanks for taking a look. KUPI is deliberately small — a bug fix or a new package
handler is usually a single file plus a test.

## Development setup

```bash
git clone https://github.com/HashirAhmad-dev/kali-universal-installer.git
cd kali-universal-installer
./run.sh                    # creates .venv (PySide6) on first run, then launches
```

Or manage the environment yourself:

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"     # or: pip install PySide6
python -m kupi
```

## Running the tests

```bash
python -m pytest                              # if pytest is installed
# dependency-free equivalents:
python tests/test_detector.py                 # extension routing
python tests/test_handlers.py                 # every handler's preflight + plan shape
python tests/test_outcome.py                  # the exit-code / error-line scanner
QT_QPA_PLATFORM=offscreen python tests/test_integration.py   # widgets + real QProcess
```

Every test file also runs standalone (`python tests/<file>.py`) and exits non-zero
on failure, so CI and a bare machine agree.

## Project layout

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md). The short version:

- **Handlers are pure** — they return `Preflight` and `InstallPlan` data, nothing else.
- **`ProcessRunner` is the only thing that runs a process.**
- **`MainWindow` orchestrates** — drops, dialogs, the archive re-dispatch loop.

## Adding a package handler

1. Create `kupi/handlers/<type>.py`:

   ```python
   from __future__ import annotations
   import os
   from ..model import Command, InstallPlan, Preflight
   from .base import PackageHandler, exec_step, which

   class WidgetHandler(PackageHandler):
       package_type = "widget"
       extensions = (".widget",)

       def describe(self, filepath: str) -> str:
           return "Widget package -- installed with widgetctl"

       def preflight(self, filepath: str) -> list[Preflight]:
           return []                       # or confirm/warning/choice prompts

       def build_plan(self, filepath: str, answers: dict[str, str]) -> InstallPlan:
           path = os.path.abspath(filepath)
           return InstallPlan(commands=[
               Command(["widgetctl", "install", path],
                       label="widgetctl install", use_pkexec=True),
           ])
   ```

2. Add the type to `PackageType` and the extension/mime maps in `kupi/detector.py`.
3. Register it in `kupi/handlers/__init__.py` (one import, one `_REGISTRY` line).
4. Add a plan-shape test to `tests/test_handlers.py`.
5. Document the exact commands in `docs/FORMATS.md` and note the change in `CHANGELOG.md`.

### Guidelines

- Pass **absolute paths**. If a step needs a working directory and root, use
  `exec_step(argv, workdir, as_root=True, label=...)` — `pkexec` resets cwd.
- Use `pkexec` (`Command(..., use_pkexec=True)`), never `sudo`.
- If a required external tool may be missing, check with `which(...)` in
  `preflight()` and offer to install it as the first command in the plan.
- Keep `describe()` to one line; it is shown before the user commits.

## Style

- `ruff` config lives in `pyproject.toml` (`ruff check .`, `ruff format .`).
- Match the surrounding code: `from __future__ import annotations`, type hints,
  short module docstrings explaining the *why*.

## Commits & PRs

- Conventional-ish subjects (`feat:`, `fix:`, `docs:`, `build:`) are appreciated.
- One logical change per PR. Fill in the PR template checklist.

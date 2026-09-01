# Architecture

KUPI is intentionally small. Three ideas hold it together:

1. **Handlers are pure.** A handler looks at a file and the environment and returns
   *data* — a list of preflight questions and an ordered list of commands. It never
   touches `QProcess`, never blocks, never prompts.
2. **One executor.** `ProcessRunner` is the only component that spawns processes. It
   runs a plan's commands sequentially, streams their output, and decides the outcome.
3. **The window orchestrates.** `MainWindow` wires drops to detection, resolves
   preflight prompts, hands plans to the runner, and drives the archive re-dispatch
   loop.

```
 drop / Browse / CLI arg
          │
          ▼
   detector.detect(path) ──► PackageType
          │
          ▼
   handlers.get_handler(type) ──► PackageHandler
          │
   ┌──────┴───────────────── MainWindow._prepare_plan ─────────────────┐
   │  handler.preflight(path)  →  QMessageBox / QInputDialog  → answers │
   │  handler.build_plan(path, answers)  →  InstallPlan                 │
   └──────┬───────────────────────────────────────────────────────────┘
          ▼
   ProcessRunner.run(plan)
     • one QProcess per Command, MergedChannels
     • readyReadStandardOutput → output(str)  (streamed, never buffered)
     • stop at first non-zero exit
     • on finish:  outcome.analyze(text, exit_codes)
          │
          ├── plan.rescan_dir set & success ──► rescan_requested(dir)
          │        └─ MainWindow scans dir, builds a new plan, runs it
          │
          └── otherwise ──► finished(InstallOutcome) ──► MainWindow._conclude
```

## Modules

| Module | Responsibility |
|---|---|
| `kupi/__main__.py` | `python3 -m kupi` entry point (QApplication + MainWindow) |
| `kupi/detector.py` | `detect(path) -> Detection` — extension table, then `file --mime-type`, then `file -b` for AppImage |
| `kupi/model.py` | `Command`, `Preflight`, `InstallPlan` dataclasses — the handler ↔ runner contract |
| `kupi/handlers/base.py` | `PackageHandler` ABC + `exec_step()` (the cwd-safe pkexec wrapper) |
| `kupi/handlers/*.py` | one handler per format |
| `kupi/handlers/__init__.py` | `PackageType → handler` registry, `get_handler()` |
| `kupi/runner.py` | `ProcessRunner` — sequential `QProcess` execution, live output, cancel, rescan signal |
| `kupi/outcome.py` | `InstallOutcome` + `analyze()` — exit codes **and** error-line scan |
| `kupi/app.py` | `MainWindow` — layout, drag/drop, preflight dialogs, orchestration, temp cleanup |
| `kupi/ui/` | `DropZone`, `TerminalView`, `StatusBadge` widgets |

## The handler contract

```python
class PackageHandler(ABC):
    package_type: str
    extensions: tuple[str, ...]

    def describe(self, filepath: str) -> str: ...
    def preflight(self, filepath: str) -> list[Preflight]: ...     # default: []
    def build_plan(self, filepath: str, answers: dict[str, str]) -> InstallPlan: ...
```

`answers` is keyed by `Preflight.id`. A declined `confirm`/`warning` aborts before
`build_plan` is called. `exec_step(argv, workdir, as_root=, label=)` produces a
`Command` that runs `argv` in `workdir` — directly when unprivileged, or wrapped as
`pkexec sh -c 'cd "$1"; shift; exec "$@"' sh <workdir> <argv…>` when `as_root`,
because `pkexec` resets the working directory.

## The execution engine

`ProcessRunner` (a `QObject` with signals):

| Signal | Meaning |
|---|---|
| `output(str)` | a chunk of merged stdout/stderr, ready to append |
| `command_started(str, int, int)` | label, 1-based step index, step total |
| `running_changed(bool)` | plan started / ended |
| `finished(InstallOutcome)` | terminal result |
| `rescan_requested(str)` | success on a plan with `rescan_dir` — continue the chain instead |

Design points:

- **One `QProcess` per command**, created fresh, `MergedChannels` so stdout and
  stderr interleave in true order.
- Output is emitted on every `readyReadStandardOutput` — **never buffered and dumped
  at the end**. A copy is accumulated for the outcome scan.
- The plan **stops at the first non-zero exit**.
- **Cancel:** `QProcess.kill()` reaches the `pkexec` wrapper, not the privileged
  child it spawned; the runner logs that a root process may still be finishing.
- Stale signals from an already-replaced process are ignored via a `sender()`
  identity check.

## Outcome

`analyze(output, exit_codes, cancelled=False)`:

| Result | When |
|---|---|
| `CANCELLED` | user cancelled |
| `FAILED` | any command exited non-zero |
| `SUCCESS_WITH_WARNINGS` | all exit 0, but the output has a line starting `E: ` or matching `error` that is not `0 errors` / `no errors` / `errors: 0` |
| `SUCCESS` | all exit 0, no error lines |

This is the point of the app: `apt`/`dpkg` can exit 0 while printing
`Errors were encountered while processing:` — that is surfaced as an amber state,
not a green check.

## Archive re-dispatch

`ArchiveHandler` only extracts. Its plan carries `rescan_dir`. On success the runner
emits `rescan_requested(dir)` (not `finished`). `MainWindow._on_rescan_requested`:

1. registers the temp dir for cleanup,
2. `_scan_extracted(dir)` → `install.sh` > `setup.sh` > first `*.deb` (shallowest wins, depth ≤ 4),
3. found → `_prepare_plan(handler, target)` (runs *that* handler's preflight too) →
   `QTimer.singleShot(0, runner.run)` so it starts outside the runner's callstack,
4. not found → `QFileDialog` for a folder → `_move_tree` → status **Extracted — manual**.

`_conclude()` is the single end-of-flow funnel — status, note, button reset, and
`shutil.rmtree` of every registered temp dir. It also runs on window close.

<!-- Thanks for contributing to KUPI. -->

## What & why

<!-- What does this change and what problem does it solve? Link issues with "Closes #123". -->

## Type of change

- [ ] Bug fix
- [ ] New package handler
- [ ] Feature / improvement
- [ ] Docs / packaging / CI

## Checklist

- [ ] `python tests/test_detector.py && python tests/test_handlers.py && python tests/test_outcome.py` pass
- [ ] `QT_QPA_PLATFORM=offscreen python tests/test_integration.py` passes
- [ ] New/changed behaviour has a test
- [ ] `./build-deb.sh` still produces a lintian-clean package (if packaging touched)
- [ ] Docs updated (`README.md`, `docs/FORMATS.md`, `CHANGELOG.md` as relevant)

## For a new package handler

- [ ] One module in `kupi/handlers/`, one line in the registry
- [ ] `describe()` / `preflight()` / `build_plan()` only — no `QProcess`, no blocking
- [ ] Exact install command(s) and root requirement documented in `docs/FORMATS.md`

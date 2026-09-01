"""Dev entry point. Thin shim over ``kupi.__main__`` so ``python main.py`` and
``run.sh`` keep working from a source checkout; the installed package uses
``python3 -m kupi``.
"""
from __future__ import annotations

from kupi.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())

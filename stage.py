#!/usr/bin/env python
"""Stage the CBDB-Desktop distribution named by CBDB_DESKTOP_ZIP.

Thin entrypoint so staging is runnable from the repo root without a
pytest session:

    python stage.py            # stage (or reuse a cached tree) and print it
    python stage.py --force    # discard the cached tree and restage
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "tests"))

from cbdb_desktop.staging import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())

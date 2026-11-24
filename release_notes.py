#!/usr/bin/env python
"""Convert the notes shipped in the distribution into Markdown.

Thin entrypoint, like stage.py:

    python release_notes.py     # -> docs/release-notes/<archive stem>/

See tests/cbdb_desktop/release_notes.py for what is read and how.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "tests"))

from cbdb_desktop.release_notes import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())

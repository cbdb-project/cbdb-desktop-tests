#!/usr/bin/env python
"""Check the shipped pages' three languages against the label glossary.

Thin entrypoint, like stage.py:

    python check_translations.py    # -> reports/CBDB_Desktop_Translations.md / .xlsx

The rules are in tests/cbdb_desktop/i18n.py; the same checks run as
tests in tests/test_translations.py.  Run the test suite first to
include what the pages show in a real browser.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "tests"))

from cbdb_desktop.i18n_report import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())

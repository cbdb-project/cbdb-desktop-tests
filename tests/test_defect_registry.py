"""The defect registry has to stay true, and stay bilingual.

`tests/cbdb_desktop/defects.py` holds one round's findings for as long
as it takes to write that round's report -- nothing else reads it, and
nothing in it makes a test tolerate a failure.  The report *is*
generated from it, which makes two failure modes worth catching
automatically rather than by eye.

* A `source` reference rots.  Every entry cites `file:line` in the
  shipped build, and a new distribution moves those lines.  A bug report
  that points at the wrong line wastes the maintainer's time and costs
  the whole report its credibility.
* One language is edited and the other is not.  A defect whose English
  says one thing and whose Chinese says another is worse than a defect
  reported in one language only.

Neither needs the application running, so this file is fast and has no
``app`` marker.
"""
from __future__ import annotations

import re

import pytest

from cbdb_desktop.defects import (DEFECTS, ORIGINS, PRIORITIES, Defect,
                                  _DEFECTS)
from cbdb_desktop.staging import AppLayout

#: "Code/main.go:42 (why)" or "Code/main.go:handleThing (why)" -> parts.
#: A symbol is the better citation where one exists: it survives the line
#: drift that every new build produces.
#:
#: The path may contain spaces.  It could not until 2026-09-10, and the
#: build had already shipped a file that needs it -- `The directory
#: structure for CBDB-Desktop.txt`, which is the distribution's own
#: statement of where its files belong and so exactly the kind of thing a
#: packaging defect has to cite.  Refusing the name would have meant
#: citing that file less precisely than the evidence allows, which is the
#: opposite of what this gate is for.
_REFERENCE = re.compile(
    r"^(?P<path>[^:]+?)"
    r"(?::(?P<line>\d+)|:(?P<symbol>[A-Za-z_]\w*))?"
    r"(?:\s+\((?P<note>.*)\))?$")

#: Fields that must be written in both languages.
BILINGUAL = ("title", "area", "summary", "evidence", "impact", "fix")


def _assert_written_in_chinese(what: str, text: str, *,
                               least_characters: int = 4,
                               least_share: float = 0.15) -> None:
    """The field is written in Chinese, not English with a stray character.

    Both a count and a share, because either alone is wrong here.  These
    fields legitimately carry English identifiers, routes, SQL and file
    paths -- ``area_zh`` is "人物瀏覽（/CBDB_Browser）", proper Chinese
    that is only a fifth CJK by character -- so a high ratio would reject
    correct entries.  A count alone would accept an English sentence with
    one Chinese word dropped in.  Together they catch what this is for:
    a half-finished translation.
    """
    meaningful = [c for c in text if not c.isspace() and not c.isdigit()]
    chinese = [c for c in meaningful if "一" <= c <= "鿿"]
    assert meaningful, f"{what} has no text"

    share = len(chinese) / len(meaningful)
    assert len(chinese) >= least_characters and share >= least_share, (
        f"{what} has {len(chinese)} Chinese characters ({share:.0%} of it) "
        "-- it reads as English text rather than a translation")


@pytest.fixture(params=sorted(DEFECTS), ids=sorted(DEFECTS))
def defect(request) -> Defect:
    return DEFECTS[request.param]


def test_every_source_reference_points_at_something_real(defect: Defect,
                                                         layout: AppLayout):
    """Each cited file exists, and each cited place is findable in it.

    The mechanical half of "check the references still point where they
    claim" -- a checklist item nobody ticks honestly by hand.  Be clear
    about the limit: a line number is checked only for being within the
    file, and a symbol only for appearing as a *definition* somewhere in
    it.  Neither proves the citation still points at the interesting
    code, so a symbol is the better citation of the two: it survives the
    line drift every new build brings, and this check has real teeth
    against it.
    """
    assert defect.source, f"{defect.key} cites no source at all"

    problems: list[str] = []
    for reference in defect.source:
        match = _REFERENCE.match(reference)
        if not match:
            problems.append(f"{reference!r} is not 'path[:line] [(note)]'")
            continue

        path = layout.root / match.group("path")
        if not path.exists():
            problems.append(f"{match.group('path')} does not exist in the build")
            continue

        line, symbol = match.group("line"), match.group("symbol")
        if line is None and symbol is None:
            continue
        if path.is_dir():
            problems.append(f"{reference} names a directory but cites a place "
                            "inside one")
            continue

        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            problems.append(f"{reference}: {exc}")
            continue

        if line is not None:
            count = text.count("\n") + 1
            if int(line) > count:
                problems.append(f"{reference}: the file has only {count} lines")
        else:
            # A definition, not a mention: "handleQuery" appears at every
            # call site, so a bare substring search would keep passing
            # long after the function was renamed or removed.
            defined = re.search(
                rf"^\s*(?:func|def|var|type|const)\s+"
                rf"(?:\([^)]*\)\s*)?{re.escape(symbol)}\b",
                text, re.MULTILINE)
            if not defined:
                problems.append(
                    f"{reference}: nothing named {symbol} is defined there")

    assert not problems, f"{defect.key}:\n  " + "\n  ".join(problems)


def test_every_defect_is_written_in_both_languages(defect: Defect):
    """No half-translated entry, and no Chinese left as English.

    The reports are generated per language from these fields; a missing
    one silently falls back to English, which reads as a translation
    nobody finished.
    """
    for field in BILINGUAL:
        english = getattr(defect, field)
        chinese = getattr(defect, f"{field}_zh")
        assert english.strip(), f"{defect.key}.{field} is empty"
        assert chinese.strip(), f"{defect.key}.{field}_zh is empty"
        assert chinese != english, \
            f"{defect.key}.{field}_zh is the English text"
        _assert_written_in_chinese(f"{defect.key}.{field}_zh", chinese)

    assert defect.steps, f"{defect.key} has no reproduction steps"
    assert len(defect.steps) == len(defect.steps_zh), (
        f"{defect.key} has {len(defect.steps)} steps in English and "
        f"{len(defect.steps_zh)} in Chinese")
    for index, (english, chinese) in enumerate(
            zip(defect.steps, defect.steps_zh), 1):
        assert chinese.strip(), f"{defect.key} step {index} is empty in Chinese"
        assert chinese != english, \
            f"{defect.key} step {index} is still the English text"

    # The share is measured over the steps as a whole, not step by step.
    # A single step is often mostly a quoted server message or a SQL
    # statement -- "回應為 200：「Rankings updated and BIOG_MAIN rebuilt
    # successfully」。" is correct Chinese and 6% CJK -- so a per-step
    # ratio would reject good translations.  Over the whole list the
    # prose dominates and the signal is real again.
    _assert_written_in_chinese(f"{defect.key}.steps_zh",
                               "".join(defect.steps_zh))


def test_every_defect_is_demonstrated_by_a_test_that_exists(defect: Defect,
                                                            pytestconfig):
    """The named tests must exist, or the report cites nothing.

    A renamed test would otherwise leave its defect reported as NOT
    EXERCISED for as long as nobody read the report closely.  The test
    files are searched by name, which is how the report matches them too.
    """
    assert defect.tests, f"{defect.key} names no test"

    root = pytestconfig.rootpath / "tests"
    sources = "\n".join(path.read_text(encoding="utf-8")
                        for path in root.rglob("test_*.py"))
    # Module level only: a nested helper, or the name inside a
    # docstring, is not something pytest collects.  This still
    # stops short of proving collection -- a test can exist and
    # be deselected -- but the report's status column covers that.
    missing = [name for name in defect.tests
               if not re.search(rf"^def {re.escape(name)}\(", sources,
                                re.MULTILINE)]
    assert not missing, f"{defect.key} names tests that do not exist: {missing}"


def test_the_registry_is_internally_consistent():
    """Keys, priorities and origins line up."""
    for key, defect in DEFECTS.items():
        assert defect.key == key
        assert defect.priority in PRIORITIES, \
            f"{key} has priority {defect.priority!r}"
        assert defect.severity in ("high", "medium", "low")
        # The origin decides who the entry is sent to, so an unknown one
        # is not a typo to shrug at: the report prints it verbatim, and
        # a data problem addressed to the application developers is both
        # wasted and wrong (AGENTS.md § "Where a defect comes from").
        assert defect.origin in ORIGINS, \
            f"{key} has origin {defect.origin!r}, not one of {sorted(ORIGINS)}"

    # The report's table of contents and its per-issue anchors are built
    # from these keys, so two entries sharing one would silently merge in
    # the deliverable.
    #
    # Compared against the *tuple* the registry is built from, not
    # against the dict.  ``DEFECTS`` is ``{d.key: d for d in _DEFECTS}``,
    # so ``set(DEFECTS)`` is its key set and ``len(set(DEFECTS)) ==
    # len(DEFECTS)`` is true whatever happens -- including in the one
    # case it was written to catch, where the comprehension has already
    # dropped the duplicate silently.  The lengths that can disagree are
    # the tuple's and the dict's.
    assert len(DEFECTS) == len(_DEFECTS), (
        f"{len(_DEFECTS)} entries were written and {len(DEFECTS)} "
        f"survived keying, so {len(_DEFECTS) - len(DEFECTS)} share a "
        "key with another and have been silently merged.  The report's "
        "contents and anchors come from these keys, so the losing "
        "entry would vanish from the deliverable without a word.")

"""The report has to be a function of the run, and of nothing else.

The deliverable of this project is the issue report, and its whole
claim on the maintainer's attention is that no part of it was written by
hand: it is rendered from ``cbdb_desktop/defects.py`` -- which holds one
round's findings while that round writes them -- plus the JSON of the
run that judged them.  Everything checked here was checked by hand once,
in the session that cleared the previous round, and by hand is exactly
the wrong place for it: a hand check cannot be repeated by whoever
generates the next report.

Four properties, each with its own failure it exists to prevent:

* **Reproducible.**  Same registry, same run, same bytes.  A report that
  moves between two renderings of one run has something in it that came
  from the renderer's environment rather than the measurement.
* **Nothing invented.**  Every issue in the report is an entry in the
  registry, and every status shown is derived from that run's outcomes.
  A report cannot name a defect the tests never demonstrated.
* **Nothing dropped.**  Every registry entry reaches the report, in both
  languages, and the coverage table accounts for *every* test file the
  run collected.  The hand-written table it replaced described 277 of
  823 tests and looked complete, which is the more dangerous of the two
  ways to be wrong.
* **Nothing tolerated invisibly.**  If the run recorded waived outcomes
  (``cbdb_desktop/waivers.py``), the report prints them, with the reason
  and the date, in the language the reader is reading.

None of this needs the application, or a real run: the runs below are
built here, so the tests judge the renderer rather than whatever happens
to be in ``reports/pytest_report.json``.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from cbdb_desktop.config import REPO_ROOT
from cbdb_desktop.defects import DEFECTS, Defect

sys.path.insert(0, str(REPO_ROOT / "reports"))

import generate_report as gr  # noqa: E402

LANGS = ("en", "zh")

#: A defect with every field filled, so a rendering exercises every
#: branch.  Built here rather than taken from the registry: the registry
#: is empty between rounds, and a test that only ran when someone had
#: filed something would be no test at all.
_SAMPLE = Defect(
    key="CBDB-D-999",
    priority="P0",
    severity="high",
    origin="software",
    title="A sample finding, for testing the renderer",
    title_zh="用於測試產生器的範例問題",
    area="Nowhere real",
    area_zh="並非真實存在的範圍",
    summary="What is wrong, in a sentence.",
    summary_zh="問題所在，一句話說明。",
    evidence="The measurement that establishes it.",
    evidence_zh="據以認定此事的實測數據。",
    impact="What it means for someone using CBDB.",
    impact_zh="對使用 CBDB 的人而言意味著什麼。",
    fix="What would resolve it.",
    fix_zh="可以如何修正。",
    steps=("Do the first thing.", "Then the second."),
    steps_zh=("先做第一件事。", "接著做第二件事。"),
    source=("Code/main.go:1",),
    tests=("test_the_sample_finding",),
)


def _run(tests: dict[str, str], *, duration: float = 12.5,
         created: float = 1788864324.0,
         crash: dict[str, str] | None = None,
         phase: str = "call") -> dict:
    """A pytest-json-report run, from {nodeid: outcome}.

    ``crash`` attaches a crash message to a node, the way pytest's JSON
    report does for a failure.  That message is how the renderer tells a
    test that *demonstrated* its defect (it carries
    ``KnownShippedDefect``) from one that merely broke.  ``phase`` says
    which of setup/call/teardown records it: a test that raises in a
    fixture is reported under "setup" with nothing under "call" at all.
    """
    crash = crash or {}
    outcomes: dict[str, int] = {}
    for outcome in tests.values():
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
    entries = []
    for nodeid, outcome in tests.items():
        entry = {"nodeid": nodeid, "outcome": outcome}
        if nodeid in crash:
            entry[phase] = {"crash": {"message": crash[nodeid]}}
        entries.append(entry)
    return {
        "created": created,
        "duration": duration,
        "summary": {**outcomes, "total": len(tests), "collected": len(tests)},
        "tests": entries,
    }


@pytest.fixture
def one_defect(monkeypatch) -> Defect:
    """A registry holding exactly the sample defect, for one test."""
    monkeypatch.setitem(gr.DEFECTS, _SAMPLE.key, _SAMPLE)
    monkeypatch.setitem(DEFECTS, _SAMPLE.key, _SAMPLE)
    return _SAMPLE


# ---------------------------------------------------------------------------
# reproducible
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lang", LANGS)
def test_the_same_run_renders_the_same_bytes_twice(lang, one_defect):
    """Nothing in the report may come from the moment it was written.

    The timestamp in the header is the *run's*, not the renderer's, and
    this is what keeps it that way: a `datetime.now()` anywhere in the
    document would make two renderings of one measurement differ, and
    then nobody can tell whether a changed report means a changed build.
    """
    run = _run({"tests/test_qbe.py::test_the_sample_finding": "xfailed"})
    first = gr.render_markdown(run, lang, "CBDB-Desktop_20260907.7z")
    second = gr.render_markdown(run, lang, "CBDB-Desktop_20260907.7z")
    assert first == second
    assert "2026-09-08" in first, \
        "the header carries the run's own date, not today's"


@pytest.mark.parametrize("lang", LANGS)
def test_the_report_is_derived_only_from_the_registry_and_the_run(lang):
    """Change the run, and only the run's own facts change.

    Two runs of the same (empty) registry differing in duration must
    produce reports that differ in exactly that, which is the property
    that makes a report diff readable.
    """
    fast = gr.render_markdown(_run({"tests/test_qbe.py::test_x": "passed"},
                                   duration=10), lang, "b.7z")
    slow = gr.render_markdown(_run({"tests/test_qbe.py::test_x": "passed"},
                                   duration=99), lang, "b.7z")
    assert fast != slow
    assert fast.replace("10s", "99s").replace("10 秒", "99 秒") == slow


# ---------------------------------------------------------------------------
# nothing invented, nothing dropped
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lang", LANGS)
def test_the_report_names_no_issue_the_registry_does_not_hold(lang,
                                                             monkeypatch):
    """A report cannot mention a finding nobody filed.

    Rendered from an empty registry -- the state every round starts in --
    the document must contain no CBDB-D id at all.  This is the check
    that a reader of the report is really being shown the registry and
    not something the renderer remembers.

    The registry is emptied here rather than asserted empty.  It used to
    be asserted, which made this test pass only between rounds and fail
    for the whole of the one round that actually has findings to report
    -- exactly when the renderer is being trusted with real content.
    """
    monkeypatch.setattr(gr, "DEFECTS", {})
    run = _run({"tests/test_qbe.py::test_x": "passed"})
    text = gr.render_markdown(run, lang, "b.7z")
    assert "CBDB-D-" not in text
    assert gr.STRINGS["no_issues"][lang] in text


@pytest.mark.parametrize("lang", LANGS)
def test_every_registry_entry_reaches_the_report(lang, one_defect):
    """And reaches it in the language the reader is reading."""
    run = _run({"tests/test_qbe.py::test_the_sample_finding": "xfailed"})
    text = gr.render_markdown(run, lang, "b.7z")

    assert one_defect.key in text
    for field in ("title", "summary", "evidence", "impact", "fix"):
        assert one_defect.text(field, lang) in text, \
            f"{field} is missing from the {lang} report"
    for step in (one_defect.steps_zh if lang == "zh" else one_defect.steps):
        assert step in text
    for reference in one_defect.source:
        assert reference in text
    for name in one_defect.tests:
        assert name in text


def test_a_fixed_defect_is_reported_as_fixed_rather_than_confirmed(one_defect):
    """The run decides the status, not the registry.

    A test that stops demonstrating its defect is the whole mechanism by
    which a fix is noticed, so the report has to say so even while the
    entry is still there -- otherwise the reader is told a fixed problem
    is present.
    """
    node = "tests/test_qbe.py::test_the_sample_finding"
    # How a finding is spelled since 2026-09-08: an ordinary failure
    # whose message carries the exception the test raised once it
    # recognised the defect's signature.
    signature = _run(
        {node: "failed"},
        crash={node: "cbdb_desktop.defects.KnownShippedDefect: "
                     "the sample finding, with its numbers"})
    # A failure with no such signature: the test broke on something
    # else, and the run neither confirms nor clears the entry.
    unrelated = _run({node: "failed"},
                     crash={node: "AssertionError: something unrelated"})
    confirmed = _run({node: "xfailed"})
    fixed = _run({node: "xpassed"})
    silent = _run({"tests/test_qbe.py::test_something_else": "passed"})

    # Raised from a fixture: pytest records it under "setup", with an
    # outcome of "error" and nothing under "call" at all.
    from_fixture = _run(
        {node: "error"}, phase="setup",
        crash={node: "cbdb_desktop.defects.KnownShippedDefect: from a "
                     "fixture, but a demonstration all the same"})
    # And the case that must NOT confirm: an ordinary assertion whose
    # message merely mentions the exception's name.  A substring search
    # would read this as a demonstration of every entry naming the test.
    mentions_it = _run(
        {node: "failed"},
        crash={node: "AssertionError: no test may raise "
                     "KnownShippedDefect for a passing build"})

    assert gr.status_of(signature, one_defect) == "CONFIRMED"
    assert gr.status_of(from_fixture, one_defect) == "CONFIRMED"
    assert gr.status_of(unrelated, one_defect) == "INCONCLUSIVE"
    assert gr.status_of(mentions_it, one_defect) == "INCONCLUSIVE"
    assert gr.status_of(confirmed, one_defect) == "CONFIRMED"
    assert gr.status_of(fixed, one_defect) == "APPARENTLY FIXED"
    assert gr.status_of(silent, one_defect) == "NOT EXERCISED"

    text = gr.render_markdown(fixed, "en", "b.7z")
    assert gr.STATUS_TEXT["en"]["APPARENTLY FIXED"] in text


# ---------------------------------------------------------------------------
# the coverage table, derived from the run
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("lang", LANGS)
def test_the_committed_report_matches_the_registry_it_was_rendered_from(lang):
    """The .md in the tree is what the registry renders today.

    The committed Markdown is the deliverable, and the only thing that
    keeps it honest is that nobody edits it by hand.  That is not quite
    enough: editing the *registry* after generating leaves a report that
    is neither hand-written nor current, and nothing said so.  It
    happened on this round -- D-006 was refiled against a different file
    and the committed report went on printing the superseded text and
    the old citations for two more commits.

    Rendering is deterministic given a run (see
    ``test_the_same_run_renders_the_same_bytes_twice``), so the check is
    just byte equality against a fresh render from the run this report
    was made from.

    Skipped when there is no local run to render from: the JSON is a
    run artefact and is not committed.
    """
    if not gr.DEFAULT_JSON.is_file():
        pytest.skip(f"no local run at {gr.DEFAULT_JSON.name} to render from; "
                    "this check needs one.  Run .\\run_tests.ps1")

    committed = REPO_ROOT / "reports" / f"{gr.STEM[lang]}.md"
    if not committed.is_file():
        pytest.skip(f"{committed.name} is not in the tree: a round that has "
                    "not written its report yet")

    run = gr.load_run(gr.DEFAULT_JSON)
    # Same three inputs main() renders from: the run, the registry, and
    # the run's own waiver record.  Leaving the waivers out would make
    # this check pass on a report that had dropped the waiver section.
    fresh = gr.render_markdown(run, lang, gr._build_name(),
                               gr.load_waivers(gr.DEFAULT_WAIVERS))

    assert committed.read_text(encoding="utf-8") == fresh, (
        f"{committed.name} is not what the registry renders from this run.  "
        "Either the registry changed after the report was generated, or the "
        "report was edited by hand.  Regenerate it: "
        "python reports\\generate_report.py")


def test_the_coverage_table_describes_every_test_file_in_the_suite():
    """Every test file this repo has is described, in both languages.

    The gate that makes the coverage table an inventory rather than a
    claim.  The hand-written list this replaced accounted for 277 of 823
    tests -- it had simply not been extended when the export, matrix,
    browser and coverage suites were added, and nothing said so.  A new
    test file now fails here until somebody writes the one line that
    says what it checks.
    """
    files = sorted(path.name for path in (REPO_ROOT / "tests").glob("test_*.py"))
    described = [name for name, _area, _what in gr.COVERAGE]

    assert sorted(described) == files, (
        "the coverage table and the suite disagree.  Missing: "
        f"{sorted(set(files) - set(described))}; "
        f"describing files that no longer exist: "
        f"{sorted(set(described) - set(files))}")
    assert len(described) == len(set(described)), "a file is described twice"

    missing_zh = [name for name in described if name not in gr.COVERAGE_ZH]
    assert not missing_zh, f"no Chinese description for {missing_zh}"


def test_the_coverage_table_accounts_for_every_test_in_the_run():
    """The rows have to add up to the run's own total.

    A file the table does not describe still gets a row, named by its
    filename, rather than being dropped -- because the failure this
    guards against is a table that understates the suite while looking
    complete.
    """
    run = _run({"tests/test_qbe.py::test_a": "passed",
                "tests/test_exports.py::test_b": "passed",
                "tests/test_brand_new.py::test_c": "passed"})

    for lang in LANGS:
        rows = gr.coverage_rows(run, lang)
        counted = sum(count for _area, count, _what in rows[:-1])
        area, total, _what = rows[-1]
        assert total == 3 == counted, rows
        assert area == gr.STRINGS["coverage_total"][lang]
        assert any("test_brand_new.py" == area for area, _c, _w in rows), \
            "an undescribed file must still appear, by name"

    assert gr.undescribed_files(run) == ["test_brand_new.py"]


def test_a_described_file_that_did_not_run_shows_zero():
    """Not omitted: "we did not run that" is information."""
    run = _run({"tests/test_qbe.py::test_a": "passed"})
    rows = dict((area, count) for area, count, _what in
                gr.coverage_rows(run, "en"))
    assert rows["The Query Builder"] == 1
    assert rows["Every export button"] == 0


# ---------------------------------------------------------------------------
# waived outcomes
# ---------------------------------------------------------------------------

_WAIVED = {
    "table": "waivers.toml",
    "waivers": 1,
    "entries": [{
        "test": "test_an_export_produces_a_well_formed_file",
        "params": ["entry:kml", "places:kml"],
        "mode": "tolerate",
        "raises": "KnownShippedDefect",
        "reason": "Agreed 2026-09-10: cosmetic for our readers.",
        "reason_zh": "2026-09-10 協商：對我們的讀者而言只是外觀問題。",
        "agreed_by": "maintainer",
        "agreed_on": "2026-09-10",
        "expires": "2026-12-01",
        "note": "",
    }],
}


@pytest.mark.parametrize("lang", LANGS)
def test_a_waived_outcome_is_printed_with_its_reason_and_its_date(lang):
    """Nothing may be tolerated without the reader being told.

    The waiver table lives outside the suite and can be edited by
    anyone; the one thing that keeps it honest towards the *maintainer*
    is that every entry appears in the report he reads, in his language,
    with who agreed to it and when.
    """
    run = _run({"tests/test_exports.py::test_x": "xfailed"})
    text = gr.render_markdown(run, lang, "b.7z", _WAIVED)
    entry = _WAIVED["entries"][0]

    assert gr.STRINGS["waived"][lang] in text
    assert entry["test"] in text
    assert entry["reason_zh" if lang == "zh" else "reason"] in text
    assert entry["agreed_on"] in text and entry["agreed_by"] in text
    assert entry["expires"] in text
    assert "entry:kml" in text and "places:kml" in text
    assert gr.STRINGS["waived_modes"][lang]["tolerate"] in text


@pytest.mark.parametrize("lang", LANGS)
def test_a_run_that_waived_nothing_says_so(lang):
    run = _run({"tests/test_qbe.py::test_x": "passed"})
    text = gr.render_markdown(run, lang, "b.7z", {"waivers": 0, "entries": []})
    assert gr.STRINGS["waived_none"][lang] in text


@pytest.mark.parametrize("lang", LANGS)
def test_no_waiver_record_omits_the_section_rather_than_claiming_zero(lang):
    """"We did not measure" and "there were none" are different claims.

    The record is written by pytest, so its absence means the report is
    being generated from a run that predates the feature or never ran
    the suite -- neither of which entitles the document to say nothing
    was waived.
    """
    run = _run({"tests/test_qbe.py::test_x": "passed"})
    text = gr.render_markdown(run, lang, "b.7z", None)
    assert gr.STRINGS["waived"][lang] not in text
    assert gr.STRINGS["waived_none"][lang] not in text


def test_the_waiver_record_is_read_from_where_pytest_writes_it(tmp_path):
    """The default path is the one conftest writes, not a copy of it."""
    assert gr.DEFAULT_WAIVERS == REPO_ROOT / "artifacts" / "waivers_applied.json"
    assert gr.load_waivers(tmp_path / "absent.json") is None

    path = tmp_path / "waivers_applied.json"
    path.write_text(json.dumps(_WAIVED, ensure_ascii=False), encoding="utf-8")
    assert gr.load_waivers(path) == _WAIVED


def test_the_conftest_record_renders_without_reshaping(tmp_path):
    """What pytest writes is what the report reads.

    A separate check because the two halves live in different files and
    a renamed field would otherwise surface as an empty column in a
    document nobody re-reads before sending.
    """
    from cbdb_desktop import waivers as w
    import datetime as dt

    table = w.WaiverTable(path=Path("waivers.toml"), waivers=(w.Waiver(
        test="test_an_export_produces_a_well_formed_file",
        params=("entry:kml",), reason="why", reason_zh="原因",
        agreed_by="maintainer", agreed_on=dt.date(2026, 9, 10)),))
    recorded = {"entries": [waiver.as_json() for waiver in table.waivers]}

    rows = gr.waived_rows(recorded, "zh")
    assert len(rows) == 1
    check, applies, effect, agreed, until, why = rows[0]
    assert check == "test_an_export_produces_a_well_formed_file"
    assert applies == "entry:kml"
    assert effect == gr.STRINGS["waived_modes"]["zh"]["tolerate"]
    assert agreed == "2026-09-10 (maintainer)"
    assert until == gr.STRINGS["waived_forever"]["zh"]
    assert why == "原因"


def test_a_waiver_covering_every_case_says_so_rather_than_leaving_it_blank():
    """An empty ``params`` means "all of them", which a blank cell hides."""
    recorded = {"entries": [dict(_WAIVED["entries"][0], params=[])]}
    for lang in LANGS:
        _check, applies, *_rest = gr.waived_rows(recorded, lang)[0]
        assert applies == gr.STRINGS["waived_all"][lang]

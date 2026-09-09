"""The waiver table has to stay honest, and it has to be the only channel.

Two different jobs in one file, and both are gates rather than
descriptions.

**The table, checked against this run.**  A waiver is addressed by the
program's own name for a test -- the function, plus the parametrisation
ids it ran with.  That address can rot: a test gets renamed, a
parametrisation id changes when an inventory grows, an endpoint key is
spelled wrongly.  A waiver that matches nothing waives nothing, the test
fails as it always would, and the failure then reads as a fresh
regression while a file in the repo insists it was agreed away.  So an
unmatched waiver fails this file, loudly, naming what it could not find.

**The suite, checked against the table.**  Tolerating a failure is only
allowed through the table.  ``test_no_test_file_expects_a_failure_of_its
_own`` walks every test module's syntax tree and refuses
``pytest.mark.xfail`` anywhere in it -- because a marker written next to
a test is invisible policy: undated, unilingual, absent from the report,
and (when it quotes a defect id) keyed to something that stops existing
the moment the next stateless round starts.

Neither needs the application, so this file is fast and carries no
``app`` marker.  With ``CBDB_WAIVERS`` unset there is nothing to waive
and the gates pass having measured zero, which is the honest reading and
is printed as such.  ``.env.example`` does set it, at this repo's own
``waivers.toml``, and ``test_the_shipped_env_example_points_at_a_usable
_table`` keeps that setting working -- an example that does not load is
how a feature nobody can configure gets shipped.
"""
from __future__ import annotations

import ast
import datetime as dt
import textwrap
from pathlib import Path

import pytest

from cbdb_desktop import waivers
from cbdb_desktop.config import REPO_ROOT
from cbdb_desktop.waivers import Waiver, WaiverError, WaiverTable, load, parse

# The same predicate the endpoint-coverage gate uses, for the same
# reason: a run selected with -k or a single file legitimately collects
# none of the tests a waiver names, and judging the table on that run
# would report a working waiver as broken.  The predicate has its own
# unit test in test_zz_controls.py, because a gate's own failure mode is
# skipping and no assertion inside it can catch that.
from test_zz_controls import _run_was_filtered

_MINIMAL = """
[test_something]
reason = "Agreed for now."
reason_zh = "暫時同意先不處理。"
agreed_by = "maintainer"
agreed_on = 2026-09-10
"""


def _waiver(**kw) -> Waiver:
    fields = dict(test="test_something", reason="why", reason_zh="原因",
                  agreed_by="maintainer", agreed_on=dt.date(2026, 9, 10))
    fields.update(kw)
    return Waiver(**fields)


# ---------------------------------------------------------------------------
# this run's table
# ---------------------------------------------------------------------------

def test_every_waiver_addresses_a_test_this_run_collected(
        request, waiver_table: WaiverTable):
    """A waiver that matches nothing is a failure, not a no-op.

    The failure mode this exists for: someone waives
    ``test_an_export_produces_a_well_formed_file`` with
    ``params = ["networks:pajec"]``, one letter wrong.  Nothing is
    waived, the endpoint fails as before, and the run looks like a
    regression nobody agreed to.  Silence would be the worst possible
    answer, so the run goes red with the misspelling in the message.
    """
    if not waiver_table.enabled:
        print("\nwaivers: CBDB_WAIVERS is not set -- 0 waivers")
        return

    why_filtered = _run_was_filtered(request.config)
    unmatched = waiver_table.unmatched()
    if why_filtered and unmatched:
        pytest.skip(f"cannot judge the waiver table on a filtered run "
                    f"({why_filtered}): {[w.test for w in unmatched]} "
                    "collected nothing here")

    problems = []
    for waiver in unmatched:
        collected = sorted(
            item.name for item in request.session.items
            if (item.originalname or item.name) == waiver.function)
        if waiver.expired():
            problems.append(
                f"{waiver.test}: expired on {waiver.expires}, so it waived "
                "nothing this run -- re-negotiate it or delete it")
        elif collected:
            problems.append(
                f"{waiver.test}: the function exists but none of "
                f"params={list(waiver.params)} matched.  Collected ids: "
                f"{collected[:12]}")
        else:
            problems.append(
                f"{waiver.test}: no test of that name was collected.  A "
                "waiver is keyed by the test function's own name, so a "
                "renamed or deleted test invalidates it by design")

    assert not problems, ("the waiver table addresses things this run does "
                          "not have:\n  " + "\n  ".join(problems))

    applied = sum(len(ids) for ids in waiver_table.applied.values())
    print(f"\nwaivers: {len(waiver_table.waivers)} in "
          f"{waiver_table.path}, applied to {applied} collected tests")


def test_no_waiver_has_expired(waiver_table: WaiverTable):
    """An agreement with a date on it stops applying when that date passes.

    Separate from the gate above so the message says *expiry* rather
    than *unmatched*: an expired waiver is not applied at all (see
    conftest), so it would otherwise be reported as addressing nothing.
    """
    expired = [f"{w.test} (expired {w.expires}, agreed by {w.agreed_by})"
               for w in waiver_table.expired()]
    assert not expired, ("these waivers have lapsed and are no longer "
                         "tolerating anything:\n  " + "\n  ".join(expired))


def test_a_skip_mode_waiver_says_what_it_stops_measuring(
        waiver_table: WaiverTable):
    """``skip`` is allowed, and it has to be a deliberate, noted choice.

    A skipped test issues no requests, so it drops out of the record
    ``test_zz_controls.py`` judges and can make the endpoint-coverage
    gate fail -- correctly, because coverage is measured rather than
    assumed.  ``tolerate`` keeps the measurement and still tolerates the
    outcome, which is why it is the default and why this asks for a
    ``note`` before a test stops running at all.
    """
    silent = [w.test for w in waiver_table.waivers
              if w.mode == "skip" and not w.note]
    assert not silent, (
        "a skip-mode waiver stops the test running at all, which also "
        "stops it contributing to endpoint coverage.  Add note = \"...\" "
        f"saying why tolerate would not do: {silent}")


# ---------------------------------------------------------------------------
# the table is the only channel
# ---------------------------------------------------------------------------

def _test_modules() -> list[Path]:
    return sorted((REPO_ROOT / "tests").glob("test_*.py"))


def test_no_test_file_expects_a_failure_of_its_own():
    """No ``pytest.mark.xfail`` anywhere in the suite.

    The registry is for writing one report; the waiver table is for
    outcomes someone agreed to tolerate.  A marker in a test file is
    neither: nobody dated it, it is in one language, the report never
    mentions it, and if it quotes a defect id it is keyed to something
    that exists only while a report is being written.

    Read as a syntax tree rather than with a regex, so the examples in
    docstrings and the explanations in comments -- which are how this
    rule is taught -- do not trip it.  ``skipif`` is left alone: it is
    how the suite declines to judge a missing optional dependency, and
    ``test_ui_pages.py`` pins its one use by name.
    """
    found: dict[str, list[int]] = {}
    for path in _test_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Attribute) or node.attr != "xfail":
                continue
            # pytest.mark.xfail -- the only spelling that can reach here
            # as an expression is the marker itself.
            found.setdefault(path.name, []).append(node.lineno)

    assert not found, (
        "these files expect a failure on their own authority: "
        f"{found}.  Record it in the waiver table instead (see "
        "cbdb_desktop/waivers.py), keyed by the test function's name and "
        "the parametrisation ids it applies to.")


def test_the_registry_is_not_wired_into_any_expectation():
    """Nothing imports the registry to decide whether a test may fail.

    The registry's whole scope is "the report is generated from it".  If
    a test module imports ``DEFECTS`` it is one edit away from being an
    expectation again, which is the state this suite was deliberately
    moved out of.  ``KnownShippedDefect`` is fine and is the point: it
    is how a test says *which* failure it found.

    Two files are exempt because the registry is their subject rather
    than their authority: ``test_defect_registry.py`` checks that a
    filed entry is true and bilingual, and ``test_reports.py`` renders
    reports from it.  Neither lets a test pass that would otherwise
    fail.
    """
    allowed = {"KnownShippedDefect"}
    offenders: dict[str, list[str]] = {}
    for path in _test_modules():
        if path.name in ("test_defect_registry.py", "test_reports.py"):
            continue           # the registry is these two files' subject
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if node.module not in ("cbdb_desktop.defects", "defects"):
                continue
            names = [alias.name for alias in node.names
                     if alias.name not in allowed]
            if names:
                offenders.setdefault(path.name, []).extend(names)

    assert not offenders, (
        "these test modules import more of the registry than the one "
        f"exception they raise: {offenders}.  The registry is written to "
        "when a report is written and read by nothing else.")


# ---------------------------------------------------------------------------
# the parser, on its own
# ---------------------------------------------------------------------------

def test_a_minimal_table_parses_with_the_defaults_it_documents():
    waiver, = parse(_MINIMAL)
    assert waiver.test == "test_something"
    assert waiver.function == "test_something"
    assert waiver.module is None
    assert waiver.mode == "tolerate", "tolerate is the default: keep measuring"
    assert waiver.params == ()
    assert waiver.raises is None
    assert waiver.expires is None
    assert waiver.agreed_on == dt.date(2026, 9, 10)


def test_a_module_qualified_key_is_accepted_for_an_ambiguous_name():
    # Quoted, because TOML reads an unquoted dot as a path and would
    # make a sub-table of it -- the parser says so by name if you forget.
    waiver, = parse(_MINIMAL.replace(
        "[test_something]", '["test_exports.py::test_something"]'))
    assert waiver.module == "test_exports.py"
    assert waiver.function == "test_something"
    assert waiver.describes(module="test_exports.py",
                            function="test_something", param=None)
    assert not waiver.describes(module="test_qbe.py",
                                function="test_something", param=None)


@pytest.mark.parametrize("find,replace,expected", [
    ("[test_something]", "[not_a_test]", "not the name of a test"),
    ("[test_something]", "[test_something]\nresaon = \"typo\"",
     "fields this suite does not know"),
    ("[test_something]", "[test_something]\nmode = \"ignore\"", "mode"),
    ("[test_something]", "[test_something]\nraises = \"Exception\"", "only"),
    ("[test_something]", "[test_something]\nparams = \"entry:kml\"",
     "list of pytest"),
    ("agreed_on = 2026-09-10", "agreed_on = \"2026-09-10\"", "TOML date"),
    # A bare TOML key may hold neither a colon nor a dot, so both
    # spellings of "I forgot the quotes" have to land somewhere useful:
    # one fails as TOML, the other parses into a sub-table.
    ("[test_something]", "[test_exports.py::test_something]",
     "has to be quoted"),
    ("[test_something]", "[test_exports.test_something]",
     "has to be quoted in TOML"),
], ids=["not-a-test", "misspelled-field", "unknown-mode", "wide-raises",
        "params-not-a-list", "date-as-string", "unquoted-colon-key",
        "unquoted-dotted-key"])
def test_the_parser_refuses_what_it_cannot_honour(find, replace, expected):
    """Every malformed entry is a hard error, never a skipped line.

    Skipping an entry we do not understand silently un-waives it, and
    the resulting failure has nothing pointing back at this file.
    """
    text = _MINIMAL.replace(find, replace, 1)
    with pytest.raises(WaiverError, match=expected):
        parse(text)


def test_an_entry_missing_a_required_field_is_refused():
    for field in ("reason", "reason_zh", "agreed_by", "agreed_on"):
        text = "\n".join(line for line in _MINIMAL.splitlines()
                         if not line.startswith(field))
        with pytest.raises(WaiverError, match="missing"):
            parse(text)


def test_a_reason_in_one_language_only_is_refused():
    """Both languages, because both reports print it.

    The report exists to be read by the CBDB team in Chinese and by the
    developers in English; a waiver visible in one of them is a waiver
    half the audience cannot see.
    """
    with pytest.raises(WaiverError, match="missing"):
        parse(_MINIMAL.replace('reason_zh = "暫時同意先不處理。"',
                               'reason_zh = ""'))


def test_broken_toml_names_the_file_it_came_from(tmp_path):
    path = tmp_path / "waivers.toml"
    path.write_text("[test_x\n", encoding="utf-8")
    with pytest.raises(WaiverError, match=str(path.name)):
        load(path)


def test_the_shipped_env_example_points_at_a_usable_table():
    """``.env.example`` enables waivers, so its setting has to work.

    Two failures this exists for, and the second is the reason it reads
    the example file rather than the maintainer's own ``.env``.

    * An example that does not load.  ``CBDB_WAIVERS`` is active in
      ``.env.example`` -- the agreements are committed with the repo, so
      a fresh checkout should judge the build the way the maintainer
      does -- and a path or a table that has rotted turns every fresh
      checkout's first run into a ``UsageError``.
    * A waiver file that stops parsing.  ``waivers.toml`` is edited by
      hand, in two languages, by whoever negotiated the agreement; the
      parser refuses anything it cannot fully honour, and that refusal
      should arrive here rather than in the middle of somebody's run.

    Read through ``load_config`` rather than by parsing the file here,
    because the resolution being checked is the real one: a relative
    path against the repo root, and the process environment *not*
    consulted (``env={}``), so a maintainer whose own environment sets
    ``CBDB_WAIVERS`` still tests the example.
    """
    from cbdb_desktop.config import load_config

    configured = load_config(env={}, env_file=REPO_ROOT / ".env.example")
    assert configured.waivers_path is not None, \
        ".env.example no longer enables CBDB_WAIVERS; the docs say it does"
    assert configured.waivers_path == REPO_ROOT / "waivers.toml", \
        f"a relative path must resolve against the repo root, not the "\
        f"working directory: {configured.waivers_path}"

    table = load(configured.waivers_path)
    assert table.enabled
    for waiver in table.waivers:
        assert waiver.function.startswith("test_")
        assert not waiver.expired(), \
            f"{waiver.test} expired on {waiver.expires} and would fail " \
            "every run until it is re-negotiated or deleted"


def test_no_table_configured_means_no_waivers():
    table = load(None)
    assert not table.enabled
    assert table.waivers == ()
    assert table.matching(module="test_x.py", function="test_y",
                          param=None) is None


def test_a_configured_table_that_is_absent_is_an_error(tmp_path):
    """Set-but-missing must never read as "no waivers".

    The one outcome this feature cannot have is quietly waiving nothing
    while a run looks normal -- or quietly waiving something because a
    path pointed at the wrong file.
    """
    with pytest.raises(WaiverError, match="does not exist"):
        load(tmp_path / "nope.toml")


# ---------------------------------------------------------------------------
# matching: function name, plus the variables it ran with
# ---------------------------------------------------------------------------

def test_a_waiver_without_params_covers_every_parametrisation():
    waiver = _waiver()
    assert waiver.describes(module="test_x.py", function="test_something",
                            param=None)
    assert waiver.describes(module="test_x.py", function="test_something",
                            param="entry:kml")


def test_params_narrow_a_waiver_to_the_ids_it_names():
    waiver = _waiver(params=("entry:kml", "places:kml"))
    assert waiver.describes(module="test_x.py", function="test_something",
                            param="entry:kml")
    assert not waiver.describes(module="test_x.py", function="test_something",
                                param="office:kml")
    assert not waiver.describes(module="test_x.py", function="test_something",
                                param=None)


def test_the_more_specific_waiver_wins():
    """A table may waive two ids of a matrix and leave the rest judged.

    Both entries can address the same run of the same test, so the
    precedence has to be decided rather than left to file order:
    otherwise a blanket entry added later silently widens a narrow one.
    """
    table = WaiverTable(
        path=Path("waivers.toml"),
        waivers=(_waiver(test="test_something", note="blanket"),
                 _waiver(test="test_something", params=("entry:kml",),
                         note="narrow")))
    picked = table.matching(module="test_x.py", function="test_something",
                            param="entry:kml")
    assert picked is not None and picked.note == "narrow"


def test_expiry_is_read_against_a_date_not_the_clock():
    waiver = _waiver(expires=dt.date(2026, 12, 1))
    assert not waiver.expired(dt.date(2026, 11, 30))
    assert not waiver.expired(dt.date(2026, 12, 1)), \
        "the day it expires is still covered"
    assert waiver.expired(dt.date(2026, 12, 2))
    assert not _waiver().expired(dt.date(2099, 1, 1)), \
        "no expiry means no expiry"


def test_the_recorded_shape_carries_everything_the_report_prints():
    """``artifacts/waivers_applied.json`` is the run's own measurement.

    "How much did we agree not to look at" belongs beside the endpoint
    coverage number, readable without re-running the suite -- and it is
    what the report's waived section is rendered from.
    """
    waiver = _waiver(params=("entry:kml",), mode="skip", note="destructive",
                     expires=dt.date(2026, 12, 1),
                     raises="KnownShippedDefect")
    recorded = waiver.as_json()
    assert recorded == {
        "test": "test_something",
        "params": ["entry:kml"],
        "mode": "skip",
        "raises": "KnownShippedDefect",
        "reason": "why",
        "reason_zh": "原因",
        "agreed_by": "maintainer",
        "agreed_on": "2026-09-10",
        "expires": "2026-12-01",
        "note": "destructive",
    }


def test_a_table_is_parsed_from_the_documented_example(tmp_path):
    """The example in the module docstring has to be a working table.

    Documentation that does not parse is how a feature nobody can
    configure gets shipped.
    """
    path = tmp_path / "waivers.toml"
    path.write_text(textwrap.dedent("""
        [test_an_export_produces_a_well_formed_file]
        params    = ["entry:kml", "places:kml"]
        reason    = "Agreed 2026-09-10: the KML preamble is cosmetic for us."
        reason_zh = "2026-09-10 協商：KML 檔頭對我們的使用者只是外觀問題。"
        agreed_by = "maintainer"
        agreed_on = 2026-09-10
        expires   = 2026-12-01
        """), encoding="utf-8")

    table = load(path)
    assert table.enabled
    waiver, = table.waivers
    assert waiver.params == ("entry:kml", "places:kml")
    assert table.matching(module="test_exports.py",
                          function="test_an_export_produces_a_well_formed_file",
                          param="entry:kml") is waiver
    assert table.matching(module="test_exports.py",
                          function="test_an_export_produces_a_well_formed_file",
                          param="office:kml") is None
    assert [w.test for w in table.unmatched()] == [waiver.test], \
        "nothing has been applied yet, so it counts as unmatched"


def test_the_module_docstring_example_matches_the_parser(tmp_path):
    """Not a paraphrase of the example -- the example itself.

    Extracted from ``waivers.py``'s own docstring, so an edit to the
    documentation that breaks the format fails here rather than in
    somebody's first attempt to use it.
    """
    doc = waivers.__doc__ or ""
    block = doc.split(".. code-block:: toml", 1)[1]
    lines = []
    for raw in block.splitlines():
        if raw.strip() and not raw.startswith("    "):
            break
        lines.append(raw[4:] if raw.startswith("    ") else raw)
    text = "\n".join(lines)
    assert "[test_an_export_produces_a_well_formed_file]" in text

    waiver, = parse(text)
    assert waiver.function == "test_an_export_produces_a_well_formed_file"
    assert waiver.reason_zh, "the documented example must show both languages"

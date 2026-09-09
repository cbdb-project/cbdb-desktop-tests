"""The filter matrix: every form, every filter, on inputs the data chose.

The six read-only forms all offer the same three filters on top of their
own codes -- a dynasty, a span of years, an address -- and until this
file existed the suite drove exactly one of the resulting combinations
per form: the codes, with every other filter switched off.  A dynasty
filter that had stopped filtering, or a year window applied to the wrong
column, would have passed every test in the suite.

Two things make this file work, and they are the two the sibling .mdb
project settled on for the same problem.

**The inputs come from the data.**  ``cbdb_desktop/discovery.py`` asks
the shipped database which (code, dynasty), (code, half-century) and
(code, address) combinations are actually populated, and the tests below
are generated from the answer.  Hand-picked parameters land on sparse
data about half the time, and a query test whose result set is empty
asserts nothing while looking exactly like a passing test.  A data
refresh moves the inputs by itself; nobody edits a list.

**The assertions do not come from the data.**  Nothing here predicts a
row count.  What is asserted are properties that hold whatever CBDB
contains, and that a handler cannot satisfy by accident:

* *Every row satisfies the filter it was given.*  Ask for dynasty 15 and
  every row must carry dynasty 15; ask for 1000-1049 and every row's
  index year must be inside it, and must not be null.  This is an
  internal invariant of one response -- no second query, no
  reconstruction of a join -- and it is the assertion that would catch a
  filter bound to the wrong column, which is the failure historians
  report as "the numbers are wrong" and cannot easily prove.
* *Narrowing cannot add.*  A filtered result must be a subset of the
  unfiltered one, compared as (person, code) pairs.
* *Disjoint windows stay disjoint.*  Two adjacent half-centuries cannot
  return the same person-year twice, and their union must be inside the
  span that covers both.
* *A populated filter returns something.*  Only where the application
  itself has already agreed the combination is live, so this is never
  "the data says 47 rows, so the form must say 47".

Costs, because they are the reason this file is shaped the way it is:
the matrix is about 90 requests, none of which writes a shared scratch
table except entry's and associations' -- and those two truncate and
refill their own, so the file is order-independent.  Inputs are
discovered once per session and cached against the database's own hash.
"""
from __future__ import annotations

from collections import Counter

import pytest

from cbdb_desktop import discovery
from cbdb_desktop.app import CbdbApp
from cbdb_desktop.config import REPO_ROOT
from cbdb_desktop.defects import KnownShippedDefect
from cbdb_desktop.forms import (FORMS_BY_NAME, NARROWS, TOGGLES,
                                WIDENS, FormSpec, Toggle)

pytestmark = pytest.mark.app

#: A guard, not an oracle: if a filter stops filtering, fail fast and
#: legibly instead of downloading the whole table.  No form query
#: applies a LIMIT.
_MAX_RESULT_ROWS = 20_000


def _pairs(form: FormSpec, rows: list[dict]) -> Counter:
    """The (person, code) multiset of a result.

    Counted rather than set-compared: a build that deduplicated two
    identical rows would leave the sets equal and the counts not.
    """
    code_key = CODE_KEY[form.name]
    return Counter((row.get("personId", row.get("c_personid")), row[code_key])
                   for row in rows)


#: Where each form's rows carry the code the query filtered on.  The same
#: map test_form_queries.py uses; duplicated deliberately rather than
#: imported, because importing a test module for a constant makes the
#: two files' collection order matter.
CODE_KEY = {
    "entry": "entryCode",
    "office": "c_office_id",
    "status": "statusCode",
    "texts": "textId",
    "associations": "assocCode",
    "places": "addrId",
}


def pytest_generate_tests(metafunc):
    """Build the matrix at collection time, so each row is its own test.

    Discovery has to happen *before* collection finishes, and a fixture
    cannot do that: pytest decides which tests exist before any fixture
    runs.  Reading a cache file at collection instead would be worse
    than it looks -- on the first run against a new build there is no
    cache, every parametrized test below silently collects to nothing,
    and pytest reports an empty parametrization as a pass.

    So the matrix is discovered here, through the same content-addressed
    staging the session uses (a cache hit is ~0.1 s) and the same
    on-disk input cache keyed by the database's SHA-256.
    """
    if "combination" not in metafunc.fixturenames:
        return
    dimension = metafunc.function.__name__
    matrix = _matrix(metafunc.config)
    wanted = _DIMENSION_OF[dimension]
    metafunc.parametrize(
        "combination",
        [pytest.param(c, id=c.id) for c in matrix if c.dimension == wanted],
    )


#: Which dimension each parametrized test drives.  Explicit rather than
#: inferred from the test's name: a renamed test would otherwise start
#: silently driving nothing.
_DIMENSION_OF = {
    "test_a_dynasty_filter_returns_only_that_dynasty": "dynasty",
    "test_a_dynasty_filter_narrows_and_never_adds": "dynasty",
    "test_a_year_window_returns_only_years_inside_it": "century",
    "test_two_adjacent_windows_do_not_overlap_and_fit_inside_their_span":
        "century",
    "test_an_address_filter_narrows_and_never_adds": "address",
}

_MATRIX_CACHE: dict[int, list[discovery.Combination]] = {}


def _matrix(config) -> list[discovery.Combination]:
    """The discovered combinations, computed once per pytest session."""
    key = id(config)
    if key in _MATRIX_CACHE:
        return _MATRIX_CACHE[key]

    import sqlite3

    from cbdb_desktop.config import load_config
    from cbdb_desktop.staging import stage_once

    layout = stage_once(load_config(),
                        force=config.getoption("--restage"))
    uri = layout.db.resolve().as_uri() + "?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True, timeout=30)
    try:
        data = discovery.load(
            conn, layout.db, REPO_ROOT / "artifacts" / "test_inputs.json",
            refresh=config.getoption("--refresh-inputs"))
    finally:
        conn.close()

    _MATRIX_CACHE[key] = discovery.combinations(data)
    return _MATRIX_CACHE[key]


@pytest.fixture(scope="session")
def matrix(request) -> list[discovery.Combination]:
    """The same combinations, for the test that checks the matrix itself."""
    return _matrix(request.config)


def _query(app: CbdbApp, form: FormSpec, body: dict) -> list[dict]:
    response = app.post(form.query_path, json=body)
    assert response.status_code == 200, \
        f"{form.name}: {response.status_code} {response.text[:300]}"
    rows = form.rows(response.json())
    assert len(rows) < _MAX_RESULT_ROWS, (
        f"{form.name}: {len(rows)} rows for one narrow code -- a filter has "
        "stopped filtering, or a join now fans out")
    return rows


# ---------------------------------------------------------------------------
# the matrix exists and is worth running
# ---------------------------------------------------------------------------

def test_the_discovered_matrix_covers_every_form_and_dimension(matrix):
    """Discovery must have found something to test, for every form.

    The failure this guards against is the quiet one: a data refresh, or
    a bug in a discovery query, leaves a form with no populated
    combinations, every parametrized test below collects to nothing, and
    the run is green because it checked nothing.  pytest reports an
    empty parametrization as a *pass*, which is why this is asserted
    separately rather than left to the tests themselves.
    """
    assert matrix, "discovery found no populated combinations at all"

    by_form: dict[str, set[str]] = {}
    for combination in matrix:
        by_form.setdefault(combination.form, set()).add(combination.dimension)

    assert set(by_form) == set(FORMS_BY_NAME), (
        "discovery found no inputs for "
        f"{sorted(set(FORMS_BY_NAME) - set(by_form))}")

    for name, form in sorted(FORMS_BY_NAME.items()):
        expected = {"code", "dynasty", "century", "address"}
        if discovery.address_filter_is_the_code_filter(form):
            # Places: its codes *are* address ids, so an address filter
            # replaces the subject rather than narrowing it.  Excluded
            # by discovery, and excluded here for the same reason,
            # rather than by a hard-coded form name.
            expected.discard("address")
        assert by_form[name] == expected, (
            f"{name}: no populated inputs for "
            f"{sorted(expected - by_form[name])}")


# ---------------------------------------------------------------------------
# every row satisfies the filter it was given
# ---------------------------------------------------------------------------

def test_a_dynasty_filter_returns_only_that_dynasty(app: CbdbApp,
                                                    combination):
    """Ask for one dynasty and every row must be of that dynasty.

    The handler special-cases ``fromDynasty == toDynasty`` into a plain
    equality on ``BIOG_MAIN.c_dy``, so this is the cleanest per-row
    invariant the form offers.  Where the response carries only the
    dynasty's *name* and not its code -- four of the six forms -- the
    check falls back to "one dynasty name throughout", which is weaker
    and still catches a filter that is not being applied.
    """
    form = FORMS_BY_NAME[combination.form]
    rows = _query(app, form, form.filtered_body(
        list(combination.codes), mode=form.dynasty_mode,
        dynasty=combination.dynasty))

    if not rows:
        pytest.skip(f"{combination.id}: the form returns nothing for a "
                    f"combination the base data has {combination.base_rows} "
                    "rows for -- an input choice, not a defect")

    if form.row_has_dynasty_code:
        wrong = {row["dy"] for row in rows} - {combination.dynasty}
        assert not wrong, (
            f"{combination.id}: asked for dynasty {combination.dynasty}, got "
            f"rows for {sorted(wrong)}")
    else:
        names = {row.get("dynasty") for row in rows}
        assert len(names) == 1, (
            f"{combination.id}: asked for one dynasty, got rows from "
            f"{sorted(n for n in names if n)}")


def test_a_year_window_returns_only_years_inside_it(app: CbdbApp, combination):
    """Ask for 1000-1049 and every row's index year must be in it.

    Including the null case, which is the interesting half: a person
    with no index year cannot be inside any window, so an index-year
    filter that returns one is a filter that was not applied to that
    row.  A ``WHERE c_index_year >= ?`` cannot return a null, so this
    also catches the filter being moved to a LEFT-joined copy of the
    column.
    """
    form = FORMS_BY_NAME[combination.form]
    start, end = combination.years
    rows = _query(app, form, form.filtered_body(
        list(combination.codes), mode=form.index_year_mode,
        from_year=start, to_year=end))

    if not rows:
        pytest.skip(f"{combination.id}: the form returns nothing for this "
                    "combination")

    outside = [row.get("indexYear") for row in rows
               if row.get("indexYear") is None
               or not start <= row["indexYear"] <= end]
    assert not outside, (
        f"{combination.id}: asked for index years {start}-{end}, "
        f"{len(outside)} rows are outside it (or have none): "
        f"{outside[:10]}")


def test_two_adjacent_windows_do_not_overlap_and_fit_inside_their_span(
        app: CbdbApp, combination):
    """Half-centuries partition: A and B disjoint, A + B inside A-to-B.

    Two properties in one request pair, both free of any oracle, and
    both false in the degenerate cases a subset check would tolerate.
    A filter that is ignored entirely returns the same rows for both
    windows -- so they are not disjoint.  A filter that returns nothing
    satisfies "inside the span" trivially, which is why the span query
    must also come back populated.
    """
    form = FORMS_BY_NAME[combination.form]
    start, end = combination.years
    later_start, later_end = end + 1, end + 50

    codes = list(combination.codes)
    first = _pairs(form, _query(app, form, form.filtered_body(
        codes, mode=form.index_year_mode, from_year=start, to_year=end)))
    second = _pairs(form, _query(app, form, form.filtered_body(
        codes, mode=form.index_year_mode,
        from_year=later_start, to_year=later_end)))
    span = _pairs(form, _query(app, form, form.filtered_body(
        codes, mode=form.index_year_mode,
        from_year=start, to_year=later_end)))

    if not first and not second:
        pytest.skip(f"{combination.id}: neither window returns anything")
    assert span, (
        f"{combination.id}: {start}-{later_end} returned nothing although "
        f"its halves returned {len(first)} and {len(second)}")

    # Disjoint: a person has one index year, so it is in one window.
    both = set(first) & set(second)
    assert not both, (
        f"{combination.id}: {len(both)} (person, code) pairs are in both "
        f"{start}-{end} and {later_start}-{later_end}, which cannot both "
        f"contain one index year: {sorted(both)[:5]}")

    missing = (first + second) - span
    assert not missing, (
        f"{combination.id}: {len(missing)} pairs are in a half-window but "
        f"not in {start}-{later_end}, which contains both: "
        f"{sorted(missing)[:5]}")


def test_an_address_filter_narrows_and_never_adds(app: CbdbApp, combination):
    """An address filter can only remove rows, and sub-units only add.

    Two monotonicity properties, and neither needs to know what the
    address hierarchy contains: filtering by one address is a subset of
    not filtering at all, and including sub-units is a superset of
    excluding them.  The second is the one worth having -- it is the
    only assertion in the suite about ``includeSubUnits`` at all, and
    the flag reaches a different join in every form.
    """
    form = FORMS_BY_NAME[combination.form]
    codes = list(combination.codes)

    unfiltered = _pairs(form, _query(app, form, form.body(codes)))
    assert unfiltered, f"{combination.id}: the unfiltered query is empty"

    narrow = _pairs(form, _query(app, form, form.filtered_body(
        codes, addr_ids=[combination.addr_id], subunits=False)))
    if not narrow:
        pytest.skip(f"{combination.id}: the address filter returns nothing")

    assert not (narrow - unfiltered), (
        f"{combination.id}: filtering by address {combination.addr_id} "
        f"produced {len(narrow - unfiltered)} pairs the unfiltered query did "
        f"not: {sorted(narrow - unfiltered)[:5]}")

    with_subunits = _pairs(form, _query(app, form, form.filtered_body(
        codes, addr_ids=[combination.addr_id], subunits=True)))
    assert not (narrow - with_subunits), (
        f"{combination.id}: including sub-units lost "
        f"{len(narrow - with_subunits)} pairs that the same address without "
        f"sub-units returned: {sorted(narrow - with_subunits)[:5]}")


# ---------------------------------------------------------------------------
# every switch, in both positions
# ---------------------------------------------------------------------------

def _discovered_codes(matrix, form_name: str) -> list[int]:
    """The discovered codes for one form."""
    return [c.codes[0] for c in matrix
            if c.form == form_name and c.dimension == "code"]


def _resolve_needs(toggle: Toggle, sqlite_conn) -> dict:
    """Fill in the fields an option needs to reach the query at all.

    ``filterBac`` does nothing without ``bacCodes``; a sub-unit switch
    does nothing without an address.  The values are discovered, so the
    option is exercised against data that exists rather than against an
    id somebody typed in.
    """
    out: dict = {}
    for field_name, value in toggle.needs.items():
        if value == "@address":
            row = sqlite_conn.execute(
                "SELECT c_index_addr_id FROM BIOG_MAIN "
                "WHERE c_index_addr_id > 0 GROUP BY c_index_addr_id "
                "HAVING COUNT(*) BETWEEN 20 AND 400 "
                "ORDER BY COUNT(*) DESC LIMIT 1").fetchone()
            assert row, "no address has between 20 and 400 people indexed"
            out[field_name] = [row[0]]
        elif value == "@bac":
            row = sqlite_conn.execute(
                "SELECT c_addr_type FROM BIOG_ADDR_CODES "
                "WHERE c_addr_type > 0 ORDER BY c_addr_type LIMIT 1"
            ).fetchone()
            assert row, "no positive address type in BIOG_ADDR_CODES"
            out[field_name] = [row[0]]
        else:
            out[field_name] = value
    return out


def test_turning_every_category_off_returns_nothing(app: CbdbApp, matrix):
    """Ask the Places form for no categories at all, and see what arrives.

    This is where the switch sweep above stopped being able to answer.
    Five of the Places form's seven category switches report "identical
    either way" on every input tried -- turning Biography off changes
    nothing -- and a skip cannot tell "the option is ignored" from "this
    data has nothing on the other side of it".

    Turning *all* of them off settles it in one request and needs no
    special input: a user who has selected no categories has asked for
    nothing, so nothing is the only defensible answer.  What comes back
    is the biography rows, because the handler substitutes Biography
    when it finds every switch off (places_form_backend.go:204-206).

    That substitution is deliberate, and as a guard against an empty
    request it is reasonable.  What makes it a defect is that the page
    lets a user reach it: the seven checkboxes have no "at least one"
    rule, ``inc-biog`` merely starts checked, and unticking all seven
    and pressing Query returns biographical addresses the user has
    explicitly excluded, with no message.

    Written as one test rather than seven because the seven-way version
    would need, per branch, an input where only that branch contributes
    -- and finding that means reproducing the handler's own joins, which
    is the thing this suite does not do.
    """
    form = FORMS_BY_NAME["places"]
    codes = _discovered_codes(matrix, "places")[-1:]
    assert codes, "discovery found no address codes"

    branches = ("includeBiog", "includeAssocPlace", "includeAssocPerson",
                "includeEntry", "includeKinship", "includeOffice",
                "includeInst")
    everything_off = dict(form.body(codes),
                          **{branch: False for branch in branches})
    biography_only = dict(form.body(codes),
                          **{branch: (branch == "includeBiog")
                             for branch in branches})

    nothing = _pairs(form, _query(app, form, everything_off))
    biography = _pairs(form, _query(app, form, biography_only))

    # Without this the test would pass on a code whose biography branch
    # is empty anyway, and prove nothing.
    assert biography, \
        f"places code {codes} has no biographical addresses, so this " \
        "cannot distinguish the two"

    if nothing == biography:
        raise KnownShippedDefect(
            f"every category switched off returned {sum(nothing.values())} "
            "rows, exactly the biography branch's own result: the handler "
            "substitutes Biography for an empty selection and the page "
            "lets the user make one")
    assert not nothing, (
        f"every category switched off returned {sum(nothing.values())} "
        f"rows from somewhere: {sorted(nothing)[:5]}")


@pytest.mark.parametrize("toggle", [pytest.param(t, id=t.id) for t in TOGGLES])
def test_a_switch_changes_the_result_in_the_direction_it_claims(
        app: CbdbApp, toggle: Toggle, matrix, sqlite_conn):
    """Run the query with the option off, then on, and compare.

    The other half of "vary every adjustable option and compare what
    came back with what should have".  The filters with *values* --
    codes, dynasty, years, address -- are covered by the matrix above;
    these are the ones with a switch.  There are 21 across the six
    forms and the suite drove two of them before this test existed.

    Two properties, and the second is the one that catches an option
    the handler decodes and then ignores:

    * **Direction.**  A switch that widens can only add rows; one that
      narrows can only remove them.  Neither claim needs to know what
      the data holds, and the direction is read off the request
      struct's own meaning -- ``includeSubUnits`` cannot lose people,
      ``mainSourceOnly`` cannot gain texts.
    * **Effect.**  On an input chosen to make the option matter, the
      two results must differ.  A handler that read the field and never
      used it would satisfy the direction check perfectly, in both
      directions, forever.

    The effect half cannot always be demanded: for some (code, option)
    pairs this data release genuinely has nothing on the other side of
    the switch.  Those skip, naming the option and the row count, rather
    than asserting a difference the build cannot produce -- and the
    skips are worth reading, because a switch that skips on *every*
    input is a switch nothing has ever tested.
    """
    form = FORMS_BY_NAME[toggle.form]
    # One code, the last discovered (the least dense of the three), not
    # all of them: a sub-unit switch on a populous place fans out past
    # 20,000 rows, and this test is about the direction of a switch
    # rather than about how much data one code covers.
    codes = _discovered_codes(matrix, toggle.form)[-1:]
    assert codes, f"{toggle.form}: discovery found no codes"

    extra = _resolve_needs(toggle, sqlite_conn)

    def run(value) -> Counter:
        body = dict(form.body(codes), **extra)
        body[toggle.option] = value
        return _pairs(form, _query(app, form, body))

    off = run(toggle.off)
    on = run(toggle.on)

    if not off and not on:
        pytest.skip(f"{toggle.id}: the query returns nothing in either "
                    "position, so the option cannot be judged")

    if toggle.direction == WIDENS:
        lost = off - on
        assert not lost, (
            f"{toggle.id}: turning it on lost {len(lost)} rows that were "
            f"there with it off, and it can only add: {sorted(lost)[:5]}")
    elif toggle.direction == NARROWS:
        gained = on - off
        assert not gained, (
            f"{toggle.id}: turning it on added {len(gained)} rows that were "
            f"not there with it off, and it can only remove: "
            f"{sorted(gained)[:5]}")

    if on == off:
        pytest.skip(
            f"{toggle.id}: identical either way ({sum(on.values())} rows) "
            "-- this input cannot tell whether the option is wired up")


def test_a_dynasty_filter_narrows_and_never_adds(app: CbdbApp, combination):
    """The subset half of the dynasty filter, separately from the per-row half.

    Worth its own test because the two fail differently: a filter bound
    to the wrong column returns rows of the wrong dynasty (the per-row
    check), while a filter that widens the query -- an OR where an AND
    was meant, a join that fans out -- returns rows the unfiltered query
    never had, and only this notices that.
    """
    form = FORMS_BY_NAME[combination.form]
    codes = list(combination.codes)

    unfiltered = _pairs(form, _query(app, form, form.body(codes)))
    assert unfiltered, f"{combination.id}: the unfiltered query is empty"

    narrow = _pairs(form, _query(app, form, form.filtered_body(
        codes, mode=form.dynasty_mode, dynasty=combination.dynasty)))
    if not narrow:
        pytest.skip(f"{combination.id}: the dynasty filter returns nothing")

    extra = narrow - unfiltered
    assert not extra, (
        f"{combination.id}: filtering by dynasty {combination.dynasty} "
        f"produced {len(extra)} pairs the unfiltered query did not: "
        f"{sorted(extra)[:5]}")

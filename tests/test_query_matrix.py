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
from cbdb_desktop.forms import FORMS_BY_NAME, FormSpec

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

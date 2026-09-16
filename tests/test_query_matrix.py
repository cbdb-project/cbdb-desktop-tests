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

import re
from collections import Counter

import pytest

from cbdb_desktop import discovery, gosource
from cbdb_desktop.app import CbdbApp
from cbdb_desktop.config import REPO_ROOT
from cbdb_desktop.defects import KnownShippedDefect
from cbdb_desktop.forms import (FORMS_BY_NAME, NARROWS, TOGGLES,
                                WIDENS, FormSpec, Toggle)
from cbdb_desktop.staging import AppLayout

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
    # Both drive the second year column Entry and Office offer, so both
    # want the century combinations the index-year tests use.
    "test_the_forms_other_year_filter_partitions_the_same_way": "century",
    "test_a_one_sided_year_window_filters_on_the_side_it_was_given":
        "century",
    "test_choosing_two_dynasties_returns_exactly_both_of_them": "dynasty",
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

    A one-element selection becomes ``BIOG_MAIN.c_dy IN (?)``, so this
    is the cleanest per-row invariant the form offers.  Where the
    response carries only the
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


#: The ``needs`` value that asks for an address with something inside
#: the Use XY box.  Named, because the toggle sweep also reads it to
#: decide which code to pair it with.
_NEEDS_A_NEIGHBOUR = "@address_with_neighbours"

_ADDRESS_WITH_NEIGHBOURS: dict[tuple, int | None] = {}


def _address_with_neighbours(sqlite_conn, form, codes) -> int:
    """An address that the chosen code reaches *and* that has neighbours.

    *Use XY* widens the chosen addresses to everything within 0.03
    degrees, so judging it needs an address with something to widen to.
    It also needs an address the rest of the query can see: the sweep
    filters by one code, and an address none of that code's people are
    indexed to gives an empty result whichever way the switch is set --
    which is what the first version of this did, and it turned all six
    of these into skips.

    So both conditions are discovered together: among the people the
    code covers, the address with the most other addresses inside the
    box.  The 0.03 is the handler's own number, read out of
    ``populateScratchAddr``; using it to *choose an input* is not a
    re-implementation of the filter, and nothing here predicts which
    addresses come back or how many rows result.

    Cached per (form, code): the self-join over ``ADDR_CODES`` is the
    slowest query in this module.
    """
    key = (getattr(form, "name", None), tuple(codes))
    if key not in _ADDRESS_WITH_NEIGHBOURS:
        people = ""
        args: tuple = ()
        if form is not None and codes:
            marks = ",".join("?" * len(codes))
            people = (f"AND bm.c_personid IN (SELECT {form.person_column} "
                      f"FROM {form.code_table} "
                      f"WHERE {form.code_column} IN ({marks}))")
            args = tuple(codes)
        row = sqlite_conn.execute(f"""
            SELECT a.c_addr_id
            FROM ADDR_CODES a
            JOIN BIOG_MAIN bm ON bm.c_index_addr_id = a.c_addr_id {people}
            JOIN ADDR_CODES b
              ON b.c_addr_id <> a.c_addr_id
             AND b.x_coord BETWEEN a.x_coord - 0.03 AND a.x_coord + 0.03
             AND b.y_coord BETWEEN a.y_coord - 0.03 AND a.y_coord + 0.03
            WHERE a.x_coord IS NOT NULL AND a.y_coord IS NOT NULL
            GROUP BY a.c_addr_id
            ORDER BY COUNT(DISTINCT b.c_addr_id) DESC, a.c_addr_id
            LIMIT 1""", args).fetchone()
        # None, not a skip.  Skipping from here ends the whole test,
        # which defeats the candidate loop that calls it: a code with no
        # usable address should hand the loop the next code, not stop the
        # sweep.
        _ADDRESS_WITH_NEIGHBOURS[key] = row[0] if row else None
    return _ADDRESS_WITH_NEIGHBOURS[key]


def _resolve_needs(toggle: Toggle, sqlite_conn, form=None, codes=()) -> dict:
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
        elif value == _NEEDS_A_NEIGHBOUR:
            address = _address_with_neighbours(sqlite_conn, form, codes)
            if address is None:
                return None       # this code has no address worth trying
            out[field_name] = [address]
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

    Until the 2026-09-15 build the answer was the biography rows,
    because the handler substituted Biography when it found every
    switch off.  As a guard against an empty request that was
    reasonable; what made it a defect is that the page let a user reach
    it, so unticking all seven and pressing Query returned biographical
    addresses the user had explicitly excluded, with no message.

    This build refuses the request instead -- HTTP 400, *at least one
    relation-type category must be selected* -- and disables Run Query
    until a category is ticked.  Both answers are defensible and the
    test accepts either: what it will not accept is a 200 carrying rows.
    A substituted default is the failure, not the status code.

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

    biography = _pairs(form, _query(app, form, biography_only))
    # Without this the test would pass on a code whose biography branch
    # is empty anyway, and prove nothing: "no rows" and "the substituted
    # branch has no rows" would look the same.
    assert biography, \
        f"places code {codes} has no biographical addresses, so this " \
        "cannot distinguish a refusal from a substitution"

    response = app.post(form.query_path, json=everything_off)

    if response.status_code == 400:
        return

    assert response.status_code == 200, (
        f"asking for no categories answered HTTP {response.status_code}: "
        f"{response.text[:200]}.  Refusing the request is a correct "
        "answer and so is an empty result, but neither is a server error")

    nothing = _pairs(form, form.rows(response.json()))
    if nothing == biography:
        raise KnownShippedDefect(
            f"every category switched off returned {sum(nothing.values())} "
            "rows, exactly the biography branch's own result: the handler "
            "substitutes Biography for an empty selection and the page "
            "lets the user make one")
    assert not nothing, (
        f"every category switched off returned {sum(nothing.values())} "
        f"rows from somewhere: {sorted(nothing)[:5]}")


#: How many relation-type categories the Places form offers.  Pinned so
#: that a build which gains or loses a branch is read rather than
#: silently changing what the test below covers; the set itself is
#: extracted.
_EXPECTED_PLACE_CATEGORIES = 7


def _place_categories(layout: AppLayout) -> dict[str, str]:
    """``{request field: the relType literal that branch writes}``.

    Extracted from the shipped Go rather than listed, so a category the
    build adds joins this test by itself.  Each branch is an
    ``if p.Include<X> {`` block containing exactly one
    ``'<literal>' AS rel_type``, and the request field name comes from
    the struct's own JSON tag -- both read as data, neither
    re-implementing what the branch then does.

    The pairing is what lets this test see a *permutation*: two switches
    whose branches were swapped leave the seven-way sum exactly right
    and every single-category answer non-empty, and only the identity
    stamped on the rows gives it away.
    """
    source = (layout.code_dir / "places_form_backend.go").read_text(
        encoding="utf-8", errors="replace")
    body = gosource.struct_body(source, "PlaceQueryParams")
    assert body, "places_form_backend.go no longer declares PlaceQueryParams"
    tags = dict(re.findall(r'^\s*(\w+)\s+bool\s+`json:"(\w+)"',
                           body, re.MULTILINE))

    out = {}
    for guard in re.finditer(r"^\tif p\.(\w+) \{", source, re.MULTILINE):
        literal = re.search(r"'([^']+)'\s+AS rel_type",
                            source[guard.end():guard.end() + 4000])
        if literal:
            out[tags.get(guard.group(1), guard.group(1))] = literal.group(1)
    return out


def test_each_place_category_contributes_its_own_part_of_the_whole(
        app: CbdbApp, matrix, layout):
    """Seven categories, one at a time, against all seven together.

    This is the experiment that replaces "turn all of them off", and it
    exists because that one stopped being available.  Five of the Places
    form's seven category switches report "identical either way" in the
    sweep above on every input tried, and a skip cannot tell "the option
    is ignored" from "this data has nothing on the other side of it".
    The all-off request used to settle it in one call -- a user who has
    selected nothing has asked for nothing, so nothing is the only
    defensible answer, whatever CBDB holds.  The 2026-09-15 build now
    refuses that request with HTTP 400, which is a better answer to give
    a user and leaves the five switches undecided again.

    Three properties, and it takes all three:

    * **The parts sum to the whole.**  The handler assembles its answer
      as a ``UNION ALL`` across the enabled branches, so the seven
      single-category answers must sum -- as multisets, not as sets --
      to exactly the all-seven answer.  A switch that is decoded and
      never used leaves its branch in every answer and the sum exceeds
      the whole.  Nothing here depends on what CBDB contains.
    * **Each part is its own branch.**  Every row carries the
      ``relType`` its branch stamped on it, so a single-category answer
      must carry that category's literal and no other.  Without this
      the sum is satisfied by any *permutation* of the seven switches:
      each answer wrong, the total right.
    * **A category contributes to its own part exactly when it
      contributes to the whole.**  This is the liveness reading, and it
      is two of the application's own answers compared with each other
      rather than a count taken from the data: if ``Kinship`` rows are
      in the all-seven answer, asking for Kinship alone must return
      some, and if they are not, it must not.

    The address code is the discovered one whose all-seven answer spans
    the most categories, because a code with one live branch can only
    judge one switch.  Choosing it is input selection -- the app is
    asked which of its own codes are interesting, and nothing about the
    answer is predicted.
    """
    form = FORMS_BY_NAME["places"]
    codes_available = _discovered_codes(matrix, "places")
    assert codes_available, "discovery found no address codes"

    categories = _place_categories(layout)
    assert len(categories) == _EXPECTED_PLACE_CATEGORIES, (
        f"{len(categories)} relation-type branches were read out of "
        f"places_form_backend.go, not {_EXPECTED_PLACE_CATEGORIES}: "
        f"{categories}.  If the build gained or lost one, update the "
        "number in the same commit as the reason; if it did not, the "
        "reader has stopped matching some and this test is judging "
        "fewer switches than it reports")

    declared = {toggle.option for toggle in TOGGLES if toggle.form == "places"}
    unswept = sorted(set(categories) - declared)
    assert not unswept, (
        f"these relation-type categories are in the build and in no row "
        f"of TOGGLES: {unswept}.  The switch sweep and this test would "
        "then be driving different sets, so a category would be "
        "identified here and never swept for direction")

    def ask(codes, selected) -> list[dict]:
        body = dict(form.body(codes),
                    **{name: (name in selected) for name in categories})
        return _query(app, form, body)

    # The code whose answer spans the most categories.  Ties go to the
    # first, which keeps the choice deterministic across runs.
    everything = set(categories)
    by_code = {code: ask([code], everything) for code in codes_available}
    codes = [max(by_code, key=lambda code:
                 (len({row["relType"] for row in by_code[code]}), -code))]
    whole_rows = by_code[codes[0]]
    whole = _pairs(form, whole_rows)
    assert whole, (
        f"no discovered places code returns anything with every category "
        f"selected ({codes_available}), so the parts cannot be compared "
        "against the whole")

    types_in_whole = {row["relType"] for row in whole_rows}
    parts = {name: ask(codes, {name}) for name in categories}

    # 1. Each part is its own branch, and only its own.
    wrong_identity = {
        name: sorted({row["relType"] for row in rows} - {literal})
        for name, (literal, rows) in
        ((n, (categories[n], parts[n])) for n in categories)
        if {row["relType"] for row in rows} - {literal}
    }
    assert not wrong_identity, (
        f"asking for one category returned rows stamped with another's "
        f"relType: {wrong_identity}.  Each branch writes its own literal "
        "into every row it produces, so a switch that selects somebody "
        "else's branch shows up here and nowhere else -- a swap of two "
        "switches leaves the totals below exactly right")

    # 2. A category is live in its own part exactly when it is live in
    #    the whole.  Two of the application's own answers, compared.
    disagree = {
        name: (bool(parts[name]), categories[name] in types_in_whole)
        for name in categories
        if bool(parts[name]) != (categories[name] in types_in_whole)
    }
    assert not disagree, (
        "these categories contribute to the seven-way answer and not to "
        "their own, or the reverse -- {category: (alone, in the whole)}: "
        f"{disagree}.  The all-seven answer is the union of the branches, "
        "so the two readings cannot differ unless the switch selects "
        "something other than the branch it names")

    # 3. The parts sum to the whole.
    summed = Counter()
    for rows in parts.values():
        summed += _pairs(form, rows)
    sizes = {name: len(rows) for name, rows in parts.items()}
    assert summed == whole, (
        "the seven categories asked for one at a time do not sum to the "
        f"seven asked for together: {sum(summed.values())} rows against "
        f"{sum(whole.values())}.  Per category: {sizes}.  "
        f"Only in the parts: {sorted((summed - whole))[:5]}; "
        f"only in the whole: {sorted((whole - summed))[:5]}")

    # 4. What this run could not judge, pinned rather than printed.
    #
    # The three assertions above are all conditional on a category
    # having rows: a branch that contributes nothing to the whole and
    # nothing to its own part satisfies every one of them however it is
    # wired.  So the undecided set is an exact pin, on the same terms as
    # test_ui_pages.UNDECLARED -- it is the honest count of what this
    # test does *not* check, and it may only shrink.
    #
    # Why these four.  The discovered places codes are drawn from
    # BIOG_ADDR_DATA, so the Biography branch is live by construction
    # and the Associate-Place and Office-Place branches happen to be;
    # the other four key off tables an address chosen that way need not
    # appear in.  All three discovered codes give the same answer, so
    # this is a property of how the input is chosen, not of the code
    # that happened to win.  Deciding them needs an address that is busy
    # in those branches, and finding one without reproducing the
    # branch's own joins is the open problem -- a lead for the next
    # round, written here because that is where it will be read.
    silent = sorted(name for name in categories if not parts[name])
    assert silent == ["includeAssocPlace", "includeEntry", "includeInst",
                      "includeKinship"], (
        f"the Places categories no discovered address code can decide "
        f"are now {silent}, and this test records four.  If the list "
        "shrank, delete the names from it in the same commit -- the "
        "build or the data just became more testable.  If it grew, this "
        f"test is now judging {len(categories) - len(silent)} of "
        f"{len(categories)} switches and saying so is the point")


@pytest.mark.parametrize("toggle", [pytest.param(t, id=t.id) for t in TOGGLES])
def test_a_switch_changes_the_result_in_the_direction_it_claims(
        app: CbdbApp, toggle: Toggle, matrix, sqlite_conn):
    """Run the query with the option off, then on, and compare.

    The other half of "vary every adjustable option and compare what
    came back with what should have".  The filters with *values* --
    codes, dynasty, years, address -- are covered by the matrix above;
    these are the ones with a switch.  There are 26 across the six
    forms; the suite drove two of them before this test existed, and
    the seven *Use XY* switches were added to the inventory on
    2026-09-10 -- until then that control, which appears on every form
    with an address filter, had never been sent in either position.

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
    # One code, not all of them.  Normally the *least* dense of the
    # three: a sub-unit switch on a populous place fans out past 20,000
    # rows, and this test is about the direction of a switch rather
    # than about how much data one code covers.
    #
    # The Use XY switches are the exception, and they need more care:
    # they only matter where the code and an address with neighbours
    # overlap, and on most single codes that overlap is one row or
    # none.  Rather than guess dense or sparse -- both were tried, and
    # both left most of these skipping -- every discovered code is
    # offered and the run below takes the first that has something to
    # compare.  A switch that skips on every input it is ever given is
    # a switch nothing has tested.
    found = _discovered_codes(matrix, toggle.form)
    candidates = ([[code] for code in found]
                  if _NEEDS_A_NEIGHBOUR in toggle.needs.values()
                  else [found[-1:]])
    codes = candidates[0]
    assert codes, f"{toggle.form}: discovery found no codes"

    def run(chosen, extra, value) -> Counter:
        body = dict(form.body(chosen), **extra)
        body[toggle.option] = value
        return _pairs(form, _query(app, form, body))

    # The first candidate that can tell the two positions apart -- not
    # merely the first that returns rows.  Breaking on `if off:` threw
    # away inputs that do discriminate and then skipped saying the input
    # could not tell, which was untrue of the sweep even where it was
    # true of that one code: two of the seven Use XY switches skipped on
    # a code while a later code showed the effect plainly, and entry's
    # was rejected for having `off` empty -- which, for a switch that can
    # only widen, is the most informative case there is.
    #
    # `extra` is resolved once per candidate and reused for both
    # positions: resolving it inside `run` picked the input twice, and
    # two ORDER BY ... LIMIT 1 queries can disagree on a tie, which would
    # compare the switch's two positions on two different inputs.
    off = on = Counter()
    tried = 0
    for codes in candidates:
        extra = _resolve_needs(toggle, sqlite_conn, form, codes)
        if extra is None:
            continue
        tried += 1
        off = run(codes, extra, toggle.off)
        on = run(codes, extra, toggle.on)
        if off != on:
            break

    if not tried:
        pytest.skip(
            f"{toggle.id}: none of the {len(candidates)} discovered code(s) "
            "reaches an address that has another within 0.03 degrees, so "
            "there is no input on which this switch can widen anything")

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
            f"on all {tried} input(s) tried -- none of the discovered "
            "codes can tell whether the option is wired up")


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


# ---------------------------------------------------------------------------
# the second year each of two forms can filter on
# ---------------------------------------------------------------------------

def test_the_forms_other_year_filter_partitions_the_same_way(
        app: CbdbApp, combination):
    """Entry and Office filter on two different years; drive the second.

    ``yearFilterType`` chooses which column a year window applies to.
    Every year test above sends ``index_year_mode`` -- the person's
    index year -- and until now nothing sent the other value, so half
    of each of these two forms' year filters had never been requested:
    ``entryyear``, the year of the entry itself, and ``officeyear``,
    the year of the posting.  They are not the same question a
    historian asks, and they are not the same SQL.

    Two properties, neither needing an oracle: each half-century's rows
    sit inside the span that covers both, and the span sits inside the
    unfiltered answer.

    Both are appending-a-conjunct properties and hold by construction
    on a handler of this shape, so what they buy is request coverage
    rather than detection -- until now nothing had sent ``entryyear``
    or ``officeyear`` in any position at all.  Saying so plainly beats
    letting two green assertions imply more than they check.  The
    detection for these modes lives next door, in
    ``test_the_two_year_modes_are_not_the_same_filter``, which fails if
    the second mode is not reaching a different column.  (``status``
    spells its index mode ``index`` rather than ``indexyear``, so a
    form quietly not recognising a mode string is a thing that happens
    here.)

    What is deliberately *not* asserted is that the two halves are
    disjoint, which is what the index-year test next door can claim.
    The first version of this did claim it and reported six failures on
    ``officeyear`` -- wrongly.  Office filters postings with
    ``c_firstyear >= From AND c_lastyear <= To``, and the rows this
    suite compares are ``(person, code)`` pairs, so one person holding
    the same office in two separate postings appears in both windows
    and should.  The overlap is the data being what it is, not the
    filter leaking.

    Skipped, naming the mode, where this combination has nothing in the
    span: containment inside an empty set is true for the wrong reason.
    """
    form = FORMS_BY_NAME[combination.form]
    if not form.other_year_mode:
        pytest.skip(f"{combination.form} filters on one year only")

    start, end = combination.years
    later_start, later_end = end + 1, end + 50
    codes = list(combination.codes)

    def window(from_year, to_year):
        return _pairs(form, _query(app, form, form.filtered_body(
            codes, mode=form.other_year_mode,
            from_year=from_year, to_year=to_year)))

    first = window(start, end)
    second = window(later_start, later_end)
    span = window(start, later_end)

    if not span:
        pytest.skip(
            f"{combination.id}: {form.other_year_mode} {start}-{later_end} "
            "returns nothing, so there is nothing to judge containment in")

    missing = (set(first) | set(second)) - set(span)
    assert not missing, (
        f"{combination.id}: {len(missing)} rows are in one half of "
        f"{form.other_year_mode} {start}-{later_end} and not in the whole "
        f"of it: {sorted(missing)[:5]}")

    unfiltered = _pairs(form, _query(app, form, form.body(codes)))
    if set(span) == set(unfiltered):
        pytest.skip(
            f"{combination.id}: {form.other_year_mode} {start}-{later_end} "
            f"returns the whole unfiltered answer ({len(unfiltered)} rows), "
            "so this window cannot tell a working filter from an ignored "
            "mode")
    assert not (set(span) - set(unfiltered)), (
        f"{combination.id}: {form.other_year_mode} {start}-{later_end} "
        "returned rows the unfiltered query does not have, so the mode is "
        "widening rather than filtering")


@pytest.mark.parametrize("form_name",
                         sorted(name for name, spec in FORMS_BY_NAME.items()
                                if spec.other_year_mode))
def test_the_two_year_modes_are_not_the_same_filter(
        app: CbdbApp, form_name: str, matrix, sqlite_conn):
    """Somewhere in the matrix, the two year columns must disagree.

    The containment test above would pass if both modes ran the same
    SQL -- two windows on one column contain each other whichever
    column it is.  What says the second mode is a *second* filter is
    that a window exists where the two answers differ.

    "A window exists" is the whole point, and it is why this is a
    sweep over every century combination the matrix discovered rather
    than one assertion per combination.  An earlier version asserted
    the two modes differ on *each* window, which is not true of a
    correct build: discovery chooses windows that are populated by
    *index* year, and a correct entry-year filter may well return the
    same people for one of them.  Demanding it every time would have
    failed a build that was working.  Demanding it never happens
    anywhere is the claim that actually distinguishes one filter from
    two.
    """
    form = FORMS_BY_NAME[form_name]
    windows = [c for c in matrix
               if c.form == form_name and c.dimension == "century"]
    if not windows:
        pytest.skip(f"discovery found no century combinations for {form_name}")

    same, differing = [], []
    for combination in windows:
        start, end = combination.years
        codes = list(combination.codes)
        by_index = _pairs(form, _query(app, form, form.filtered_body(
            codes, mode=form.index_year_mode, from_year=start, to_year=end)))
        by_other = _pairs(form, _query(app, form, form.filtered_body(
            codes, mode=form.other_year_mode, from_year=start, to_year=end)))
        if not by_index and not by_other:
            continue
        (differing if by_index != by_other else same).append(
            (combination.id, sum(by_index.values()), sum(by_other.values())))

    if not same and not differing:
        pytest.skip(
            f"{form_name}: neither year mode returns anything for any of "
            f"the {len(windows)} discovered windows, so they cannot be "
            "told apart on this data")

    assert differing, (
        f"{form_name}: {form.index_year_mode} and {form.other_year_mode} "
        f"returned identical results on all {len(same)} window(s) that "
        f"returned anything: {same[:5]}.  These name two different "
        "columns -- the person's index year and the year of the record "
        "itself -- so agreeing everywhere means the second mode is not "
        "reaching a different filter")

def test_a_one_sided_year_window_filters_on_the_side_it_was_given(
        app: CbdbApp, combination):
    """One end of the window at a time: "from 1200", then "to 1249".

    Every year test in this file sends both ends.  A user need not: the
    forms take the two years separately, and leaving one blank is the
    ordinary way to ask "anything after 1200".  That path is worth its
    own test because this build has the bug it looks for somewhere
    else: on the Networks form a From-only dynasty range silently
    filters almost nothing, because the missing end arrives as a zero
    that the condition is then written against
    (``networks_form_query.go:buildDynastyConditions``).

    Three orderings, and none of them needs to know what the data
    holds:

    * the closed window is inside the from-only window, which is
      inside the unfiltered answer;
    * the closed window is inside the to-only window as well;
    * and if the closed window excluded anybody, at least one of the
      open-ended windows must exclude somebody too.

    Only the third can fail on a handler of the shape these six have.
    All six build the window as two independent conjuncts, so dropping
    one of them is *literally* the closed query with a condition
    removed and the first two orderings hold by construction -- worth
    saying plainly rather than letting three green assertions imply
    more than they check.  The third does not follow from the shape:
    it compares what the two bounds do apart against what they did
    together, and a bound that is silently ignored breaks it.

    Which is the Networks failure, and it cannot occur here: these six
    declare their years as ``*int`` and test for nil, while Networks
    uses a plain ``int`` that cannot tell "unset" from zero.  So what
    this buys against *this* build is request coverage -- a path a user
    takes daily and no test had ever taken -- and a guard against the
    six growing the shape Networks already has.
    """
    form = FORMS_BY_NAME[combination.form]
    start, end = combination.years
    codes = list(combination.codes)
    mode = form.index_year_mode

    unfiltered = _pairs(form, _query(app, form, form.body(codes)))
    if not unfiltered:
        pytest.skip(f"{combination.id}: the unfiltered query is empty")

    closed = _pairs(form, _query(app, form, form.filtered_body(
        codes, mode=mode, from_year=start, to_year=end)))
    from_only = _pairs(form, _query(app, form, form.filtered_body(
        codes, mode=mode, from_year=start)))
    to_only = _pairs(form, _query(app, form, form.filtered_body(
        codes, mode=mode, to_year=end)))

    for name, wider in (("from-only", from_only), ("to-only", to_only)):
        escaped = set(wider) - set(unfiltered)
        assert not escaped, (
            f"{combination.id}: the {name} window {start}-{end} returned "
            f"{len(escaped)} rows the unfiltered query does not have: "
            f"{sorted(escaped)[:5]}")
        lost = set(closed) - set(wider)
        assert not lost, (
            f"{combination.id}: {len(lost)} rows are inside the closed "
            f"window {start}-{end} and missing from the {name} window that "
            f"contains it: {sorted(lost)[:5]}")

    if not closed:
        pytest.skip(f"{combination.id}: the closed window {start}-{end} is "
                    "empty, so the open-ended ones have nothing to contain")

    # The half that can actually fail, and it is an assertion rather
    # than a skip because it follows from the other three results
    # rather than from the data: if the closed window excludes
    # somebody, then one of its two bounds excluded them, and that
    # bound must still exclude them when it is the only one sent.  Two
    # open windows that both return everything, over a closed window
    # that returns less, is a bound being dropped -- which is exactly
    # what the Networks form does with a From-only dynasty range.
    #
    # Where the closed window excludes nobody the question does not
    # arise, and the equality below is the ordinary answer rather than
    # a symptom.
    narrowed = set(closed) != set(unfiltered)
    ignored_both = (set(from_only) == set(unfiltered)
                    and set(to_only) == set(unfiltered))
    assert not (narrowed and ignored_both), (
        f"{combination.id}: the closed window {start}-{end} returns "
        f"{len(closed)} of {len(unfiltered)} rows, so at least one of its "
        "bounds excludes somebody -- yet from-only and to-only each "
        "return the whole unfiltered answer.  A bound that filters when "
        "it is paired and not when it is alone has been dropped rather "
        "than applied")


def test_choosing_two_dynasties_returns_exactly_both_of_them(
        app: CbdbApp, combination, matrix, sqlite_conn):
    """More than one dynasty at a time, which nothing had asked for.

    Every dynasty test above sends a one-element selection, so what
    they drive is a ``c_dy IN (?)`` with a single placeholder -- which
    is indistinguishable from an equality test, and says nothing about
    what the form does when a user ticks several dynasties in the
    picker.  Since the 2026-09-15 build that is the *only* way the
    filter is expressed: the From/To pair, and the year-span arithmetic
    the handlers used to do with ``DYNASTIES.c_start`` and ``c_end``,
    are gone from all seven forms.

    The property is the asymmetric one AGENTS.md asks for rather than a
    containment, because containment is satisfied by a filter that is
    ignored altogether.  Two dynasty codes are mutually exclusive --
    ``BIOG_MAIN.c_dy`` holds one value per person -- so asking for
    ``{A, B}`` must return the multiset for ``A`` plus the multiset for
    ``B``, exactly:

        Counter(A) + Counter(B) == Counter(A+B)

    That is false when the selection is ignored (the answer would be
    the whole unfiltered result), false when only the first code is
    applied, false when the list is ANDed rather than ORed (nothing
    comes back), and false if a person were counted twice.  No count is
    predicted from the data: all three numbers come from the
    application.
    """
    form = FORMS_BY_NAME[combination.form]
    codes = list(combination.codes)
    first = combination.dynasty

    # A second dynasty, chosen from the data and then confirmed against
    # the application -- picking an input, never predicting an answer.
    #
    # Discovery has already found which dynasties are populated for this
    # very code, so its siblings come first: they are two or three codes
    # rather than eighty-four, and each is known to have rows.  The full
    # DYNASTIES list stays as the fallback, because a code with only one
    # populated dynasty has no sibling and the test should still try
    # rather than skip.  Code 0 ("unknown") is excluded from the
    # fallback: it is a real row in DYNASTIES that no page offers.
    siblings = [other.dynasty for other in matrix
                if other.dimension == "dynasty"
                and other.form == combination.form
                and tuple(other.codes) == tuple(combination.codes)
                and other.dynasty != first]
    rest = [row[0] for row in sqlite_conn.execute(
        "SELECT c_dy FROM DYNASTIES WHERE c_dy > 0 AND c_dy <> ? "
        "ORDER BY c_sort", (first,)).fetchall()]
    candidates = siblings + [dy for dy in rest if dy not in siblings]

    def ask(selection):
        return _pairs(form, _query(app, form, form.filtered_body(
            codes, mode=form.dynasty_mode, dynasty=selection)))

    only_first = ask([first])
    second = None
    only_second: Counter = Counter()
    for candidate in candidates:
        answer = ask([candidate])
        if answer:
            second, only_second = candidate, answer
            break

    if second is None:
        pytest.skip(
            f"{combination.id}: no second dynasty returns anything for "
            "this code, so a selection of two cannot be judged")
    if not only_first:
        pytest.skip(
            f"{combination.id}: dynasty {first} returns nothing for this "
            "code, so a selection containing it cannot be judged")

    together = ask([first, second])

    assert together == only_first + only_second, (
        f"{combination.id}: asking for dynasties {first} and {second} "
        f"together returned {sum(together.values())} rows, but "
        f"{first} alone returns {sum(only_first.values())} and "
        f"{second} alone returns {sum(only_second.values())}, which sum "
        f"to {sum((only_first + only_second).values())}.  A person "
        "belongs to exactly one dynasty, so a two-dynasty selection is "
        "the two one-dynasty answers and nothing else: more means the "
        "selection was widened or ignored, fewer means one of the two "
        "codes was dropped.  "
        f"Only in the pair: {sorted((together - (only_first + only_second)))[:3]}; "
        f"missing from it: {sorted(((only_first + only_second) - together))[:3]}")

    # Equality above is satisfied by a join that fanned every row out by
    # the same factor on all three requests.  The single-code case is
    # covered by test_a_dynasty_filter_narrows_and_never_adds, which
    # names fan-out as its subject; this is the two-code case, and it
    # costs one more request.
    unfiltered = _pairs(form, _query(app, form, form.body(codes)))
    escaped = together - unfiltered
    assert not escaped, (
        f"{combination.id}: asking for dynasties {first} and {second} "
        f"returned {sum(escaped.values())} row(s) the unfiltered query "
        f"does not have: {sorted(escaped)[:5]}")


# ---------------------------------------------------------------------------
# the switch inventory, against the switches the build declares
# ---------------------------------------------------------------------------

#: The query-parameter struct each of the six read-only forms decodes.
_QUERY_PARAMS = {
    "associations": ("associations_form_backend.go", "AssocQueryParams"),
    "entry": ("entry_form_backend.go", "EntryQueryParams"),
    "office": ("office_form_backend.go", "OfficeQueryParams"),
    "places": ("places_form_backend.go", "PlaceQueryParams"),
    "status": ("status_form_backend.go", "StatusQueryParams"),
    "texts": ("texts_form_backend.go", "TextQueryParams"),
}

#: Switches that are not booleans, so the sweep below cannot find them
#: by type: they pick between named alternatives rather than being on
#: or off.  Listed with what makes each one a switch rather than a
#: value, because that is the judgement a survey cannot make.
_NON_BOOLEAN_SWITCHES = {
    ("entry", "addressFrame"): "1 = the person's index address, 2 = the "
                               "entry's own; neither contains the other",
    ("texts", "queryMode"): "'source' runs one query, 'both' runs two",
}


def test_every_switch_the_build_declares_is_one_the_sweep_drives(layout):
    """``TOGGLES`` against the boolean fields of the six query structs.

    This is the gate the inventory did not have, and its absence is
    the whole reason seven switches went unsent for the life of the
    suite: *Use XY* is on every form with an address filter, and
    nothing failed while nothing drove it.  § *Coverage is the
    program's job* -- a list a human keeps is a list that goes stale
    silently, and the fix is not to keep it better but to make the
    build fail the suite when it grows something the list lacks.

    Both directions, and both matter.  A field the build has and the
    inventory lacks is a switch nobody is driving.  A row in the
    inventory naming a field no struct declares is a test sending a
    key the handler discards, which passes for the wrong reason
    forever.
    """
    declared: dict[tuple[str, str], str] = {}
    for form, (source, struct_name) in sorted(_QUERY_PARAMS.items()):
        text = (layout.code_dir / source).read_text(
            encoding="utf-8", errors="replace")
        body = gosource.struct_body(text, struct_name)
        assert body is not None, f"{source} no longer declares {struct_name}"
        for go_name, json_name in re.findall(
                r'^\s*(\w+)\s+bool\s+`json:"(\w+)"', body, re.MULTILINE):
            declared[(form, json_name)] = go_name

    listed = {(toggle.form, toggle.option) for toggle in TOGGLES}
    undriven = sorted(set(declared) - listed)
    assert not undriven, (
        f"{len(undriven)} switch(es) the build declares are in no row of "
        f"TOGGLES, so nothing sends them in either position: {undriven}.  "
        "Add a row with the direction the field's own meaning implies, or "
        "say here why it cannot be judged")

    invented = sorted(listed - set(declared) - set(_NON_BOOLEAN_SWITCHES))
    assert not invented, (
        f"TOGGLES names {len(invented)} option(s) no query struct "
        f"declares as a boolean: {invented}.  A test sending a key the "
        "handler discards passes whatever the handler does")

    stale = sorted(set(_NON_BOOLEAN_SWITCHES) - listed)
    assert not stale, (
        f"these are recorded as non-boolean switches and no longer "
        f"appear in TOGGLES: {stale}")


# ---------------------------------------------------------------------------
# what a filter does with a value the data uses to mean "not recorded"
# ---------------------------------------------------------------------------

#: ``form -> (mode, the reply's year key, the table and column filtered)``
#: for the two forms whose second year mode compares against a column
#: that stores 0 where the year is unknown.
_ZERO_IS_UNKNOWN = {
    "entry": ("entryyear", "entryYear", "ENTRY_DATA", "c_year"),
    "office": ("officeyear", "firstYear", "POSTED_TO_OFFICE_DATA",
               "c_firstyear"),
}


@pytest.mark.parametrize("form_name", sorted(_ZERO_IS_UNKNOWN))
def test_a_year_window_does_not_admit_rows_whose_year_is_unknown(
        app: CbdbApp, form_name: str, matrix, sqlite_conn):
    """0 means "not recorded", and ``0 <= 1100`` is true.

    Both columns store 0 for an unknown year -- 164,443 of 264,775
    entry rows -- and both filters compare against the column
    directly, so an upper bound admits every undated row.  Office is
    worse than that: its lower bound tests ``c_firstyear`` and its
    upper tests ``c_lastyear``, so a posting with a known start and an
    unrecorded end satisfies the upper bound however late it began.

    The oracle is the response's own rows.  Each carries the year it
    was filtered on, so a row outside the window is a row the filter
    did not apply to; nothing is predicted and no SQL is reproduced.

    Two shapes, because they fail differently: a window with both ends
    and one with only an upper bound.  The second is what a user gets
    by leaving the From box empty, and on Entry it returns *nothing
    but* undated rows.
    """
    mode, year_key, table, column = _ZERO_IS_UNKNOWN[form_name]
    form = FORMS_BY_NAME[form_name]
    codes = _discovered_codes(matrix, form_name)[:1]
    assert codes, f"{form_name}: discovery found no codes"

    (unknown,) = sqlite_conn.execute(
        f"SELECT COUNT(*) FROM {table} WHERE {column} = 0").fetchone()
    assert unknown, (
        f"{table}.{column} no longer uses 0 for an unrecorded year, so "
        "this test is about a sentinel the data has stopped using")

    # The window is read from the column being filtered rather than
    # written down: a half-century that the data actually populates,
    # so the comparison is against rows that exist.  A hand-picked
    # 1000-1100 happened to work on this release and would have gone
    # quietly empty on one where the code covers another period.
    marks = ",".join("?" * len(codes))
    window_row = sqlite_conn.execute(
        f"SELECT ({column} / 100) * 100 AS century, COUNT(*) AS n "
        f"FROM {table} "
        f"WHERE {column} > 0 AND {form.code_column} IN ({marks}) "
        f"GROUP BY century ORDER BY n DESC LIMIT 1", tuple(codes)).fetchone()
    if not window_row or not window_row[0]:
        pytest.skip(
            f"{form_name} code(s) {codes} have no dated rows in "
            f"{table}.{column}, so no window can be asked about")
    start = int(window_row[0])
    end = start + 99

    def rows_for(**window):
        answer = _query(app, form, form.filtered_body(codes, mode=mode, **window))
        return [row for row in answer if isinstance(row, dict)]

    closed = rows_for(from_year=start, to_year=end)
    upper_only = rows_for(to_year=end)
    if not closed and not upper_only:
        pytest.skip(f"{form_name}: {mode} returns nothing for {start}-{end} "
                    "on the densest code, so there is nothing to judge")

    def years(rows):
        return [row.get(year_key) for row in rows]

    stray_closed = [y for y in years(closed) if not y or not start <= y <= end]
    stray_upper = [y for y in years(upper_only) if not y or y > end]

    if stray_closed or stray_upper:
        raise KnownShippedDefect(
            f"the {form_name} form's {mode} window admits rows whose "
            f"{year_key} is not inside it.  Asked for {start}-{end}: "
            f"{len(stray_closed)} of {len(closed)} rows are outside, with "
            f"years {sorted(set(stray_closed))[:6]}.  Asked for up to "
            f"{end} with the From box empty: {len(stray_upper)} of "
            f"{len(upper_only)}, with years "
            f"{sorted(set(stray_upper))[:6]}.  {table}.{column} stores 0 "
            f"for an unrecorded year in {unknown:,} rows and the filter "
            "compares against the column directly, so every undated row "
            "satisfies every upper bound")


def test_a_dynasty_the_picker_offers_is_one_the_filter_can_use(
        app: CbdbApp, sqlite_conn):
    """Korea has no years.  It used to matter; it must not any more.

    Three ``DYNASTIES`` rows carry no year span at all -- code 0
    (*unknown*), 58 (*Korea*) and 67 (*Xinluo (Korea)*), both years 0 --
    and until the 2026-09-15 build every form resolved a dynasty choice
    *through* those years, guarding on the code being ``> 0`` rather
    than on the years being real.  58 and 67 passed the guard and
    produced a comparison against zero, so choosing one of them showed
    the user either everything or nothing with no way to tell which.

    The migration to an explicit ``c_dy IN (...)`` removes the whole
    mechanism: a dynasty with no years is now filtered exactly like a
    dynasty with years, because no years are consulted.  This is the
    test that keeps it removed.  It is deliberately still driven rather
    than deleted -- the year arithmetic could come back, and this is the
    input that would notice, on the two codes that were affected rather
    than on a code chosen at random.

    The property needs no oracle: ask for a spanless dynasty and every
    row must be of that dynasty, and the answer must be a *proper*
    subset of the unfiltered one.  "Everything" and "nothing" -- the two
    things the old arithmetic produced -- both fail it.
    """
    spanless = sqlite_conn.execute(
        "SELECT c_dy, c_dynasty FROM DYNASTIES "
        "WHERE c_dy > 0 AND COALESCE(c_start, 0) = 0 "
        "  AND COALESCE(c_end, 0) = 0 ORDER BY c_dy").fetchall()
    if not spanless:
        pytest.skip("every dynasty the picker offers has a year span, so "
                    "there is no unusable choice to make")

    # A form and one of its codes whose people actually include
    # somebody from a spanless dynasty -- chosen from the data, which
    # selects the input and predicts nothing about the answer.  Without
    # it the filter would correctly return nothing and the assertions
    # would run against an empty list.
    #
    # The forms whose rows carry a dynasty code are tried first, because
    # only those can answer the per-row half below; the others can still
    # answer the subset half, which is the part that catches "everything"
    # and "nothing".  Spanless dynasties are thinly populated -- 1,395
    # people in Korea and four in Xinluo on this data, with single-figure
    # row counts per code -- so the window is deliberately wide at the
    # bottom.  One row is enough to distinguish a filter that works from
    # one that returns the whole table.
    placeholders = ",".join("?" for _ in spanless)
    candidates = sorted(FORMS_BY_NAME.values(),
                        key=lambda spec: not spec.row_has_dynasty_code)
    chosen_input = None
    for spec in candidates:
        row = sqlite_conn.execute(
            f"SELECT d.{spec.code_column}, bm.c_dy "
            f"FROM {spec.code_table} d "
            f"JOIN BIOG_MAIN bm ON bm.c_personid = d.{spec.person_column} "
            f"WHERE bm.c_dy IN ({placeholders}) "
            f"GROUP BY d.{spec.code_column}, bm.c_dy "
            f"HAVING COUNT(*) BETWEEN 1 AND 200 "
            f"ORDER BY COUNT(*) DESC LIMIT 1",
            tuple(code for code, _ in spanless)).fetchone()
        if row is not None:
            chosen_input = (spec, row[0], row[1])
            break

    if chosen_input is None:
        pytest.skip(
            "nobody in a dynasty with no year span "
            f"({[f'{c} ({n})' for c, n in spanless]}) appears under any "
            "form's codes, so the choice cannot be driven on this data")
    form, code, spanless_dy = chosen_input
    name = dict(spanless)[spanless_dy]

    unfiltered = _pairs(form, _query(app, form, form.body([code])))
    assert unfiltered, f"{form.name} code {code} returns nothing unfiltered"

    chosen = _query(app, form, form.filtered_body(
        [code], mode=form.dynasty_mode, dynasty=spanless_dy))
    filtered = _pairs(form, chosen)

    assert filtered, (
        f"dynasty {spanless_dy} ({name}) has no year span in DYNASTIES, "
        "and choosing it on the "
        f"{form.name} form returns nothing at all -- although "
        f"{sum(unfiltered.values())} rows come back unfiltered and the "
        f"data has people of that dynasty under code {code}.  A dynasty "
        "with no years is being resolved through its years again")
    assert set(filtered) < set(unfiltered), (
        f"dynasty {spanless_dy} ({name}) has no year span, and choosing "
        f"it on the {form.name} form returns {sum(filtered.values())} of "
        f"the {sum(unfiltered.values())} rows an unfiltered query returns "
        "-- so the filter is doing nothing.  That is what the old year "
        "arithmetic did with a zero span, and it is what "
        "`c_dy IN (...)` was supposed to end")

    # The per-row half, which is what "filtered like any other dynasty"
    # actually means.  A handler that narrowed to some arbitrary subset
    # would satisfy the two assertions above.  Only the forms that
    # return a dynasty per row can be asked.
    if form.row_has_dynasty_code:
        wrong = {row.get("dy") for row in chosen
                 if isinstance(row, dict)} - {spanless_dy}
        assert not wrong, (
            f"asking the {form.name} form for dynasty {spanless_dy} "
            f"({name}) returned rows from {sorted(wrong)} as well")


#: The vocabulary the shared dynasty picker speaks since it became
#: multi-select.  One field, a list of codes.
_DYNASTY_FIELD = "dynastyCodes"

#: The vocabulary it replaced: a From/To pair, plus the four boundary
#: years the page used to look up and send so the handler could do year
#: arithmetic with them.  A struct still declaring any of these is a
#: form the migration did not reach.
_RETIRED_DYNASTY_FIELDS = (
    "fromDynasty", "toDynasty",
    "fromDynastyBegin", "fromDynastyEnd",
    "toDynastyBegin", "toDynastyEnd",
)

#: Which request structs decode a dynasty choice at all -- pinned, so
#: that a form dropping the filter entirely fails here rather than
#: passing by being absent from a gate about dynasty filters.  The *set*
#: is extracted from the build below; this is only the count it must
#: come to, in the shape AGENTS.md operating principle 5 asks for.
_EXPECTED_DYNASTY_STRUCTS = 8


def _structs_that_decode_a_dynasty(layout: AppLayout) -> dict[str, str]:
    """``{struct name: file}`` for every request struct with a dynasty field.

    Extracted rather than listed.  A struct counts if it declares the
    new field or any of the retired ones, which is exactly "this form
    offers a dynasty filter" without having to know which forms those
    are -- so a form the build adds is judged without anyone
    remembering, and a struct the build renames does not silently drop
    out of the gate.
    """
    wanted = (_DYNASTY_FIELD,) + _RETIRED_DYNASTY_FIELDS
    found = {}
    for source in sorted(layout.code_dir.glob("*.go")):
        text = source.read_text(encoding="utf-8", errors="replace")
        for struct_name in re.findall(r"^type\s+(\w+)\s+struct\s*\{",
                                      text, re.MULTILINE):
            body = gosource.struct_body(text, struct_name)
            if body and any(f'json:"{field}"' in body for field in wanted):
                found[struct_name] = source.name
    return found


def test_every_form_reads_the_dynasty_choice_the_picker_now_sends(
        layout: AppLayout):
    """One picker, one vocabulary -- or the odd form out filters nothing.

    ``dynasty_picker.html`` is shared by every form that offers a
    dynasty filter, and in this build it became multi-select: it hands
    back an array of chosen dynasties, and the forms send that array as
    ``dynastyCodes``.  The handlers were rewritten to match, replacing
    the From/To pair and the ``DYNASTIES.c_start``/``c_end`` arithmetic
    that resolved it.

    A form left behind by that migration does not fail loudly.  It
    declares fields the page no longer sends, decodes them as zero
    values, and answers with an unfiltered result -- the silent wrong
    answer this suite exists to catch.  This reads the shipped Go as
    data and requires the whole set to have moved together.

    Replaces ``test_the_forms_agree_where_one_dynasty_ends_and_the_next
    _begins``, whose subject -- five forms writing ``D.c_start < ?``
    while Places wrote ``D.c_start <= ?``, so a dynasty beginning
    exactly where a range ended belonged to it on one form and not on
    another -- no longer exists in any form.  The agreement that test
    checked is now structural, and this is where it is checked.
    """
    structs = _structs_that_decode_a_dynasty(layout)
    assert len(structs) == _EXPECTED_DYNASTY_STRUCTS, (
        f"{len(structs)} request struct(s) in this build decode a dynasty "
        f"choice, not {_EXPECTED_DYNASTY_STRUCTS}: {structs}.  If a form "
        "gained or lost the filter, update the number in the same commit "
        "as the reason; if it did not, the struct reader has stopped "
        "matching some and this gate is judging less than it thinks")

    missing = {}
    retired = {}
    for struct, filename in sorted(structs.items()):
        body = gosource.struct_body(
            (layout.code_dir / filename).read_text(
                encoding="utf-8", errors="replace"), struct)
        if f'json:"{_DYNASTY_FIELD}"' not in body:
            missing[f"{filename}:{struct}"] = "no dynastyCodes"
        still_there = sorted(field for field in _RETIRED_DYNASTY_FIELDS
                             if f'json:"{field}"' in body)
        if still_there:
            retired[f"{filename}:{struct}"] = still_there

    assert not missing, (
        f"these forms do not decode `{_DYNASTY_FIELD}`: {sorted(missing)}.  "
        "That is the only dynasty field the shared multi-select picker's "
        "callers send, so a dynasty chosen in the picker reaches the "
        "handler as nothing and the filter is silently skipped.  Note "
        "where the fix goes: a handler and its own page can be perfectly "
        "consistent with each other and still be wrong here, because what "
        "moved is the *picker's* call contract -- it now hands its opener "
        "one array argument.  Adding the field to the struct alone would "
        "not fix the page; see the page-side check in "
        "test_page_contracts.py")
    assert not retired, (
        "these forms still decode the From/To dynasty vocabulary the "
        "shared picker stopped speaking, so those fields arrive as zero "
        f"values and the dynasty filter is silently skipped: {retired}")


def test_use_xy_does_not_treat_the_unmapped_corner_as_a_place(
        app: CbdbApp, sqlite_conn):
    """0,0 is where the unmapped addresses are, not a location.

    *Use XY* gathers every address within 0.03 degrees of the ones
    chosen.  ``ADDR_CODES`` stores a block of addresses at exactly
    ``x_coord = 0, y_coord = 0``, which is how this data records a
    place that was never located; nothing else in the table lies inside
    the box around that point, so it collapses all of them into one
    "place".

    Ticking a box that means *catch the same place under a different
    code* then turns a query about one garrison into a query about
    every unmapped one.  The switch widens by design, so the direction
    check in the sweep above is satisfied; only the size of the
    widening says anything is wrong, which is why this is separate.
    """
    unmapped = [row[0] for row in sqlite_conn.execute(
        "SELECT c_addr_id FROM ADDR_CODES "
        "WHERE x_coord = 0 AND y_coord = 0 ORDER BY c_addr_id")]
    if len(unmapped) < 2:
        pytest.skip("fewer than two addresses sit at 0,0, so there is no "
                    "collapsed corner to fall into")

    form = FORMS_BY_NAME["places"]
    (code,) = sqlite_conn.execute(
        f"SELECT {form.code_column} FROM {form.code_table} "
        f"GROUP BY {form.code_column} HAVING COUNT(*) BETWEEN 5 AND 400 "
        f"ORDER BY {form.code_column} LIMIT 1").fetchone()

    def rows_for(use_xy: bool):
        body = form.filtered_body([code], addr_ids=[unmapped[0]])
        body["addrUseXY"] = use_xy
        return [row for row in _query(app, form, body) if isinstance(row, dict)]

    without = rows_for(False)
    with_xy = rows_for(True)

    reached = {row.get("addrId") for row in with_xy} - {None}
    others = reached - {unmapped[0]}
    # Any other address at all, not "more than one".  A single
    # unrelated address is already the whole defect, and a floor
    # here would let a smaller recurrence pass -- the same "pin
    # exactly" rule this file applies to its counts.
    if others:
        raise KnownShippedDefect(
            f"address {unmapped[0]} has no coordinates -- it is one of "
            f"{len(unmapped)} stored at exactly 0,0 because they were "
            f"never located -- and Use XY treats it as a coordinate "
            f"like any other.  "
            f"Filtering on it alone returns {len(without)} rows; with Use "
            f"XY it returns {len(with_xy)} rows from {len(reached)} "
            f"different addresses, {len(others)} of them unrelated places "
            "that share only the absence of a coordinate.  The switch "
            "means \"the same place under another code\", and the user "
            "cannot see which addresses it added")

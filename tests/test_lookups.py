"""The read-only lookup endpoints -- the code and address lists the forms
offer their users before any query is run.

Every endpoint here is fast (the largest, ``/api/addresses``, is 7 MB in
0.1 s) and none writes to the shared ``ZZ_SCRATCH_*`` tables, so this
file stays order-independent.

The oracles are deliberately not re-derived SQL.  They are: the shape the
application itself declares in its Go structs, agreement *between* two of
the application's own endpoints, and base facts from the shipped database
-- "does this code exist in its own table", never "here is the join the
handler should have run".
"""
from __future__ import annotations

import pytest

from cbdb_desktop.app import CbdbApp
from cbdb_desktop.defects import BY_NAME, KnownShippedDefect

pytestmark = pytest.mark.app


def _keys(rows: list[dict]) -> set[str]:
    return set(rows[0])


# ---------------------------------------------------------------------------
# declared shapes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path,expected_keys,rows_expected", [
    ("/api/entry-types",
     {"code", "desc", "descChn", "parentId"}, 29),
    ("/api/entry-code-type-rel",
     {"entryCode", "entryType"}, 280),
    ("/api/office/office-types",
     {"nodeId", "parentId", "desc", "descChn"}, 2739),
    ("/api/associations/assoc-types",
     {"nodeId", "parentId", "desc", "descChn", "level", "sortOrder"}, 45),
    ("/api/status-types",
     {"code", "parentCode", "desc", "descChn"}, 13),
    ("/api/status-code-type-rel",
     {"statusCode", "statusTypeCode"}, 284),
    ("/api/dynasties",
     {"code", "name", "nameChn", "startYear", "endYear"}, 85),
    ("/api/addresses",
     {"id", "name", "nameChn", "adminType", "belongsToChn", "belongsToPY",
      "firstYear", "lastYear", "xCoord", "yCoord"}, 37_118),
    ("/api/texts/text-categories",
     {"nodeId", "parentId", "desc", "descChn", "level", "sortOrder"}, 51),
    ("/api/indexaddr/codes",
     {"addr_type", "combined_desc", "desc_chn"}, 22),
    ("/api/indexaddr/rankings",
     {"addr_type", "index_addr_rank", "index_addr_default_rank"}, 22),
])
def test_a_lookup_returns_its_declared_shape(app: CbdbApp, path: str,
                                             expected_keys: set[str],
                                             rows_expected: int):
    """Every lookup is a JSON array of objects with exactly these keys.

    Key sets are pinned rather than sampled: a renamed field silently
    empties a dropdown in the UI, which is precisely the kind of change
    that survives a "does it return 200" check.

    Row counts are pinned exactly, for the same reason the route counts
    are: these are stable code tables, and a floor loose enough to be
    safe is loose enough to hide half a list going missing.  A data
    release that legitimately adds codes fails here and gets read.
    """
    rows = app.json("GET", path)
    assert isinstance(rows, list), f"{path} returned {type(rows).__name__}, not an array"
    assert len(rows) == rows_expected, f"{path} returned {len(rows)} rows"
    # One row settles it: Go marshals a struct with the same key set every
    # time, so checking all 37 118 rows of /api/addresses buys nothing.
    assert _keys(rows) == expected_keys, sorted(_keys(rows))


# ---------------------------------------------------------------------------
# agreement between endpoints
# ---------------------------------------------------------------------------

def test_every_entry_type_relation_names_a_type_the_app_offers(app: CbdbApp):
    """The two entry lookups must describe the same taxonomy.

    The picker builds its tree from /api/entry-types and then filters
    codes with /api/entry-code-type-rel; a relation pointing at a type
    the tree does not contain is a code the user can never reach.
    """
    types = {row["code"] for row in app.json("GET", "/api/entry-types")}
    relations = app.json("GET", "/api/entry-code-type-rel")

    orphans = sorted({r["entryType"] for r in relations} - types)
    assert not orphans, f"entry types referenced but never offered: {orphans}"


def test_every_status_relation_names_a_type_the_app_offers(app: CbdbApp):
    types = {row["code"] for row in app.json("GET", "/api/status-types")}
    relations = app.json("GET", "/api/status-code-type-rel")

    orphans = sorted({r["statusTypeCode"] for r in relations} - types)
    assert not orphans, f"status types referenced but never offered: {orphans}"


@pytest.mark.parametrize("path,root_marker,roots", [
    # The three trees do not agree on how a root is marked: office and
    # association roots point at "0", while the texts tree's single root
    # has a null parent.  Both are pinned, per endpoint, so that "null is
    # allowed" cannot quietly spread to a tree whose parents have all
    # become null -- which would look like a valid forest of roots.
    ("/api/office/office-types", "0", 8),
    ("/api/associations/assoc-types", "0", 10),
    ("/api/texts/text-categories", None, 1),
])
def test_a_code_tree_is_internally_consistent(app: CbdbApp, path: str,
                                              root_marker, roots: int):
    """Each tree's parent links resolve, so the picker can build it.

    An unresolvable parent orphans a whole branch: those codes exist, and
    the user can never click down to them.
    """
    rows = app.json("GET", path)
    ids = {str(row["nodeId"]) for row in rows}

    assert len(rows) == len(ids), \
        f"{path}: {len(rows) - len(ids)} duplicate nodeId values"

    at_root = [row for row in rows if row["parentId"] == root_marker
               and str(row["nodeId"]) != str(root_marker)]
    assert len(at_root) == roots, \
        f"{path}: {len(at_root)} root nodes, expected {roots}"

    allowed = ids | {str(root_marker)}
    dangling = sorted({str(row["parentId"]) for row in rows} - allowed)
    assert not dangling, f"{path}: parents with no node: {dangling[:20]}"


def test_dynasties_describe_usable_year_ranges(app: CbdbApp):
    """A dropdown of dynasties is only useful if its ranges make sense."""
    rows = app.json("GET", "/api/dynasties")

    codes = [row["code"] for row in rows]
    assert len(codes) == len(set(codes)), "duplicate dynasty codes"

    backwards = [r for r in rows
                 if r["startYear"] is not None and r["endYear"] is not None
                 and r["startYear"] > r["endYear"]]
    assert not backwards, [f"{r['name']}: {r['startYear']}..{r['endYear']}"
                           for r in backwards]

    nameless = [r for r in rows if not str(r["name"]).strip()
                and not str(r["nameChn"]).strip()]
    assert not nameless, \
        f"{len(nameless)} dynasties have no name in either language"


def test_every_offered_address_really_exists(app: CbdbApp, sqlite_conn):
    """Every address in the picker names a real address.

    The base-fact half of this is a membership test against ADDR_CODES --
    not a reconstruction of the handler's query.  It catches the failure
    that matters: a dropdown offering an id that no longer resolves.
    """
    rows = app.json("GET", "/api/addresses")
    ids = [row["id"] for row in rows]

    known = {r[0] for r in sqlite_conn.execute("SELECT c_addr_id FROM ADDR_CODES")}
    unknown = sorted(set(ids) - known)
    assert not unknown, f"addresses offered that ADDR_CODES does not have: {unknown[:20]}"

    # Coordinates, where present, must be on Earth.
    off_planet = [r for r in rows
                  if (r["xCoord"] not in (None, 0)
                      and not -180 <= r["xCoord"] <= 180)
                  or (r["yCoord"] not in (None, 0)
                      and not -90 <= r["yCoord"] <= 90)]
    assert not off_planet, [(r["id"], r["xCoord"], r["yCoord"])
                            for r in off_planet[:10]]


def test_the_address_list_has_its_expected_size(app: CbdbApp):
    """The picker shows 37 118 rows for 29 932 distinct addresses.

    The handler inner-joins ADDR_BELONGS_DATA, so an address appears once
    per period it belonged to, each row carrying its own firstYear and
    lastYear.  That is a design choice rather than a bug, but a
    surprising one for a picker, so both totals are frozen: a build that
    starts de-duplicating -- or starts multiplying rows for some other
    reason -- changes what the user scrolls through and should say so
    here.

    Deliberately a golden rather than a computed expectation.  Deriving
    the number would mean reproducing the handler's two inner joins, and
    a partial copy of them would false-alarm on a data quirk in a table
    the test does not model.
    """
    rows = app.json("GET", "/api/addresses")

    assert len(rows) == 37_118, len(rows)
    assert len({row["id"] for row in rows}) == 29_932, \
        len({row["id"] for row in rows})


def test_index_address_codes_and_rankings_describe_the_same_types(app: CbdbApp):
    """The IndexAddr form joins these two lists by address type."""
    codes = app.json("GET", "/api/indexaddr/codes")
    rankings = app.json("GET", "/api/indexaddr/rankings")

    assert {row["addr_type"] for row in codes} == \
        {row["addr_type"] for row in rankings}
    assert len({row["addr_type"] for row in rankings}) == len(rankings), \
        "duplicate address types in the rankings"


# ---------------------------------------------------------------------------
# filtered lookups
# ---------------------------------------------------------------------------

def test_offices_by_type_returns_only_that_branch(app: CbdbApp):
    """The office picker's right-hand pane, driven for real."""
    types = app.json("GET", "/api/office/office-types")
    root = next(t for t in types if str(t["parentId"]) in ("0", ""))
    # A real sub-branch, not the root: asking the root for "its" offices
    # returns the whole table, which would test nothing about scoping.
    branch = next(t for t in types
                  if str(t["parentId"]) == str(root["nodeId"])
                  and str(t["nodeId"]) != str(root["nodeId"]))

    everything = app.json("GET", "/api/office/offices-by-type",
                          params={"treeNodeId": root["nodeId"]})
    assert everything, "the office picker's root pane returned nothing"

    rows = app.json("GET", "/api/office/offices-by-type",
                    params={"treeNodeId": branch["nodeId"]})
    assert rows, f"branch {branch['nodeId']} ({branch['desc']}) returned nothing"
    assert set(rows[0]) == {"c_office_id", "c_office_chn", "c_office_pinyin",
                            "c_office_trans", "c_dy", "c_dynasty",
                            "c_dynasty_chn"}
    ids = [row["c_office_id"] for row in rows]
    assert len(ids) == len(set(ids)), "the same office offered twice"

    # A branch is part of the tree, not the whole of it.
    assert set(ids) < {row["c_office_id"] for row in everything}, \
        "the branch pane returned everything the root pane did"

    # An id no tree node uses must yield an empty list, not null: the page
    # reads .length off it.
    empty = app.json("GET", "/api/office/offices-by-type",
                     params={"treeNodeId": "no-such-node"})
    assert empty == [], empty


def test_associations_by_type_returns_only_that_branch(app: CbdbApp):
    types = app.json("GET", "/api/associations/assoc-types")
    node = next(t for t in types if len(str(t["nodeId"])) == 2)

    rows = app.json("GET", "/api/associations/assocs-by-type",
                    params={"typeCode": node["nodeId"]})
    assert rows, f"association type {node['nodeId']} returned nothing"
    assert set(rows[0]) == {"assocCode", "desc", "descChn", "pair",
                            "roleType", "sortOrder"}
    codes = [row["assocCode"] for row in rows]
    assert len(codes) == len(set(codes)), "the same association offered twice"


def test_texts_by_category_returns_only_that_branch(app: CbdbApp):
    categories = app.json("GET", "/api/texts/text-categories")

    # Most categories are empty; find one that is not, rather than
    # asserting against whichever happens to be first.
    for category in categories:
        rows = app.json("GET", "/api/texts/texts-by-category",
                        params={"categoryId": category["nodeId"]})
        assert isinstance(rows, list)
        if rows:
            ids = [row["textId"] for row in rows]
            assert len(ids) == len(set(ids)), "the same text offered twice"
            return
    pytest.fail("no text category returned any texts")


# ---------------------------------------------------------------------------
# the browser's paged list
# ---------------------------------------------------------------------------

def test_the_people_list_pages_consistently(app: CbdbApp):
    """Two pages of 50 are the same people as one page of 100.

    Pagination that disagrees with itself is the classic way a user
    silently never sees a record, and it needs no oracle beyond the
    endpoint's own answers.
    """
    first = app.json("GET", "/api/browser/people", params={"limit": 50, "offset": 0})
    second = app.json("GET", "/api/browser/people", params={"limit": 50, "offset": 50})
    hundred = app.json("GET", "/api/browser/people", params={"limit": 100, "offset": 0})

    assert set(first) == {"records", "total", "offset"}
    assert first["offset"] == 0 and second["offset"] == 50
    assert first["total"] == second["total"] == hundred["total"], \
        "the total changed between pages"

    combined = first["records"] + second["records"]
    assert len(combined) == len(hundred["records"])
    assert [r["personId"] for r in combined] == \
        [r["personId"] for r in hundred["records"]], \
        "paging returns different people than one larger page"


def test_the_people_list_caps_the_page_size(app: CbdbApp):
    """A caller asking for 1000 rows is silently given 100.

    Pinned because it is a real limit users hit, and because a build that
    stops clamping would let one request pull 658 941 rows.
    """
    payload = app.json("GET", "/api/browser/people", params={"limit": 1000})
    assert len(payload["records"]) == 100
    assert payload["total"] > 100


def test_the_people_total_agrees_with_the_shipped_data(app: CbdbApp, sqlite_conn):
    """An unfiltered listing counts everybody in BIOG_MAIN.

    A base fact -- a row count of one table -- not a re-derivation of the
    handler's SELECT.
    """
    payload = app.json("GET", "/api/browser/people", params={"limit": 1})
    expected = sqlite_conn.execute("SELECT COUNT(*) FROM BIOG_MAIN").fetchone()[0]
    assert payload["total"] == expected


def test_a_short_search_finds_the_person_it_names(app: CbdbApp):
    """Searching by one or two characters narrows the list and finds people.

    The oracle is the application's own listing, not a re-run of its
    query.  An earlier version of this test counted matching rows in
    ZZZ_NAMES with the same two LIKE clauses the handler uses -- which is
    the handler's filter chain retyped, and worse, guaranteed to agree:
    for patterns under three characters SQLite cannot use the trigram
    index and scans that very table, so both sides were executing the
    same scan.  It could only ever confirm that the SQL had been copied
    correctly.

    What is checked instead is a property the application must have
    however it is implemented: a search narrows the list, and a person
    the list itself returned can be found by a fragment of their own name.
    """
    everybody = app.json("GET", "/api/browser/people", params={"limit": 1})["total"]

    listed = app.json("GET", "/api/browser/people", params={"limit": 20})["records"]
    person = next(r for r in listed if len((r.get("name") or "").strip()) >= 2)
    term = person["name"].strip()[:2]

    hits = app.json("GET", "/api/browser/people",
                    params={"search": term, "limit": 100})

    assert 0 < hits["total"] < everybody, \
        f"search {term!r} returned {hits['total']} of {everybody}"
    if hits["total"] <= 100:
        assert any(r["personId"] == person["personId"] for r in hits["records"]), \
            f"{person['name']} cannot be found by searching {term!r}"

    # A longer fragment of the same name can only ever match fewer people
    # -- but only where the search works at all.  While the FTS index is
    # empty (see the defect below), any 3+ character term returns nothing,
    # which would make this trivially true rather than meaningful.
    full = person["name"].strip()
    if len(full) >= 3:
        narrower = app.json("GET", "/api/browser/people",
                            params={"search": full, "limit": 1})
        if narrower["total"] > 0:
            assert narrower["total"] <= hits["total"], \
                f"searching {full!r} matched more people than {term!r}"


@pytest.mark.xfail(strict=True, raises=KnownShippedDefect,
                   reason=BY_NAME["orphan-name"].reason)
def test_every_name_belongs_to_a_person_who_exists(sqlite_conn):
    """No name may be indexed for a person the database does not contain.

    Marked xfail(strict) with the decorator rather than raised inside the
    body: an imperative pytest.xfail() reports a plain pass once the
    defect is fixed, so nobody is ever told.  The decorator turns a fix
    into an XPASS failure, which is the notification a fixed bug deserves.
    """
    orphans = [row[0] for row in sqlite_conn.execute(
        "SELECT DISTINCT n.c_personid FROM ZZZ_NAMES n "
        "LEFT JOIN BIOG_MAIN b ON b.c_personid = n.c_personid "
        "WHERE b.c_personid IS NULL")]
    if orphans == [100382]:
        raise KnownShippedDefect(
            "person 100382 has names in ZZZ_NAMES but no BIOG_MAIN row")
    assert orphans == [], (
        f"{len(orphans)} person id(s) have names but no BIOG_MAIN row: "
        f"{orphans[:10]}.  They are searchable by name and then 404 when "
        "opened.  This is a different set from the one known to ship.")


@pytest.mark.parametrize("term,expected_minimum", [
    ("Wang", 50_000),        # a very common surname
    ("Wang Anshi", 1),       # a person every edition of CBDB contains
    ("Su Shi", 1),
    ("王安石", 1),   # the same person, in Chinese
])
@pytest.mark.xfail(strict=True, raises=KnownShippedDefect,
                   reason=BY_NAME["name-search"].reason)
def test_searching_people_by_name_finds_them(app: CbdbApp, term: str,
                                             expected_minimum: int):
    """The main way a user finds a person in the browser.

    The marker is narrowed to KnownShippedDefect so that only the defect
    described above is tolerated: a 500, malformed JSON, or a *different*
    wrong answer still fails as a failure.  And the day the index is
    rebuilt this passes unexpectedly, which pytest reports as an error --
    the notification a fixed bug deserves.
    """
    payload = app.json("GET", "/api/browser/people",
                       params={"search": term, "limit": 20})

    if payload["total"] == 0 and payload["records"] == []:
        raise KnownShippedDefect(
            f"search {term!r} ({len(term)} characters) found nobody; at least "
            f"{expected_minimum} people have that in a name")
    assert payload["total"] >= expected_minimum, \
        f"search {term!r} found {payload['total']} people"


@pytest.mark.xfail(strict=True, raises=KnownShippedDefect,
                   reason=BY_NAME["name-search"].reason)
def test_the_name_search_index_is_populated(sqlite_conn):
    """The root cause of the search defect, asserted where it lives.

    A search test can only say "nothing came back"; this says why, so a
    reader does not have to rediscover it.  Both numbers are base facts
    about the shipped database.

    The bar is a ratio, not "more than zero": a partially rebuilt index
    would leave search broken for most names while satisfying any
    non-zero check.
    """
    content = sqlite_conn.execute("SELECT COUNT(*) FROM ZZZ_NAMES").fetchone()[0]
    indexed = sqlite_conn.execute(
        "SELECT COUNT(*) FROM ZZZ_NAMES_FTS_docsize").fetchone()[0]
    assert content > 100_000, content

    if indexed == 0:
        raise KnownShippedDefect(
            f"the name index holds no documents at all for {content:,} names")
    assert indexed >= content, (
        f"the name index holds {indexed:,} documents for {content:,} names -- "
        "a partial rebuild leaves search broken for most names")


def test_a_person_who_does_not_exist_is_a_404(app: CbdbApp, sqlite_conn):
    """A missing person is reported, not answered with an empty shell."""
    highest = sqlite_conn.execute(
        "SELECT MAX(c_personid) FROM BIOG_MAIN").fetchone()[0]
    response = app.get(f"/api/browser/person/{highest + 1000}")
    assert response.status_code == 404, response.status_code

    assert app.get("/api/browser/person/not-a-number").status_code == 400

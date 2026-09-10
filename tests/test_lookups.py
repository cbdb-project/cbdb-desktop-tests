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
     {"entryCode", "entryType"}, 284),
    ("/api/office/office-types",
     {"nodeId", "parentId", "desc", "descChn"}, 2742),
    ("/api/associations/assoc-types",
     {"nodeId", "parentId", "desc", "descChn", "level", "sortOrder"}, 45),
    ("/api/status-types",
     {"code", "parentCode", "desc", "descChn"}, 14),
    ("/api/status-code-type-rel",
     {"statusCode", "statusTypeCode"}, 285),
    ("/api/dynasties",
     {"code", "name", "nameChn", "startYear", "endYear"}, 85),
    ("/api/addresses",
     {"id", "name", "nameChn", "adminType", "belongsToChn", "belongsToPY",
      "firstYear", "lastYear", "xCoord", "yCoord"}, 37_118),
    ("/api/texts/text-categories",
     {"nodeId", "parentId", "desc", "descChn", "level", "sortOrder"}, 51),
    # 20, not 22: the two BIOG_ADDR_CODES rows that are not real choices
    # ("[Missing Data]" = -1 and "unknown" = 0) are excluded server-side
    # as of the 2026-09-07 build.  See
    # test_the_dropdown_offers_only_address_types_that_can_be_ranked.
    ("/api/indexaddr/codes",
     {"addr_type", "combined_desc", "desc_chn"}, 20),
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
    ("/api/office/office-types", "0", 11),
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


def test_the_dropdown_offers_only_address_types_that_can_be_ranked(
        app: CbdbApp, sqlite_conn):
    """The IndexAddr form joins these two lists by address type.

    They are deliberately no longer the same list.  ``/codes`` fills the
    nine priority dropdowns and ``/rankings`` says which type currently
    sits in each; ``BIOG_ADDR_CODES`` also holds two rows that are not
    real choices -- "[Missing Data]" (-1) and "unknown" (0) -- and the
    2026-09-07 build stopped offering them, because a non-positive code
    arriving in an update request is now treated as "no selection"
    (``buildCleanRanks``).  Offering a value the backend is contractually
    obliged to discard is what installed the bogus rank: a ranking
    arriving with a non-positive code in a slot, which the backend then
    treated as "no selection".

    So what has to hold is an inclusion in each direction, not equality:
    every offered type has a ranking row (or its dropdown could not show
    a rank), and every *ranked* type is offered (or the page would show a
    rank the user cannot see the name of, and cannot re-select after
    changing it).
    """
    codes = app.json("GET", "/api/indexaddr/codes")
    rankings = app.json("GET", "/api/indexaddr/rankings")

    offered = {row["addr_type"] for row in codes}
    described = {row["addr_type"] for row in rankings}
    assert len(described) == len(rankings), \
        "duplicate address types in the rankings"

    assert offered <= described, \
        f"types offered in the dropdown with no ranking row: " \
        f"{sorted(offered - described)}"

    # 1..9 is the ranked range; 100 is "not ranked" (indexAddrRankings
    # Handler's own comment), and the page only reads 1..9.
    ranked = {row["addr_type"] for row in rankings
              if 1 <= row["index_addr_rank"] <= 9}
    assert ranked, "no address type is ranked at all"
    assert ranked <= offered, (
        f"address types are ranked but not offered in the dropdown: "
        f"{sorted(ranked - offered)} -- the form cannot name them, and a "
        "user who changes the ranking cannot put them back")

    # The excluded rows are exactly the non-positive ones, and they are
    # a base fact of the shipped table, not a re-derivation of the
    # handler's filter: what is checked is that nothing *else* went
    # missing from the dropdown along with them.
    non_positive = {row[0] for row in sqlite_conn.execute(
        "SELECT c_addr_type FROM BIOG_ADDR_CODES WHERE c_addr_type <= 0")}
    assert non_positive, "the shipped table has no non-positive address type"
    assert described - offered == non_positive, (
        f"the dropdown drops {sorted(described - offered)}; only the "
        f"non-selectable rows {sorted(non_positive)} should be missing")


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

    # A longer fragment of the same name can only ever match fewer
    # people.  Guarded by a non-zero check anyway: while the FTS index
    # was empty -- the 2026-09-01 build shipped one that way -- any 3+
    # character term
    # returned nothing, which made this trivially true.
    full = person["name"].strip()
    if len(full) >= 3:
        narrower = app.json("GET", "/api/browser/people",
                            params={"search": full, "limit": 1})
        if narrower["total"] > 0:
            assert narrower["total"] <= hits["total"], \
                f"searching {full!r} matched more people than {term!r}"


def test_every_name_belongs_to_a_person_who_exists(sqlite_conn):
    """No name may be indexed for a person the database does not contain.

    A **data-origin** check (AGENTS.md § "Where a defect comes from"): a
    failure here is a property of the database snapshot that was
    packaged, not of any code path in ``cbdb.exe``.  Every row
    ``RunZZZNames`` writes is read out of ``BIOG_MAIN`` or reached
    through an INNER JOIN against it, so the derivation cannot invent an
    orphan; an orphan means ``BIOG_MAIN`` lost a row *after* ``ZZZ_NAMES``
    was last derived from it.  That is fixed by rebuilding from the
    current source, not by the application developers.

    The 2026-09-01 build shipped exactly one (person 100382, searchable
    by name and then a 404 when opened).  The 2026-09-07 build ships
    none, which is what a clean rebuild is supposed to produce.

    ``CBDBSetUpCode/zzznames_referential_check.go`` is this same query,
    shipped as a build-time guard; nothing in the build sequence calls it
    yet, so this test is currently the only place it runs.
    """
    orphans = [row[0] for row in sqlite_conn.execute(
        "SELECT DISTINCT n.c_personid FROM ZZZ_NAMES n "
        "LEFT JOIN BIOG_MAIN b ON b.c_personid = n.c_personid "
        "WHERE b.c_personid IS NULL")]
    assert orphans == [], (
        f"{len(orphans)} person id(s) have names but no BIOG_MAIN row: "
        f"{orphans[:10]}.  They are searchable by name and then 404 when "
        "opened.  This is a snapshot-provenance problem: rebuild "
        "ZZZ_NAMES from the current BIOG_MAIN.")


@pytest.mark.parametrize("term,expected_minimum", [
    ("Wang", 50_000),        # a very common surname
    ("Wang Anshi", 1),       # a person every edition of CBDB contains
    ("Su Shi", 1),
    ("王安石", 1),   # the same person, in Chinese
])
def test_searching_people_by_name_finds_them(app: CbdbApp, term: str,
                                             expected_minimum: int):
    """The main way a user finds a person in the browser.

    Terms of three or more characters are the interesting ones: SQLite
    routes a short LIKE pattern past the trigram index and scans the
    content table, so short searches went on working while the index was
    empty, as the 2026-09-01 build shipped it.  Anything three
    characters or longer goes through ``ZZZ_NAMES_FTS`` and is the case
    that actually exercises it -- which is why every term below except
    "Wang" is at least three characters, in both scripts.
    """
    payload = app.json("GET", "/api/browser/people",
                       params={"search": term, "limit": 20})

    assert payload["total"] >= expected_minimum, \
        f"search {term!r} ({len(term)} characters) found " \
        f"{payload['total']} people"
    assert payload["records"], f"search {term!r} reported a total but no rows"


def test_the_name_search_index_covers_every_name(sqlite_conn):
    """Every row of ZZZ_NAMES is in the trigram index that searches it.

    The root cause of that -- an unbuilt full-text name index --
    asserted where it lives.
    ``ZZZ_NAMES_FTS`` is an external-content FTS5 table, so browsing it
    directly shows every row regardless -- they are read straight from
    ``ZZZ_NAMES``.  Only the shadow tables say whether the index itself
    was ever built, which is why the count comes from
    ``ZZZ_NAMES_FTS_docsize`` (one row per indexed document) rather than
    from the virtual table.

    Equality, not "more than zero": the 2026-09-01 build shipped a
    schema and sync triggers that were both correct over an index holding
    zero documents, and any non-zero floor would also pass on a
    partially rebuilt index that leaves search broken for most names.

    ``CBDBSetUpCode/zzznames_backend.go`` now makes the same comparison
    inside ``RunZZZNames``' own transaction and rolls back on a mismatch;
    ``test_the_build_verifies_the_search_index_before_committing`` checks
    that guard is still in the shipped source.
    """
    content = sqlite_conn.execute("SELECT COUNT(*) FROM ZZZ_NAMES").fetchone()[0]
    indexed = sqlite_conn.execute(
        "SELECT COUNT(*) FROM ZZZ_NAMES_FTS_docsize").fetchone()[0]
    assert content > 100_000, content

    assert indexed == content, (
        f"the name index holds {indexed:,} documents for {content:,} names -- "
        "search is broken for whatever is missing, and nothing in the "
        "application reports it")


def test_the_build_verifies_the_search_index_before_committing(layout):
    """The database builder must not be able to ship an unbuilt index.

    Read as data out of the shipped builder source, the way
    ``routes.py`` reads the routing table.  What produced the
    2026-09-01 build's unbuilt name index was not missing code but code
    that could not tell whether it had run, so the guard's *presence* is
    the property worth pinning.
    A rebuild that stops checking would let the same silent failure ship
    again, and the symptom -- search finding nothing for three-character
    terms -- would only be caught by the test above, on a build that has
    already been packaged and sent out.
    """
    source = (layout.setup_code_dir / "zzznames_backend.go").read_text(
        encoding="utf-8", errors="replace")

    assert "ZZZ_NAMES_FTS_docsize" in source, (
        "RunZZZNames no longer counts the FTS shadow table after "
        "rebuilding it: an unindexed database can be committed again")
    assert "FTS rebuild incomplete" in source, \
        "the FTS row-count mismatch no longer fails the transaction"


def test_a_person_who_does_not_exist_is_a_404(app: CbdbApp, sqlite_conn):
    """A missing person is reported, not answered with an empty shell."""
    highest = sqlite_conn.execute(
        "SELECT MAX(c_personid) FROM BIOG_MAIN").fetchone()[0]
    response = app.get(f"/api/browser/person/{highest + 1000}")
    assert response.status_code == 404, response.status_code

    assert app.get("/api/browser/person/not-a-number").status_code == 400


# ---------------------------------------------------------------------------
# the dependent dropdowns: a code list narrowed by the type above it
# ---------------------------------------------------------------------------

#: The two pickers that narrow one list by a selection in another, and
#: what each calls things.  Both are POST, which is unusual for a
#: lookup and is what put them outside the reach of any sweep over GET
#: endpoints.
#:
#: ``(endpoint, request key, reply key, the table the type codes live
#: in, that table's type column)``.  The type codes are read out of the
#: data rather than written down here: they are a hierarchy whose shape
#: belongs to CBDB, and a refresh that retires one should choose another
#: rather than leave this testing a code that no longer exists.
DEPENDENT_PICKERS = {
    "entry": ("/api/entry-codes-for-type", "entryTypeCode", "entryCode",
              "ENTRY_CODE_TYPE_REL", "c_entry_type"),
    "status": ("/api/status-codes-for-type", "statusTypeCode", "statusCode",
               "STATUS_CODE_TYPE_REL", "c_status_type_code"),
}


def _codes_for(app: CbdbApp, picker: str, type_code: str) -> set[int]:
    """The set of codes the picker offers under ``type_code``."""
    endpoint, request_key, reply_key, _table, _column = DEPENDENT_PICKERS[picker]
    rows = app.json("POST", endpoint, json={request_key: type_code})
    assert isinstance(rows, list), (
        f"{endpoint} now answers with {type(rows).__name__} rather than a "
        "bare array; both handlers encoded an array when this was written")
    return {row[reply_key] for row in rows}


@pytest.fixture(scope="module", params=sorted(DEPENDENT_PICKERS))
def picker_types(request, sqlite_conn):
    """``(picker, [type codes], [child code])`` chosen from the data.

    Two kinds of type code are wanted: the ones with the most rows
    behind them, because a filter that returns nothing proves nothing;
    and a *longer* code sharing a prefix with one of them, because the
    containment property below is only interesting where the hierarchy
    actually has two levels.
    """
    picker = request.param
    _endpoint, _req, _reply, table, column = DEPENDENT_PICKERS[picker]

    busiest = [row[0] for row in sqlite_conn.execute(
        f"SELECT {column} FROM {table} "
        f"WHERE {column} IS NOT NULL AND {column} <> '' "
        f"GROUP BY {column} ORDER BY COUNT(*) DESC, {column} LIMIT 3")]
    assert busiest, f"{table} offers no type codes to test with"

    # Any parent/child pair in the hierarchy, not merely one under the
    # busiest code.  The first version asked only about `busiest[0]`,
    # which has no children in this data, so the containment test below
    # skipped on both pickers -- reporting "nothing to judge" about a
    # hierarchy that has 7 two-level and 3 three-level Entry codes.
    pair = sqlite_conn.execute(
        f"SELECT parent.{column}, child.{column} "
        f"FROM (SELECT DISTINCT {column} FROM {table}) parent "
        f"JOIN (SELECT DISTINCT {column} FROM {table}) child "
        f"  ON LENGTH(child.{column}) > LENGTH(parent.{column}) "
        f" AND SUBSTR(child.{column}, 1, LENGTH(parent.{column})) "
        f"     = parent.{column} "
        f"ORDER BY LENGTH(parent.{column}), parent.{column}, child.{column} "
        f"LIMIT 1").fetchone()
    return picker, busiest, pair


def test_a_dependent_picker_offers_only_codes_the_whole_list_has(
        app: CbdbApp, picker_types):
    """Narrowing by type may remove codes; it may not invent them.

    The unfiltered call -- an empty type -- is the picker's own answer
    to "everything", so it is the right thing to compare against: no
    count is predicted here and no join is re-run, only the application
    compared with itself under two requests.

    This is the whole of what the Entry and Status type dropdowns do,
    and neither endpoint had been requested by any test before.
    """
    picker, busiest, _deeper = picker_types
    everything = _codes_for(app, picker, "")
    assert everything, f"the {picker} picker offers no codes at all"

    narrowed_by = {}
    for type_code in busiest:
        narrowed = _codes_for(app, picker, type_code)
        assert narrowed, (
            f"{picker} type {type_code!r} is one of the three commonest in "
            f"the data and the picker offers nothing under it")
        stray = sorted(narrowed - everything)
        assert not stray, (
            f"{picker} type {type_code!r} offers {len(stray)} code(s) the "
            f"unfiltered list does not have: {stray[:5]}.  A filtered "
            "dropdown that adds options is offering the user something "
            "the form cannot then act on")
        narrowed_by[type_code] = narrowed

    # Containment on its own is the third true-by-construction shape
    # AGENTS.md names: a handler that ignored the type entirely and
    # always answered with the whole list would satisfy every subset
    # assertion above.  So the filter is also required to *filter*.
    #
    # Neither of these predicts a count.  The first compares the
    # picker's answer with the picker's own answer to "everything"; the
    # second compares two of its answers with each other.  A handler
    # rewritten from scratch to the same specification passes both; one
    # that dropped its WHERE clause fails both.
    assert any(codes < everything for codes in narrowed_by.values()), (
        f"every {picker} type returned all {len(everything)} codes, so "
        "choosing a type changes nothing.  The narrowing branch is not "
        "running, and the dropdown below the type selector is showing "
        "the user the unfiltered list whatever they pick")

    distinct = {frozenset(codes) for codes in narrowed_by.values()}
    assert len(distinct) > 1, (
        f"the {len(busiest)} commonest {picker} types all return the same "
        f"{len(everything)} codes; the type selector is inert")


def test_a_deeper_type_offers_a_subset_of_the_one_above_it(
        app: CbdbApp, picker_types):
    """The hierarchy the prefix match implies, asserted as containment.

    These codes are a tree flattened into a string: ``01`` is the parent
    of ``0102``, and the handler selects children by comparing the first
    *n* characters.  The property that makes it a tree -- a child's
    codes are among its parent's -- is what a user relies on when they
    narrow a dropdown twice, and it is checkable without knowing how the
    handler does the comparison.

    Skipped rather than failed when the shipped data has no two-level
    code for this picker: the claim would then be about nothing, and a
    test that quietly passes in that state is worse than one that says
    it could not judge.
    """
    picker, _busiest, pair = picker_types
    if not pair:
        pytest.skip(f"the {picker} type codes are a single level in this "
                    "data, so there is no containment to check")
    parent, child = pair
    below = _codes_for(app, picker, child)
    above = _codes_for(app, picker, parent)

    assert below, f"{picker} type {child!r} exists in the data and offers nothing"
    outside = sorted(below - above)
    assert not outside, (
        f"{picker} type {child!r} sits under {parent!r} in "
        f"{DEPENDENT_PICKERS[picker][3]}, and offers {len(outside)} code(s) "
        f"its parent does not: {outside[:5]}.  Narrowing a dropdown twice "
        "would then show the user options that disappear when they go back "
        "one level")


def test_the_two_dependent_pickers_agree_about_what_no_type_means(
        app: CbdbApp, picker_types):
    """Both take ``""`` and both take ``"Root"``, and both mean everything.

    ``Root`` is what a tree picker sends when the user selects the top
    node, and both handlers test for it -- Entry after a
    ``strings.TrimSpace``, Status on the raw field, but both with the
    same ``== "" || == "Root"`` shape.  Pinned because the
    consequence of one of them dropping that second clause is not an
    error: the prefix branch would compare the first four characters of
    each type code against ``Root``, match nothing, and hand the user an
    empty dropdown.  That is reported as "the form is broken", and it
    would be a one-word change that no other test here would see.
    """
    picker, _busiest, _pair = picker_types
    everything = _codes_for(app, picker, "")
    assert everything, f"the {picker} picker offers no codes at all"

    assert _codes_for(app, picker, "Root") == everything, (
        f"the {picker} picker no longer treats 'Root' as the whole list, "
        "so selecting the top node of the tree empties the dropdown "
        "instead of filling it")

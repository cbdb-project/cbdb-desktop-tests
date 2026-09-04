"""The six read-only form queries, driven with real filters.

These are the endpoints a historian actually uses: pick some codes in a
picker, press Query, look at the grid, export it.  This file does that
against the shipped binary for entry, office, status, texts, associations
and places -- the six forms whose queries need no prior state.

**What the exports actually compare.**  It is tempting to call
"export the grid and compare it to the grid" a strong oracle.  It is only
sometimes one, and the difference is worth stating:

* **entry** is the real one.  ``handleQuery`` marshals its records to
  JSON *and* stages the same slice into ``ZZ_SCRATCH_ENTRY`` row by row,
  logging and skipping any insert that fails; ``export-results`` then
  dumps that table.  Comparing the two therefore checks a 54-column
  insert list against a 54-field struct, and would notice dropped rows.
* **associations** re-reads ``ZZ_SOCIAL_NETWORK``, which is also where
  its query read from -- same table, same order.  That catches format
  and scan losses, not much else.
* **office, status, texts, places** post the grid back to a formatter
  that serialises exactly what it was given.  Row counts cannot differ.
  What that pair *does* pin is that the export struct's JSON tags still
  match the query response's: if they drifted, Go would decode
  zero-valued structs and the person ids would come back as 0.

**Order dependence is real, but not where it first appears.**  Of these
six, only entry (``ZZ_SCRATCH_ENTRY``) and associations
(``ZZ_SOCIAL_NETWORK``, ``ZZ_SCRATCH_PEOPLE``) write anything during a
query; the other four build their result in a single SELECT.  Cross-form
leakage is therefore not something these six can do to each other -- but
three *other* forms clobber the tables associations exports from, which
is a real defect and is tested at the end of this file.

Every test issues its own query before exporting, so the file is safe
under ``-k`` selection and in any file order.

Filter values are chosen from the data (codes with a handful of rows) so
responses stay small: no form query applies a LIMIT, and one popular
entry code returned 89 MB while this suite was being written.  Choosing
an input is not an oracle -- nothing here predicts what a query returns.
"""
from __future__ import annotations

import base64
import csv
import io
from collections import Counter

import pytest

from cbdb_desktop.app import CbdbApp
from cbdb_desktop.defects import BY_NAME, KnownShippedDefect
from cbdb_desktop.forms import FORMS, FORMS_BY_NAME, FormSpec

pytestmark = pytest.mark.app

# How many rows a filter code may cover in its base table before it is too
# expensive to use as a test input.
_MAX_ROWS_PER_CODE = 12
_MIN_ROWS_PER_CODE = 2

# A guard, not an oracle: if a future build adds a fan-out join to one of
# these queries, fail fast and legibly instead of downloading it.
_MAX_RESULT_ROWS = 5_000

#: Where each form's rows carry the code the query filtered on.  Every one
#: of the six does carry it, which is what makes
#: test_a_query_returns_only_what_was_asked_for possible.
CODE_KEY = {
    "entry": "entryCode",
    "office": "c_office_id",
    "status": "statusCode",
    "texts": "textId",
    "associations": "assocCode",
    "places": "addrId",
}

#: Identifier fields worth checking for danglers.  personId comes through
#: an INNER JOIN on BIOG_MAIN and cannot dangle; the rest arrive through
#: LEFT joins, so a broken one reaches the grid as an id with a blank
#: name -- which is exactly the sort of thing a data release breaks.
PERSON_ID_KEYS = ("personId", "c_personid", "kinId", "assocId",
                  "kinAssocId", "assocClaimerId")


@pytest.fixture(scope="module")
def cheap_codes(app: CbdbApp, sqlite_conn):
    """Filter values that are small *and* actually produce rows.

    Two steps, and the second one matters.  Codes are drawn from the base
    table by row count, which keeps responses small -- but a code can have
    rows there and still contribute nothing to a form's result (four of
    five candidate text ids do exactly that).  So each candidate is then
    tried against the application, and only the live ones are kept.

    Asking the app which of its own codes return rows is input selection,
    not an oracle: no expectation is derived from the answer.
    """
    cache: dict[tuple[str, int], list[int]] = {}

    def pick(form: FormSpec, limit: int = 5) -> list[int]:
        key = (form.name, limit)
        if key not in cache:
            candidates = [row[0] for row in sqlite_conn.execute(
                f'SELECT "{form.code_column}" FROM "{form.code_table}" '
                f'GROUP BY "{form.code_column}" '
                "HAVING COUNT(*) BETWEEN ? AND ? "
                "ORDER BY COUNT(*) DESC, 1 LIMIT ?",
                (_MIN_ROWS_PER_CODE, _MAX_ROWS_PER_CODE, limit * 8)).fetchall()]
            live = []
            for code in candidates:
                if len(live) == limit:
                    break
                if form.rows(_query(app, form, [code])):
                    live.append(code)
            cache[key] = live
        codes = cache[key]
        assert len(codes) >= min(2, limit), (
            f"{form.name}: only {len(codes)} of the candidate "
            f"{form.code_column} values return any rows")
        return codes

    return pick


def _csv_rows(data_url: str) -> list[list[str]]:
    """Decode one exported file: a base64 data URL of tab-separated text."""
    assert data_url.startswith("data:"), data_url[:60]
    blob = data_url.split("base64,", 1)[1]
    text = base64.b64decode(blob).decode("utf-8")
    rows = list(csv.reader(io.StringIO(text), delimiter="\t"))
    # A trailing newline yields one empty row; anything else blank is
    # kept, so an unexpectedly empty exported line is visible.
    if rows and rows[-1] == []:
        rows.pop()
    return rows


def _query(app: CbdbApp, form: FormSpec, codes: list[int]):
    response = app.post(form.query_path, json=form.body(codes))
    assert response.status_code == 200, \
        f"{form.name}: {response.status_code} {response.text[:300]}"
    payload = response.json()
    rows = form.rows(payload)
    assert len(rows) < _MAX_RESULT_ROWS, (
        f"{form.name}: {len(rows)} rows for {len(codes)} narrow codes -- "
        "a filter has stopped filtering, or a join now fans out")
    return payload


def _export(app: CbdbApp, form: FormSpec, payload) -> list[dict]:
    response = app.post(form.export_path, json=form.export_body(payload))
    assert response.status_code == 200, \
        f"{form.name}: export {response.status_code} {response.text[:300]}"
    exported = response.json()
    assert exported["status"] == "ok", exported
    assert [f["name"] for f in exported["files"]] == list(form.export_files)
    return exported["files"]


def _column(header: list[str], *names: str) -> int:
    wanted = {n.lower().replace("_", "") for n in names}
    for index, name in enumerate(header):
        if name.lower().replace("_", "") in wanted:
            return index
    raise AssertionError(f"no {names} column in {header}")


def _person_ids(rows: list[dict]) -> set[int]:
    return {row[key] for row in rows for key in PERSON_ID_KEYS
            if key in row and isinstance(row[key], int) and row[key] > 0}


@pytest.fixture(params=[form.name for form in FORMS])
def form(request) -> FormSpec:
    return FORMS_BY_NAME[request.param]


# ---------------------------------------------------------------------------
# the query itself
# ---------------------------------------------------------------------------

def test_a_query_returns_rows_in_the_shape_the_form_declares(
        app: CbdbApp, form: FormSpec, cheap_codes):
    """A real query with real filters comes back populated and well-formed."""
    codes = cheap_codes(form)
    payload = _query(app, form, codes)
    rows = form.rows(payload)

    assert rows, f"{form.name}: no rows for codes that have some"
    assert isinstance(rows, list)
    assert CODE_KEY[form.name] in rows[0], sorted(rows[0])

    # Every code asked for is represented.  Without this, a filter value
    # that quietly contributes nothing would weaken every test below that
    # depends on several codes being live.
    represented = {row[CODE_KEY[form.name]] for row in rows}
    assert represented == set(codes), \
        f"{form.name}: asked for {sorted(codes)}, got {sorted(represented)}"

    if form.people_key:
        assert form.people(payload), f"{form.name}: no accompanying people rows"


def test_every_person_in_a_result_exists(app: CbdbApp, form: FormSpec,
                                         cheap_codes, sqlite_conn):
    """A grid must not name people the database does not have.

    The person the row is *about* arrives through an INNER JOIN on
    BIOG_MAIN and cannot dangle.  The related people -- kin, associate,
    claimer -- arrive through LEFT joins, so those are the ids worth
    checking: a broken one shows up in the grid as an id with a blank
    name.  Membership in BIOG_MAIN is a base fact; the query's own
    filtering is not reproduced.
    """
    payload = _query(app, form, cheap_codes(form))
    rows = form.rows(payload) + form.people(payload)

    ids = _person_ids(rows)
    assert ids, f"{form.name}: no person ids to check"

    placeholders = ",".join("?" * len(ids))
    known = {row[0] for row in sqlite_conn.execute(
        f"SELECT c_personid FROM BIOG_MAIN WHERE c_personid IN ({placeholders})",
        tuple(ids))}
    missing = sorted(ids - known)
    assert not missing, \
        f"{form.name}: people named in the grid but absent from BIOG_MAIN: " \
        f"{missing[:10]}"


def test_a_query_returns_only_what_was_asked_for(app: CbdbApp, form: FormSpec,
                                                 cheap_codes):
    """Each row carries one of the codes the query filtered on.

    For most forms the filtered and displayed column are the same SQL
    expression, so this mainly catches a projection drifting to another
    alias or a join fanning out.  Associations is the exception with real
    content: it filters on ASSOC_DATA.c_assoc_code and displays
    ZZ_SOCIAL_NETWORK.c_link_code after six enrichment UPDATEs.
    """
    codes = cheap_codes(form)
    rows = form.rows(_query(app, form, codes))

    returned = {row[CODE_KEY[form.name]] for row in rows}
    unexpected = sorted(returned - set(codes))
    assert not unexpected, \
        f"{form.name}: asked for {codes}, got rows for {unexpected}"


def test_two_filters_together_return_exactly_the_two_apart(
        app: CbdbApp, form: FormSpec, cheap_codes):
    """Additivity: querying A+B gives the rows of A plus the rows of B.

    A disjunctive filter has to be additive, and this is the one property
    of these queries that a degenerate implementation cannot satisfy.
    "A is a subset of A+B" would not do: it holds when the filter is
    ignored entirely (every query returns everything) and when a query
    returns nothing.  Equality of the (person, code) pairs holds in
    neither case.

    Whole rows are deliberately not compared.  Fields like xyCount are
    frequencies *within the result set* -- how many returned rows share a
    coordinate -- so they legitimately grow as the result grows.

    Counted, not set-compared: a build that deduplicated two identical
    (person, code) rows would leave the sets equal and the counts not.
    """
    codes = cheap_codes(form)
    key = CODE_KEY[form.name]

    def pairs(selected) -> Counter:
        rows = form.rows(_query(app, form, selected))
        assert rows, f"{form.name}: {selected} returned nothing"
        return Counter((row.get("personId", row.get("c_personid")), row[key])
                       for row in rows)

    a = pairs(codes[:1])
    b = pairs(codes[1:2])
    together = pairs(codes[:2])

    assert a != b, f"{form.name}: two different codes returned the same rows"
    assert a + b == together, (
        f"{form.name}: querying both codes is not the sum of querying each: "
        f"{sorted((a + b) - together)[:5]} missing, "
        f"{sorted(together - (a + b))[:5]} unexpected")


# ---------------------------------------------------------------------------
# export against query
# ---------------------------------------------------------------------------

def test_the_export_renders_the_result_it_was_given(app: CbdbApp, form: FormSpec,
                                                    cheap_codes):
    """The grid and the exported file describe the same people.

    See the module docstring for how much this proves per form: a real
    staging round trip for entry, a JSON field-name round trip for the
    four formatter-backed forms.  In every case the person ids are
    compared, not just the row count -- two different result sets can be
    the same size.
    """
    payload = _query(app, form, cheap_codes(form))
    rows = form.rows(payload)
    files = _export(app, form, payload)

    exported = _csv_rows(files[0]["url"])
    assert exported, f"{form.name}: the exported file is empty"
    header, body = exported[0], exported[1:]
    assert len(header) > 1, f"{form.name}: exported header is {header}"

    widths = {len(row) for row in body}
    assert widths == {len(header)}, \
        f"{form.name}: exported rows have widths {sorted(widths)} for a " \
        f"header of {len(header)} columns"

    column = _column(header, "c_person_id", "c_personid", "personid")
    id_key = "personId" if "personId" in rows[0] else "c_personid"
    assert sorted(row[column] for row in body) == \
        sorted(str(row[id_key]) for row in rows), \
        f"{form.name}: the export names different people than the grid"


def test_the_second_exported_file_lists_the_people_once_each(
        app: CbdbApp, form: FormSpec, cheap_codes):
    """Every export ships a second file: one row per person.

    A different code path from the first file -- a SELECT DISTINCT over
    the person and address columns -- so comparing it against the grid's
    own distinct people is genuinely app-against-app.
    """
    payload = _query(app, form, cheap_codes(form))
    rows = form.rows(payload)
    files = _export(app, form, payload)

    exported = _csv_rows(files[1]["url"])
    header, body = exported[0], exported[1:]
    column = _column(header, "c_person_id", "c_personid", "personid")

    listed = [row[column] for row in body]
    assert len(listed) == len(set(listed)), \
        f"{form.name}: the people file repeats a person"

    if form.people_key:
        # Where the response carries its own people list, that list is
        # what this file renders.
        expected = {str(row["personId"]) for row in form.people(payload)}
    else:
        id_key = "personId" if "personId" in rows[0] else "c_personid"
        expected = {str(row[id_key]) for row in rows}

    # Equality, not containment: an export that silently dropped people
    # would satisfy a subset check, and dropping people from a file
    # somebody is about to analyse is the failure worth catching.
    assert set(listed) == expected, (
        f"{form.name}: the people file and the grid disagree -- "
        f"{sorted(expected - set(listed))[:10]} missing, "
        f"{sorted(set(listed) - expected)[:10]} unexpected")


def test_an_export_with_nothing_to_export_says_so(app: CbdbApp, form: FormSpec):
    """What happens when there is nothing to export -- pinned per form.

    The six do not agree, and the disagreement is the point: four refuse
    with 400, while entry and associations answer 200 with whatever the
    scratch tables happen to hold, because they never look at the body at
    all.  Pinning both halves records the inconsistency where someone
    will see it.
    """
    if form.export_reads_scratch:
        response = app.post(form.export_path, json=form.export_body([]))
        assert response.status_code == 200, response.text[:200]
        assert response.json()["status"] == "ok"
        return

    empty = {"data": []} if form.name != "status" else {"statusData": [],
                                                        "peopleData": []}
    response = app.post(form.export_path, json=empty)
    assert response.status_code == 400, \
        f"{form.name}: exporting nothing gave {response.status_code}"


# ---------------------------------------------------------------------------
# repeatability
# ---------------------------------------------------------------------------

def test_the_same_query_twice_gives_the_same_answer(app: CbdbApp, form: FormSpec,
                                                    cheap_codes):
    """Identical requests give identical answers.

    For entry and associations this exercises the truncate-and-refill of
    their scratch tables; for the other four it is a determinism check on
    a single SELECT.  Both are worth having, for different reasons.
    """
    codes = cheap_codes(form)
    first = _query(app, form, codes)
    second = _query(app, form, codes)
    assert first == second, f"{form.name}: two identical queries disagreed"


# ---------------------------------------------------------------------------
# cross-form interference
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, raises=KnownShippedDefect,
                   reason=BY_NAME["associations-export-clobbered"].reason)
def test_another_form_does_not_empty_the_associations_export(
        app: CbdbApp, cheap_codes):
    """Associations exports whatever is in ZZ_SOCIAL_NETWORK *now*.

    Its export takes no body and no lock: it re-reads the scratch table
    the query filled.  Three other forms -- Association Pairs, Networks
    and Kinship -- delete from that same table as part of their own
    queries.  So visiting one of them between pressing Query and pressing
    Export replaces the user's result with an empty file, with no error
    and no indication that anything was lost.

    This is the increment's real order-dependence: not the six read-only
    forms interfering with each other (four of them write nothing), but
    the forms that share this table with them.
    """
    associations = FORMS_BY_NAME["associations"]
    payload = _query(app, associations, cheap_codes(associations))
    rows = associations.rows(payload)
    assert rows, "no associations to lose"

    before = _csv_rows(_export(app, associations, payload)[0]["url"])
    assert len(before) - 1 == len(rows), "the export did not match the query"

    # A perfectly ordinary thing for a user to do next.
    other = app.post("/api/assocpairs/query", json={
        "personId1": 1762, "personId2": 0, "useList": False,
        "includeKinship": False, "use2ndOrder": False,
        "yearFilterType": "none", "allDynasties": True})
    assert other.status_code == 200, other.text[:200]

    after = _csv_rows(_export(app, associations, payload)[0]["url"])
    if len(after) - 1 == 0:
        raise KnownShippedDefect(
            f"an Association Pairs query emptied the Associations export: "
            f"{len(before) - 1} rows before, {len(after) - 1} after")
    assert len(after) - 1 == len(rows), (
        f"the Associations export changed after an unrelated query: "
        f"{len(before) - 1} rows before, {len(after) - 1} after")

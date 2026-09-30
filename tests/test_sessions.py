"""What happens when the application is used twice at once.

Every other file in this suite drives the application the way one person
with one window drives it, one request after another.  That is the
common case and not the only one: a historian comparing two queries
opens two tabs, and somebody who cannot find the window they started
double-clicks the shortcut again.

Both of those break the application's result, silently, and the reason
is structural rather than accidental: **nothing in a request says who it
came from**.  There is no session cookie, no tab id, no per-connection
state; the scratch tables a query fills and an export reads are one set
per database file.  The 2026-09-07 build gave each *form* its own copy
of those tables, which fixed cross-form interference and
left cross-request interference exactly as it was.

The tests here are deliberately small and structural.  Two of them drive
two tabs' worth of requests at one server; the third launches a second
``cbdb.exe`` against the database the first one holds, and asks whether
it is refused.  (Until 20260925 there was no single-instance guard, and
that test read ``main.go`` to establish the absence.  An absence can be
read; whether a guard that exists actually holds cannot.)

They are written as an ordinary sequence of requests rather than with
threads.  A real race would be a stronger demonstration and a much
worse test -- flaky, slow, and unnecessary: sequential overwriting is
already the whole user-visible defect.
"""
from __future__ import annotations

import csv
import io

import pytest

from cbdb_desktop.app import AppError, CbdbApp
from cbdb_desktop.defects import KnownShippedDefect
from cbdb_desktop.exports import delivered_files
from cbdb_desktop.forms import FORMS_BY_NAME

pytestmark = pytest.mark.app


def _rows(envelope: dict) -> list[list[str]]:
    """The first file an Associations export delivers, as rows.

    From 20260925 the files arrive packed in one ZIP; the first member is
    the association rows, as the first file was before.
    """
    (name, raw), *_rest = delivered_files("associations", envelope["files"])
    expected = FORMS_BY_NAME["associations"].export_files[0]
    assert name == expected, (
        f"the Associations export's first file is {name!r}, not {expected!r}; "
        "the row counts below would be comparing a different file")
    text = raw.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text), delimiter="\t"))
    while rows and rows[-1] in ([], [""]):
        rows.pop()
    return rows


@pytest.fixture(scope="module")
def two_association_codes(app: CbdbApp, sqlite_conn) -> list[int]:
    """Two association codes that return different, non-empty results.

    Both halves matter.  Non-empty, because "tab A's export is empty"
    and "tab A's export is tab B's result" are different failures and
    only the second is this defect.  Different, because an export that
    happens to be identical either way would make the test pass on a
    build that had no isolation at all.
    """
    form = FORMS_BY_NAME["associations"]
    candidates = [row[0] for row in sqlite_conn.execute(
        f'SELECT "{form.code_column}" FROM "{form.code_table}" '
        f'GROUP BY "{form.code_column}" HAVING COUNT(*) BETWEEN 2 AND 12 '
        "ORDER BY COUNT(*) DESC, 1 LIMIT 20")]

    live: list[int] = []
    sizes: list[int] = []
    for code in candidates:
        rows = form.rows(app.json("POST", form.query_path,
                                  json=form.body([code])))
        if rows:
            live.append(code)
            sizes.append(len(rows))
        if len(live) >= 2 and sizes[0] != sizes[-1]:
            return [live[0], live[-1]]
    pytest.skip(f"no two association codes return different result sizes "
                f"(tried {len(candidates)})")


def test_a_second_query_replaces_what_the_first_would_export(
        app: CbdbApp, two_association_codes):
    """Two tabs, one result.

    The sequence is exactly what a user does: query in tab A, look at
    it, query something else in tab B, go back to tab A and press
    Export.  Nothing here is an unusual request -- both queries are
    ordinary, both are addressed to the endpoint the page addresses,
    and the export takes no arguments because the endpoint takes none.

    The signature is narrowed to "tab A's export became tab B's
    result", so an export that came back empty, or errored, or lost
    rows in some other way, still fails as a failure.
    """
    associations = FORMS_BY_NAME["associations"]
    first, second = two_association_codes

    # Tab A queries and looks at its grid.
    grid_a = associations.rows(app.json("POST", associations.query_path,
                                       json=associations.body([first])))
    assert grid_a, "tab A's query returned nothing"

    export_a = app.json("POST", associations.export_path, json={})
    rows_a = _rows(export_a)
    assert len(rows_a) - 1 == len(grid_a), \
        "the export did not match the query it was for"

    # Tab B queries something else.
    grid_b = associations.rows(app.json("POST", associations.query_path,
                                        json=associations.body([second])))
    assert grid_b, "tab B's query returned nothing"
    assert len(grid_b) != len(grid_a), \
        "the two codes returned the same number of rows after all"

    # Tab A, still showing its own grid, presses Export.
    again = _rows(app.json("POST", associations.export_path, json={}))

    if len(again) - 1 == len(grid_b):
        raise KnownShippedDefect(
            f"tab A exported tab B's result: {len(grid_a)} rows in the grid "
            f"tab A is looking at, {len(again) - 1} rows in the file it just "
            f"downloaded, {len(grid_b)} rows in the query tab B ran")
    assert len(again) - 1 == len(grid_a), (
        f"tab A's export changed after another request: {len(rows_a) - 1} "
        f"rows, then {len(again) - 1}, for a grid of {len(grid_a)}")


def test_a_second_working_list_replaces_the_first(app: CbdbApp, sqlite_conn):
    """The same thing one step earlier: two tabs, one working list.

    Worth having separately from the export case because it is the
    stronger of the two.  An export reading stale rows is at least
    *visibly* wrong once somebody compares the file to the screen; a
    working list replaced under a form means the query the user then
    runs is about a different set of people, and the result is
    internally consistent and about the wrong people.
    """
    people = [row[0] for row in sqlite_conn.execute(
        "SELECT c_personid FROM KIN_DATA GROUP BY c_personid "
        "HAVING COUNT(*) BETWEEN 2 AND 5 ORDER BY c_personid LIMIT 4")]
    assert len(people) >= 4, people

    # Tab A builds its list of two.
    assert app.json("POST", "/api/kinship/import-people",
                    json={"personIds": people[:2]})["count"] == 2

    # Tab B, on the same form, builds a different list of two.
    assert app.json("POST", "/api/kinship/import-people",
                    json={"personIds": people[2:4]})["count"] == 2

    # Tab A asks the form what it is working on.
    count = app.json("GET", "/api/kinship/person-count")["count"]
    assert count == 2, count

    ego_rows = app.json("POST", "/api/kinship/query",
                        json={"maxUp": 1, "maxDown": 1, "maxCol": 1,
                              "maxMarr": 1, "mourningCircle": False})
    subjects = {row["personId"] for row in ego_rows["kinRecords"]
                if isinstance(row.get("personId"), int)}

    # Liveness first.  Both assertions below are subset tests, and the
    # empty set is a subset of everything -- so a Kinship query that
    # returned nothing at all would sail through this test having
    # shown that tab A's result is about neither tab's people and
    # also about tab A's people.  Whether the two tabs interfere is
    # unanswerable without a result to look at, and an unanswerable
    # question must not read as an answer.
    assert subjects, (
        f"the kinship query returned no rows carrying a personId for "
        f"{people[:2]}, so there is nothing to attribute to either "
        "tab.  That is a broken query rather than a clean session: "
        "the two people were just imported and person-count agreed "
        "there were two of them.")

    if subjects <= set(people[2:4]):
        raise KnownShippedDefect(
            f"the query tab A ran is about tab B's people: asked about "
            f"{people[:2]}, the result is about {sorted(subjects)}")
    assert subjects <= set(people[:2]), \
        f"the result is about neither list: {sorted(subjects)}"


def test_a_second_instance_on_the_same_database_is_refused(app: CbdbApp):
    """A second cbdb.exe against the same database must be refused.

    Driven, by launching the second copy against the database the
    session's server already holds -- which is what a user does who
    double-clicks the shortcut again.  Earlier builds had no guard at
    all, and this test read ``main.go`` to say so; reading source can
    only establish an *absence*.  Once a guard exists, whether it holds
    is a question only the running binary answers: a lock taken on the
    wrong path, or on a file the second copy never opens, reads as a
    guard and refuses nothing.

    The in-process mutexes the handlers take (``associationsMu``,
    ``kinshipMu``) are irrelevant here by construction: a second process
    gets its own copy of each, so they serialise nothing between the two.

    Three things are asserted, each falsifiable on its own: the second
    copy never announced a port (it did not serve), it said why (so the
    user is not left with a window that closed on them), and the first
    copy is still healthy (the refusal did not take the running one down
    with it).
    """
    second = CbdbApp(app.layout, app.db_path, app.config)
    try:
        second.start()
    except AppError as exc:
        refusal = str(exc)
    else:
        raise KnownShippedDefect(
            f"a second cbdb.exe started against {app.db_path} and is "
            f"serving at {second.base_url} while the first serves at "
            f"{app.base_url}: nothing refused it, so both can write the "
            "same scratch tables, each under its own in-process mutexes")
    finally:
        second.stop()

    assert "already running" in refusal, (
        "the second cbdb.exe did not serve, but not because it recognised "
        f"the running instance.  What it said:\n{refusal}")
    # main.go has two refusals: one that found the running copy's
    # address (CBDB.db.url, written by recordInstanceURL) and sends the
    # user's browser there, and one that could not and just exits.  With
    # the first copy up and reachable, the first is the designed path --
    # the second is a window that closes on the user.
    assert app.base_url in refusal, (
        f"the second cbdb.exe refused, but did not send the user to the "
        f"running copy at {app.base_url}, which was reachable.  What it "
        f"said:\n{refusal}")
    assert app.json("GET", "/api/health")["database_connected"] is True, (
        "refusing the second instance cost the first one its database")

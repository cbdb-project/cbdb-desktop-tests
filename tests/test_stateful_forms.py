"""The forms that remember things: kinship, networks, association pairs,
group data.

Unlike the six read-only forms, these do not take their subject in the
query.  The user builds a *working list* of people first (set one, import
several, clear), and the query then runs over whatever that list holds.
A second, separate list -- the stored person ids -- is how one form hands
a result to another.

Both lists are single and global.  There is one
``ZZ_SCRATCH_IMPORT_PEOPLE`` and one ``ZZ_STORE_PERSON_ID`` for the whole
application, shared by every form, which is why:

* Kinship and Networks always report the same ``person-count``: they are
  two views of one table, and that agreement is a free cross-form
  invariant worth asserting.
* Any form's ``store-person-ids`` replaces every other form's stored
  list -- except that Kinship and Networks refuse with 409 when the list
  is not empty, while the other six overwrite it silently.  That
  asymmetry is pinned below; it is the sort of thing that is nobody's bug
  and everybody's surprise.

These tests therefore run as explicit sequences and set up their own
state rather than inheriting it.  This file is deliberately last
alphabetically, so its state changes cannot reach the read-only forms.

Traversal depth is pinned to the minimum everywhere (`maxLoop`,
`maxNodeDist`, the kinship distances) -- these queries are graph walks
with no server-side cap, and `maxLoop: 100` on a well-connected person is
effectively unbounded.
"""
from __future__ import annotations

import pytest

from cbdb_desktop.app import CbdbApp
from cbdb_desktop.defects import BY_NAME, KnownShippedDefect

pytestmark = pytest.mark.app


@pytest.fixture(scope="module")
def egos(sqlite_conn) -> list[int]:
    """People with a handful of kin, so a traversal stays small.

    Chosen from the data to keep responses cheap; nothing about the
    expected results is derived from this query.
    """
    people = [row[0] for row in sqlite_conn.execute(
        "SELECT c_personid FROM KIN_DATA GROUP BY c_personid "
        "HAVING COUNT(*) BETWEEN 2 AND 5 ORDER BY c_personid LIMIT 6")]
    # Five, not three: the store-overwrite test uses egos[3:5], and a
    # short list there would silently become an empty request and read
    # as the application failing to replace a list.
    assert len(people) >= 5, people
    return people


@pytest.fixture
def clean_lists(app: CbdbApp, egos):
    """Empty both shared lists before the test, and again afterwards.

    Without this each test inherits whatever the previous one left --
    including, on a fresh install, whatever the release was packaged with
    (see CBDB-D-005).

    This resets the two *lists*, not the dozen scratch tables the queries
    fill.  Those are left as they are deliberately: every query truncates
    the tables it reads before writing them, so the tests that read a
    result always re-seed it.  Nothing here restores the application to
    its shipped state, and no test should assume it does.
    """
    def reset():
        app.post("/api/networks/clear-person", json={})
        # The store has no "clear"; storing an empty list is how the
        # forms that overwrite silently empty it.
        app.post("/api/places/store-person-ids", json={"personIds": []})

    reset()
    yield
    reset()


def _count(app: CbdbApp, path: str) -> int:
    return app.json("GET", path)["count"]


# ---------------------------------------------------------------------------
# what the release ships with
# ---------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, raises=KnownShippedDefect,
                   reason=BY_NAME["shipped-scratch-state"].reason)
def test_a_fresh_install_starts_with_no_working_state(app: CbdbApp, sqlite_conn):
    """A new user's application should be empty until they use it.

    Read from the *master* database rather than the running app, because
    by the time this test runs other tests have legitimately put things
    in the session's copy.  What is being asserted is a property of the
    artefact that was shipped.
    """
    populated = {}
    for row in sqlite_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        name = row[0]
        # "ZZ_", with the underscore: ZZZ_NAMES (866,011 rows),
        # ZZZ_BELONGS_TO and ZZZ_DISTANCE_DATA are shipped reference data
        # and are meant to be full.  Matching "ZZ" would report the
        # release's own lookup tables as a stranger's session.
        if not name.upper().startswith("ZZ_"):
            continue
        count = sqlite_conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
        if count:
            populated[name] = count

    if populated:
        raise KnownShippedDefect(
            f"{len(populated)} scratch tables in the shipped database still "
            f"hold a previous session's work: "
            f"{dict(sorted(populated.items())[:6])}")
    assert not populated


# ---------------------------------------------------------------------------
# the working list
# ---------------------------------------------------------------------------

def test_setting_and_clearing_the_working_list(app: CbdbApp, egos, clean_lists):
    """Set one person, import several, clear: the count follows.

    Deliberately mixes the two forms -- Kinship sets, Networks imports
    and clears, and both are asked for the count -- because the list is
    one table behind two form's endpoints.  Asserting only that the two
    counts *agree* would prove nothing: both handlers run the same SELECT
    against the same table.  What is worth checking is that a write
    through one form is visible through the other.
    """
    assert _count(app, "/api/networks/person-count") == 0

    assert app.json("POST", "/api/kinship/set-person",
                    json={"personId": egos[0]})["count"] == 1
    assert _count(app, "/api/networks/person-count") == 1, \
        "a person set on the Kinship form is not on the Networks form"

    imported = app.json("POST", "/api/networks/import-people",
                        json={"personIds": egos[:3]})
    assert imported["count"] == 3
    assert _count(app, "/api/kinship/person-count") == 3, \
        "people imported on the Networks form are not on the Kinship form"

    assert app.json("POST", "/api/networks/clear-person", json={})["count"] == 0
    assert _count(app, "/api/kinship/person-count") == 0


def test_a_kinship_query_needs_a_person_and_says_nothing_without_one(
        app: CbdbApp, clean_lists):
    """With an empty working list the query is empty, not an error."""
    payload = app.json("POST", "/api/kinship/query",
                       json={"maxUp": 1, "maxDown": 1, "maxCol": 1,
                             "maxMarr": 1, "mourningCircle": False})
    assert set(payload) == {"kinRecords", "kinNetRecords", "peopleRecords"}
    assert payload["kinRecords"] == []
    assert payload["peopleRecords"] == []


# ---------------------------------------------------------------------------
# the stored list
# ---------------------------------------------------------------------------

def test_storing_ids_in_one_form_makes_them_visible_in_the_others(
        app: CbdbApp, egos, clean_lists):
    """The store is how a result travels between forms.

    Four endpoints in three forms read one table; storing through a
    fifth must be visible in all of them.  Everything here is the
    application checking itself.
    """
    stored = app.json("POST", "/api/entry/store-person-ids",
                      json={"personIds": egos[:3]})
    assert stored["count"] == 3

    assert _count(app, "/api/kinship/store-count") == 3
    assert _count(app, "/api/networks/store-count") == 3

    recalled = app.json("GET", "/api/groupdata/recall-ids")
    assert recalled["count"] == 3
    # "found" carries whole people, not bare ids: the form shows the user
    # who it is about to work on.
    assert sorted(row["personId"] for row in recalled["found"]) == sorted(egos[:3])
    assert all(row["name"] or row["nameChn"] for row in recalled["found"])

    # Association Pairs recalls at most two: it fills two person slots.
    pair = app.json("GET", "/api/assocpairs/recall-ids")
    assert len(pair) == 2
    assert {p["personId"] for p in pair} <= set(egos[:3])
    assert all(p["name"] or p["nameChn"] for p in pair)


def test_the_forms_disagree_about_overwriting_a_stored_list(
        app: CbdbApp, egos, clean_lists):
    """Kinship and Networks refuse; the others overwrite without asking.

    Pinned as behaviour, not filed as a defect: each half is defensible
    on its own, and only the inconsistency is odd.  A user who stores a
    list from Entry and then stores from Kinship gets an error; the same
    user storing from Places instead loses the first list silently.
    """
    app.post("/api/entry/store-person-ids", json={"personIds": egos[:3]})
    assert _count(app, "/api/kinship/store-count") == 3

    for guarded in ("/api/kinship/store-person-ids",
                    "/api/networks/store-person-ids"):
        response = app.post(guarded, json={"personIds": egos[3:5]})
        assert response.status_code == 409, \
            f"{guarded} overwrote a non-empty store"
        assert response.json()["count"] == 3
    assert _count(app, "/api/kinship/store-count") == 3, \
        "a refused store changed the list anyway"

    silent = app.post("/api/places/store-person-ids",
                      json={"personIds": egos[3:5]})
    assert silent.status_code == 200
    assert _count(app, "/api/kinship/store-count") == 2, \
        "the store was not replaced"


# ---------------------------------------------------------------------------
# the queries
# ---------------------------------------------------------------------------

def test_a_kinship_query_returns_a_network_around_its_person(
        app: CbdbApp, egos, clean_lists, sqlite_conn):
    """The real kinship traversal, at its smallest useful depth."""
    app.post("/api/kinship/set-person", json={"personId": egos[0]})

    payload = app.json("POST", "/api/kinship/query",
                       json={"maxUp": 1, "maxDown": 1, "maxCol": 1,
                             "maxMarr": 1, "mourningCircle": False})
    kin = payload["kinRecords"]
    people = payload["peopleRecords"]
    assert kin, f"no kin for person {egos[0]}"
    assert people, "kin records with nobody in them"

    ids = {row[key] for row in kin + people
           for key in ("personId", "kinId", "nodeId")
           if isinstance(row.get(key), int) and row[key] > 0}
    placeholders = ",".join("?" * len(ids))
    known = {row[0] for row in sqlite_conn.execute(
        f"SELECT c_personid FROM BIOG_MAIN WHERE c_personid IN ({placeholders})",
        tuple(ids))}
    assert not ids - known, \
        f"kinship named people absent from BIOG_MAIN: {sorted(ids - known)[:10]}"

    again = app.json("POST", "/api/kinship/query",
                     json={"maxUp": 1, "maxDown": 1, "maxCol": 1,
                           "maxMarr": 1, "mourningCircle": False})
    assert again == payload, "two identical kinship queries disagreed"


def test_a_deeper_kinship_query_reaches_at_least_as_far(
        app: CbdbApp, egos, clean_lists):
    """Raising the distance limits cannot lose relatives.

    Monotonicity is the one property of a traversal that holds whatever
    the graph looks like, so it needs no oracle -- and it would catch a
    limit that had stopped being applied in either direction.
    """
    # egos[0] is the smallest graph in the fixture; a later one grows
    # enough between depths for the comparison to mean something.
    app.post("/api/kinship/set-person", json={"personId": egos[1]})

    def reached(depth: int) -> set:
        payload = app.json("POST", "/api/kinship/query",
                           json={"maxUp": depth, "maxDown": depth,
                                 "maxCol": depth, "maxMarr": depth,
                                 "mourningCircle": False})
        return {row.get("kinId") for row in payload["kinRecords"]}

    near = reached(1)
    far = reached(2)

    # Without this the test passes when the traversal returns nothing at
    # all -- which is what a broken set-person would look like.
    assert near, f"person {egos[1]} has no relatives at distance 1"
    assert len(far) > len(near), \
        f"searching further reached nobody new ({len(near)} then {len(far)})"
    assert near <= far, \
        f"searching further lost {len(near - far)} relatives"


def test_group_data_asks_only_for_the_sections_that_were_requested(
        app: CbdbApp, egos, clean_lists):
    """Each of the five sections is fetched only when its flag is set.

    The five counts are *not* an oracle: the handler assigns each one
    from its own slice length, so "count equals len(records)" is
    len(x) == len(x) round-tripped through JSON and cannot fail.  What
    can fail is the five independent request flags -- turning one off
    must empty that section and leave the other four alone.
    """
    sections = ("status", "office", "entry", "text", "place")
    flags = {"status": "queryStatus", "office": "queryOffice",
             "entry": "queryEntry", "text": "queryText", "place": "queryAddr"}

    everything = app.json("POST", "/api/groupdata/query", json=dict(
        {"personIds": egos[:3]}, **{flag: True for flag in flags.values()}))

    assert set(everything) == {f"{kind}Records" for kind in sections} | \
        {f"{kind}Count" for kind in sections}
    populated = [kind for kind in sections if everything[f"{kind}Records"]]
    assert len(populated) >= 2, \
        f"three real people produced data in only {populated}"

    # Turn off whichever section has data and check that only it changed.
    dropped = populated[0]
    body = dict({"personIds": egos[:3]},
                **{flag: (kind != dropped) for kind, flag in flags.items()})
    without = app.json("POST", "/api/groupdata/query", json=body)

    assert without[f"{dropped}Records"] == [], \
        f"{dropped} came back although it was not asked for"
    for kind in sections:
        if kind != dropped:
            assert without[f"{kind}Records"] == everything[f"{kind}Records"], \
                f"turning off {dropped} changed {kind}"


def test_group_data_reports_only_the_people_it_was_asked_about(
        app: CbdbApp, egos, clean_lists):
    """Every row belongs to one of the people in the request.

    An internal invariant of the response: no oracle, and it catches the
    failure that matters most in a form whose whole purpose is "these
    people, these facts".
    """
    payload = app.json("POST", "/api/groupdata/query", json={
        "personIds": egos[:3], "queryStatus": True, "queryOffice": True,
        "queryEntry": True, "queryText": True, "queryAddr": True})

    asked = set(egos[:3])
    for kind in ("status", "office", "entry", "text", "place"):
        rows = payload[f"{kind}Records"]
        strangers = {row["personId"] for row in rows
                     if isinstance(row.get("personId"), int)} - asked
        assert not strangers, \
            f"{kind} rows are about people who were not asked for: " \
            f"{sorted(strangers)[:10]}"


def test_group_data_asks_for_people_before_it_will_run(app: CbdbApp,
                                                       clean_lists):
    response = app.post("/api/groupdata/query", json={
        "personIds": [], "queryStatus": True, "queryOffice": False,
        "queryEntry": False, "queryText": False, "queryAddr": False})
    assert response.status_code == 400, response.status_code


def test_group_data_reports_which_imported_ids_it_found(app: CbdbApp, egos,
                                                        clean_lists):
    """Importing a list separates the people who exist from those who do not."""
    missing = 99_999_999
    payload = app.json("POST", "/api/groupdata/import-ids",
                       json={"personIds": egos[:2] + [missing]})

    assert sorted(row["personId"] for row in payload["found"]) == sorted(egos[:2])
    assert payload["notFound"] == [missing]
    assert payload["count"] == 2


def test_a_networks_query_returns_a_bounded_graph(app: CbdbApp, egos,
                                                  clean_lists):
    """The networks traversal at depth 1, which is where it stays cheap.

    ``maxLoop`` and ``maxNodeDist`` come from the request with no
    server-side cap, so this is also a reminder of what not to raise in a
    test.
    """
    app.post("/api/networks/set-person", json={"personId": egos[0]})

    payload = app.json("POST", "/api/networks/query", json={
        "usePersonID": True, "useKin": True, "useNonKin": True,
        "useMale": True, "useFemale": True,
        "maxLoop": 1, "maxNodeDist": 1,
        "kinParam": True, "maxUp": 1, "maxDwn": 1, "maxCol": 1, "maxMar": 1})

    assert set(payload) == {"edgeRecords", "nodeRecords", "aggRecords"}
    for key in payload:
        assert isinstance(payload[key], list), key

    edges = payload["edgeRecords"]
    # Node records describe one person each; edges carry both endpoints.
    nodes = {row["personId"] for row in payload["nodeRecords"]}
    assert edges and nodes, "a person with kin produced no graph"

    # Every edge endpoint must be a node the response also describes: a
    # graph whose edges point at people it does not list is one the page
    # cannot draw, and noticing that needs no oracle.
    endpoints = {row["personId"] for row in edges} | \
                {row["nodeId"] for row in edges}
    assert endpoints <= nodes, \
        f"{len(endpoints - nodes)} edge endpoints are missing from the node " \
        f"list: {sorted(endpoints - nodes)[:10]}"

    # The endpoint check above follows from how the tables are filled, so
    # it pins the shape rather than the parameters.  The distance limits
    # do not: they come straight off the request with no server-side cap,
    # and this is what says they were applied at all.
    assert max(row["nodeDist"] for row in payload["nodeRecords"]) <= 1, \
        "a node is further away than maxNodeDist allowed"
    assert max(row["edgeDist"] for row in edges) <= 1, \
        "an edge reaches further than maxLoop allowed"


def test_an_association_pairs_query_returns_its_two_people(app: CbdbApp,
                                                           clean_lists):
    """The pair form's own shape, for a person who has associations."""
    payload = app.json("POST", "/api/assocpairs/query", json={
        "personId1": 1762, "personId2": 0, "useList": False,
        "includeKinship": False, "use2ndOrder": False,
        "yearFilterType": "none", "allDynasties": True})

    assert set(payload) == {"people", "network"}
    assert isinstance(payload["people"], list)
    assert isinstance(payload["network"], list)
    assert payload["people"], "the queried person is not in their own result"
    assert any(row.get("personId1") == 1762 or row.get("personId") == 1762
               for row in payload["people"]), \
        [sorted(row) for row in payload["people"][:2]]

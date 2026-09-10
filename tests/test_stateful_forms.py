"""The forms that remember things: kinship, networks, association pairs,
group data.

Unlike the six read-only forms, these do not take their subject in the
query.  The user builds a *working list* of people first (set one, import
several, clear), and the query then runs over whatever that list holds.
A second, separate list -- the stored person ids -- is how one form hands
a result to another.

The two lists stopped being the same kind of thing in the 2026-09-07
build:

* **The working list is now per form.**  It used to be one global
  ``ZZ_SCRATCH_IMPORT_PEOPLE``, so Kinship and Networks were two views
  of one table and always reported the same ``person-count``.  Splitting
  it into ``ZZ_SIP_KINSHIP`` / ``ZZ_SIP_NETWORK`` / ``ZZ_SIP_ASSOC_PAIR``
  was part of that remediation, and it changes what a user
  sees: people imported on the Networks form are no longer waiting on
  the Kinship form.  The isolation is asserted in both directions below
  -- a later refactor that re-shared one of these tables would
  otherwise pass every other test here.
* **The stored list is still global.**  One ``ZZ_STORE_PERSON_ID`` for
  the whole application, which is now the only cross-form channel and
  therefore how a result travels between forms.  Kinship and Networks
  refuse with 409 when it is not empty while the other six overwrite it
  silently; that asymmetry is pinned below, being the sort of thing that
  is nobody's bug and everybody's surprise.

These tests therefore run as explicit sequences and set up their own
state rather than inheriting it.  This file is deliberately last
alphabetically, so its state changes cannot reach the read-only forms.

Traversal depth is pinned to the minimum everywhere (`maxLoop`,
`maxNodeDist`, the kinship distances) -- these queries are graph walks
with no server-side cap, and `maxLoop: 100` on a well-connected person is
effectively unbounded.
"""
from __future__ import annotations

import re

import pytest

from cbdb_desktop.app import CbdbApp
from cbdb_desktop.defects import KnownShippedDefect
from cbdb_desktop.forms import STORE_RESET, WORKING_LIST_RESETS
from cbdb_desktop.subjects import SUBJECT

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
    """Empty every list before the test, and again afterwards.

    Without this each test inherits whatever the previous one left --
    including, on a fresh install, whatever the release was packaged with
    (a confirmed defect of the 2026-09-01 build).

    This resets the *lists*, not the dozen scratch tables the queries
    fill.  Those are left as they are deliberately: every query truncates
    the tables it reads before writing them, so the tests that read a
    result always re-seed it.  Nothing here restores the application to
    its shipped state, and no test should assume it does.
    """
    def reset():
        for path, body in WORKING_LIST_RESETS:
            app.post(path, json=body)
        app.post(STORE_RESET[0], json=STORE_RESET[1])

    reset()
    yield
    reset()


def _count(app: CbdbApp, path: str) -> int:
    return app.json("GET", path)["count"]


# ---------------------------------------------------------------------------
# what the release ships with
# ---------------------------------------------------------------------------

def test_a_fresh_install_starts_with_no_working_state(app: CbdbApp, sqlite_conn):
    """A new user's application should be empty until they use it.

    Read from the *master* database rather than the running app, because
    by the time this test runs other tests have legitimately put things
    in the session's copy.  What is being asserted is a property of the
    artefact that was shipped.

    This was a confirmed defect of the 2026-09-01 build, where fourteen scratch
    tables arrived holding a previous session's work.  Its origin was
    the release process, not the code -- the database sent out was a
    working copy rather than one built through the provisioning pipeline
    -- so nothing was patched and this test is the only thing that would
    notice it happening again.  Which is the reason to keep it: a
    process fix is exactly the kind that quietly stops being followed.
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

    assert not populated, (
        f"{len(populated)} scratch tables in the shipped database hold a "
        f"previous session's work: {dict(sorted(populated.items())[:6])}.  "
        "The release was assembled from a working copy rather than from a "
        "database built through the provisioning pipeline.")


# ---------------------------------------------------------------------------
# the working list
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("form", ["kinship", "networks"])
def test_setting_and_filling_the_working_list(app: CbdbApp, egos,
                                              clean_lists, form: str):
    """Set one person, then import several: the count follows.

    Driven through one form at a time, which is the shape the lists now
    have.  Until 2026-09-07 this test deliberately mixed the two --
    Kinship set, Networks imported and cleared -- because there was one
    table behind both forms' endpoints, and the property worth checking
    was that a write through one was visible through the other.  That
    property is now false by design, and asserted false in the next
    test rather than quietly dropped.
    """
    assert _count(app, f"/api/{form}/person-count") == 0

    assert app.json("POST", f"/api/{form}/set-person",
                    json={"personId": egos[0]})["count"] == 1
    assert _count(app, f"/api/{form}/person-count") == 1

    # Both list-filling endpoints truncate first, so importing three
    # people over one person leaves three, not four.
    imported = app.json("POST", f"/api/{form}/import-people",
                        json={"personIds": egos[:3]})
    assert imported["count"] == 3
    assert _count(app, f"/api/{form}/person-count") == 3

    # Emptying it is deliberately *not* done through import-people here:
    # the two forms disagree about what an empty import means, and that
    # disagreement has its own test below.  Each form's own documented
    # reset is used instead -- the one the fixtures use.
    path, body = next((p, b) for p, b in WORKING_LIST_RESETS
                      if p.startswith(f"/api/{form}/"))
    assert app.post(path, json=body).status_code == 200
    assert _count(app, f"/api/{form}/person-count") == 0


def test_the_two_forms_disagree_about_importing_an_empty_list(
        app: CbdbApp, egos, clean_lists):
    """Kinship's empty import clears the list; Networks' does not.

    Pinned as behaviour rather than filed, and the asymmetry is the
    whole content of it. Both endpoints answer ``{"count": 0}``:

    * Kinship truncates and then inserts nothing, so the answer is
      true;
    * Networks short-circuits on an empty list and returns before it
      clears anything, so the answer is a count of a list that still
      holds three people.

    Not a defect report, because the page cannot reach it: an empty
    import means a file that parsed to no ids, and the frontend does
    not send that. It is here because it cost a run — a fixture that
    reset the working lists this way left three people behind and the
    next test read them as its own — and because "the count a form
    reports is not the count it has" is the kind of thing worth having
    written down before somebody trusts it.
    """
    assert app.json("POST", "/api/networks/import-people",
                    json={"personIds": egos[:3]})["count"] == 3
    assert app.json("POST", "/api/networks/import-people",
                    json={"personIds": []})["count"] == 0
    assert _count(app, "/api/networks/person-count") == 3, \
        "Networks' empty import now clears the list -- update this test " \
        "and cbdb_desktop.forms.WORKING_LIST_RESETS, which works around it"

    assert app.json("POST", "/api/kinship/import-people",
                    json={"personIds": egos[:3]})["count"] == 3
    assert app.json("POST", "/api/kinship/import-people",
                    json={"personIds": []})["count"] == 0
    assert _count(app, "/api/kinship/person-count") == 0, \
        "Kinship's empty import no longer clears the list, which is how " \
        "the fixtures empty it"


def test_each_forms_working_list_is_its_own(app: CbdbApp, egos, clean_lists):
    """Filling one form's working list must not touch another's.

    The user-visible half of that remediation, and the half a
    later refactor is most likely to undo: the three tables are named
    per form (``ZZ_SIP_KINSHIP``, ``ZZ_SIP_NETWORK``,
    ``ZZ_SIP_ASSOC_PAIR``) and nothing but the name keeps them apart.

    Asserted in both directions and with *different* people in each
    list, so it cannot pass by the two counts happening to agree --
    which is precisely what the previous, shared implementation did.
    """
    assert app.json("POST", "/api/kinship/import-people",
                    json={"personIds": egos[:2]})["count"] == 2
    assert _count(app, "/api/networks/person-count") == 0, \
        "people imported on the Kinship form appeared on the Networks form"

    assert app.json("POST", "/api/networks/import-people",
                    json={"personIds": egos[2:5]})["count"] == 3
    assert _count(app, "/api/kinship/person-count") == 2, \
        "importing on the Networks form changed the Kinship form's list"

    # Clearing one leaves the other -- the trap for any test, or any
    # fixture, that assumes one endpoint resets the application.
    assert app.json("POST", "/api/networks/clear-person",
                    json={})["count"] == 0
    assert _count(app, "/api/kinship/person-count") == 2, \
        "clearing the Networks list emptied the Kinship list too"


def test_a_kinship_query_needs_a_person_and_says_nothing_without_one(
        app: CbdbApp, clean_lists):
    """With an empty working list the query is empty, not an error.

    Depends on ``clean_lists`` clearing *Kinship's own* list.  When that
    fixture cleared only through /api/networks/clear-person -- correct
    while the two forms shared one table -- this test read whatever the
    previous test had left on the Kinship form and failed with a full
    result.  A state dependency, not a defect in the application.
    """
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


# ---------------------------------------------------------------------------
# the dynasty span the Networks page offers
# ---------------------------------------------------------------------------

#: The Networks query, at the depth that keeps it cheap.  Everything the
#: dynasty tests below vary is added on top of this.
_NETWORK_BASE = {
    "usePersonID": True, "useKin": True, "useNonKin": True,
    "useMale": True, "useFemale": True, "maxLoop": 1, "maxNodeDist": 1,
    "kinParam": True, "maxUp": 1, "maxDwn": 1, "maxCol": 1, "maxMar": 1,
}

#: Two real dynasties, and the years the shipped ``DYNASTIES`` table
#: gives them.  whichever two the data yields: adjacent, both
#: populous, and the page computes exactly these four numbers when a
#: user picks them -- then does not send them.
@pytest.fixture(scope="module")
def two_dynasties(sqlite_conn):
    """Two overlapping dynasties spanning the subject's own lifetime.

    Read from ``DYNASTIES`` rather than pinned as literals: AGENTS.md is
    explicit that inputs come from the data, and the year bounds here
    have to be *the ones the picker would have supplied*, so a literal
    that drifted out of step with the table would leave the ``repaired``
    control silently no longer a control.

    Chosen relative to ``SUBJECT`` rather than from the top of the table,
    which matters more than it looks.  The first version took the first
    two overlapping dynasties in year order and got SanGuo (220-265) --
    a period in which a Song figure's network contains nobody, so every
    measurement came back 1 and the control could not tell a working
    filter from a broken one.  A filter is only judgeable over a span
    where the answer would otherwise be large.
    """
    subject_dy = sqlite_conn.execute(
        "SELECT c_dy FROM BIOG_MAIN WHERE c_personid = ?", (SUBJECT,)).fetchone()
    assert subject_dy and subject_dy[0],         f"person {SUBJECT} has no dynasty in BIOG_MAIN; pick another subject"

    rows = sqlite_conn.execute(
        "SELECT c_dy, c_dynasty, c_start, c_end FROM DYNASTIES "
        "WHERE c_start > 0 AND c_end > c_start ORDER BY c_start").fetchall()
    home = [r for r in rows if r[0] == subject_dy[0]]
    assert home, f"dynasty {subject_dy[0]} is not in DYNASTIES"
    earlier = home[0]

    # The next dynasty that starts before this one ends -- the overlap is
    # what makes it a *span* rather than two disjoint windows.
    later = next((r for r in rows
                  if r[0] != earlier[0] and earlier[2] < r[2] < earlier[3]), None)
    if later is None:
        pytest.skip(f"nothing overlaps {earlier[1]} ({earlier[2]}-{earlier[3]})")
    return earlier, later


#: What ``buildDynastyConditions`` compares against, and therefore what
#: the page has to send for a dynasty choice to mean anything.
_DYNASTY_YEAR_FIELDS = frozenset({
    "fromDynastyBegin", "fromDynastyEnd", "toDynastyBegin", "toDynastyEnd",
})


def _fields_missing_from_the_networks_query(layout) -> set[str]:
    """Which of the four year fields the Networks page never sends.

    Read off the request the page builds, not off the page as a whole:
    the four names *do* occur in the file, as the globals
    ``gFromDynastyBegin`` and friends that the dynasty picker fills in,
    so a plain substring search over the template would report that the
    page sends them when what it does is compute them and drop them.

    The page has one query payload -- ``const params={...}`` immediately
    followed by ``JSON.stringify(params)`` -- and its keys are what this
    returns.
    """
    text = (layout.templates_dir / "networks" / "index.html").read_text(
        encoding="utf-8", errors="replace")

    opening = re.search(r"const\s+params\s*=\s*\{", text)
    assert opening, \
        "the Networks page no longer builds its query as `const params={...}`"

    depth, i = 1, opening.end()
    while i < len(text) and depth:
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        i += 1
    body = text[opening.end():i - 1]

    assert "JSON.stringify(params)" in text[i:i + 400], (
        "`params` is no longer the body of the query request; this helper "
        "is reading an object that is not what gets sent")

    sent = set(re.findall(r"^\s*(\w+)\s*:", body, re.MULTILINE))
    assert "fromDynasty" in sent, \
        f"the query payload no longer carries a dynasty at all: {sorted(sent)}"
    return _DYNASTY_YEAR_FIELDS - sent


def _network_nodes(app: CbdbApp, ego: int, **extra) -> int:
    """How many people one Networks query returns.  -1 when it errors."""
    app.post("/api/networks/set-person", json={"personId": ego})
    response = app.post("/api/networks/query",
                        json=dict(_NETWORK_BASE, **extra))
    if response.status_code != 200:
        return -1
    return len({row["personId"] for row in response.json()["nodeRecords"]})


def test_the_networks_page_sends_the_dynasty_span_its_handler_needs(
        app: CbdbApp, clean_lists, two_dynasties):
    """Pick two dynasties on the Networks form and see what arrives.

    The Networks form offers a dynasty *span* -- a From picker and a To
    picker -- and its handler filters on the two dynasties' **years**:
    ``DYNASTIES_1.c_end > FromDynastyBegin`` and
    ``DYNASTIES_1.c_start < ToDynastyEnd`` (networks_form_query.go,
    ``buildDynastyConditions``).  The page computes those four numbers
    when the picker returns (``gFromDynastyBegin`` and friends) and then
    builds a request without them, so the handler reads them as 0.

    Three ways for a user to hit it, and this test drives all three
    against the same ego so the numbers are comparable:

    * **From only** -- ``c_end > 0`` is true of every dynasty, so the
      filter the user asked for is silently not applied;
    * **two different dynasties** -- ``c_start < 0`` is true of five
      dynasties out of eighty-five, so the answer collapses to almost
      nothing, with no message;
    * **All Dynasties** -- the page's own button sets both codes to a
      ``-2`` sentinel the handler does not recognise, which slips past
      its "neither boundary set" guard and builds a condition on
      ``DYNASTIES_1`` that the chosen FROM clause never joined.

    The decisive half is the last comparison: sending the same request
    **with** the four year fields the page dropped makes the two-dynasty
    span behave, which is what identifies the page rather than the
    handler as the thing to fix.
    """
    # SUBJECT rather than a discovered ego: judging a filter needs a network
    # big enough for "narrower" to mean something, and this is the person
    # the suite already fixes for that reason (subjects.py, whose existence
    # test_staging.py checks against the shipped data).
    ego = SUBJECT
    unfiltered = _network_nodes(app, ego, useDynasties=False)
    assert unfiltered > 100, (
        f"person {ego} returns only {unfiltered} people at depth 1; too "
        "small a network to tell a working filter from a broken one")

    (from_dy, from_name, from_start, from_end),         (to_dy, to_name, to_start, to_end) = two_dynasties

    same = _network_nodes(app, ego, useDynasties=True,
                          fromDynasty=from_dy, toDynasty=from_dy)
    from_only = _network_nodes(app, ego, useDynasties=True,
                               fromDynasty=from_dy, toDynasty=-1)
    span = _network_nodes(app, ego, useDynasties=True,
                          fromDynasty=from_dy, toDynasty=to_dy)
    everything = _network_nodes(app, ego, useDynasties=True,
                                fromDynasty=-2, toDynasty=-2)

    # The same span, with the four numbers the page leaves out.  This is
    # the control: if it behaves, the handler is right and the request
    # was wrong.
    repaired = _network_nodes(app, ego, useDynasties=True,
                              fromDynasty=from_dy, toDynasty=to_dy,
                              fromDynastyBegin=from_start,
                              fromDynastyEnd=from_end,
                              toDynastyBegin=to_start,
                              toDynastyEnd=to_end)

    measured = (f"{from_name} ({from_start}-{from_end}) to {to_name} "
                f"({to_start}-{to_end}): "
                f"unfiltered={unfiltered}, one dynasty={same}, "
                f"from only={from_only}, span={span}, "
                f"All Dynasties={everything}, span repaired={repaired}")

    assert same > 0, f"even a single dynasty returns nothing: {measured}"

    # The subject of this test is the *page*, so the page is what it
    # judges.  The numbers above establish that the four fields matter
    # -- 1 person without them, 438 with -- but a test that only drove
    # the handler could not tell "the page was fixed" from "the page is
    # still broken": the fix D-008 asks for changes what the page sends,
    # and hand-built request bodies are not what the page sends.  So the
    # decision is taken on the request the page builds, and the driven
    # numbers are the reason it is worth taking.
    missing = _fields_missing_from_the_networks_query(app.layout)

    if missing:
        raise KnownShippedDefect(
            f"the Networks page builds its query without {sorted(missing)}, "
            "which is what buildDynastyConditions filters on.  Measured "
            "against person " + str(ego) + ": " + measured
            + ".  'All Dynasties' answers HTTP 500 (-1 above); a span of "
            "two dynasties collapses because the year bounds arrive as 0; "
            "and From-only barely filters at all, because `c_end > 0` is "
            "true of all but five of the eighty-five dynasties.  Supplying "
            "the four year fields the page computes but never sends repairs "
            "the span, which is where the fix belongs")

    # Past this point the page sends the four fields, so `repaired` is
    # the request the page now makes and `span` is one it no longer
    # makes.  Only `repaired` may be asserted on: judging `span` here
    # would fail a correctly fixed build and blame the handler for a
    # body the page had stopped sending.
    assert same <= repaired <= unfiltered, (
        f"the page now sends the year bounds and a two-dynasty span is not "
        f"between one dynasty and no filter: {measured}")
    assert everything != -1, f"'All Dynasties' still answers HTTP 500: {measured}"
    assert everything >= repaired, (
        f"'All Dynasties' returned fewer people than a two-dynasty span: "
        f"{measured}")

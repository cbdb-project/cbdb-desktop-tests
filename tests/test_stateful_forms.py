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

import base64
import re
from collections import Counter

import pytest

from cbdb_desktop import gosource
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

#: A kinship traversal small enough to run several times in one test
#: and wide enough to produce an export worth comparing.
_KINSHIP_QUERY = {"maxUp": 2, "maxDown": 2, "maxCol": 2, "maxMarr": 2,
                  "mourningCircle": False}


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


def _kinship_export_files(app: CbdbApp) -> dict[str, str]:
    """``{filename: contents}`` from one *Export Query Results*.

    The handler answers a JSON envelope of ``{Name, URL}`` where each
    URL is a base64 ``data:`` payload -- three files, one per table it
    reads.  Unpacked here so a caller can say *which* file changed
    rather than only that the bundle did.
    """
    got = app.json("POST", "/api/kinship/export-results", json={})
    files = got.get("files") or got.get("Files") or []
    assert files, (
        f"the Kinship export returned no files: {str(got)[:200]}")
    out = {}
    for entry in files:
        name = entry.get("Name") or entry.get("name")
        url = entry.get("URL") or entry.get("url") or ""
        head, _, payload = url.partition(",")
        assert head.endswith(";base64"), (
            f"the Kinship export no longer base64-encodes {name}: its "
            f"URL begins {head!r}.  Decoding it as base64 anyway would "
            "compare two pieces of garbage, which can differ or agree "
            "for reasons that have nothing to do with this test")
        out[name] = base64.b64decode(payload).decode("utf-8", "replace")
    return out


def test_looking_a_person_up_does_not_discard_a_kinship_result(
        app: CbdbApp, egos, clean_lists):
    """Reading somebody's kinship in the Browser is not a read.

    ``GET /api/browser/person/{id}/kinship`` begins by deleting
    ``ZZ_KIN_LIST``, ``ZZ_KIN_LIST_TMP``, ``ZZ_SCRATCH_KIN`` and
    ``ZZ_SCRATCH_KINNET``.  Two of those are where the Kinship form's
    own query puts its answer, and ``handleExportResults`` is the one
    export that reads them back out of the database rather than from
    what the page sends it.  So a researcher who has a Kinship result
    on screen and then looks somebody up in the Browser exports a
    different network from the one they are looking at, and nothing
    says so.

    Note which file is *not* in that list.  The export is three files:
    ``KinshipNetwork`` from ``ZZ_SCRATCH_KINNET``, ``EgoRelativeKinship``
    from ``ZZ_SCRATCH_KIN``, and ``KinshipPeople`` from
    ``ZZ_SP_KINSHIP`` -- which the browser handler never touches.  The
    bundle therefore comes back describing two different people, which
    is why this test compares the files one at a time.

    The new *Export Profile* button makes all of this reachable without
    visiting a kinship tab at all; that half is checked from the page
    source by ``test_export_profile_loads_the_kinship_tab_it_lists``,
    because no test here presses a button.

    Judged by the application's own two answers to the same request,
    with no prediction of what a Kinship export should contain.  The
    re-query at the end separates *replaced* from *corrupted*: if the
    result comes back on a fresh query, the tables were emptied and
    refilled by somebody else's traversal rather than damaged.
    """
    app.post("/api/kinship/set-person", json={"personId": egos[0]})
    result = app.json("POST", "/api/kinship/query", json=_KINSHIP_QUERY)
    assert result.get("kinRecords"), (
        f"person {egos[0]} has no kin at this depth, so there is no "
        "result for a browser lookup to discard and this test would "
        "pass without checking anything")

    before = _kinship_export_files(app)

    # The user looks somebody else up -- or presses Export Profile,
    # which does this for them.
    other = next(p for p in egos[1:] if p != egos[0])
    looked = app.get(f"/api/browser/person/{other}/kinship")
    assert looked.status_code == 200, (
        f"the Browser could not show person {other}'s kinship (HTTP "
        f"{looked.status_code}), so this test cannot say what such a "
        "lookup does to the Kinship form")

    after = _kinship_export_files(app)

    changed = sorted(name for name in set(before) | set(after)
                     if before.get(name) != after.get(name))
    if changed:
        kept = sorted((set(before) & set(after)) - set(changed))
        restored = app.json("POST", "/api/kinship/query", json=_KINSHIP_QUERY)
        # Characters of the decoded file, not bytes: the names are
        # Chinese and the files carry a BOM, so the two differ and
        # only one of them is what this test actually measured.
        sizes = ", ".join(
            f"{name} {len(before.get(name, '')):,}->{len(after.get(name, '')):,}"
            for name in changed)
        raise KnownShippedDefect(
            f"a Kinship result is discarded by looking someone up in "
            f"the Browser.  The form had a result for person "
            f"{egos[0]}; after GET /api/browser/person/{other}/kinship "
            f"its Export Query Results answers HTTP 200 with different "
            f"content in {changed} ({sizes} characters), and nothing on "
            f"either page says the result changed.  handleGetKinship "
            f"opens by deleting ZZ_KIN_LIST, ZZ_KIN_LIST_TMP, "
            f"ZZ_SCRATCH_KIN and ZZ_SCRATCH_KINNET, which is where the "
            f"Kinship form's query put its answer.  "
            + (f"{kept} came back unchanged, because it is read from "
               f"ZZ_SP_KINSHIP, which that handler does not delete -- "
               f"so the bundle the user downloads describes two "
               f"different people at once.  "
               if kept else
               "Every file in the bundle changed.  ")
            + f"Re-running the Kinship query returns "
            f"{len(restored.get('kinRecords') or []):,} kinRecords, so "
            f"the result was replaced rather than damaged: the user is "
            f"exporting somebody else's traversal.  The five other "
            f"Kinship exports build their rows from the records the "
            f"page posts to them and read no scratch table, so they "
            f"are unaffected; this is Export Query Results alone.")

    assert after == before, (
        "unreachable: the KnownShippedDefect above covers every "
        "difference, and this is here so that a build which stops "
        "discarding the result passes rather than merely not raising")


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
#: The association categories are added per request from the build --
#: see ``gosource.all_categories_on`` -- because since the 2026-09-15
#: build ticking none of them means "no association ties" rather than
#: "no filter", and a network with no association ties is not the
#: network these tests are about.
_NETWORK_BASE = {
    "usePersonID": True, "useKin": True, "useNonKin": True,
    "useMale": True, "useFemale": True, "maxLoop": 1, "maxNodeDist": 1,
    "kinParam": True, "maxUp": 1, "maxDwn": 1, "maxCol": 1, "maxMar": 1,
}

#: The key the Networks page now sends its dynasty choice under, since
#: the shared picker became multi-select.  The four year fields the page
#: used to compute and drop -- ``fromDynastyBegin`` and friends -- are
#: gone from both sides, together with the ``DYNASTIES_1.c_end >`` /
#: ``c_start <`` arithmetic in ``buildDynastyConditions`` that consumed
#: them; the condition is now ``BIOG_MAIN_1.c_dy IN (...)``.
_DYNASTY_KEY = "dynastyCodes"

#: The page-scoped variable the shared picker's callback fills, and
#: therefore the only place a user's choice can come from.
_DYNASTY_SOURCE = "selectedDynasties"


def _networks_query_payload(layout) -> dict[str, str]:
    """``{key: the expression it is assigned}`` for the Networks query.

    Read off the payload object, not off the page as a whole.  A plain
    substring search over the template reports a name the page merely
    *computes* as a name the page sends -- which is how the version of
    this test written for the previous build had to work, and why it
    said so at length.  The page has one query payload,
    ``const params={...}`` immediately followed by
    ``JSON.stringify(params)``, and this returns each of its keys with
    the expression assigned to it.

    The *expression*, not just the key, because a key alone proves
    nothing about the value: ``dynastyCodes: []`` satisfies "the page
    sends dynastyCodes" while silently discarding whatever the user
    chose, and the requests this test then builds by hand would go on
    proving the handler works.
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

    return {key: value.strip().rstrip(",")
            for key, value in re.findall(r"^\s*(\w+)\s*:([^\n]*)", body,
                                         re.MULTILINE)}


def _network_nodes_raw(app: CbdbApp, ego: int, **extra) -> list[dict]:
    """The ``nodeRecords`` of one Networks query, or ``[]`` on an error."""
    app.post("/api/networks/set-person", json={"personId": ego})
    response = app.post("/api/networks/query",
                        json=dict(_NETWORK_BASE,
                                  **gosource.all_categories_on(app.layout),
                                  **extra))
    if response.status_code != 200:
        return []
    return response.json()["nodeRecords"]


def _network_dynasties(app: CbdbApp, ego: int, **extra) -> tuple[int, set]:
    """``(node count, dynasty codes of everyone but the ego)``.

    ``-1`` for the count when the query errored, so a 500 is a
    measurement rather than an exception with the diagnosis nowhere.
    """
    app.post("/api/networks/set-person", json={"personId": ego})
    response = app.post("/api/networks/query",
                        json=dict(_NETWORK_BASE,
                                  **gosource.all_categories_on(app.layout),
                                  **extra))
    if response.status_code != 200:
        return -1, set()
    nodes = response.json()["nodeRecords"]
    return (len({row["personId"] for row in nodes}),
            {row.get("dy") for row in nodes
             if row.get("personId") != ego})


def test_the_networks_page_sends_the_dynasty_choice_its_handler_reads(
        app: CbdbApp, clean_lists):
    """Pick dynasties on the Networks form and see what arrives.

    Networks is the one form with a dynasty filter that the discovered
    matrix does not cover, because its result is a traversal rather than
    a filtered table -- so this is where that filter is driven.

    Both halves are checked, and they fail differently.  The *page* half
    is the request it builds: the shared picker hands back an array and
    the page has to send it under the key the handler decodes, or the
    filter silently receives nothing.  The *handler* half is what comes
    back: every node the traversal admits must be of a dynasty that was
    asked for, and widening the selection may add people but may never
    lose any.

    Union **is** asserted, and the reason it can be is particular to
    this form and to this depth -- the body of the test says it at the
    assertion, because getting it wrong in either direction costs a
    round.  In short: the condition constrains the node being admitted,
    so at a depth where the walk passes *through* one person to reach
    another, union would fail on a correct build; this request is depth
    one, where the second loop adds edges and never nodes.
    """
    # SUBJECT rather than a discovered ego: judging a filter needs a
    # network big enough for "narrower" to mean something, and this is
    # the person the suite already fixes for that reason (subjects.py,
    # whose existence test_staging.py checks against the shipped data).
    ego = SUBJECT

    sent = _networks_query_payload(app.layout)
    assert _DYNASTY_KEY in sent, (
        f"the Networks page builds its query without `{_DYNASTY_KEY}`, "
        "which is the only dynasty field its handler decodes, so a "
        "dynasty chosen in the picker reaches the server as nothing at "
        f"all and the filter is silently skipped.  The payload sends: "
        f"{sorted(sent)}")
    # And it must send the user's selection, not a constant.  The
    # variable the picker's callback fills is the only thing that can
    # carry a choice; `dynastyCodes: []` would satisfy the key check
    # above while throwing the selection away.
    assert _DYNASTY_SOURCE in sent[_DYNASTY_KEY], (
        f"the Networks page sends `{_DYNASTY_KEY}: {sent[_DYNASTY_KEY]}`, "
        f"which does not read `{_DYNASTY_SOURCE}` -- the variable the "
        "dynasty picker's callback fills.  Whatever the user chooses, "
        "that request carries something else")

    unfiltered, present = _network_dynasties(app, ego, useDynasties=False)
    assert unfiltered > 100, (
        f"person {ego} returns only {unfiltered} people at depth 1; too "
        "small a network to tell a working filter from a broken one")

    # The two dynasties are read out of the *unfiltered answer* -- the
    # application's own account of who is in this network -- and then
    # confirmed one at a time.  Choosing them from DYNASTIES by year
    # overlap, as the From/To version of this test did, picks codes that
    # may contribute nobody: measured on this ego, the overlapping
    # dynasty returned the ego and nothing else, so every assertion
    # about *two* dynasties passed without the second one doing
    # anything.
    counts = Counter(row.get("dy") for row in _network_nodes_raw(app, ego)
                     if row.get("personId") != ego)
    ranked = [dy for dy, _n in counts.most_common() if dy]
    if len(ranked) < 2:
        pytest.skip(
            f"person {ego}'s network spans fewer than two dynasties "
            f"({counts}), so a two-dynasty selection cannot be judged")
    from_dy, to_dy = ranked[0], ranked[1]

    one, one_seen = _network_dynasties(
        app, ego, useDynasties=True, dynastyCodes=[from_dy])
    other, other_seen = _network_dynasties(
        app, ego, useDynasties=True, dynastyCodes=[to_dy])
    both, both_seen = _network_dynasties(
        app, ego, useDynasties=True, dynastyCodes=[from_dy, to_dy])
    empty, _ = _network_dynasties(
        app, ego, useDynasties=True, dynastyCodes=[])

    measured = (f"ego {ego}: unfiltered={unfiltered}, "
                f"dynasty {from_dy}={one}, dynasty {to_dy}={other}, "
                f"both={both}, empty selection={empty}")

    # ``> 1``, not ``> 0``: the ego is in nodeRecords whatever the filter
    # does, so ``> 0`` is true by construction and the message it carries
    # -- "nobody but the ego" -- describes the case it lets through.
    assert one > 1 and other > 1, (
        f"a single dynasty returned nobody but the ego, although both "
        f"were read out of the unfiltered answer: {measured}")

    # The per-node half: what came back, against what was asked for.
    # This is the assertion that catches a condition bound to the wrong
    # alias or to the wrong person -- the shape this form has had before.
    assert one_seen <= {from_dy}, (
        f"asking for dynasty {from_dy} alone returned nodes of "
        f"{sorted(one_seen - {from_dy})} as well.  {measured}")
    assert other_seen <= {to_dy}, (
        f"asking for dynasty {to_dy} alone returned nodes of "
        f"{sorted(other_seen - {to_dy})} as well.  {measured}")
    assert both_seen <= {from_dy, to_dy}, (
        f"asking for dynasties {from_dy} and {to_dy} returned nodes of "
        f"{sorted(both_seen - {from_dy, to_dy})} as well.  {measured}")

    # Union, and it is worth saying exactly why it is assertable here
    # when the discovered matrix asserts the same shape for the six
    # read-only forms and this form looks like it should not.
    #
    # The dynasty condition constrains BIOG_MAIN_1, the node being
    # admitted.  At a depth where the walk can pass *through* one
    # person to reach another, a node reachable only via someone of the
    # second dynasty would appear under the pair and under neither
    # single code, and union would fail on a correct build.  This
    # request is depth one: ``maxNodeDist`` is 1, so ``loopLimit`` is 2,
    # loop 1 admits the ego's direct associates, and loop 2 is the
    # closure pass -- whose FROM (``fromAssocLast``) joins
    # ``ZZ_SP_NETWORK`` to itself on both endpoints and therefore adds
    # edges between people already admitted, never new people.  So at
    # this depth the node sets really are a partition by dynasty, and
    # the strongest available oracle is the exact one.
    assert both_seen == (one_seen | other_seen), (
        f"the nodes admitted for both dynasties are not the union of "
        f"the nodes admitted for each: only in the pair "
        f"{sorted(both_seen - (one_seen | other_seen))}, missing from it "
        f"{sorted((one_seen | other_seen) - both_seen)}.  {measured}")
    assert both == one + other - 1, (
        f"two dynasties returned {both} people, and the two single "
        f"selections returned {one} and {other} -- which share only the "
        f"ego, so the pair should return {one + other - 1}.  {measured}")

    # Widening cannot exceed no filter at all.
    assert both <= unfiltered, (
        f"two dynasties returned more people than no filter: {measured}")

    # An empty selection is "All Dynasties" -- the page's own Clear
    # button -- and adds no condition, so it must match no filter at
    # all.  The previous build sent a -2 sentinel here and answered
    # HTTP 500; -1 is how _network_dynasties reports that.
    assert empty == unfiltered, (
        f"an empty dynasty selection is All Dynasties and must equal an "
        f"unfiltered query: {measured}")

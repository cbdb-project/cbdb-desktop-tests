"""The stored-person list: the one way a result travels between forms.

Ten forms can hand their result to another form, and they all do it
through one global table, ``ZZ_STORE_PERSON_ID``.  A user runs a query
on Office, presses *Store Person IDs*, opens Networks, presses *Recall*,
and the people they found are the people Networks now works on.  That
round trip is the only cross-form channel the application has, and until
this file nothing drove most of it: the endpoint gate reported fourteen
endpoints a user can reach that no test had ever requested, and ten of
them were this channel.

Why they went undriven is worth saying, because it is not laziness.
Each one on its own looks trivial -- ``{"personIds": [...]}`` in, a
status out -- and a test that posts a list and asserts 200 proves
nothing that reading the handler would not have told you.  What is
*not* trivial is the property the endpoints exist for, and it cannot be
seen from any one of them:

    what one form stores is what another form recalls.

That is a cross-endpoint agreement, which is an oracle this suite
allows, and it needs both halves of the channel to be driven together.
Every test below is a round trip for that reason.  None of them
predicts a row count from the database, and none reproduces a handler's
SQL.

Three further things this file pins, each learned from the source:

* **The refusal, and the way past it.**  Kinship and Networks answer
  409 when the stored list is not empty; the other eight overwrite it
  without asking.  The two that refuse offer a ``/confirmed`` endpoint
  which is what the page calls after the user agrees.  Both halves are
  driven -- the refusal *and* the confirmation -- because a refusal
  nobody can get past is a broken feature, and a confirmation that
  works when nothing refused is not the feature at all.

* **What the two refusing forms store is their query result.**  Their
  store endpoints do not read the request body at all: Networks copies
  ``ZZ_SP_NETWORK``, and Kinship copies ``ZZ_SP_KINSHIP`` *together
  with* the egos in ``ZZ_SCRATCH_KIN``, so its stored list can be
  larger than its ``peopleRecords``.  Worth knowing before writing an
  assertion about either.

* **Recall is a copy, not a move.**  ``handleRecallPersonIDs`` inserts
  from ``ZZ_STORE_PERSON_ID`` into the form's own working list and does
  not clear the source.  So a second form can recall the same people,
  which is asserted here rather than assumed: it is the difference
  between a channel and a hand-off, and a change to it would be
  invisible to any test of one form.

* **``PersonIDSource.SourceForm`` is written by all ten and read by
  nothing.**  Every store handler stamps its form's name into that
  column, and no ``SELECT`` of it exists in ``Code/`` or in any
  template.  Noted here and nowhere else -- no test in this file reads
  that column, and saying one did would be worse than saying nothing.
  It is not filed either: a column with no consumer costs a user
  nothing today, and the VBA original it came from is where the reader
  used to be.
"""
from __future__ import annotations

import re

import pytest

from cbdb_desktop.app import CbdbApp
from cbdb_desktop.defects import KnownShippedDefect
from cbdb_desktop.forms import STORE_RESET, WORKING_LIST_RESETS
from cbdb_desktop.routes import all_routes

pytestmark = pytest.mark.app


# ---------------------------------------------------------------------------
# the inventory, and the gate that keeps it honest
# ---------------------------------------------------------------------------
#
# Written out, because pytest needs them at collection time to
# parametrise -- and then checked against the shipped route table by
# `test_the_channel_is_the_one_the_build_registers` below, which is the
# same arrangement `test_zz_controls.py` uses for its button and
# endpoint counts.  The list is for addressing; the build is the
# authority.  Without that gate this file would be a hand-kept list
# claiming to be an inventory, and a ninth store endpoint would appear
# in neither.

#: ``form label -> endpoint that overwrites ZZ_STORE_PERSON_ID without
#: asking``.  The spelling is not uniform, which is a large part of why
#: six of these went undriven: Status owns the unprefixed
#: ``/api/store-person-ids``, and Group Data and Association Pairs say
#: ``store-ids`` where the rest say ``store-person-ids``.
STORE_ENDPOINTS = {
    "associations": "/api/associations/store-person-ids",
    "assocpairs": "/api/assocpairs/store-ids",
    "entry": "/api/entry/store-person-ids",
    "groupdata": "/api/groupdata/store-ids",
    "office": "/api/office/store-person-ids",
    "places": "/api/places/store-person-ids",
    "status": "/api/store-person-ids",
    "texts": "/api/texts/store-person-ids",
}

#: The two forms that refuse to overwrite a non-empty stored list, and
#: the endpoint each offers to do it anyway.  Ten forms write the
#: shared list in total: these two and the eight above.
CONFIRMING_FORMS = {
    "kinship": ("/api/kinship/store-person-ids",
                "/api/kinship/store-person-ids/confirmed"),
    "networks": ("/api/networks/store-person-ids",
                 "/api/networks/store-person-ids/confirmed"),
}

#: Forms that can pull the stored list into their own working list.
RECALL_ENDPOINTS = {
    "kinship": "/api/kinship/recall-person-ids",
    "networks": "/api/networks/recall-person-ids",
}


@pytest.fixture
def clean_channel(app: CbdbApp):
    """Empty every working list and the stored list, before and after."""
    def reset():
        for path, body in WORKING_LIST_RESETS:
            app.post(path, json=body)
        app.post(STORE_RESET[0], json=STORE_RESET[1])

    reset()
    yield
    reset()


@pytest.fixture(scope="module")
def travellers(sqlite_conn) -> list[int]:
    """Five real people to send through the channel.

    Chosen from the data rather than written down: recall joins
    ``BIOG_MAIN`` to build the working-list row, so an id the table does
    not have would be dropped on the way through and the count would
    disagree for a reason that has nothing to do with the channel.
    """
    people = [row[0] for row in sqlite_conn.execute(
        "SELECT c_personid FROM BIOG_MAIN "
        "WHERE c_name IS NOT NULL AND c_name <> '' "
        "ORDER BY c_personid LIMIT 5")]
    assert len(people) == 5, people
    return people


def _working_list_size(app: CbdbApp, form: str) -> int:
    return app.json("GET", f"/api/{form}/person-count")["count"]


#: The smallest query each confirming form accepts, and the key in its
#: answer that carries the people it found.  Minimal on purpose: these
#: are graph walks with no server-side cap, and this test needs a
#: non-empty result, not a large one.
_SMALLEST_QUERY = {
    "kinship": ({"maxUp": 1, "maxDown": 1, "maxCol": 1, "maxMarr": 1,
                 "mourningCircle": False}, "peopleRecords"),
    "networks": ({"usePersonID": True, "useKin": True, "useNonKin": True,
                  "useMale": True, "useFemale": True, "maxLoop": 1,
                  "maxNodeDist": 1, "kinParam": True, "maxUp": 1,
                  "maxDwn": 1, "maxCol": 1, "maxMar": 1}, "nodeRecords"),
}


def _run_a_query(app: CbdbApp, form: str) -> int:
    """Run the form's own query and return how many people it found."""
    body, key = _SMALLEST_QUERY[form]
    answer = app.json("POST", f"/api/{form}/query", json=body)
    return len({row["personId"] for row in answer[key]})


# ---------------------------------------------------------------------------
# the round trip
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("form", sorted(STORE_ENDPOINTS))
def test_what_one_form_stores_another_form_recalls(
        app: CbdbApp, form: str, travellers, clean_channel):
    """Store on each of the eight forms; recall on Networks and Kinship.

    This is the whole point of the endpoint: the user's result leaving
    one form and arriving in another.  Asserting it needs both ends, and
    the assertion is agreement between two of the application's own
    outputs -- the list that went in against the working-list count that
    comes out -- not a number this suite worked out for itself.

    Both recalling forms are checked on every store, which is what
    establishes that recall *copies*.  If it moved the rows, the second
    recall would find an empty list and the count would be zero; that it
    is not is the difference between a shared channel and a hand-off,
    and neither the store handler nor either recall handler says which
    one it is when read on its own.
    """
    stored = app.post(STORE_ENDPOINTS[form], json={"personIds": travellers})
    assert stored.status_code == 200, (
        f"{form} could not store a list of {len(travellers)} people: "
        f"HTTP {stored.status_code} {stored.text[:200]}")

    for recalling, endpoint in sorted(RECALL_ENDPOINTS.items()):
        recalled = app.post(endpoint, json={})
        assert recalled.status_code == 200, (
            f"{recalling} could not recall the list {form} stored: "
            f"HTTP {recalled.status_code} {recalled.text[:200]}")

        arrived = _working_list_size(app, recalling)
        assert arrived == len(travellers), (
            f"{form} stored {len(travellers)} people and {recalling} "
            f"recalled {arrived}.  These are the two ends of the only "
            "channel between forms, so a disagreement here is a result "
            "that changes on its way from the form that found it to the "
            "form that uses it")

    # The people, not only how many of them.  A count agreeing at both
    # ends would still agree if the channel delivered five *different*
    # real people, which is the failure worth catching: a result that
    # arrives with the right size and the wrong contents looks correct
    # everywhere it is displayed.
    #
    # The query is a superset -- it expands one step from each person it
    # was given -- so containment is what can be asserted, and it is
    # enough: substituting anybody would drop a traveller out of it.
    body, key = _SMALLEST_QUERY["networks"]
    reached = {row["personId"]
               for row in app.json("POST", "/api/networks/query", json=body)[key]}
    missing = sorted(set(travellers) - reached)
    assert not missing, (
        f"{form} stored {travellers} and querying from what Networks "
        f"recalled does not reach {missing}.  The count matched at both "
        "ends, so the channel is carrying the right number of the wrong "
        "people")


def test_recalling_does_not_empty_the_list_for_the_next_form(
        app: CbdbApp, travellers, clean_channel):
    """Recall twice, from two forms, and get the same people twice.

    Stated separately from the round trip above because it is a
    different claim about the same endpoints, and because it is the
    claim a future change is most likely to break: the obvious way to
    write "recall" is to move the rows.
    """
    app.post(STORE_ENDPOINTS["status"], json={"personIds": travellers})

    first = app.post(RECALL_ENDPOINTS["networks"], json={})
    second = app.post(RECALL_ENDPOINTS["kinship"], json={})
    assert first.status_code == second.status_code == 200, \
        f"{first.text[:150]} / {second.text[:150]}"

    assert _working_list_size(app, "networks") == len(travellers)
    assert _working_list_size(app, "kinship") == len(travellers), (
        "the second form to recall got a different list from the first; "
        "recall is emptying the stored list as it reads it, so only one "
        "form can ever receive a result")


def test_storing_an_empty_list_empties_the_channel(
        app: CbdbApp, travellers, clean_channel):
    """The documented way to clear it, driven rather than assumed.

    The eight handlers that take a list begin ``DELETE FROM
    ZZ_STORE_PERSON_ID`` and then insert whatever arrived, so an empty
    list is how the channel is cleared.  (Kinship and Networks are not
    among them: their store endpoints ignore the request body entirely
    and copy their own query result, which is why they are excluded
    here and driven separately below.)

    ``STORE_RESET`` in ``forms.py`` is exactly this call, and every test
    in this suite relies on it for isolation, so it is what gets driven
    -- not a sibling that happens to be nearby.  An earlier version of
    this test cleared through Status while claiming to protect the
    Places call that ``STORE_RESET`` actually makes; the two are
    separate implementations and one can break without the other.
    """
    reset_endpoint, reset_body = STORE_RESET
    app.post(reset_endpoint, json={"personIds": travellers})
    app.post(RECALL_ENDPOINTS["networks"], json={})
    assert _working_list_size(app, "networks") == len(travellers)

    emptied = app.post(reset_endpoint, json=reset_body)
    assert emptied.status_code == 200, emptied.text[:200]

    app.post(RECALL_ENDPOINTS["networks"], json={})
    assert _working_list_size(app, "networks") == 0, (
        "storing an empty list left people in the channel; STORE_RESET "
        "no longer resets, and every test that depends on it is now "
        "inheriting state instead of starting clean")


# ---------------------------------------------------------------------------
# the refusal, and the way past it
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("form", sorted(CONFIRMING_FORMS))
def test_the_form_that_refuses_to_overwrite_offers_a_way_to_agree(
        app: CbdbApp, form: str, travellers, clean_channel):
    """409 when the list is occupied, and ``/confirmed`` to proceed.

    Kinship and Networks differ from the other eight here, and the
    asymmetry is deliberate enough to be worth holding in place: they
    ask before discarding somebody's stored result.  The page turns the
    409 into a prompt and calls ``/confirmed`` when the user agrees.

    Driving only the refusal would leave the more interesting half
    untested -- a confirmation endpoint that does not actually overwrite
    would strand the user at a dialogue that never completes, and the
    409 would look like correct behaviour throughout.  So both are
    driven, in the order the user meets them.
    """
    plain, confirmed = CONFIRMING_FORMS[form]

    # What these two forms store is the people their *query* found --
    # `ZZ_SP_NETWORK` / `ZZ_SP_KINSHIP`, the result table -- and not the
    # working list that was fed in.  That is the right behaviour and it
    # is easy to get wrong from the outside: the first version of this
    # test imported people and expected them back, which stored nothing
    # and looked exactly like a broken confirmation.  So a query is run
    # first, and how many people it found is read from its own answer.
    app.post(f"/api/{form}/set-person", json={"personId": travellers[1]})
    found = _run_a_query(app, form)
    assert found, (
        f"the {form} query returned nobody, so there is nothing for "
        "Store Person IDs to store and this test would pass on a broken "
        "confirmation")

    # Something else is already in the channel, which is the condition
    # the refusal is about.
    app.post(STORE_ENDPOINTS["status"], json={"personIds": travellers})

    refused = app.post(plain, json={})
    assert refused.status_code == 409, (
        f"{form} overwrote an occupied stored list without asking: HTTP "
        f"{refused.status_code}.  The other eight forms do that by design; "
        "these two are the ones that are supposed to ask first")

    agreed = app.post(confirmed, json={})
    assert agreed.status_code == 200, (
        f"{form} refused with 409 and then would not accept the "
        f"confirmation either: HTTP {agreed.status_code} "
        f"{agreed.text[:200]}.  A user who agrees to the prompt has no "
        "way through")

    # The reply's count is read back out of the table by the handler, so
    # it is worth comparing against -- and then confirmed independently
    # through the other end of the channel, which is the check that does
    # not depend on the handler being honest about its own work.
    assert agreed.json().get("count") == found, (
        f"{form} confirmed a store of {found} people and reported "
        f"{agreed.json().get('count')}")

    app.post(RECALL_ENDPOINTS["networks"], json={})
    after = _working_list_size(app, "networks")
    assert after == found, (
        f"{form} accepted the confirmation and the channel holds "
        f"{after} people rather than the {found} its query found; the "
        "prompt completes and does nothing")


# ---------------------------------------------------------------------------
# the other two ways a working list gets filled
# ---------------------------------------------------------------------------

def test_the_association_pairs_query_runs_on_the_list_it_was_given(
        app: CbdbApp, sqlite_conn, clean_channel):
    """``import-list`` fills the list; ``useList`` makes the query read it.

    There is no count endpoint for this form's working list, so the only
    honest way to see what ``import-list`` did is to ask the query that
    consumes it.  Two different lists are imported in turn and the two
    answers compared: if the query ignored the list, or the second
    import did not replace the first, the two answers would be equal.
    Comparing them to *each other* is what makes this checkable without
    predicting either -- no count is asserted, and no association is
    worked out in Python.

    The people are chosen from ``ASSOC_DATA`` for having a few
    associations each: a person with none would give an empty answer
    both times, and two empty answers are equal for a reason that says
    nothing about the endpoint.
    """
    candidates = [row[0] for row in sqlite_conn.execute(
        "SELECT c_personid FROM ASSOC_DATA GROUP BY c_personid "
        "HAVING COUNT(*) BETWEEN 3 AND 10 ORDER BY c_personid LIMIT 6")]
    assert len(candidates) >= 4, candidates
    first, second = candidates[:2], candidates[2:4]

    def answer_for(people: list[int]) -> tuple[int, ...]:
        imported = app.post("/api/assocpairs/import-list",
                            json={"personIds": people})
        assert imported.status_code == 200, imported.text[:200]
        result = app.json("POST", "/api/assocpairs/query", json={"useList": True})
        return tuple(sorted(row["personId"] for row in result["people"]))

    from_first = answer_for(first)
    from_second = answer_for(second)

    assert from_first, f"importing {first} and querying returned nobody"
    assert from_second, f"importing {second} and querying returned nobody"
    assert from_first != from_second, (
        f"two different imported lists, {first} and {second}, gave the "
        f"same answer {from_first}.  Either the query is not reading the "
        "working list or the second import did not replace the first, and "
        "a user's second search would be showing them their first")

    cleared = app.post("/api/assocpairs/clear-list", json={})
    assert cleared.status_code == 200, cleared.text[:200]
    emptied = app.json("POST", "/api/assocpairs/query", json={"useList": True})
    assert not emptied["people"], (
        "the query still found people after the list was cleared, so what "
        "it reads is not what Clear empties")


def test_rerun_seeds_the_working_list_with_the_people_the_query_found(
        app: CbdbApp, travellers, clean_channel):
    """*Rerun Last Query* is a step outward, not a repeat.

    The button's name says one thing and the endpoint does another, and
    the two together are coherent once read as a pair: ``/rerun`` copies
    the *result* of the last query into the working list, and the page
    then calls ``/query`` again -- so the second query walks outward
    from everybody the first one found.  That is how a user grows a
    network a step at a time.

    What is checked is the join between the two halves: the number
    ``/rerun`` reports is the number the query found, and the working
    list afterwards holds exactly that many.  Both come from the
    application's own endpoints; nothing here predicts how large a
    network ought to be.
    """
    app.post("/api/networks/set-person", json={"personId": travellers[1]})
    found = _run_a_query(app, "networks")
    assert found > 1, (
        f"the seed query found {found} people; with nothing to expand "
        "from, this test would pass on a rerun that did nothing")

    rerun = app.post("/api/networks/rerun", json={})
    assert rerun.status_code == 200, \
        f"rerun failed: HTTP {rerun.status_code} {rerun.text[:200]}"
    # `rerun` reports RowsAffected and `person-count` is COUNT(*) of the
    # same table, so comparing those two to each other could not fail.
    # What can fail, and is the property the button promises, is that
    # the working list ends up holding the people the *query* found --
    # measured against the query's own answer, one endpoint against
    # another.
    assert rerun.json()["count"] == found, (
        f"the query found {found} people and rerun took "
        f"{rerun.json()['count']} of them into the working list")

    seeded = _working_list_size(app, "networks")
    assert seeded == found, (
        f"the query found {found} people and the working list now holds "
        f"{seeded}; the next query would expand from a different set of "
        "people than the one the user was shown")

    # And the people themselves, not merely how many: re-querying from
    # the seeded list must reach at least everybody the first query
    # found, since each of them is now a starting point.
    again = _run_a_query(app, "networks")
    assert again >= found, (
        f"expanding from {found} people reached {again}, fewer than "
        "started; rerun seeded the working list with somebody else")


def test_the_channel_is_the_one_the_build_registers(layout):
    """The three lists above, against the shipped route table.

    The lists exist so pytest can parametrise on them at collection
    time; this is what stops them drifting from the application.  Both
    directions are checked, and the second is the one that matters: an
    endpoint the build has and this file does not is a part of the
    channel nothing drives, which is exactly the state the fourteen
    undriven endpoints were in before this file was written.
    """
    registered = {route.path for route in all_routes(layout)
                  if route.path.startswith("/api/") and "{" not in route.path}

    def tails(*suffixes):
        return {path for path in registered
                if any(path.endswith(s) for s in suffixes)}

    stores = tails("/store-person-ids", "/store-ids") | {"/api/store-person-ids"}
    stores &= registered
    confirmed = tails("/store-person-ids/confirmed")
    stores -= confirmed
    recalls = tails("/recall-person-ids")

    listed_stores = set(STORE_ENDPOINTS.values())
    listed_stores |= {plain for plain, _ in CONFIRMING_FORMS.values()}

    assert listed_stores == stores, (
        "the set of endpoints that write the shared person list has "
        f"changed.  In the build and not here: {sorted(stores - listed_stores)}; "
        f"here and not in the build: {sorted(listed_stores - stores)}")
    assert {c for _, c in CONFIRMING_FORMS.values()} == confirmed, (
        f"the confirmation endpoints have changed: build {sorted(confirmed)}, "
        f"this file {sorted(c for _, c in CONFIRMING_FORMS.values())}")
    assert set(RECALL_ENDPOINTS.values()) == recalls, (
        f"the recall endpoints have changed: build {sorted(recalls)}, "
        f"this file {sorted(RECALL_ENDPOINTS.values())}")


# ---------------------------------------------------------------------------
# what a list of people is allowed to contain
# ---------------------------------------------------------------------------

#: The four endpoints that take a list of person ids and say how many
#: they accepted, and where each says it.  They were written separately
#: and they do not agree, which is what makes them checkable against
#: each other: three report what they found, one reports what it was
#: sent.
#:
#: "Accepted" rather than "loaded", because Group Data is not quite the
#: same kind of thing -- it validates the ids and hands back the records
#: it matched rather than filling a working list on the server.  Its
#: count is still an honest count of what it found, which is all this
#: comparison needs of it.
LIST_LOADERS = {
    "kinship": ("/api/kinship/import-people", "count"),
    "networks": ("/api/networks/import-people", "count"),
    "groupdata": ("/api/groupdata/import-ids", "count"),
    "assocpairs": ("/api/assocpairs/import-list", "count"),
}

#: The one that is known to answer with the size of the request.  Named,
#: so that a regression in one of its siblings is reported as its own
#: problem rather than swept into this finding: "some endpoint miscounts"
#: and "this endpoint miscounts" are different statements, and only the
#: second is what the registry entry says.
_COUNTS_THE_REQUEST = frozenset({"assocpairs"})


def test_a_list_loader_reports_how_many_people_it_loaded(
        app: CbdbApp, sqlite_conn, clean_channel):
    """Three of the four count rows; the fourth counts the request.

    Every one of these endpoints resolves the ids against ``BIOG_MAIN``,
    so an id the database does not have contributes nothing.  What each
    then tells the user differs, and the disagreement is the oracle:
    Kinship answers ``{"count": 2, "errorCount": 1}``, Networks reads
    ``COUNT(*)`` back out of its table, Group Data returns the records
    it matched -- and Association Pairs returns ``len(req.PersonIDs)``,
    which is the request handed back and would say three however many
    were loaded.

    Nothing here predicts a count.  One id is chosen to be absent by
    taking it past the largest the table holds, and the endpoints are
    then compared with each other.
    """
    real = [row[0] for row in sqlite_conn.execute(
        "SELECT c_personid FROM BIOG_MAIN ORDER BY c_personid LIMIT 2")]
    (absent,) = sqlite_conn.execute(
        "SELECT MAX(c_personid) + 9999 FROM BIOG_MAIN").fetchone()

    reported = {}
    for form, (endpoint, key) in sorted(LIST_LOADERS.items()):
        answer = app.json("POST", endpoint, json={"personIds": real + [absent]})
        reported[form] = answer.get(key)

    honest = {f: n for f, n in reported.items() if n == len(real)}
    inflated = {f: n for f, n in reported.items() if n != len(real)}

    assert honest, (
        f"every list loader reported {reported} for a list of "
        f"{len(real) + 1} ids of which {len(real)} exist; if they now all "
        "count the request, this test has lost the sibling it compares "
        "against and needs a different oracle")

    unexpected = sorted(set(inflated) - _COUNTS_THE_REQUEST)
    assert not unexpected, (
        f"{unexpected} reported {[inflated[f] for f in unexpected]} for a "
        f"list of {len(real) + 1} ids of which {len(real)} exist.  That is "
        "a different endpoint from the one this test reports, so it is a "
        "new finding and not the recorded one")

    if inflated:
        raise KnownShippedDefect(
            f"a list loader reports the size of the file rather than the "
            f"number of people it loaded: {inflated}, against "
            f"{sorted(honest)} which report {len(real)}.  One of the three "
            f"ids sent does not exist in BIOG_MAIN, so {len(real)} rows "
            "were inserted; the page prints the number it is given, so a "
            "historian importing an id list from an older CBDB release is "
            "told the whole list loaded and then silently queries a subset")


def test_importing_the_same_person_twice_imports_one_person(
        app: CbdbApp, sqlite_conn, clean_channel):
    """A list with a repeated id, through the working list and out again.

    ``ZZ_SIP_NETWORK`` is declared in the Go with ``UNIQUE
    (c_person_id)`` and every insert into it is ``INSERT OR IGNORE``, so
    the application clearly intends a person to appear once.  The
    shipped table has no such constraint -- ``CREATE TABLE IF NOT
    EXISTS`` against an existing table is a no-op, column list and
    constraints and all -- so the guard does nothing and the ignore has
    nothing to ignore.

    A repeated id is ordinary input: the page builds its list from a
    file one line at a time and does not deduplicate, which is how a
    person ends up in a network twice.

    Driven end to end rather than read off the schema, because what
    matters is not the constraint but what a user sees: the count under
    the list, the rows in the result, and every export taken from them.
    """
    (person,) = sqlite_conn.execute(
        "SELECT c_personid FROM BIOG_MAIN ORDER BY c_personid LIMIT 1").fetchone()

    def load_and_query(ids: list[int]) -> tuple[int, list[int]]:
        app.post("/api/networks/clear-person", json={})
        app.post("/api/networks/import-people", json={"personIds": ids})
        listed = _working_list_size(app, "networks")
        body, key = _SMALLEST_QUERY["networks"]
        rows = app.json("POST", "/api/networks/query", json=body)[key]
        return listed, [row["personId"] for row in rows]

    once_listed, once_people = load_and_query([person])
    twice_listed, twice_people = load_and_query([person, person])

    assert once_listed == 1 and once_people, (
        f"importing one person listed {once_listed} and found "
        f"{len(once_people)}; the comparison below needs a working "
        "single-person import")

    repeated = sorted({p for p in twice_people if twice_people.count(p) > 1})
    if twice_listed != 1 or repeated:
        raise KnownShippedDefect(
            f"importing person {person} twice left the working list "
            f"reporting {twice_listed} people, and the query returned "
            f"{len(twice_people)} rows for {len(set(twice_people))} people "
            f"-- {repeated} appearing more than once, against "
            f"{len(once_people)} rows and no repeats for the same import "
            "without the duplicate.  ZZ_SIP_NETWORK is declared UNIQUE "
            "(c_person_id) in networks_form_backend.go and the shipped "
            "table has no such constraint, so INSERT OR IGNORE ignores "
            "nothing.  The duplicate reaches the result and every export "
            "taken from it")


#: Store handlers that empty the shared list and refill it from the
#: request without a transaction around the pair.  Exact, and recorded
#: rather than filed: no user can see it without a crash arriving
#: between the two statements, and AGENTS.md is clear that a latent
#: problem does not belong in a report of things users can see.  It is
#: still worth holding in place -- the next handler written by copying
#: one of these should copy one of the seven that gets it right.
_STORES_WITHOUT_A_TRANSACTION = {
    "status_form_backend.go": "handleStorePersonIDs, which owns the "
                              "unprefixed /api/store-person-ids",
}


def test_a_handler_that_empties_the_shared_list_refills_it_atomically(layout):
    """``DELETE`` then ``INSERT``, and what happens in between.

    Eight handlers replace the shared person list with one the caller
    sent, and seven of them wrap the emptying and the refilling in a
    single ``h.db.Begin()`` with a deferred ``Rollback``.  The eighth
    runs both as bare ``h.db.Exec``, so the ``DELETE`` commits on its
    own: a failure part-way through the inserts leaves the user's
    previous result destroyed and the new one truncated, on the only
    channel the application has for moving a result between forms.

    The oracle is the other seven.  This is not a rule imposed from
    outside -- it is what this build already does everywhere else, and
    the one exception is what the pinned set records.
    """
    pattern = re.compile(
        r"func \(h \*\w+\) (?P<name>handleStorePersonIDs|handleStoreIDs)\b"
        r".*?\n\}", re.DOTALL)

    with_tx, without_tx = {}, {}
    for source in layout.go_sources():
        text = source.read_text(encoding="utf-8", errors="replace")
        for match in pattern.finditer(text):
            body = match.group(0)
            if "DELETE FROM ZZ_STORE_PERSON_ID" not in body:
                continue          # kinship and networks refuse instead
            target = with_tx if "h.db.Begin()" in body else without_tx
            target[source.name] = match.group("name")

    assert len(with_tx) + len(without_tx) == 8, (
        f"{len(with_tx) + len(without_tx)} handlers replace the shared "
        f"list, not 8: {sorted(with_tx) + sorted(without_tx)}")

    unexpected = sorted(set(without_tx) - set(_STORES_WITHOUT_A_TRANSACTION))
    assert not unexpected, (
        "a handler empties the shared person list and refills it without "
        f"a transaction, and this file has not judged it: {unexpected}.  "
        f"The {len(with_tx)} others use one; copy whichever was copied "
        "from")

    fixed = sorted(set(_STORES_WITHOUT_A_TRANSACTION) - set(without_tx))
    assert not fixed, (
        f"{fixed} now wraps its replacement in a transaction; delete the "
        "row recording that it did not")

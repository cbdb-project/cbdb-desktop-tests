"""Index-address rankings -- the only part of the app that rewrites CBDB data.

Every other endpoint in this suite reads the biographical tables and
writes only scratch.  ``/api/indexaddr/update`` resets
``BIOG_ADDR_CODES.c_index_addr_rank`` for every row, clears
``BIOG_MAIN.c_index_addr_id`` for every person, and rebuilds it from the
new ranking.  ``/reset`` does the same with the default order.

So this file gets **its own application instance on its own copy of the
database**, and never touches the session's.  Two reasons: after an
update, ``BIOG_MAIN``'s index address genuinely differs from the shipped
data, which would invalidate every other test that joins on it; and the
rebuild is not atomic across its two transactions, so a failure halfway
leaves the database in a state no other test should have to reason about.

The oracles are the application's own before-and-after answers, plus row
counts in the copy it just rewrote -- never a reconstruction of how a
ranking is supposed to be applied.
"""
from __future__ import annotations

import shutil
import sqlite3
import warnings

import pytest

from cbdb_desktop.app import AppError, CbdbApp
from cbdb_desktop.config import Config
from cbdb_desktop.staging import AppLayout

pytestmark = [pytest.mark.app, pytest.mark.slow]

#: The value the form uses for "this rank is not in use".
DISABLED = 1000


@pytest.fixture(scope="module")
def index_addr_app(layout: AppLayout, config: Config, artifacts_dir,
                   tmp_path_factory):
    """A private application, on a database only this file may rewrite."""
    private = tmp_path_factory.mktemp("index-addr") / "CBDB.db"
    shutil.copyfile(layout.db, private)

    server = CbdbApp(layout, private, config,
                     log_path=artifacts_dir / "cbdb-index-addr.log")
    try:
        server.start()
    except (AppError, OSError) as exc:
        server.stop()
        pytest.fail(f"could not start the index-address application: {exc}",
                    pytrace=False)
    try:
        yield server
    finally:
        server.stop()
        leaked = []
        for suffix in ("", "-wal", "-shm"):
            candidate = private.with_name(private.name + suffix)
            try:
                candidate.unlink()
            except FileNotFoundError:
                pass
            except OSError:
                leaked.append(candidate)
        if leaked:
            # A 1.2 GB copy that silently stays behind is exactly what the
            # session run directory warns about; this one lives in the
            # pytest temp tree, which nothing prunes.
            warnings.warn(f"index-address database copy left behind: {leaked}",
                          stacklevel=1)


@pytest.fixture
def restore_default_ranking(index_addr_app: CbdbApp):
    """Put the ranking back after a test that changed it."""
    yield
    response = index_addr_app.post("/api/indexaddr/reset", json={})
    assert response.status_code == 200, response.text[:200]


def _ranking(app: CbdbApp) -> list[dict]:
    return app.json("GET", "/api/indexaddr/rankings")


def _active_order(rankings: list[dict]) -> list[int]:
    """The address types in rank order, as the form displays them."""
    active = [row for row in rankings if row["index_addr_rank"] < 100]
    return [row["addr_type"] for row in sorted(active,
                                               key=lambda r: r["index_addr_rank"])]


def _slots(order: list[int]) -> list[int]:
    """A nine-slot ranks array from a list of address types."""
    return (order + [DISABLED] * 9)[:9]


# ---------------------------------------------------------------------------
# what the form offers
# ---------------------------------------------------------------------------

def test_the_form_offers_a_ranking_it_can_explain(index_addr_app: CbdbApp):
    """Every ranked address type can be named, and re-selected, by the page.

    The page joins the two lists to show a name beside each rank, so a
    ranked type missing from the dropdown is a blank row on screen and a
    rank the user cannot restore once they have changed it.

    Not equality of the two lists: since the 2026-09-07 build ``/codes``
    deliberately omits the two non-selectable rows (-1 "[Missing Data]"
    and 0 "unknown") that ``/rankings`` still describes -- see
    ``test_the_dropdown_offers_only_address_types_that_can_be_ranked``
    in test_lookups.py, which pins that difference against the shipped
    table.
    """
    codes = index_addr_app.json("GET", "/api/indexaddr/codes")
    rankings = _ranking(index_addr_app)

    offered = {row["addr_type"] for row in codes}
    assert all(row["combined_desc"] or row["desc_chn"] for row in codes)

    order = _active_order(rankings)
    assert order, "no address type is ranked at all"
    assert len(order) == len(set(order)), "an address type is ranked twice"
    assert len(order) <= 9, f"{len(order)} ranks for nine slots"
    assert set(order) <= offered, (
        f"ranked but not offered in the dropdown: {sorted(set(order) - offered)}")
    assert all(addr_type > 0 for addr_type in order), (
        f"a non-positive address type is installed as a rank: {order} -- "
        "the update endpoint is contractually obliged to treat those as "
        "'not set' (buildCleanRanks), so one cannot legitimately be here")


# ---------------------------------------------------------------------------
# the guards
# ---------------------------------------------------------------------------

def test_the_first_rank_cannot_be_empty(index_addr_app: CbdbApp):
    """Something has to be ranked first, or nobody gets an index address."""
    response = index_addr_app.post("/api/indexaddr/update",
                                   json={"ranks": [DISABLED] * 9})
    assert response.status_code == 400
    assert "Rank 1" in response.text


def test_a_repeated_address_type_keeps_only_its_first_place(
        index_addr_app: CbdbApp, restore_default_ranking):
    """A duplicate is tolerated, and only its highest slot takes effect.

    This is the 2026-09-07 contract, and it is the opposite of the
    2026-09-01 one: a repeated address type used to be a 400 naming the
    two slots.  ``buildCleanRanks`` now drops the repeat and shifts the
    rest forward, on the reasoning that picking the same type twice is an
    honest mistake with one obvious reading, while rejecting the whole
    request also rejected the eight slots the user got right.

    What must not happen is the repeat surviving into the ranking, or
    the codes after it being lost with it -- that would silently discard
    priorities the user did set.
    """
    order = _active_order(_ranking(index_addr_app))
    assert len(order) >= 3, order

    # The duplicate has to fit inside nine slots along with everything
    # it is meant not to displace, so the base is one shorter than a
    # full ranking.  (Go decodes into a fixed [9]int, so a tenth element
    # would be dropped by encoding/json before the handler saw it, and
    # this test would be measuring that instead.)
    base = order[:8]
    asked = [base[0]] + base
    payload = index_addr_app.json("POST", "/api/indexaddr/update",
                                  json={"ranks": _slots(asked)})
    assert payload["status"] in ("ok", "unchanged"), payload

    after = _active_order(_ranking(index_addr_app))
    assert after == base, (
        f"a repeated address type was not folded away cleanly: asked for "
        f"{asked}, got {after}")


def test_a_duplicate_in_the_middle_does_not_truncate_the_ranking(
        index_addr_app: CbdbApp, restore_default_ranking):
    """A repeat between two good ranks must not lose the ones after it.

    The interesting half of the duplicate change, and the case the
    report calls out as previously open: every function in the backend
    walks the ranks array and stops at the first 1000, so a duplicate
    *left in place* as a gap would end the ranking early and silently
    drop every priority behind it.  ``buildCleanRanks`` packs survivors
    at the front instead, which is what makes "break on 1000" safe.
    """
    order = _active_order(_ranking(index_addr_app))
    assert len(order) >= 4, order

    # A repeat of rank 1 dropped into the middle of the list.  Same nine-
    # slot arithmetic as above: eight genuine types plus one repeat.
    base = order[:8]
    asked = [base[0], base[1], base[0]] + base[2:]
    payload = index_addr_app.json("POST", "/api/indexaddr/update",
                                  json={"ranks": _slots(asked)})
    assert payload["status"] in ("ok", "unchanged"), payload

    after = _active_order(_ranking(index_addr_app))
    assert after == base, (
        f"a duplicate in slot 3 truncated the ranking: asked for {asked}, "
        f"got {after} -- the ranks behind it were dropped")


def test_a_duplicate_behind_an_empty_slot_is_dropped(
        index_addr_app: CbdbApp, restore_default_ranking):
    """A repeat parked behind a gap must not become a second rank.

    In the 2026-09-01 build this was harmless by coincidence: all three
    places that walked the array stopped at the first disabled slot --
    the duplicate check, the code that wrote the ranks, and the rebuild
    that decided who got which address -- so the hidden duplicate was
    accepted *and* ignored, and the three agreeing is what made it safe.

    ``buildCleanRanks`` now makes it safe on purpose rather than by
    agreement: the repeat is dropped for being a repeat, before any of
    those functions runs.  The observable result is the same, which is
    why the assertion is unchanged -- and that is the point of keeping
    the test.
    """
    order = _active_order(_ranking(index_addr_app))
    assert len(order) >= 2, order

    # A duplicate of rank 1, parked behind a disabled slot.
    hidden = [order[0], DISABLED, order[0]] + [DISABLED] * 6
    response = index_addr_app.post("/api/indexaddr/update",
                                   json={"ranks": hidden})
    assert response.status_code == 200, response.text[:200]

    after = _active_order(_ranking(index_addr_app))
    assert after == [order[0]], after


def test_an_empty_slot_no_longer_truncates_the_ranking(
        index_addr_app: CbdbApp, restore_default_ranking):
    """A gap between two genuine ranks keeps both, packed together.

    The other half of the change above, and the half that is visible to
    a user.  Every function in the backend still walks the array and
    stops at the first 1000; what changed is that ``buildCleanRanks``
    packs the survivors at the front, so a "not set" slot the page left
    in the middle no longer discards every priority behind it.

    Deliberately a *distinct* second type, so the assertion can only
    pass if the value behind the gap really arrived: with the duplicate
    of the test above it would also pass on a build that truncated.
    """
    order = _active_order(_ranking(index_addr_app))
    assert len(order) >= 2, order

    gapped = [order[0], DISABLED, order[1]] + [DISABLED] * 6
    payload = index_addr_app.json("POST", "/api/indexaddr/update",
                                  json={"ranks": gapped})
    assert payload["status"] in ("ok", "unchanged"), payload

    after = _active_order(_ranking(index_addr_app))
    assert after == [order[0], order[1]], (
        f"a gap in slot 2 discarded the rank behind it: asked for {gapped}, "
        f"got {after}")


def test_a_ranking_with_too_many_slots_keeps_the_first_nine(
        index_addr_app: CbdbApp, restore_default_ranking):
    """An over-long array is truncated, not rejected -- pinned as behaviour.

    ``Ranks`` is a fixed ``[9]int``, so ``encoding/json`` discards
    anything past the ninth element before the handler is reached; there
    is no place in the application where a longer array could be
    refused, short of decoding into a slice first.  Recorded here
    because "eleven slots accepted" reads like a validation hole and is
    really the request being silently shortened -- and because a build
    that changed to a slice would start applying the tenth and eleventh
    priorities, which this would catch.
    """
    order = _active_order(_ranking(index_addr_app))
    assert len(order) == 9, order

    reordered = [order[1], order[0]] + order[2:9]
    response = index_addr_app.post("/api/indexaddr/update",
                                   json={"ranks": reordered + order[:2]})
    assert response.status_code == 200, response.text[:200]

    after = _active_order(_ranking(index_addr_app))
    assert after == reordered, (
        f"an 11-slot request was not applied as its first nine: asked for "
        f"{reordered + order[:2]}, got {after}")


def test_re_applying_the_current_ranking_changes_nothing(index_addr_app: CbdbApp):
    """The form short-circuits an update that would be a no-op.

    Worth having because the alternative is rewriting c_index_addr_id for
    658,941 people to arrive back where it started.
    """
    order = _active_order(_ranking(index_addr_app))

    payload = index_addr_app.json("POST", "/api/indexaddr/update",
                                  json={"ranks": _slots(order)})
    assert payload["status"] == "unchanged", payload
    assert _active_order(_ranking(index_addr_app)) == order


# ---------------------------------------------------------------------------
# the round trip
# ---------------------------------------------------------------------------

def test_reordering_the_ranking_takes_effect_and_can_be_undone(
        index_addr_app: CbdbApp, restore_default_ranking):
    """Reorder, observe, reset -- the whole user-visible cycle.

    The database this rewrites is this file's private copy, so the
    ~659,000-row rebuild cannot reach any other test.
    """
    before = _active_order(_ranking(index_addr_app))
    assert len(before) >= 2, before

    swapped = [before[1], before[0]] + before[2:]
    payload = index_addr_app.json("POST", "/api/indexaddr/update",
                                  json={"ranks": _slots(swapped)})
    assert payload["status"] == "ok", payload

    assert _active_order(_ranking(index_addr_app)) == swapped, \
        "the ranking the form reports is not the one it was given"

    reset = index_addr_app.json("POST", "/api/indexaddr/reset", json={})
    assert reset["status"] in ("ok", "unchanged"), reset
    assert _active_order(_ranking(index_addr_app)) == before, \
        "reset did not restore the ranking the build shipped with"


def test_reordering_the_ranking_rewrites_peoples_index_address(
        index_addr_app: CbdbApp, restore_default_ranking):
    """The point of the form: it changes which address a person gets.

    Counted in the database the application just rewrote -- its own
    output, not a reconstruction of the rule it applied.  The assertion
    is deliberately weak about *which* people change, because that is the
    application's decision; it is strong about the rebuild having
    happened at all and having left every person with a usable value.
    """
    def index_addresses() -> tuple[int, int]:
        conn = sqlite3.connect(
            index_addr_app.db_path.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            with_addr = conn.execute(
                "SELECT COUNT(*) FROM BIOG_MAIN "
                "WHERE c_index_addr_id IS NOT NULL").fetchone()[0]
            distinct = conn.execute(
                "SELECT COUNT(DISTINCT c_index_addr_type_code) FROM BIOG_MAIN "
                "WHERE c_index_addr_type_code IS NOT NULL").fetchone()[0]
            return with_addr, distinct
        finally:
            conn.close()

    before = _active_order(_ranking(index_addr_app))
    people_before, types_before = index_addresses()
    assert people_before > 0, "nobody has an index address to begin with"

    # Rank only the second type: every person whose address came from the
    # first must now get something else, or nothing.
    payload = index_addr_app.json("POST", "/api/indexaddr/update",
                                  json={"ranks": _slots([before[1]])})
    assert payload["status"] == "ok", payload

    people_after, types_after = index_addresses()
    # Ranking exactly one address type is a request the application can
    # only satisfy one way: nobody may end up with a different type, and
    # anyone whose address came from another type must lose theirs.
    assert types_after == 1, \
        f"{types_after} address types survived a ranking that named one"
    assert people_after < people_before, \
        f"{people_after} people still have an index address, against " \
        f"{people_before} before: the rebuild did not narrow anything"


def test_a_body_that_names_nothing_is_refused(index_addr_app: CbdbApp):
    """A request with no usable ranking at all is refused, not applied.

    "No usable ranking" is now a narrower category than it was.  Go
    decodes into a fixed ``[9]int`` and errors on neither a short array
    nor a long one, so length was never what got a body rejected: a
    short array is zero-padded, and ``buildCleanRanks`` reads any code
    <= 0 as "not set".  What is left after that pass is either at least
    one genuine address type -- a ranking, however partial -- or nothing
    at all, and only the second case can be refused.

    Both bodies here reduce to nothing: a non-array cannot decode into
    ``[9]int``, and an absent ``ranks`` leaves nine zeroes, which is
    exactly the "Rank 1 is empty" case.  ``{"ranks": [1, 2]}``
    deliberately is *not* in this list -- it names two real types and is
    now applied, which
    ``test_a_short_ranking_is_applied_as_exactly_what_it_named`` covers.
    """
    for body in ({"ranks": "not an array"}, {}):
        response = index_addr_app.post("/api/indexaddr/update", json=body)
        assert response.status_code == 400, \
            f"{body} -> {response.status_code} {response.text[:120]}"

    # And nothing was applied on the way to being refused.
    assert _active_order(_ranking(index_addr_app)), \
        "a refused request cleared the ranking anyway"


def test_a_short_ranking_is_applied_as_exactly_what_it_named(
        index_addr_app: CbdbApp, restore_default_ranking):
    """A ranking with too few slots must install those slots and no others.

    This is the heart of CBDB-D-006, and the shape of the fix is what
    makes it worth a test of its own rather than a status-code check.
    ``/api/indexaddr/update`` is the only endpoint in the application
    that rewrites CBDB data rather than scratch, and it accepts a short
    array: Go zero-values the missing elements of its ``[9]int``, so the
    2026-09-01 build read the padding as address type 0 -- "unknown", a
    real row in ``BIOG_ADDR_CODES`` -- and installed it as a genuine
    rank for all 659k people.

    The fix does not reject the short body; it reads the padding as "not
    set".  So what has to be asserted is not a 400 but that **nothing
    the request did not name comes back in the ranking**: the eight
    types sent, in order, and nothing in slot nine.
    """
    order = _active_order(_ranking(index_addr_app))
    assert len(order) >= 8, order

    def index_address_types() -> set[int]:
        """Which address types people actually ended up indexed by."""
        conn = sqlite3.connect(
            index_addr_app.db_path.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            return {row[0] for row in conn.execute(
                "SELECT DISTINCT c_index_addr_type_code FROM BIOG_MAIN "
                "WHERE c_index_addr_type_code IS NOT NULL")}
        finally:
            conn.close()

    # Eight slots: one short, and reordered so that being applied at all
    # is visible in the ranking afterwards.
    asked = [order[1], order[0]] + order[2:8]
    assert len(asked) == 8, asked
    response = index_addr_app.post("/api/indexaddr/update",
                                   json={"ranks": asked})
    assert response.status_code == 200, \
        f"a short ranking was refused: {response.status_code} " \
        f"{response.text[:200]}"

    applied = _active_order(_ranking(index_addr_app))
    assert applied == asked, (
        f"a short ranking was not applied as sent: asked for {asked}, got "
        f"{applied}.  A slot the request never named is now a priority for "
        "every person in CBDB.")

    # And the rebuild that follows must not have indexed anybody by a
    # type outside the ranking it was given -- 0 ("unknown") being the
    # one the zero-padding used to install.
    stray = index_address_types() - set(asked)
    assert not stray, (
        f"people are indexed by address types the ranking does not "
        f"contain: {sorted(stray)}")

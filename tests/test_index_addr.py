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
from cbdb_desktop.defects import BY_NAME, KnownShippedDefect
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
    """Codes and rankings describe the same address types.

    The page joins the two lists to show a name beside each rank, so a
    type in one and not the other is a blank row on screen.
    """
    codes = index_addr_app.json("GET", "/api/indexaddr/codes")
    rankings = _ranking(index_addr_app)

    assert {row["addr_type"] for row in codes} == \
        {row["addr_type"] for row in rankings}
    assert all(row["combined_desc"] or row["desc_chn"] for row in codes)

    order = _active_order(rankings)
    assert order, "no address type is ranked at all"
    assert len(order) == len(set(order)), "an address type is ranked twice"
    assert len(order) <= 9, f"{len(order)} ranks for nine slots"


# ---------------------------------------------------------------------------
# the guards
# ---------------------------------------------------------------------------

def test_the_first_rank_cannot_be_empty(index_addr_app: CbdbApp):
    """Something has to be ranked first, or nobody gets an index address."""
    response = index_addr_app.post("/api/indexaddr/update",
                                   json={"ranks": [DISABLED] * 9})
    assert response.status_code == 400
    assert "Rank 1" in response.text


def test_the_same_address_type_cannot_be_ranked_twice(index_addr_app: CbdbApp):
    """A duplicate among the active slots is refused, and named."""
    order = _active_order(_ranking(index_addr_app))
    assert len(order) >= 2, order

    response = index_addr_app.post(
        "/api/indexaddr/update",
        json={"ranks": _slots([order[0], order[0]] + order[2:])})
    assert response.status_code == 400
    assert "ranks 1 and 2" in response.text, response.text[:200]


def test_ranks_after_the_first_empty_slot_are_ignored(index_addr_app: CbdbApp,
                                                      restore_default_ranking):
    """A disabled slot ends the ranking; anything after it is not read.

    Pinned because it looks like a validation hole and is not one.  All
    three places that walk the array stop at the first disabled slot --
    the duplicate check (indexaddr_form_backend.go:199), the code that
    writes the ranks (:373), and the rebuild that decides who gets which
    address (:485) -- so a duplicate hidden behind a gap is accepted
    *and* ignored.  The three agreeing is what makes it harmless.
    """
    order = _active_order(_ranking(index_addr_app))
    assert len(order) >= 2, order

    # A duplicate of rank 1, parked behind a disabled slot.
    hidden = [order[0], DISABLED, order[0]] + [DISABLED] * 6
    response = index_addr_app.post("/api/indexaddr/update",
                                   json={"ranks": hidden})
    assert response.status_code in (200, 400), response.text[:200]

    if response.status_code == 400:
        pytest.fail("the duplicate behind a disabled slot was refused -- the "
                    "validation and the application of a ranking no longer "
                    "agree about where a ranking ends")

    # It was accepted; only the first slot can have taken effect.
    after = _active_order(_ranking(index_addr_app))
    assert after == [order[0]], after


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


def test_an_unusable_ranking_is_refused(index_addr_app: CbdbApp):
    """Three bodies the form could never send are refused.

    They are refused, but not for the reason they look like they are.
    Go decodes into a fixed [9]int and neither errors on a short array
    nor on a long one, so none of these is rejected for its *length*:
    each is zero-padded into a ranking with several address type 0 slots,
    and the duplicate-type check happens to catch that.  The next test
    covers the case where the padding leaves only one zero.
    """
    for body in ({"ranks": "not an array"},
                 {"ranks": [1, 2]},
                 {}):
        response = index_addr_app.post("/api/indexaddr/update", json=body)
        assert response.status_code == 400, \
            f"{body} -> {response.status_code} {response.text[:120]}"


@pytest.mark.xfail(strict=True, raises=KnownShippedDefect,
                   reason=BY_NAME["unvalidated-ranking"].reason)
def test_a_ranking_of_the_wrong_length_is_refused(index_addr_app: CbdbApp,
                                                  restore_default_ranking):
    """A ranking with the wrong number of slots must not be applied.

    This is the only endpoint in the application that rewrites CBDB data
    rather than scratch, and it validates nothing about the shape of what
    it is given: eight slots are zero-padded to nine and applied, eleven
    are truncated to nine and applied.  Both answer "Rankings updated and
    BIOG_MAIN rebuilt successfully".
    """
    order = _active_order(_ranking(index_addr_app))
    assert len(order) >= 8, order

    def people_with_an_index_address() -> int:
        conn = sqlite3.connect(
            index_addr_app.db_path.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            return conn.execute("SELECT COUNT(*) FROM BIOG_MAIN "
                                "WHERE c_index_addr_id IS NOT NULL").fetchone()[0]
        finally:
            conn.close()

    before = people_with_an_index_address()

    # Eight slots: one short.  Padding leaves a single address type 0, so
    # the duplicate check that catches the other bad bodies does not fire.
    short = index_addr_app.post("/api/indexaddr/update",
                                json={"ranks": order[:8]})
    short_applied = _active_order(_ranking(index_addr_app)) \
        if short.status_code == 200 else None
    short_people = people_with_an_index_address()

    # Eleven slots: two too many, and deliberately in a different order so
    # that being accepted is visible in the ranking afterwards.
    reordered = [order[1], order[0]] + order[2:9]
    long = index_addr_app.post("/api/indexaddr/update",
                               json={"ranks": reordered + order[:2]})
    long_applied = _active_order(_ranking(index_addr_app)) \
        if long.status_code == 200 else None

    problems = []
    if short.status_code == 200:
        # Not just "it answered 200": the padded slot has to be visible in
        # the ranking, and the rebuild has to have happened.  A handler
        # that accepted the body and did nothing would not be this defect.
        problems.append(
            f"8 slots accepted and applied as {short_applied} (address type "
            f"{short_applied[-1] if short_applied else '?'} was never sent); "
            f"people with an index address went from {before} to "
            f"{short_people}")
    if long.status_code == 200:
        problems.append(
            f"11 slots accepted and applied as {long_applied}; the last two "
            "were discarded")

    if problems:
        raise KnownShippedDefect("; ".join(problems))

    assert short.status_code == 400, short.text[:200]
    assert long.status_code == 400, long.text[:200]

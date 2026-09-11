"""Every button, and whether this suite has pressed what it calls.

The coverage gate.  ``test_exports.py`` guarantees no export endpoint
goes undriven; this file makes the same guarantee for the rest of the
user interface, and measures it rather than asserting it: the driver
records every ``(method, path)`` it requests, and the last test in the
run compares that record against every endpoint the shipped pages can
reach.

Why it is worth a file of its own.  Coverage that depends on somebody
noticing a gap is coverage that decays: the 2026-09-01 build shipped
with 36 of its 42 file-producing endpoints untested and nothing said so,
because nothing was counting.  Counting is cheap and it does not forget.

**Named ``test_zz_`` so it runs last.**  Module order in this suite is
load bearing and enforced by ``pytest.ini`` (``-p no:randomly``);
``test_stateful_forms.py`` used to be last by alphabet alone.  This file
has to be after everything, because what it asserts is a property of
the *whole run*.  It touches no state of its own.

**It refuses to judge a partial run.**  Under ``-k``, ``-m``, ``--lf``
or an explicit file argument, most of the suite has not executed and
the record is legitimately short, so the gate skips rather than
reporting a false gap.  That is a real hole -- a filtered run cannot
certify coverage -- and it is why ``run_tests.ps1`` runs unfiltered.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cbdb_desktop import controls
from cbdb_desktop.app import CbdbApp
from cbdb_desktop.config import REPO_ROOT
from cbdb_desktop.routes import all_routes

#: Buttons per page in the shipped build, pinned exactly -- 248 of them.
#: A build that adds a control has to be looked at: either the endpoint
#: it reaches is already driven, or something has to start driving it.
#:
#: 248 is more than it sounds. It counts the three language buttons and
#: the result-tab buttons on every page, which change no state on the
#: server at all. The endpoint gate below is what carries the real
#: weight; this is here so that "a page grew a button" cannot pass
#: unnoticed, and so that a parser regression in controls.py shows up as
#: a count that moved rather than as coverage that quietly shrank.
EXPECTED_BUTTONS = {
    "association_pairs": 21,
    "associations": 18,
    # The Browser page has grown twice: 13 on the 20260908 build, 16 on
    # the 20260909 one, 18 here.
    #
    # 20260909 reworked it.  Its eleven tab buttons gained `id`
    # attributes, so they are keyed by name here instead of by their
    # inline handler, and three new ones appeared -- btnEnglish,
    # btnSimplified and btnTraditional, a language switcher.  All three
    # are wired: each reloads the person and the open tab through the
    # /api/browser/person/{id}* endpoints.
    #
    # 20260910 added two: Save Person ID, which hands the person being
    # browsed to the cross-form channel (driven in
    # test_cross_form_channel.py), and Export Profile, which writes the
    # person's whole record to an HTML file from the same endpoints --
    # and, by loading every tab it has not cached, reaches the kinship
    # handler for a user who never opened that tab (CBDB-D-028).  Both
    # are wired.
    #
    # Read and moved deliberately, which is what this pin is for.
    "browser": 18,
    "entry": 19,
    "group_data": 16,
    "index_addr": 3,
    "kinship": 18,
    "navigation": 0,
    "networks": 25,
    "office": 22,
    "pickers/address_picker": 5,
    "pickers/associations_picker": 4,
    "pickers/dynasty_picker": 3,
    "pickers/entry_picker": 5,
    "pickers/office_picker": 4,
    "pickers/people_picker": 3,
    "pickers/status_picker": 5,
    "pickers/texts_picker": 4,
    "places": 12,
    "qbe": 8,
    "status": 17,
    "texts": 18,
}

#: How many distinct ``/api/`` endpoints the shipped pages can reach.
#: Pinned so that the gate below cannot certify coverage of a reachable
#: set that has quietly shrunk: it is the denominator of the only
#: coverage number this suite reports, and a denominator nobody checks
#: is how "105 of 105" came to mean nothing.
EXPECTED_REACHABLE_ENDPOINTS = 106

#: Endpoints the pages can reach that this suite deliberately does not
#: request, with the reason.  Every entry is a decision; the gate
#: subtracts exactly these and nothing else, so an endpoint that stops
#: being driven fails rather than joining an implicit allowance.
ENDPOINTS_NOT_DRIVEN: dict[str, str] = {
    # Empty, and that is the point: every endpoint a page can reach is
    # currently driven by something, including the two that rewrite
    # BIOG_MAIN for 659k people (test_index_addr.py drives those against
    # its own private copy of the database, and its CbdbApp is recorded
    # here like any other).
    #
    # The temptation is to pre-populate this with anything awkward.
    # Don't: an entry here is a hole in the gate, so it should cost a
    # conversation.  A run that legitimately cannot reach an endpoint --
    # `-m "not slow"` deselects the index-address file -- is a *filtered*
    # run, and the gate skips those entirely rather than excusing
    # individual endpoints.
}


@pytest.fixture(scope="module")
def pages(layout):
    return controls.inventory(layout)


# ---------------------------------------------------------------------------
# the inventory itself
# ---------------------------------------------------------------------------

def test_every_page_has_the_buttons_it_shipped_with(pages):
    """The control inventory, pinned per page."""
    counted = {page: len(buttons) for page, (buttons, _) in pages.items()}
    assert counted == EXPECTED_BUTTONS, (
        "the set of buttons in the build changed.  Decide what the new "
        "ones do and whether anything drives them:\n"
        f"{ {p: (counted.get(p), EXPECTED_BUTTONS.get(p))
              for p in set(counted) | set(EXPECTED_BUTTONS)
              if counted.get(p) != EXPECTED_BUTTONS.get(p)} }")


def test_every_button_is_wired_to_something(pages):
    """A button that calls nothing is a button that does nothing.

    Asserted as an exact count of zero rather than trusted: the two
    wiring styles in these templates are read by two different pieces of
    ``controls.py``, and a parser that stopped understanding one of them
    would report perfectly wired buttons as dead.  Which is why the next
    test checks the same extraction from the other end.
    """
    unwired = [button.key for page_buttons, _ in pages.values()
               for button in page_buttons if button.wiring == "none"]
    assert not unwired, (
        f"{len(unwired)} buttons are wired to no handler at all -- either "
        f"they are dead controls or controls.py can no longer read how "
        f"this page binds them: {unwired}")


def test_every_endpoint_the_pages_call_is_a_route_the_build_registers(layout,
                                                                      pages):
    """The other end of the extraction: pages and routes must agree.

    This is what makes the button extraction trustworthy rather than
    merely plausible.  Every endpoint found in a page is compared with
    the routing table read out of the Go source -- two independent
    artefacts of the same build, parsed by two independent modules.  A
    page calling an endpoint the build does not serve is a 404 the user
    sees; a parser inventing an endpoint fails here too, which is the
    point.
    """
    registered = {route.path for route in all_routes(layout)}
    called: dict[str, set[str]] = {}
    for page, path in controls._pages(layout).items():
        html = path.read_text(encoding="utf-8", errors="replace")
        for endpoint in controls.endpoints_in_page(html):
            called.setdefault(endpoint, set()).add(page)

    assert called, "no page calls any API endpoint"
    unknown = {endpoint: sorted(who) for endpoint, who in called.items()
               if endpoint not in registered}
    assert not unknown, (
        "these pages call endpoints the build does not register.  Either "
        "the page is broken, or controls.py read the URL wrongly (see "
        f"controls.normalise):\n{unknown}")


# ---------------------------------------------------------------------------
# the gate
# ---------------------------------------------------------------------------

def run_was_filtered(arguments: list[str], *, keyword: str = "",
                     markexpr: str = "", last_failed: bool = False
                     ) -> str | None:
    """Why a run cannot certify coverage, or None if it can.

    Takes its inputs rather than reading ``config`` so that it can be
    unit-tested, which it needs to be: the first version compared
    ``config.args`` against the literal ``["tests"]``, and
    ``run_tests.ps1`` invokes pytest with an **absolute** path.  So the
    gate declared every canonical run "filtered" and skipped -- the one
    outcome that looks exactly like success.  Two cold runs went green
    with no coverage measured at all, and the only reason it was noticed
    is that ``artifacts/endpoint_coverage.json`` was missing.

    A gate that can silently not run is not a gate.  Hence
    ``test_the_filter_predicate_recognises_the_canonical_run`` below.
    """
    if keyword:
        return f"-k {keyword!r}"
    if markexpr:
        return f"-m {markexpr!r}"
    if last_failed:
        return "--lf"
    if not arguments:
        return None                      # bare `pytest`: testpaths applies

    tests_dir = (REPO_ROOT / "tests").resolve()
    for argument in arguments:
        # A path argument is unfiltered only if it *is* the tests
        # directory; anything inside it selects a subset.  Split off a
        # "::node" selector first, which is always a subset.
        if "::" in argument:
            return f"explicit test selection: {argument}"
        try:
            resolved = Path(argument).resolve()
        except OSError:
            return f"unreadable test path: {argument}"
        if resolved != tests_dir:
            return f"explicit test path: {argument}"
    return None


def _run_was_filtered(config) -> str | None:
    return run_was_filtered(
        [str(argument) for argument in config.args],
        keyword=config.getoption("keyword") or "",
        markexpr=config.getoption("markexpr") or "",
        last_failed=bool(config.getoption("last_failed", default=False)),
    )


def test_the_filter_predicate_recognises_the_canonical_run():
    """The gate must not mistake ``run_tests.ps1`` for a filtered run.

    Deliberately a test of the predicate and not of the gate: the gate's
    own failure mode is *skipping*, which no assertion inside it can
    catch.  This is the only thing standing between "coverage is
    measured every run" and "coverage was silently never measured", and
    the second is what actually happened for two runs.
    """
    tests_dir = str((REPO_ROOT / "tests").resolve())

    # The two ways the suite is really invoked.
    assert run_was_filtered([]) is None
    assert run_was_filtered([tests_dir]) is None
    assert run_was_filtered(["tests"]) is None, \
        "a relative path to the same directory must count as unfiltered"

    # And the ways it is filtered.
    assert run_was_filtered([tests_dir], keyword="export")
    assert run_was_filtered([tests_dir], markexpr="not slow")
    assert run_was_filtered([tests_dir], last_failed=True)
    assert run_was_filtered([str(REPO_ROOT / "tests" / "test_exports.py")])
    assert run_was_filtered([f"{tests_dir}::test_thing"])


def test_every_endpoint_the_ui_can_reach_is_exercised_by_this_run(
        request, layout, pages):
    """Measured coverage: every UI-reachable endpoint was requested.

    The record comes from ``CbdbApp.requested``, which every request in
    the run adds to, so this is what the suite *did*, not what it says
    it does.  Path variables are folded to ``{id}`` on both sides so a
    per-person sub-resource matches the route that declares it.

    Methods are deliberately ignored *here*.  A page's ``fetch`` carries
    its method in an options object this extractor does not read, so the
    reachable set has no method to match against.

    That was once the whole story, and the reasoning -- "matching on the
    path alone can only under-report a gap, never invent one" -- was
    wrong in the one way that mattered.  ``test_routes.py`` sends a
    ``PATCH`` to every registered ``/api/`` path to prove the route
    still exists, mux answers 405 without entering the handler, and
    ``CbdbApp.requested`` recorded it anyway.  One probe therefore
    marked every endpoint driven, this gate reported 105 reachable /
    105 covered / 0 gaps, and fourteen endpoints nothing had ever really
    requested sat inside that 100%.

    The fix is in the recorder, not here: ``CbdbApp`` no longer records
    a request the router refused with 405 (see ``_ROUTER_REFUSED``), so
    the probe leaves no trace and a path is "driven" only when some
    handler actually ran for it.  Ignoring the method is safe again.

    "Driven" still means only that a handler ran -- a 400, a 409 or a
    500 counts.  This gate measures whether the suite *reached* every
    endpoint the interface can, which is the question it is named
    after; whether each answer was right is every other test's job.

    Worth naming where that is generous, because it is the PATCH probe's
    shape one level up: the kinship and networks ``store-person-ids``
    endpoints count as reached on the strength of
    ``test_stateful_forms.py``, which posts to them only to assert they
    answer **409** and refuse to overwrite.  The suite has watched those
    two decline; it has never seen either succeed.  Their ``/confirmed``
    siblings -- what the page calls once the user says yes -- are two of
    the gaps below, which is how that shows up rather than being hidden.
    """
    filtered = _run_was_filtered(request.config)
    if filtered:
        pytest.skip(
            f"this run is filtered ({filtered}), so most of the suite did "
            "not execute and the request record is legitimately short.  "
            "Coverage is certified by an unfiltered run: .\\run_tests.ps1")

    reachable: dict[str, set[str]] = {}
    for page, path in controls._pages(layout).items():
        html = path.read_text(encoding="utf-8", errors="replace")
        for endpoint in controls.endpoints_in_page(html):
            reachable.setdefault(endpoint, set()).add(page)

    # The gate's own liveness, pinned exactly.  With no reachable set
    # there are no gaps and this passes while measuring nothing -- "a
    # check that can silently skip is not a check", which is what this
    # file is for.  One extractor regression away, and it would write
    # "reachable_from_the_ui": 0 into the artefact and go green.
    #
    # Exact and not "> 90": a floor that admits 91 admits an extractor
    # that has quietly stopped seeing ten endpoints, which is the same
    # partial decay this whole commit is about.  § *Pin exactly, not
    # with a floor* -- and a build that gains or drops an endpoint is
    # expected to fail here and be read.
    assert len(reachable) == EXPECTED_REACHABLE_ENDPOINTS, (
        f"{len(reachable)} endpoints were found in the shipped pages, not "
        f"{EXPECTED_REACHABLE_ENDPOINTS}.  If the build gained or dropped "
        "one, update the number in the same commit as the reason; if it did "
        "not, controls.endpoints_in_page has stopped reading some and this "
        "gate is about to certify coverage of less than it thinks")

    driven = {path for _method, path in CbdbApp.requested}
    excused = set(ENDPOINTS_NOT_DRIVEN)

    stale = sorted(excused - set(reachable))
    assert not stale, (
        f"ENDPOINTS_NOT_DRIVEN excuses endpoints no page calls any more: "
        f"{stale}")

    gaps = {endpoint: sorted(who) for endpoint, who in sorted(reachable.items())
            if endpoint not in driven and endpoint not in excused}

    # Write the measurement out whether it passes or not: the number is
    # the interesting artefact of a run, and reading it should not
    # require re-running the suite.
    summary = {
        "reachable_from_the_ui": len(reachable),
        "requested_in_this_run": len(driven),
        "covered": len(reachable) - len(gaps) - len(excused),
        "excused": ENDPOINTS_NOT_DRIVEN,
        "gaps": gaps,
    }
    out = REPO_ROOT / "artifacts" / "endpoint_coverage.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=1), encoding="utf-8")

    assert not gaps, (
        f"{len(gaps)} endpoint(s) a user can reach from the interface were "
        f"never requested by this run:\n  " +
        "\n  ".join(f"{endpoint}  (from {', '.join(who)})"
                    for endpoint, who in gaps.items()) +
        "\n\nDrive them, or add each to ENDPOINTS_NOT_DRIVEN with a reason.")

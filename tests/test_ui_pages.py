"""The pages, in a real browser: do they load, and do their controls work?

The layer the rest of the suite cannot see.  Everything else here talks
HTTP and therefore checks what the server computes; a control that stays
greyed out with its precondition met, or a page that throws during load,
is invisible to all of it.  Both were reported by the maintainer using
the application -- a decisive experiment nobody had automated.

Three checks, in order of how much they buy:

1. **Every form page loads without throwing.**  A page that raises
   during load stops attaching its handlers, and from then on nothing on
   it responds -- the single failure mode that kills a whole form.
   Cheap, and it covers all thirteen pages.

2. **Every control that ships disabled is enabled by its precondition.**
   106 controls across the build ship ``disabled``; ``PRECONDITIONS``
   says, per page, what a user does and which controls that must
   un-grey.  It is a table rather than a script so that it reads as a
   claim about the application, and
   ``test_every_disabled_control_has_a_declared_precondition`` is the
   coverage gate over it: a control nobody has declared a precondition
   for sits in ``UNDECLARED``, which is pinned and may only shrink.

3. **What a page tells the user matches what it did.**  The export
   handlers report the server's file count as though every file had been
   saved; here that is compared against the downloads the browser
   accepted.

**Skipped, not failed, without Chromium.**  Playwright downloads its own
browser and a fresh checkout will not have it (see
``cbdb_desktop/browser.py``).  A skipped run says so rather than going
quietly green.

**And this is not the user's browser.**  Downloads are auto-accepted
here, so Chrome's multiple-download permission -- what CBDB-D-012 is
really about -- never engages and both files arrive.  The half of that
defect a browser can confirm is the misreported count; the half it
cannot is checked by reading the page's own delivery code, in
``test_exports.py``.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from cbdb_desktop import browser, controls
from cbdb_desktop.app import CbdbApp
from cbdb_desktop.defects import KnownShippedDefect

pytestmark = [pytest.mark.app, pytest.mark.browser]

_USABLE, _WHY_NOT = browser.available()
pytestmark.append(pytest.mark.skipif(not _USABLE, reason=_WHY_NOT))

#: A person with a small, non-empty network.  Fixed rather than
#: discovered: a browser test that also has to choose its own input is
#: two experiments in one, and this is the same subject
#: test_stateful_forms.py uses for the same reason.
SUBJECT = 1762

#: One entry code that returns a result, for the export accounting.
ENTRY_CODE = 36


@dataclass(frozen=True)
class Precondition:
    """What a user does on one page, and what that must un-grey."""

    page: str
    path: str
    #: Requests to make first, as ``(path, body)`` -- the state a user
    #: reaches through a picker, established directly because driving a
    #: popup picker in a browser tests the picker, not this.
    seed: tuple[tuple[str, dict], ...] = ()
    #: JavaScript run in the page afterwards: the clicks and ticks a
    #: user performs.  Runs in the page's own world, so it calls the
    #: page's own functions.
    interact: str = "() => {}"
    #: Milliseconds to wait after interacting, for a query to finish.
    settle_ms: int = 1500
    #: Controls that must be enabled once all of that has happened.
    must_enable: tuple[str, ...] = ()
    notes: str = ""


PRECONDITIONS: tuple[Precondition, ...] = (
    # The Networks form, reloaded with a person already on the server.
    # This is CBDB-D-013: the page's restore path sets its own
    # "a person is selected" flag and enables one button, without
    # re-running the function that decides whether Run Query is
    # allowed -- so the precondition is met and the button is grey.
    Precondition(
        page="networks",
        path="/LookAtNetworks",
        seed=(("/api/networks/set-person", {"personId": SUBJECT}),),
        interact="""() => {
          for (const id of ['chk-kin', 'chk-nonkin', 'chk-male', 'chk-female']) {
            const box = document.getElementById(id);
            if (box && !box.disabled && !box.checked) box.checked = true;
          }
        }""",
        must_enable=("btn-run",),
        notes="the checkboxes are set without firing their onchange, "
              "which is exactly the state a returning user is in: the "
              "page restored a person and nothing has fired since",
    ),
    # The same page, with the checkbox events actually fired.  This one
    # passes, and it is here so the failure above cannot be read as
    # "the Networks form never enables Run Query".
    Precondition(
        page="networks",
        path="/LookAtNetworks",
        seed=(("/api/networks/set-person", {"personId": SUBJECT}),),
        interact="""() => {
          for (const id of ['chk-kin', 'chk-nonkin', 'chk-male', 'chk-female']) {
            const box = document.getElementById(id);
            if (box && !box.disabled && !box.checked) {
              box.checked = true;
              box.dispatchEvent(new Event('change'));
            }
          }
        }""",
        must_enable=("btn-run", "chk-kin-param"),
        notes="ticking Kinship Relations is what enables Use Kinship "
              "Parameters, so both are asserted together",
    ),
    # The Entry form after a real query: every export button must work.
    Precondition(
        page="entry",
        path="/LookAtEntry",
        interact=f"""async () => {{
          handleEntrySelection([{ENTRY_CODE}], ['t'], ['t'], '', '', '');
          await runQuery();
        }}""",
        settle_ms=25000,
        must_enable=("btnExportResults", "btnGIS", "btnNeo4j", "btnStoreIDs"),
    ),
    # The Kinship form after a real query.
    Precondition(
        page="kinship",
        path="/LookAtKinship",
        seed=(("/api/kinship/set-person", {"personId": SUBJECT}),),
        interact="""async () => {
          document.getElementById('btn-run').disabled = false;
          await runQuery();
        }""",
        settle_ms=20000,
        must_enable=("btn-export-results", "btn-tab", "btn-kml", "btn-neo4j",
                     "btn-pajek", "btn-gephi", "btn-uci-net"),
        notes="btn-run is force-enabled first: what this test is about "
              "is the export buttons after a result exists, and the "
              "Kinship form's own enable path is a separate question",
    ),
)

#: Controls that ship disabled and that no ``Precondition`` above
#: declares.  Pinned so the number can only go down: every entry is a
#: control whose enable path nothing in this suite checks, and the
#: honest thing is to count them rather than imply the coverage is
#: complete.
#:
#: The pickers are the bulk of it and the least worrying -- their
#: buttons enable on a selection inside a popup window, which needs a
#: harness for driving pickers that does not exist yet.  The form-page
#: entries are the ones worth working through.
UNDECLARED: dict[str, tuple[str, ...]] = {
    "association_pairs": ("btnClearList", "btnExportResults", "btnGIS",
                          "btnGephi", "btnNeo4j", "btnPajek", "btnQuery",
                          "btnStoreIDs", "btnUCINet"),
    "associations": ("btn-export-query", "btn-kml", "btn-neo4j", "btn-store",
                     "btn-tab"),
    "entry": ("btnSaveCodes",),
    "group_data": ("btnClear", "btnExportResults", "btnGIS", "btnNeo4j",
                   "btnQuery", "btnStoreIDs", "chkGisAddr", "chkGisEntry",
                   "chkGisOffPpl", "chkGisOffice", "chkGisStatus",
                   "chkGisText"),
    "kinship": ("btn-recall-ids", "btn-run", "btn-store"),
    "networks": ("btn-all-people", "btn-all-places", "btn-export-results",
                 "btn-from-dynasty", "btn-gis", "btn-guess", "btn-neo4j",
                 "btn-pajek", "btn-recall-id", "btn-rerun", "btn-store-id",
                 "btn-to-dynasty", "btn-ucinet", "chk-place-limit",
                 "chk-sub-units", "chk-xy-ref", "txt-max-col", "txt-max-dwn",
                 "txt-max-mar", "txt-max-up"),
    "office": ("btn-all-offices", "btn-all-places-office",
               "btn-all-places-people", "btn-export-results",
               "btn-gis-office", "btn-gis-people", "btn-kml-office",
               "btn-kml-people", "btn-neo4j", "btn-store-ids"),
    "pickers/address_picker": ("btn-clear-filter", "btn-sel-all-filt",
                               "btn-select"),
    "pickers/associations_picker": ("btn-select",),
    "pickers/dynasty_picker": ("btn-dynasty-search", "btn-dynasty-select"),
    "pickers/entry_picker": ("btn-entry-select", "btn-search",
                             "btn-search-next", "btn-select-all"),
    "pickers/office_picker": ("btn-select",),
    "pickers/status_picker": ("btn-search", "btn-search-next",
                              "btn-select-all", "btn-status-select"),
    "pickers/texts_picker": ("btn-select",),
    "places": ("btnExportNeo4j", "btnExportResults", "btnRunQuery",
               "btnSaveGIS", "btnSaveKML", "btnStorePersonIDs"),
    "status": ("btnAllPlaces", "btnExportGIS", "btnExportNeo4j",
               "btnExportResults", "btnRunQuery", "btnStoreIDs"),
    "texts": ("btn-export-results", "btn-kml", "btn-neo4j", "btn-store",
              "btn-tab"),
}

@dataclass
class _Result:
    states: dict[str, str] = field(default_factory=dict)
    log: browser.PageLog = field(default_factory=browser.PageLog)


def _drive(app: CbdbApp, pre: Precondition) -> _Result:
    """Establish a precondition in a browser and read the control states."""
    for path, body in pre.seed:
        response = app.post(path, json=body)
        assert response.status_code == 200, \
            f"{pre.page}: seeding {path} gave {response.status_code}"

    result = _Result()
    with browser.open_page(app.base_url, pre.path) as (page, log):
        result.log = log
        page.evaluate(pre.interact)
        page.wait_for_timeout(pre.settle_ms)
        result.states = browser.control_states(page, list(pre.must_enable))
    return result


# ---------------------------------------------------------------------------
# does the page load at all
# ---------------------------------------------------------------------------

def test_every_page_the_build_serves_loads_without_throwing(app: CbdbApp,
                                                            layout):
    """No page may raise during load.

    The broadest check in this file, and the worst failure mode behind
    it: a page that throws while attaching its handlers leaves every
    control inert, and every HTTP test in this suite still passes.
    There is no cheaper way to notice.

    The list of pages is **read out of the routing table**, not guessed
    from the template directory names.  An earlier version of this test
    derived "/LookAtPlaces" from the `places/` template and reported the
    resulting 404 as a broken page -- the route is `/LookAtPlace`,
    singular.  Guessing at the build is what routes.py exists to stop.
    """
    from cbdb_desktop.routes import all_routes, concrete_get_pages

    pages = [route.path for route in concrete_get_pages(all_routes(layout))]
    assert len(pages) >= 13, pages

    broken: dict[str, list[str]] = {}
    for path in sorted(pages):
        try:
            with browser.open_page(app.base_url, path) as (_page, log):
                if not log.clean:
                    broken[path] = log.page_errors + log.console_errors
        except RuntimeError as exc:
            broken[path] = [str(exc)]

    assert not broken, (
        "these pages logged an error while loading.  A page that throws "
        "during load stops attaching its handlers, and every control on "
        f"it is then dead: {broken}")


# ---------------------------------------------------------------------------
# enable state
# ---------------------------------------------------------------------------

def test_every_disabled_control_has_a_declared_precondition(layout):
    """The coverage gate for this file: count what is not covered.

    106 controls ship disabled.  This file declares a precondition for
    some of them; the rest are listed in ``UNDECLARED``, pinned, and
    that list may only shrink.  Without this the file would look like
    full coverage of enable state while checking four pages' worth.

    A control that leaves ``UNDECLARED`` without gaining a
    ``Precondition`` fails here, and so does a new disabled control in a
    new build -- which is the same guarantee the export and endpoint
    inventories give.
    """
    import re

    declared: dict[str, set[str]] = {}
    for pre in PRECONDITIONS:
        declared.setdefault(pre.page, set()).update(pre.must_enable)

    pattern = re.compile(
        r"""<(?:button|input|select)\b[^>]*\bid\s*=\s*["']([^"']+)["']"""
        r"""[^>]*\bdisabled""", re.IGNORECASE)
    pattern2 = re.compile(
        r"""<(?:button|input|select)\b[^>]*\bdisabled[^>]*"""
        r"""\bid\s*=\s*["']([^"']+)["']""", re.IGNORECASE)

    actual: dict[str, set[str]] = {}
    for page, path in controls._pages(layout).items():
        html = path.read_text(encoding="utf-8", errors="replace")
        ids = set(pattern.findall(html)) | set(pattern2.findall(html))
        if ids:
            actual[page] = ids

    undeclared = {page: tuple(sorted(ids - declared.get(page, set())))
                  for page, ids in sorted(actual.items())}
    undeclared = {page: ids for page, ids in undeclared.items() if ids}

    expected = {page: tuple(sorted(ids))
                for page, ids in sorted(UNDECLARED.items())}
    assert undeclared == expected, (
        "the set of disabled controls with no declared precondition "
        "changed.  If it shrank, delete the entries from UNDECLARED in "
        "the same commit; if it grew, the new controls need a "
        f"Precondition:\n{undeclared}")

    covered = sum(len(v) for v in declared.values())
    total = sum(len(v) for v in actual.values())
    print(f"\nenable-state coverage: {covered} of {total} disabled controls "
          f"have a declared precondition")


# One test per declared precondition, id'd by the page and the controls
# it must un-grey ("networks-btn-run").  No precondition is expected to
# fail: one that does is a control the user cannot press having done
# everything the form asks, and it is reported as a failure.  Tolerating
# one is a decision recorded in the waiver table under this function's
# name plus that id -- never as a marker here.
@pytest.mark.parametrize("pre", [
    pytest.param(pre, id=f"{pre.page}-{'+'.join(pre.must_enable)}")
    for pre in PRECONDITIONS
])
def test_a_control_is_enabled_once_its_precondition_is_met(app: CbdbApp,
                                                           pre: Precondition):
    """Do the thing the control waits for, and check it un-greys.

    The user-visible property, measured.  A control still disabled here
    is a control the user cannot press having done everything the form
    asks -- and the server, asked the same question over HTTP, answers
    perfectly.
    """
    result = _drive(app, pre)

    missing = sorted(k for k, v in result.states.items() if v == "MISSING")
    assert not missing, \
        f"{pre.page}: the page has no control called {missing}"

    still_disabled = sorted(k for k, v in result.states.items()
                            if v == "disabled")
    if still_disabled:
        raise KnownShippedDefect(
            f"{pre.page}: {still_disabled} still disabled after the "
            f"precondition was met ({pre.notes or pre.interact.strip()[:60]})")

    assert result.log.clean, \
        f"{pre.page}: the page logged {result.log.page_errors} " \
        f"{result.log.console_errors}"


# ---------------------------------------------------------------------------
# what the page claims it did
# ---------------------------------------------------------------------------

def test_an_export_does_not_claim_more_files_than_it_delivered(
        app: CbdbApp, sqlite_conn):
    """The page's own success message, checked against the downloads.

    ``"2 file(s) ready"`` is the count the *server* returned; the page
    never asks the browser what it accepted.  Here they are compared,
    twice in a row, because the second press is where the maintainer saw
    them diverge.

    In this browser they agree -- downloads are auto-accepted, so both
    files arrive both times -- and that is the point worth writing down:
    this test passes on a permissive browser and would fail on the
    user's.  It is the honest half of CBDB-D-012, and the reason the
    other half is checked by reading the page's delivery code instead.

    The entry code is discovered rather than fixed: the first version of
    this test used one with 92,572 rows, whose export takes long enough
    that the page's own three-second success message had come and gone
    before it was read.  Choosing a small input is the same discipline
    the HTTP tests use, for the same reason.
    """
    codes = [row[0] for row in sqlite_conn.execute(
        "SELECT c_entry_code FROM ENTRY_DATA GROUP BY c_entry_code "
        "HAVING COUNT(*) BETWEEN 2 AND 12 ORDER BY COUNT(*) DESC LIMIT 8")]
    live = next((code for code in codes
                 if app.json("POST", "/api/entry/query",
                             json={"entryCodes": [code], "addrIds": [],
                                   "addrSubUnits": False, "addressFrame": 1,
                                   "yearFilterType": "none"})), None)
    assert live, f"none of {codes} returns any rows"

    with browser.open_page(app.base_url, "/LookAtEntry") as (page, log):
        page.evaluate(f"""() => handleEntrySelection(
            [{live}], ['t'], ['t'], '', '', '')""")
        page.evaluate("() => runQuery()")
        page.wait_for_function("() => (queryResults || []).length > 0",
                               timeout=60_000)

        for press in (1, 2):
            log.downloads.clear()
            browser.take_attempts(page, log)
            page.evaluate("() => exportQueryResults()")
            # showSuccess() inserts a .success div and removes it three
            # seconds later, so the message has to be caught while it is
            # there -- polled, not slept for.  showError() is watched
            # too: an export that failed must not read as one that said
            # nothing.
            page.wait_for_function(
                "() => document.querySelector('.success, .error, #error-box')"
                " !== null", timeout=60_000)
            claimed = page.evaluate(
                "() => [...document.querySelectorAll('.success, .error')]"
                ".map(e => e.textContent).join(' | ')")
            page.wait_for_timeout(500)
            attempted = browser.take_attempts(page, log)
            accepted = list(log.downloads)

            import re
            match = re.search(r"(\d+)\s*file\(s\)", claimed)
            assert match, (
                f"press {press}: the page said {claimed!r}, which does not "
                "report a file count -- update this test if the message "
                "changed")
            said = int(match.group(1))

            assert said == len(attempted), (
                f"press {press}: the page claims {said} file(s) and "
                f"attempted {len(attempted)} downloads -- it is not even "
                "reporting its own intention")
            assert said == len(accepted), (
                f"press {press}: the page claims {said} file(s) and the "
                f"browser accepted {len(accepted)} ({accepted}).  On a "
                "browser that declines automatic multiple downloads this "
                "is what the user sees, and the message is a lie.")

            # Let the message expire before the next press, so the poll
            # above cannot read the previous one.
            page.wait_for_timeout(3200)

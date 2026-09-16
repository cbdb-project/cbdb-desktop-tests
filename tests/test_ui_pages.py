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
   109 controls across the build ship ``disabled``; ``PRECONDITIONS``
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
here, so Chrome's multiple-download permission -- which is what those
handlers are really up against -- never engages and both files arrive.
The half of that defect a browser can confirm is the misreported count;
the half it cannot is checked by reading the page's own delivery code,
in ``test_exports.py``.
"""
from __future__ import annotations

import re

from dataclasses import dataclass, field

import pytest

from cbdb_desktop import browser, controls
from cbdb_desktop.app import CbdbApp
from cbdb_desktop.defects import KnownShippedDefect
from cbdb_desktop.subjects import (ASSOC_CODE, ENTRY_CODE, OFFICE_CODE,
                                    SUBJECT)

pytestmark = [pytest.mark.app, pytest.mark.browser]

_USABLE, _WHY_NOT = browser.available()
pytestmark.append(pytest.mark.skipif(not _USABLE, reason=_WHY_NOT))

#: The three inputs these tests fix instead of discovering, and why --
#: see ``cbdb_desktop/subjects.py``, which also carries the check that
#: the shipped data still has them.  That check lives outside this file
#: on purpose: it needs no browser, and here it would be skipped by the
#: module-wide Chromium guard above, so a retired input would go
#: unnoticed on exactly the machines that skip.


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
    #
    # This slot held a second, event-free version of the precondition
    # below: the four checkboxes had their ``.checked`` set without a
    # ``change`` event, on the reading that the page's restore path
    # enables a button without re-running the function that decides
    # whether Run Query is allowed.  On the 2026-09-08 build that
    # reading does not hold, and the deciding evidence is in the page:
    # the restore path ends in ``checkRunCriteria()``
    # (Templates/networks/index.html:1727, and again at :1671 for the
    # picker's own callback), and every control that can change the
    # answer calls it too -- nineteen call sites.  What was left was a
    # state no user can reach: after the restore the button is grey
    # because no relation type is ticked, which is correct, and ticking
    # one fires the handler that un-greys it.  Removed rather than
    # rewritten, because with the event dispatched it is exactly the
    # entry below.
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
    # The Associations form, which ships Run Query disabled as of the
    # 2026-09-08 build: it un-greys once at least one association code
    # has been picked.  Driven through the page's own picker callback,
    # which is what the popup calls on selection, rather than by
    # writing the hidden field this test would then be checking itself.
    Precondition(
        page="associations",
        path="/LookAtAssociations",
        interact=f"""() => {{
          assocPickerCallback({{codes: [{ASSOC_CODE}],
                                desc: 'Assisted', descChn: ''}});
        }}""",
        settle_ms=200,
        must_enable=("btnRunQuery",),
        notes="new in this build: Run Query starts disabled and the "
              "picker's callback is what enables it",
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
    # The Office form, whose Run Query ships disabled as of the
    # 2026-09-15 build.  Driven through the page's own picker callback,
    # which is what the popup calls on selection.
    Precondition(
        page="office",
        path="/LookAtOffice",
        interact="""() => {
          officePickerCallback({codes: [%d], desc: 'x', descChn: ''});
        }""" % OFFICE_CODE,
        settle_ms=200,
        must_enable=("btnRunQuery",),
        notes="new in this build, and the half of the change that "
              "works -- see "
              "test_all_offices_leaves_the_office_form_able_to_query "
              "for the half that does not",
    ),
    # The Browser page, new in the 20260910 build: looking a person up
    # is what un-greys the two buttons that act on them.
    Precondition(
        page="browser",
        path="/CBDB_Browser",
        interact="""() => { loadPerson(%d); }""" % SUBJECT,
        must_enable=("btn-store-person-id", "btn-export-profile"),
        notes="Both arrived with the 20260910 build -- Save Person ID "
              "hands the person to the cross-form channel, Export "
              "Profile writes their record to an HTML file -- and both "
              "ship disabled.  loadPerson() is the page's own entry "
              "point and enables them once the person's detail has "
              "come back, so this is the user looking somebody up.",
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
    # chkGisKML is new in the 2026-09-15 build: an Export as KML
    # checkbox beside the six section boxes, enabled by the same
    # hasData path they are.
    "group_data": ("btnClear", "btnExportResults", "btnGIS", "btnNeo4j",
                   "btnQuery", "btnStoreIDs", "chkGisAddr", "chkGisEntry",
                   "chkGisKML", "chkGisOffPpl", "chkGisOffice",
                   "chkGisStatus", "chkGisText"),
    "kinship": ("btn-recall-ids", "btn-run", "btn-store"),
    # Two fewer than the 2026-09-10 build: btn-from-dynasty and
    # btn-to-dynasty are gone, replaced by the one Select Dynasties
    # button the multi-select picker needs, which does not ship
    # disabled.
    "networks": ("btn-all-people", "btn-all-places", "btn-export-results",
                 "btn-gis", "btn-guess", "btn-neo4j",
                 "btn-pajek", "btn-recall-id", "btn-rerun", "btn-store-id",
                 "btn-ucinet", "chk-place-limit",
                 "chk-sub-units", "chk-xy-ref", "txt-max-col", "txt-max-dwn",
                 "txt-max-mar", "txt-max-up"),
    "office": ("btn-all-offices", "btn-all-places-office",
               "btn-all-places-people", "btn-export-results",
               "btn-gis-office", "btn-gis-people", "btn-kml-office",
               "btn-kml-people", "btn-neo4j", "btn-store-ids"),
    "pickers/address_picker": ("btn-clear-filter", "btn-sel-all-filt",
                               "btn-select"),
    "pickers/associations_picker": ("btn-select",),
    # New page in the 2026-09-15 build, and the same shape as every
    # other picker: its buttons enable on a selection inside a popup,
    # which is the harness this file does not have.
    "pickers/bac_picker": ("btn-bac-search", "btn-bac-select"),
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
        _refuse_a_dead_page(page, pre, log)
        page.evaluate(pre.interact)
        page.wait_for_timeout(pre.settle_ms)
        result.states = browser.control_states(page, list(pre.must_enable))
    return result


def _refuse_a_dead_page(page, pre: Precondition, log) -> None:
    """Fail legibly when the page's script did not run at all.

    ``interact`` calls the page's own functions, so on a page whose
    inline ``<script>`` failed to parse every entry here dies inside
    ``page.evaluate`` with a bare ``ReferenceError: <name> is not
    defined`` and a Playwright traceback -- a reader gets the symptom
    of the parse error and no hint of the cause.  Two entries did
    exactly that on this build.

    So the functions ``interact`` is about to name are checked first,
    and the failure says why they would be missing.  Not a
    ``KnownShippedDefect``: this is collateral, the finding is the parse
    error itself (``test_page_scripts.py`` and
    ``test_every_page_the_build_serves_loads_without_throwing``), and a
    second finding for one cause would need a second entry describing
    it.
    """
    named = sorted(set(re.findall(r"\b([A-Za-z_$][\w$]*)\s*\(", pre.interact))
                   - _NOT_PAGE_FUNCTIONS)
    if not named:
        return
    missing = page.evaluate(
        "names => names.filter(n => typeof window[n] !== 'function')", named)
    assert not missing, (
        f"{pre.page}: {missing} are not defined after the page loaded, so "
        "its inline <script> did not execute -- a syntax error in it "
        "discards the whole block and every control with it.  The page "
        f"logged {log.page_errors} {log.console_errors}.  "
        "test_page_scripts.py reports which line")


#: Names that appear as calls in an ``interact`` body and are not the
#: page's own functions: browser built-ins and the DOM.
_NOT_PAGE_FUNCTIONS = frozenset({
    # the DOM and the standard library
    "getElementById", "querySelector", "querySelectorAll", "dispatchEvent",
    "Event", "filter", "forEach", "map", "click", "parseInt", "String",
    "Number", "Array", "Object", "JSON", "console", "setTimeout",
    # JavaScript keywords, which `name (` also matches: every `interact`
    # is an arrow function, so at minimum `async (` is always there.
    "async", "await", "function", "return", "typeof", "new", "delete",
    "if", "for", "while", "switch", "catch", "of", "in",
})


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
    # Exact, not a floor.  ``>= 13`` was here and is the instrument
    # operating principle 5 warns about: it survives a build that stops
    # serving four pages, and this test's whole claim is that *every*
    # page was loaded.  25 on the 2026-09-15 build -- the thirteen form
    # pages, nine pickers, QBE, navigation and logout -- one more than
    # 2026-09-10, which is bac_picker.
    assert len(pages) == 25, sorted(pages)

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


def test_every_button_is_wired_to_a_function_that_exists(app: CbdbApp,
                                                         layout):
    """Every handler a button names, defined on the page that names it.

    The test above asks whether a page *logged* an error.  This asks
    what that error costs, in the terms the defect is actually about:
    of the functions this page's own buttons are wired to, how many
    exist once the page has loaded.  On a page whose inline ``<script>``
    failed to parse, the answer is none of them, and "0 of 37 functions
    reach window" is a different sentence to hand a maintainer from "the
    page logged something".

    It also catches what neither the parse scan nor the load check can:
    a handler renamed in the HTML and not in the script, a function
    declared inside a block that never runs, a top-level ``throw`` after
    the declarations.  Those leave one button dead rather than all of
    them, and nothing else here would see it.

    The buttons and their handlers come from ``controls.inventory``, the
    same extraction the endpoint gate is built from, so a page the build
    adds is covered without anyone remembering.  Only the inline
    ``onclick`` style can be checked this way: a listener bound with
    ``addEventListener`` names a function that need never be global, and
    asserting on those would report correct pages as broken.  How many
    of each is measured below rather than assumed, so a build that moved
    every page to listeners would show as this test covering nothing.
    """
    inventory = controls.inventory(layout)
    assert inventory, "no pages found; the control inventory has gone stale"

    # ``page -> route``, derived rather than listed.  The form pages come
    # from the build's own navigation map -- three of the template
    # directories do not match their route -- and the pickers and QBE
    # from the routing table, which serves them by filename.
    from cbdb_desktop.routes import all_routes, concrete_get_pages, page_map

    route_of = {page: "/" + target
                for page, target in page_map(layout).items()}
    for route in concrete_get_pages(all_routes(layout)):
        stem = route.path.rsplit("/", 1)[-1].removesuffix(".html")
        if route.path.startswith("/Templates/pickers/"):
            route_of[f"pickers/{stem}"] = route.path
        elif route.path == "/QBE":
            route_of["qbe"] = route.path

    wanted: dict[str, tuple[str, list[str]]] = {}
    inline = listeners = 0
    for page, (buttons, _script) in sorted(inventory.items()):
        names = []
        for button in buttons:
            if not button.handler:
                continue
            if button.wiring == "onclick":
                inline += 1
                # The handler is an expression -- ``setLanguage('english')``
                # -- and what has to exist is the function it names.
                called = re.match(r"\s*([A-Za-z_$][\w$]*)\s*\(",
                                  button.handler)
                if called:
                    names.append(called.group(1))
            else:
                listeners += 1
        route = route_of.get(page)
        if route and names:
            wanted[page] = (route, sorted(set(names)))

    assert inline > 100, (
        f"only {inline} buttons are wired with an inline onclick "
        f"({listeners} use addEventListener), so this test is judging "
        "almost nothing.  If the build has moved to listeners, this "
        "needs a different question rather than a smaller one")

    dead: dict[str, list[str]] = {}
    for page, (route, names) in wanted.items():
        with browser.open_page(app.base_url, route) as (browser_page, _log):
            missing = browser_page.evaluate(
                "names => names.filter(n => typeof window[n] !== 'function')",
                names)
        if missing:
            dead[page] = [f"{len(missing)} of {len(names)}"] + sorted(missing)

    assert not dead, (
        "these pages are wired to functions that do not exist once the "
        "page has loaded, so pressing the button does nothing and the "
        f"only trace is a console error: {dead}.  A page missing *all* of "
        "them did not run its script at all -- see test_page_scripts.py "
        "for the line that stopped it")


# ---------------------------------------------------------------------------
# enable state
# ---------------------------------------------------------------------------

def test_every_disabled_control_has_a_declared_precondition(layout):
    """The coverage gate for this file: count what is not covered.

    109 controls ship disabled.  This file declares a precondition for
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
    for page, path in controls.pages(layout).items():
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


def test_all_offices_leaves_the_office_form_able_to_query(app: CbdbApp):
    """Press *All Offices* and Run Query must still work.

    The Office form's handler treats an empty ``officeCodes`` as *every
    office* -- ``if len(p.OfficeCodes) > 0`` is the only thing that adds
    the filter -- and the page's own variable says so: ``let
    _officeCodes = [];   // [] = all offices``.  *All Offices* is the
    button that puts the form into that state, and it is the only way a
    user can ask for an unfiltered office query.

    The 2026-09-15_2 build made Run Query start disabled until an office
    is picked, which is right on its own, and wired it to
    ``updateRunQueryState()``, which greys the button whenever
    ``_officeCodes`` is empty.  *All Offices* calls ``clearOffice()``,
    which empties ``_officeCodes`` -- so the button whose whole purpose
    is to ask for every office now disables the button that would ask.

    Driven rather than read, because the two halves of it are in
    different functions and reading either alone says nothing: the
    sequence is what a user does.  Pick an office, check Run Query is
    live (which is the precondition entry above, asserted again here so
    that a failure of *this* test cannot be the picker's fault), then
    press All Offices and look again.

    The control is the HTTP query the button is asking for: it is sent
    with an empty ``officeCodes`` and must return rows, or the button
    would be disabled in front of a request that does not work anyway
    and this would be a different report.
    """
    unfiltered = app.post("/api/office/query", json={
        "officeCodes": [], "addrIds": [], "peopleAddrIds": [],
        "yearFilterType": "none", "includeSubUnits": False,
    })
    assert unfiltered.status_code == 200, (
        "an office query with no codes -- which is what All Offices asks "
        f"for -- answered HTTP {unfiltered.status_code}: "
        f"{unfiltered.text[:200]}.  The button being disabled would then "
        "be the smaller half of the problem")

    with browser.open_page(app.base_url, "/LookAtOffice") as (page, log):
        page.evaluate(
            "() => { officePickerCallback("
            "{codes: [%d], desc: 'x', descChn: ''}); }" % OFFICE_CODE)
        page.wait_for_timeout(200)
        after_pick = browser.control_states(page, ["btnRunQuery"])["btnRunQuery"]

        page.evaluate("() => { document.getElementById("
                      "'btn-all-offices').click(); }")
        page.wait_for_timeout(200)
        after_all = browser.control_states(
            page, ["btnRunQuery", "btn-all-offices"])

    assert after_pick == "enabled", (
        "Run Query is still disabled after an office was picked, so this "
        "test cannot tell what All Offices does to it -- see the Office "
        f"precondition above, which asks the same question: {after_pick}")

    if after_all["btnRunQuery"] == "disabled":
        raise KnownShippedDefect(
            "pressing All Offices on the Office form disables Run Query.  "
            "The button exists to ask for every office, the handler reads "
            "an empty officeCodes as exactly that, and the same request "
            f"sent over HTTP answers 200 -- but clearOffice() empties "
            "_officeCodes and updateRunQueryState() greys Run Query "
            "whenever it is empty, so no user can send it.  An unfiltered "
            "office query is now unreachable from the page that offers "
            "it, and the only feedback is a button that stops responding")

    assert after_all["btnRunQuery"] == "enabled", (
        f"Run Query is {after_all['btnRunQuery']} after All Offices")
    assert log.clean, (
        f"the Office page logged {log.page_errors} {log.console_errors}")


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
    user's.  It is the honest half of that finding, and the reason the
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
        # The same guard the preconditions get, for the same reason: on
        # a page whose script did not parse, every call below dies as a
        # bare Playwright ReferenceError with the cause nowhere in it.
        missing = page.evaluate(
            "names => names.filter(n => typeof window[n] !== 'function')",
            ["handleEntrySelection", "runQuery", "exportQueryResults"])
        assert not missing, (
            f"the Entry page has no {missing} after loading, so its inline "
            "<script> did not execute and there is no export to account "
            f"for.  The page logged {log.page_errors} {log.console_errors}.  "
            "test_page_scripts.py reports which line")

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

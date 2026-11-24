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
   121 controls across the build ship ``disabled`` (20261021), 53 of them
   with a declared precondition; ``PRECONDITIONS``
   says, per page, what a user does and which controls that must
   un-grey.  It is a table rather than a script so that it reads as a
   claim about the application, and
   ``test_every_disabled_control_has_a_declared_precondition`` is the
   coverage gate over it: a control nobody has declared a precondition
   for sits in ``UNDECLARED``, which is pinned and may only shrink.

3. **What a page tells the user matches what it did.**  The export
   handlers report what the server returned -- a file count up to
   20260916_2, the bundle's name since 20260925 -- as though the browser
   had saved it; here that is compared against the downloads the browser
   accepted.

**Skipped, not failed, without Chromium.**  Playwright downloads its own
browser and a fresh checkout will not have it (see
``cbdb_desktop/browser.py``).  A skipped run says so rather than going
quietly green.

**And this is not the user's browser.**  Downloads are auto-accepted
here, so Chrome's multiple-download permission -- which is what a
per-file download loop is really up against -- never engages and every
file arrives.  What a browser can confirm is what the page reports;
what it cannot is checked by reading the page's own delivery code and
counting the entries each reply carries, in ``test_exports.py``.
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
    #: An input chosen from the shipped database rather than fixed: one
    #: SQL statement whose first row's columns replace ``$1``, ``$2``...
    #: in ``interact``.  It selects a request to send and predicts
    #: nothing (AGENTS.md, "Choosing a cheap input from the data").
    choose: str = ""


#: The start of a Networks ``interact``: choose the person the way the
#: people picker does -- it posts ``people-picker-select`` to the form,
#: whose listener registers the person with the server and then calls
#: ``checkRunCriteria`` -- and wait for that round trip to finish.
_NETWORKS_PICK_PERSON = """async () => {
          window.dispatchEvent(new MessageEvent('message', {data: {
            type: 'people-picker-select',
            person: {personId: %d, name: 'p', nameChn: ''}}}));
          for (let i = 0; i < 100 && !gUsePersonID; i++) {
            await new Promise(done => setTimeout(done, 100));
          }
""" % SUBJECT


#: Any real place, for preconditions that only need *a* place selected:
#: the address is stored by the page, never queried, so the first one
#: serves.  A choice of input, not a prediction.
_ANY_PLACE = ("SELECT c_addr_id FROM ADDR_CODES WHERE c_addr_id > 0 "
              "ORDER BY c_addr_id LIMIT 1")

#: What the address picker does on selection: call the opener's
#: handleAddressSelection with the chosen place.
_PICK_PLACE = """() => {
          handleAddressSelection({selectedAddresses:
            [{id: $1, name: 'x', nameChn: ''}]});
        }"""


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
    #
    # The person is chosen *after* the page has loaded, through the
    # message the people picker posts.  Up to 20260925 this entry seeded
    # ``/api/networks/set-person`` before opening the page; from 20261021
    # (NET-5) serving the page clears ZZ_SIP_NETWORK, so a seeded person
    # is gone by the time the page asks for its count -- correct
    # behaviour, and a user cannot reach the old state anyway.
    Precondition(
        page="networks",
        path="/LookAtNetworks",
        interact=_NETWORKS_PICK_PERSON + """
          for (const id of ['chk-kin', 'chk-nonkin', 'chk-male', 'chk-female']) {
            const box = document.getElementById(id);
            if (box && !box.disabled && !box.checked) {
              box.checked = true;
              box.dispatchEvent(new Event('change'));
            }
          }
        }""",
        must_enable=("btn-run", "chk-kin-param", "btn-all-people"),
        notes="ticking Kinship Relations is what enables Use Kinship "
              "Parameters, so both are asserted together; All People "
              "un-greys on the person being registered",
    ),
    # The Networks form after a real query.  NET-6 (20261021) moved the
    # KML and Include-ID boxes below the exports they modify and greys
    # them until there are results; setExportButtonsEnabled is the one
    # function that decides all nine.  A node distance of 1 keeps the
    # network small.
    Precondition(
        page="networks",
        path="/LookAtNetworks",
        interact=_NETWORKS_PICK_PERSON + """
          for (const id of ['chk-nonkin', 'chk-male', 'chk-female']) {
            const box = document.getElementById(id);
            if (box && !box.disabled && !box.checked) {
              box.checked = true;
              box.dispatchEvent(new Event('change'));
            }
          }
          document.getElementById('txt-node-dist').value = '1';
          await runQuery();
        }""",
        settle_ms=5000,
        must_enable=("chk-kml", "chk-include-id", "btn-gis", "btn-guess",
                     "btn-ucinet", "btn-pajek", "btn-neo4j",
                     "btn-export-results", "btn-store-id"),
        notes="NET-6: the two export checkboxes are disabled until a "
              "query returns, together with the exports they modify",
    ),
    # Association Pairs after a real query on a directly associated pair:
    # the person and one of their associates, chosen from ASSOC_DATA.
    # Both slots are filled through the message the people picker posts,
    # after setting which slot it is for, as the two Select buttons do.
    Precondition(
        page="association_pairs",
        path="/LookAtAssociationPairs",
        choose=f"SELECT c_personid, c_assoc_id FROM ASSOC_DATA "
               f"WHERE c_personid = {SUBJECT} AND c_assoc_id > 0 "
               "ORDER BY c_assoc_id LIMIT 1",
        interact="""async () => {
          for (const [slot, id] of [[1, $1], [2, $2]]) {
            _pickerTarget = slot;
            window.dispatchEvent(new MessageEvent('message', {data: {
              type: 'people-picker-select',
              person: {personId: id, name: 'p' + id, nameChn: ''}}}));
          }
          await runQuery();
        }""",
        settle_ms=3000,
        must_enable=("btnQuery", "chkKML", "btnStoreIDs", "btnExportResults",
                     "btnGIS", "btnNeo4j", "btnPajek", "btnGephi",
                     "btnUCINet"),
        notes="Run Query un-greys once both people are chosen; the KML box "
              "(new in 20261021) and the exports once the pair has a result",
    ),
    # Status: choosing a place is what un-greys Include sub-units and
    # Use XY (STA-2, 20261021) and All Places.  The address is only
    # stored, never queried here, so any real one serves.
    Precondition(
        page="status",
        path="/LookAtStatus",
        choose="SELECT c_addr_id FROM ADDR_CODES WHERE c_addr_id > 0 "
               "ORDER BY c_addr_id LIMIT 1",
        interact="""() => {
          handleAddressSelection({selectedAddresses:
            [{id: $1, name: 'x', nameChn: ''}]});
        }""",
        settle_ms=200,
        must_enable=("chkSubUnits", "chkUseXY", "btnAllPlaces",
                     "btnRunQuery"),
        notes="STA-2: the address checkboxes are disabled until a place is "
              "selected; a place alone is also enough to run a query",
    ),
    # Status after a real query on a sparse status code.
    Precondition(
        page="status",
        path="/LookAtStatus",
        choose="SELECT c_status_code FROM STATUS_DATA "
               "GROUP BY c_status_code HAVING COUNT(*) BETWEEN 2 AND 12 "
               "ORDER BY COUNT(*) DESC, 1 LIMIT 1",
        interact="""async () => {
          handleStatusSelection([$1], ['x'], null, '', '');
          await runQuery();
        }""",
        settle_ms=3000,
        must_enable=("chkKML", "btnExportGIS", "btnExportNeo4j",
                     "btnExportResults", "btnStoreIDs"),
        notes="the KML box beside Save to GIS, and the exports, once the "
              "query has a result",
    ),
    # Texts: Main source only and Self-biography only apply only to
    # Biographical Sources (TXT-1, 20261021), so choosing that query mode
    # -- clicking its radio button -- is what un-greys them.
    Precondition(
        page="texts",
        path="/LookAtTexts",
        interact="""() => {
          document.getElementById('qmode-source').click();
        }""",
        settle_ms=200,
        must_enable=("chk-main-source", "chk-self-bio"),
        notes="TXT-1: disabled in the default Both mode",
    ),
    # Texts: choosing a place un-greys the address checkboxes (TXT-2).
    Precondition(
        page="texts",
        path="/LookAtTexts",
        choose="SELECT c_addr_id FROM ADDR_CODES WHERE c_addr_id > 0 "
               "ORDER BY c_addr_id LIMIT 1",
        interact="""() => {
          handleAddressSelection({selectedAddresses:
            [{id: $1, name: 'x', nameChn: ''}]});
        }""",
        settle_ms=200,
        must_enable=("chk-sub-units", "chk-use-xy"),
        notes="TXT-2: disabled until a place is selected",
    ),
    # Query Builder: Copy SQL and Save SQL (QBE-3, 20261021) un-grey once
    # a query has run.  A one-column query on DYNASTIES, the smallest
    # table a user would reach for: add the table, double-click a field
    # into the grid, press Run.
    Precondition(
        page="qbe",
        path="/QBE",
        interact="""async () => {
          addTableBox('DYNASTIES');
          addFieldToGrid('t1', 'c_dynasty');
          document.getElementById('btnRun').click();
        }""",
        settle_ms=3000,
        must_enable=("btnCopySQL", "btnSaveSQL"),
        notes="QBE-3: the SQL tab's Copy and Save are disabled until there "
              "is SQL to copy",
    ),
    # Build_20261028 gave every form with an address filter the rule
    # Status and Texts had in 20261021 (the developers' ENT-1, ASC-1,
    # OFF-1, PLC-7, TXT-6): Include Subordinate Units and Use XY are
    # greyed until a place is selected, and so is the All Places button
    # that clears it.  Each is driven through the page's own
    # handleAddressSelection, which is what the address picker calls.
    Precondition(
        page="entry",
        path="/LookAtEntry",
        choose=_ANY_PLACE,
        interact=_PICK_PLACE,
        settle_ms=200,
        must_enable=("chkSubUnits", "chkUseXY"),
        notes="ENT-1: disabled until a place is selected",
    ),
    Precondition(
        page="associations",
        path="/LookAtAssociations",
        choose=_ANY_PLACE,
        interact=_PICK_PLACE,
        settle_ms=200,
        must_enable=("chk-subunits", "chk-usexy"),
        notes="ASC-1: disabled until a place is selected",
    ),
    Precondition(
        page="places",
        path="/LookAtPlace",
        choose=_ANY_PLACE,
        interact=_PICK_PLACE,
        settle_ms=200,
        must_enable=("include-sub-units", "use-xy", "btnAllPlaces"),
        notes="PLC-7: the address options and All Places wait for a place",
    ),
    # The Office form has two place filters, the people's and the
    # office's; the picker fills whichever _addrPickerTarget names, as
    # its two Select buttons set it.  Both are driven.
    Precondition(
        page="office",
        path="/LookAtOffice",
        choose=_ANY_PLACE,
        interact="""() => {
          for (const target of ['people', 'office']) {
            _addrPickerTarget = target;
            handleAddressSelection({selectedAddresses:
              [{id: $1, name: 'x', nameChn: ''}]});
          }
        }""",
        settle_ms=200,
        must_enable=("chk-sub-people", "chk-xy-people",
                     "btn-all-places-people", "chk-sub-office",
                     "chk-xy-office", "btn-all-places-office"),
        notes="OFF-1: each place filter's options, and its All Places, "
              "un-grey when that filter has a place",
    ),
    # Texts: All Places and All Texts clear a selection, so they are
    # grey until there is one (TXT-6).
    Precondition(
        page="texts",
        path="/LookAtTexts",
        choose=_ANY_PLACE,
        interact="""() => {
          handleAddressSelection({selectedAddresses:
            [{id: $1, name: 'x', nameChn: ''}]});
          textsPickerCallback({codes: [$1], desc: 'x', descChn: ''});
        }""",
        settle_ms=200,
        must_enable=("btnAllPlaces", "btnAllTexts"),
        notes="TXT-6: the two clear buttons wait for something to clear; "
              "the text code is only stored, never queried, so any "
              "integer serves",
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
    # The Entry form's Run Query, which ships disabled as of 20260925
    # (updateEnableState: "Run Query needs at least one of: an entry
    # selection or a place").  Driven through the page's own picker
    # callback, which is what the popup calls on selection.
    Precondition(
        page="entry",
        path="/LookAtEntry",
        interact=f"""() => {{
          handleEntrySelection([{ENTRY_CODE}], ['t'], ['t'], '', '', '');
        }}""",
        settle_ms=200,
        # Save Codes un-greys on the same selection
        # (``btnSaveCodes.disabled = false`` in handleEntrySelection).
        must_enable=("btnQuery", "btnSaveCodes"),
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
        must_enable=("btnRunQuery", "btn-all-offices"),
        notes="new in the 2026-09-15_2 build; what All Offices does to "
              "it -- every office within a place, since 20260925 -- is "
              "test_all_offices_leaves_the_office_form_able_to_query",
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
    # Eight fewer than 20260925: the query-result precondition declared
    # in 20261021 covers Run Query and every export.  Clear List needs an
    # imported file, which is a file chooser.
    "association_pairs": ("btnClearList",),
    "associations": ("btn-export-query", "btn-kml", "btn-neo4j", "btn-store",
                     "btn-tab"),
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
    # disabled.  Nine fewer again in 20261021: btn-rerun went with NET-4,
    # and All People plus the seven exports are now declared.
    "networks": ("btn-all-places", "btn-recall-id", "chk-place-limit",
                 "chk-sub-units", "chk-xy-ref", "txt-max-col", "txt-max-dwn",
                 "txt-max-mar", "txt-max-up"),
    # Three fewer since Build_20261028: All Offices and the two All
    # Places buttons are declared with the place preconditions.
    "office": ("btn-export-results",
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
    # Both pickers lost their search "Next" button in the 2026-09-16_2
    # build, which reworked their search to filter the loaded list
    # rather than step through matches one at a time.
    "pickers/entry_picker": ("btn-entry-select", "btn-search",
                             "btn-select-all"),
    "pickers/office_picker": ("btn-select",),
    "pickers/status_picker": ("btn-search",
                              "btn-select-all", "btn-status-select"),
    "pickers/texts_picker": ("btn-select",),
    "places": ("btnExportNeo4j", "btnExportResults", "btnRunQuery",
               "btnSaveGIS", "btnSaveKML", "btnStorePersonIDs"),
    # Empty since 20261021: the place and query-result preconditions
    # declare every control the Status form ships disabled.
    "texts": ("btn-export-results", "btn-kml", "btn-neo4j", "btn-store",
              "btn-tab"),
}

@dataclass
class _Result:
    states: dict[str, str] = field(default_factory=dict)
    log: browser.PageLog = field(default_factory=browser.PageLog)


def _interaction(pre: Precondition, sqlite_conn) -> str:
    """``pre.interact`` with its chosen inputs filled in."""
    if not pre.choose:
        return pre.interact
    row = sqlite_conn.execute(pre.choose).fetchone()
    assert row, f"{pre.page}: the data offers no input for {pre.choose!r}"
    script = pre.interact
    # Highest index first, so $1 does not eat the front of $12.
    for index in range(len(row), 0, -1):
        script = script.replace(f"${index}", str(int(row[index - 1])))
    return script


def _drive(app: CbdbApp, pre: Precondition, sqlite_conn=None) -> _Result:
    """Establish a precondition in a browser and read the control states."""
    for path, body in pre.seed:
        response = app.post(path, json=body)
        assert response.status_code == 200, \
            f"{pre.page}: seeding {path} gave {response.status_code}"
    interact = _interaction(pre, sqlite_conn)

    result = _Result()
    with browser.open_page(app.base_url, pre.path) as (page, log):
        result.log = log
        _refuse_a_dead_page(page, pre, log)
        page.evaluate(interact)
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
    named = sorted(set(re.findall(r"(?<![.\w$])([A-Za-z_$][\w$]*)\s*\(",
                                  pre.interact)) - _NOT_PAGE_FUNCTIONS)
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
#: Only keywords and constructors.  A *method* call cannot reach this
#: list at all -- the pattern above refuses a name preceded by a dot --
#: which is what keeps a future `interact` using `.closest()` or
#: `.trim()` from failing the guard with a nonsense message.  Keeping
#: the DOM's method names here as well would have worked today and hidden
#: that hole until somebody used a method nobody had thought of.
_NOT_PAGE_FUNCTIONS = frozenset({
    "async", "await", "function", "return", "typeof", "new", "delete",
    "if", "for", "while", "switch", "catch", "of", "in", "void",
    "Event", "MessageEvent", "Array", "Object", "String", "Number",
    "Promise", "Date",
    "parseInt", "parseFloat", "setTimeout", "JSON", "console",
})


# ---------------------------------------------------------------------------
# does the page load at all
# ---------------------------------------------------------------------------

#: The one page that throws while loading in the 20261021 build, and
#: exactly what it logs.  Recognising this shape is what lets any other
#: page that starts throwing arrive as an ordinary failure.
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


def test_group_data_can_be_used_before_its_first_query(app: CbdbApp):
    """Import a list of people into Group Data, as the first thing a user does.

    The load check above says the page throws; this says what that
    costs a user, measured on the first action the form asks for.  A
    file with one person ID is handed to the page's own file input --
    the same ``change`` event the Import button's file chooser fires --
    and once the server has answered, the import must have taken:
    no error shown, and Clear (which ships disabled) enabled so the list
    can be emptied again.
    """
    with browser.open_page(app.base_url, "/LookAtGroupData") as (page, log):
        with page.expect_response(
                lambda r: "/api/groupdata/import-ids" in r.url) as answer:
            page.set_input_files("#fileImport", files=[{
                "name": "people.txt", "mimeType": "text/plain",
                "buffer": f"{SUBJECT}\n".encode("ascii")}])
        status = answer.value.status
        page.wait_for_timeout(500)
        error = page.evaluate(
            "() => { const e = document.getElementById('globalError');"
            " return e && !e.classList.contains('hidden') ? e.textContent : ''; }")
        states = browser.control_states(page, ["btnClear", "btnImport"])
        loaded = page.evaluate("() => loadedPeople.length")

    assert status == 200, f"the server refused the import: HTTP {status}"
    assert not error, f"Group Data reported an error after an import: {error}"
    assert states["btnClear"] == "enabled", (
        f"after importing {loaded} person(s), Clear is {states['btnClear']}")
    assert log.clean, f"Group Data logged {log.page_errors} {log.console_errors}"


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
    unrouted = []
    inline = listeners = 0
    for page, (buttons, _script) in sorted(inventory.items()):
        names: set[str] = set()
        for button in buttons:
            if not button.handler:
                continue
            if button.wiring != "onclick":
                listeners += 1
                continue
            inline += 1
            # An ``onclick`` is an expression and may hold more than one
            # call: the Browser page wires ten of its tabs as
            # ``showTab('tab-kinship', this); loadTabKinship()``.  Taking
            # only the first left all ten ``loadTab*`` unchecked -- and
            # one of them is the function another test in this file
            # depends on.  The lookbehind keeps a method call out: what
            # must exist on ``window`` is a bare name, not ``.slice``.
            names |= set(re.findall(r"(?<![.\w$])([A-Za-z_$][\w$]*)\s*\(",
                                    button.handler)) - _NOT_PAGE_FUNCTIONS
        route = route_of.get(page)
        if names and not route:
            unrouted.append(page)
        elif route and names:
            wanted[page] = (route, sorted(names))

    assert not unrouted, (
        f"these pages have buttons wired to named functions and no route "
        f"this test knows how to open: {unrouted}.  They were silently "
        "skipped, so the gate was covering less than it reports -- a form "
        "directory that ships before it is wired into the navigation map "
        "lands here")

    # Exact, not a floor.  ``> 100`` was here, and it survives a build
    # that moves half these buttons to addEventListener -- which is the
    # silent shrink the guard exists to prevent, and which nothing else
    # would notice, because EXPECTED_BUTTONS pins the totals and not the
    # split.  Operating principle 5, applied to this file's own coverage.
    # (202, 41) on 20260925.  20261021 removed Networks' inline Rerun
    # button (NET-4) and added three listener-wired Query Builder buttons:
    # Copy SQL, Save SQL (QBE-3) and the join dialog's + Add fields (QBE-4).
    # Build_20261028 added four inline buttons and removed one: the Query
    # Builder's EN / 繁 / 简, the Places form's All Places (PLC-7), and
    # Status lost its Help button (STA-5).
    assert (inline, listeners) == (204, 44), (
        f"{inline} buttons are wired with an inline onclick and "
        f"{listeners} with addEventListener, against 204 and 44.  Only "
        "the first kind can be checked here -- a listener's function "
        "need never be global -- so a build that moved them would "
        "shrink this test without failing it")

    dead: dict[str, list[str]] = {}
    for page, (route, names) in wanted.items():
        try:
            with browser.open_page(app.base_url, route) as (browser_page, _log):
                missing = browser_page.evaluate(
                    "names => names.filter("
                    "n => typeof window[n] !== 'function')", names)
        except RuntimeError as exc:
            dead[page] = [f"the page would not open: {exc}"]
            continue
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

    134 controls ship disabled on Build_20261028.  This file declares a
    precondition for 69 of them; the rest are listed in ``UNDECLARED``, pinned, and
    that list may only shrink.  Without this the file would look like
    full coverage of enable state while checking four pages' worth.

    A control that leaves ``UNDECLARED`` without gaining a
    ``Precondition`` fails here, and so does a new disabled control in a
    new build -- which is the same guarantee the export and endpoint
    inventories give.
    """
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


def test_all_offices_leaves_the_office_form_able_to_query(
        app: CbdbApp, sqlite_conn):
    """*All Offices* within a place must still be a query a user can run.

    What *All Offices* means changed in 20260925, on both sides at once.
    The handler now refuses a request with no office, no people address
    and no office address ("Select at least one office or a place.",
    HTTP 400), and says why: an empty ``officeCodes`` means every office
    *within an address filter*.  The page's ``updateRunQueryState``
    greys Run Query on exactly the same three conditions.  So the
    earlier contract -- All Offices alone asks for every office in
    CBDB -- is gone by design, and asserting it would be asserting a
    feature the build no longer offers.

    What is left, and still has to hold, is agreement between the two
    halves, in both directions:

    * All Offices with a place chosen: Run Query stays live, and the
      request it sends -- no office codes, that place -- answers rows.
    * All Offices with no place: Run Query is grey, and the server
      refuses the same request.  A page that let it through would show
      the user a 400; one that greyed a request the server would answer
      would hide a query nothing else can ask for.

    Driven rather than read, because the halves are in different
    functions: the sequence is what a user does.  What is observed on
    the page is the button's state; the request is sent over HTTP by
    hand, in the shape ``runQuery`` builds it (``officeAddrIds:
    _officeAddrIDs``), not captured from the page.  The place is chosen
    from the data (an office address with a handful of postings), then
    checked against the application, as every input here is.
    """
    candidates = [row[0] for row in sqlite_conn.execute(
        "SELECT c_addr_id FROM POSTED_TO_ADDR_DATA WHERE c_addr_id > 0 "
        "GROUP BY c_addr_id HAVING COUNT(*) BETWEEN 2 AND 12 "
        "ORDER BY COUNT(*) DESC, 1 LIMIT 10")]
    base = {"officeCodes": [], "peopleAddrIds": [], "officeAddrIds": [],
            "yearFilterType": "none"}
    place = None
    for addr in candidates:
        response = app.post("/api/office/query",
                            json=dict(base, officeAddrIds=[addr]))
        assert response.status_code == 200, (
            f"every office at office address {addr} -- what All Offices "
            f"plus a place asks for -- answered HTTP "
            f"{response.status_code}: {response.text[:200]}")
        rows = response.json()
        # The cap and the per-row check are what make "answers rows" mean
        # "answers the place".  No office query has a LIMIT, so a handler
        # that stopped applying officeAddrIds would hand back the whole
        # Office table here and, without them, still be taken as a place
        # that works.
        assert len(rows) < 5000, (
            f"every office at office address {addr} returned {len(rows)} "
            "rows for an address with a handful of postings -- the "
            "address filter has stopped filtering")
        stray = sorted({row.get("officeAddrId") for row in rows} - {addr},
                       key=str)
        assert not stray, (
            f"asked for postings at office address {addr}, got rows at "
            f"{stray[:5]}")
        if rows:
            place = addr
            break
    assert place is not None, (
        f"none of the office addresses {candidates} returns a posting")

    refused = app.post("/api/office/query", json=base)

    with browser.open_page(app.base_url, "/LookAtOffice") as (page, log):
        # The same guard the preconditions get: on a page whose script
        # did not parse, the call below is a bare ReferenceError with
        # the cause nowhere in it.
        absent = page.evaluate(
            "names => names.filter(n => typeof window[n] !== 'function')",
            ["officePickerCallback", "clearOffice", "handleAddressSelection",
             "openOfficeAddressPicker", "clearOfficeAddress"])
        assert not absent, (
            f"the Office page has no {absent} after loading, so its "
            "inline <script> did not execute and there is no enable "
            f"state to judge.  The page logged {log.page_errors} "
            f"{log.console_errors}.  test_page_scripts.py has the line")

        def run_query_state() -> str:
            page.wait_for_timeout(200)
            return browser.control_states(page, ["btnRunQuery"])["btnRunQuery"]

        def press_all_offices() -> None:
            page.evaluate("() => { document.getElementById("
                          "'btn-all-offices').click(); }")

        page.evaluate(
            "() => { officePickerCallback("
            "{codes: [%d], desc: 'x', descChn: ''}); }" % OFFICE_CODE)
        after_pick = run_query_state()

        # All Offices, no place.
        press_all_offices()
        alone = run_query_state()

        # A place, then All Offices again.  The picker popup is what
        # calls handleAddressSelection; its target is set by the button
        # that opened it, which is set here without opening a window.
        page.evaluate(
            "() => { officePickerCallback("
            "{codes: [%d], desc: 'x', descChn: ''}); }" % OFFICE_CODE)
        page.evaluate(
            "addr => { _addrPickerTarget = 'office'; handleAddressSelection("
            "{selectedAddresses: [{id: addr, name: 'x', nameChn: ''}]}); }",
            place)
        press_all_offices()
        with_place = run_query_state()

        logged = f"{log.page_errors} {log.console_errors}"
        clean = log.clean

    assert clean, f"the Office page logged {logged}"
    assert after_pick == "enabled", (
        "Run Query is still disabled after an office was picked, so this "
        "test cannot tell what All Offices does to it -- see the Office "
        f"precondition above, which asks the same question: {after_pick}")

    assert with_place == "enabled", (
        f"with office address {place} chosen, pressing All Offices leaves "
        f"Run Query {with_place} -- and the request it would send answers "
        "rows.  A query the handler accepts is unreachable from the page")

    assert refused.status_code == 400, (
        "with no office and no place the handler answered HTTP "
        f"{refused.status_code}, not the 400 this build's rule gives: "
        f"{refused.text[:200]}.  If an unfiltered query is allowed again, "
        "All Offices alone should enable Run Query")
    assert alone == "disabled", (
        f"with no place chosen, All Offices leaves Run Query {alone}, and "
        "the request it would send is refused with HTTP 400 -- the page "
        "offers a query the server will not run")


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
                                                           pre: Precondition,
                                                           sqlite_conn):
    """Do the thing the control waits for, and check it un-greys.

    The user-visible property, measured.  A control still disabled here
    is a control the user cannot press having done everything the form
    asks -- and the server, asked the same question over HTTP, answers
    perfectly.
    """
    result = _drive(app, pre, sqlite_conn)

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

            # Two phrasings.  Up to 20260916_2 the page reported a count
            # ("2 file(s) ready"); 20260925 bundles the files into one
            # ZIP and names what it delivered instead ("Query results
            # export: EntryResults.zip compressed to ZIP file").  A name
            # is a stronger claim than a count, so it is checked
            # against the names the browser saved as well.
            named = None
            match = re.search(r"(\d+)\s*file\(s\)", claimed)
            if match:
                said = int(match.group(1))
            else:
                match = re.search(r"export:\s*(.+?)\s+compressed to ZIP",
                                  claimed)
                assert match, (
                    f"press {press}: the page said {claimed!r}, which "
                    "reports neither a file count nor the files it "
                    "delivered -- update this test if the message changed")
                named = [n.strip() for n in match.group(1).split(",")
                         if n.strip()]
                said = len(named)

            assert said == len(attempted), (
                f"press {press}: the page claims {said} file(s) and "
                f"attempted {len(attempted)} downloads -- it is not even "
                "reporting its own intention")
            assert said == len(accepted), (
                f"press {press}: the page claims {said} file(s) and the "
                f"browser accepted {len(accepted)} ({accepted}).  On a "
                "browser that declines automatic multiple downloads this "
                "is what the user sees, and the message is a lie.")
            if named is not None:
                assert sorted(named) == sorted(accepted), (
                    f"press {press}: the page says it delivered {named} and "
                    f"the browser saved {accepted}")

            # Let the message expire before the next press, so the poll
            # above cannot read the previous one.
            page.wait_for_timeout(3200)

"""What each page sends, against what its handler actually does with it.

Every other module in this suite asks whether a *handler* is right.  This
one asks a question one layer out, which the rest cannot see: whether the
page and the handler agree about the request and the reply.  A form here
is two programs -- Go behind an HTTP boundary, JavaScript in front of it
-- and the boundary is JSON, which fails silently in both directions.  A
field the page does not send arrives as a zero value; a field the handler
does not read is a control the user can set to no effect; a reply shaped
differently from what the page checks becomes an error message on a
request that in fact succeeded.  None of these produce a stack trace, a
non-200, or a wrong row, so nothing that tests a handler alone can find
them.

Four shapes of disagreement, and the tests below are grouped by them:

* **the reply the page cannot read** -- the handler answers correctly and
  the page reports failure, because the two envelopes differ;
* **the control that reaches nothing** -- a checkbox or a number the page
  faithfully sends, and no line of Go ever reads;
* **the capability with no way in** -- a branch in the handler that no
  control on its page can select;
* **the answer that is quietly partial** -- a row dropped, or an
  arbitrary subset returned, with a 200 either way.

The oracles are the ones this suite already allows: the shipped source
read as data, agreement between endpoints of one form, and base-table
membership.  Nothing below reproduces a handler's query in Python.

A note on how the pinned sets are written.  Each is an exact set, not a
floor: a build that fixes one of these fails here rather than passing
quietly, which is the point of recording it.  Where a survey turns up
cases of more than one kind -- a ``LIMIT`` that is arbitrary and a
``LIMIT`` that is a keyed lookup -- both are listed, and the reason for
splitting them is written next to the split rather than left to the
reader.
"""
from __future__ import annotations

import re

import pytest

from cbdb_desktop import gosource
from cbdb_desktop.app import CbdbApp
from cbdb_desktop.defects import KnownShippedDefect
from cbdb_desktop.staging import AppLayout
from cbdb_desktop.subjects import SUBJECT

# ---------------------------------------------------------------------------
# reading the shipped source as data
# ---------------------------------------------------------------------------

#: One field of a Go struct that carries a ``json:`` tag.  Anonymous and
#: embedded fields have no name to match and are skipped, which is right:
#: they are not what a page addresses.
_JSON_FIELD = re.compile(
    r"^[ \t]*(?P<go>[A-Z]\w*)\s+[\w\*\[\]\.]+\s+`json:\"(?P<js>[\w]+)",
    re.MULTILINE)

#: A package-level struct declaration.  The body ends at a ``}`` in the
#: first column, which is where ``gofmt`` puts it for a top-level type.
#: Function-local structs (``type placeHit struct`` inside a handler) are
#: indented and so are *not* matched -- deliberately: they are not what a
#: page addresses, and admitting them would attribute their fields to a
#: body running on to the enclosing function's close.
_STRUCT = re.compile(r"^type\s+(?P<name>\w+)\s+struct\s*\{(?P<body>.*?)^\}",
                     re.DOTALL | re.MULTILINE)

#: A backtick-quoted Go literal.  Every SQL statement carrying a
#: ``LIMIT`` is written this way in the shipped build, which is what the
#: survey below relies on -- ``networks_form_query.go`` does assemble some
#: clauses from double-quoted concatenation, and those would not be seen
#: here.  Checked rather than assumed: none of them contains a ``LIMIT``.
_GO_LITERAL = re.compile(r"`([^`]*)`", re.DOTALL)


@pytest.fixture(scope="module")
def go_text(layout: AppLayout) -> dict[str, str]:
    """``{filename: source}`` for the application's Go, read once.

    ``layout.go_sources()`` is ``Code/*.go``: the sources behind
    ``cbdb.exe``.  It excludes ``CBDBSetUpCode/``, which builds the
    database rather than serving it, and the ``*_test.go`` the build
    ships.  Every "in the build" below means this population -- a field
    read only by the setup program would show here as unread, which is
    why the pinned sets record what each unread field faces rather than
    just counting them.
    """
    return {p.name: p.read_text(encoding="utf-8", errors="replace")
            for p in layout.go_sources()}


@pytest.fixture(scope="module")
def page_text(layout: AppLayout) -> dict[str, str]:
    """``{form: index.html}`` for every form page, read once.

    Only ``index.html`` -- the build ships dated siblings beside several
    of them (``networks.index.20260813.html`` and friends) which are
    previous versions kept for reference and which no route serves.
    Reading those would let a control that has since been *removed* go on
    satisfying a test.
    """
    return {form: path.read_text(encoding="utf-8", errors="replace")
            for form, path in layout.form_templates().items()}


@pytest.fixture(scope="module")
def all_pages(layout: AppLayout) -> dict[str, str]:
    """Every live template, pickers included, keyed by path from Templates/.

    ``page_text`` above is the form pages; this is everything a browser
    can be served, which for questions about what the *application* calls
    is the right population -- a picker is where several helper endpoints
    would be called from if anything called them.

    The dated siblings are excluded for the same reason as above: a
    control removed from the live page must not go on being satisfied by
    a copy of the page from before it was removed.
    """
    live = {}
    for path in sorted(layout.templates_dir.rglob("*.html")):
        # `name.<8 digits>.html` -- the build's convention for a kept copy.
        if re.search(r"\.\d{8}\.html$", path.name):
            continue
        key = path.relative_to(layout.templates_dir).as_posix()
        live[key] = path.read_text(encoding="utf-8", errors="replace")
    assert live, "no templates found; the layout has changed shape"
    return live


# ===========================================================================
# 1. the reply the page cannot read
# ===========================================================================

#: What the Association Pairs page does with each export reply, read off
#: ``Templates/association_pairs/index.html``.  All four call sites are
#: written to the same recipe -- ``if (j.status !== 'ok') throw`` and then
#: ``j.files.forEach`` -- so a handler that answers in any other shape is
#: reported to the user as a failure no matter what it produced.
_ASSOCPAIRS_EXPORTS = {
    "export-gis":     {"useKML": False},
    "export-sna":     {"format": "pajek"},
    "export-neo4j":   {},
}

#: The exports that answer in the shape the page reads.  Naming them is
#: what makes this test an agreement check between endpoints of one form
#: rather than a rule this suite invented: same file, and two of the four
#: already do it.
#:
#: Only ``export-neo4j`` is parametrised above, and so only it is driven
#: as a control.  ``export-results`` takes no request body at all -- it
#: reads the form's scratch tables -- so reaching it needs a query to have
#: run first, which is a different test's setup and is where it is
#: covered.  It is named here rather than silently omitted, because the
#: count in the docstring below rests on it.
_ANSWERS_IN_THE_PAGES_SHAPE = frozenset({"export-neo4j", "export-results"})


def _assocpairs_person(person_id: int) -> dict:
    """One row in the shape ``AssocPairsPersonRecord`` declares.

    The handlers under test need only a non-empty ``people`` list -- each
    begins ``if len(req.People) == 0 { 400 }`` -- so this is the smallest
    request that reaches the reply, and the reply is what is being
    judged.
    """
    return {"personId": person_id, "name": "", "nameChn": ""}


@pytest.mark.parametrize("endpoint", sorted(_ASSOCPAIRS_EXPORTS))
def test_an_assocpairs_export_answers_in_the_envelope_its_page_reads(
        app: CbdbApp, endpoint: str):
    """Four export buttons, one reply shape, and two handlers that use it.

    ``exportGIS``, ``exportSNA`` and ``exportNeo4j`` in the page share a
    recipe: post, ``if (!resp.ok) throw``, then

        const j = await resp.json();
        if (j.status !== 'ok') throw new Error(j.status || 'Unknown error');
        (j.files || []).forEach(f => triggerDownload(f.url, f.name));

    ``handleExportNeo4j`` and ``handleExportResults`` encode
    ``{"status": "ok", "files": [...]}``, which that recipe reads.
    ``handleExportGIS`` and ``handleExportSNA`` encode ``{"url": ...,
    "name": ...}`` instead.  ``undefined !== 'ok'`` is true, so the page
    throws ``Error(undefined || 'Unknown error')`` and shows *"GIS export
    error: Unknown error"* -- on a 200 whose body holds the finished
    file, correctly built, base64 in hand.

    That is four buttons the user cannot use: GIS, and the three SNA
    formats behind ``export-sna``.  The failure is not in either half on
    its own, which is why no handler test and no page test finds it.
    """
    body = dict(_ASSOCPAIRS_EXPORTS[endpoint])
    body["people"] = [_assocpairs_person(SUBJECT)]
    body["network"] = []

    response = app.post(f"/api/assocpairs/{endpoint}", json=body)
    assert response.status_code == 200, (
        f"{endpoint} refused the smallest request its own guard admits: "
        f"HTTP {response.status_code} {response.text[:200]}")

    payload = response.json()
    understood = payload.get("status") == "ok"

    if endpoint in _ANSWERS_IN_THE_PAGES_SHAPE:
        assert understood, (
            f"{endpoint} was the control for this test and no longer "
            f"answers as the page reads it: keys {sorted(payload)}")
        return

    if not understood:
        raise KnownShippedDefect(
            f"/api/assocpairs/{endpoint} built the export and answered "
            f"with keys {sorted(payload)}; its page throws unless the "
            "reply carries status=='ok', so it reports 'Unknown error' "
            "and downloads nothing.  Two exports of the same form "
            "(export-neo4j, export-results) answer in the shape the page "
            "reads, so this is a disagreement inside one file rather "
            "than a convention this suite is imposing")


# ===========================================================================
# 2. the control that reaches nothing
# ===========================================================================

def _request_keys(page: str, endpoint: str) -> set[str]:
    """The JSON keys the page posts to ``endpoint``.

    Reads the ``JSON.stringify({...})`` that belongs to the ``fetch`` for
    that endpoint, so what comes back is what the *page sends* -- not
    every occurrence of a name in the file.  That distinction is the
    whole point: several of these names also appear as DOM ids and as
    globals the page computes and then drops, and a substring search
    would report a page as sending a field it merely knows about.

    Shorthand (``{ people, network, useKML }``) and explicit
    (``{ format: fmt }``) both appear in these pages, so both are read.
    """
    fetch = re.search(r"fetch\(\s*'/api/" + re.escape(endpoint) + r"'.*?\}\s*\)",
                      page, re.DOTALL)
    if not fetch:
        return set()
    body = re.search(r"JSON\.stringify\(\s*\{(?P<keys>[^}]*)\}", fetch.group(0))
    if not body:
        return set()
    return {part.split(":", 1)[0].strip()
            for part in body.group("keys").split(",") if part.strip()}


def _only_file_named_by(response) -> str:
    """The name of the single file an Association Pairs export returned.

    These five exports answered with a bare ``{name, url}`` until the
    2026-09-15 build moved them to the ``{status, files}`` envelope the
    page has always required -- which is the fix to the Unknown-error
    finding, and the reason this helper exists rather than a
    ``.get("name")``.  Asserting the envelope here as well as in
    ``exports.py`` is deliberate: this test's conclusions are drawn from
    the file name, so reading it out of the wrong shape would make them
    statements about nothing.
    """
    assert response.status_code == 200,         f"export-gis refused a minimal request: {response.text[:200]}"
    payload = response.json()
    assert payload.get("status") == "ok" and payload.get("files"), (
        "an Association Pairs export no longer answers with "
        f"{{status: 'ok', files: [...]}}: {sorted(payload)}.  The page "
        "throws on anything else, so this is a user-visible change")
    return payload["files"][0]["name"]


def test_the_assocpairs_kml_checkbox_changes_what_comes_back(
        app: CbdbApp, page_text: dict[str, str], go_text: dict[str, str]):
    """``chkKML`` is sent as ``useKML``; the handler reads ``format``.

    The page has a KML checkbox, reads it, and posts ``useKML`` with the
    export.  ``AssocPairsExportParams`` has no ``UseKML`` field -- the
    handler branches on ``req.Format == "kml"``, and the page never sends
    ``format`` to this endpoint.  So the box is inert: ticked or not, the
    reply is the same ``.tsv``.

    Both halves are judged, and the *page* is what the verdict rests on.
    Driving the endpoint alone would not do: the fix this defect asks for
    is that the page send ``format`` as its siblings do, and a test built
    from hand-written request bodies cannot tell a page that has been
    fixed from one that has not.  So the request the page builds is read
    as data, and the endpoint is driven to show what that request buys.
    """
    exported = _request_keys(page_text["association_pairs"], "assocpairs/export-gis")
    assert exported, \
        "the Association Pairs page no longer posts to export-gis"

    handler = go_text["assocpairs_form_backend.go"]
    struct = _STRUCT.search(handler[handler.index("type AssocPairsExportParams"):])
    read_by_handler = {m.group("js") for m in _JSON_FIELD.finditer(struct.group("body"))}

    ignored = exported - read_by_handler

    # The control first: driven with the key the *handler* declares, the
    # KML writer works.  This has to be measured separately from the
    # page's own key, because it is the fact that makes the mismatch a
    # defect rather than a missing feature -- and because it stays true
    # whether the page is fixed or not, so it is still a control on the
    # build after somebody acts on this.
    body = {"people": [_assocpairs_person(SUBJECT)], "network": []}
    reachable = app.post("/api/assocpairs/export-gis",
                         json=dict(body, format="kml"))
    assert reachable.status_code == 200, \
        f"export-gis refused a minimal request: {reachable.text[:200]}"
    by_handlers_key = _only_file_named_by(reachable)
    assert by_handlers_key.endswith(".kml"), (
        f"asking export-gis for format='kml' produced {by_handlers_key!r}; "
        "the KML writer is broken independently of which key selects it, "
        "which is a different defect from the one this test reports")

    # Then the page's key, which is the thing under test.
    ticked = _only_file_named_by(
        app.post("/api/assocpairs/export-gis", json=dict(body, useKML=True)))

    if ignored:
        raise KnownShippedDefect(
            f"the Association Pairs page sends {sorted(ignored)} to "
            f"export-gis and AssocPairsExportParams declares "
            f"{sorted(read_by_handler)}, so the key never binds: ticking "
            f"the box yields {ticked!r}, while the same request with the "
            f"handler's own key yields {by_handlers_key!r}.  handleExportGIS "
            "branches on format=='kml', which this page never sends, so "
            "assocWriteKML is unreachable from the only page that offers it")


#: Fields declared with a ``json:`` tag whose Go name appears nowhere else
#: in the shipped source -- so nothing assigns them and nothing reads them.
#: Pinned exactly, and split by which direction the field faces, because
#: the two are not the same bug:
#:
#: * on a **request** struct the field is a control the user sets and the
#:   application discards;
#: * on a **response** struct it is a key that ships in every reply and is
#:   always the zero value -- inert here only because no page reads it.
_UNREAD_REQUEST_FIELDS = {
    # The two on NetworkQuery -- IncludeID and MaxLoop, the Networks
    # page's *Include ID in Output* checkbox and *Max Loop* number --
    # were here until the 2026-09-15 build, which consumed both: the
    # first is remembered under the form's mutex and read again at
    # export time, the second raises the walk's loop bound.
    #
    # These two replaced them, and they are the same shape of thing
    # seen from the other end of a migration.  Association Pairs is the
    # one form the dynasty picker's move to multi-select did not reach
    # (test_query_matrix.py::test_every_form_reads_the_dynasty_choice_
    # the_picker_now_sends), and of the six From/To fields it still
    # declares, its own handler reads four.  So even a page that spoke
    # its vocabulary correctly would be sending two numbers into
    # nothing.
    ("assocpairs_form_backend.go", "AssocPairsQueryParams",
     "FromDynastyEnd"): "fromDynastyEnd",
    ("assocpairs_form_backend.go", "AssocPairsQueryParams",
     "ToDynastyBegin"): "toDynastyBegin",
}
_UNPOPULATED_RESPONSE_FIELDS = {
    ("kinship_form_backend.go", "KinRecord", "KinRel0"): "kinRel0",
}


def _tagged_fields(sources: dict[str, str]) -> list[tuple[str, str, str, str]]:
    """``(file, struct, Go name, json name)`` for every tagged field."""
    found = []
    for name, text in sources.items():
        for struct in _STRUCT.finditer(text):
            for field in _JSON_FIELD.finditer(struct.group("body")):
                found.append((name, struct.group("name"),
                              field.group("go"), field.group("js")))
    return found


def test_a_field_the_json_declares_is_a_field_the_program_uses(
        go_text: dict[str, str], page_text: dict[str, str]):
    """Every ``json:``-tagged field, against every mention of its name.

    A field whose Go identifier occurs exactly once in the whole build --
    its own declaration -- is never assigned and never read.  Counting
    mentions rather than classifying reads and writes is deliberate: the
    classification needs a Go parser to be right, and being wrong in the
    direction of *missing* a use would hide the thing this test exists
    to find, whereas a mention that turns out to be inert costs one line
    in the sets above.

    This build has three.  The two that cost a user something in the
    previous build -- *Max Loop* and *Include ID in Output* on the
    Networks page, both read from the DOM, both posted, and neither
    consulted -- are consumed now, and the sets above are shorter for
    it.

    The two that replaced them face the same way and reach a user only
    if the Association Pairs page is fixed first: that form still sends
    the retired From/To dynasty vocabulary, and two of the six fields it
    sends are read by nothing even there.  The finding that matters on
    that page is the picker contract, not these; they are recorded
    because a fix applied to one and not the other would leave half a
    dynasty filter working.
    """
    inventory = _tagged_fields(go_text)
    assert inventory, "no json-tagged fields found; the field regex has gone stale"

    whole = "\n".join(go_text.values())
    unread = {
        (f, struct, go): js
        for f, struct, go, js in inventory
        if len(re.findall(r"\b" + re.escape(go) + r"\b", whole)) <= 1
    }

    expected = dict(_UNREAD_REQUEST_FIELDS) | dict(_UNPOPULATED_RESPONSE_FIELDS)
    unexpected = {k: v for k, v in unread.items() if k not in expected}
    assert not unexpected, (
        "a json field is declared and never used, and this file does not "
        f"know about it: {sorted(unexpected)}")

    missing = sorted(set(expected) - set(unread))
    assert not missing, (
        "a field pinned here as unused is now used, or has been removed; "
        f"either way the record below is stale: {missing}")

    # ``key: value`` *and* ``payload.key = value``.  Both spellings are
    # in use and only the first was matched, which under-reported: the
    # Association Pairs page builds its query by assigning onto a
    # payload object, so every field it sends was invisible here.  A
    # test that decides "no page sends this" has to know both ways a
    # page can send something.  Comments are stripped first, or a field
    # named in prose counts as sent.
    sent_by_a_page = sorted(
        (f, struct, go, js) for (f, struct, go), js in _UNREAD_REQUEST_FIELDS.items()
        if any(re.search(r"\b" + re.escape(js) + r"\s*[:=][^=]",
                         _without_comments(page))
               for page in page_text.values())
    )
    if sent_by_a_page:
        raise KnownShippedDefect(
            f"{len(sent_by_a_page)} value(s) a page computes and sends are "
            "declared by the handler that receives them and read by no "
            "line of Go: "
            + "; ".join(f"{js} ({struct}.{go} in {f})"
                        for f, struct, go, js in sent_by_a_page)
            + ".  All of them are on Association Pairs, which is the one "
              "form still speaking the From/To dynasty vocabulary the "
              "shared picker stopped sending -- so its dynasty filter is "
              "inert for a larger reason, and these two fields would "
              "still be inert after that was fixed.  The page computes "
              "each from the dynasty it thinks was chosen and assigns it "
              "onto the query payload; the handler's own year arithmetic "
              "reads the other four and never these")


# ===========================================================================
# 3. the capability with no way in
# ===========================================================================

#: Backend file stem -> the Templates directory that page lives in, for
#: the two whose names differ.  Every other backend is ``<form>_form_
#: backend.go`` against ``Templates/<form>/index.html``, and that is
#: derived rather than listed so a new form is covered the day it ships.
_FORM_DIRECTORY = {"assocpairs": "association_pairs",
                   "groupdata": "group_data",
                   "indexaddr": "index_addr"}

#: A handler branch that selects KML: the format switch every backend
#: uses, in both the ``if`` and ``case`` spellings that have shipped.
_SELECTS_KML = re.compile(r'(?:Format\s*==\s*"kml"|case\s+"kml")')


def _form_of(source: str) -> str:
    """The Templates directory that ``<x>_form_backend.go`` serves."""
    stem = source[:-len("_form_backend.go")]
    return _FORM_DIRECTORY.get(stem, stem)


#: How many ``*_form_backend.go`` files branch on a KML format on
#: this build.  The denominator of the survey below: without it, a
#: pattern that stopped matching would make the survey pass having
#: read nothing.
#:
#: Exact, not a floor.  A floor was written here first, reasoning
#: that a build adding a tenth KML writer should be surveyed rather
#: than rejected -- which is the argument operating principle 5
#: exists to refuse, and which the survey forty lines above this one
#: already refuses in the same words: a floor "would still pass with
#: an extractor that had quietly stopped seeing half the build".
#: Concretely, ``>= 9`` passes a build where the pattern stops
#: matching three backends and catches three others it did not mean
#: to.  A legitimate tenth writer is expected to fail this and be
#: read.
_BACKENDS_THAT_WRITE_KML = 9


def test_a_kml_the_handler_can_write_is_a_kml_the_page_can_ask_for(
        go_text: dict[str, str], page_text: dict[str, str]):
    """For each backend that writes KML, can its page select it?

    The test is deliberately weak in what it demands: the page has to
    mention ``kml`` *somewhere*, in any form -- a control id, a value, a
    comment.  A page that cannot manage even that cannot be sending the
    handler the string it branches on, and the KML the handler writes is
    dead code no user can reach.

    ``group_data`` is this build's case.  ``groupdata_form_backend.go``
    has six ``req.Format == "kml"`` branches -- its GIS exports for
    status, office and office-people among them -- each calling its own
    writer and naming a ``*_gis_*.kml`` file;
    ``Templates/group_data/index.html`` does not contain the letters
    ``kml`` at all.  Six branches, and no way in.
    """
    unreachable = []
    surveyed = 0
    for source, text in sorted(go_text.items()):
        if not source.endswith("_form_backend.go"):
            continue
        branches = len(_SELECTS_KML.findall(text))
        if not branches:
            continue
        surveyed += 1
        form = _form_of(source)
        page = page_text.get(form)
        assert page is not None, (
            f"{source} branches on \"kml\" and no Templates/{form}/index.html "
            "answers to it; the directory map above is stale")
        if "kml" not in page.lower():
            unreachable.append((form, source, branches))

    # A denominator, because a survey with none reports "every page
    # can ask for its KML" just as happily when it examined nothing.
    # If ``_SELECTS_KML`` stops matching -- the branch is rewritten,
    # the literal is spelled differently -- every backend would
    # ``continue`` and this test would pass having checked no page at
    # all.  Nine backends carry such a branch on this build.
    assert surveyed == _BACKENDS_THAT_WRITE_KML, (
        f"{surveyed} backend(s) were found to branch on \"kml\", "
        f"against {_BACKENDS_THAT_WRITE_KML} on the build this was "
        "written from.  Fewer means either the KML writers are going "
        "away or the pattern this survey matches on no longer matches "
        "them, and in the second case the survey below is examining "
        "nothing.  More means a writer was added and should be read "
        "before the number is.")

    if unreachable:
        raise KnownShippedDefect(
            "a page offers no way to ask for the KML its own handler writes: "
            + "; ".join(f"{form} ({source}: {n} branch(es) selecting KML)"
                        for form, source, n in unreachable)
            + ".  On the Group Data page those branches are its GIS exports "
              "-- status, office and office-people among them -- so the GIS "
              "output a user can obtain there is tab-separated only, and "
              "groupWriteKMLStatus, groupWriteKMLOffice and "
              "groupWriteKMLOfficePeople are unreachable")


def test_a_filter_the_places_handler_offers_has_a_control_that_can_set_it(
        go_text: dict[str, str], page_text: dict[str, str]):
    """``filterBac`` is a place filter that is hard-wired off.

    ``PlaceQueryParams`` declares ``FilterBAC bool `json:"filterBac"``,
    and the handler acts on it.  The page sends it, so the field is not
    dead in the sense the test above checks -- but it sends a literal:

        filterBac:          false,   // set to true and populate bacCodes when

    There is no control anywhere on the page that writes to it, and the
    comment beside it is an instruction to a future developer rather
    than a feature.  A user cannot reach the filter, which makes the
    difference from the Networks case worth stating: there the value is
    live and the handler ignores it; here the handler honours it and the
    value can never be anything but ``false``.
    """
    page = page_text["places"]
    literal = re.search(r"filterBac\s*:\s*(?P<value>true|false)\s*,", page)
    assert literal, (
        "the Places page no longer sends filterBac as a literal; if a "
        "control now sets it, delete this test")

    reads_it = re.search(r"\bFilterBAC\b", go_text["places_form_backend.go"])
    assert reads_it, "places_form_backend.go no longer declares FilterBAC"

    # Every place the page writes filterBac, and every element whose id
    # looks like a BAC control.  Capturing the value and testing it is
    # what this needs: a lookahead written after ``\s*`` can backtrack
    # onto the whitespace and "succeed" against the very literal it was
    # meant to exclude, which is how the first version of this test
    # passed on a build that has the defect.
    written = re.findall(r"filterBac\s*[:=]\s*(\S+?)\s*[,;)]", page)
    settable = [v for v in written if v not in ("true", "false")]
    # Anchored on the two names the build actually uses -- `bacCodes`,
    # the companion field the page's own comment says to populate, and
    # `filterBac` itself.  `[Bb]ac` as a substring matched "back" and
    # "background" too, so a single getElementById('btn-back') would have
    # made this pass on a build that still has the defect.
    settable += re.findall(r"getElementById\([^)]*\b(?:bacCodes|filterBac)\b",
                           page, re.IGNORECASE)
    if not settable:
        raise KnownShippedDefect(
            f"the Places page hard-codes filterBac: {literal.group('value')} "
            "and offers no control that can change it, so the BAC filter "
            "PlaceQueryParams declares and places_form_backend.go honours "
            "cannot be switched on by any user of the page")


#: Routed endpoints no page calls.  Pinned exactly, from a survey of
#: every ``HandleFunc`` against every shipped page -- the first version of
#: this test hard-coded ``place-search`` and therefore could not have
#: found the second one.  AGENTS.md § *coverage is the program's job*:
#: the decision of what to look at belongs in an inventory the build
#: fills in, not in a name a test author happened to think of.
#: How many ``/api/`` routes the shipped Go registers.  The denominator
#: of the survey below, pinned for the reason recorded in that test.
# 116 since the 2026-09-15 build, which deleted
# /api/networks/person-search and /api/networks/place-search --
# the two endpoints this survey had found and reported as
# reachable from no page at all, and the fix it asked for.
EXPECTED_API_ROUTES = 116

# Empty, and empty is the goal.  The 2026-09-15 build removed the two
# that were here -- the Networks person and place autocomplete helpers,
# each documented in its own comment as serving a picker that never
# called it -- by deleting the handlers rather than wiring them up.
# The survey stays: it is extracted from the build, so the next
# endpoint that ships with no way in fails the first assertion below
# rather than needing anyone to look for it.
_ROUTED_AND_UNCALLED: dict[str, str] = {}


def _without_comments(page: str) -> str:
    """The page with HTML and JavaScript comments removed.

    Deliberately blunt: it also blanks the contents of ``<!-- -->`` and
    ``/* */`` inside string literals, which can only ever *remove* text
    and so can only make this survey report more endpoints as uncalled,
    never fewer.  Erring that way is right here -- a false "uncalled"
    is one grep away from being disproved, while a false "called" hides
    a finding and looks like success.
    """
    page = re.sub(r"<!--.*?-->", " ", page, flags=re.DOTALL)
    page = re.sub(r"/\*.*?\*/", " ", page, flags=re.DOTALL)
    return re.sub(r"(?m)//.*$", " ", page)


def test_every_api_endpoint_the_build_routes_has_a_page_that_calls_it(
        go_text: dict[str, str], all_pages: dict[str, str]):
    """Every ``/api/`` route, against every page that could call one.

    The pages searched are *all* of them, pickers included -- not just
    ``Templates/*/index.html``.  That matters here more than usual: both
    endpoints this finds describe themselves as helpers *for a picker*,
    so a survey that could not see picker templates would have been
    asking the wrong question and getting the right answer by luck.

    Recorded here rather than left to the endpoint coverage gate, which
    asks whether *this suite* reached an endpoint.  That is a different
    question from whether the *application* can, and an endpoint no page
    calls is invisible to it: the gate's denominator is built from what
    the pages reach.
    """
    routed = {}
    for name, text in go_text.items():
        for path in re.findall(r'HandleFunc\(\s*"(/api/[^"]*)"', text):
            routed.setdefault(path, name)

    # Pinned exactly, not floored.  A floor is the wrong instrument for
    # the denominator of a coverage claim: "more than 50" would still
    # pass with an extractor that had quietly stopped seeing half the
    # build, and the conclusion drawn below -- *these* are the endpoints
    # nothing calls -- would then be a statement about the extractor.
    assert len(routed) == EXPECTED_API_ROUTES, (
        f"{len(routed)} /api/ routes were read out of the Go source, not "
        f"{EXPECTED_API_ROUTES}.  If the build gained or dropped one, "
        "update the number in the same commit as the reason; if it did "
        "not, the HandleFunc pattern has stopped matching some")

    # The pattern reads only `HandleFunc("literal"` -- checked to be
    # sufficient rather than assumed: every HandleFunc in this build
    # takes a string literal as its first argument, so there is no
    # computed route for it to miss.  That is asserted, because a build
    # that started registering routes in a loop would otherwise shrink
    # this survey silently.
    computed = [(name, arg.strip()[:60])
                for name, text in go_text.items()
                for arg in re.findall(r"HandleFunc\(\s*([^,]+),", text)
                if not arg.strip().startswith('"')]
    assert not computed, (
        f"a route is registered from something other than a string "
        f"literal: {computed}.  The survey below reads literals only, so "
        "it can no longer see every route")

    # A route with a {placeholder} is called with the placeholder filled
    # in, so its literal text never appears in a page.  Matching on the
    # fixed prefix alone is not enough: eleven of these share the stem
    # `/api/browser/person`, so one mention of that prefix anywhere would
    # mark all eleven as called.  The tail after the placeholder is
    # required too, which is what distinguishes them.
    # Comments are not calls.  The pages carry long explanatory
    # comments -- several name endpoints they describe rather than
    # invoke -- so an endpoint mentioned only in prose would otherwise
    # count as reached and this survey would under-report.
    code_of_pages = {name: _without_comments(page)
                     for name, page in all_pages.items()}

    uncalled = {}
    for path, source in sorted(routed.items()):
        head, _, rest = path.partition("{")
        head = head.rstrip("/")
        tail = rest.partition("}")[2].strip("/")
        called = any(head in page and (not tail or tail in page)
                     for page in code_of_pages.values())
        if not called:
            uncalled[path] = source

    unexpected = sorted(set(uncalled) - set(_ROUTED_AND_UNCALLED))
    assert not unexpected, (
        "an endpoint is routed that no page calls, and this file has not "
        f"judged it: { {p: uncalled[p] for p in unexpected} }")

    missing = sorted(set(_ROUTED_AND_UNCALLED) - set(uncalled))
    assert not missing, (
        f"an endpoint pinned here as uncalled is now called: {missing}")

    # Guarded on the *constant*, not on the discovered set.  The two
    # assertions above establish that ``uncalled`` equals
    # ``_ROUTED_AND_UNCALLED`` exactly -- one fails if an endpoint
    # joined the set, the other if one left it -- so testing
    # ``if uncalled:`` was testing the pin against itself and read as
    # though the set were being discovered here.
    #
    # But it cannot be unconditional either, which is the case the
    # first rewrite of this missed: when the build is fixed *and*
    # somebody correctly empties the pin, both assertions pass and an
    # unconditional raise reports "0 endpoint(s) are routed and no
    # page calls them" -- a finding for a defect that is gone, which
    # the accountability gate then demands an entry for.
    if _ROUTED_AND_UNCALLED:
        raise KnownShippedDefect(
            f"{len(uncalled)} endpoint(s) are routed and implemented "
            "and no page calls them: "
            + "; ".join(f"{path} ({uncalled[path]}) -- "
                        f"{_ROUTED_AND_UNCALLED[path]}"
                        for path in sorted(uncalled))
            + ".  Both are autocomplete helpers written for pickers "
              "that do not use them, so neither piece of work reaches "
              "a user")


# ===========================================================================
# 4. the answer that is quietly partial
# ===========================================================================

#: Columns the schema declares as text and whose *names* read like
#: codes, so a handler is tempted to scan them into an int.  One entry,
#: and the reason it is a table rather than a literal is that the
#: mistake is a species, not an incident.
_TEXT_COLUMNS_THAT_LOOK_NUMERIC = {
    "c_admin_type": "varchar(255) in ADDR_CODES, holding names like "
                    "'Zhou' and 'Xian' in all 30,100 rows",
}


def test_no_handler_scans_a_text_column_into_a_number(
        go_text: dict[str, str], sqlite_conn):
    """The mistake two handlers made, asserted where the fix goes.

    ``ADDR_CODES.c_admin_type`` is declared ``varchar(255)`` and holds
    text.  Two handlers read it into an ``int``, and the two failed
    differently, which is what makes this worth a source-level check
    rather than two endpoint tests:

    * the Associations Neo4j export let the scan error escape and
      answered HTTP 500 on every input -- loud, and findable by pressing
      the button;
    * ``handlePlaceSearch`` swallowed it with ``continue`` and answered
      200 with an empty list, so not one row of a 30,100-row table could
      be found through it and nothing said so.  Silent, and findable
      only by knowing what the answer should have been.

    The 2026-09-15 build fixed both -- the export scans into a string,
    and the search endpoint was deleted along with the picker helper
    nobody called.  This is what keeps them fixed, and it is a source
    check on purpose (AGENTS.md operating principle 8): it says which
    line to change, it cannot be flaky, and it covers the handlers that
    do not exist yet.  The endpoint test it replaces could only ever ask
    the one endpoint.

    The tell is the numeric default in the ``COALESCE`` -- ``COALESCE(
    c_admin_type, 0)`` -- which is how both offenders were written and
    is only ever written for a value about to be read as a number.

    Scoped honestly: a scan of the bare column, with no ``COALESCE`` at
    all, is not seen.  The obvious second tell -- a Go field named
    ``AdminType`` declared ``int`` -- was tried and withdrawn, because
    ``associations_form_backend.go`` has one that reads
    ``BIOG_ADDR_CODES.c_addr_type``, a genuine smallint primary key.
    Matching on a field's name says nothing about which column it
    receives, and a gate that cries wolf on correct code is a gate
    somebody switches off.
    """
    # The premise, from the database rather than from memory: if this
    # column ever becomes numeric, the whole test is stale and should
    # say so rather than going on policing a fixed mistake.
    declared = {
        row[1]: (row[2] or "").upper()
        for row in sqlite_conn.execute('PRAGMA table_info("ADDR_CODES")')}
    for column, why in _TEXT_COLUMNS_THAT_LOOK_NUMERIC.items():
        assert column in declared, (
            f"ADDR_CODES no longer has {column}; this test is judging a "
            "column the build has dropped")
        assert "CHAR" in declared[column] or "TEXT" in declared[column], (
            f"ADDR_CODES.{column} is now declared {declared[column]!r}, "
            f"not the text type this test is about ({why}).  If the data "
            "really became numeric, delete this test with the finding")

    offenders: dict[str, list[str]] = {}
    for name, text in sorted(go_text.items()):
        body = gosource.strip_comments(text)
        for column in _TEXT_COLUMNS_THAT_LOOK_NUMERIC:
            # `COALESCE(c_admin_type, 0)` -- a numeric default is only
            # ever written for a value about to be read as a number.
            for match in re.finditer(
                    r"COALESCE\(\s*(?:\w+\.)?" + re.escape(column)
                    + r"\s*,\s*([^)\s]+)\s*\)", body):
                if match.group(1) not in ("''", '""'):
                    offenders.setdefault(name, []).append(
                        f"COALESCE({column}, {match.group(1)})")
    assert not offenders, (
        "a handler reads a text column as a number: "
        + "; ".join(f"{name}: {found}" for name, found in offenders.items())
        + ".  " + "; ".join(f"{column} is {why}" for column, why
                            in _TEXT_COLUMNS_THAT_LOOK_NUMERIC.items())
        + ".  Scanning it into an int fails on every row; whether that "
          "surfaces as an HTTP 500 or as a successful search that finds "
          "nothing depends only on whether the error arm is `return` or "
          "`continue`")


#: Every ``SELECT`` in the build that caps its rows without ordering
#: them, pinned exactly and split by whether the cap is arbitrary.
#:
#: A ``LIMIT`` with no ``ORDER BY`` returns *some* rows, chosen by
#: whatever plan SQLite picks; the plan is not part of the schema and can
#: change when an index does.  That is a defect when the rows differ from
#: one another and the caller keeps what it is handed.  It is not one
#: when the query is a lookup whose predicate already selects a single
#: intended row and the ``LIMIT`` is belt-and-braces -- so those are
#: listed separately, with what makes them keyed.
#: Empty, and empty is the goal.  ``handleRecallIDs`` was here until the
#: 2026-09-15 build: ``LIMIT 2`` over ``ZZ_STORE_PERSON_ID``, whose rows
#: are different people, so which two the Association Pairs form
#: recalled depended on SQLite's plan.  It now reads ``ORDER BY
#: s.rowid``, which makes the two it keeps the two that were stored
#: first.  The survey stays, extracted from the build: the next capped
#: query that ships without an order fails the assertion below without
#: anyone going looking for it.
_ARBITRARY_ROW_CAPS: dict[tuple[str, str], str] = {}
_KEYED_ROW_CAPS = {
    ("browser_form_backend.go", "kinrelReductionUpdate"):
        "correlated subquery keyed on kr.c_kinrel_target = the row's "
        "kinrel text, with c_required = 1",
    ("kinship_form_backend.go", "kinrelReductionUpdate"):
        "the same subquery, in the form that owns ZZ_KIN_LIST_TMP",
}


def _sql_literals(text: str) -> list[tuple[int, str]]:
    """``(line, sql)`` for every backtick literal that looks like SQL."""
    out = []
    for match in _GO_LITERAL.finditer(text):
        body = match.group(1)
        if re.search(r"\bSELECT\b", body, re.IGNORECASE):
            out.append((text[:match.start()].count("\n") + 1, body))
    return out


def test_a_query_that_keeps_only_some_rows_says_which_ones(
        go_text: dict[str, str]):
    """``LIMIT`` without ``ORDER BY``, surveyed and classified.

    This build has three, and one of them is arbitrary.
    ``handleRecallIDs`` answers *GET /api/assocpairs/recall-ids* with

        SELECT s.c_personid, ... FROM ZZ_STORE_PERSON_ID s
        LEFT JOIN BIOG_MAIN bm ON ... LIMIT 2

    ``ZZ_STORE_PERSON_ID`` is the form's stored-person list, and the
    Association Pairs page recalls two people from it into the two ends
    of the pair.  Which two is left to the query plan.  A user who stored
    five people and pressed Recall gets a pair the application chose and
    did not name -- and pressing it again is not guaranteed to give the
    same one.
    """
    unordered = {}
    for name, text in go_text.items():
        for line, sql in _sql_literals(text):
            if not re.search(r"\bLIMIT\b", sql, re.IGNORECASE):
                continue
            if re.search(r"\bORDER\s+BY\b", sql, re.IGNORECASE):
                continue
            owner = _enclosing_name(text, line)
            unordered[(name, owner)] = " ".join(sql.split())[:120]

    expected = dict(_ARBITRARY_ROW_CAPS) | dict(_KEYED_ROW_CAPS)
    unexpected = {k: v for k, v in unordered.items() if k not in expected}
    assert not unexpected, (
        "a query caps its rows without ordering them and this file has not "
        f"judged it: {sorted(unexpected)}")

    missing = sorted(set(expected) - set(unordered))
    assert not missing, (
        f"a row cap recorded here is gone or now ordered: {missing}")

    # Built from what this run found, and reported with the SQL this run
    # read.  Deriving it from the pinned dict alone would make the raise a
    # restatement of a constant -- true before the suite started.
    arbitrary = {key: (_ARBITRARY_ROW_CAPS[key], unordered[key])
                 for key in sorted(set(unordered) & set(_ARBITRARY_ROW_CAPS))}
    # Guarded on the pin for the reason given at the uncalled-endpoint
    # raise above: the key set here is the pinned constant
    # intersected with itself, so ``if arbitrary:`` tested nothing --
    # but an unconditional raise would report a finding on a build
    # where the pin had rightly been emptied.  What is measured is
    # the SQL and the row counts inside the message.
    if _ARBITRARY_ROW_CAPS:
        raise KnownShippedDefect(
            "a query returns an arbitrary subset of rows that differ "
            "from one another: "
            + "; ".join(f"{f}:{owner} -- {why} -- {sql}"
                        for (f, owner), (why, sql)
                        in sorted(arbitrary.items()))
            + ".  SQLite is free to return any two rows and to return "
              "different ones after an index changes, so Recall on the "
              "Association Pairs page fills the pair with people the user "
              "did not choose and the application cannot name")


#: ``func Name(`` or ``func (recv) Name(``, and ``const name = ``/``var
#: name = `` -- enough to attribute a SQL literal to the thing that owns
#: it.  Requiring the declaration shape matters: a looser pattern matches
#: the word ``func`` inside a comment or a string and mis-attributes
#: every finding after it.
_OWNER = re.compile(
    r"^(?:func\s+(?:\([^)]*\)\s*)?(?P<func>\w+)\s*[(\[]"
    r"|\s*(?:const|var)\s+(?P<name>\w+)\s*=)",
    re.MULTILINE)


def _enclosing_name(text: str, line: int) -> str:
    """The nearest declaration at or above ``line``, or ``"?"``."""
    upto = "\n".join(text.split("\n")[:line])
    owner = "?"
    for match in _OWNER.finditer(upto):
        owner = match.group("func") or match.group("name")
    return owner


def _function_body(text: str, name: str) -> str:
    """The body of JavaScript ``function name(...)``, brace-matched.

    Written out rather than regexed because the question these tests ask
    -- *does this particular function do X* -- is exactly the question a
    regex cannot answer: any pattern that spans from a function's header
    to some token inside it will happily run past the closing brace and
    find that token in the next function down.

    Braces inside strings, template literals and comments are skipped,
    since any of them would otherwise close the body early and truncate
    what is searched.  Regex literals are **not** handled: telling ``/``
    as division from ``/`` as the start of a pattern needs the preceding
    token, which needs a tokeniser.  The pickers this reads contain no
    regex literal, and ``test_the_function_body_reader_stops_at_the_
    function`` asserts that -- rather than leaving the gap to be
    discovered by a wrong answer, which is the failure this helper
    exists to prevent.

    Returns ``""`` when the function is not found, so a caller's
    assertion reports the absence, and raises when the braces do not
    balance rather than silently returning the rest of the file.
    """
    header = re.search(r"function\s+" + re.escape(name) + r"\s*\([^)]*\)\s*\{", text)
    if not header:
        return ""
    i, depth = header.end(), 1
    while i < len(text) and depth:
        ch = text[i]
        if ch in "\"'`":
            quote, i = ch, i + 1
            while i < len(text) and text[i] != quote:
                i += 2 if text[i] == "\\" else 1
        elif text.startswith("//", i):
            i = text.find("\n", i)
            if i < 0:
                break
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = len(text) if end < 0 else end + 1
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if not depth:
                return text[header.end():i]
        i += 1
    raise AssertionError(
        f"the body of {name}() does not close: the brace depth ran out at "
        "the end of the file.  Returning the remainder would hand every "
        "caller the rest of the page and call it one function")


def _picker_sources(layout: AppLayout) -> dict[str, str]:
    """The picker templates ``_function_body`` is used on."""
    return {p.name: p.read_text(encoding="utf-8", errors="replace")
            for p in sorted((layout.templates_dir / "pickers").glob("*.html"))
            if not re.search(r"\.\d{8}\.html$", p.name)}


def _governing_condition(body: str, pos: int) -> str:
    """The condition of the innermost ``if`` still open at ``pos``.

    Walks forward keeping a stack of the braces that are open, so the
    answer is the ``if`` whose block actually contains ``pos`` rather
    than whichever one is nearest in the text.  A fixed-width lookback
    gets this wrong in both directions -- see the caller.

    Returns ``""`` when nothing governs the position, which a caller
    reads as *unguarded*, the strictest reading.
    """
    opener = re.compile(r"if\s*\((?P<cond>[^{;]*?)\)\s*\{")
    stack: list[str] = []
    i = 0
    while i < pos:
        match = opener.match(body, i)
        if match:
            stack.append(match.group("cond").strip())
            i = match.end()
            continue
        if body[i] == "{":
            stack.append("")
        elif body[i] == "}":
            if stack:
                stack.pop()
        i += 1
    for cond in reversed(stack):
        if cond:
            return cond
    return ""


def _without_js_comments(source: str) -> str:
    """JavaScript with ``//`` and ``/* */`` blanked.

    Used before asking whether a body *does* something: a call that has
    been commented out is not a call, and a substring search cannot
    tell the difference.
    """
    source = re.sub(r"/\*.*?\*/", " ", source, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", " ", source)


def _regex_literals(source: str) -> list[str]:
    """The ``= /.../flags`` literals in some JavaScript, if any.

    Strings first, then comments, so that a slash inside either is not
    read as the start of a pattern.  Only the assignment form is
    matched, which is what ``_function_body`` can be tripped by and is
    narrow enough not to mistake division for a pattern.
    """
    stripped = re.sub(r"""(["'`])(?:\\.|(?!\1).)*\1""", "", source,
                      flags=re.DOTALL)
    stripped = _without_js_comments(stripped)
    return re.findall(r"=\s*(/(?:[^/\n\\]|\\.)+/[gimsuy]*)", stripped)


def test_the_function_body_reader_stops_at_the_function(layout: AppLayout):
    """The reader above, against the file it is used on.

    A helper that silently over-reads would make every test using it pass
    or fail for reasons that have nothing to do with the function named,
    so it is checked here rather than trusted: the body of
    ``selectAllFiltered`` must contain what that function does and must
    not contain what the *next* function does.
    """
    text = (layout.templates_dir / "pickers" / "address_picker.html").read_text(
        encoding="utf-8", errors="replace")

    body = _function_body(text, "selectAllFiltered")
    assert body, "selectAllFiltered is no longer in the address picker"
    assert "selectAllState" in body, \
        "the reader lost part of selectAllFiltered's own body"
    assert "isSelectAllFiltered" not in body, (
        "the reader ran past selectAllFiltered into the code that follows "
        "it; every judgement built on it would be about the wrong function")
    assert _function_body(text, "noSuchFunctionExists") == "", \
        "the reader returns a body for a function that is not there"

    # The documented gap, asserted rather than assumed: a regex literal
    # containing a brace or a quote would send the reader past the close.
    # None of the pickers has one, and this is what says so.
    for name, page in _picker_sources(layout).items():
        assert not _regex_literals(page), (
            f"{name} now contains a regex literal; _function_body does not "
            "parse those, so any judgement it makes about that file may be "
            "reading the wrong function")

    # The Browser page cannot be held to that.  It has seven regex
    # literals, one of them ``/"/g``, and asking the reader for a body
    # that contains one really does fail -- ``_function_body(text,
    # "esc")`` raises "does not close".  A whole-file ban would be a
    # rule the build has already broken, so the invariant is narrowed to
    # what is actually relied on: the bodies this suite reads out of
    # that page must themselves be free of regex literals.  Today they
    # are, and today that is true by position rather than by design,
    # which is exactly why it is asserted.
    browser = (layout.templates_dir / "browser" / "index.html").read_text(
        encoding="utf-8", errors="replace")
    for name in ("exportProfile", "loadTabKinship"):
        body = _function_body(browser, name)
        assert body, (
            f"{name} is no longer in the Browser page; "
            "test_export_profile_loads_the_kinship_tab_it_lists reads it")
        found = _regex_literals(body)
        assert not found, (
            f"{name} now contains a regex literal ({found[0]!r}).  "
            "_function_body does not parse those: it treats a quote or a "
            "brace inside one as real, so the body it returned may stop "
            "early or run into the next function, and the test that reads "
            "this body would be judging the wrong code")


def test_select_all_filtered_selects_every_address_the_filter_matched(
        layout: AppLayout):
    """The button selects what is *rendered*, and 100 rows are rendered.

    ``Templates/pickers/address_picker.html`` keeps three lists: the full
    table, ``filteredAddresses`` (*"full match set (all rows matching the
    filter)"*), and ``renderedAddresses``, which is
    ``filteredAddresses.slice(0, MAX_RENDER)`` with ``MAX_RENDER = 100``.
    Only the rendered slice becomes ``<option>`` elements.

    ``selectAllFiltered()`` then walks ``sel.options``, and ``sendResult``
    walks ``sel.options`` again to build what it hands back -- so on a
    filter matching more than a hundred addresses the button returns the
    first hundred, and returns them with

        isSelectAllFiltered: true, filterPY: ..., filterChn: ...

    which every host page reads as *"the user chose the whole filter"*
    and displays as the filter text.  The truncation is invisible in the
    result: the query runs on a hundred addresses while the page says it
    ran on the filter.  The status bar does say *"Showing first 100 of
    N"*, but the button is not disabled in that state and its own comment
    says it *"selects every visible (filtered) item"*.
    """
    picker = (layout.templates_dir / "pickers" / "address_picker.html")
    text = picker.read_text(encoding="utf-8", errors="replace")

    cap = re.search(r"const\s+MAX_RENDER\s*=\s*(\d+)", text)
    assert cap, "the address picker no longer caps its rendering; this test is stale"
    render = _function_body(text, "renderList")
    assert render, (
        "_function_body found no renderList in the address picker, so "
        "neither the slice nor the prompt below is being read out of "
        "the function that draws the list.  The cap itself is declared "
        "outside it and is still matched against the whole file.")
    assert re.search(r"renderedAddresses\s*=\s*filteredAddresses\.slice\(0,\s*MAX_RENDER\)",
                     render), \
        "the rendered slice is no longer taken from the filtered set"

    # Each function's own body, brace-matched.  A regex of the shape
    # ``function X\{.*?sel\.options`` cannot do this job however it is
    # written: under DOTALL the ``.*?`` runs straight through the end of
    # X into whatever function comes next, so it reports "X walks the
    # options" whenever *anything below X* does.  Rewriting
    # ``selectAllFiltered`` to iterate ``filteredAddresses`` -- the exact
    # fix this defect asks for -- still matched, on the occurrence inside
    # ``sendResult`` forty lines further down.  The test would then have
    # gone on reporting the defect against a build that had fixed it.
    bodies = {name: _function_body(text, name)
              for name in ("selectAllFiltered", "sendResult")}
    # `name in text` would be satisfied by a mention -- including by a
    # rewrite to `const selectAllFiltered = () => {...}`, which this
    # reader does not match and would then judge as an empty body.
    absent = sorted(name for name, body in bodies.items() if not body)
    assert not absent, (
        f"_function_body found no body for {absent} in the address picker; "
        "either the functions are gone or they are declared in a form the "
        "reader does not match, and nothing below would be judging them")
    walkers = {name: "sel.options" in body for name, body in bodies.items()}

    # The fix, asserted where it was made.  Until the 2026-09-15 build
    # both functions walked sel.options, so Select All Filtered returned
    # the rendered slice -- at most MAX_RENDER addresses -- while
    # sendResult labelled it isSelectAllFiltered=true and the host page
    # rendered that as the whole filter text.  sendResult now takes the
    # isSelectAllFiltered path from filteredAddresses, which is the list
    # that holds the entire match set.
    #
    # selectAllFiltered() still walks sel.options, and that is correct:
    # it ticks what the user can see.  What matters is which list the
    # *result* is built from, so only sendResult is required to have
    # moved -- and requiring exactly that, rather than "neither walks
    # sel.options", is what keeps this from failing a correct build.
    assert re.search(r"isSelectAllFiltered\s*\)?\s*\{[^}]*filteredAddresses"
                     r"\s*\.\s*slice\(\s*\)", bodies["sendResult"],
                     re.DOTALL), (
        "sendResult no longer answers a Select All Filtered by copying "
        "filteredAddresses, the list holding the whole match set.  If it "
        "has gone back to walking sel.options, a filter matching more "
        f"than {cap.group(1)} addresses silently returns the first "
        f"{cap.group(1)} of them, labelled as the whole filter.  "
        "sendResult reads:\n" + bodies["sendResult"][:600])

    # The truncation prompt.  It is the mitigation the waiver on this
    # test was agreed on, and the waiver is now retired -- but the
    # prompt is still what tells a user the list they are looking at is
    # not the whole match set, so losing it is still worth a failure.
    # Read out of renderList rather than the file: a whole-file search
    # is satisfied by any surviving mention, a comment or a dead branch
    # included, and would stay green after the line itself had gone.
    warns = re.search(r"filteredAddresses\.length\s*>\s*MAX_RENDER",
                      render) and "Showing first " in render
    assert warns, (
        "the address picker no longer tells the user it truncated the "
        "list -- the count line that reads \"Showing first N of M -- "
        "refine your search\" is gone from "
        "Templates/pickers/address_picker.html")


def test_export_profile_loads_the_kinship_tab_it_lists(layout: AppLayout):
    """One button press reaches the endpoint that clears the Kinship form.

    This is the second half of the Kinship-discard finding, and the
    half no request can demonstrate: the damage is done by
    ``GET /api/browser/person/{id}/kinship``, and what makes it likely
    rather than merely possible is that the *Export Profile* button
    added in this build issues that request on behalf of a user who
    never asked to see kinship at all.

    Three links in that chain, each read out of the page that makes
    it and each asserted separately, so a build that breaks the chain
    anywhere says which part it broke:

    1. ``EXPORT_TABS`` lists a kinship tab with a loader;
    2. ``exportProfile`` calls that loader for a tab it has not cached;
    3. that loader fetches the kinship endpoint.

    Source read as data -- no claim is made here about what the
    request *does*, which is
    ``test_looking_a_person_up_does_not_discard_a_kinship_result``'s
    job, driven against the running binary.
    """
    page = layout.templates_dir / "browser" / "index.html"
    text = page.read_text(encoding="utf-8", errors="replace")

    listing = re.search(r"const\s+EXPORT_TABS\s*=\s*\[(.*?)\];",
                        text, re.DOTALL)
    assert listing, (
        "the Browser page no longer declares EXPORT_TABS, so nothing "
        "below is reading the list Export Profile walks")

    row = re.search(r"id:\s*'tab-kinship'[^}]*loader:\s*(\w+)",
                    listing.group(1))
    assert row, (
        "EXPORT_TABS has no kinship entry with a loader.  If the tab "
        "was dropped from the export, Export Profile no longer reaches "
        "the kinship handler and the second half of this finding is "
        f"fixed; the list is:\n{listing.group(1).strip()[:600]}")
    loader = row.group(1)

    body = _function_body(text, "exportProfile")
    assert body, (
        "_function_body found no exportProfile in the Browser page, so "
        "the call below would be searched for in the whole file")
    body = _without_js_comments(body)
    assert "tab.loader()" in body, (
        "exportProfile no longer calls each tab's loader, so it may no "
        "longer fetch a tab the user never opened -- which is the whole "
        f"of this finding's reach.  Its body is:\n{body[:600]}")

    # The link that matters, and the one three true facts do not add up
    # to.  The cheapest fix for this defect is one line inside the loop
    # --  ``if (tab.id === 'tab-kinship') continue;``  -- and it leaves
    # the kinship row, the loader call and the loader's own fetch all
    # exactly as they are.  Asserting only that the parts exist would
    # report the defect against a build that had fixed it, which is the
    # failure the comment above ``bodies`` in the picker test describes
    # in its own terms.
    #
    # So: the loop must walk the whole list, and the only tab it may
    # skip is the one with nothing to fetch.
    assert re.search(r"for\s*\(\s*const\s+tab\s+of\s+EXPORT_TABS\s*\)",
                     body), (
        "exportProfile no longer walks EXPORT_TABS directly -- it may be "
        "filtering the list, in which case kinship could have been "
        f"excluded from it.  Its body is:\n{body[:600]}")

    # Two ways a tab can be passed over: skipped before the call, or
    # the call guarded out from under it.  Rejecting only the first
    # leaves ``if (tab.id !== 'tab-kinship' && !_tabCache[k]) await
    # tab.loader()`` -- a real fix -- looking untouched to this test.
    skips = [_governing_condition(body, m.start())
             for m in re.finditer(r"\bcontinue\b", body)]
    loads = [_governing_condition(body, m.start())
             for m in re.finditer(r"tab\.loader\(\)", body)]

    stale = ([f"skips when {cond or '<always>'}" for cond in skips
              if "!tab.cacheKey" not in cond]
             + [f"loads only when {cond or '<always>'}" for cond in loads
                if "_tabCache" not in cond or "tab.id" in cond])
    assert not stale, (
        "exportProfile now passes over a tab for some reason other "
        "than it already being cached.  If what it passes over is "
        "kinship, pressing Export Profile no longer reaches the "
        "handler that clears the Kinship form, and the second half "
        "of this finding is fixed -- confirm and retire it.  "
        f"Found: {stale}")

    # A third way, which the two checks above cannot see: seeding
    # the cache for kinship just before the check leaves the
    # governing condition exactly as it is and still stops the
    # fetch.  In this build exportProfile only ever *reads* that
    # cache -- the loaders fill it -- so the claim is simply that
    # it still writes nothing to it.
    assert not re.search(r"_tabCache\[[^\]]*\]\s*=[^=]", body), (
        "exportProfile now writes to _tabCache.  If it is seeding "
        "the kinship entry so the loader is skipped, Export "
        "Profile no longer reaches the handler that clears the "
        "Kinship form, and the second half of this finding is "
        f"fixed -- confirm and retire it.  Its body is:\n{body[:900]}")

    fetches = _function_body(text, loader)
    assert fetches, (
        f"_function_body found no {loader}, the loader EXPORT_TABS "
        "names for the kinship tab")
    assert re.search(r"/api/browser/person/\$\{[^}]+\}/kinship", fetches), (
        f"{loader} no longer fetches /api/browser/person/<id>/kinship.  "
        "If it reads from somewhere that does not clear the Kinship "
        "form's tables, Export Profile is no longer a way into "
        f"CBDB-D-028.  Its body is:\n{fetches[:600]}")


def test_every_link_the_navigation_offers_resolves(app: CbdbApp, layout: AppLayout):
    """The front page's own links, followed.

    Cheap, and it finds one: *Users Guide* points at
    ``../../static/CBDB_UserGuide.pdf`` and ``Static/`` ships one file,
    ``cbdb_styles.css``.

    Only same-origin, non-anchor links are followed -- an external URL is
    not this build's to keep working, and following one would make the
    suite depend on the network.
    """
    page = (layout.templates_dir / "navigation" / "index.html").read_text(
        encoding="utf-8", errors="replace")
    hrefs = [h for h in re.findall(r'href="([^"]+)"', page)
             if not h.startswith(("#", "http://", "https://", "mailto:", "javascript:"))]
    assert hrefs, "the navigation page offers no links; the href pattern is stale"

    broken = []
    for href in sorted(set(hrefs)):
        # The page is served at the root, so its ../.. climbs out of a
        # depth it does not have; the browser clamps that to the root,
        # and this resolves it the same way.  An href that is already
        # absolute is left alone: prefixing it unconditionally produced
        # "//QBE", which only worked because gorilla/mux cleans the path
        # and redirects -- so two of this page's links were being checked
        # as something other than what they say.
        path = re.sub(r"^(?:\.\.?/)+", "/", href.split("?", 1)[0])
        if not path.startswith("/"):
            path = "/" + path
        response = app.get(path)
        if response.status_code >= 400:
            broken.append((href, path, response.status_code))

    if broken:
        raise KnownShippedDefect(
            "a link on the navigation page does not resolve: "
            + "; ".join(f"{href} -> {path} HTTP {code}"
                        for href, path, code in broken)
            + ".  Static/ ships cbdb_styles.css and nothing else, so the "
              "Users Guide the front page offers is not in the "
              "distribution")

"""Every export button in the application, pressed for real.

The suite's largest blind spot until this file existed.  Ten forms offer
42 file-producing endpoints between them -- Export Results, GIS, KML,
Neo4j, Pajek, Gephi, UCINet, Save Codes -- and six of them were being
driven: one ``export-results`` per read-only form.  Runs therefore
reported no export problems while thirty-six of the endpoints had never
been requested at all.  The first run that pressed them found four
defect families, two of them buttons that answer HTTP 500 every time on
every input.

So the endpoint list is not written here.  It lives in
``cbdb_desktop/exports.py`` as an inventory, and
``test_every_export_route_is_driven`` reads the routing table out of the
shipped Go source and fails if any registered export route is missing
from it.  That is the mechanism, and it does not depend on whoever runs
the suite remembering to look: a build that adds an export button fails
the gate until someone declares how to drive it.

**What each test proves.**  Deliberately not "the file has the right
contents".  There is no independent source for what a Pajek file of this
kinship network should say, and writing one in Python would be a
transcription of the writer under test (AGENTS.md's first prohibition).
What is checked is what survives the handler being rewritten:

* it answers at all, in the envelope it is supposed to, naming the files
  it is supposed to name;
* the payload is a **well-formed file of its declared kind** -- decodable
  UTF-8, a header, every row the width of the header, or parseable KML
  with placemarks.  Ragged rows are the export failure historians
  actually report: a column shifts and every value after it sits under
  the wrong heading;
* the people in the file exist in ``BIOG_MAIN``;
* pressing the button twice gives the same file;
* an export with nothing behind it does not hand back a file full of
  somebody else's rows.

Preconditions are re-established per test rather than once per module,
because several of these endpoints ignore their request body and re-read
a scratch table: for those, "the query ran most recently" *is* the
contract, and a shared fixture would quietly let one test export
another's result.
"""
from __future__ import annotations

import base64
import csv
import io
import json
import re
import xml.etree.ElementTree as ElementTree
from collections import Counter

import pytest

from cbdb_desktop.app import CbdbApp
from cbdb_desktop.defects import KnownShippedDefect
from cbdb_desktop.exports import (
    BOM_FORBIDDEN,
    BOM_IRRELEVANT,
    BOM_REQUIRED,
    EXPORTS,
    EXPORTS_BY_KEY,
    FILES,
    FORMAT_RULES,
    KML,
    NOT_EXPORTS,
    RAW,
    SINGLE_FILE,
    STATUS_FILES,
    TABLE,
    ExportSpec,
    FormatRule,
)
from cbdb_desktop.forms import (FORMS_BY_NAME, STORE_RESET,
                                WORKING_LIST_RESETS)
from cbdb_desktop.routes import all_routes

pytestmark = pytest.mark.app

#: Row counts stay small: no export applies a LIMIT either, and the GIS
#: writers hold the whole file in memory before sending it.
_MAX_ROWS_PER_CODE = 12
_MIN_ROWS_PER_CODE = 2

#: A filter value no code table contains, for driving "there is nothing
#: to export".  Negative rather than merely large: CBDB ids grow, and a
#: build five years from now would find 999999999 occupied.
_NO_SUCH_CODE = -987654

#: Columns that carry a person id in an exported file, whatever the
#: family called it.  Matched case- and punctuation-insensitively.
_PERSON_COLUMNS = ("personid", "cpersonid", "id", "kinid", "nodeid",
                   "nameid", "personid1", "personid2")

#: Content types each kind of file is allowed to arrive as.  Pinned
#: because they are what makes a browser save the file rather than
#: render it -- and because they are inconsistent, which is worth
#: recording where somebody will see it.
_RAW_CONTENT_TYPES = {
    TABLE: ("text/tab-separated-values", "text/plain"),
    KML: ("application/vnd.google-earth.kml+xml",),
}

#: KML endpoints with no tab sibling to compare against, so
#: test_a_kml_export_maps_the_rows_that_have_coordinates cannot judge
#: them.  Group data's KML set is six files covering five sections and
#: its tab set is the same six under different names; matching them up
#: is a mapping this suite would have to maintain, for a form whose
#: coordinates come from the same columns as every other form's.
_KML_WITHOUT_A_TAB_SIBLING = frozenset({"groupdata:kml"})


# ---------------------------------------------------------------------------
# reading what came back
# ---------------------------------------------------------------------------

#: The three bytes that tell Excel a .csv is UTF-8.  Without them, Excel
#: on Windows reads the file in the system ANSI code page and every
#: Chinese name in it is mojibake.  The 2026-09-08 build writes the
#: mark to every .tsv, which is what made that readable; before it, none
#: of them carried one.
UTF8_BOM = b"\xef\xbb\xbf"

#: Extensions whose consumer is a spreadsheet, and which therefore need
#: the mark.  Not the KML: XML declares its own encoding.
#:
#: Not the SNA formats either, but for one reason rather than the two
#: this comment used to give.  It said "Pajek, GDF and VNA readers do
#: not expect one", and that is **false for Pajek on this build**: all
#: four ``.net`` writers emit the mark deliberately
#: (``assocpairs_form_backend.go``, ``kinship_``, ``networks_``,
#: ``places_``, each with the comment "Pajek's UTF-8 reader expects a
#: BOM, unlike UCINet/Gephi").  So the mark is *required* for ``.net``
#: and *forbidden* for ``.gdf`` and ``.vna``, and a suffix list with one
#: bucket cannot say that, which is why the per-format expectation now
#: lives in ``FORMAT_RULES`` and is judged by
#: ``test_a_files_byte_order_mark_is_what_its_format_needs``.  This list
#: is what remains: the narrower question of which files a *spreadsheet*
#: opens, guarded by the non-ASCII check the per-format test does not
#: need.
#:
#: ``.tsv`` is the one that matters on the 2026-09-08 build and it has to
#: be listed: that build renamed every tab-delimited export from
#: ``.csv``/``.tab``/``.txt`` to ``.tsv``, and a suffix list written
#: before the rename would have gone on matching only the Neo4j
#: bundles -- checking the encoding of nothing a person opens, while
#: reporting nothing wrong.  The older three stay so that a build which
#: renames one back is still judged.
_SPREADSHEET_SUFFIXES = (".tsv", ".csv", ".tab", ".txt")


def _raw_data_url(label: str, url: str) -> bytes:
    """The bytes a data URL carries, with nothing decoded yet.

    Separate from :func:`_decode_data_url` because the *bytes* are the
    subject of one test on their own: whether a file whose name promises
    UTF-8 begins with the mark that makes a spreadsheet believe it.
    """
    assert isinstance(url, str), f"{label}: url is {type(url).__name__}"
    assert url.startswith("data:"), f"{label}: not a data URL: {url[:60]!r}"
    assert "base64," in url, f"{label}: data URL is not base64: {url[:60]!r}"
    blob = url.split("base64,", 1)[1]
    try:
        return base64.b64decode(blob, validate=True)
    except Exception as exc:                      # noqa: BLE001 - reported
        raise AssertionError(
            f"{label}: file payload is not valid base64: {exc}") from exc


def _decode_data_url(label: str, url: str) -> str:
    raw = _raw_data_url(label, url)
    try:
        return raw.removeprefix(UTF8_BOM).decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AssertionError(
            f"{label}: file payload is not UTF-8 ({exc}) -- these exports "
            "are named _UTF8 and a historian opening this gets mojibake"
        ) from exc


def _unwrap(spec: ExportSpec, response) -> list[tuple[str, str]]:
    """``[(file name, text)]`` from whichever envelope this form uses.

    The envelope is asserted, not sniffed: three shapes are in live use
    across these endpoints and a form quietly changing which one it
    answers with would break the page that reads it.
    """
    label = spec.key

    if spec.envelope == RAW:
        content_type = response.headers.get("Content-Type", "")
        allowed = _RAW_CONTENT_TYPES[spec.content]
        assert content_type.split(";")[0].strip() in allowed, (
            f"{label}: served as {content_type!r}; expected one of {allowed}")
        disposition = response.headers.get("Content-Disposition", "")
        assert "attachment" in disposition, (
            f"{label}: the file is not sent as a download "
            f"({disposition!r}) -- the browser will render it instead")
        name = re.search(r'filename="?([^";]+)', disposition)
        return [(name.group(1) if name else "<unnamed>", response.text)]

    assert "json" in response.headers.get("Content-Type", ""), \
        f"{label}: expected a JSON envelope, got " \
        f"{response.headers.get('Content-Type')!r}: {response.text[:200]}"
    payload = response.json()
    assert isinstance(payload, dict), \
        f"{label}: envelope is {type(payload).__name__}"

    if spec.envelope == STATUS_FILES:
        assert payload.get("status") == "ok", f"{label}: {payload}"
        assert isinstance(payload.get("files"), list), \
            f"{label}: keys are {sorted(payload)}"
        entries = payload["files"]
    elif spec.envelope == FILES:
        assert isinstance(payload.get("files"), list), \
            f"{label}: keys are {sorted(payload)}"
        entries = payload["files"]
    else:
        assert spec.envelope == SINGLE_FILE, spec.envelope
        assert set(payload) >= {"name", "url"}, \
            f"{label}: keys are {sorted(payload)}"
        entries = [payload]

    out = []
    for entry in entries:
        assert set(entry) >= {"name", "url"}, f"{label}: {sorted(entry)}"
        assert str(entry["name"]).strip(), f"{label}: a file has no name"
        out.append((entry["name"],
                    _decode_data_url(f"{label}/{entry['name']}", entry["url"])))
    return out


def _rows(text: str) -> list[list[str]]:
    """Split an exported table into rows, on whichever delimiter it uses.

    Tab first: every writer in this application is tab-separated except
    the Neo4j families, which are comma-separated CSV.  Sniffing on the
    header line alone is enough and avoids recording the delimiter per
    endpoint -- a value containing a comma cannot make a tab-separated
    header look comma-separated.
    """
    header_line = text.split("\n", 1)[0]
    delimiter = "\t" if "\t" in header_line else ","
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    while rows and rows[-1] in ([], [""]):
        rows.pop()
    return rows


def _check_table(label: str, text: str, *, allow_empty_body: bool
                 ) -> tuple[list[str], list[list[str]]]:
    """A file is a header plus rows of the same width.  Returns both."""
    assert text.strip(), f"{label}: the exported file is empty"
    rows = _rows(text)
    assert rows, f"{label}: the exported file has no rows at all"

    header, body = rows[0], rows[1:]
    assert len(header) > 1, f"{label}: exported header is {header}"
    repeated = [name for name, count in Counter(header).items() if count > 1]
    assert not repeated, (
        f"{label}: the header repeats {repeated} -- whichever column a "
        "reader loads second wins")

    if not allow_empty_body:
        assert body, f"{label}: header only, no data rows"

    widths = Counter(len(row) for row in body)
    assert set(widths) <= {len(header)}, (
        f"{label}: rows are not the width of the header ({len(header)} "
        f"columns): saw widths {dict(widths)}.  Every value after a short "
        "or long row sits under the wrong heading.")
    return header, body


# ---------------------------------------------------------------------------
# the social-network formats
# ---------------------------------------------------------------------------
#
# Pajek (.net), GUESS/Gephi (.gdf) and UCINet (.vna) are not delimited
# tables and checking them as if they were is how the first version of
# this file "found" nine defects that were nothing of the kind: a Pajek
# file's first line is *Vertices <n>*, which is a section header, not a
# column header.
#
# So each format gets the check its own readers apply.  These are worth
# more than a table check, not less: a Pajek file whose vertex count
# disagrees with its vertex list is rejected outright by Pajek, and that
# is a mistake a writer can make on any input.

def _check_pajek(label: str, text: str) -> None:
    """``*Vertices n``, then n vertices, then edges within 1..n."""
    lines = [line for line in text.splitlines() if line.strip()]
    assert lines, f"{label}: the Pajek file is empty"

    header = lines[0].split()
    assert header and header[0].lower() == "*vertices", \
        f"{label}: a Pajek file must open with '*Vertices n', not {lines[0]!r}"
    assert len(header) >= 2 and header[1].isdigit(), \
        f"{label}: no vertex count in {lines[0]!r}"
    declared = int(header[1])

    sections = [index for index, line in enumerate(lines)
                if line.lstrip().startswith("*") and index > 0]
    end = sections[0] if sections else len(lines)
    vertices = lines[1:end]
    assert len(vertices) == declared, (
        f"{label}: the header declares {declared} vertices and the file "
        f"lists {len(vertices)} -- Pajek refuses the file")

    ids = set()
    for line in vertices:
        number = line.split(maxsplit=1)[0]
        assert number.isdigit(), \
            f"{label}: a vertex line does not start with its number: {line!r}"
        ids.add(int(number))
    assert ids == set(range(1, declared + 1)), (
        f"{label}: vertex numbers are not 1..{declared}: "
        f"{sorted(ids)[:5]}...")

    for line in lines[end + 1:] if sections else []:
        if line.lstrip().startswith("*"):
            continue
        parts = line.split()
        if len(parts) < 2 or not parts[0].isdigit() or not parts[1].isdigit():
            continue
        for endpoint in (int(parts[0]), int(parts[1])):
            assert endpoint in ids, (
                f"{label}: an edge names vertex {endpoint}, which the file "
                f"does not define ({declared} vertices)")


def _check_gdf(label: str, text: str) -> None:
    """GUESS/Gephi: ``nodedef>`` and ``edgedef>`` sections, each rectangular."""
    lines = [line for line in text.splitlines() if line.strip()]
    assert lines, f"{label}: the GDF file is empty"
    assert lines[0].lower().startswith("nodedef>"), \
        f"{label}: a GDF file must open with 'nodedef>', not {lines[0]!r}"

    width = None
    section = None
    for line in lines:
        lowered = line.lower()
        if lowered.startswith(("nodedef>", "edgedef>")):
            section = lowered.split(">", 1)[0]
            width = len(line.split(">", 1)[1].split(","))
            continue
        assert width is not None, f"{label}: a row before any section header"
        assert len(line.split(",")) == width, (
            f"{label}: a {section} row has {len(line.split(','))} fields "
            f"where the section header declares {width}: {line[:80]!r}")
    assert section is not None, f"{label}: no section header at all"


def _vna_fields(line: str) -> list[str]:
    """Split a VNA row on whitespace, keeping quoted values whole.

    Names are quoted precisely because they contain spaces -- ``"Cui
    Weiya"`` is one field -- and a plain ``split()`` counts it as two,
    which reports every row of every VNA file as the wrong width.  Not
    ``shlex``: it treats a lone apostrophe in a transliteration as an
    unterminated quote and raises.
    """
    return re.findall(r'"[^"]*"|\S+', line)


def _check_vna(label: str, text: str) -> None:
    """UCINet VNA: ``*node data`` / ``*tie data``, each with its own header."""
    lines = [line for line in text.splitlines() if line.strip()]
    assert lines, f"{label}: the VNA file is empty"
    assert lines[0].lower().startswith("*node data"), \
        f"{label}: a VNA file must open with '*node data', not {lines[0]!r}"

    width = None
    section = None
    for line in lines:
        if line.lstrip().startswith("*"):
            section, width = line.strip(), None
            continue
        fields = _vna_fields(line)
        if width is None:            # the first row of a section is its header
            width = len(fields)
            continue
        assert len(fields) == width, (
            f"{label}: a row under {section!r} has {len(fields)} fields where "
            f"its header declares {width}: {line[:80]!r}")
    assert section is not None, f"{label}: no section header at all"


#: Which checker a file gets, by the extension the application chose for
#: it.  Read off the response rather than declared per endpoint: the
#: writer picks the name and the format together, so they cannot drift
#: apart, and one endpoint (assocpairs' export-sna) legitimately answers
#: with three different formats.
_CHECKERS = {".net": _check_pajek, ".gdf": _check_gdf, ".vna": _check_vna}


def _payload_rows(name: str, text: str) -> int:
    """How many *records* a file carries, whatever kind of file it is.

    Used only by the "nothing to export" test, where the question is
    "does this file describe anybody" and the answer has to be right for
    five different formats.  A Pajek file's ``*Vertices 0`` is not a data
    row; a GDF's ``nodedef>`` line is not either; and counting lines
    would call both of them populated.
    """
    extension = name[name.rfind("."):].lower() if "." in name else ""
    if extension == ".net":
        first = text.splitlines()[0].split() if text.strip() else []
        return int(first[1]) if len(first) >= 2 and first[1].isdigit() else 0
    if extension in (".gdf", ".vna"):
        rows = 0
        header_pending = False
        for line in text.splitlines():
            if not line.strip():
                continue
            if line.lstrip().startswith("*"):
                header_pending = True        # VNA: the next line is a header
                continue
            if line.lower().startswith(("nodedef>", "edgedef>")):
                continue                     # GDF: the header is the marker
            if header_pending:
                header_pending = False
                continue
            rows += 1
        return rows
    if extension == ".kml":
        return text.count("<Placemark")
    rows = _rows(text)
    return max(len(rows) - 1, 0)


def _check_file(label: str, name: str, text: str, *, allow_empty_body: bool
                ) -> None:
    """Validate one exported file as whatever kind of file it is."""
    extension = name[name.rfind("."):].lower() if "." in name else ""
    checker = _CHECKERS.get(extension)
    if checker is not None:
        checker(label, text)
        return
    if extension == ".kml":
        _check_kml(label, text)
        return
    _check_table(label, text, allow_empty_body=allow_empty_body)


def _check_kml(label: str, text: str) -> None:
    """A KML export must be XML a mapping tool can open."""
    assert text.strip(), f"{label}: the KML file is empty"
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as exc:
        raise AssertionError(
            f"{label}: the KML file is not well-formed XML ({exc}).  Google "
            f"Earth and QGIS refuse the whole file: {text[:120]!r}") from exc

    tag = root.tag.rsplit("}", 1)[-1]
    assert tag == "kml", f"{label}: root element is <{tag}>, not <kml>"

    # An empty placemark list is not asserted against here: every KML
    # writer in this build skips rows with no coordinates, and whether a
    # given office or person has any is a property of the data.  What
    # that *should* equal is checked in
    # test_a_kml_export_maps_the_rows_that_have_coordinates, against the
    # same endpoint's tab export -- one of the application's own outputs
    # rather than a guess about the data.
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] != "coordinates":
            continue
        parts = (element.text or "").strip().split(",")
        assert len(parts) >= 2, \
            f"{label}: coordinates {element.text!r} are not 'lon,lat'"
        for value in parts[:2]:
            float(value)      # a ValueError here fails the test, as it should


def _person_ids_in(header: list[str], body: list[list[str]]) -> set[int]:
    normalised = [re.sub(r"[^a-z0-9]", "", name.lower()) for name in header]
    column = next((normalised.index(name) for name in _PERSON_COLUMNS
                   if name in normalised), None)
    if column is None:
        return set()
    out = set()
    for row in body:
        value = row[column].strip()
        if value.lstrip("-").isdigit() and int(value) > 0:
            out.add(int(value))
    return out


# ---------------------------------------------------------------------------
# establishing what there is to export
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def cheap_codes(app: CbdbApp, sqlite_conn):
    """Filter values that are small *and* actually produce rows.

    The same two-step selection as test_form_queries.py's fixture of the
    same name, for the same reason: a code can have rows in its base
    table and still contribute nothing to a form's result, so each
    candidate is tried against the application and only the live ones are
    kept.  Choosing an input is not an oracle -- nothing about the
    expected answer is derived from it.

    Cached per form for the module: input selection is stateless, and
    re-running it per test would multiply this file's runtime.
    """
    cache: dict[str, list[int]] = {}

    def pick(form_name: str, limit: int = 3) -> list[int]:
        if form_name in cache:
            return cache[form_name]
        form = FORMS_BY_NAME[form_name]
        candidates = [row[0] for row in sqlite_conn.execute(
            f'SELECT "{form.code_column}" FROM "{form.code_table}" '
            f'GROUP BY "{form.code_column}" '
            "HAVING COUNT(*) BETWEEN ? AND ? "
            "ORDER BY COUNT(*) DESC, 1 LIMIT ?",
            (_MIN_ROWS_PER_CODE, _MAX_ROWS_PER_CODE, limit * 8)).fetchall()]
        live: list[int] = []
        for code in candidates:
            if len(live) == limit:
                break
            response = app.post(form.query_path, json=form.body([code]))
            assert response.status_code == 200, \
                f"{form_name}: {response.status_code} {response.text[:200]}"
            if form.rows(response.json()):
                live.append(code)
        assert live, f"{form_name}: no candidate code returns any rows"
        cache[form_name] = live
        return live

    return pick


@pytest.fixture(scope="module")
def egos(sqlite_conn) -> list[int]:
    """People with a handful of kin, so a traversal stays small.

    The graph forms apply no server-side cap on traversal depth, so the
    subject is chosen for smallness -- an input choice, predicting
    nothing about the result.
    """
    people = [row[0] for row in sqlite_conn.execute(
        "SELECT c_personid FROM KIN_DATA GROUP BY c_personid "
        "HAVING COUNT(*) BETWEEN 3 AND 6 ORDER BY c_personid LIMIT 4")]
    assert len(people) >= 3, people
    return people


@pytest.fixture(scope="module")
def missing_person(sqlite_conn) -> int:
    """A person id the database does not contain.

    For driving "there is nothing to export" on the forms whose subject
    is a person rather than a code.  Person 0 will not do: asking
    Association Pairs about person 0 leaves a row in its scratch people
    table, so the export then has something to find and the test reads
    as a defect that no user could reach -- the page cannot send 0.
    """
    highest = sqlite_conn.execute(
        "SELECT MAX(c_personid) FROM BIOG_MAIN").fetchone()[0]
    return int(highest) + 1000


@pytest.fixture(scope="module")
def associate(sqlite_conn) -> int:
    """Somebody with a few associations, for the pair form."""
    row = sqlite_conn.execute(
        "SELECT c_personid FROM ASSOC_DATA GROUP BY c_personid "
        "HAVING COUNT(*) BETWEEN 3 AND 8 ORDER BY c_personid LIMIT 1"
    ).fetchone()
    assert row, "no person in ASSOC_DATA has between 3 and 8 associations"
    return row[0]


@pytest.fixture
def working_lists(app: CbdbApp):
    """Empty both shared lists before and after any test that fills one.

    ``ZZ_SCRATCH_IMPORT_PEOPLE`` and ``ZZ_STORE_PERSON_ID`` are global to
    the application, so a test here that left people in them would change
    what test_stateful_forms.py sees.  This file runs before that one,
    which makes cleaning up this file's business rather than its
    neighbour's.
    """
    def reset():
        for path, body in WORKING_LIST_RESETS:
            app.post(path, json=body)
        app.post(STORE_RESET[0], json=STORE_RESET[1])

    reset()
    yield
    reset()


@pytest.fixture
def subject(app: CbdbApp, cheap_codes, egos, associate,
            missing_person, working_lists):
    """Run one form's query and return its response, for an export to use.

    Function-scoped on purpose.  Several endpoints in the inventory
    ignore their request body and re-read a scratch table, so what they
    export is whatever query ran last *in the application*; a
    module-scoped payload would let the kinship tests export the
    networks result and still look green.
    """
    def establish(form_name: str, *, empty: bool = False):
        if form_name in FORMS_BY_NAME:
            form = FORMS_BY_NAME[form_name]
            codes = [_NO_SUCH_CODE] if empty else cheap_codes(form_name)
            payload = app.json("POST", form.query_path, json=form.body(codes))
            if empty:
                assert not form.rows(payload), \
                    f"{form_name}: code {_NO_SUCH_CODE} returned rows"
            else:
                assert form.rows(payload), f"{form_name}: nothing to export"
            return payload

        if form_name == "kinship":
            if not empty:
                app.post("/api/kinship/set-person", json={"personId": egos[0]})
            payload = app.json("POST", "/api/kinship/query",
                               json={"maxUp": 1, "maxDown": 1, "maxCol": 1,
                                     "maxMarr": 1, "mourningCircle": False})
            if not empty:
                assert payload["kinRecords"], \
                    f"person {egos[0]} produced no kinship result to export"
            return payload

        if form_name == "networks":
            if not empty:
                app.post("/api/networks/set-person",
                         json={"personId": egos[0]})
            payload = app.json("POST", "/api/networks/query", json={
                "usePersonID": True, "useKin": True, "useNonKin": True,
                "useMale": True, "useFemale": True,
                "maxLoop": 1, "maxNodeDist": 1,
                "kinParam": True, "maxUp": 1, "maxDwn": 1, "maxCol": 1,
                "maxMar": 1})
            if not empty:
                assert payload["nodeRecords"], \
                    f"person {egos[0]} produced no network to export"
            return payload

        if form_name == "assocpairs":
            # Both slots, and neither of them 0: BIOG_MAIN contains a
            # person 0 -- the placeholder the data uses for "unknown" --
            # so querying for 0 legitimately returns one person and the
            # export then has something real to write.
            person = missing_person if empty else associate
            other = missing_person + 1 if empty else 0
            payload = app.json("POST", "/api/assocpairs/query", json={
                "personId1": person, "personId2": other, "useList": False,
                "includeKinship": False, "use2ndOrder": False,
                "yearFilterType": "none", "allDynasties": True})
            if not empty:
                assert payload["people"], \
                    f"person {associate} produced no pairs to export"
            return payload

        if form_name == "groupdata":
            people = [] if empty else egos[:3]
            if empty:
                # The query refuses an empty list, so there is nothing to
                # run: group data holds no scratch result of its own.
                return {"statusRecords": [], "officeRecords": [],
                        "entryRecords": [], "textRecords": [],
                        "placeRecords": [], "_personIds": []}
            payload = app.json("POST", "/api/groupdata/query", json={
                "personIds": people, "queryStatus": True,
                "queryOffice": True, "queryEntry": True, "queryText": True,
                "queryAddr": True})
            populated = [kind for kind in ("status", "office", "entry",
                                           "text", "place")
                         if payload[f"{kind}Records"]]
            assert populated, f"{people} produced no group data to export"
            # export-results re-runs the query from the ids rather than
            # formatting rows, so it needs them back.
            payload["_personIds"] = people
            return payload

        raise AssertionError(f"no precondition defined for form {form_name!r}")

    return establish


def _export(app: CbdbApp, spec: ExportSpec, payload):
    """POST one export and return the response, insisting only on 200."""
    response = app.post(spec.path, json=spec.body(payload))
    if response.status_code == 500:
        raise KnownShippedDefect(
            f"{spec.key} ({spec.path}) answers HTTP 500: "
            f"{response.text[:200].strip()}")
    assert response.status_code == 200, (
        f"{spec.key} ({spec.path}) -> HTTP {response.status_code}: "
        f"{response.text[:400]}")
    return response


# ---------------------------------------------------------------------------
# the coverage gate
# ---------------------------------------------------------------------------

def test_every_export_route_is_driven(layout):
    """No registered export endpoint may be absent from the inventory.

    The point of this file, expressed as a test.  The route surface is
    read out of the shipped Go source (``routes.py``), filtered by name
    to the endpoints that hand a user a file, and compared against
    ``exports.EXPORTS``.  Anything left over is an export nobody drives
    -- which is how a build shipped with 39 of them untested and a report
    saying no export problems had been found.

    ``NOT_EXPORTS`` is the escape hatch, and it is deliberately an
    explicit dictionary with a reason per entry rather than a pattern:
    excluding by pattern is how a genuine export gets excluded by
    accident.
    """
    registered = {route.path for route in all_routes(layout)
                  if re.search(r"/(export|save|import)-", route.path)}
    assert registered, "the route scan found no export endpoints at all"

    driven = {spec.path for spec in EXPORTS}
    excluded = set(NOT_EXPORTS)

    assert excluded <= registered, (
        f"NOT_EXPORTS names routes this build does not register: "
        f"{sorted(excluded - registered)}")

    untested = sorted(registered - driven - excluded)
    assert not untested, (
        f"{len(untested)} export endpoint(s) are registered by the build "
        f"and driven by nothing:\n  " + "\n  ".join(untested) +
        "\n\nAdd an ExportSpec to cbdb_desktop/exports.py (or, if it is "
        "not an export, an entry in NOT_EXPORTS with a reason).")

    stale = sorted(driven - registered)
    assert not stale, (
        f"the inventory drives routes this build no longer registers: "
        f"{stale}")


def test_the_inventory_covers_every_form_that_can_export(layout):
    """Every form page with an export button has exports declared.

    A second, independent reading of the same question: the test above
    starts from the routes and asks what is undriven; this one starts
    from the pages and asks which form has no export at all.  A build
    that dropped a form's whole export block would satisfy the route gate
    -- nothing registered, so nothing missing -- and fail here.
    """
    forms_with_exports = {spec.form for spec in EXPORTS}
    assert len(forms_with_exports) == 10, sorted(forms_with_exports)

    #: Template directory name -> inventory form key, where they differ.
    aliases = {"association_pairs": "assocpairs", "group_data": "groupdata"}

    exporting_pages = set()
    for name, index in layout.form_templates().items():
        html = index.read_text(encoding="utf-8", errors="replace")
        if re.search(r"""fetch\(\s*['"]/api/[^'"]*/?(export|save)-""", html):
            exporting_pages.add(name)
    assert exporting_pages, "no form template calls an export endpoint"

    missing = sorted(page for page in exporting_pages
                     if aliases.get(page, page) not in forms_with_exports)
    assert not missing, (
        f"these form pages call an export endpoint but have no "
        f"ExportSpec: {missing}")


# ---------------------------------------------------------------------------
# every export, driven
# ---------------------------------------------------------------------------

# The checks every endpoint in the inventory gets put through: four
# about what it answers, and four about the file it produces.
# None of them carries an expectation of failure: an endpoint that is
# broken fails, and tolerating that is a decision recorded outside the
# suite, in the waiver table, addressed by this test's own name and the
# parametrisation id below (``cbdb_desktop/waivers.py``).  A marker
# written here instead would be invisible policy -- and, keyed to a
# defect id that only exists while a report is being written, would
# stop meaning anything on the next stateless round.
_ALL_CHECKS = frozenset({"well_formed", "people", "repeatable", "empty",
                         "delimiter", "columns", "numbers", "encoding"})


def _params(check: str):
    """The inventory as pytest params, one per export endpoint.

    The id is the endpoint's own key (``networks:pajek``), which is what
    makes a waiver addressable: ``params = ["networks:pajek"]`` under
    this function's name waives exactly that one endpoint's check and
    leaves every other endpoint judged.
    """
    assert check in _ALL_CHECKS, check
    return [pytest.param(spec, id=spec.key) for spec in EXPORTS]


@pytest.mark.parametrize("spec", _params("well_formed"))
def test_an_export_produces_a_well_formed_file(app: CbdbApp, spec: ExportSpec,
                                               subject):
    """Press the button after a real query, and read what comes back.

    The broadest assertion in the suite and the one that has paid for
    itself most: for 39 of these endpoints it was the first check that
    they answer at all.  What is judged is the shape of the artefact a
    user is about to open -- the envelope, the file names, and whether
    each file is a rectangular table or parseable KML -- never its
    values, which have no independent source.
    """
    payload = subject(spec.form)
    files = _unwrap(spec, _export(app, spec, payload))

    names = [name for name, _ in files]
    assert len(set(names)) == len(names), \
        f"{spec.key}: two files with the same name: {names}"
    if spec.files:
        assert tuple(names) == spec.files, (
            f"{spec.key}: the export named {names}, not {list(spec.files)}.  "
            "A dropped or renamed file is a file somebody's next step "
            "cannot find.")

    for name, text in files:
        label = f"{spec.key}/{name}"
        if spec.content == KML:
            first_line = text.splitlines()[0].strip() if text.strip() else ""
            if first_line.startswith("<?xml") and not first_line.endswith("?>"):
                # The unclosed-declaration signature, recognised exactly
                # so that any *other* malformation of the same file still
                # fails as an ordinary failure rather than being read as
                # this one.
                raise KnownShippedDefect(
                    f"{label}: the file opens with {first_line!r} -- the XML "
                    "declaration is not closed with '?>', so every reader "
                    "rejects the whole file")
            _check_kml(label, text)
        else:
            # A file in a multi-file set may legitimately be header-only:
            # the Neo4j exports emit one file per node and edge type, and
            # a small result has no rows of some kinds.
            _check_file(label, name, text, allow_empty_body=len(files) > 1)


@pytest.mark.parametrize("spec", _params("people"))
def test_an_export_describes_the_people_the_grid_did(app: CbdbApp,
                                                     spec: ExportSpec,
                                                     subject, sqlite_conn):
    """The file names real people, and no people the query did not find.

    Membership in ``BIOG_MAIN`` is a base fact about the shipped data --
    a row-existence check, not a reconstruction of any handler's joins.
    Containment rather than equality with the grid, because several
    families legitimately narrow (KML drops rows with no coordinates) or
    widen (Neo4j emits a node file covering both ends of every edge) the
    set of people involved.  What must not happen is a *stranger*
    appearing in a file a historian is about to analyse.
    """
    if spec.content == KML:
        pytest.skip(f"{spec.key}: KML carries names, not ids")

    payload = subject(spec.form)
    files = _unwrap(spec, _export(app, spec, payload))

    exported: set[int] = set()
    for _name, text in files:
        rows = _rows(text)
        if len(rows) >= 2:
            exported |= _person_ids_in(rows[0], rows[1:])
    if not exported:
        pytest.skip(f"{spec.key}: no person-id column in any exported file")

    placeholders = ",".join("?" * len(exported))
    known = {row[0] for row in sqlite_conn.execute(
        f"SELECT c_personid FROM BIOG_MAIN "
        f"WHERE c_personid IN ({placeholders})", tuple(exported))}
    missing = sorted(exported - known)
    assert not missing, (
        f"{spec.key}: the exported file names {len(missing)} people who "
        f"are not in BIOG_MAIN: {missing[:10]}")


@pytest.mark.parametrize("spec", _params("repeatable"))
def test_an_export_is_repeatable(app: CbdbApp, spec: ExportSpec, subject):
    """Pressing the same button twice gives the same file.

    Cheap, and it catches what made the shared-scratch-table defect of
    the 2026-09-01 build so hard to notice: an export whose content
    depends on state nothing in the request describes.  For the
    scratch-reading endpoints this is the only assertion in the suite
    that they are idempotent.
    """
    payload = subject(spec.form)
    first = _export(app, spec, payload)
    second = _export(app, spec, payload)

    assert first.text == second.text, \
        f"{spec.key}: two identical exports produced different files"


@pytest.mark.parametrize("spec", _params("empty"))
def test_an_export_with_no_result_does_not_invent_one(
        app: CbdbApp, spec: ExportSpec, subject):
    """With an empty result behind it, an export must not hand back rows.

    The forms disagree about *how* they answer, and pinning a status code
    per endpoint would be recording an accident.  What is asserted is the
    property that matters to a user: either the request is refused, or
    the file that comes back has no data rows.  A header row is honest;
    somebody else's rows are not, and that is precisely the shape the
    shared-scratch-table defect took -- an export handing over a result
    the user's own query had not produced.

    Emptiness is established by running the form's own query over an
    input with no matches, which is also what truncates the scratch
    tables -- there is no "clear result" endpoint to call instead.
    """
    payload = subject(spec.form, empty=True)

    response = app.post(spec.path, json=spec.body(payload))
    if response.status_code == 500:
        raise KnownShippedDefect(
            f"{spec.key} answers HTTP 500 even with nothing to export: "
            f"{response.text[:200].strip()}")
    if response.status_code != 200:
        assert 400 <= response.status_code < 500, (
            f"{spec.key}: exporting nothing gave HTTP "
            f"{response.status_code}: {response.text[:300]}")
        return

    if spec.envelope == RAW:
        files = [("nothing" + (".kml" if spec.content == KML else ".tab"),
                  response.text)]
    else:
        payload = response.json()
        if payload.get("files", ()) is None:
            # Two forms answer {"status": "ok", "files": null} rather
            # than an empty list when there is nothing to write.  Pinned
            # as tolerated: a page reading .length off it would break,
            # but no page reaches this state, and "no files" is an
            # honest answer to "export nothing".
            return
        files = _unwrap(spec, response)

    for name, text in files:
        rows = _payload_rows(name, text)
        assert rows == 0, (
            f"{spec.key}/{name}: exporting nothing produced {rows} data "
            "rows -- they came from somewhere other than this request")


# ---------------------------------------------------------------------------
# defects this file found
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("spec", [
    pytest.param(spec, id=spec.key) for spec in EXPORTS
    if spec.content == KML and spec.key not in _KML_WITHOUT_A_TAB_SIBLING
])
def test_a_kml_export_maps_the_rows_that_have_coordinates(app: CbdbApp,
                                                          spec: ExportSpec,
                                                          subject):
    """A KML file must carry a placemark for the places in the result.

    Every KML writer in this build skips rows with no coordinates, and
    whether a given office or person has any is a property of the data
    -- so "no placemarks" is sometimes the right answer, and asserting a
    non-empty file would fail on an input that simply has no mapped
    places.  (It did: an office code whose postings have no office
    coordinates produced a valid, empty KML and looked like a defect.)

    What settles it is the same endpoint's **tab** export, taken from
    the same query: one of the application's own outputs, not a guess
    about the data.  Rows there carry the coordinates in named columns,
    so the two can be compared:

    * if the tab file has coordinate-bearing rows, the KML must have at
      least one placemark -- an empty KML then means the writer dropped
      every place;
    * the KML may have *fewer*, because two of the writers de-duplicate
      by person and one exports office locations rather than people's.

    Under-specified on purpose.  Equality would be a transcription of
    each writer's own de-duplication rule, and would have to be
    re-derived every time one changed.
    """
    tab = next(s for s in EXPORTS
               if s.form == spec.form and s.family in ("gis", "gis-people"))
    payload = subject(spec.form)

    tab_files = _unwrap(tab, _export(app, tab, payload))
    coordinate_rows = 0
    for _name, text in tab_files:
        rows = _rows(text)
        if len(rows) < 2:
            continue
        header = [re.sub(r"[^a-z]", "", name.lower()) for name in rows[0]]
        xs = [index for index, name in enumerate(header)
              if name in ("x", "xcoord", "entryx")]
        ys = [index for index, name in enumerate(header)
              if name in ("y", "ycoord", "entryy")]
        if not xs or not ys:
            continue
        coordinate_rows += sum(
            1 for row in rows[1:]
            if row[xs[0]].strip() and row[ys[0]].strip())

    if not coordinate_rows:
        pytest.skip(f"{spec.key}: this result has no mapped places, so an "
                    "empty KML is the right answer")

    kml_files = _unwrap(spec, _export(app, spec, payload))
    placemarks = sum(text.count("<Placemark") for _name, text in kml_files)
    assert placemarks > 0, (
        f"{spec.key}: the tab export of the same query has "
        f"{coordinate_rows} rows with coordinates and the KML has no "
        "placemarks at all -- the file opens and shows nothing")
    assert placemarks <= coordinate_rows, (
        f"{spec.key}: {placemarks} placemarks for {coordinate_rows} "
        "coordinate-bearing rows -- the KML invented places")


def _raw_files(spec: ExportSpec, response) -> list[tuple[str, bytes]]:
    """``[(file name, raw bytes)]`` -- the same unwrapping, undecoded.

    Deliberately a second, smaller reader rather than a change to
    ``_unwrap``: the encoding test is the only one that cares about
    bytes, and threading them through every other assertion would make
    all of them harder to read for one test's benefit.
    """
    if spec.envelope == RAW:
        disposition = response.headers.get("Content-Disposition", "")
        name = re.search(r'filename="?([^";]+)', disposition)
        return [(name.group(1) if name else "<unnamed>", response.content)]

    payload = response.json()
    entries = ([payload] if spec.envelope == SINGLE_FILE
               else payload.get("files") or [])
    return [(entry["name"], _raw_data_url(f"{spec.key}/{entry['name']}",
                                          entry["url"]))
            for entry in entries]


# Every table-shaped export, judged on its encoding.  An endpoint that
# answers HTTP 500 for every input produces no file whose encoding could
# be judged, so it fails here as well as in the four checks above --
# two failures for one cause, which is the honest reading and is why
# nothing is excluded up front.  A waiver, if one is agreed, names this
# function and the endpoint key.
@pytest.mark.parametrize("spec", [
    pytest.param(spec, id=spec.key) for spec in EXPORTS
    if spec.content == TABLE
])
def test_a_spreadsheet_export_can_be_opened_by_a_spreadsheet(
        app: CbdbApp, spec: ExportSpec, subject):
    """A file named _UTF8 must announce itself as UTF-8.

    The bytes being valid UTF-8 is not enough, and this is the gap
    between "the test passes" and "the user can read the file".  Excel
    on Windows decides a ``.csv``'s encoding by looking for a byte-order
    mark; finding none it uses the system ANSI code page, and every
    Chinese name, place and title in the file becomes mojibake.  The
    application reports success, the download completes, and what the
    user sees looks like corrupt data.

    So the assertion is about the first three bytes, for the file
    families a spreadsheet opens.  KML and the SNA formats are excluded
    deliberately, though not all for the same reason: XML declares its
    own encoding, and GDF and VNA readers do not expect a mark, so
    adding one there would break them.  **Pajek is the exception** -- all
    four ``.net`` writers in this build emit the mark on purpose ("Pajek's
    UTF-8 reader expects a BOM, unlike UCINet/Gephi") -- so ``.net`` is
    excluded here only because this test's question is "can a
    spreadsheet open it".  Whether the mark Pajek *needs* is actually
    there is asked by
    ``test_a_files_byte_order_mark_is_what_its_format_needs``, which
    judges every format against its own rule.

    Guarded by a non-ASCII check: a file that happens to contain only
    ASCII is readable either way, and failing on it would report a
    problem the user cannot have.
    """
    payload = subject(spec.form)
    files = _raw_files(spec, _export(app, spec, payload))

    # Driven first and excluded only here, so an endpoint that answers
    # HTTP 500 still fails this test rather than being skipped by a
    # classification.
    if spec.machine_import:
        pytest.skip(
            f"{spec.key}: an import set for another program, not a file a "
            "spreadsheet opens.  Neo4j's LOAD CSV reads a byte-order mark "
            "as part of the first column's name, so the build omits it "
            "here on purpose -- the same reason KML and the SNA formats "
            "are excluded above")

    without: list[str] = []
    judged: list[str] = []
    for name, raw in files:
        if not name.lower().endswith(_SPREADSHEET_SUFFIXES):
            continue
        try:
            text = raw.removeprefix(UTF8_BOM).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise AssertionError(
                f"{spec.key}/{name} is not UTF-8 at all ({exc})") from exc
        if text.isascii():
            continue          # readable in any code page
        judged.append(name)
        if not raw.startswith(UTF8_BOM):
            without.append(name)

    if without:
        raise KnownShippedDefect(
            f"{spec.key}: {len(without)} file(s) contain non-ASCII text and "
            f"start with no UTF-8 byte-order mark: {without}.  Excel will "
            "open them in the system code page and show mojibake.")

    # Two ways there was nothing to judge, and they are not the same
    # thing -- which is what the single skip this replaced got wrong.
    # Written when the build marked nothing, the test ended in an
    # unconditional raise; once the 2026-09-08 build started marking
    # every .tsv, every parametrisation fell through to one skip saying
    # "no spreadsheet file here carries non-ASCII text", said equally of
    # a correctly marked file full of Chinese names and of a Pajek .net
    # that was never a spreadsheet.  A reader could not tell "verified
    # marked" from "nothing to judge", and neither could a later round.
    spreadsheet = [name for name, _ in files
                   if name.lower().endswith(_SPREADSHEET_SUFFIXES)]
    if not spreadsheet:
        pytest.skip(
            f"{spec.key}: produces no spreadsheet-suffixed file at all "
            f"({[name for name, _ in files]}) -- a graph format, which this "
            "test's question does not fit: 'can a spreadsheet open it' is "
            "not asked of a .gdf or a .vna, and for .net the mark is "
            "*required* rather than forbidden.  Both are judged by "
            "test_a_files_byte_order_mark_is_what_its_format_needs")
    if not judged:
        pytest.skip(
            f"{spec.key}: {len(spreadsheet)} spreadsheet file(s) "
            f"({spreadsheet}), every one of them pure ASCII on this input, "
            "so no code page could misread them")


def _strip_go_comments(source: str) -> str:
    """Remove comments, leaving string literals alone.

    Conservative on purpose.  The comments that matter here are the doc
    blocks above each handler, which list the files it produces -- read
    literally they look exactly like a writer naming a ``.tsv``.  A
    blanket ``//[^\\n]*`` strip would also cut into a string containing
    ``//``, so a trailing comment is only removed when it carries no
    quote of its own.
    """
    source = re.sub(r"/\*.*?\*/", " ", source, flags=re.DOTALL)
    source = re.sub(r"(?m)^[ \t]*//.*$", "", source)          # doc blocks
    return re.sub(r"(?m)//[^\n\"'`]*$", "", source)           # safe trailers



#: The start of a top-level Go declaration, so a finding can be reported
#: by the function it sits in rather than by a line number that the next
#: build moves.  The trailing ``(`` matters: it requires the shape of a
#: real declaration, so a line inside one of this build's multi-line SQL
#: strings that happens to begin with the word "func" is not mistaken
#: for one.
#:
#: The obvious alternative -- blank the backtick strings first, then look
#: for boundaries -- was tried and rejected, because it is *less* safe.
#: ``networks_form_backend.go`` contains an odd number of backticks (517
#: once comments are stripped), so pairing them shifts and a naive blank
#: swallowed six real declarations, moving every finding after them into
#: a function that does not exist.  Requiring the signature shape cannot
#: eat code, which is the failure mode that matters here.
_GO_FUNC = re.compile(r"^func\s+(?:\([^)]*\)\s*)?(\w+)\s*[(\[]",
                      re.MULTILINE)


def _go_functions(text: str) -> list[tuple[str, str]]:
    """``[(name, body), ...]`` split at top-level ``func`` boundaries.

    Not a Go parser: the body of one function runs to the start of the
    next, which is all this needs.  ``func`` at column 0 is the only
    thing treated as a boundary, so a closure inside a handler stays
    part of it -- correct here, because a writer that delegates to its
    own local helper is still one writer.

    What stops a line inside one of this build's multi-line backtick SQL
    strings from splitting a handler in two is ``_GO_FUNC`` requiring
    the shape of a declaration, not a blanking pass -- see the note
    there for why blanking was tried and rejected.
    """
    starts = [(m.start(), m.group(1))
              for m in _GO_FUNC.finditer(text)]
    # Package scope counts.  Without this first entry the text before the
    # first ``func`` is never yielded, so a header declared as a
    # package-level ``const`` -- which is exactly where a KML preamble
    # could live -- would be scanned by nothing and reported as clean.
    # ``test_scratch_tables.py`` calls the same region "<file scope>".
    if not starts or starts[0][0] > 0:
        starts.insert(0, (0, "<file scope>"))
    starts.append((len(text), ""))
    return [(name, text[begin:starts[index + 1][0]])
            for index, (begin, name) in enumerate(starts[:-1])]


#: A quoted ``.tsv`` file name -- a writer naming its output, not prose
#: mentioning a format.
_NAMES_A_TSV = re.compile(r'"[^"\n]*\.tsv"')

#: Writing the UTF-8 byte-order mark, however this build spells it.
_WRITES_MARK = re.compile(r"utf8BOM|uFEFF|ufeff|xEF\b")


def _unmarked_spreadsheet_writers(source: str) -> tuple[list[str], int]:
    """``([function names], how many were judged)`` for one Go source.

    A function that names a ``.tsv`` file must write the mark itself.
    Separate from the test so that
    ``test_the_mark_check_notices_one_writer_losing_it`` can prove this
    predicate has teeth without touching the staged build.
    """
    text = _strip_go_comments(source)
    unmarked, checked = [], 0
    for name, body in _go_functions(text):
        if not _NAMES_A_TSV.search(body):
            continue
        checked += 1
        if not _WRITES_MARK.search(body):
            unmarked.append(name)
    return unmarked, checked


def test_the_mark_check_notices_one_writer_losing_it():
    """Mutation test for the check below, on a synthetic source.

    The point of § *Mutation-test the infrastructure*: the file-level
    version of this check passed a source where one of two writers had
    lost the mark, because the other one still had it.  This pins the
    granularity so that version cannot come back.
    """
    both_marked = '''
func (h *H) handleExportResults(w http.ResponseWriter, r *http.Request) {
\tbuf.Write(utf8BOM)
\tfiles = append(files, F{"Data_UTF8.tsv", toDataURL(buf)})
}

func (h *H) handleExportGIS(w http.ResponseWriter, r *http.Request) {
\tw.Write(utf8BOM)
\tw.Header().Set("Content-Disposition", "attachment; filename=gis.tsv")
}
'''
    assert _unmarked_spreadsheet_writers(both_marked) == ([], 2)

    # One writer loses the mark; the other still has it, in the same
    # file.  This is the case the previous version reported as clean.
    one_lost = both_marked.replace("\tw.Write(utf8BOM)\n", "")
    assert _unmarked_spreadsheet_writers(one_lost) == (["handleExportGIS"], 2)

    # A doc comment listing the files a handler produces is prose, not a
    # writer, and must not be counted at all.
    prose_only = '''
// handleSomething returns two files:
//   1. Data_UTF8.tsv -- a full dump
func (h *H) handleSomething(w http.ResponseWriter, r *http.Request) {
\treturn
}
'''
    assert _unmarked_spreadsheet_writers(prose_only) == ([], 0)


def test_every_form_that_writes_a_spreadsheet_writes_the_mark(layout):
    """Read in the source: no form is left writing ``.tsv`` unmarked.

    Found by reading the shipped Go, which makes it a property of the
    build rather than of one endpoint's data.  Worth having alongside
    the HTTP test for the reason § *Prefer a check that needs nothing
    running* gives: it says where the fix goes, and it cannot be
    satisfied by an input that happens to be ASCII.

    A partial job -- one form's exports marked and the rest not -- turns
    this red, which is the right outcome: the file names all promise the
    same thing.

    Judged **per writer**, which is the granularity that matters and the
    one this test got wrong twice.  Pinning exact ``file:line`` sites was
    too tight: four lines inserted above one of them broke it while
    nothing about the build had changed.  Comparing sets of *files* was
    too loose, and loose in the direction that hides a regression --
    every one of these backends contains several writers plus the Neo4j
    ones that omit the mark on purpose, so dropping the mark from one
    spreadsheet writer leaves the file still "a file that writes a mark"
    and the test still green.

    So the unit is the enclosing Go function: one that names a ``.tsv``
    file has to write the mark itself.  That survives code moving around
    it, and it fails on exactly the change the user would notice.
    """
    unmarked: list[str] = []
    checked = 0
    for source in layout.go_sources():
        found, total = _unmarked_spreadsheet_writers(
            source.read_text(encoding="utf-8", errors="replace"))
        checked += total
        unmarked += [f"{source.name}:{name}" for name in found]

    # Exact, not a floor: § *Pin exactly, not with a floor*.  ">= 15"
    # would let six of the twenty-one writers disappear from the
    # detector before this noticed, and a detector that has stopped
    # seeing a writer is indistinguishable from a build that no longer
    # has one.  A legitimate new export fails here and gets read.
    assert checked == 21, (
        f"{checked} functions name a .tsv file, not 21.  If the build "
        "gained or dropped an export, update this number in the same "
        "commit as the reason; if it did not, the detector has stopped "
        "seeing writers it used to see")
    assert not unmarked, (
        "these writers produce a tab-delimited spreadsheet without a "
        "UTF-8 byte-order mark, so Excel will open it in the system code "
        f"page and show mojibake: {unmarked}")


#: A page asking the browser to save one file per element of a list, all
#: from one click.  **Three** spellings are in use across these
#: templates and all three mean the same thing.
#:
#: The comment here used to say two, and "a third would have to be added
#: here" -- which is exactly what had happened and what stopped anyone
#: looking.  A `for (const file of j.files)` loop in office, status and
#: texts went unmatched, so a P0 finding was filed as 17 handlers across
#: 7 pages when the build has 22 across 10, with three whole pages
#: missing from it.  Hence ``_ITERATES_A_FILE_LIST`` below: the next
#: spelling fails a test instead of shrinking a number nobody can check.
_DOWNLOAD_PER_FILE = re.compile(
    r"""forEach\s*\(\s*\(?\s*\w+\s*\)?\s*=>\s*triggerDownload"""
    r"""|for\s*\(\s*(?:const|let|var)\s+\w+\s+of\s+[\w.]*\bfiles\b"""
    r"""|for\s*\(\s*let\s+\w+\s*=\s*0\s*;[^)]*\.files\.length""",
    re.IGNORECASE)

#: Any loop over a response's file list, however it is written.  The
#: guard on the pattern above: every way a page can walk a file list has
#: to be *recognised* by it, so a fourth spelling is a failure here
#: rather than a silent omission from the finding.
_ITERATES_A_FILE_LIST = re.compile(
    r"""for\s*\([^)]*\bfiles\b"""
    r"""|\bfiles(?:\s*\|\|\s*\[\])?\s*\)?\s*\.\s*(?:forEach|map)\s*\(""",
    re.IGNORECASE)

#: And the message such a handler then prints, which reports the number
#: of files the *server* returned rather than the number the browser
#: accepted.  This is the half that misleads.  Three phrasings again:
#: "N file(s) downloaded", "N files ready", and a template literal.
_REPORTS_A_FILE_COUNT = re.compile(
    r"""(?:\bfiles\s*\|\|\s*\[\]\)\.length|\.files\.length"""
    r"""|\$\{\s*files\.length\s*\})"""
    r"""[^;\n]*?(?:file\(s\)|files?\s+(?:downloaded|ready|saved))""",
    re.IGNORECASE)


def test_no_page_asks_the_browser_for_more_than_one_download(layout):
    """A multi-file export cannot be delivered as several downloads.

    Read out of the shipped templates rather than driven in a browser.
    Every browser permits one automatic download per user gesture and
    blocks the rest; a handler that clicks a synthetic ``<a download>``
    once per file therefore saves the first and loses the others, and
    once the block has been triggered it applies to later exports from
    the same page too -- which is why pressing Export a second time
    saves nothing.

    Checked in the source rather than in a browser for two reasons.  The
    suite has no browser, and more importantly the *server* side of this
    is faultless: ``test_an_export_is_repeatable`` shows the endpoint
    returning both files, identically, every time.  Nothing reachable
    over HTTP can see this defect, which is exactly why it survived
    every previous round of testing while a user hit it on the second
    click.

    Reported as a map of page to occurrence count -- not pinned as one.
    This docstring used to say "pinned", and the test has never asserted
    a map: it raises whenever any page does this at all, which is the
    right shape for a finding but not what the word promised.  What is
    pinned is the classification: every loop over a file list has to be
    one the pattern above recognises, so a page fixed shows up as a
    smaller map and a spelling nobody has seen fails outright.
    """
    per_file: dict[str, int] = {}
    claims: dict[str, int] = {}
    walks: dict[str, int] = {}
    for page, path in sorted(layout.form_templates().items()):
        html = path.read_text(encoding="utf-8", errors="replace")
        found = len(_DOWNLOAD_PER_FILE.findall(html))
        if found:
            per_file[page] = found
        told = len(_REPORTS_A_FILE_COUNT.findall(html))
        if told:
            claims[page] = told
        seen = len(_ITERATES_A_FILE_LIST.findall(html))
        if seen:
            walks[page] = seen

    # The guard.  Every loop over a file list must be one the pattern
    # above recognises, or this finding silently under-reports -- which
    # is how office, status and texts stayed out of it.
    assert walks == per_file, (
        "a page walks a response's file list in a spelling "
        "_DOWNLOAD_PER_FILE does not recognise, so the count below would "
        f"be too low.  Loops found: {walks}; classified: {per_file}.  Add "
        "the spelling to _DOWNLOAD_PER_FILE in the same commit")

    if not per_file:
        assert not claims, (
            "no page downloads per file any more, but these still report a "
            f"server-side file count as though they had: {claims}")
        return

    raise KnownShippedDefect(
        f"{sum(per_file.values())} export handlers across {len(per_file)} "
        f"pages ask the browser to save one file per element of a list, "
        f"from a single click: {per_file}.  "
        f"{sum(claims.values())} of them then report the count the server "
        f"returned as though every file had been saved: {claims}.")


#: The writers this round found emitting an unclosed XML declaration,
#: keyed by ``file:function`` so the next build moving code around does
#: not break the pin.  Exact, so a third one fails instead of being
#: folded into the finding these two make.
_KNOWN_UNCLOSED_KML = {
    "entry_form_backend.go:entryWriteKML",
    "places_form_backend.go:writePlaceKML",
}


def test_every_kml_writer_closes_its_xml_declaration(layout):
    """The same defect, found in the source rather than over HTTP.

    Reading the shipped Go as data (the discipline ``routes.py`` uses):
    a writer that emits an unclosed XML declaration cannot produce a
    valid file for *any* input, so it does not need a query to find and
    a reader does not need to run the application to believe it.

    Keyed by ``file:function``, not ``file:line``.  This test pinned
    exact line numbers until the 2026-09-08 build moved code above both
    of them -- entry by four lines, places by one -- and broke it while
    nothing about the defect had changed.  That was the second such
    repair in this suite; the enclosing function is what a fix actually
    moves.

    And it *raises* rather than asserting the defect is present, which
    is the shape the report needs: on the day these two writers are
    fixed this test passes, and the entry that names it is reported
    APPARENTLY FIXED.  Asserting ``broken == {...}`` would have failed
    with a plain ``AssertionError`` instead, and the report would have
    called a fixed defect INCONCLUSIVE.
    """
    broken = {}
    for source in layout.go_sources():
        text = _strip_go_comments(
            source.read_text(encoding="utf-8", errors="replace"))
        for name, body in _go_functions(text):
            for line in body.splitlines():
                if "<?xml version" not in line:
                    continue
                # The declaration as it will be written, with Go's
                # escaping of either quoting style removed.
                written = line.replace('\\"', '"')
                if '<?xml version="1.0" encoding="UTF-8"?>' not in written:
                    broken[f"{source.name}:{name}"] = line.strip()

    # Narrowed to the exact signature, then asserted.  Raising on
    # anything at all would be a floor: a *third* writer losing its
    # `?>` would raise the same KnownShippedDefect, the report would go
    # on saying "Both KML exports", and a waiver keyed on
    # raises = "KnownShippedDefect" would tolerate the new one silently.
    # § *Pin exactly, not with a floor*.
    if set(broken) == _KNOWN_UNCLOSED_KML:
        raise KnownShippedDefect(
            f"{len(broken)} KML writer(s) emit an XML declaration that is "
            "never closed with '?>', so no reader accepts the file they "
            f"produce: {sorted(broken)}")

    assert not broken, (
        "these KML writers emit an unclosed XML declaration, and the set is "
        f"not the one this round recorded: {sorted(broken)}, expected "
        f"{sorted(_KNOWN_UNCLOSED_KML)}.  A new one is a new finding; a "
        "missing one is a fix, and either way this needs reading rather "
        "than tolerating")


# ---------------------------------------------------------------------------
# the file as a file: delimiter, shape, types, quoting, encoding
# ---------------------------------------------------------------------------
#
# Everything above judges an export by what it contains relative to the
# query.  These judge the *artefact*: whether the bytes are the file the
# name promises.  A historian never sees the response envelope -- they
# see a file their spreadsheet either opens correctly or does not, and
# every property below is one that decides which.
#
# The rules live in ``cbdb_desktop/exports.py`` (``FORMAT_RULES``), read
# from the suffix, so a build that invents an extension fails the gate
# below rather than being judged by a default nobody chose.

#: Columns whose values a spreadsheet has to be able to total, sort or
#: map -- and what each one is, so a reader can judge the claim rather
#: than take it.  Coordinates, counts, identifiers and years: the
#: families the user of an export actually computes with.
#:
#: An explicit inventory and **not** every column the schema declares
#: numeric, which is what this started as and was wrong twice over.
#: SQLite's affinity rules do not forbid text in a NUMERIC column, so
#: "the database calls it numeric, therefore a non-number here is a
#: defect" over-claims -- it would have reported a legitimate textual
#: value as a bug.  And the sweep quietly mis-classified ``BOOLEAN(2)``,
#: which has NUMERIC affinity through SQLite's catch-all rule and
#: matches none of the obvious substrings.
#:
#: Every entry is still checked against the shipped schema by
#: ``test_every_numeric_column_is_one_the_database_declares_numeric``:
#: this table says which columns matter, the database says what they
#: are, and the two have to agree.
NUMERIC_COLUMNS: dict[str, str] = {
    "x_coord": "longitude; a map cannot plot prose",
    "y_coord": "latitude",
    "xy_count": "how many returned rows share this coordinate",
    "c_personid": "the CBDB person id every file is joined on",
    "c_kin_id": "the related person's id",
    "c_assoc_id": "the associate's id",
    "c_node_id": "the network node's person id",
    "c_addr_id": "the address code",
    "c_index_addr_id": "the person's index address code",
    "c_entry_addr_id": "the entry's own address code",
    "c_office_id": "the office code",
    "c_status_code": "the status code",
    "c_textid": "the text id",
    "c_entry_code": "the entry code",
    "c_assoc_code": "the association code",
    "c_kin_code": "the kinship code",
    "c_index_year": "the year a person is indexed under; sorted on",
    "c_dy": "the dynasty code",
    "c_year": "the year of the event this row records",
    "c_firstyear": "the first year of a posting or an address",
    "c_lastyear": "the last year",
    "c_sequence": "the order of a person's postings",
    "c_age": "age in years",
}

#: SQLite's own affinity rules, in the order it applies them (see
#: "Determination Of Column Affinity" in the SQLite docs).  Written out
#: because the substring shortcut this replaces got ``BOOLEAN(2)``
#: wrong: it has NUMERIC affinity via the final catch-all, and matches
#: none of INT/REAL/FLOA/DOUB/NUMERIC/DECIMAL.
def _affinity(declared: str) -> str:
    kind = (declared or "").upper()
    if not kind:
        # A view or expression column: SQLite gives it *no* affinity, not
        # BLOB.  Reported as its own answer so that the check below can
        # ignore it -- a column with no declared type says nothing about
        # whether it holds a number, in either direction, and reading it
        # as BLOB made c_personid look like a text column because one
        # view exposes it without a type.
        return "NONE"
    if "INT" in kind:
        return "INTEGER"
    if "CHAR" in kind or "CLOB" in kind or "TEXT" in kind:
        return "TEXT"
    if "BLOB" in kind:
        return "BLOB"
    if "REAL" in kind or "FLOA" in kind or "DOUB" in kind:
        return "REAL"
    return "NUMERIC"


#: The affinities that store a number.  ``NONE`` is here because a
#: column with no declared type is not evidence of anything: excluding
#: it would fail every column that any view exposes untyped.
_NUMERIC_AFFINITIES = frozenset({"INTEGER", "REAL", "NUMERIC", "NONE"})

#: Exported header names that are a database column under a different
#: spelling.  Four forms rename their columns on the way out -- office,
#: status, texts and places write ``PersonID``/``XCoord``/``XYCount``
#: where entry and associations write ``c_personid``/``x_coord``/
#: ``xy_count`` -- and without this the type check judged 8 of the
#: inventory's 54 endpoints and skipped the rest.
#:
#: One entry is **not** a rename, and the build says so itself:
#: ``XYCount`` is a coordinate frequency computed in Go over the result
#: set (``associations_form_backend.go:428`` -- "XYCount for the grid is
#: still computed in Go ... ZZ_SN_ASSOC has no xy_count column"), while
#: the database's ``xy_count`` is a person-level column, "distinct from
#: the grid's edge-level XYCount" (``:766``).  It is mapped anyway
#: because the *claim being checked* holds either way -- both are counts
#: and both must be numbers -- but calling it a rename would be false.
#:
#: Two nearby headings are deliberately **not** mapped, and adding
#: either would have produced a false defect immediately: ``Female`` is
#: written "M"/"F" where ``c_female`` is 0/1, and ``XY`` is a
#: comma-joined "x,y" string.
#:
#: Read off the Go writers by hand, which is the kind of thing AGENTS.md
#: warns about, so be exact about what protects it:
#: ``test_every_alias_resolves_into_the_numeric_inventory`` proves each
#: target is a column the inventory covers, so an alias cannot point at
#: nothing and quietly stop judging a heading.  Nothing can prove an
#: alias names the *same quantity* -- that is a claim about what a
#: writer meant -- but a wrong entry fails in the safe direction: it
#: reports a defect that is not there, loudly, on the next run.
_HEADER_ALIASES = {
    "personid": "c_personid",
    "indexyear": "c_index_year",
    "dy": "c_dy",
    "sequence": "c_sequence",
    "firstyear": "c_firstyear",
    "lastyear": "c_lastyear",
    "officeid": "c_office_id",
    "statuscode": "c_status_code",
    "textid": "c_textid",
    "addrid": "c_addr_id",
    "associd": "c_assoc_id",
    "kinid": "c_kin_id",
    "nodeid": "c_node_id",
    "x": "x_coord",
    "y": "y_coord",
    "xcoord": "x_coord",
    "ycoord": "y_coord",
    "xycount": "xy_count",
}


def _database_column(header: str) -> str:
    """The database column an exported heading names, however spelled."""
    plain = header.strip().lstrip("\ufeff").lower()
    return _HEADER_ALIASES.get(plain, plain)


def _rule_for(name: str):
    """The ``FormatRule`` a file name promises, by its suffix."""
    return FORMAT_RULES.get("." + name.rsplit(".", 1)[-1].lower())



@pytest.fixture(scope="session")
def schema_affinities(sqlite_conn) -> dict[str, set[str]]:
    """``{column name: {affinity, ...}}`` over every shipped table.

    Read with ``PRAGMA table_info``, which is how SQLite itself resolves
    a name -- a base fact about the artefact, not a reconstruction of
    anything a handler computes.
    """
    out: dict[str, set[str]] = {}
    for (table,) in sqlite_conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view')"):
        for row in sqlite_conn.execute(f'PRAGMA table_info("{table}")'):
            out.setdefault(row[1].lower(), set()).add(_affinity(row[2]))
    assert len(out) > 500, (
        f"only {len(out)} column names found in the shipped schema; "
        "PRAGMA table_info has stopped answering and this oracle is "
        "about to judge nothing")
    return out


def _is_number(value: str) -> bool:
    """True when a cell holds something a spreadsheet reads as a number."""
    try:
        float(value)
    except ValueError:
        return False
    return True


def test_every_produced_suffix_has_a_declared_rule():
    """No export may produce a file whose format nothing describes.

    The gate over ``FORMAT_RULES``.  Without it a build that renamed an
    export to ``.dat`` would produce a file every check below skipped,
    and the run would stay green while nothing judged it -- the shape
    this suite calls claimed coverage.
    """
    produced = {"." + name.rsplit(".", 1)[-1].lower()
                for spec in EXPORTS for name in spec.files}
    assert produced, "no export in the inventory names a file"

    undeclared = sorted(produced - set(FORMAT_RULES))
    assert not undeclared, (
        f"these file extensions are produced but no FormatRule describes "
        f"them, so nothing judges their delimiter or their encoding: "
        f"{undeclared}")


@pytest.mark.parametrize("spec", _params("delimiter"))
def test_a_delimited_file_uses_the_delimiter_its_suffix_promises(
        app: CbdbApp, spec: ExportSpec, subject):
    """A ``.csv`` is separated by commas and a ``.tsv`` by tabs.

    The name is the only thing telling whatever opens the file how to
    split a line, so a tab-delimited file called ``.csv`` is a file that
    loads as one wide column -- which is what this build shipped until
    the 2026-09-08 rename, under three different extensions.

    What is asserted is that the file is a **consistent rectangle with
    more than one column under the delimiter its own name promises**.
    That is the property a spreadsheet needs and the one this build
    failed until the .tsv rename: tab-delimited bytes in a file called
    .csv load as a single wide column.

    What is deliberately *not* asserted is that the other candidate
    delimiter does worse.  An earlier version compared the two field
    counts and claimed "a genuinely comma-separated file cannot satisfy
    that under tabs, and vice versa", which is false in both
    directions: a valid CSV header carrying tabs inside a quoted field
    splits into more fields under tab than under comma, and a
    tab-delimited header whose first field contains commas can split
    into more under comma.  The count is still reported in the failure
    message, as information; it is not evidence.
    """
    payload = subject(spec.form)
    files = _unwrap(spec, _export(app, spec, payload))

    judged = 0
    unjudgeable: list[str] = []
    for name, text in files:
        rule = _rule_for(name)
        assert rule is not None, f"{spec.key}/{name}: no rule for this suffix"
        if rule.delimiter is None:
            continue
        if not text.strip():
            continue

        header = text.splitlines()[0]
        promised = len(next(csv.reader([header], delimiter=rule.delimiter)))
        other = "," if rule.delimiter == "\t" else "\t"
        alternative = len(next(csv.reader([header], delimiter=other)))

        if promised == 1 and alternative == 1:
            # One column under either candidate: a genuinely single-field
            # file, whose delimiter no reading of it can reveal.  Nothing
            # in this build produces one, and reporting it as a defect
            # would be a false positive by construction -- so it is
            # named and left, not failed.
            unjudgeable.append(name)
            continue

        assert promised > 1, (
            f"{spec.key}/{name}: the name promises "
            f"{rule.delimiter!r}-separated ({rule.why}), but the header "
            f"splits into one field on it.  It splits into {alternative} on "
            f"{other!r}, so the file is delimited by the wrong character "
            "for its own name and a spreadsheet will load it as one column")

        # A rectangle, not just a wide first line.  A file delimited by
        # the wrong character usually gives ragged rows once the data
        # starts, even where the header happens to split.
        rows = [row for row in csv.reader(io.StringIO(text),
                                          delimiter=rule.delimiter) if row]
        widths = {len(row) for row in rows}
        assert widths == {promised}, (
            f"{spec.key}/{name}: the header splits into {promised} fields "
            f"on the promised {rule.delimiter!r} but the rows give widths "
            f"{sorted(widths)} -- the file is not a table under the "
            f"delimiter its name claims.  On {other!r} the header would "
            f"give {alternative}")
        judged += 1

    if not judged:
        if unjudgeable:
            pytest.skip(
                f"{spec.key}: {unjudgeable} hold a single field under either "
                "candidate delimiter, so which one separates them cannot be "
                "read off the file")
        pytest.skip(f"{spec.key}: produces no delimited table "
                    f"({[name for name, _ in files]})")


@pytest.mark.parametrize("spec", _params("columns"))
def test_every_row_of_a_delimited_file_is_as_wide_as_its_header(
        app: CbdbApp, spec: ExportSpec, subject):
    """Ragged rows are the export failure historians actually report.

    A row one field short shifts every value after it under the wrong
    heading, and nothing in the file says so: the numbers simply mean
    something else from that column on.  Parsed with ``csv.reader`` on
    the declared delimiter, so a correctly quoted value containing a
    delimiter counts as the single field it is.
    """
    payload = subject(spec.form)
    files = _unwrap(spec, _export(app, spec, payload))

    judged = 0
    for name, text in files:
        rule = _rule_for(name)
        # Asserted, not skipped past.  14 of the inventory's specs name
        # no files at all -- their names come from Content-Disposition
        # at run time -- so the suffix gate cannot see them, and a
        # `continue` here would let one of those judge nothing in
        # silence.  That is the shape the gate exists to prevent.
        assert rule is not None, (
            f"{spec.key}/{name}: no FormatRule for this suffix, so nothing "
            "knows how to split it.  Add one to FORMAT_RULES")
        if rule.delimiter is None or not text.strip():
            continue
        rows = [row for row in csv.reader(io.StringIO(text),
                                          delimiter=rule.delimiter) if row]
        assert rows, f"{spec.key}/{name}: no rows at all"
        width = len(rows[0])
        ragged = {index: len(row) for index, row in enumerate(rows[1:], 2)
                  if len(row) != width}
        assert not ragged, (
            f"{spec.key}/{name}: the header has {width} columns but "
            f"{len(ragged)} row(s) do not -- every value after the short "
            f"column sits under the wrong heading.  First few: "
            f"{dict(list(ragged.items())[:5])}")
        judged += 1

    if not judged:
        pytest.skip(f"{spec.key}: produces no delimited table "
                    f"({[name for name, _ in files]})")


@pytest.mark.parametrize("spec", _params("numbers"))
def test_a_column_that_has_to_hold_a_number_holds_one(
        app: CbdbApp, spec: ExportSpec, subject):
    """A coordinate or a count must arrive as a number, not as prose.

    The oracle is the shipped schema's own declared types (see
    ``numeric_columns``), matched to the exported header by name.  So
    the claim is narrow and checkable: *this column is called
    ``x_coord``, the database declares every ``x_coord`` REAL, therefore
    every value under that heading has to parse as a number*.  Nothing
    here predicts what the number should be.

    Be exact about what this can and cannot catch on *this* build,
    because most of the writers make the failure structurally
    impossible.  The forms that rename their columns build every numeric
    field with ``strconv.Itoa`` or ``nullIntStr`` from a typed Go
    ``int``/``*float64``: if the column held text the ``Scan`` would
    error and the endpoint would answer HTTP 500 -- which is what
    ``ADDR_CODES.c_admin_type`` does to the Associations Neo4j export,
    and it is caught by the well-formed check, not here.  For those, what
    this pins is that each writer's header list and its value list stay
    aligned.

    Where it can catch a wrong type outright is the two exports whose
    writer is a generic ``SELECT *`` with an ``interface{}`` scan --
    ``entry:results`` and ``associations:results`` -- because those pass
    whatever the column holds straight through.

    An empty cell is missing data, not a wrong type, and is allowed; a
    column of nothing but empty cells is not counted as judged.
    """
    payload = subject(spec.form)
    files = _unwrap(spec, _export(app, spec, payload))

    judged: list[str] = []
    wrong: dict[str, list[str]] = {}
    for name, text in files:
        rule = _rule_for(name)
        assert rule is not None, (
            f"{spec.key}/{name}: no FormatRule for this suffix, so nothing "
            "knows how to split it.  Add one to FORMAT_RULES")
        if rule.delimiter is None or not text.strip():
            continue
        rows = [row for row in csv.reader(io.StringIO(text),
                                          delimiter=rule.delimiter) if row]
        if len(rows) < 2:
            continue
        header = list(rows[0])
        for index, heading in enumerate(header):
            column = _database_column(heading)
            if column not in NUMERIC_COLUMNS:
                continue
            values = [row[index].strip() for row in rows[1:]
                      if index < len(row) and row[index].strip()]
            if values:
                # Counted only when there was something to look at.  A
                # column of empty cells -- every value NULL through
                # nullIntStr -- used to count as judged, which made the
                # coverage number larger than the checking.
                judged.append(f"{name}:{column}")
            offenders = [value for value in values if not _is_number(value)]
            if offenders:
                wrong[f"{name}:{column}"] = sorted(set(offenders))[:5]

    assert not wrong, (
        f"{spec.key}: these columns are declared numeric by the shipped "
        f"schema but the export writes text under them: {wrong}.  A "
        "spreadsheet will sort and total them as strings")

    if not judged:
        delimited = [name for name, _ in files
                     if (_rule_for(name) or FormatRule(None, "", "")).delimiter]
        if not delimited:
            pytest.skip(f"{spec.key}: produces no delimited table "
                        f"({[name for name, _ in files]})")
        pytest.skip(
            f"{spec.key}: {len(delimited)} delimited file(s) {delimited}, "
            "and not one header names a column the shipped schema declares "
            "numeric -- this form renames its columns on the way out, and "
            "an alias table is deliberately not guessed at")


@pytest.mark.parametrize("spec", _params("encoding"))
def test_a_files_byte_order_mark_is_what_its_format_needs(
        app: CbdbApp, spec: ExportSpec, subject):
    """The mark is required, forbidden or irrelevant -- per format.

    Three answers, not one, and the build gets all three right on
    purpose, which is why a single list could never have judged them:

    * ``.tsv``/``.csv`` a person opens: **required**, or Excel on
      Windows reads the file in the system code page and every Chinese
      name becomes mojibake;
    * ``.gdf``/``.vna``: **forbidden**, because Gephi and UCINet read
      the mark as part of the first field's name;
    * ``.net``: **required** -- Pajek's UTF-8 reader expects it, and all
      four writers say so where they emit it.  Nothing checked this
      until now: the suffix list this replaces excluded every SNA
      format on the strength of a comment that was wrong about Pajek.
    * ``.kml``: **irrelevant**; XML declares its own encoding.

    The Neo4j bundles are ``.csv`` and deliberately unmarked, which the
    inventory records as ``machine_import`` -- ``LOAD CSV`` would read
    the mark as part of the first column's name.
    """
    payload = subject(spec.form)
    files = _raw_files(spec, _export(app, spec, payload))

    judged = 0
    problems: list[str] = []
    for name, raw in files:
        rule = _rule_for(name)
        assert rule is not None, f"{spec.key}/{name}: no rule for this suffix"
        expected = rule.bom
        if expected == BOM_REQUIRED and spec.machine_import:
            expected = BOM_FORBIDDEN
        if expected == BOM_IRRELEVANT or not raw:
            continue

        judged += 1
        present = raw.startswith(UTF8_BOM)
        if expected == BOM_REQUIRED and not present:
            problems.append(
                f"{name} needs the mark and has none ({rule.why})")
        elif expected == BOM_FORBIDDEN and present:
            problems.append(
                f"{name} must not carry the mark and does ({rule.why})")

    if problems:
        raise KnownShippedDefect(f"{spec.key}: " + "; ".join(problems))

    if not judged:
        pytest.skip(f"{spec.key}: no file here has an encoding this can "
                    f"judge ({[name for name, _ in files]})")


#: Values the shipped data really holds that collide with a delimiter,
#: and the export that carries each one into a file.  Every field is
#: measured, not invented: a quoting test written with a made-up string
#: tests its own escaping, and one run over whatever a discovered code
#: happened to hold proves nothing at all while passing.
#:
#: The first case is the decisive one and the reason this table is not
#: simply the two ``:results`` exports.  Those are ``.tsv``, so a comma
#: in them is an ordinary character that needs no escaping -- an earlier
#: version of this test used exactly that and proved only that the
#: value survived.  ``entry:neo4j`` writes ``EntryCodes_UTF8.csv``,
#: which really is comma-separated (``newCSV()`` in
#: ``cbdb_shared_utils.go``, no ``Comma`` override), so the two commas
#: in entry code 330's description are a genuine collision: unescaped,
#: the row grows two fields and every column after them shifts.
#:
#: The second is the only double quote the reachable data contains --
#: ``ASSOC_CODES`` 445, ``Shared "same way" with`` -- and a quote has to
#: be escaped in *both* dialects, so the ``.tsv`` export carries it.
#:
#: What the shipped data cannot exercise, said plainly so the next round
#: does not have to rediscover it: **no reachable value contains a tab**,
#: and none *begins* with a quote.  So tab-escaping inside a ``.tsv``
#: has no input to drive it, and the mid-field quote above is escaped by
#: this writer but would also parse back intact if it were not -- which
#: is exactly why the raw-bytes assertion below exists rather than a
#: parse alone.  ``KINSHIP_CODES.c_kinrel`` holds the one tab in the
#: code tables and reaches only a comma-separated file, where a tab
#: needs no escaping.
#:
#: ``raw_marker`` is what the bytes must show if the writer escaped it:
#: the field wrapped in quotes, with any internal quote doubled.  That
#: is the half a parse cannot prove, because Python will happily read an
#: under-escaped field back as one field in non-strict mode.
_DELIMITER_COLLISIONS = (
    ("entry", 330, "entry:neo4j", "EntryCodes_UTF8.csv",
     "Recommendation, by special grace, to the Classical Studies Section",
     '"Recommendation, by special grace, to the Classical Studies Section"',
     "two commas in a comma-separated file"),
    ("associations", 445, "associations:results", "Associations_UTF8.tsv",
     'Shared "same way" with',
     '"Shared ""same way"" with"',
     "a double quote, which both dialects must escape"),
)


@pytest.mark.parametrize(
    "form,code,export_key,filename,value,raw_marker,why",
    _DELIMITER_COLLISIONS,
    ids=[f"{form}-{code}" for form, code, *_ in _DELIMITER_COLLISIONS])
def test_a_value_that_collides_with_the_delimiter_is_escaped(
        app: CbdbApp, form: str, code: int, export_key: str, filename: str,
        value: str, raw_marker: str, why: str, working_lists):
    """A comma in a description must not become a new column.

    The one property of a delimited file a writer gets wrong silently:
    a value containing the delimiter, or a quote, has to be escaped, and
    if it is not the row grows a field and every column after it shifts.
    The row count is unchanged, the file still opens, and nothing
    announces it -- the numbers simply belong to different headings from
    that point on.

    Two assertions, and the second is the one with teeth:

    * the value comes back as **exactly one field**, which is the
      user-visible property; and
    * the **raw bytes** show it escaped -- wrapped in quotes, internal
      quotes doubled.  Without this the test would pass on an
      under-escaped file, because Python's reader is tolerant: a bare
      quote mid-field is accepted, and a field split by an unescaped
      delimiter still parses as *some* number of fields.

    Driven with real values (see ``_DELIMITER_COLLISIONS``), and through
    an export whose delimiter the value actually collides with -- which
    is why the comma case goes through the Neo4j bundle rather than the
    ``.tsv``.
    """
    form_spec = FORMS_BY_NAME[form]
    response = app.post(form_spec.query_path, json=form_spec.body([code]))
    assert response.status_code == 200,         f"{form}: query for {code} gave {response.status_code}"

    spec = EXPORTS_BY_KEY[export_key]
    files = dict(_unwrap(spec, _export(app, spec, response.json())))
    assert filename in files, (
        f"{export_key} produced {sorted(files)}, not {filename} -- the file "
        "this case is about is no longer in that export")
    text = files[filename]

    rule = _rule_for(filename)
    assert rule and rule.delimiter, f"{filename}: not a delimited table"

    rows = [row for row in csv.reader(io.StringIO(text),
                                      delimiter=rule.delimiter) if row]
    fields = {cell.strip() for row in rows for cell in row}
    assert value in fields, (
        f"{export_key}/{filename}: {value!r} -- which is what the shipped "
        f"data holds for {form} code {code}, and which carries {why} -- did "
        f"not come back as a single field.  Either the writer split it, or "
        f"it is not in this file.  Fields resembling it: "
        f"{sorted(f for f in fields if f[:20] in value)[:3]}")

    assert raw_marker in text, (
        f"{export_key}/{filename}: {value!r} is present but the bytes do "
        f"not show it escaped -- expected to find {raw_marker!r} in the "
        f"file.  It carries {why}, so a reader that is stricter than "
        "Python's will split the row there")


def test_the_delimited_file_checks_record_what_they_judged(artifacts_dir):
    """Write the coverage of the file checks out, per format.

    Counted rather than claimed.  The commit that added these checks
    quoted "30 exports judged" and "40 files judged" in its message, and
    neither number was written anywhere a reader could check -- which is
    the objection AGENTS.md makes about "we tested the exports".  This
    is the smallest fix: the inventory's own arithmetic, in an artefact,
    so the next round can compare rather than take somebody's word.

    Derived from the inventory rather than from a run, deliberately: it
    says what *can* be judged and by which rule, which is the
    denominator.  What a run actually judged is in its own skips, and
    those name their reason.
    """
    by_rule: dict[str, dict[str, int]] = {}
    for suffix, rule in sorted(FORMAT_RULES.items()):
        files = [name for spec in EXPORTS for name in spec.files
                 if name.lower().endswith(suffix)]
        by_rule[suffix] = {
            "files_named_in_the_inventory": len(files),
            "delimiter": rule.delimiter or "(not a delimited table)",
            "byte_order_mark": rule.bom,
        }

    named = [name for spec in EXPORTS for name in spec.files]
    summary = {
        "endpoints_in_the_inventory": len(EXPORTS),
        "endpoints_naming_their_files": sum(1 for s in EXPORTS if s.files),
        "endpoints_streaming_raw": sum(1 for s in EXPORTS if not s.files),
        "files_named_in_the_inventory": len(named),
        "columns_that_must_hold_a_number": len(NUMERIC_COLUMNS),
        "header_aliases": len(_HEADER_ALIASES),
        "by_format": by_rule,
    }
    (artifacts_dir / "delimited_file_coverage.json").write_text(
        json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")

    # The endpoints that stream their file without naming it are the
    # blind spot of the suffix gate above: their real extension arrives
    # in a header at run time.  Recorded so the number is visible rather
    # than discovered again.
    assert summary["endpoints_streaming_raw"] == 14, (
        f"{summary['endpoints_streaming_raw']} endpoints stream a file "
        "without naming it, not 14.  Those are the ones whose suffix "
        "test_every_produced_suffix_has_a_declared_rule cannot see, so the "
        "number is worth knowing when it changes")


def test_every_numeric_column_is_one_the_database_declares_numeric(
        schema_affinities):
    """The inventory above and the shipped schema have to agree.

    ``NUMERIC_COLUMNS`` says which columns a reader computes with;
    ``PRAGMA table_info`` says what the database thinks they are.  If
    the two disagree, one of them is wrong, and this is where it is
    caught -- a column renamed or retyped by a data release fails here,
    naming itself, instead of dropping out of the type check and
    leaving it green.

    Pinned in both directions: every entry must exist and be numeric
    everywhere it appears, and the count is exact, so a column cannot be
    quietly removed from the inventory either.
    """
    assert len(NUMERIC_COLUMNS) == 23, (
        f"{len(NUMERIC_COLUMNS)} columns are declared to need a number, "
        "not 23.  Adding one is welcome -- the count is pinned so that "
        "*removing* one is a decision somebody makes on purpose")

    missing = sorted(c for c in NUMERIC_COLUMNS if c not in schema_affinities)
    assert not missing, (
        f"these columns are not in the shipped schema at all: {missing}.  "
        "Either a data release renamed them or the inventory has a typo, "
        "and either way the headings they cover are not being checked")

    not_numeric = {
        column: sorted(schema_affinities[column])
        for column in NUMERIC_COLUMNS
        if not schema_affinities[column] <= _NUMERIC_AFFINITIES}
    assert not not_numeric, (
        "these columns are in the inventory as having to hold a number, "
        "but the shipped schema gives them a text or blob affinity "
        f"somewhere: {not_numeric}.  Either the claim is wrong or the "
        "database changed under it")


def test_every_alias_resolves_into_the_numeric_inventory():
    """Each alias has to land on something the inventory covers.

    Deliberately modest about what this proves.  It checks the *target*
    is a column ``NUMERIC_COLUMNS`` knows about, so an alias cannot
    point at nothing and quietly stop judging a heading.  It does **not**
    prove the alias names the same quantity -- ``"x": "c_personid"``
    would satisfy it -- and no test can, because that is a claim about
    what a writer meant.  What makes a wrong entry survivable is the
    direction it fails in: it would report a defect that is not there,
    loudly, on the next run.
    """
    assert _HEADER_ALIASES, "the alias table is empty"
    assert len(_HEADER_ALIASES) == 18, (
        f"{len(_HEADER_ALIASES)} aliases, not 18.  Pinned for the same "
        "reason as the inventory: losing one silently stops judging a "
        "heading")

    stray = sorted(f"{header} -> {column}"
                   for header, column in _HEADER_ALIASES.items()
                   if column not in NUMERIC_COLUMNS)
    assert not stray, (
        f"these aliases point outside the numeric inventory: {stray}.  An "
        "alias exists to bring a renamed heading *into* the type check, so "
        "one that lands elsewhere is judging nothing")

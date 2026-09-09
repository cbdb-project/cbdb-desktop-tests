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
import re
import xml.etree.ElementTree as ElementTree
from collections import Counter

import pytest

from cbdb_desktop.app import CbdbApp
from cbdb_desktop.defects import KnownShippedDefect
from cbdb_desktop.exports import (
    EXPORTS,
    FILES,
    KML,
    NOT_EXPORTS,
    RAW,
    SINGLE_FILE,
    STATUS_FILES,
    TABLE,
    ExportSpec,
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
#: Chinese name in it is mojibake -- see CBDB-D-011.
UTF8_BOM = b"\xef\xbb\xbf"

#: Extensions whose consumer is a spreadsheet, and which therefore need
#: the mark.  Not the KML (XML declares its own encoding) and not the
#: SNA formats (Pajek, GDF and VNA readers do not expect one).
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

# The four checks every endpoint in the inventory gets put through.
# None of them carries an expectation of failure: an endpoint that is
# broken fails, and tolerating that is a decision recorded outside the
# suite, in the waiver table, addressed by this test's own name and the
# parametrisation id below (``cbdb_desktop/waivers.py``).  A marker
# written here instead would be invisible policy -- and, keyed to a
# defect id that only exists while a report is being written, would
# stop meaning anything on the next stateless round.
_ALL_CHECKS = frozenset({"well_formed", "people", "repeatable", "empty"})


def _params(check: str):
    """The inventory as pytest params, one per export endpoint.

    The id is the endpoint's own key (``networks:pajek``), which is what
    makes a waiver addressable: ``params = ["networks:pajek"]`` under
    this function's name waives exactly that one endpoint's check and
    leaves the other 44 judged.
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
                # CBDB-D-007's exact signature, recognised here so the
                # marker on this parameter can be narrowed to it: any
                # other malformation still fails as a failure.
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

    Cheap, and it catches what made CBDB-D-004 so hard to notice: an
    export whose content depends on state nothing in the request
    describes.  For the scratch-reading endpoints this is the only
    assertion in the suite that they are idempotent.
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
    somebody else's rows are not, and that is precisely the shape
    CBDB-D-004 took -- an export handing over a result the user's own
    query had not produced.

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
    deliberately -- XML declares its own encoding and Pajek, GDF and VNA
    readers do not expect a mark, so adding one there would break them.

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
        if not raw.startswith(UTF8_BOM):
            without.append(name)

    if not without:
        pytest.skip(f"{spec.key}: no spreadsheet file here carries "
                    "non-ASCII text, so its encoding cannot be misread")

    raise KnownShippedDefect(
        f"{spec.key}: {len(without)} file(s) contain non-ASCII text and "
        f"start with no UTF-8 byte-order mark: {without}.  Excel will "
        "open them in the system code page and show mojibake.")


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


#: The start of a top-level Go declaration, method or plain function.
_GO_FUNC = re.compile(r"^func\s+(?:\([^)]*\)\s*)?(\w+)", re.MULTILINE)


def _go_functions(text: str) -> list[tuple[str, str]]:
    """``[(name, body), ...]`` split at top-level ``func`` boundaries.

    Not a Go parser: the body of one function runs to the start of the
    next, which is all this needs.  ``func`` at column 0 is the only
    thing treated as a boundary, so a closure inside a handler stays
    part of it -- correct here, because a writer that delegates to its
    own local helper is still one writer.
    """
    starts = [(m.start(), m.group(1)) for m in _GO_FUNC.finditer(text)]
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
#: from one click.  Two spellings are in use across these templates and
#: both mean the same thing; a third would have to be added here, which
#: is why the *count* of matches is pinned rather than merely their
#: absence.
_DOWNLOAD_PER_FILE = re.compile(
    r"""forEach\s*\(\s*\(?\s*\w+\s*\)?\s*=>\s*triggerDownload"""
    r"""|for\s*\(\s*let\s+\w+\s*=\s*0\s*;[^)]*\.files\.length""",
    re.IGNORECASE)

#: And the message such a handler then prints, which reports the number
#: of files the *server* returned rather than the number the browser
#: accepted.  This is the half that misleads.
_REPORTS_A_FILE_COUNT = re.compile(
    r"""(?:files\s*\|\|\s*\[\]\)\.length|\.files\.length)\s*"""
    r"""(?:\+|\})?[^;\n]*?file\(s\)""",
    re.IGNORECASE)


def test_no_page_asks_the_browser_for_more_than_one_download(layout):
    """A multi-file export cannot be delivered as several downloads.

    The mechanism behind CBDB-D-012, read out of the shipped templates.
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

    Pinned as an exact map of page to occurrence count, so a page that
    is fixed shows up here and a page that grows another one does too.
    """
    per_file: dict[str, int] = {}
    claims: dict[str, int] = {}
    for page, path in sorted(layout.form_templates().items()):
        html = path.read_text(encoding="utf-8", errors="replace")
        found = len(_DOWNLOAD_PER_FILE.findall(html))
        if found:
            per_file[page] = found
        told = len(_REPORTS_A_FILE_COUNT.findall(html))
        if told:
            claims[page] = told

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


def test_every_kml_writer_closes_its_xml_declaration(layout):
    """The same defect, found in the source rather than over HTTP.

    Reading the shipped Go as data (the discipline ``routes.py`` uses):
    a writer that emits an unclosed XML declaration cannot produce a
    valid file for *any* input, so it does not need a query to find and
    a reader does not need to run the application to believe it.  Listed
    exactly, so a partial fix fails here instead of quietly passing.
    """
    broken = {}
    for source in layout.go_sources():
        text = source.read_text(encoding="utf-8", errors="replace")
        for number, line in enumerate(text.splitlines(), start=1):
            if "<?xml version" not in line:
                continue
            # The declaration as it will be written, with Go's escaping
            # of either quoting style removed.
            written = line.replace('\\"', '"')
            if "<?xml version=\"1.0\" encoding=\"UTF-8\"?>" not in written:
                broken[f"{source.name}:{number}"] = line.strip()

    assert broken == {
        "entry_form_backend.go:1006":
            'fmt.Fprint(w, `<?xml version="1.0" encoding="UTF-8">`+"\\n")',
        "places_form_backend.go:764":
            'fmt.Fprint(w, `<?xml version="1.0" encoding="UTF-8">`+"\\n")',
    }, (
        "the set of unclosed XML declarations changed -- update the defect "
        f"report:\n{broken}")

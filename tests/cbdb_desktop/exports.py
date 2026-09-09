"""Every file the application can hand a user, and how to make it produce one.

This is the export surface: 42 file-producing endpoints across ten
forms, driven as 54 button-and-format combinations,
reached in the UI by the row of buttons under each result grid -- Export
Results, GIS, KML, Neo4j, Pajek, Gephi/GUESS, UCINet, Save Codes.  They
are the point of the application for anyone doing quantitative history:
the grid is looked at, the files are worked with.

**Why this module exists at all.**  Until it did, the suite drove six of
them -- one ``export-results`` per read-only form -- and every
run reported no export problems.  That is not the same as there being
none.  The first run that pressed the rest found four separate defect
families, two of them dead buttons that answer HTTP 500 every time.

So the endpoints are not listed here from recollection:
``tests/test_exports.py`` reads the routing table out of the shipped Go
source (see ``routes.py``) and fails if any registered export route is
missing from ``EXPORTS`` below.  A build that adds an export button
cannot quietly go untested; it fails the coverage gate until someone
declares how to drive it.

**What is a description and what is an oracle.**  Everything here is a
description of the *interface* -- the path, the JSON field names the
request struct declares, which envelope the response uses, which files
it names.  Nothing here predicts the contents of a row.  Row values are
judged in the tests, and only against things that would survive the
handler being rewritten: the response's own internal consistency,
agreement with the grid the same query produced, and membership of
person ids in ``BIOG_MAIN``.

**The envelope and file names ARE pinned**, exactly, the way the route
count and the lookup row counts are.  Three different envelopes are in
use across these 45 endpoints and nobody chose that on purpose; a form
that started answering with a different one, or dropped a file from a
set, would otherwise be invisible to a test that only asked "did I get
some files".  A legitimate change fails here and gets read.

**Preconditions are real.**  An export is the second half of a user's
action, never the first.  Every form requires a query to have run, and
several read a scratch table rather than the request body, so the query
has to have run *in this application, most recently* -- which is why
``reads_scratch`` is recorded and the tests re-establish state per test
rather than once per module.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

# ---------------------------------------------------------------------------
# response envelopes
# ---------------------------------------------------------------------------
# Observed, then pinned.  All three JSON shapes are in live use and the
# difference is not systematic: the same Neo4j export is wrapped in
# {status, files} by seven forms and in {files} by two.

#: ``{"status": "ok", "files": [{"name", "url"}, ...]}``
STATUS_FILES = "status+files"

#: ``{"files": [...]}`` -- the same thing without the status field.
FILES = "files"

#: ``{"name": ..., "url": ...}`` -- one file, no envelope.  Sometimes
#: with a ``status`` field alongside (entry's Save Codes), sometimes not.
SINGLE_FILE = "single"

#: The file streamed as the response body, with a Content-Disposition
#: attachment header.
RAW = "raw"

#: What the file itself is, once unwrapped: a delimited table, or KML.
TABLE = "table"
KML = "kml"


@dataclass(frozen=True)
class ExportSpec:
    """One export endpoint, and how to ask it for a file."""

    form: str
    path: str
    #: Family name, as the UI labels the button.  Used to name the test
    #: and to group failures, never to decide an assertion.
    family: str
    envelope: str
    content: str
    #: Build the request body from the form's query response.
    body: Callable[[Any], dict]
    #: True when the handler ignores the request body and re-reads the
    #: scratch tables the last query filled.  For these the *order* of
    #: requests is the whole contract, and a test that skipped the query
    #: would be exporting the previous test's result.
    reads_scratch: bool = False
    #: The file names the response must carry, in order, for a
    #: multi-file envelope; the single file's name for SINGLE_FILE;
    #: empty for RAW, which names its file in a header instead.
    files: tuple[str, ...] = ()
    #: True when the files are an import set for another program to read
    #: rather than something a person opens.  The Neo4j exports are the
    #: only ones: they are staged for ``LOAD CSV``, which reads a
    #: byte-order mark as part of the first column's name, so the build
    #: omits the mark there on purpose while writing it to every
    #: spreadsheet-facing ``.tsv``.  Recorded here rather than decided
    #: in a test, so the exclusion is one line of the inventory that the
    #: next round inherits.
    machine_import: bool = False
    notes: str = ""

    @property
    def key(self) -> str:
        """Short id for a test name: ``kinship:pajek``."""
        return f"{self.form}:{self.family}"


# ---------------------------------------------------------------------------
# body builders
# ---------------------------------------------------------------------------
#
# Field names come from the request structs in Code/*_form_backend.go.
# They differ per form for no reason anyone remembers: entry, office,
# texts, places and associations take "data"; status takes "statusData"
# and "peopleData"; kinship and assocpairs take the record lists their
# own query returned; group data takes five record lists plus five
# booleans; the Networks form takes nothing at all.

def _nothing(_payload: Any) -> dict:
    return {}


def _data(rows_key: str | None = None, **extra: Any) -> Callable[[Any], dict]:
    """``{"data": <rows>}``, plus any fixed extra fields."""
    def build(payload: Any) -> dict:
        rows = payload if rows_key is None else payload[rows_key]
        return dict({"data": rows}, **extra)
    return build


def _status_and_people(**extra: Any) -> Callable[[Any], dict]:
    def build(payload: Any) -> dict:
        return dict({"statusData": payload["status"],
                     "peopleData": payload["people"]}, **extra)
    return build


def _whole_payload(**extra: Any) -> Callable[[Any], dict]:
    """The query response itself, plus any fixed extra fields.

    Kinship and Association Pairs declare export structs whose fields
    are the query response's fields, so handing the response straight
    back is both the shortest correct body and what the page itself does
    (it keeps the response in a page-scoped variable and posts it).
    """
    def build(payload: Any) -> dict:
        assert isinstance(payload, dict), type(payload)
        return {key: value for key, value in payload.items()
                if not key.startswith("_")} | dict(extra)
    return build


def _group_records(**extra: Any) -> Callable[[Any], dict]:
    def build(payload: Any) -> dict:
        return dict({
            "statusRecords": payload["statusRecords"],
            "officeRecords": payload["officeRecords"],
            "entryRecords": payload["entryRecords"],
            "textRecords": payload["textRecords"],
            "placeRecords": payload["placeRecords"],
        }, **extra)
    return build


#: On the 2026-09-08 build every tab-delimited export is named ``.tsv``.
#: It ships one writer for them -- ``csv.NewWriter`` with ``Comma =
#: '\t'`` -- and until this build the files it produced were handed out
#: as ``.csv``, ``.tab`` or ``.txt`` depending on the form, none of
#: which described a tab-delimited file.  The rename is deliberate and
#: it is consistent across all eleven of them (see e.g.
#: ``entry_form_backend.go:944`` "Tab-delimited .tsv file -- matches VBA
#: GIS header exactly"), so the pins below follow the build.
#:
#: The Neo4j bundles are the deliberate exception and keep ``.csv``:
#: they are an import set for ``LOAD CSV``, not a file anyone opens in a
#: spreadsheet, and the same commit that added the Excel byte-order mark
#: to the ``.tsv`` writers left the Neo4j ones without it on purpose
#: ("Excel needs the BOM to recognize UTF-8; Neo4j exports omit it").
#
#: The six Neo4j exports that ship a fixed six-file set, and the two
#: that do not, are all pinned individually below.  Written out rather
#: than generated: the file *order* differs between forms (office puts
#: PeopleOffice second, status puts PeopleStatus fourth) and a generator
#: would have had to encode that anyway, less legibly.
_NEO4J_PEOPLE_PLACES = ("People_UTF8.csv", "Places_UTF8.csv",
                        "PeoplePlaces_UTF8.csv")


EXPORTS: tuple[ExportSpec, ...] = (
    # -- entry ------------------------------------------------------------
    ExportSpec(
        form="entry", path="/api/entry/export-results", family="results",
        envelope=STATUS_FILES, content=TABLE, body=_nothing,
        reads_scratch=True,
        files=("EntryData_UTF8.tsv", "EntryPeopleData_UTF8.tsv"),
        notes="dumps ZZ_SCRATCH_ENTRY; ignores the request body",
    ),
    ExportSpec(
        form="entry", path="/api/entry/export-gis", family="gis",
        envelope=RAW, content=TABLE, body=_data(format="tab"),
        notes="the only GIS export sent as text/plain rather than "
              "text/tab-separated-values",
    ),
    ExportSpec(
        form="entry", path="/api/entry/export-gis", family="kml",
        envelope=RAW, content=KML, body=_data(format="kml"),
        notes="the same endpoint; format=kml switches the writer",
    ),
    ExportSpec(
        form="entry", path="/api/entry/export-neo4j", family="neo4j",
        envelope=STATUS_FILES, content=TABLE, body=_data(),
        files=_NEO4J_PEOPLE_PLACES + ("PeopleEntry_UTF8.csv",
                                      "PeoplePlacesCodes_UTF8.csv",
                                      "EntryCodes_UTF8.csv"),
        machine_import=True,
    ),
    ExportSpec(
        form="entry", path="/api/entry/save-entry-codes", family="save",
        envelope=SINGLE_FILE, content=TABLE,
        body=lambda payload: {"entryCodes": [
            {"code": row["entryCode"], "desc": row.get("entryDesc", ""),
             "descChn": row.get("entryChn", "")}
            for row in payload[:5]]},
        files=("entry_codes.tsv",),
        notes="saves the picker's selection so it can be re-imported",
    ),

    # -- office -----------------------------------------------------------
    ExportSpec(
        form="office", path="/api/office/export-results", family="results",
        envelope=STATUS_FILES, content=TABLE, body=_data(),
        files=("OfficePostings.tsv", "OfficePostingsPeople.tsv"),
    ),
    ExportSpec(
        form="office", path="/api/office/export-gis", family="gis",
        envelope=RAW, content=TABLE,
        body=_data(format="tab", exportTarget="offices"),
    ),
    ExportSpec(
        form="office", path="/api/office/export-gis", family="gis-people",
        envelope=RAW, content=TABLE,
        body=_data(format="tab", exportTarget="people"),
        notes="the form's second GIS button: people rather than postings",
    ),
    ExportSpec(
        form="office", path="/api/office/export-gis", family="kml",
        envelope=RAW, content=KML,
        body=_data(format="kml", exportTarget="offices"),
    ),
    ExportSpec(
        form="office", path="/api/office/export-neo4j", family="neo4j",
        envelope=STATUS_FILES, content=TABLE, body=_data(),
        files=("People_UTF8.csv", "PeopleOffice_UTF8.csv", "Places_UTF8.csv",
               "PeoplePlaces_UTF8.csv", "PeoplePlacesCodes_UTF8.csv",
               "OfficeCode_UTF8.csv"),
        machine_import=True,
    ),

    # -- status (registered at the top level, without /status/) ------------
    ExportSpec(
        form="status", path="/api/export-results", family="results",
        envelope=STATUS_FILES, content=TABLE, body=_status_and_people(),
        files=("StatusRecords.tsv", "StatusRecordsPeople.tsv"),
    ),
    ExportSpec(
        form="status", path="/api/export-gis", family="gis",
        envelope=RAW, content=TABLE,
        body=lambda payload: {"data": payload["people"], "format": "tab"},
        notes="takes the people rows, not the status rows",
    ),
    ExportSpec(
        form="status", path="/api/export-gis", family="kml",
        envelope=RAW, content=KML,
        body=lambda payload: {"data": payload["people"], "format": "kml"},
    ),
    ExportSpec(
        form="status", path="/api/export-neo4j", family="neo4j",
        envelope=STATUS_FILES, content=TABLE, body=_status_and_people(),
        files=_NEO4J_PEOPLE_PLACES + ("PeopleStatus_UTF8.csv",
                                      "PeoplePlacesCodes_UTF8.csv",
                                      "StatusCode_UTF8.csv"),
        machine_import=True,
    ),

    # -- texts ------------------------------------------------------------
    ExportSpec(
        form="texts", path="/api/texts/export-results", family="results",
        envelope=STATUS_FILES, content=TABLE, body=_data(),
        files=("TextSourceRecords.tsv", "TextSourceRecordsPeople.tsv"),
    ),
    ExportSpec(
        form="texts", path="/api/texts/export-gis", family="gis",
        envelope=RAW, content=TABLE,
        body=_data(format="tab", encoding="unicode"),
    ),
    ExportSpec(
        form="texts", path="/api/texts/export-gis", family="kml",
        envelope=RAW, content=KML,
        body=_data(format="kml", encoding="unicode"),
    ),
    ExportSpec(
        form="texts", path="/api/texts/export-neo4j", family="neo4j",
        envelope=STATUS_FILES, content=TABLE, body=_data(encoding="unicode"),
        files=("People_UTF8.csv", "PeopleText_UTF8.csv", "Places_UTF8.csv",
               "PeoplePlaces_UTF8.csv", "PeoplePlacesCodes_UTF8.csv",
               "TextCode_UTF8.csv"),
        machine_import=True,
    ),

    # -- places -----------------------------------------------------------
    ExportSpec(
        form="places", path="/api/places/export-results", family="results",
        envelope=STATUS_FILES, content=TABLE, body=_data(),
        files=("PlacePeopleRecords.tsv", "PlacePeopleRecordsPeople.tsv"),
    ),
    ExportSpec(
        form="places", path="/api/places/export-gis", family="gis",
        envelope=RAW, content=TABLE,
        body=_data(format="tab", encoding="unicode"),
    ),
    ExportSpec(
        form="places", path="/api/places/export-gis", family="kml",
        envelope=RAW, content=KML,
        body=_data(format="kml", encoding="unicode"),
    ),
    ExportSpec(
        form="places", path="/api/places/export-neo4j", family="neo4j",
        envelope=STATUS_FILES, content=TABLE, body=_data(encoding="unicode"),
        files=("People_UTF8.csv", "PeopleIndexAddr_UTF8.csv",
               "Places_UTF8.csv", "PeoplePlaceRelations_UTF8.csv",
               "PeoplePlaceRelationCodes_UTF8.csv",
               "IndexAddrCode_UTF8.csv"),
        machine_import=True,
    ),
    ExportSpec(
        form="places", path="/api/places/export-pajek", family="pajek",
        envelope=SINGLE_FILE, content=TABLE, body=_data(encoding="unicode"),
        files=("network_UTF8.net",),
    ),
    ExportSpec(
        form="places", path="/api/places/export-gephi", family="gephi",
        envelope=SINGLE_FILE, content=TABLE, body=_data(encoding="unicode"),
        files=("network_UTF8.gdf",),
    ),
    ExportSpec(
        form="places", path="/api/places/export-ucinet", family="ucinet",
        envelope=SINGLE_FILE, content=TABLE, body=_data(encoding="unicode"),
        files=("network_UTF8.vna",),
    ),

    # -- associations -----------------------------------------------------
    ExportSpec(
        form="associations", path="/api/associations/export-query",
        family="results", envelope=STATUS_FILES, content=TABLE,
        body=_nothing, reads_scratch=True,
        files=("Associations_UTF8.tsv", "AssociationsPeople_UTF8.tsv"),
        notes="re-reads ZZ_SN_ASSOC / ZZ_SP_ASSOC (per-form since "
              "2026-09-07; before that they shared one table with three "
              "other forms, which is how one form's query emptied "
              "another form's export)",
    ),
    ExportSpec(
        form="associations", path="/api/associations/export-gis", family="gis",
        envelope=RAW, content=TABLE,
        body=_data("records", format="tab", encoding="unicode"),
    ),
    ExportSpec(
        form="associations", path="/api/associations/export-gis", family="kml",
        envelope=RAW, content=KML,
        body=_data("records", format="kml", encoding="unicode"),
    ),
    ExportSpec(
        form="associations", path="/api/associations/export-neo4j",
        family="neo4j", envelope=STATUS_FILES, content=TABLE,
        body=_data("records", encoding="unicode"),
        files=_NEO4J_PEOPLE_PLACES + ("PeopleAssociations_UTF8.csv",
                                      "PeoplePlacesCodes_UTF8.csv",
                                      "AssociationCodes_UTF8.csv"),
        notes="answers HTTP 500 on this build: it scans ADDR_CODES."
              "c_admin_type, a text column, into an int",
        machine_import=True,
    ),

    # -- kinship ----------------------------------------------------------
    ExportSpec(
        form="kinship", path="/api/kinship/export-results", family="results",
        envelope=FILES, content=TABLE, body=_nothing, reads_scratch=True,
        files=("KinshipNetwork.tsv", "EgoRelativeKinship.tsv",
               "KinshipPeople.tsv"),
        notes="reads ZZ_SCRATCH_KINNET and friends under kinshipMu",
    ),
    ExportSpec(
        form="kinship", path="/api/kinship/export-gis", family="gis",
        envelope=SINGLE_FILE, content=TABLE,
        body=_whole_payload(format="tab"), files=("kin_gis.tsv",),
    ),
    ExportSpec(
        form="kinship", path="/api/kinship/export-gis", family="kml",
        envelope=SINGLE_FILE, content=KML,
        body=_whole_payload(format="kml"), files=("kin_gis.kml",),
    ),
    ExportSpec(
        form="kinship", path="/api/kinship/export-neo4j", family="neo4j",
        envelope=FILES, content=TABLE, body=_whole_payload(),
        files=("People_UTF8.csv", "PeopleKinship_UTF8.csv",
               "Places_UTF8.csv", "PeoplePlaces_UTF8.csv",
               "KinshipCodes_UTF8.csv"),
        machine_import=True,
    ),
    ExportSpec(
        form="kinship", path="/api/kinship/export-pajek", family="pajek",
        envelope=SINGLE_FILE, content=TABLE, body=_whole_payload(),
        files=("kinship_UTF8.net",),
    ),
    ExportSpec(
        form="kinship", path="/api/kinship/export-gephi", family="gephi",
        envelope=SINGLE_FILE, content=TABLE, body=_whole_payload(),
        files=("kinship_UTF8.gdf",),
    ),
    ExportSpec(
        form="kinship", path="/api/kinship/export-uci-net", family="ucinet",
        envelope=SINGLE_FILE, content=TABLE, body=_whole_payload(),
        files=("kinship_UTF8.vna",),
        notes="spelled export-uci-net here and export-ucinet on Networks",
    ),

    # -- networks ---------------------------------------------------------
    # Every one of these reads a scratch table: the Networks form's
    # exports take no request body at all.
    ExportSpec(
        form="networks", path="/api/networks/export-results", family="results",
        envelope=STATUS_FILES, content=TABLE, body=_nothing,
        reads_scratch=True,
        files=("Networks_UTF8.tsv", "NetworkPeople_UTF8.tsv"),
    ),
    ExportSpec(
        form="networks", path="/api/networks/export-gis", family="gis",
        envelope=SINGLE_FILE, content=TABLE, body=_nothing,
        reads_scratch=True, files=("network_gis_UTF8.tsv",),
    ),
    ExportSpec(
        form="networks", path="/api/networks/export-kml", family="kml",
        envelope=SINGLE_FILE, content=KML, body=_nothing,
        reads_scratch=True, files=("network_UTF8.kml",),
    ),
    ExportSpec(
        form="networks", path="/api/networks/export-neo4j", family="neo4j",
        envelope=FILES, content=TABLE, body=_nothing, reads_scratch=True,
        files=_NEO4J_PEOPLE_PLACES + ("PeopleAssociations_UTF8.csv",
                                      "AssociationCodes_UTF8.csv",
                                      "KinshipCodes_UTF8.csv"),
        machine_import=True,
    ),
    ExportSpec(
        form="networks", path="/api/networks/export-pajek", family="pajek",
        envelope=SINGLE_FILE, content=TABLE, body=_nothing,
        reads_scratch=True, files=("network_UTF8.net",),
        notes="answers HTTP 500 on this build: selects c_node_dist, "
              "which ZZ_SN_NETWORK does not declare",
    ),
    ExportSpec(
        form="networks", path="/api/networks/export-gephi", family="gephi",
        envelope=SINGLE_FILE, content=TABLE, body=_nothing,
        reads_scratch=True, files=("network_UTF8.gdf",),
        notes="handler is handleExportGUESS; the button says Gephi.  "
              "Answers HTTP 500 on this build: selects c_node_dist, "
              "which ZZ_SN_NETWORK does not declare",
    ),
    ExportSpec(
        form="networks", path="/api/networks/export-ucinet", family="ucinet",
        envelope=SINGLE_FILE, content=TABLE, body=_nothing,
        reads_scratch=True, files=("network_UTF8.vna",),
        notes="answers HTTP 500 on this build: selects c_node_dist, "
              "which ZZ_SN_NETWORK does not declare",
    ),

    # -- association pairs -------------------------------------------------
    ExportSpec(
        form="assocpairs", path="/api/assocpairs/export-results",
        family="results", envelope=STATUS_FILES, content=TABLE,
        body=_nothing, reads_scratch=True,
        files=("AssocPairsNetwork.tsv", "AssocPairsPeople.tsv"),
    ),
    ExportSpec(
        form="assocpairs", path="/api/assocpairs/export-gis", family="gis",
        envelope=SINGLE_FILE, content=TABLE,
        body=_whole_payload(format="tab"),
        files=("assocpairs_network.tsv",),
        notes="was the only GIS export named .txt; the 2026-09-08 "
              "build renamed every tab-delimited export to .tsv",
    ),
    ExportSpec(
        form="assocpairs", path="/api/assocpairs/export-gis", family="kml",
        envelope=SINGLE_FILE, content=KML,
        body=_whole_payload(format="kml"),
        files=("assocpairs_network.kml",),
    ),
    ExportSpec(
        form="assocpairs", path="/api/assocpairs/export-neo4j",
        family="neo4j", envelope=STATUS_FILES, content=TABLE,
        body=_whole_payload(),
        files=_NEO4J_PEOPLE_PLACES + ("AssociationRecords_UTF8.csv",),
        machine_import=True,
    ),
    ExportSpec(
        form="assocpairs", path="/api/assocpairs/export-sna", family="pajek",
        envelope=SINGLE_FILE, content=TABLE,
        body=_whole_payload(format="pajek"),
        files=("assocpairs_network.net",),
        notes="one endpoint, three formats -- the button decides",
    ),
    ExportSpec(
        form="assocpairs", path="/api/assocpairs/export-sna", family="gephi",
        envelope=SINGLE_FILE, content=TABLE,
        body=_whole_payload(format="gephi"),
        files=("assocpairs_network.gdf",),
    ),
    ExportSpec(
        form="assocpairs", path="/api/assocpairs/export-sna", family="ucinet",
        envelope=SINGLE_FILE, content=TABLE,
        body=_whole_payload(format="ucinet"),
        files=("assocpairs_network.vna",),
    ),

    # -- group data --------------------------------------------------------
    ExportSpec(
        form="groupdata", path="/api/groupdata/export-results",
        family="results", envelope=STATUS_FILES, content=TABLE,
        body=lambda payload: dict(
            {"personIds": payload["_personIds"]},
            queryStatus=True, queryOffice=True, queryEntry=True,
            queryText=True, queryAddr=True),
        files=("GroupStatusData_UTF8.tsv", "GroupPostingsData_UTF8.tsv",
               "GroupEntryData_UTF8.tsv", "GroupTextData_UTF8.tsv",
               "GroupPlacesData_UTF8.tsv"),
        notes="re-runs the query from the person ids rather than "
              "formatting the rows it is given",
    ),
    ExportSpec(
        form="groupdata", path="/api/groupdata/export-gis", family="gis",
        envelope=STATUS_FILES, content=TABLE,
        body=_group_records(format="tab", exportStatus=True,
                            exportOffice=True, exportOfficePeople=True,
                            exportEntry=True, exportText=True,
                            exportAddr=True),
        files=("status_gis_UTF8.tsv", "office_office_gis_UTF8.tsv",
               "office_people_gis_UTF8.tsv", "entry_gis_UTF8.tsv",
               "text_gis_UTF8.tsv", "place_gis_UTF8.tsv"),
        notes="six files for six sections; on earlier builds five were "
              "named .tab and one .txt, all six now .tsv",
    ),
    ExportSpec(
        form="groupdata", path="/api/groupdata/export-gis", family="kml",
        envelope=STATUS_FILES, content=KML,
        body=_group_records(format="kml", exportStatus=True,
                            exportOffice=True, exportOfficePeople=True,
                            exportEntry=True, exportText=True,
                            exportAddr=True),
        files=(),
        notes="file names are not pinned: the KML set is the tab set "
              "with different extensions, and pinning both would double "
              "the maintenance for no extra signal",
    ),
    ExportSpec(
        form="groupdata", path="/api/groupdata/export-neo4j", family="neo4j",
        envelope=STATUS_FILES, content=TABLE, body=_group_records(),
        files=_NEO4J_PEOPLE_PLACES + (
            "PeoplePlacesCodes_UTF8.csv", "PeopleStatus_UTF8.csv",
            "PeopleOffice_UTF8.csv", "PeopleEntry_UTF8.csv",
            "StatusCode_UTF8.csv", "OfficeCodes_UTF8.csv",
            "EntryCode_UTF8.csv"),
        notes="the one Neo4j export with a conditional file: "
              "InstitutionCodes_UTF8.csv appears only when the result "
              "has institution data, and this fixture's does not",
        machine_import=True,
    ),
)

EXPORTS_BY_KEY = {spec.key: spec for spec in EXPORTS}

#: Route paths the inventory deliberately does not drive as exports, and
#: why.  The coverage gate in test_exports.py subtracts these, so a new
#: build's new export endpoint fails there rather than being silently
#: absent.  Every entry is an *input* endpoint that the gate's name-based
#: filter picks up because of its name.
#:
#: This block used to claim that "each is exercised in
#: test_stateful_forms.py or in test_exports.py's own import round trip".
#: That was true of three of the four and false of the fourth, so the
#: export gate was subtracting ``/api/assocpairs/import-list`` from its
#: own coverage on the strength of a sentence nobody had checked -- the
#: endpoint has never had a request made to it anywhere in the suite.
#: The claim is now per entry, and the one that is not driven says so.
#: The *endpoint* gate in test_zz_controls.py counts it as a gap, which
#: is where it will be answered.
NOT_EXPORTS: dict[str, str] = {
    "/api/kinship/import-people":
        "input: fills the working list -- driven in test_stateful_forms.py",
    "/api/networks/import-people":
        "input: fills the working list -- driven in test_stateful_forms.py",
    "/api/groupdata/import-ids":
        "input: fills the working list -- driven in test_stateful_forms.py",
    "/api/assocpairs/import-list":
        "input: fills the two person slots -- NOT driven by anything yet, "
        "and counted as a gap by the endpoint gate",
}


# ---------------------------------------------------------------------------
# what each file extension promises about its own bytes
# ---------------------------------------------------------------------------
#
# A file name is a promise to whatever opens it, and these are the two
# halves of that promise this build can be held to: which byte separates
# one field from the next, and whether the bytes begin with a UTF-8
# byte-order mark.  Both are properties of the *file*, judged by reading
# it -- no handler's formatting logic is reproduced anywhere.
#
# Written as a table because the answers are not uniform and nobody
# chose that: `.tsv` and `.csv` disagree about the delimiter, Pajek
# *needs* the mark while Gephi and UCINet are broken by it, and the
# Neo4j bundles are `.csv` files that deliberately omit it.  A comment
# claiming "the SNA formats do not expect a mark" was wrong about Pajek
# for exactly as long as it took someone to check.

#: The mark is required: something a person opens in a spreadsheet, or a
#: reader that documents needing it.
BOM_REQUIRED = "required"

#: The mark must not be there: the reader treats it as data.
BOM_FORBIDDEN = "forbidden"

#: Neither: the format declares its own encoding, or is not text.
BOM_IRRELEVANT = "irrelevant"


@dataclass(frozen=True)
class FormatRule:
    """What one file extension promises about the bytes inside it."""

    #: The single character between fields, or None when the format is
    #: not a delimited table (Pajek, GDF, VNA, KML).
    delimiter: str | None
    bom: str
    why: str


#: Keyed by lower-case suffix.  Every file any export produces must have
#: a suffix in here -- ``test_every_produced_suffix_has_a_declared_rule``
#: is the gate, so a build that invents ``.dat`` fails rather than going
#: unjudged.
FORMAT_RULES: dict[str, FormatRule] = {
    ".tsv": FormatRule(
        "\t", BOM_REQUIRED,
        "this build's name for every tab-delimited export, and the "
        "files a historian opens in Excel"),
    ".csv": FormatRule(
        ",", BOM_REQUIRED,
        "comma-separated by its own name.  The Neo4j bundles are the "
        "exception and carry machine_import, which excludes them from "
        "the mark: LOAD CSV reads one as part of the first column name"),
    ".tab": FormatRule(
        "\t", BOM_REQUIRED,
        "tab by name.  No export uses it on the 2026-09-08 build -- the "
        "rename to .tsv took them all -- and the rule stays so that a "
        "build which brings one back is judged rather than skipped"),
    ".txt": FormatRule(
        "\t", BOM_REQUIRED,
        "the GIS exports that were named .txt before the rename were "
        "tab-delimited, so that is what .txt has to mean here"),
    ".net": FormatRule(
        None, BOM_REQUIRED,
        "Pajek: not a delimited table, and its UTF-8 reader expects the "
        "mark -- all four writers say so where they emit it"),
    ".gdf": FormatRule(
        None, BOM_FORBIDDEN,
        "Gephi/GUESS reads the mark as part of the first field name"),
    ".vna": FormatRule(
        None, BOM_FORBIDDEN, "UCINet, same reason as GDF"),
    ".kml": FormatRule(
        None, BOM_IRRELEVANT,
        "XML declares its own encoding in its first line"),
}

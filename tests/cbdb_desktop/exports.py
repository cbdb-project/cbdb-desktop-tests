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
        files=("EntryData_UTF8.csv", "EntryPeopleData_UTF8.csv"),
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
    ),
    ExportSpec(
        form="entry", path="/api/entry/save-entry-codes", family="save",
        envelope=SINGLE_FILE, content=TABLE,
        body=lambda payload: {"entryCodes": [
            {"code": row["entryCode"], "desc": row.get("entryDesc", ""),
             "descChn": row.get("entryChn", "")}
            for row in payload[:5]]},
        files=("entry_codes.txt",),
        notes="saves the picker's selection so it can be re-imported",
    ),

    # -- office -----------------------------------------------------------
    ExportSpec(
        form="office", path="/api/office/export-results", family="results",
        envelope=STATUS_FILES, content=TABLE, body=_data(),
        files=("OfficePostings.csv", "OfficePostingsPeople.csv"),
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
    ),

    # -- status (registered at the top level, without /status/) ------------
    ExportSpec(
        form="status", path="/api/export-results", family="results",
        envelope=STATUS_FILES, content=TABLE, body=_status_and_people(),
        files=("StatusRecords.csv", "StatusRecordsPeople.csv"),
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
    ),

    # -- texts ------------------------------------------------------------
    ExportSpec(
        form="texts", path="/api/texts/export-results", family="results",
        envelope=STATUS_FILES, content=TABLE, body=_data(),
        files=("TextSourceRecords.csv", "TextSourceRecordsPeople.csv"),
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
    ),

    # -- places -----------------------------------------------------------
    ExportSpec(
        form="places", path="/api/places/export-results", family="results",
        envelope=STATUS_FILES, content=TABLE, body=_data(),
        files=("PlacePeopleRecords.csv", "PlacePeopleRecordsPeople.csv"),
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
        files=("Associations_UTF8.csv", "AssociationsPeople_UTF8.csv"),
        notes="re-reads ZZ_SN_ASSOC / ZZ_SP_ASSOC (per-form since "
              "2026-09-07; the shared tables were CBDB-D-004)",
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
        notes="answers HTTP 500 on this build -- see CBDB-D-009",
    ),

    # -- kinship ----------------------------------------------------------
    ExportSpec(
        form="kinship", path="/api/kinship/export-results", family="results",
        envelope=FILES, content=TABLE, body=_nothing, reads_scratch=True,
        files=("KinshipNetwork.csv", "EgoRelativeKinship.csv",
               "KinshipPeople.csv"),
        notes="reads ZZ_SCRATCH_KINNET and friends under kinshipMu",
    ),
    ExportSpec(
        form="kinship", path="/api/kinship/export-gis", family="gis",
        envelope=SINGLE_FILE, content=TABLE,
        body=_whole_payload(format="tab"), files=("kin_gis.tab",),
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
        files=("Networks_UTF8.csv", "NetworkPeople_UTF8.csv"),
    ),
    ExportSpec(
        form="networks", path="/api/networks/export-gis", family="gis",
        envelope=SINGLE_FILE, content=TABLE, body=_nothing,
        reads_scratch=True, files=("network_gis_UTF8.tab",),
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
    ),
    ExportSpec(
        form="networks", path="/api/networks/export-pajek", family="pajek",
        envelope=SINGLE_FILE, content=TABLE, body=_nothing,
        reads_scratch=True, files=("network_UTF8.net",),
        notes="answers HTTP 500 on this build -- see CBDB-D-008",
    ),
    ExportSpec(
        form="networks", path="/api/networks/export-gephi", family="gephi",
        envelope=SINGLE_FILE, content=TABLE, body=_nothing,
        reads_scratch=True, files=("network_UTF8.gdf",),
        notes="handler is handleExportGUESS; the button says Gephi.  "
              "Answers HTTP 500 on this build -- see CBDB-D-008",
    ),
    ExportSpec(
        form="networks", path="/api/networks/export-ucinet", family="ucinet",
        envelope=SINGLE_FILE, content=TABLE, body=_nothing,
        reads_scratch=True, files=("network_UTF8.vna",),
        notes="answers HTTP 500 on this build -- see CBDB-D-008",
    ),

    # -- association pairs -------------------------------------------------
    ExportSpec(
        form="assocpairs", path="/api/assocpairs/export-results",
        family="results", envelope=STATUS_FILES, content=TABLE,
        body=_nothing, reads_scratch=True,
        files=("AssocPairsNetwork.csv", "AssocPairsPeople.csv"),
    ),
    ExportSpec(
        form="assocpairs", path="/api/assocpairs/export-gis", family="gis",
        envelope=SINGLE_FILE, content=TABLE,
        body=_whole_payload(format="tab"),
        files=("assocpairs_network.txt",),
        notes="the only GIS export named .txt rather than .tab",
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
        files=("GroupStatusData_UTF8.csv", "GroupPostingsData_UTF8.csv",
               "GroupEntryData_UTF8.csv", "GroupTextData_UTF8.csv",
               "GroupPlacesData_UTF8.csv"),
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
        files=("status_gis_UTF8.tab", "office_office_gis_UTF8.txt",
               "office_people_gis_UTF8.tab", "entry_gis_UTF8.tab",
               "text_gis_UTF8.tab", "place_gis_UTF8.tab"),
        notes="six files for six sections; one of them is named .txt",
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
    ),
)

EXPORTS_BY_KEY = {spec.key: spec for spec in EXPORTS}

#: Route paths the inventory deliberately does not drive as exports, and
#: why.  The coverage gate in test_exports.py subtracts these, so a new
#: build's new export endpoint fails there rather than being silently
#: absent.  Every entry is an *input* endpoint that the gate's name-based
#: filter picks up; each is exercised in test_stateful_forms.py or in
#: test_exports.py's own import round trip.
NOT_EXPORTS: dict[str, str] = {
    "/api/kinship/import-people": "input: fills the working list",
    "/api/networks/import-people": "input: fills the working list",
    "/api/groupdata/import-ids": "input: fills the working list",
    "/api/assocpairs/import-list": "input: fills the two person slots",
}

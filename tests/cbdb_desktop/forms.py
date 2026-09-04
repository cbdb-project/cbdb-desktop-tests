"""What the suite needs to know about each read-only form query.

One entry per form: where to send a query, how to spell it, where the
rows come back, and how to ask the application to export the result it
just produced.

This is a description of the *interface* -- endpoint paths, JSON field
names, which key holds the rows -- taken from the request structs in
``Code/*_form_backend.go``.  It contains no filtering, joining or
ordering: the application decides what a query means, and the tests only
have to be able to phrase one and read the answer.

Choosing inputs is separate from judging outputs.  ``code_table``/
``code_column`` name the base table a cheap filter value is drawn from
(a code with a handful of rows keeps a response small -- no form query
applies a LIMIT, and one popular code returned 89 MB while this suite was
being written).  Picking an input from the data is not an oracle; nothing
below is ever used to predict what the application should return.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class FormSpec:
    """How to drive one form's query and export endpoints."""

    name: str
    query_path: str
    export_path: str
    code_table: str
    code_column: str
    #: Build a query body from a list of filter codes.
    body: Callable[[list[int]], dict[str, Any]]
    #: Key holding the result rows, or None when the response is an array.
    rows_key: str | None = None
    #: Second key holding the accompanying people rows, where there is one.
    people_key: str | None = None
    #: Build the export body from the query response.  Some forms take the
    #: rows back; others re-read the scratch tables and take nothing.
    export_body: Callable[[Any], dict[str, Any]] = lambda payload: {"data": payload}
    #: CSV files the export is expected to return.
    export_files: tuple[str, ...] = ()
    #: True when the export ignores the request body and re-reads the
    #: scratch tables the last query filled.  Entry and associations do
    #: this; office, status, texts and places render what they are given.
    export_reads_scratch: bool = False
    notes: str = ""

    def rows(self, payload: Any) -> list[dict]:
        """The result rows, whichever shape this form answers with."""
        if self.rows_key is None:
            return payload
        return payload[self.rows_key]

    def people(self, payload: Any) -> list[dict]:
        if self.people_key is None:
            return []
        return payload[self.people_key]


FORMS: tuple[FormSpec, ...] = (
    FormSpec(
        name="entry",
        query_path="/api/entry/query",
        export_path="/api/entry/export-results",
        code_table="ENTRY_DATA",
        code_column="c_entry_code",
        body=lambda codes: {"entryCodes": codes, "addrIds": [],
                            "addrSubUnits": False, "addressFrame": 1,
                            "yearFilterType": "none"},
        export_files=("EntryData_UTF8.csv", "EntryPeopleData_UTF8.csv"),
        export_reads_scratch=True,
        notes="export-results ignores its request body and dumps "
              "ZZ_SCRATCH_ENTRY (entry_form_backend.go:handleExportResults)",
    ),
    FormSpec(
        name="office",
        query_path="/api/office/query",
        export_path="/api/office/export-results",
        code_table="POSTED_TO_OFFICE_DATA",
        code_column="c_office_id",
        body=lambda codes: {"officeCodes": codes, "peopleAddrIds": [],
                            "peopleAddrSubUnits": False, "officeAddrIds": [],
                            "officeAddrSubUnits": False,
                            "yearFilterType": "none"},
        export_files=("OfficePostings.csv", "OfficePostingsPeople.csv"),
    ),
    FormSpec(
        name="status",
        # The status form is the one that registers its endpoints at the
        # top level rather than under /api/status/.
        query_path="/api/query-status",
        export_path="/api/export-results",
        code_table="STATUS_DATA",
        code_column="c_status_code",
        body=lambda codes: {"statusCodes": codes, "yearFilter": "",
                            "addrIds": [], "includeSubUnits": False},
        rows_key="status",
        people_key="people",
        export_body=lambda payload: {"statusData": payload["status"],
                                     "peopleData": payload["people"]},
        export_files=("StatusRecords.csv", "StatusRecordsPeople.csv"),
        notes="uses yearFilter, not yearFilterType, and its own vocabulary",
    ),
    FormSpec(
        name="texts",
        query_path="/api/texts/query",
        export_path="/api/texts/export-results",
        code_table="BIOG_TEXT_DATA",
        code_column="c_textid",
        body=lambda codes: {"textIds": codes, "addrIds": [],
                            "includeSubUnits": False, "yearFilterType": "",
                            "queryMode": "source"},
        export_files=("TextSourceRecords.csv", "TextSourceRecordsPeople.csv"),
    ),
    FormSpec(
        name="associations",
        query_path="/api/associations/query",
        export_path="/api/associations/export-query",
        code_table="ASSOC_DATA",
        code_column="c_assoc_code",
        body=lambda codes: {"assocCodes": codes, "addrIds": [],
                            "includeSubUnits": False,
                            "yearFilterType": "none"},
        rows_key="records",
        people_key="people",
        # This export takes no body at all: it re-reads the scratch tables
        # the query filled, which makes it the strongest available
        # cross-check of the two paths against each other.
        export_body=lambda payload: {},
        export_files=("Associations_UTF8.csv", "AssociationsPeople_UTF8.csv"),
        export_reads_scratch=True,
    ),
    FormSpec(
        name="places",
        query_path="/api/places/query",
        export_path="/api/places/export-results",
        code_table="BIOG_ADDR_DATA",
        code_column="c_addr_id",
        body=lambda codes: {"addrIds": codes, "includeSubUnits": False,
                            "yearFilterType": "none", "includeBiog": True,
                            "filterBac": False, "bacCodes": []},
        export_files=("PlacePeopleRecords.csv", "PlacePeopleRecordsPeople.csv"),
    ),
)

FORMS_BY_NAME = {form.name: form for form in FORMS}

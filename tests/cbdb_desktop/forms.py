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

    # -- the filter dimensions, for the discovered query matrix ---------
    #
    # Every form takes the same three filters -- a year or dynasty
    # window, an address, and its own codes -- under a different set of
    # field names, and one of them (status) even spells the parameter
    # itself differently.  Recording the names here is what lets
    # test_query_matrix.py drive all six from one piece of code instead
    # of six copies that drift apart.

    #: Which request field selects the year/dynasty mode.  Status is the
    #: odd one out: "yearFilter", and its index-year value is "index"
    #: rather than "indexyear".
    year_filter_field: str = "yearFilterType"
    index_year_mode: str = "indexyear"
    dynasty_mode: str = "dynasty"
    #: Which field carries the address ids, and its sub-unit flag.
    addr_field: str = "addrIds"
    subunit_field: str = "includeSubUnits"
    #: True when a result row carries the dynasty *code* ("dy") and not
    #: only the dynasty's name, so a dynasty filter can be checked per
    #: row rather than only as a subset relation.
    row_has_dynasty_code: bool = False
    #: The person column in ``code_table``, for choosing inputs.
    person_column: str = "c_personid"
    notes: str = ""

    def filtered_body(self, codes: list[int], *, mode: str | None = None,
                      from_year: int | None = None, to_year: int | None = None,
                      dynasty: int | None = None,
                      addr_ids: list[int] | None = None,
                      subunits: bool | None = None) -> dict:
        """``body(codes)`` with one extra filter applied.

        Built by overriding fields in the form's own base body rather
        than by composing a request from scratch, so the parts of the
        request this suite has no opinion about keep whatever value the
        form's normal query uses.
        """
        body = dict(self.body(codes))
        if mode is not None:
            body[self.year_filter_field] = mode
        if from_year is not None:
            body["fromYear"] = from_year
        if to_year is not None:
            body["toYear"] = to_year
        if dynasty is not None:
            body["fromDynasty"] = dynasty
            body["toDynasty"] = dynasty
        if addr_ids is not None:
            body[self.addr_field] = addr_ids
        if subunits is not None:
            body[self.subunit_field] = subunits
        return body

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
        subunit_field="addrSubUnits",
        row_has_dynasty_code=True,
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
        addr_field="peopleAddrIds",
        subunit_field="peopleAddrSubUnits",
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
        year_filter_field="yearFilter",
        index_year_mode="index",
        notes="uses yearFilter, not yearFilterType, and its own vocabulary",
    ),
    FormSpec(
        name="texts",
        query_path="/api/texts/query",
        export_path="/api/texts/export-results",
        # BIOG_SOURCE_DATA, not BIOG_TEXT_DATA.  The form has three
        # modes and the default is "source", whose query reads
        # BIOG_SOURCE_DATA; "role" is the one that reads BIOG_TEXT_DATA.
        # Drawing candidate text ids from the wrong one is why four of
        # five of them used to come back empty -- a text can have rows
        # in BIOG_TEXT_DATA and no source record at all.
        code_table="BIOG_SOURCE_DATA",
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
        row_has_dynasty_code=True,
    ),
)

FORMS_BY_NAME = {form.name: form for form in FORMS}

#: How to empty every working list the application keeps, as
#: ``(path, body)`` pairs.  One entry per list, because since the
#: 2026-09-07 build there is one list per form: clearing through
#: Networks leaves Kinship's alone.
#:
#: Lives here, next to the form descriptions, because two test files need
#: it and a copy in each is a copy that will be updated in one of them.
#: An earlier version of this suite had exactly that, and the file that
#: was not updated spent a run exporting the previous test's result.
#:
#: The three forms do not agree on how.  Networks and Association Pairs
#: register a clear endpoint; **Kinship does not** -- its page has no
#: Clear button, because both of its list-filling endpoints truncate
#: first, so importing an empty list is the only way to empty it.  And
#: Networks' ``import-people`` short-circuits on an empty list and
#: answers ``{"count": 0}`` *without* clearing, so the clear endpoint is
#: the only thing that works there.  Both quirks are pinned in
#: test_stateful_forms.py.
WORKING_LIST_RESETS: tuple[tuple[str, dict], ...] = (
    ("/api/kinship/import-people", {"personIds": []}),
    ("/api/networks/clear-person", {}),
    ("/api/assocpairs/clear-list", {}),
)

#: Storing an empty list is how the forms that overwrite silently empty
#: the one global store.  There is no "clear" for it.
STORE_RESET = ("/api/places/store-person-ids", {"personIds": []})

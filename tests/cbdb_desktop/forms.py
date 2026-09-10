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
    #: Files the export is expected to return.  Tab-delimited and named
    #: ``.tsv`` since the 2026-09-08 build, which renamed every one of
    #: them from ``.csv`` -- see the note above ``EXPORTS`` in
    #: ``exports.py``, which pins the same names for all 42 endpoints.
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
    #: The *other* year the form can filter on, where it has one.  Entry
    #: and Office each offer a second column -- the year of the entry
    #: itself, the year of the posting -- and the suite drove only
    #: ``index_year_mode`` until 2026-09-10, so half of each form's year
    #: filter had never been requested.  Empty where the form has one
    #: mode; the sweep skips those rather than inventing a second.
    other_year_mode: str = ""
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
        other_year_mode="entryyear",
        body=lambda codes: {"entryCodes": codes, "addrIds": [],
                            "addrSubUnits": False, "addressFrame": 1,
                            "yearFilterType": "none"},
        export_files=("EntryData_UTF8.tsv", "EntryPeopleData_UTF8.tsv"),
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
        other_year_mode="officeyear",
        body=lambda codes: {"officeCodes": codes, "peopleAddrIds": [],
                            "peopleAddrSubUnits": False, "officeAddrIds": [],
                            "officeAddrSubUnits": False,
                            "yearFilterType": "none"},
        export_files=("OfficePostings.tsv", "OfficePostingsPeople.tsv"),
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
        export_files=("StatusRecords.tsv", "StatusRecordsPeople.tsv"),
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
        export_files=("TextSourceRecords.tsv", "TextSourceRecordsPeople.tsv"),
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
        export_files=("Associations_UTF8.tsv", "AssociationsPeople_UTF8.tsv"),
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
        export_files=("PlacePeopleRecords.tsv", "PlacePeopleRecordsPeople.tsv"),
        row_has_dynasty_code=True,
    ),
)

FORMS_BY_NAME = {form.name: form for form in FORMS}


# ---------------------------------------------------------------------------
# the adjustable options, and what turning each one on must do
# ---------------------------------------------------------------------------
#
# Codes, dynasty, years and address are the filters with values; these
# are the ones with a switch.  Between them the six forms offer 21 of
# them, and before this table the suite drove exactly two.
#
# What makes them testable without an oracle is that each one has a
# *direction*.  A switch that widens the query can only add rows; one
# that narrows it can only remove them.  Neither claim needs to know
# what the data holds, and neither can be satisfied by a handler that
# ignores the switch -- that would leave the two results identical, and
# an identical result is asserted against too, because a switch that
# changes nothing on data chosen to make it matter is a switch that is
# not wired up.
#
# The direction is read off the request struct's own meaning, not
# guessed: "includeSubUnits" cannot remove people, "mainSourceOnly"
# cannot add texts.  Where a switch legitimately does neither -- it
# changes which *columns* come back, or which of two modes runs -- the
# direction is "differs", and only the "it did something" half applies.

#: Shared note for the seven *Use XY* switches.  Written once because
#: the mechanism is one function -- ``populateScratchAddr`` in
#: ``office_form_backend.go`` -- that every form's address filter calls.
_USE_XY = (
    "Use XY widens the chosen addresses to every address within 0.03 "
    "degrees of one of them, so it can only add rows.  It reaches the "
    "query only when an address filter is set, which is why `needs` "
    "names one: with no address chosen, populateScratchAddr is never "
    "called and the switch is inert for a reason that is not a defect."
)

WIDENS = "widens"        #: turning it on can only add rows
NARROWS = "narrows"      #: turning it on can only remove rows
DIFFERS = "differs"      #: it changes the result, in no fixed direction


@dataclass(frozen=True)
class Toggle:
    """One boolean or mode option on a form, and what it must do."""

    form: str
    #: The request field this switch sets.  Named ``option`` and not
    #: ``field`` because ``dataclasses.field`` is in scope here and a
    #: dataclass attribute shadowing it reads like a bug even when it is
    #: not one.
    option: str
    direction: str
    #: The value that is "on".  Almost always True; ``queryMode`` and
    #: friends take a string.
    on: Any = True
    off: Any = False
    #: True when the option only reaches the query in combination with
    #: another field -- ``filterBac`` does nothing without ``bacCodes``
    #: -- and the test must therefore send both.
    needs: dict[str, Any] = field(default_factory=dict)
    notes: str = ""

    @property
    def id(self) -> str:
        return f"{self.form}-{self.option}"


TOGGLES: tuple[Toggle, ...] = (
    # -- entry ------------------------------------------------------------
    Toggle(form="entry", option="addrSubUnits", direction=WIDENS,
           needs={"addrIds": "@address"},
           notes="an address plus its sub-units is a superset of the "
                 "address alone"),
    Toggle(form="entry", option="addrUseXY", direction=WIDENS,
           needs={"addrIds": "@address_with_neighbours"},
           notes=_USE_XY),
    # addressFrame picks *which* address a row is filtered on -- the
    # person's index address (1) or the entry's own (2) -- so neither
    # result contains the other.
    Toggle(form="entry", option="addressFrame", direction=DIFFERS,
           on=2, off=1, needs={"addrIds": "@address"}),

    # -- office -----------------------------------------------------------
    Toggle(form="office", option="peopleAddrSubUnits", direction=WIDENS,
           needs={"peopleAddrIds": "@address"}),
    Toggle(form="office", option="officeAddrSubUnits", direction=WIDENS,
           needs={"officeAddrIds": "@address"},
           notes="the office's own location, not the person's"),
    Toggle(form="office", option="peopleAddrUseXY", direction=WIDENS,
           needs={"peopleAddrIds": "@address_with_neighbours"}, notes=_USE_XY),
    Toggle(form="office", option="officeAddrUseXY", direction=WIDENS,
           needs={"officeAddrIds": "@address_with_neighbours"},
           notes=_USE_XY + "  Office is the only form with two address "
                 "filters, and therefore two of these."),

    # -- status -----------------------------------------------------------
    Toggle(form="status", option="includeSubUnits", direction=WIDENS,
           needs={"addrIds": "@address"}),
    Toggle(form="status", option="addrUseXY", direction=WIDENS,
           needs={"addrIds": "@address_with_neighbours"}, notes=_USE_XY),

    # -- texts ------------------------------------------------------------
    Toggle(form="texts", option="includeSubUnits", direction=WIDENS,
           needs={"addrIds": "@address"}),
    Toggle(form="texts", option="addrUseXY", direction=WIDENS,
           needs={"addrIds": "@address_with_neighbours"}, notes=_USE_XY),
    Toggle(form="texts", option="mainSourceOnly", direction=NARROWS),
    Toggle(form="texts", option="selfBioOnly", direction=NARROWS),
    # "both" runs the source query and the role query; "source" runs only
    # the first, so both is a superset.
    Toggle(form="texts", option="queryMode", direction=WIDENS,
           on="both", off="source"),

    # -- associations -----------------------------------------------------
    Toggle(form="associations", option="includeSubUnits", direction=WIDENS,
           needs={"addrIds": "@address"}),
    Toggle(form="associations", option="addrUseXY", direction=WIDENS,
           needs={"addrIds": "@address_with_neighbours"}, notes=_USE_XY),

    # -- places -----------------------------------------------------------
    Toggle(form="places", option="includeSubUnits", direction=WIDENS),
    Toggle(form="places", option="addrUseXY", direction=WIDENS,
           needs={"addrIds": "@address_with_neighbours"}, notes=_USE_XY),
    # The Places form's seven branch switches: each adds a category of
    # person to the result, so each can only widen it.
    Toggle(form="places", option="includeBiog", direction=WIDENS),
    Toggle(form="places", option="includeAssocPlace", direction=WIDENS),
    Toggle(form="places", option="includeAssocPerson", direction=WIDENS),
    Toggle(form="places", option="includeEntry", direction=WIDENS),
    Toggle(form="places", option="includeKinship", direction=WIDENS),
    Toggle(form="places", option="includeOffice", direction=WIDENS),
    Toggle(form="places", option="includeInst", direction=WIDENS),
    # filterBac restricts the biography branch to named address types,
    # so it can only remove rows -- and only when it is given types.
    Toggle(form="places", option="filterBac", direction=NARROWS,
           needs={"bacCodes": "@bac", "includeBiog": True}),
)

TOGGLES_BY_ID = {toggle.id: toggle for toggle in TOGGLES}

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

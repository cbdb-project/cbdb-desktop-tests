"""How this suite records a defect in the shipped build.

A test that has found a real defect must do three things at once: stay
out of the way of a green run (a permanently red suite teaches people to
ignore it), say loudly what is wrong on every run, and *notice when the
defect is fixed* so the marker can be removed.

``pytest.mark.xfail(strict=True)`` does all three -- but on its own it
also swallows any *other* failure of the same test.  A test marked
"expected to fail because the search index is empty" would go on quietly
xfailing if the endpoint started returning 500, or malformed JSON, or a
different wrong answer entirely.

So a defect is signalled by raising :class:`KnownShippedDefect` after the
test has confirmed the *exact* known signature, and the marker is
narrowed to that exception::

    @pytest.mark.xfail(strict=True, raises=KnownShippedDefect,
                       reason=DEFECTS["name-search"].reason)
    def test_something(app):
        result = app.json(...)
        if result == the_known_wrong_answer:
            raise KnownShippedDefect("...")
        assert result == the_right_answer

Now the known defect xfails; anything else fails as a failure; and a fix
turns the test green-unexpectedly, which pytest reports as an error.

The registry below is the single source of truth for what has been found.
``reports/generate_report.py`` turns it, plus the outcomes of one run,
into the issues report -- so the bug report and the tests can never drift
apart.
"""
from __future__ import annotations

from dataclasses import dataclass, field


class KnownShippedDefect(AssertionError):
    """Raised when a test confirms a defect already known to be shipped.

    Subclasses AssertionError so the message reads like a normal test
    failure when it does escape (for instance under ``--runxfail``).
    """


@dataclass(frozen=True)
class Defect:
    """One confirmed defect in the shipped build."""

    key: str
    title: str
    severity: str            # "high" | "medium" | "low"
    area: str                # which part of the application
    summary: str             # what is wrong, in a sentence or two
    evidence: str            # the measurement that establishes it
    impact: str              # what it means for someone using CBDB
    fix: str                 # what would resolve it
    source: tuple[str, ...] = ()   # file:line references into the build
    tests: tuple[str, ...] = ()    # test names that demonstrate it

    @property
    def reason(self) -> str:
        """The line pytest prints for this defect in an xfail summary.

        Deliberately one line.  The full account -- evidence, impact,
        suggested fix -- lives in the generated issues report; repeating
        it per test made a run's summary unreadable, which defeats the
        point of saying it at all.
        """
        return (f"SHIPPED DEFECT [{self.key}] {self.title} "
                f"(reports/CBDB_Desktop_Issues.md)")


_DEFECTS: tuple[Defect, ...] = (
    Defect(
        key="CBDB-D-001",
        title="Person search finds nothing for terms of three or more characters",
        severity="high",
        area="People browser (/CBDB_Browser)",
        summary=(
            "Data/CBDB.db ships ZZZ_NAMES_FTS -- the external-content FTS5 "
            "trigram index over ZZZ_NAMES -- created together with its sync "
            "triggers but never populated.  SQLite uses that index for LIKE "
            "patterns of three or more characters and scans the content table "
            "below that, so short searches work and every realistic one "
            "silently returns nothing."),
        evidence=(
            "ZZZ_NAMES holds 866,011 names; ZZZ_NAMES_FTS_idx and "
            "ZZZ_NAMES_FTS_docsize are empty and ZZZ_NAMES_FTS_data holds 2 "
            "rows.  Through the shipped binary: 'wa' returns 56,504 (correct), "
            "'Wang' returns 0 of 50,493, 'Wang Anshi' returns 0 of 5, "
            "'王安石' returns 0 of 2, while '王安' correctly returns 146.  "
            "Rebuilding the index on a copy takes about 4 seconds and makes "
            "every one of those searches return exactly the counts the data "
            "supports."),
        impact=(
            "The primary way of finding a person is broken for essentially "
            "every realistic query.  A full surname, a full name, or a "
            "three-character Chinese name returns an empty list that is "
            "indistinguishable from 'this person is not in CBDB'.  All 658,941 "
            "people are affected; the underlying data is intact."),
        fix=(
            "Run INSERT INTO ZZZ_NAMES_FTS(ZZZ_NAMES_FTS) VALUES('rebuild') "
            "against the release database -- CBDBSetUpCode/zzznames_backend.go "
            "already does this as part of RunZZZNames -- and assert at build "
            "time that ZZZ_NAMES_FTS_docsize and ZZZ_NAMES have equal counts."),
        source=("Code/browser_form_backend.go:812",
                "CBDBSetUpCode/zzznames_backend.go:114",
                "Data/CBDB.db.schema.sql:1035"),
        tests=("test_searching_people_by_name_finds_them",
               "test_the_name_search_index_is_populated"),
    ),
    Defect(
        key="CBDB-D-002",
        title="The Query Builder offers 30 columns that do not exist",
        severity="medium",
        area="Query Builder (/QBE)",
        summary=(
            "Data/qbe_schema.json lists 30 columns across 8 views that "
            "Data/CBDB.db does not have.  HasColumn validates a request "
            "against that JSON whitelist alone and never against the "
            "database, so each one passes validation and then fails in "
            "SQLite."),
        evidence=(
            "Comparing the whitelist against PRAGMA table_info for all 99 "
            "offered tables finds 30 absent columns, in View_BiogInstAddrData, "
            "View_BiogInstData, View_BiogSourceData, View_BiogTextData, "
            "View_Entry, View_EventData, View_KinAddr and "
            "View_PostingOfficeData.  Selecting any of them through "
            "/api/qbe/run answers HTTP 500 'Query failed: no such column'.  "
            "Four of them are the first column their table offers, so the "
            "failure is one click away."),
        impact=(
            "A user building a query picks a column from the grid's own "
            "dropdown and gets a server error with no indication that the "
            "column was never available.  The eight affected views are "
            "otherwise usable."),
        fix=(
            "Regenerate Data/qbe_schema.json from the live schema with "
            "Code/gen_qbe_schema.py, and have LoadSchemaFromJSON verify each "
            "whitelisted column against the database at startup so a stale "
            "whitelist fails loudly instead of per-query."),
        source=("Code/qbe_schema.go:89", "Code/gen_qbe_schema.py",
                "Data/qbe_schema.json"),
        tests=("test_every_offered_column_exists_in_the_database",
               "test_a_phantom_column_gives_the_user_a_server_error",
               "test_every_offered_table_can_actually_be_queried"),
    ),
    Defect(
        key="CBDB-D-003",
        title="A name is indexed for a person the database does not contain",
        severity="low",
        area="Name index (ZZZ_NAMES)",
        summary=(
            "Person 100382 has rows in ZZZ_NAMES but no row in BIOG_MAIN.  "
            "ZZZ_NAMES is derived from BIOG_MAIN and ALTNAME_DATA at build "
            "time, so this is a row the derivation kept after its source "
            "dropped it."),
        evidence=(
            "One person id -- 100382, 元世祖 / 'Pouyuandaizhudi' -- appears in "
            "ZZZ_NAMES with no matching BIOG_MAIN row.  It is reachable by "
            "name search, and /api/browser/person/100382 then answers 404."),
        impact=(
            "Minor: a single name that can be found and not opened.  Worth "
            "fixing mainly because it means the derivation can outlive its "
            "source, which would matter more at a larger scale."),
        fix=(
            "Rebuild ZZZ_NAMES from the current BIOG_MAIN, and add a "
            "referential check to the build."),
        source=("CBDBSetUpCode/zzznames_backend.go",),
        tests=("test_every_name_belongs_to_a_person_who_exists",),
    ),
    Defect(
        key="CBDB-D-004",
        title="Another form's query silently empties the Associations export",
        severity="high",
        area="Associations form (/LookAtAssociations)",
        summary=(
            "The Associations export takes no request body and no lock: it "
            "re-reads ZZ_SOCIAL_NETWORK and ZZ_SCRATCH_PEOPLE, the scratch "
            "tables its own query filled.  Association Pairs and Networks "
            "clear ZZ_SOCIAL_NETWORK at the start of their own queries, so "
            "visiting either between pressing Query and pressing Export "
            "replaces the result with an empty file.  Kinship clears only "
            "ZZ_SCRATCH_PEOPLE, which empties the second exported file "
            "rather than the first."),
        evidence=(
            "Through the shipped binary: an Associations query returns 55 "
            "rows and exports 55 rows.  A single "
            "POST /api/assocpairs/query then leaves the same export "
            "returning 0 rows -- HTTP 200, status 'ok', a file with nothing "
            "in it but a header.  No error is reported at any point."),
        impact=(
            "A user loses their result with no indication that anything "
            "happened.  The export button still works, the file still "
            "downloads, and it is empty.  Reaching the state takes nothing "
            "unusual: run a query, look at a related form, come back and "
            "export."),
        fix=(
            "Have the export render the result it is given, as the office, "
            "status, texts and places exports already do; or key the "
            "scratch tables per session and hold associationsMu across the "
            "query-and-export pair."),
        source=("Code/associations_form_backend.go:932 (the export reads "
                "ZZ_SOCIAL_NETWORK, taking no lock)",
                "Code/assocpairs_form_backend.go:417 (clears it)",
                "Code/networks_form_backend.go:1190 (clears it)",
                "Code/kinship_form_backend.go:750 (clears ZZ_SCRATCH_PEOPLE, "
                "so the people file empties instead)"),
        tests=("test_another_form_does_not_empty_the_associations_export",),
    ),
    Defect(
        key="CBDB-D-005",
        title="The release ships a previous session's working state",
        severity="medium",
        area="Shipped database (Data/CBDB.db)",
        summary=(
            "Fourteen ZZ_* scratch tables in the released database still "
            "hold the results of somebody's working session.  The forms "
            "read those tables on startup, so a fresh install opens with a "
            "person already in its working list and exports that return a "
            "stranger's data before the user has run anything."),
        evidence=(
            "On a fresh copy of the shipped database, before any request "
            "that changes state: /api/kinship/person-count and "
            "/api/networks/person-count both answer 1 (Ouyang Xiu, person "
            "1384, sits in ZZ_SCRATCH_IMPORT_PEOPLE); store-count answers "
            "2; /api/assocpairs/recall-ids returns Lv Daqi and Lv Zuqian; "
            "the Entry export returns 123 rows and the Associations export "
            "16, both from queries the user never ran.  ZZ_KIN_LIST (112 "
            "rows), ZZ_SCRATCH_KINNET (111), ZZ_SCRATCH_PEOPLE (88), "
            "ZZ_SCRATCH_ENTRY (123) and nine more are likewise populated."),
        impact=(
            "A new user's first Export gives them somebody else's result "
            "with no indication that it is not theirs, and the Kinship and "
            "Networks forms start with a person nobody selected.  It also "
            "means the release was built from a database that had been "
            "used, rather than from a clean one.  Self-limiting: every "
            "form truncates its own scratch tables before writing, so the "
            "state survives only until the user's first query -- which is "
            "why this is medium rather than high."),
        fix=(
            "Empty the ZZ_* scratch tables before packaging, and add a "
            "build-time assertion that they are empty.  Clearing them "
            "costs nothing: every form truncates its own scratch tables "
            "before writing to them anyway."),
        source=("Data/CBDB.db",
                "Code/kinship_form_backend.go:handlePersonCount",
                "Code/entry_form_backend.go:handleExportResults"),
        tests=("test_a_fresh_install_starts_with_no_working_state",),
    ),
    Defect(
        key="CBDB-D-006",
        title="A malformed ranking is accepted and applied to every person",
        severity="high",
        area="Index address rankings (/IndexAddr)",
        summary=(
            "POST /api/indexaddr/update declares its body as a nine-slot "
            "array and validates nothing about its length.  Go's JSON "
            "decoder zero-pads a shorter array and truncates a longer one "
            "without error, so a request with the wrong number of slots is "
            "accepted and applied -- and this is the one endpoint in the "
            "application that rewrites CBDB data rather than scratch."),
        evidence=(
            "Against the shipped binary, on a private copy: a ranks array "
            "of eight elements answers 200 'Rankings updated and BIOG_MAIN "
            "rebuilt successfully' and installs address type 0 ('unknown') "
            "at rank 9, changing the number of people with an index address "
            "from 383,322 to 379,051.  An eleven-element array is accepted "
            "too, with the last two types silently discarded.  The bodies "
            "that are refused are refused for unrelated reasons: a string "
            "fails in the JSON decoder, while a two-element array and an "
            "absent field are zero-padded and then caught by the "
            "duplicate-type check, because padding leaves several slots "
            "holding address type 0.  Eight slots leave only one, so "
            "nothing catches them."),
        impact=(
            "A client that sends the wrong number of slots -- an older or "
            "newer page, a script, a partially-filled form -- silently "
            "reconfigures the index address of every person in the "
            "database and ranks 'unknown' as a real address type.  Nothing "
            "reports it, and the previous ranking is gone; only /reset "
            "restores the shipped order -- and only to the shipped "
            "default, so a ranking the user had configured is gone for "
            "good.  This is why it is rated alongside the export defect: "
            "it silently destroys persistent, user-visible configuration "
            "across every person in the database."),
        fix=(
            "Decode the ranks into a slice and reject a body that does not "
            "carry exactly nine slots, and reject address types that are "
            "not in BIOG_ADDR_CODES (0 is a real row, 'unknown', which is "
            "why the padding goes unnoticed)."),
        source=("Code/indexaddr_form_backend.go:69 (Ranks is a fixed [9]int)",
                "Code/indexaddr_form_backend.go:182 (decode, then no length "
                "check)",
                "Code/indexaddr_form_backend.go:199 (the duplicate check "
                "that accidentally catches the other bad bodies)"),
        tests=("test_a_ranking_of_the_wrong_length_is_refused",),
    ),
)

DEFECTS: dict[str, Defect] = {defect.key: defect for defect in _DEFECTS}

# Convenient aliases, so a test can name the defect it demonstrates
# without repeating an identifier.
BY_NAME: dict[str, Defect] = {
    "name-search": DEFECTS["CBDB-D-001"],
    "qbe-phantom-columns": DEFECTS["CBDB-D-002"],
    "orphan-name": DEFECTS["CBDB-D-003"],
    "associations-export-clobbered": DEFECTS["CBDB-D-004"],
    "shipped-scratch-state": DEFECTS["CBDB-D-005"],
    "unvalidated-ranking": DEFECTS["CBDB-D-006"],
}

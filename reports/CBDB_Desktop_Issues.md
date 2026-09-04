# CBDB-Desktop — issues found by the test suite

Generated 2026-09-04 11:03 UTC from a run of 212 tests (21s).

Build under test: `cbdb-desktop_20260901.zip`

| outcome | count |
|---|---|
| passed | 173 |
| xfailed | 39 |

Every issue below was found by driving the shipped `Bin/cbdb.exe` over HTTP against the shipped database, and each one is demonstrated by a named test that fails (as a strict xfail) for as long as the defect is present.

## Summary

| id | severity | status | issue |
|---|---|---|---|
| CBDB-D-001 | high | CONFIRMED | Person search finds nothing for terms of three or more characters |
| CBDB-D-004 | high | CONFIRMED | Another form's query silently empties the Associations export |
| CBDB-D-002 | medium | CONFIRMED | The Query Builder offers 30 columns that do not exist |
| CBDB-D-003 | low | CONFIRMED | A name is indexed for a person the database does not contain |

## CBDB-D-001 — Person search finds nothing for terms of three or more characters

**Severity:** high &nbsp;&nbsp; **Area:** People browser (/CBDB_Browser) &nbsp;&nbsp; **Status in this run:** CONFIRMED

**What is wrong.** Data/CBDB.db ships ZZZ_NAMES_FTS -- the external-content FTS5 trigram index over ZZZ_NAMES -- created together with its sync triggers but never populated.  SQLite uses that index for LIKE patterns of three or more characters and scans the content table below that, so short searches work and every realistic one silently returns nothing.

**Evidence.** ZZZ_NAMES holds 866,011 names; ZZZ_NAMES_FTS_idx and ZZZ_NAMES_FTS_docsize are empty and ZZZ_NAMES_FTS_data holds 2 rows.  Through the shipped binary: 'wa' returns 56,504 (correct), 'Wang' returns 0 of 50,493, 'Wang Anshi' returns 0 of 5, '王安石' returns 0 of 2, while '王安' correctly returns 146.  Rebuilding the index on a copy takes about 4 seconds and makes every one of those searches return exactly the counts the data supports.

**Impact.** The primary way of finding a person is broken for essentially every realistic query.  A full surname, a full name, or a three-character Chinese name returns an empty list that is indistinguishable from 'this person is not in CBDB'.  All 658,941 people are affected; the underlying data is intact.

**Suggested fix.** Run INSERT INTO ZZZ_NAMES_FTS(ZZZ_NAMES_FTS) VALUES('rebuild') against the release database -- CBDBSetUpCode/zzznames_backend.go already does this as part of RunZZZNames -- and assert at build time that ZZZ_NAMES_FTS_docsize and ZZZ_NAMES have equal counts.

**In the build:** `Code/browser_form_backend.go:812`, `CBDBSetUpCode/zzznames_backend.go:114`, `Data/CBDB.db.schema.sql:1035`

**Demonstrated by:**

- 5 xfailed: `test_searching_people_by_name_finds_them[Wang-50000]`, `test_searching_people_by_name_finds_them[Wang Anshi-1]`, `test_searching_people_by_name_finds_them[Su Shi-1]`, `test_searching_people_by_name_finds_them[\u738b\u5b89\u77f3-1]` (+1 more)

## CBDB-D-004 — Another form's query silently empties the Associations export

**Severity:** high &nbsp;&nbsp; **Area:** Associations form (/LookAtAssociations) &nbsp;&nbsp; **Status in this run:** CONFIRMED

**What is wrong.** The Associations export takes no request body and no lock: it re-reads ZZ_SOCIAL_NETWORK and ZZ_SCRATCH_PEOPLE, the scratch tables its own query filled.  Association Pairs and Networks clear ZZ_SOCIAL_NETWORK at the start of their own queries, so visiting either between pressing Query and pressing Export replaces the result with an empty file.  Kinship clears only ZZ_SCRATCH_PEOPLE, which empties the second exported file rather than the first.

**Evidence.** Through the shipped binary: an Associations query returns 55 rows and exports 55 rows.  A single POST /api/assocpairs/query then leaves the same export returning 0 rows -- HTTP 200, status 'ok', a file with nothing in it but a header.  No error is reported at any point.

**Impact.** A user loses their result with no indication that anything happened.  The export button still works, the file still downloads, and it is empty.  Reaching the state takes nothing unusual: run a query, look at a related form, come back and export.

**Suggested fix.** Have the export render the result it is given, as the office, status, texts and places exports already do; or key the scratch tables per session and hold associationsMu across the query-and-export pair.

**In the build:** `Code/associations_form_backend.go:932 (the export reads ZZ_SOCIAL_NETWORK, taking no lock)`, `Code/assocpairs_form_backend.go:417 (clears it)`, `Code/networks_form_backend.go:1190 (clears it)`, `Code/kinship_form_backend.go:750 (clears ZZ_SCRATCH_PEOPLE, so the people file empties instead)`

**Demonstrated by:**

- 1 xfailed: `test_another_form_does_not_empty_the_associations_export`

## CBDB-D-002 — The Query Builder offers 30 columns that do not exist

**Severity:** medium &nbsp;&nbsp; **Area:** Query Builder (/QBE) &nbsp;&nbsp; **Status in this run:** CONFIRMED

**What is wrong.** Data/qbe_schema.json lists 30 columns across 8 views that Data/CBDB.db does not have.  HasColumn validates a request against that JSON whitelist alone and never against the database, so each one passes validation and then fails in SQLite.

**Evidence.** Comparing the whitelist against PRAGMA table_info for all 99 offered tables finds 30 absent columns, in View_BiogInstAddrData, View_BiogInstData, View_BiogSourceData, View_BiogTextData, View_Entry, View_EventData, View_KinAddr and View_PostingOfficeData.  Selecting any of them through /api/qbe/run answers HTTP 500 'Query failed: no such column'.  Four of them are the first column their table offers, so the failure is one click away.

**Impact.** A user building a query picks a column from the grid's own dropdown and gets a server error with no indication that the column was never available.  The eight affected views are otherwise usable.

**Suggested fix.** Regenerate Data/qbe_schema.json from the live schema with Code/gen_qbe_schema.py, and have LoadSchemaFromJSON verify each whitelisted column against the database at startup so a stale whitelist fails loudly instead of per-query.

**In the build:** `Code/qbe_schema.go:89`, `Code/gen_qbe_schema.py`, `Data/qbe_schema.json`

**Demonstrated by:**

- 32 xfailed: `test_every_offered_column_exists_in_the_database`, `test_every_offered_table_can_actually_be_queried`, `test_a_phantom_column_gives_the_user_a_server_error[View_BiogInstAddrData-c_personid]`, `test_a_phantom_column_gives_the_user_a_server_error[View_BiogInstAddrData-c_notes]` (+28 more)

## CBDB-D-003 — A name is indexed for a person the database does not contain

**Severity:** low &nbsp;&nbsp; **Area:** Name index (ZZZ_NAMES) &nbsp;&nbsp; **Status in this run:** CONFIRMED

**What is wrong.** Person 100382 has rows in ZZZ_NAMES but no row in BIOG_MAIN.  ZZZ_NAMES is derived from BIOG_MAIN and ALTNAME_DATA at build time, so this is a row the derivation kept after its source dropped it.

**Evidence.** One person id -- 100382, 元世祖 / 'Pouyuandaizhudi' -- appears in ZZZ_NAMES with no matching BIOG_MAIN row.  It is reachable by name search, and /api/browser/person/100382 then answers 404.

**Impact.** Minor: a single name that can be found and not opened.  Worth fixing mainly because it means the derivation can outlive its source, which would matter more at a larger scale.

**Suggested fix.** Rebuild ZZZ_NAMES from the current BIOG_MAIN, and add a referential check to the build.

**In the build:** `CBDBSetUpCode/zzznames_backend.go`

**Demonstrated by:**

- 1 xfailed: `test_every_name_belongs_to_a_person_who_exists`

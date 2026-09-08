# CBDB-Desktop — Issues Report

_A respectful summary of issues uncovered during automated regression testing._

_Build under test: CBDB-Desktop_20260907.7z_

_Generated 2026-09-08 08:59 UTC from a run of 789 tests (174s)._

Dear maintainer,

Below is a summary of the issues we uncovered while building an automated regression-test suite for CBDB-Desktop. We hope this report is useful as you continue your wonderful stewardship of this dataset, and we sincerely thank you for the immense work that has gone into building it.

Every issue below was found by launching the shipped `Bin/cbdb.exe` and driving its own HTTP endpoints against the shipped database — nothing here re-implements the application's logic, so what is described is what the released program does. The issues are ordered by severity (P0 highest). Each entry includes a short description, the measurement that establishes it, step-by-step reproduction, and a suggested fix. None of these are urgent; they are documented so they can be addressed at your convenience.

## How this run went

| outcome | count |
| --- | --- |
| passed | 670 |
| xfailed (a known defect, still present) | 84 |
| skipped | 35 |

## What the suite covers

| Area | Tests | What it checks |
| --- | --- | --- |
| The distribution itself | 54 | That the tree under test really is the shipped archive, file by file |
| The application process | 13 | That the shipped binary starts, serves, and releases its database |
| Every registered route | 17 | All 141 routes read out of the shipped Go source, driven for real |
| The code and address lists | 35 | The dropdowns each form offers before a query is run |
| The Query Builder | 51 | Its whitelist, the SQL it shows the user, and its guards |
| The six single-query forms | 51 | Entry, office, status, texts, associations, places — queries and exports |
| The forms that remember | 16 | Kinship, networks, association pairs, group data — working lists |
| Index-address rankings | 12 | The only endpoints that rewrite CBDB data rather than scratch |
| This report's own sources | 22 | That every issue below still cites real code, in both languages |

## Summary

| ID | Priority | Status in this run | Issue |
| --- | --- | --- | --- |
| CBDB-D-007 | P0 | CONFIRMED | Two KML exports produce a file no mapping tool will open |
| CBDB-D-010 | P0 | CONFIRMED | Two browser tabs, or two copies of the application, share one result |
| CBDB-D-011 | P0 | CONFIRMED | Every exported CSV is UTF-8 without a byte-order mark, so Excel shows Chinese names as mojibake |
| CBDB-D-012 | P0 | CONFIRMED | A multi-file export saves only the first file and reports that it saved them all |
| CBDB-D-002 | P2 | CONFIRMED | The Query Builder offers 30 columns that do not exist |
| CBDB-D-008 | P2 | CONFIRMED | Three of the Networks form's export buttons always fail |
| CBDB-D-009 | P2 | CONFIRMED | The Associations form's Neo4j export always fails |

## Table of contents

- [CBDB-D-007 — Two KML exports produce a file no mapping tool will open](#cbdb-d-007--two-kml-exports-produce-a-file-no-mapping-tool-will-open)
- [CBDB-D-010 — Two browser tabs, or two copies of the application, share one result](#cbdb-d-010--two-browser-tabs-or-two-copies-of-the-application-share-one-result)
- [CBDB-D-011 — Every exported CSV is UTF-8 without a byte-order mark, so Excel shows Chinese names as mojibake](#cbdb-d-011--every-exported-csv-is-utf-8-without-a-byte-order-mark-so-excel-shows-chinese-names-as-mojibake)
- [CBDB-D-012 — A multi-file export saves only the first file and reports that it saved them all](#cbdb-d-012--a-multi-file-export-saves-only-the-first-file-and-reports-that-it-saved-them-all)
- [CBDB-D-002 — The Query Builder offers 30 columns that do not exist](#cbdb-d-002--the-query-builder-offers-30-columns-that-do-not-exist)
- [CBDB-D-008 — Three of the Networks form's export buttons always fail](#cbdb-d-008--three-of-the-networks-forms-export-buttons-always-fail)
- [CBDB-D-009 — The Associations form's Neo4j export always fails](#cbdb-d-009--the-associations-forms-neo4j-export-always-fails)
- [Severity legend](#severity-legend)
- [Reproducing this report](#reproducing-this-report)

## CBDB-D-007 — Two KML exports produce a file no mapping tool will open

**Affected area:** Entry form and Places form — KML

**Severity:** P0 — Silent wrong answer — the application returns wrong or empty results, or produces a file nothing can read, with no error shown to the user.

**Where it comes from:** `software` — In the application: cbdb.exe, its Go sources, its page templates, or the database builder's logic.  Fixed by the CBDB-Desktop developers.

**Status in this run:** CONFIRMED

#### Description

The Entry and Places KML writers open the file with `<?xml version="1.0" encoding="UTF-8">` -- closing the XML declaration with `>` instead of `?>`.  That is not well-formed XML, so every reader rejects the entire file at the first line.  The application reports success and the download completes normally.

#### Evidence

Query either form, press KML, and the file begins `<?xml version="1.0" encoding="UTF-8">`.  Python's XML parser reports 'unclosed token: line 1, column 0'; Google Earth and QGIS refuse the file.  Five other KML writers in the same build (associations, kinship, networks, group data and office) close the declaration correctly, which is what makes this a slip rather than a decision -- and what makes it findable in the source without running anything: entry_form_backend.go:1002 and places_form_backend.go:763.

#### Impact

A historian exports the geography of an entry route or a set of places, opens it in Google Earth, and is told the file is corrupt.  Nothing in the application suggests anything went wrong, so the natural conclusion is that the mapping tool is at fault or the data is bad.  The same two forms' GIS (.tab) exports are unaffected, which is the workaround.

#### Steps to reproduce

1. Open the Entry form (/LookAtEntry), pick an entry code and press Query.
2. Press KML and save the file.
3. Open it in Google Earth, QGIS, or any XML parser: the file is rejected at line 1.
4. The Places form (/LookAtPlaces) behaves identically.

#### Suggested fix

Write `?>` in both places.  Worth adding one shared helper that emits the KML preamble, since there are now seven copies of it and two of them were wrong.

#### Where it lives in the build

- `Code/entry_form_backend.go:1002`
- `Code/places_form_backend.go:763`

#### Demonstrated by

- 49 × passed: `test_an_export_produces_a_well_formed_file[entry:results]`, `test_an_export_produces_a_well_formed_file[entry:gis]`, `test_an_export_produces_a_well_formed_file[entry:neo4j]`, `test_an_export_produces_a_well_formed_file[entry:save]` (+45)
- 6 × xfailed (a known defect, still present): `test_an_export_produces_a_well_formed_file[entry:kml]`, `test_an_export_produces_a_well_formed_file[places:kml]`, `test_an_export_produces_a_well_formed_file[associations:neo4j]`, `test_an_export_produces_a_well_formed_file[networks:pajek]` (+2)

## CBDB-D-010 — Two browser tabs, or two copies of the application, share one result

**Affected area:** Every form with a working list or a scratch result

**Severity:** P0 — Silent wrong answer — the application returns wrong or empty results, or produces a file nothing can read, with no error shown to the user.

**Where it comes from:** `software` — In the application: cbdb.exe, its Go sources, its page templates, or the database builder's logic.  Fixed by the CBDB-Desktop developers.

**Status in this run:** CONFIRMED

#### Description

Nothing in a request identifies the tab or the session it came from.  The scratch tables a query fills and an export reads are one set per database, so a query run in one tab replaces what another tab's export is about to read.  Worse, main.go takes no single-instance lock and defaults to port 0, so cbdb.exe can be launched twice against the same Data/cbdb.db; the in-process mutexes then protect nothing, because the two processes have their own.

#### Evidence

This is the CBDB-Desktop developers' own finding from the 2026-09-07 remediation session, logged there as open and confirmed here from the shipped source: the per-form scratch tables added for CBDB-D-004 remove cross-*form* sharing and leave cross-*request* sharing exactly as it was.  Two requests to the same endpoint are indistinguishable to the handler, and a grep of main.go finds no mutex, lock file, PID file or port pinning.

#### Impact

A user with the Associations form open in two tabs -- an ordinary way to compare two queries -- can export the wrong one, with no error.  The two-process case is worse than overwriting: SQLite's WAL mode permits both to write, so the two can interleave writes into the same scratch tables and produce a result that is neither query's answer.

#### Steps to reproduce

1. Open the Associations form in two browser tabs.
2. In tab A, run a query; the grid fills.
3. In tab B, run a different query.
4. Back in tab A, press Export Results: the file describes tab B's query.
5. Separately: launch Bin/cbdb.exe twice. Both start, both open the same Data/cbdb.db, and neither mentions the other.

#### Suggested fix

Namespace the scratch state per session rather than per form: a session id in a cookie, and either per-session table names or a session column in each scratch table.  Separately, and much cheaper, refuse to start a second instance against the same database (a lock file beside Data/cbdb.db, checked at startup) -- that alone removes the interleaved-write half of the problem.

#### Where it lives in the build

- `Code/main.go`
- `Code/associations_form_backend.go:233`
- `Code/networks_form_backend.go:411`

#### Demonstrated by

- 2 × xfailed (a known defect, still present): `test_a_second_query_replaces_what_the_first_would_export`, `test_nothing_stops_a_second_instance_opening_the_database`

## CBDB-D-011 — Every exported CSV is UTF-8 without a byte-order mark, so Excel shows Chinese names as mojibake

**Affected area:** Every export on every form

**Severity:** P0 — Silent wrong answer — the application returns wrong or empty results, or produces a file nothing can read, with no error shown to the user.

**Where it comes from:** `software` — In the application: cbdb.exe, its Go sources, its page templates, or the database builder's logic.  Fixed by the CBDB-Desktop developers.

**Status in this run:** CONFIRMED

#### Description

The exported files are named EntryData_UTF8.csv, AssociationsPeople_UTF8.csv and so on, and their bytes really are UTF-8 -- but none of them carries a UTF-8 byte-order mark.  Excel on Windows decides a .csv's encoding by looking for that mark and, finding none, reads the file in the system ANSI code page.  Every Chinese name, place and title in the file is then displayed as mojibake.

#### Evidence

Every export in the suite is decoded and its first bytes inspected: not one of the 42 file-producing endpoints emits EF BB BF, and a search of the shipped Go source for a byte-order mark in any spelling (\xEF, \uFEFF, "BOM") returns nothing at all.  The files contain non-ASCII in every case that matters -- a Neo4j People file for one kinship network carries names in Chinese in its second column.

#### Impact

This is the whole point of the application for most of its users: they export a result and open it.  The application reports success, the file downloads, and what appears on screen is unreadable -- which looks like corrupt data rather than an encoding default, so the natural next step is to doubt CBDB.  The workaround (Data > From Text/CSV, choose UTF-8) is not discoverable, and three bytes at the front of each file would remove the need for it.

#### Steps to reproduce

1. Open the Entry form (/LookAtEntry), pick an entry code and press Query.
2. Press Export Results and save EntryPeopleData_UTF8.csv.
3. Double-click the file so Excel opens it: the Chinese columns are mojibake.
4. Inspect the first bytes -- `certutil -dump EntryPeopleData_UTF8.csv | more`, or open it in a hex editor -- and there is no EF BB BF.
5. Re-open the same file through Data > From Text/CSV and choose 65001 / UTF-8: the text is correct, which is what identifies the missing mark as the whole problem.

#### Suggested fix

Write EF BB BF at the start of every text export whose consumer is a spreadsheet -- the .csv, .tab and .txt families.  One shared helper, since the buffers are all built the same way (cbdb_shared_utils.go's toDataURL is the natural place for the CSV ones).  Leave the KML and the SNA formats alone: XML declares its own encoding, and Pajek, GDF and VNA readers do not expect a mark.

#### Where it lives in the build

- `Code/cbdb_shared_utils.go:60`
- `Code/entry_form_backend.go`
- `Code/kinship_form_backend.go`

#### Demonstrated by

- 1 × passed: `test_no_export_writes_a_byte_order_mark`
- 9 × skipped: `test_a_spreadsheet_export_can_be_opened_by_a_spreadsheet[places:pajek]`, `test_a_spreadsheet_export_can_be_opened_by_a_spreadsheet[places:gephi]`, `test_a_spreadsheet_export_can_be_opened_by_a_spreadsheet[places:ucinet]`, `test_a_spreadsheet_export_can_be_opened_by_a_spreadsheet[kinship:pajek]` (+5)
- 31 × xfailed (a known defect, still present): `test_a_spreadsheet_export_can_be_opened_by_a_spreadsheet[entry:results]`, `test_a_spreadsheet_export_can_be_opened_by_a_spreadsheet[entry:gis]`, `test_a_spreadsheet_export_can_be_opened_by_a_spreadsheet[entry:neo4j]`, `test_a_spreadsheet_export_can_be_opened_by_a_spreadsheet[entry:save]` (+27)

## CBDB-D-012 — A multi-file export saves only the first file and reports that it saved them all

**Affected area:** Export Results and Neo4j, on every form that returns more than one file

**Severity:** P0 — Silent wrong answer — the application returns wrong or empty results, or produces a file nothing can read, with no error shown to the user.

**Where it comes from:** `software` — In the application: cbdb.exe, its Go sources, its page templates, or the database builder's logic.  Fixed by the CBDB-Desktop developers.

**Status in this run:** CONFIRMED

#### Description

An export that produces several files downloads them by creating one hidden <a download> per file and clicking each in turn, all inside a single user gesture.  Browsers permit one automatic download per gesture and block the rest, so the first file is saved and the others are not.  The page then reports the number of files the *server* returned -- "2 file(s) ready" -- because it counts the response, not the downloads.  After the block is triggered the browser refuses subsequent exports from the page as well, which is why pressing Export a second time appears to do nothing.

#### Evidence

Reproduced by the maintainer against a running build at http://localhost:8042/LookAtEntry: Export Results reported "Query results export complete - 2 file(s) ready" and one file arrived; pressing Export again saved nothing at all.  The mechanism is in the shipped templates.  Entry's two multi-file handlers fire their clicks in one tick -- `(j.files || []).forEach(f => triggerDownload(f.url, f.name))` -- and then report `(j.files || []).length`.  Four pages do the same; Associations and Networks stagger their clicks by 150 ms per file, which is an attempt at the same problem and still one gesture.  Group Data's Neo4j export returns ten files this way.

#### Impact

The file that goes missing is the second one, and on every form that is the people file -- the names, index years and coordinates.  A user who trusts the message believes they have a complete export and discovers otherwise, if at all, much later.  It also makes the export button appear broken on the second press, which is how it was noticed.

#### Steps to reproduce

1. Open the Entry form (/LookAtEntry), pick an entry code and press Query.
2. Press Export Results.  The status line reads "Query results export complete - 2 file(s) ready".
3. Look in the download folder: one file, not two.
4. Press Export Results again.  Nothing is saved, and the status line says the same thing.
5. The same happens for Neo4j on Entry, Association Pairs and Group Data, where the file sets are six, four and ten files.

#### Suggested fix

Two independent halves.  (1) Deliver a multi-file export as **one** download: a zip built server-side is the usual answer and needs no browser cooperation.  (2) Stop reporting a count the page cannot know: say what was requested ("preparing 2 files") or nothing, never "2 file(s) downloaded".  The second half is a one-line change per handler and removes the part of this that misleads.

#### Where it lives in the build

- `Templates/entry/index.html`
- `Templates/group_data/index.html`
- `Templates/association_pairs/index.html`
- `Templates/associations/index.html`

#### Demonstrated by

- 1 × xfailed (a known defect, still present): `test_no_page_asks_the_browser_for_more_than_one_download`

## CBDB-D-002 — The Query Builder offers 30 columns that do not exist

**Affected area:** Query Builder (/QBE)

**Severity:** P2 — Visible runtime error — the user's action fails with a server error.

**Where it comes from:** `software` — In the application: cbdb.exe, its Go sources, its page templates, or the database builder's logic.  Fixed by the CBDB-Desktop developers.

**Status in this run:** CONFIRMED

#### Description

Data/qbe_schema.json lists 30 columns across 8 views that Data/cbdb.db does not have under those names.  Each of the eight views selects the same column name twice -- KIN_DATA.c_personid and View_PeopleData.c_personid, say -- and SQLite resolves that collision by renaming the second one `c_personid:1`.  The whitelist generator reads the CREATE VIEW text and does not model that rename, so it offers a name the database does not answer to.  ValidateGridState checks a request against the JSON alone, so each one passes validation and then fails in SQLite.

#### Evidence

Comparing the whitelist against PRAGMA table_info for all 102 offered tables finds 30 absent columns, in View_BiogInstAddrData, View_BiogInstData, View_BiogSourceData, View_BiogTextData, View_Entry, View_EventData, View_KinAddr and View_PostingOfficeData.  Every one of the 30 has a sibling in the same view with ':1' appended -- a one-to-one correspondence, which is what identifies duplicate-name resolution as the mechanism rather than a stale file.  Selecting any of them through /api/qbe/run answers HTTP 500 'Query failed: no such column'.  Four of them are the first column their view offers, so the failure is one click away.

#### Impact

A user building a query picks a column from the grid's own dropdown and gets a server error with no indication that the column was never available.  The eight affected views are otherwise usable.  Because the mechanism is duplicate output names rather than a stale file, regenerating qbe_schema.json from the same CREATE VIEW text -- which is what was done for the 2026-09-07 build -- does not change anything: the JSON and the SQL agree with each other and both disagree with SQLite.

#### Steps to reproduce

1. Open the Query Builder (/QBE).
2. Add the view `View_Entry` to the grid.
3. From its column list — the one the page itself supplies — pick `c_personid`.
4. Press Run. The result is HTTP 500: 'Query failed: no such column: v.c_personid'.
5. In the shipped database, `PRAGMA table_info(View_Entry)` lists `c_personid:1` and no `c_personid`.
6. The same happens for 30 columns across 8 views; the full list is pinned in tests/test_qbe.py.

#### Suggested fix

Two independent halves, and the first is the real fix.  (1) Give the eight views unambiguous output names -- alias the second occurrence in the CREATE VIEW, in CBDBSetUpCode/CBDB_AdditionalTablesViewsIndices.sql -- so there is nothing for SQLite to rename.  A column called `c_personid:1` cannot be selected by any client, so this is worth doing whatever the Query Builder does.  (2) Generate qbe_schema.json from PRAGMA table_info against the built database rather than by parsing CREATE VIEW text, so the whitelist cannot describe columns the database does not have.  The build already ships a Go test that would have caught this -- Code/qbe_schema_test.go, added for this very defect, which does read PRAGMA table_info -- but it skips itself unless run from the project root and had not been run against this database.

#### Where it lives in the build

- `Code/qbe_schema.go:89`
- `Code/qbe_schema_test.go`
- `Data/gen_qbe_schema.py`
- `Data/qbe_schema.json`
- `CBDBSetUpCode/CBDB_AdditionalTablesViewsIndices.sql`

#### Demonstrated by

- 1 × passed: `test_no_view_resolves_two_columns_to_the_same_name`
- 32 × xfailed (a known defect, still present): `test_every_offered_column_exists_in_the_database`, `test_every_offered_table_can_actually_be_queried`, `test_a_phantom_column_gives_the_user_a_server_error[View_BiogInstAddrData-c_personid]`, `test_a_phantom_column_gives_the_user_a_server_error[View_BiogInstAddrData-c_notes]` (+28)

## CBDB-D-008 — Three of the Networks form's export buttons always fail

**Affected area:** Networks form (/LookAtNetworks) — Pajek, Gephi and UCINet

**Severity:** P2 — Visible runtime error — the user's action fails with a server error.

**Where it comes from:** `software` — In the application: cbdb.exe, its Go sources, its page templates, or the database builder's logic.  Fixed by the CBDB-Desktop developers.

**Status in this run:** CONFIRMED

#### Description

The Pajek, Gephi and UCINet exports each read the edges of the network out of ZZ_SN_NETWORK and ask that table for a column called c_node_dist.  ZZ_SN_NETWORK has no such column -- the distance it carries per edge is called c_edge_dist -- so SQLite refuses the query and the handler answers HTTP 500.  There is no input for which any of the three can succeed.

#### Evidence

Run a Networks query for a person with kin at depth 1, then press Pajek, Gephi or UCINet: each answers HTTP 500 'Database error: no such column: c_node_dist'.  The three node queries in the same handlers read c_node_dist from ZZ_SP_NETWORK, which does have it; only the edge queries against ZZ_SN_NETWORK are wrong.  Confirmed against the shipped database with PRAGMA table_info: ZZ_SN_NETWORK's 89 columns include c_edge_dist and not c_node_dist.

#### Impact

Three of the seven export formats on the form whose entire purpose is social-network analysis cannot be used at all.  Anyone wanting to take a CBDB network into Pajek, Gephi or UCINet has to go through the Kinship or Association Pairs form instead, where the same three formats work.  The defect predates the 2026-09-07 per-form scratch tables: the shared ZZ_SOCIAL_NETWORK these tables replaced did not have c_node_dist either, so these buttons have never worked and no test had pressed them.

#### Steps to reproduce

1. Open the Networks form (/LookAtNetworks) and set a person who has relatives.
2. Press Run with the smallest distances (maxLoop 1, maxNodeDist 1) so a graph comes back.
3. Press Pajek. The response is HTTP 500 'Database error: no such column: c_node_dist'.
4. The same happens for Gephi and for UCINet.  Export Results, GIS, KML and Neo4j on the same form all work.

#### Suggested fix

In networks_form_backend.go, change the three edge queries to select c_edge_dist (the column ZZ_SN_NETWORK actually has) rather than c_node_dist, or join the node distance in from ZZ_SP_NETWORK if edge distance is not what the colour scale is meant to express.  Both readings are defensible and the code cannot say which was intended, which is why this is reported rather than patched here.

#### Where it lives in the build

- `Code/networks_form_backend.go:2089`
- `Code/networks_form_backend.go:2212`
- `Code/networks_form_backend.go:2337`
- `Code/networks_form_backend.go:419`

#### Demonstrated by

- 98 × passed: `test_an_export_produces_a_well_formed_file[entry:results]`, `test_an_export_produces_a_well_formed_file[entry:gis]`, `test_an_export_produces_a_well_formed_file[entry:neo4j]`, `test_an_export_produces_a_well_formed_file[entry:save]` (+94)
- 10 × xfailed (a known defect, still present): `test_an_export_produces_a_well_formed_file[entry:kml]`, `test_an_export_produces_a_well_formed_file[places:kml]`, `test_an_export_produces_a_well_formed_file[associations:neo4j]`, `test_an_export_produces_a_well_formed_file[networks:pajek]` (+6)

## CBDB-D-009 — The Associations form's Neo4j export always fails

**Affected area:** Associations form (/LookAtAssociations) — Neo4j

**Severity:** P2 — Visible runtime error — the user's action fails with a server error.

**Where it comes from:** `software` — In the application: cbdb.exe, its Go sources, its page templates, or the database builder's logic.  Fixed by the CBDB-Desktop developers.

**Status in this run:** CONFIRMED

#### Description

Building the Neo4j files reads ADDR_CODES and scans c_admin_type into a Go int.  In the shipped database that column is text: its values are administrative-type names like 'State', 'Shengshi' and '[Unknown]', in all 30,100 rows.  The scan fails on the first address, the handler gives up, and the response is HTTP 500.

#### Evidence

Run any Associations query and press Neo4j: HTTP 500 'Neo4j export error: scan addrRow: sql: Scan error on column index 3'.  Column index 3 is c_admin_type.  In the shipped database `SELECT DISTINCT typeof(c_admin_type) FROM ADDR_CODES` returns only 'text', and the schema declares it varchar(255) -- so no data refresh will make the scan succeed.  The same export on five other forms reads ADDR_CODES without asking for this column and works.

#### Impact

Association networks cannot be taken into Neo4j at all.  The Associations form's other three exports work, so the data is reachable another way, but the button a user presses for this reports a server error every time.

#### Steps to reproduce

1. Open the Associations form (/LookAtAssociations) and pick any association code with a handful of records.
2. Press Query; the grid fills.
3. Press Neo4j. The response is HTTP 500 'Neo4j export error: scan addrRow'.

#### Suggested fix

Scan c_admin_type into a string (and, if a number is wanted downstream, resolve it through ADDR_CODES' own type table rather than assuming the column is numeric).  Worth checking every other Scan against ADDR_CODES in the same pass: this column's name reads like a code and its contents are not one.

#### Where it lives in the build

- `Code/associations_form_backend.go:1384`
- `Code/associations_form_backend.go:1395`

#### Demonstrated by

- 98 × passed: `test_an_export_produces_a_well_formed_file[entry:results]`, `test_an_export_produces_a_well_formed_file[entry:gis]`, `test_an_export_produces_a_well_formed_file[entry:neo4j]`, `test_an_export_produces_a_well_formed_file[entry:save]` (+94)
- 10 × xfailed (a known defect, still present): `test_an_export_produces_a_well_formed_file[entry:kml]`, `test_an_export_produces_a_well_formed_file[places:kml]`, `test_an_export_produces_a_well_formed_file[associations:neo4j]`, `test_an_export_produces_a_well_formed_file[networks:pajek]` (+6)

## Severity legend

- **P0** — Silent wrong answer — the application returns wrong or empty results, or produces a file nothing can read, with no error shown to the user.
- **P1** — Destructive write — a request rewrites stored data that it should not, and the previous state cannot be recovered.
- **P2** — Visible runtime error — the user's action fails with a server error.
- **P3** — Packaging — the released files contain something they should not.
- **P4** — Data integrity — a reference in the shipped data does not resolve.

## Reproducing this report

The whole report is generated from one command. With the distribution zip named in `.env` as `CBDB_DESKTOP_ZIP`:

```powershell
.\run_tests.ps1
```

That stages the archive, launches the shipped binary against a private copy of the shipped database, runs 789 tests, and rewrites these files. The suite never writes to the reference copy of `Data/CBDB.db` — every test runs against a per-session copy, so a run leaves the distribution exactly as it found it.

The test that demonstrates each issue is named under it. To run just one:

```powershell
python -m pytest tests -k test_searching_people_by_name_finds_them -v
```


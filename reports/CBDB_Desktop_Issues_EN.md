# CBDB-Desktop — Issues Report

_A respectful summary of issues uncovered during automated regression testing._

_Build under test: CBDB-Desktop_20260908.7z_

_Generated 2026-09-09 10:12 UTC from a run of 877 tests (276s)._

Dear maintainer,

Below is a summary of the issues we uncovered while building an automated regression-test suite for CBDB-Desktop. We hope this report is useful as you continue your wonderful stewardship of this dataset, and we sincerely thank you for the immense work that has gone into building it.

Most of the issues below were found by launching the shipped `cbdb.exe` and driving its own HTTP endpoints against the shipped database; the rest were found by reading the shipped page templates, Go sources and release archive, which is the honest way to describe a defect that needs no query to demonstrate. Either way, nothing here re-implements the application's logic, so what is described is what the released program does. The issues are ordered by severity (P0 highest). Each entry includes a short description, the measurement that establishes it, step-by-step reproduction, and a suggested fix. None of these are urgent; they are documented so they can be addressed at your convenience.

## How this run went

| outcome | count |
| --- | --- |
| passed | 756 |
| failed | 62 |
| xfailed (a known defect, still present) | 3 |
| skipped | 56 |

Of the 62 failures, **61** are the tests that demonstrate the issues below -- they are how those issues are established, and they will pass again when the issues are fixed.  The remaining **1** point to gaps in this test suite rather than defects in the distribution: a control or an endpoint we have not yet driven. They are listed here so the two are not confused, and they are ours to close, not yours.

| Check | What it says we have not driven |
| --- | --- |
| `test_every_endpoint_the_ui_can_reach_is_exercised_by_this_run` | 14 endpoint(s) a user can reach from the interface were never requested by this run |

## What the suite covers

| Area | Tests | What it checks |
| --- | --- | --- |
| The distribution itself | 59 | That the tree under test really is the shipped archive, file by file |
| The application process | 13 | That the shipped binary starts, serves, and releases its database |
| Every registered route | 17 | All 141 routes read out of the shipped Go source, driven for real |
| The code and address lists | 35 | The dropdowns each form offers before a query is run |
| The Query Builder | 51 | Its whitelist, the SQL it shows the user, and its guards |
| The six single-query forms | 51 | Entry, office, status, texts, associations, places — queries and exports |
| The forms that remember | 16 | Kinship, networks, association pairs, group data — working lists |
| Index-address rankings | 12 | The only endpoints that rewrite CBDB data rather than scratch |
| Every filter, on inputs read from the data | 254 | One query per populated combination the shipped database has, plus every switch turned both ways |
| Every export button | 275 | All 45 file-producing endpoints pressed, and the files they return read back |
| The pages in a real browser | 7 | That every page loads without throwing, and that a control waiting on the user un-greys when they do it |
| Two tabs at once | 3 | Whether one query can replace what another was about to export |
| The working tables | 6 | Which form owns which scratch table, read out of the shipped Go |
| This run's own coverage | 5 | That every endpoint the shipped pages can reach was actually requested by this run |
| What was agreed to leave alone | 28 | That every waived outcome still names a check this run has, and that nothing else in the suite tolerates a failure |
| This report's own sources | 22 | That every issue below still cites real code, in both languages |
| This report itself | 23 | That it is reproducible from the run above, invents no issue, drops none, and hides nothing that was waived |
| every test in this run | 877 |  |

## Agreed to leave for now

These outcomes are known and were agreed to be left as they are for the time being.  They are listed so that nothing is tolerated invisibly: each one names the check that reports it, so it can be picked up again at any time.

| Check | Applies to | Effect | Agreed | Until | Why |
| --- | --- | --- | --- | --- | --- |
| test_a_second_query_replaces_what_the_first_would_export | all cases | still checked, failure tolerated | 2026-09-09 (maintainer) | no end date | Agreed to leave as it is: the scratch tables are one set per database, so a query in a second tab replaces what the first tab would export.  Namespacing them per session is a redesign of every form's working state, and this build's users work in one window at a time. |
| test_a_second_working_list_replaces_the_first | all cases | still checked, failure tolerated | 2026-09-09 (maintainer) | no end date | The same agreement, one step earlier: two tabs of one form share a single working list, so the second import replaces the first and the query that follows is about the wrong people.  Left alone for the same reason. |
| test_nothing_stops_a_second_instance_opening_the_database | all cases | still checked, failure tolerated | 2026-09-09 (maintainer) | no end date | The same agreement, at the process level: main.go takes no single-instance lock and chooses its port at random, so cbdb.exe can be launched twice against one database.  A lock file would be the cheap half of a fix, and it was agreed to leave that for a later build too. |

## Summary

| ID | Priority | Status in this run | Issue |
| --- | --- | --- | --- |
| CBDB-D-001 | P0 | CONFIRMED | Both KML exports write an XML declaration that is never closed, so no reader accepts the file |
| CBDB-D-002 | P0 | CONFIRMED | The Places page lets a user switch every category off, and then answers with the Biography rows they excluded |
| CBDB-D-003 | P0 | CONFIRMED | Twenty-two export buttons ask the browser to save several files at once, and twenty-one of them report every file as saved when only the first arrived |
| CBDB-D-004 | P2 | CONFIRMED | Three of the Networks form's four network exports answer HTTP 500 for every input: they select a column their own scratch table does not have |
| CBDB-D-005 | P2 | CONFIRMED | The Associations form's Neo4j export answers HTTP 500 whenever the result has an address: a text column is scanned into an integer |
| CBDB-D-006 | P2 | CONFIRMED | The Query Builder offers 30 columns that the shipped views expose under a different name, and every one of them gives the user a server error |
| CBDB-D-007 | P3 | CONFIRMED | The distribution ships ten dated working copies of its own templates |

## Table of contents

- [CBDB-D-001 — Both KML exports write an XML declaration that is never closed, so no reader accepts the file](#cbdb-d-001--both-kml-exports-write-an-xml-declaration-that-is-never-closed-so-no-reader-accepts-the-file)
- [CBDB-D-002 — The Places page lets a user switch every category off, and then answers with the Biography rows they excluded](#cbdb-d-002--the-places-page-lets-a-user-switch-every-category-off-and-then-answers-with-the-biography-rows-they-excluded)
- [CBDB-D-003 — Twenty-two export buttons ask the browser to save several files at once, and twenty-one of them report every file as saved when only the first arrived](#cbdb-d-003--twenty-two-export-buttons-ask-the-browser-to-save-several-files-at-once-and-twenty-one-of-them-report-every-file-as-saved-when-only-the-first-arrived)
- [CBDB-D-004 — Three of the Networks form's four network exports answer HTTP 500 for every input: they select a column their own scratch table does not have](#cbdb-d-004--three-of-the-networks-forms-four-network-exports-answer-http-500-for-every-input-they-select-a-column-their-own-scratch-table-does-not-have)
- [CBDB-D-005 — The Associations form's Neo4j export answers HTTP 500 whenever the result has an address: a text column is scanned into an integer](#cbdb-d-005--the-associations-forms-neo4j-export-answers-http-500-whenever-the-result-has-an-address-a-text-column-is-scanned-into-an-integer)
- [CBDB-D-006 — The Query Builder offers 30 columns that the shipped views expose under a different name, and every one of them gives the user a server error](#cbdb-d-006--the-query-builder-offers-30-columns-that-the-shipped-views-expose-under-a-different-name-and-every-one-of-them-gives-the-user-a-server-error)
- [CBDB-D-007 — The distribution ships ten dated working copies of its own templates](#cbdb-d-007--the-distribution-ships-ten-dated-working-copies-of-its-own-templates)
- [Severity legend](#severity-legend)
- [Reproducing this report](#reproducing-this-report)

## CBDB-D-001 — Both KML exports write an XML declaration that is never closed, so no reader accepts the file

**Affected area:** Entry form and Places form, KML export

**Severity:** P0 — Silent wrong answer — the application returns wrong or empty results, or produces a file nothing can read, with no error shown to the user.

**Where it comes from:** `software` — In the application: cbdb.exe, its Go sources, its page templates, or the database builder's logic.  Fixed by the CBDB-Desktop developers.

**Status in this run:** CONFIRMED

#### Description

The Entry and Places forms write their KML with the opening line `<?xml version="1.0" encoding="UTF-8">`.  An XML declaration has to end `?>`; this one ends `>`.  Every XML parser therefore rejects the document at its first line, so the file cannot be opened in Google Earth, QGIS or ArcGIS -- and the application reports the export as successful.

#### Evidence

Measured twice, independently.  Driving the two endpoints through the shipped binary returns files beginning with that exact string (`entry:kml/entry_gis_UTF8.kml` and `places:kml/places_export.kml`).  Reading the shipped Go finds the same two writers and no others, so this cannot depend on the data: it is wrong for every input.

#### Impact

Two of the application's geographic exports produce nothing usable, and nothing tells the user.  Anyone mapping entry or place addresses gets a download that their GIS silently refuses to open.

#### Steps to reproduce

1. Open the Entry form (/LookAtEntry), pick any entry code and run the query.
2. Press KML and save the file.
3. Open it in Google Earth, or run any XML parser over it: it fails on line 1.
4. Repeat on the Places form (/LookAtPlace) for the same result.

#### Suggested fix

Add the missing `?` in both writers: `<?xml version="1.0" encoding="UTF-8"?>`.  Worth checking the other KML writers in the same commit -- they are already correct, which is why only these two are listed.

#### Where it lives in the build

- `Code/entry_form_backend.go:1006`
- `Code/places_form_backend.go:764`

#### Demonstrated by

- 7 × failed: `test_an_export_produces_a_well_formed_file[entry:kml]`, `test_an_export_produces_a_well_formed_file[places:kml]`, `test_an_export_produces_a_well_formed_file[associations:neo4j]`, `test_an_export_produces_a_well_formed_file[networks:pajek]` (+3)
- 48 × passed: `test_an_export_produces_a_well_formed_file[entry:results]`, `test_an_export_produces_a_well_formed_file[entry:gis]`, `test_an_export_produces_a_well_formed_file[entry:neo4j]`, `test_an_export_produces_a_well_formed_file[entry:save]` (+44)

## CBDB-D-002 — The Places page lets a user switch every category off, and then answers with the Biography rows they excluded

**Affected area:** Places form, category switches

**Severity:** P0 — Silent wrong answer — the application returns wrong or empty results, or produces a file nothing can read, with no error shown to the user.

**Where it comes from:** `software` — In the application: cbdb.exe, its Go sources, its page templates, or the database builder's logic.  Fixed by the CBDB-Desktop developers.

**Status in this run:** CONFIRMED

#### Description

The Places query handler substitutes `IncludeBiog = true` when it finds all seven category switches off.  As a guard against an empty request that is defensible; what makes it a defect is that the page lets a user reach it.  The seven checkboxes enforce no "at least one" rule, so unticking all of them and pressing Query returns biographical addresses the user has explicitly excluded, with no message.

#### Evidence

Measured on address code 20056, chosen by the suite from the shipped data rather than by hand.  With every category switched off the query returned 396 rows, and the same request with Biography alone switched on returned the same 396 rows -- the empty selection is not merely non-empty, it is exactly the Biography branch's own result.  Measured through the running binary; the substitution is then visible in the source.

#### Impact

A researcher who narrows the query by unticking categories gets results from a category they excluded, presented as the answer to the question they asked.  Nothing in the interface indicates that the selection was overridden.

#### Steps to reproduce

1. Open the Places form (/LookAtPlace) and select an address -- address code 20056 is the one measured above.
2. Untick all seven category checkboxes, including Biography.
3. Press Run Query: rows come back.
4. Tick Biography only and run again: the same rows, in the same number.

#### Suggested fix

Either refuse an empty selection in the page (keep Run Query disabled until at least one category is ticked, the way this build's Associations form now does for its picker), or answer an empty selection with no rows and say so.  The server-side default can stay as a guard once the page cannot send that request.

#### Where it lives in the build

- `Code/places_form_backend.go:205`
- `Templates/places/index.html:90`
- `Templates/places/index.html:540`

#### Demonstrated by

- 1 × failed: `test_turning_every_category_off_returns_nothing`

## CBDB-D-003 — Twenty-two export buttons ask the browser to save several files at once, and twenty-one of them report every file as saved when only the first arrived

**Affected area:** Export buttons on ten form pages

**Severity:** P0 — Silent wrong answer — the application returns wrong or empty results, or produces a file nothing can read, with no error shown to the user.

**Where it comes from:** `software` — In the application: cbdb.exe, its Go sources, its page templates, or the database builder's logic.  Fixed by the CBDB-Desktop developers.

**Status in this run:** CONFIRMED

#### Description

These handlers loop over the file list the server returned and trigger a download per element from a single click.  A browser permits one automatic download per user gesture and blocks the rest, and once blocked the restriction applies to later exports from the same page -- which is why pressing Export a second time can save nothing at all.  Twenty-one of the twenty-two then print the count the *server* returned ("2 file(s) ready"), having never asked the browser what it accepted.

#### Evidence

Counted in the shipped templates: 22 such handlers across all 10 pages that export more than one file (association_pairs 4, associations 2, entry 2, group_data 3, kinship 2, networks 2, office 2, places 2, status 2, texts 1), of which 21 report a server-side count as though it were the outcome (the same, less one of networks').  Three spellings of the same loop are in use and all three are counted; a fourth would fail the check rather than shrink these numbers.

The server side is faultless: the same endpoints return every file, identically, on repeated requests.  Under automation downloads are auto-accepted and every file arrives, so the blocking half is established by reading the delivery code and was reported from real use; the misreported count is measured in the browser.

#### Impact

A user presses Export, is told two or five files are ready, and finds one on disk.  The files that did not arrive are not named, and there is no error to search for.

#### Steps to reproduce

1. Open the Kinship form, run a query, and press Export Results.
2. Note the message: three files ready.
3. Look in the download folder: one file.
4. Press Export Results again -- on a default browser profile nothing is saved this time.

#### Suggested fix

Deliver a multi-file export as one download -- a zip archive is the usual answer and needs no browser permission -- or save the files one user gesture at a time.  Either way, report what was actually delivered rather than what the response contained.

#### Where it lives in the build

- `Templates/kinship/index.html:630`
- `Templates/association_pairs/index.html:936`
- `Templates/group_data/index.html:914`
- `Templates/entry/index.html:1093`
- `Templates/associations/index.html:680`
- `Templates/networks/index.html:1551`
- `Templates/places/index.html:691`
- `Templates/office/index.html:850`
- `Templates/status/index.html:795`
- `Templates/texts/index.html:823`

#### Demonstrated by

- 1 × failed: `test_no_page_asks_the_browser_for_more_than_one_download`

## CBDB-D-004 — Three of the Networks form's four network exports answer HTTP 500 for every input: they select a column their own scratch table does not have

**Affected area:** Networks form: Pajek, Gephi/GUESS and UCINet exports

**Severity:** P2 — Visible runtime error — the user's action fails with a server error.

**Where it comes from:** `software` — In the application: cbdb.exe, its Go sources, its page templates, or the database builder's logic.  Fixed by the CBDB-Desktop developers.

**Status in this run:** CONFIRMED

#### Description

All three read `c_node_dist` from `ZZ_SN_NETWORK`.  That table is created by this same file and its column list does not contain `c_node_dist` -- it has `c_edge_dist` and `c_distance`.  SQLite refuses the query, so the three buttons fail for every query result there can be.  The sibling forms (Associations, Association Pairs) do declare a `c_node_dist`, which is the likely origin of the name.

#### Evidence

Each endpoint answers `500 Database error: no such column: c_node_dist`, including when there is nothing to export -- so the failure is in the statement, not in the data.  Reading the shipped Go independently finds the same three SELECTs and the CREATE TABLE they contradict.

#### Impact

The Networks form is the application's social-network tool and three of its four network formats cannot produce a file at all.  Only Neo4j works.

#### Steps to reproduce

1. Open the Networks form (/LookAtNetworks), select a person and run a query that returns edges.
2. Press Pajek.  The request answers HTTP 500.
3. Repeat with Gephi/GUESS and UCINet: the same error.
4. Press Neo4j: that one produces its files.

#### Suggested fix

Decide which distance the three exports mean and use that column -- `c_edge_dist` is the one `ZZ_SN_NETWORK` populates for an edge -- or add `c_node_dist` to the CREATE TABLE and populate it.  A `PRAGMA table_info` check over each scratch table's declared columns at build time would have caught this, as `Code/qbe_schema_test.go` does for the Query Builder.

#### Where it lives in the build

- `Code/networks_form_backend.go:2093`
- `Code/networks_form_backend.go:2216`
- `Code/networks_form_backend.go:2341`
- `Code/networks_form_backend.go:419`

#### Demonstrated by

- 18 × failed: `test_an_export_produces_a_well_formed_file[entry:kml]`, `test_an_export_produces_a_well_formed_file[places:kml]`, `test_an_export_produces_a_well_formed_file[associations:neo4j]`, `test_an_export_produces_a_well_formed_file[networks:pajek]` (+14)
- 176 × passed: `test_an_export_produces_a_well_formed_file[entry:results]`, `test_an_export_produces_a_well_formed_file[entry:gis]`, `test_an_export_produces_a_well_formed_file[entry:neo4j]`, `test_an_export_produces_a_well_formed_file[entry:save]` (+172)
- 23 × skipped: `test_an_export_describes_the_people_the_grid_did[entry:kml]`, `test_an_export_describes_the_people_the_grid_did[entry:save]`, `test_an_export_describes_the_people_the_grid_did[office:gis]`, `test_an_export_describes_the_people_the_grid_did[office:gis-people]` (+19)

## CBDB-D-005 — The Associations form's Neo4j export answers HTTP 500 whenever the result has an address: a text column is scanned into an integer

**Affected area:** Associations form, Neo4j export

**Severity:** P2 — Visible runtime error — the user's action fails with a server error.

**Where it comes from:** `software` — In the application: cbdb.exe, its Go sources, its page templates, or the database builder's logic.  Fixed by the CBDB-Desktop developers.

**Status in this run:** CONFIRMED

#### Description

The export reads `ADDR_CODES.c_admin_type` into a Go struct field declared `AdminType int`.  That column is text: every one of its 30,100 rows holds a string such as "Xian" or "Zhou".  The scan therefore fails on the first address row and the whole export returns HTTP 500.

#### Evidence

The endpoint answers `500 Neo4j export error: scan addrRow: sql: Scan error on column index 3, name "admin_type": converting driver.Value type string ("Xian") to a int: invalid syntax`.  The shipped schema declares the column `varchar(255)`, and a read-only count over the shipped database finds all 30,100 values are of type text, the commonest being "Xian" (13,687 rows).  So a rebuild of the data would not change it: the declared type in the Go struct is wrong.

#### Impact

The Associations form cannot export to Neo4j for any query whose people have addresses, which is almost all of them.  The user sees a server error.

#### Steps to reproduce

1. Open the Associations form (/LookAtAssociations), pick an association code and run the query.
2. Press Neo4j.
3. The request answers HTTP 500 with the scan error above.

#### Suggested fix

Declare the field `string` and read it as text -- the `COALESCE(c_admin_type, 0)` in the same SELECT should become `COALESCE(c_admin_type, '')` to match.

The same mistake is in the build a second time, and it is not in another Neo4j export -- no other one scans this column.  It is `handlePlaceSearch` in `networks_form_backend.go`, which selects `COALESCE(c_admin_type, 0)` into an `AdminType int` and then `continue`s on a scan error, so it returns an empty list for every search instead of an error.  Nothing in the shipped templates calls that route today, which is why no user has reported it; it is worth fixing in the same commit rather than left to be found once something does.

#### Where it lives in the build

- `Code/associations_form_backend.go:1377`
- `Code/associations_form_backend.go:1388`
- `Code/networks_form_backend.go:2987`
- `Data/cbdb.db.schema.sql:42`

#### Demonstrated by

- 18 × failed: `test_an_export_produces_a_well_formed_file[entry:kml]`, `test_an_export_produces_a_well_formed_file[places:kml]`, `test_an_export_produces_a_well_formed_file[associations:neo4j]`, `test_an_export_produces_a_well_formed_file[networks:pajek]` (+14)
- 147 × passed: `test_an_export_produces_a_well_formed_file[entry:results]`, `test_an_export_produces_a_well_formed_file[entry:gis]`, `test_an_export_produces_a_well_formed_file[entry:neo4j]`, `test_an_export_produces_a_well_formed_file[entry:save]` (+143)
- 41 × skipped: `test_an_export_describes_the_people_the_grid_did[entry:kml]`, `test_an_export_describes_the_people_the_grid_did[entry:save]`, `test_an_export_describes_the_people_the_grid_did[office:gis]`, `test_an_export_describes_the_people_the_grid_did[office:gis-people]` (+37)

## CBDB-D-006 — The Query Builder offers 30 columns that the shipped views expose under a different name, and every one of them gives the user a server error

**Affected area:** The generated Query Builder schema, and the view definitions in CBDBSetUpCode

**Severity:** P2 — Visible runtime error — the user's action fails with a server error.

**Where it comes from:** `software` — In the application: cbdb.exe, its Go sources, its page templates, or the database builder's logic.  Fixed by the CBDB-Desktop developers.

**Status in this run:** CONFIRMED

#### Description

Eight of the shipped views name 30 of their columns with a `:1` suffix -- `c_personid:1`, `c_notes:1`, `c_dy:1` and so on.  SQLite generates those names itself, because each of these views is a deeply nested Access-style join tree whose selected columns are not aliased explicitly.

The column list the grid offers comes from `Data/qbe_schema.json`, generated by `gen_qbe_schema.py`.  That script *knows about this*: it detects the duplicate names, keeps only the first occurrence with the suffix removed, prints a warning, and its own header says "the real fix is adding an explicit AS alias to the view definition".  But it keeps the unsuffixed name on the assumption that this is "how SQLite itself resolves an unqualified reference to one of several same-named columns" -- and for these views that assumption is wrong.  The suffixed name is the one that works: `SELECT t."c_personid:1" FROM View_Entry t` returns rows, while the unsuffixed `SELECT t.c_personid FROM View_Entry t` is refused.  So the generator took a name that could be queried and wrote down one that cannot, and for four of the views it is the first column offered, which makes the whole view look unusable.

#### Evidence

Driving the Query Builder through the running binary, all 30 combinations answer `500 Query failed: no such column`, and for View_BiogInstAddrData, View_BiogInstData, View_Entry and View_KinAddr that is the first column the grid offers.  Reading the shipped database read-only, `PRAGMA table_info` reports exactly those 30 columns with a `:1` suffix across exactly those 8 views.  The naming is reproducible from the view's own SELECT alone; the suffixed name is queryable when quoted, the unsuffixed one is not, and adding an explicit `AS c_personid` to that SELECT removes the suffix and makes `SELECT t.c_personid` succeed -- which identifies the fix as well as the cause.

#### Impact

A user of the Query Builder picks a column from the list the application itself offers and gets a server error.  Four views look entirely broken because their first offered column is one of these.

#### Steps to reproduce

1. Open the Query Builder (/QBE).
2. Choose the view View_Entry.
3. Select its first offered column, c_personid, and run.
4. The request answers 500 `no such column: t.c_personid`.
5. In the shipped database, PRAGMA table_info(View_Entry) shows the column is named `c_personid:1`.

#### Suggested fix

`gen_qbe_schema.py`'s own header already names it: alias the colliding columns explicitly in the eight view definitions (`ENTRY_DATA.c_personid AS c_personid`).  That is the fix verified above -- it removes the suffix and makes `SELECT t.c_personid` succeed -- and it leaves the generated column list correct as it stands.

Until that happens, the generator should not emit a name it cannot verify.  Its warning is printed at generation time, where nobody sees it again; a column whose name does not survive `SELECT t.<name> FROM <view> t LIMIT 0` would be better omitted from the JSON than offered to the user, and that check costs one query per column at generation time.  Emitting the real, suffixed name and quoting it in the generated SQL would also work -- it is the name that resolves -- but the alias is the better fix, because the label a scholar reads should not have a `:1` in it.

#### Where it lives in the build

- `Data/gen_qbe_schema.py:52`
- `Data/qbe_schema.json:5456`
- `CBDBSetUpCode/CBDB_AdditionalTablesViewsIndices.sql:1254`
- `Code/qbe_schema.go:53`

#### Demonstrated by

- 32 × failed: `test_every_offered_column_exists_in_the_database`, `test_every_offered_table_can_actually_be_queried`, `test_a_phantom_column_gives_the_user_a_server_error[View_BiogInstAddrData-c_personid]`, `test_a_phantom_column_gives_the_user_a_server_error[View_BiogInstAddrData-c_notes]` (+28)

## CBDB-D-007 — The distribution ships ten dated working copies of its own templates

**Affected area:** Packaging: Templates/

**Severity:** P3 — Packaging — the released files contain something they should not.

**Where it comes from:** `release` — In how this particular release was assembled -- a working copy shipped in place of a freshly built one, a file that was not regenerated.  Fixed in the release process by whoever builds the distribution.

**Status in this run:** CONFIRMED

#### Description

Ten of the archive's 85 members are dated backups of templates that ship alongside the live file -- `entry/entry.index.20260906.html` next to `entry/index.html`, `qbe/qbe.20260827.html` next to `qbe/qbe.html`, and so on.  No route serves them and only `Static/` is file-served, so they are not reachable pages; they are a working directory that was packaged as it stood.

#### Evidence

Read from the archive's own directory, not from the unpacked tree: `Templates/associations/associations.index.20260906.html`, `associations.index.20260908.html`, `entry/entry.index.20260906.html`, `networks/networks.index.20260813.html`, `office/office.index.20260815.html`, `pickers/address_picker.20260729.html`, `places/places.index.20260906.html`, `qbe/qbe.20260827.html`, `status/status.index.20260816.html` and `texts/texts.index.20260815.html`.  Diffing one against its live sibling shows it is genuinely older: the 20260906 copy of the Entry page has no `chkUseXY` control, which the shipped page has.

#### Impact

Small but not nil.  It makes the released tree ambiguous about which template is current, it puts pre-release working state in users' hands, and it is the kind of slip that eventually ships a stale file *as* the live one.  Here it also shows up as three test failures, because the suite enumerates the pages and buttons it finds in the build rather than a list of its own.

#### Steps to reproduce

1. List the archive's contents: 7z l CBDB-Desktop_20260908.7z
2. Note the ten Templates/ members whose names carry a date.
3. Diff any one of them against index.html in the same directory.

#### Suggested fix

Build the distribution from a clean export rather than from the working directory, or exclude `*.<date>.html` when packaging.  The backups themselves are useful; they just belong in version control rather than in the release.

#### Where it lives in the build

- `Templates/pickers/address_picker.20260729.html`
- `Templates/qbe/qbe.20260827.html`
- `Templates/entry/entry.index.20260906.html`

#### Demonstrated by

- 4 × failed: `test_distribution_ships_the_expected_pieces`, `test_the_distribution_ships_no_dated_working_copies`, `test_every_disabled_control_has_a_declared_precondition`, `test_every_page_has_the_buttons_it_shipped_with`

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

That stages the archive, launches the shipped binary against a private copy of the shipped database, runs 877 tests, and rewrites these files. The suite never writes to the reference copy of `Data/CBDB.db` — every test runs against a per-session copy, so a run leaves the distribution exactly as it found it.

The test that demonstrates each issue is named under it. To run just one:

```powershell
python -m pytest tests -k test_searching_people_by_name_finds_them -v
```


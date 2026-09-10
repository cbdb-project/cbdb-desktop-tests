# CBDB-Desktop — Issues Report

_A respectful summary of issues uncovered during automated regression testing._

_Build under test: CBDB-Desktop_20260908.7z_

_Generated 2026-09-10 06:16 UTC from a run of 1166 tests (370s)._

Dear maintainer,

Below is a summary of the issues we uncovered while building an automated regression-test suite for CBDB-Desktop. We hope this report is useful as you continue your wonderful stewardship of this dataset, and we sincerely thank you for the immense work that has gone into building it.

Most of the issues below were found by launching the shipped `cbdb.exe` and driving its own HTTP endpoints against the shipped database; the rest were found by reading the shipped page templates, Go sources and release archive, which is the honest way to describe a defect that needs no query to demonstrate. Either way, nothing here re-implements the application's logic, so what is described is what the released program does. The band on each issue is a kind as much as a rank: P0 to P2 run from worse to less bad, but P3 onwards name categories -- packaging, data integrity, a feature no page can reach -- so a P5 is not milder than a P3, and the text printed beside each band says what it means. Each entry includes a short description, the measurement that establishes it, step-by-step reproduction, and a suggested fix.

We have not tried to set your priorities: the bands describe what we measured, not what your users are asking for, and you are far better placed than we are to judge which of these matter. Several are silent -- the application gives a wrong or partial answer with no error shown -- and we have said so plainly where that is the case, because it is the kind of thing that is easy to miss and hard to notice later. Nothing here needs to be answered today.

## How this run went

| outcome | count |
| --- | --- |
| passed | 944 |
| failed | 95 |
| xfailed (a known defect, still present) | 3 |
| skipped | 124 |

Of the 95 failures, **91** are the tests that demonstrate the issues below -- they are how those issues are established, and they will pass again when the issues are fixed.  The remaining **4** are accounted for underneath, so that a reader does not have to reconcile these numbers against the list of issues and find that they do not add up.

**4 failure(s) in this run are not yet classified.**  They are not among the issues below and they are not one of our known coverage gaps, which means this run found something nobody has looked at yet.  Each may turn out to be a defect worth filing or a problem with the check itself; please read them rather than trusting this list to be complete.

| Check | What it reported |
| --- | --- |
| `test_a_filter_the_places_handler_offers_has_a_control_that_can_set_it` | the Places page hard-codes filterBac: false and offers no control that can change it, so the BAC filter PlaceQueryParams declares and places_form_backend.go honours cannot be switched on by any user o |
| `test_the_place_search_helper_finds_the_places_the_table_holds` | /api/networks/place-search?q=Zhou returned 200 and an empty list; 3692 rows of ADDR_CODES carry that word in their name. c_admin_type is varchar(255) holding text and the handler scans it into an int |
| `test_the_committed_report_still_says_what_the_registry_says` | reports/CBDB_Desktop_Issues_EN.md no longer says what the registry says -- the registry was edited after the report was generated, or the report was edited by hand. Missing: ['CBDB-D-015.title', 'CBD |
| `test_the_committed_report_still_says_what_the_registry_says` | reports/CBDB_Desktop_Issues_ZH-Hant.md no longer says what the registry says -- the registry was edited after the report was generated, or the report was edited by hand. Missing: ['CBDB-D-015.title', |

## What the suite covers

| Area | Tests | What it checks |
| --- | --- | --- |
| The distribution itself | 59 | That the tree under test really is the shipped archive, file by file |
| The application process | 13 | That the shipped binary starts, serves, and releases its database |
| Every registered route | 17 | All 141 routes read out of the shipped Go source, driven for real |
| Passing a result from one form to another | 18 | The stored-person list: what one form stores, another recalls |
| Each page against its own handler | 13 | Whether the two halves of a form agree about the request and the reply -- a control the handler never reads, a reply the page cannot read, a capability with no way in |
| The code and address lists | 41 | The dropdowns each form offers before a query is run |
| The Query Builder | 51 | Its whitelist, the SQL it shows the user, and its guards |
| The six single-query forms | 51 | Entry, office, status, texts, associations, places — queries and exports |
| The forms that remember | 17 | Kinship, networks, association pairs, group data — working lists |
| Index-address rankings | 12 | The only endpoints that rewrite CBDB data rather than scratch |
| Every filter, on inputs read from the data | 254 | One query per populated combination the shipped database has, plus every switch turned both ways |
| Every export button | 498 | All 45 file-producing endpoints pressed, and the files they return read back |
| The pages in a real browser | 7 | That every page loads without throwing, and that a control waiting on the user un-greys when they do it |
| Two tabs at once | 3 | Whether one query can replace what another was about to export |
| The working tables | 7 | Which form owns which scratch table, read out of the shipped Go |
| This run's own coverage | 5 | That every endpoint the shipped pages can reach was actually requested by this run |
| What was agreed to leave alone | 28 | That every waived outcome still names a check this run has, and that nothing else in the suite tolerates a failure |
| This report's own sources | 49 | That every issue below still cites real code, in both languages |
| This report itself | 23 | That it is reproducible from the run above, invents no issue, drops none, and hides nothing that was waived |
| every test in this run | 1166 |  |

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
| CBDB-D-008 | P0 | CONFIRMED | The Networks page drops the four year fields its dynasty filter is built on, and a two-dynasty span collapses to a single person |
| CBDB-D-010 | P0 | CONFIRMED | Three controls the user can set change nothing: the Association Pairs KML checkbox, and Networks' Max Loops and Include ID |
| CBDB-D-012 | P0 | CONFIRMED | "Select All Filtered" returns the first hundred addresses and reports them as the whole filter |
| CBDB-D-013 | P0 | CONFIRMED | Recall on the Association Pairs page fills the pair with two people nothing chose, and says nothing about the rest of the stored list |
| CBDB-D-015 | P0 | CONFIRMED | A person imported twice is counted twice, queried twice, and written twice into six of the seven Networks exports |
| CBDB-D-016 | P0 | CONFIRMED | Association Pairs reports how many ids were in the file, not how many people it loaded |
| CBDB-D-004 | P2 | CONFIRMED | Three of the Networks form's four network exports answer HTTP 500 for every input: they select a column their own scratch table does not have |
| CBDB-D-005 | P2 | CONFIRMED | The Associations form's Neo4j export answers HTTP 500 whenever the result has an address: a text column is scanned into an integer |
| CBDB-D-006 | P2 | CONFIRMED | The Query Builder offers 30 columns that the shipped views expose under a different name, and every one of them gives the user a server error |
| CBDB-D-009 | P2 | CONFIRMED | Four Association Pairs export buttons report "Unknown error" on exports that succeeded |
| CBDB-D-007 | P3 | CONFIRMED | The distribution ships ten dated working copies of its own templates |
| CBDB-D-014 | P3 | CONFIRMED | The front page's Users Guide link is a 404: the PDF is not in the distribution |
| CBDB-D-011 | P5 | CONFIRMED | Five shipped capabilities have no way in: Group Data's KML exports, Association Pairs' KML writer, two autocomplete endpoints, and the Places ASCII encoding |

## Table of contents

- [CBDB-D-001 — Both KML exports write an XML declaration that is never closed, so no reader accepts the file](#cbdb-d-001--both-kml-exports-write-an-xml-declaration-that-is-never-closed-so-no-reader-accepts-the-file)
- [CBDB-D-002 — The Places page lets a user switch every category off, and then answers with the Biography rows they excluded](#cbdb-d-002--the-places-page-lets-a-user-switch-every-category-off-and-then-answers-with-the-biography-rows-they-excluded)
- [CBDB-D-003 — Twenty-two export buttons ask the browser to save several files at once, and twenty-one of them report every file as saved when only the first arrived](#cbdb-d-003--twenty-two-export-buttons-ask-the-browser-to-save-several-files-at-once-and-twenty-one-of-them-report-every-file-as-saved-when-only-the-first-arrived)
- [CBDB-D-008 — The Networks page drops the four year fields its dynasty filter is built on, and a two-dynasty span collapses to a single person](#cbdb-d-008--the-networks-page-drops-the-four-year-fields-its-dynasty-filter-is-built-on-and-a-two-dynasty-span-collapses-to-a-single-person)
- [CBDB-D-010 — Three controls the user can set change nothing: the Association Pairs KML checkbox, and Networks' Max Loops and Include ID](#cbdb-d-010--three-controls-the-user-can-set-change-nothing-the-association-pairs-kml-checkbox-and-networks-max-loops-and-include-id)
- [CBDB-D-012 — "Select All Filtered" returns the first hundred addresses and reports them as the whole filter](#cbdb-d-012--select-all-filtered-returns-the-first-hundred-addresses-and-reports-them-as-the-whole-filter)
- [CBDB-D-013 — Recall on the Association Pairs page fills the pair with two people nothing chose, and says nothing about the rest of the stored list](#cbdb-d-013--recall-on-the-association-pairs-page-fills-the-pair-with-two-people-nothing-chose-and-says-nothing-about-the-rest-of-the-stored-list)
- [CBDB-D-015 — A person imported twice is counted twice, queried twice, and written twice into six of the seven Networks exports](#cbdb-d-015--a-person-imported-twice-is-counted-twice-queried-twice-and-written-twice-into-six-of-the-seven-networks-exports)
- [CBDB-D-016 — Association Pairs reports how many ids were in the file, not how many people it loaded](#cbdb-d-016--association-pairs-reports-how-many-ids-were-in-the-file-not-how-many-people-it-loaded)
- [CBDB-D-004 — Three of the Networks form's four network exports answer HTTP 500 for every input: they select a column their own scratch table does not have](#cbdb-d-004--three-of-the-networks-forms-four-network-exports-answer-http-500-for-every-input-they-select-a-column-their-own-scratch-table-does-not-have)
- [CBDB-D-005 — The Associations form's Neo4j export answers HTTP 500 whenever the result has an address: a text column is scanned into an integer](#cbdb-d-005--the-associations-forms-neo4j-export-answers-http-500-whenever-the-result-has-an-address-a-text-column-is-scanned-into-an-integer)
- [CBDB-D-006 — The Query Builder offers 30 columns that the shipped views expose under a different name, and every one of them gives the user a server error](#cbdb-d-006--the-query-builder-offers-30-columns-that-the-shipped-views-expose-under-a-different-name-and-every-one-of-them-gives-the-user-a-server-error)
- [CBDB-D-009 — Four Association Pairs export buttons report "Unknown error" on exports that succeeded](#cbdb-d-009--four-association-pairs-export-buttons-report-unknown-error-on-exports-that-succeeded)
- [CBDB-D-007 — The distribution ships ten dated working copies of its own templates](#cbdb-d-007--the-distribution-ships-ten-dated-working-copies-of-its-own-templates)
- [CBDB-D-014 — The front page's Users Guide link is a 404: the PDF is not in the distribution](#cbdb-d-014--the-front-pages-users-guide-link-is-a-404-the-pdf-is-not-in-the-distribution)
- [CBDB-D-011 — Five shipped capabilities have no way in: Group Data's KML exports, Association Pairs' KML writer, two autocomplete endpoints, and the Places ASCII encoding](#cbdb-d-011--five-shipped-capabilities-have-no-way-in-group-datas-kml-exports-association-pairs-kml-writer-two-autocomplete-endpoints-and-the-places-ascii-encoding)
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

## CBDB-D-008 — The Networks page drops the four year fields its dynasty filter is built on, and a two-dynasty span collapses to a single person

**Affected area:** Networks: dynasty range

**Severity:** P0 — Silent wrong answer — the application returns wrong or empty results, or produces a file nothing can read, with no error shown to the user.

**Where it comes from:** `software` — In the application: cbdb.exe, its Go sources, its page templates, or the database builder's logic.  Fixed by the CBDB-Desktop developers.

**Status in this run:** CONFIRMED

#### Description

`buildDynastyConditions` filters on the *years* a dynasty spans, not on its code: `DYNASTIES_1.c_end > FromDynastyBegin` and `DYNASTIES_1.c_start < ToDynastyEnd`.  The page computes those four numbers when the dynasty picker returns -- `gFromDynastyBegin` and friends -- and then builds `const params={...}` without them, so the handler reads all four as 0.  Three user-visible consequences follow, and there is no fourth way to choose a dynasty on this page: every dynasty choice goes through this one path.

#### Evidence

Driven against person 1762 at depth 1, all four kinship limits at 1, counting distinct people in `nodeRecords`, with the two dynasties and their year bounds read out of `DYNASTIES` rather than hand-picked -- Song (960-1279) to Western Xia (1032-1227):  no dynasty filter, 441; one dynasty, 429; **From only, 439** -- `c_end > 0` holds for 80 of the 85 rows in `DYNASTIES`, so the filter the user asked for is very nearly a no-op, and the two people it does drop are the measurable trace of that; **two dynasties, 1** -- `c_start < 0` is true of five dynasties out of eighty-five, so the answer collapses with no message; **All Dynasties, HTTP 500** `Database error: no such column: DYNASTIES_1.c_end` -- the page's own button sets both codes to a `-2` sentinel that slips past the handler's "neither boundary set" guard and builds a condition on a table the chosen FROM clause never joined.  The decisive comparison is the last: sending the identical request **with** the four year fields the page computed gives 433, so the handler is right and the page is what is broken.  The build contains its own control -- the Association Pairs page solves the same problem correctly, sending `allDynasties: true` as a boolean instead of an out-of-band code, and sending both year bounds with each dynasty into nil-able `*int` fields that can tell "unset" from "0".  The pattern that works is one form away.

#### Impact

A researcher who narrows a network to a span of two dynasties gets one person back and no indication that anything went wrong; the natural reading is that the data is thin, and the result is publishable-looking and false.  From-only returns 439 of the 441 people an unfiltered query returns, so the filter the user set is very nearly not applied at all.  All Dynasties fails outright.

#### Steps to reproduce

1. Open Networks, choose a person with a large network (1762).
2. Set From Dynasty = Song and To Dynasty = Western Xia, then press Run Query.
3. Note the result: one node, no message.
4. Press All Dynasties and Run Query: HTTP 500.

#### Suggested fix

Send `fromDynastyBegin`, `fromDynastyEnd`, `toDynastyBegin` and `toDynastyEnd` in `params`; the page already has all four in globals, and the Association Pairs page shows the shape.  Separately, give the handler an explicit `-2` case, or stop the page sending a sentinel the handler does not define -- and make the guard reject an unrecognised code rather than build SQL from it.

#### Where it lives in the build

- `Code/networks_form_query.go:buildDynastyConditions`
- `Templates/networks/index.html:704`
- `Templates/networks/index.html:1054`

#### Demonstrated by

- 1 × failed: `test_the_networks_page_sends_the_dynasty_span_its_handler_needs`

## CBDB-D-010 — Three controls the user can set change nothing: the Association Pairs KML checkbox, and Networks' Max Loops and Include ID

**Affected area:** Association Pairs, Networks: dead controls

**Severity:** P0 — Silent wrong answer — the application returns wrong or empty results, or produces a file nothing can read, with no error shown to the user.

**Where it comes from:** `software` — In the application: cbdb.exe, its Go sources, its page templates, or the database builder's logic.  Fixed by the CBDB-Desktop developers.

**Status in this run:** CONFIRMED

#### Description

Each is read from the DOM, sent in the request, and then not read.  The Association Pairs page posts `useKML`; `AssocPairsExportParams` declares `format`, `network` and `people`, so the key never binds and `handleExportGIS` branches on a `format` this page never sends.  The Networks page posts `maxLoop` and `includeID`; `NetworkQuery` declares `MaxLoop` and `IncludeID`, and no line of Go under `Code/` mentions either identifier again.

#### Evidence

**KML.**  The page's request to `export-gis` carries `['useKML']`; the handler's params struct declares `['format', 'network', 'people']`.  Driven both ways, the reply names `assocpairs_network.tsv` either way, so `assocWriteKML` is unreachable from the only page that offers it (CBDB-D-011 counts it among the capabilities with no way in).

**Max Loops and Include ID.**  Surveying every `json:`-tagged field in `Code/*.go` against every mention of its name turns up exactly three whose identifier occurs once, in its own declaration.  Two are `NetworkQuery.MaxLoop` and `NetworkQuery.IncludeID`, and the Networks page sends both -- `maxLoop: parseInt(document.getElementById('txt-max-loop').value,10)||2` and `includeID: document.getElementById('chk-include-id').checked`.  The third, `KinRecord.KinRel0`, is a response field no page reads: inert rather than a defect, and named here so the count above can be checked.

#### Impact

Max Loops is a numeric input offered between 1 and 10 whose traversal depth is fixed by something else, and Include ID in Output changes no output: both are settings a user can change, and changing them changes nothing.  The KML checkbox is the same fault with a further consequence -- because it never binds, the KML writer behind it can only be reached by calling the endpoint directly.  On this build a user does not even get the TSV: CBDB-D-009 means the page reports "GIS export error: Unknown error" and downloads nothing.  Fixing that envelope alone would hand the user a TSV with the KML box ticked, which is why the two belong in the same change.

#### Steps to reproduce

1. Open Networks, set Max Loops to 1, run a query, then set it to 10 and run again.  Compare the two result sets.
2. Tick Include ID in Output, export, and compare the columns.
3. For KML, read the request the Association Pairs page builds: it posts useKML, and AssocPairsExportParams has no such field.

#### Suggested fix

For KML: send `format` from this page as its siblings do, or have the handler read `useKML` -- and fix CBDB-D-009 in the same change, or the box still appears to do nothing.  For the two Networks fields: wire them to the traversal and the writers, or remove the controls.  A control that is present and inert is worse than one that is absent, because a user who sets it believes the result reflects it.

#### Where it lives in the build

- `Code/assocpairs_form_backend.go:handleExportGIS`
- `Code/networks_form_backend.go:NetworkQuery`
- `Templates/association_pairs/index.html:173`
- `Templates/networks/index.html:1071`

#### Demonstrated by

- 2 × failed: `test_the_assocpairs_kml_checkbox_changes_what_comes_back`, `test_a_field_the_json_declares_is_a_field_the_program_uses`

## CBDB-D-012 — "Select All Filtered" returns the first hundred addresses and reports them as the whole filter

**Affected area:** Address picker

**Severity:** P0 — Silent wrong answer — the application returns wrong or empty results, or produces a file nothing can read, with no error shown to the user.

**Where it comes from:** `software` — In the application: cbdb.exe, its Go sources, its page templates, or the database builder's logic.  Fixed by the CBDB-Desktop developers.

**Status in this run:** CONFIRMED

#### Description

The picker keeps `filteredAddresses` (its own comment: *"full match set (all rows matching the filter)"*) and `renderedAddresses = filteredAddresses.slice(0, MAX_RENDER)` with `MAX_RENDER = 100`.  Only the rendered slice becomes `<option>` elements.  `selectAllFiltered()` walks `sel.options`, and `sendResult` walks `sel.options` again to build what it hands back -- so on a filter matching more than a hundred addresses the button returns the first hundred, and returns them with `isSelectAllFiltered: true` plus the filter text, which every host page reads as "the user chose the whole filter".

#### Evidence

Read from `Templates/pickers/address_picker.html`, with each function's body taken by brace matching rather than by pattern, so that what is attributed to `selectAllFiltered` is what that function does: the cap (`const MAX_RENDER = 100`), the slice that applies it, and both functions walking `sel.options`.  The button's own comment says it *"selects every visible (filtered) item"*.  The status bar does say *"Showing first 100 of N -- refine your search"*, but the button is not disabled in that state and nothing in the result it sends records the truncation.  The scale is measurable, and has to be measured against the right population: the picker does not filter `ADDR_CODES`.  It filters `allAddresses`, loaded once from `/api/addresses` -- 37,118 rows, because that endpoint joins `ADDR_BELONGS_DATA` and each row carries its own year range -- and it matches case-insensitively on the pinyin name.  Filtered the way the page filters, "Zhou" gives 5,373 rows, "Xian" 7,166 and "Fu" 2,007, so the button returns 1.9%, 1.4% and 5.0% of what the user asked for.

#### Impact

The query then runs on a hundred addresses while the page displays the filter text, so the result looks like an answer about the whole filter and is an answer about a small fraction of it.  Which hundred depends on the order the list arrived in, which is not the user's choice and is not shown.

#### Steps to reproduce

1. Open any form that offers an address picker and open it.
2. Filter on "Zhou" so the status bar reads "Showing first 100 of 5373".
3. Press Select All Filtered, and count the addresses the host page received: 100.

#### Suggested fix

Build the result from `filteredAddresses` rather than from `sel.options`; the full set is already in memory and the render cap exists only to keep the `<select>` manageable.  If sending thousands of ids is not wanted, send the filter itself and let the host page resolve it -- but do not send a hundred rows labelled as the filter.

#### Where it lives in the build

- `Templates/pickers/address_picker.html:118`
- `Templates/pickers/address_picker.html:223`
- `Templates/pickers/address_picker.html:344`
- `Templates/pickers/address_picker.html:381`

#### Demonstrated by

- 1 × failed: `test_select_all_filtered_selects_every_address_the_filter_matched`
- 1 × passed: `test_the_function_body_reader_stops_at_the_function`

## CBDB-D-013 — Recall on the Association Pairs page fills the pair with two people nothing chose, and says nothing about the rest of the stored list

**Affected area:** Association Pairs: recall-ids

**Severity:** P0 — Silent wrong answer — the application returns wrong or empty results, or produces a file nothing can read, with no error shown to the user.

**Where it comes from:** `software` — In the application: cbdb.exe, its Go sources, its page templates, or the database builder's logic.  Fixed by the CBDB-Desktop developers.

**Status in this run:** CONFIRMED

#### Description

`handleRecallIDs` answers *GET /api/assocpairs/recall-ids* with `SELECT s.c_personid, ... FROM ZZ_STORE_PERSON_ID s LEFT JOIN BIOG_MAIN bm ON ... LIMIT 2` and no `ORDER BY`.  `ZZ_STORE_PERSON_ID` is the application's stored-person list -- the one channel by which a result travels between forms -- and it can hold any number of people.  Two come back, chosen by the query plan.

#### Evidence

Driven, not merely read, and counted through a second endpoint rather than through the reply to the write.  Storing five people via `POST /api/assocpairs/store-ids` answers `{"count":5}`, but that number is `len(req.PersonIDs)` -- the request handed back, which would say five whatever the table did.  `POST /api/networks/recall-person-ids`, which reads the same global `ZZ_STORE_PERSON_ID`, independently answers `{"count":5}`; `GET /api/assocpairs/recall-ids` then returns two, the same two on three consecutive calls.  So *two of the five come back and the other three are neither returned nor mentioned* -- measured against the list as another form still sees it, which is also what shows those three are still stored rather than lost.

The handler's own comment says *"Returns people stored in ZZ_STORE_PERSON_ID (up to 2 for pair mode)"*, so the cap is deliberate and this report does not ask for it to be lifted.  What is not deliberate is the rest: nothing orders the rows, so which two is left to the query plan, and nothing tells the user that the other three are still in the list, waiting, and not in front of them.  That the choice is unspecified rather than unstable is what the missing `ORDER BY` establishes: SQLite is not obliged to keep returning these two, and nothing in the code asks it to.  Every `SELECT` in `Code/*.go` that caps its rows without ordering them was surveyed; the build has three, and the other two are correlated subqueries in `kinrelReductionUpdate` keyed on `kr.c_kinrel_target` with `c_required = 1`, where the predicate already selects the intended row.

#### Impact

A user who sent five people to this form from another one, then pressed Recall, is working on two of them and is not told which two or why.  The pair is filled and the page looks correct.  Nothing is destroyed -- the stored list still holds all five, and another form still reads them back -- so this is a failure to report rather than data loss; but the two the user ends up working on were chosen by the query plan, and because nothing orders the rows it is not a choice they could learn to predict either.

#### Steps to reproduce

1. POST /api/assocpairs/store-ids with five personIds; the reply says count: 5.
2. GET /api/assocpairs/recall-ids: two people come back.
3. On the page, the same sequence fills the pair and reports nothing about the other three.

#### Suggested fix

Decide what Recall means when the stored list holds more than two, and say it in the code: an `ORDER BY` that names the intended rows (insertion order if the table records it, `c_personid` otherwise), and a message when rows are dropped.  Better still, let the user pick which two.

#### Where it lives in the build

- `Code/assocpairs_form_backend.go:handleRecallIDs`

#### Demonstrated by

- 1 × failed: `test_a_query_that_keeps_only_some_rows_says_which_ones`

## CBDB-D-015 — A person imported twice is counted twice, queried twice, and written twice into six of the seven Networks exports

**Affected area:** Networks: the imported working list

**Severity:** P0 — Silent wrong answer — the application returns wrong or empty results, or produces a file nothing can read, with no error shown to the user.

**Where it comes from:** `software` — In the application: cbdb.exe, its Go sources, its page templates, or the database builder's logic.  Fixed by the CBDB-Desktop developers.

**Status in this run:** CONFIRMED

#### Description

`networks_form_backend.go` declares its working list as `CREATE TABLE IF NOT EXISTS ZZ_SIP_NETWORK (... UNIQUE (c_person_id))` and inserts into it with `INSERT OR IGNORE` in all four places that fill it.  The table ships in the database without that constraint, and `CREATE TABLE IF NOT EXISTS` against a table that already exists is a no-op -- so the guard never runs, and the `OR IGNORE` has nothing to ignore.  A repeated id is ordinary input: the page builds its list from a file one line at a time and does not deduplicate.

#### Evidence

Driven through the shipped binary.  Importing person 0 once: `/api/networks/person-count` says 1, and the smallest query returns 19 rows for 19 distinct people.  Importing the same person *twice*: person-count says **2 for one person**, and the same query returns **20 rows for 19 distinct people**, person 0 appearing twice.  The duplicate is not confined to the working list: `networks_form_query.go` seeds `ZZ_SP_NETWORK` from it with no `DISTINCT`, and the result rows and six of the seven export writers read `ZZ_SP_NETWORK` with no `DISTINCT` either -- Export Results, GIS, KML, Gephi/GUESS, UCINet and Pajek.  The seventh, Neo4j, is unaffected, and how it escapes is the fix in miniature: it collects its people into `ZZ_SCRATCH_P_TEXT` with `INSERT OR IGNORE ... SELECT DISTINCT`, and that table *does* ship with the unique constraint its declaration asks for.

The constraint is missing in the shipped table and not in the Go: `PRAGMA index_list` finds no unique index on `ZZ_SIP_NETWORK`, `ZZ_SIP_KINSHIP` or `ZZ_SIP_ASSOC_PAIR`, while `ZZ_SCRATCH_ADDR` -- declared the same way, in the same file -- does have one.  So this is an omission in the database builder rather than a decision.  Kinship and Association Pairs escape the visible half by luck: their working lists duplicate too, and their person-counts are wrong in the same way, but their queries deduplicate downstream.

#### Impact

A network is a count of people and a set of relationships, and both are wrong.  The person appears twice in the result grid, twice in Export Results, twice in the GIS table, twice in the KML, and twice in the Gephi, UCINet and Pajek files -- where a duplicated vertex is not merely cosmetic, since the network measures those tools compute are defined over the vertex set.  Only the Neo4j bundle comes out right.  The points-per-coordinate figure the GIS and KML exports carry counts rows, so it inflates too.  Nothing on screen marks any of it, and the input that causes it -- a list file with a repeated id -- is one a historian would have no reason to think twice about.

#### Steps to reproduce

1. Open Networks and import a list file with the same person id on two lines (or POST /api/networks/import-people with {"personIds": [1, 1]}).
2. Read the count under the list: it says 2 for one person.
3. Run the query and look for that person in the results grid: two rows.
4. Save to GIS and count the person's rows in the file: two.  Save to Neo4j and count them there: one.

#### Suggested fix

Add `UNIQUE (c_person_id)` to `ZZ_SIP_NETWORK` in `CBDB_AdditionalTablesViewsIndices.sql`, which is what actually creates it; the Go already declares the constraint and every insert into that table is already `INSERT OR IGNORE`, so nothing else has to change.

**Only that table.**  `ZZ_SIP_KINSHIP` and `ZZ_SIP_ASSOC_PAIR` duplicate in the same way and their person-counts are wrong in the same way, but neither declares the constraint and neither inserts with `OR IGNORE` -- so adding `UNIQUE` to them would turn a silent duplicate into a failed insert, which is a worse outcome and a decision for whoever owns those forms.  If their counts are to be fixed, `SELECT DISTINCT` at the point of insert is the safe way.  Worth a look in the other direction too: every `CREATE TABLE IF NOT EXISTS` in the Go describes a table that already ships, so any constraint declared there and missing from the builder is inert in exactly this way.

#### Where it lives in the build

- `Code/networks_form_backend.go:384`
- `Code/networks_form_backend.go:handleExportNeo4j`
- `CBDBSetUpCode/CBDB_AdditionalTablesViewsIndices.sql`
- `Code/networks_form_query.go`

#### Demonstrated by

- 2 × failed: `test_importing_the_same_person_twice_imports_one_person`, `test_a_uniqueness_a_form_declares_is_one_the_table_enforces`

## CBDB-D-016 — Association Pairs reports how many ids were in the file, not how many people it loaded

**Affected area:** Association Pairs: import-list

**Severity:** P0 — Silent wrong answer — the application returns wrong or empty results, or produces a file nothing can read, with no error shown to the user.

**Where it comes from:** `software` — In the application: cbdb.exe, its Go sources, its page templates, or the database builder's logic.  Fixed by the CBDB-Desktop developers.

**Status in this run:** CONFIRMED

#### Description

`handleImportList` inserts by joining `BIOG_MAIN`, so an id the database does not have inserts nothing -- and then answers `"count": len(req.PersonIDs)`, the request handed back.  The page prints that number: *"Imported N person IDs"*, *"N people loaded"*.

#### Evidence

Three ids sent, of which two exist in `BIOG_MAIN` and one is past the largest id the table holds.  Association Pairs answers `{"count": 3}` and the following query returns exactly what sending only the two real ids returns.

The oracle is the three sibling endpoints that load the same kind of list, because they disagree with it and with nothing else: Kinship answers `{"count": 2, "errorCount": 1}`, Networks reads `COUNT(*)` back out of its own table and answers `{"count": 2}`, and Group Data answers `{"count": 2}` with the rows it found.  Three of the four report what happened; the fourth reports what it was asked to do.

#### Impact

A historian importing an id list from an older CBDB release, or from a colleague's spreadsheet, is told the whole list loaded and then queries a subset.  Nothing later contradicts it: the result simply has fewer people in it than the source list had, which looks like a finding about the data rather than about the import.

#### Steps to reproduce

1. On Look At Association Pairs, import a list containing two real person ids and one that does not exist.
2. The page says three people were loaded.
3. Run the query: the answer is the one for two people.
4. Send the same three ids to /api/kinship/import-people for comparison: it answers count 2, errorCount 1.

#### Suggested fix

Report what was inserted, not what was asked for.  The three sibling handlers show two ways: count `RowsAffected` as Kinship does and return an `errorCount` beside it, or read `COUNT(*)` back as Networks does.  Kinship's shape is the more useful of the two, because a user who is told one id failed can go and look for it.

#### Where it lives in the build

- `Code/assocpairs_form_backend.go:handleImportList`
- `Templates/association_pairs/index.html:513`

#### Demonstrated by

- 1 × failed: `test_a_list_loader_reports_how_many_people_it_loaded`

## CBDB-D-004 — Three of the Networks form's four network exports answer HTTP 500 for every input: they select a column their own scratch table does not have

**Affected area:** Networks form: Pajek, Gephi/GUESS and UCINet exports

**Severity:** P2 — Visible failure — the user's action fails with an error they see.  Usually a server error; sometimes a page that reports failure on a request that in fact succeeded.  The band is about what the user is shown, not about which half of the application went wrong.

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

- 34 × failed: `test_an_export_produces_a_well_formed_file[entry:kml]`, `test_an_export_produces_a_well_formed_file[places:kml]`, `test_an_export_produces_a_well_formed_file[associations:neo4j]`, `test_an_export_produces_a_well_formed_file[networks:pajek]` (+30)
- 308 × passed: `test_an_export_produces_a_well_formed_file[entry:results]`, `test_an_export_produces_a_well_formed_file[entry:gis]`, `test_an_export_produces_a_well_formed_file[entry:neo4j]`, `test_an_export_produces_a_well_formed_file[entry:save]` (+304)
- 91 × skipped: `test_an_export_describes_the_people_the_grid_did[entry:kml]`, `test_an_export_describes_the_people_the_grid_did[entry:save]`, `test_an_export_describes_the_people_the_grid_did[office:gis]`, `test_an_export_describes_the_people_the_grid_did[office:gis-people]` (+87)

## CBDB-D-005 — The Associations form's Neo4j export answers HTTP 500 whenever the result has an address: a text column is scanned into an integer

**Affected area:** Associations form, Neo4j export

**Severity:** P2 — Visible failure — the user's action fails with an error they see.  Usually a server error; sometimes a page that reports failure on a request that in fact succeeded.  The band is about what the user is shown, not about which half of the application went wrong.

**Where it comes from:** `software` — In the application: cbdb.exe, its Go sources, its page templates, or the database builder's logic.  Fixed by the CBDB-Desktop developers.

**Status in this run:** CONFIRMED

#### Description

The export reads `ADDR_CODES.c_admin_type` into a Go struct field declared `AdminType int`.  That column is text: every one of its 30,100 rows holds a string such as "Xian" or "Zhou".  The scan therefore fails on the first address row and the whole export returns HTTP 500.

#### Evidence

The endpoint answers `500 Neo4j export error: scan addrRow: sql: Scan error on column index 3, name "admin_type": converting driver.Value type string ("Xian") to a int: invalid syntax`.  The shipped schema declares the column `varchar(255)`, and a read-only count over the shipped database finds all 30,100 values are of type text, the commonest being "Xian" (13,687 rows).  So a rebuild of the data would not change it: the declared type in the Go struct is wrong.

**The same column is read the same wrong way a second time**, in `networks_form_backend.go:handlePlaceSearch`, and the two are worth reading together because they fail differently.  There the scan sits in a row loop whose error arm is `if err := rows.Scan(...); err != nil { continue }`, so every row is discarded along with the reason it failed, and the handler encodes the empty slice with a 200: `GET /api/networks/place-search?q=Zhou` returns `[]` where 20 rows were asked for and 5,136 match the predicate, so not one row of the table can be found through it.  That instance is latent in this build, because no page calls the endpoint (CBDB-D-011) -- which is why it is recorded here rather than filed as something users can see.  Both sites need the same small change -- scan the column into the string it already is -- and the `continue` is the more dangerous half: it turns a schema mismatch into a search that succeeds and finds nothing.

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

- 34 × failed: `test_an_export_produces_a_well_formed_file[entry:kml]`, `test_an_export_produces_a_well_formed_file[places:kml]`, `test_an_export_produces_a_well_formed_file[associations:neo4j]`, `test_an_export_produces_a_well_formed_file[networks:pajek]` (+30)
- 279 × passed: `test_an_export_produces_a_well_formed_file[entry:results]`, `test_an_export_produces_a_well_formed_file[entry:gis]`, `test_an_export_produces_a_well_formed_file[entry:neo4j]`, `test_an_export_produces_a_well_formed_file[entry:save]` (+275)
- 109 × skipped: `test_an_export_describes_the_people_the_grid_did[entry:kml]`, `test_an_export_describes_the_people_the_grid_did[entry:save]`, `test_an_export_describes_the_people_the_grid_did[office:gis]`, `test_an_export_describes_the_people_the_grid_did[office:gis-people]` (+105)

## CBDB-D-006 — The Query Builder offers 30 columns that the shipped views expose under a different name, and every one of them gives the user a server error

**Affected area:** The generated Query Builder schema, and the view definitions in CBDBSetUpCode

**Severity:** P2 — Visible failure — the user's action fails with an error they see.  Usually a server error; sometimes a page that reports failure on a request that in fact succeeded.  The band is about what the user is shown, not about which half of the application went wrong.

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

## CBDB-D-009 — Four Association Pairs export buttons report "Unknown error" on exports that succeeded

**Affected area:** Association Pairs: exports

**Severity:** P2 — Visible failure — the user's action fails with an error they see.  Usually a server error; sometimes a page that reports failure on a request that in fact succeeded.  The band is about what the user is shown, not about which half of the application went wrong.

**Where it comes from:** `software` — In the application: cbdb.exe, its Go sources, its page templates, or the database builder's logic.  Fixed by the CBDB-Desktop developers.

**Status in this run:** CONFIRMED

#### Description

`exportGIS`, `exportSNA` and `exportNeo4j` in the page share one recipe: post, then `if (j.status !== 'ok') throw new Error(j.status || 'Unknown error')`, then `j.files.forEach(...)`.  Two of the four handlers answer `{"status":"ok","files":[...]}`, which that reads.  `handleExportGIS` and `handleExportSNA` answer `{"url":...,"name":...}` instead, so `undefined !== 'ok'` is true and the page throws -- on an HTTP 200 whose body holds the finished file, correctly built.

#### Evidence

Posting the smallest body each handler's own guard admits (`people` with one row): `/api/assocpairs/export-gis` and `/api/assocpairs/export-sna` both answer 200 with keys `['name', 'url']`; `/api/assocpairs/export-neo4j`, in the same file, answers with `status` and `files`, as does `export-results` beside it.  So this is a disagreement inside one file rather than a convention imposed from outside.  Four buttons are affected: Save to GIS, and the three SNA formats (Pajek, Gephi, UCINet) that share `export-sna`.

This reverses a judgement recorded in this project's own AGENTS.md, which listed the inconsistent export envelopes as *not* a defect "because no user can see it".  That was decided by reading the handlers, which agree with each other; no page had been read.  On this form a user does see it, and AGENTS.md is amended in the same change.

#### Impact

Four of this form's six export buttons cannot be used.  The message names no cause, so a user has nothing to act on, and because the server side is in fact correct the fault is invisible to anything that tests handlers alone.

#### Steps to reproduce

1. Open Look At Association Pairs and run any query.
2. Press Save to GIS.  The page shows "GIS export error: Unknown error" and downloads nothing.
3. Watch the same request in the browser's network panel: 200, with the file base64-encoded in the body.

#### Suggested fix

Make the two odd handlers answer in the shape the page reads -- `{"status":"ok","files":[{name,url}]}` -- which is what their two siblings already do.  Changing the page instead would mean three call sites diverging again the next time an export is added.

#### Where it lives in the build

- `Code/assocpairs_form_backend.go:handleExportGIS`
- `Code/assocpairs_form_backend.go:handleExportSNA`
- `Templates/association_pairs/index.html:960`
- `Templates/association_pairs/index.html:1002`

#### Demonstrated by

- 2 × failed: `test_an_assocpairs_export_answers_in_the_envelope_its_page_reads[export-gis]`, `test_an_assocpairs_export_answers_in_the_envelope_its_page_reads[export-sna]`
- 1 × passed: `test_an_assocpairs_export_answers_in_the_envelope_its_page_reads[export-neo4j]`

## CBDB-D-007 — The distribution ships ten dated working copies of its own templates

**Affected area:** Packaging: Templates/

**Severity:** P3 — Packaging — the released files contain something they should not, or lack something they should.

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

## CBDB-D-014 — The front page's Users Guide link is a 404: the PDF is not in the distribution

**Affected area:** Packaging: Static/

**Severity:** P3 — Packaging — the released files contain something they should not, or lack something they should.

**Where it comes from:** `release` — In how this particular release was assembled -- a working copy shipped in place of a freshly built one, a file that was not regenerated.  Fixed in the release process by whoever builds the distribution.

**Status in this run:** CONFIRMED

#### Description

`Templates/navigation/index.html` offers a *Users Guide* link pointing at `../../static/CBDB_UserGuide.pdf`.  `Static/` ships one file, `cbdb_styles.css`.

#### Evidence

Every same-origin link on the navigation page was followed.  All resolve except this one, which answers HTTP 404.  `Static/` is the only file-served directory in the build, so there is nowhere else the file could be reached from.

The distribution settles for itself which side this belongs on.  `The directory structure for CBDB-Desktop.txt`, shipped at the root of the archive, lists `PDF files: CBDB-Desktop\Static\xxx.pdf` at its last line, and `cbdb_navigation_backend.go:62` describes the directory it serves as "Static files (PDF user guide, images, etc.)".  So the layout expects PDFs in `Static/`, the code that serves it expects the guide among them, the template links to it accordingly, and what is missing is the file: this is the packaging step, not a template pointing somewhere it never should have.

#### Impact

The documentation the application points its users at is not there.  This is a desktop distribution aimed at researchers rather than developers, and the guide is one of only two links the front page offers outside the forms themselves.

#### Steps to reproduce

1. Start the application and open the front page.
2. Press Users Guide.
3. Or: 7z l CBDB-Desktop_20260908.7z | findstr Static

#### Suggested fix

Ship `CBDB_UserGuide.pdf` in `Static/`, which is where the distribution's own layout document says PDFs go.  If the guide lives elsewhere -- a project website -- make the link point there and say so.

#### Where it lives in the build

- `Templates/navigation/index.html:75`
- `The directory structure for CBDB-Desktop.txt:82`
- `Code/cbdb_navigation_backend.go:62`
- `Static/`

#### Demonstrated by

- 1 × failed: `test_every_link_the_navigation_offers_resolves`

## CBDB-D-011 — Five shipped capabilities have no way in: Group Data's KML exports, Association Pairs' KML writer, two autocomplete endpoints, and the Places ASCII encoding

**Affected area:** Group Data, Association Pairs, Networks, Places: unreachable features

**Severity:** P5 — Unreachable feature — the application implements something no page can ask for.  The band says only that no user can get to it.  Whether the code behind it is correct is a separate question with a separate answer, so an unreachable feature that is also broken is recorded in both places rather than argued about in one.

**Where it comes from:** `software` — In the application: cbdb.exe, its Go sources, its page templates, or the database builder's logic.  Fixed by the CBDB-Desktop developers.

**Status in this run:** CONFIRMED

#### Description

Five pieces of finished work that no user of this build can reach.  `groupdata_form_backend.go` has six `req.Format == "kml"` branches and `Templates/group_data/index.html` does not contain the letters `kml` at all.  Association Pairs has the letters and not the binding: its checkbox sends a key the handler does not read (CBDB-D-010), so `assocWriteKML` is unreachable too.  `/api/networks/place-search` and `/api/networks/person-search` are routed, implemented, and called by no template.  And `handleExportPajek` accepts `encoding: "ascii"` while all five of the Places page's export calls send the literal `'unicode'`.

#### Evidence

Every backend that branches on `"kml"` was checked against its own page for any mention of `kml` in any form -- a control id, a value, a comment.  Nine backends carry such a branch and eight pass that test; `group_data` is the one that fails it outright, with six branches and no mention.  Association Pairs passes it only on the literal `chkKML` in its markup, which CBDB-D-010 shows is a mention and not a route: hence five here rather than four.

For the endpoints, every `/api/` route in `Code/*.go` was matched against every live template under `Templates/`, **pickers included** -- which matters, since both endpoints name a picker as their caller, and a survey reading only the form pages would have got the right answer for the wrong reason.  Exactly two routes have no caller, and they are those two.

For the encoding, `grep` finds `encoding: 'unicode'` at five call sites in `Templates/places/index.html` (656, 683, 747, 764, 781) and the string `ascii` in no template at all.  Driving the endpoint directly shows the branch works and one thing in it does not: with `encoding="ascii"` the labels do switch to pinyin -- past the mark the file holds 0 byte values above 0x7F against 18 in the unicode one -- yet `handleExportPajek` prepends `utf8BOM` unconditionally, so the file it names `network_ascii.net` opens with `EF BB BF`.  That last part is a defect in unreachable code, recorded here for whoever connects the control rather than filed as something users can see.

#### Impact

The GIS output a Group Data user can actually obtain is tab-separated only, so `groupWriteKMLStatus`, `groupWriteKMLOffice` and `groupWriteKMLOfficePeople` are code no user can run, and the mapping workflow the other forms offer is missing there.  Neither picker has the autocomplete that was written for it.  The Places export offers one encoding of the two it implements.  None of this puts a wrong answer on screen -- it is finished work that shipped without its last connection.  Whether the unreachable code is itself correct is a separate question, and twice here the answer is no: the BOM above, and the scan bug in `place-search` recorded under CBDB-D-005.  That is the cost of an unreachable feature -- nothing exercises it, so nothing tells anyone it is broken.

#### Steps to reproduce

1. Open Group Data and look for a KML option beside any GIS export.  There is none; searching the page for "kml" finds nothing either.
2. Search every file under Templates/ for "place-search" and "person-search": no hits outside the Go source.
3. Search Templates/places/index.html for "encoding": five hits, all the literal 'unicode'.

#### Suggested fix

Add the format control to the Group Data GIS exports, matching the other forms; make the Association Pairs checkbox bind (CBDB-D-010); give the Places export an encoding control, or drop the branch.  For the two search endpoints, either wire the pickers to them or remove the routes.  Whichever way each one goes, decide it deliberately: an endpoint nothing calls is a maintenance cost with no user, and two of these have been carrying bugs nobody could have hit.

#### Where it lives in the build

- `Code/groupdata_form_backend.go:1084`
- `Templates/group_data/index.html`
- `Code/networks_form_backend.go:handlePlaceSearch`
- `Code/networks_form_backend.go:handlePersonSearch`
- `Code/places_form_backend.go:handleExportPajek`
- `Templates/places/index.html:656`

#### Demonstrated by

- 3 × failed: `test_an_export_named_ascii_contains_ascii`, `test_a_kml_the_handler_can_write_is_a_kml_the_page_can_ask_for`, `test_every_api_endpoint_the_build_routes_has_a_page_that_calls_it`

## Severity legend

- **P0** — Silent wrong answer — the application returns wrong or empty results, or produces a file nothing can read, with no error shown to the user.
- **P1** — Destructive write — a request rewrites stored data that it should not, and the previous state cannot be recovered.
- **P2** — Visible failure — the user's action fails with an error they see.  Usually a server error; sometimes a page that reports failure on a request that in fact succeeded.  The band is about what the user is shown, not about which half of the application went wrong.
- **P3** — Packaging — the released files contain something they should not, or lack something they should.
- **P4** — Data integrity — a reference in the shipped data does not resolve.
- **P5** — Unreachable feature — the application implements something no page can ask for.  The band says only that no user can get to it.  Whether the code behind it is correct is a separate question with a separate answer, so an unreachable feature that is also broken is recorded in both places rather than argued about in one.

## Reproducing this report

The whole report is generated from one command. With the distribution zip named in `.env` as `CBDB_DESKTOP_ZIP`:

```powershell
.\run_tests.ps1
```

That stages the archive, launches the shipped binary against a private copy of the shipped database, runs 1166 tests, and rewrites these files. The suite never writes to the reference copy of `Data/CBDB.db` — every test runs against a per-session copy, so a run leaves the distribution exactly as it found it.

The test that demonstrates each issue is named under it. To run just one:

```powershell
python -m pytest tests -k test_searching_people_by_name_finds_them -v
```


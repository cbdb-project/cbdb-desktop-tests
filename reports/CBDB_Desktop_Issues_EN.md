# CBDB-Desktop — Issues Report

_A respectful summary of issues uncovered during automated regression testing._

_Build under test: CBDB-Desktop_20260915_2.7z_

_Generated 2026-09-16 02:45 UTC from a run of 1382 tests (427s)._

Dear maintainer,

Below is a summary of the issues we uncovered while building an automated regression-test suite for CBDB-Desktop. We hope this report is useful as you continue your wonderful stewardship of this dataset, and we sincerely thank you for the immense work that has gone into building it.

Most of the issues below were found by launching the shipped `cbdb.exe` and driving its own HTTP endpoints against the shipped database; the rest were found by reading the shipped page templates, Go sources and release archive, which is the honest way to describe a defect that needs no query to demonstrate. Either way, nothing here re-implements the application's logic, so what is described is what the released program does. The band on each issue is a kind as much as a rank: P0 to P2 run from worse to less bad, but P3 onwards name categories -- packaging, data integrity, a feature no page can reach -- so a P5 is not milder than a P3, and the text printed beside each band says what it means. Each entry includes a short description, the measurement that establishes it, step-by-step reproduction, and a suggested fix.

We have not tried to set your priorities: the bands describe what we measured, not what your users are asking for, and you are far better placed than we are to judge which of these matter. Several are silent -- the application gives a wrong or partial answer with no error shown -- and we have said so plainly where that is the case, because it is the kind of thing that is easy to miss and hard to notice later. Nothing here needs to be answered today.

## How this run went

| outcome | count |
| --- | --- |
| passed | 1182 |
| failed | 16 |
| xfailed (a known defect, still present) | 3 |
| skipped | 181 |

Of the 16 failures, **14** are the tests that demonstrate the issues below -- they are how those issues are established, and they will pass again when the issues are fixed.  The remaining **2** are accounted for underneath, so that a reader does not have to reconcile these numbers against the list of issues and find that they do not add up.

**2** of them are this suite's own business rather than defects in the distribution: something the interface offers that we have not yet driven, or a piece of our own bookkeeping that has slipped.  Ours to close, not yours.

| Check | What it reported about us |
| --- | --- |
| `test_the_committed_report_still_says_what_the_registry_says` | 7 findings are filed in the registry but reports/CBDB_Desktop_Issues_EN.md is not in the tree. The report is the deliverable of a round, not an optional by-product. Write it: python reports\generate |
| `test_the_committed_report_still_says_what_the_registry_says` | 7 findings are filed in the registry but reports/CBDB_Desktop_Issues_ZH-Hant.md is not in the tree. The report is the deliverable of a round, not an optional by-product. Write it: python reports\gen |

## What the suite covers

| Area | Tests | What it checks |
| --- | --- | --- |
| The distribution itself | 63 | That the tree under test really is the shipped archive, file by file |
| The application process | 13 | That the shipped binary starts, serves, and releases its database |
| Every registered route | 17 | All 142 routes read out of the shipped Go source, driven for real |
| Passing a result from one form to another | 22 | The stored-person list: what one form stores, another recalls |
| Each page against its own handler | 16 | Whether the two halves of a form agree about the request and the reply -- a control the handler never reads, a reply the page cannot read, a capability with no way in |
| Whether each page's JavaScript still parses | 30 | A form keeps all its behaviour in one inline script, so a syntax error in it leaves every control on the page dead while the page still loads -- read out of the shipped templates, with no browser |
| The code and address lists | 42 | The dropdowns each form offers before a query is run |
| The Group Data form | 7 | Its five section switches driven one at a time, and what it answers when every one of them is off |
| The Entry and Status pickers | 4 | Their type trees: that every type offered has codes somewhere beneath it, and that every parent named is a type that exists |
| The Networks form's filters | 11 | Its kin and non-kin switches, the sex filter, and each of the twenty-seven association categories that select anything, driven on its own |
| The Query Builder's grid, cell by cell | 34 | Its eleven operators, four aggregates, sort row, join kinds and what it does with a cell it cannot parse |
| The Query Builder | 21 | Its whitelist, the SQL it shows the user, and its guards |
| The six single-query forms | 51 | Entry, office, status, texts, associations, places — queries and exports |
| The forms that remember | 18 | Kinship, networks, association pairs, group data — working lists |
| Index-address rankings | 12 | The only endpoints that rewrite CBDB data rather than scratch |
| Every filter, on inputs read from the data | 420 | One query per populated combination the shipped database has, plus every switch turned both ways |
| Every export button | 498 | All 45 file-producing endpoints pressed, and the files they return read back |
| The pages in a real browser | 11 | That every page loads without throwing, and that a control waiting on the user un-greys when they do it |
| Two tabs at once | 3 | Whether one query can replace what another was about to export |
| The working tables | 7 | Which form owns which scratch table, read out of the shipped Go |
| This run's own coverage | 5 | That every endpoint the shipped pages can reach was actually requested by this run |
| What was agreed to leave alone | 28 | That every waived outcome still names a check this run has, and that nothing else in the suite tolerates a failure |
| This report's own sources | 22 | That every issue below still cites real code, in both languages |
| This report itself | 27 | That it is reproducible from the run above, invents no issue, drops none, and hides nothing that was waived |
| every test in this run | 1382 |  |

### What this round did not reach

The table above counts what was checked; it is not a list of what the application does.  A feature can appear in it because one narrow thing about it is checked -- that a button un-greys when it should, say -- while what the button produces is never read.  Where that is true of something this build added, the issue below says so in its own words.  Read a row as *this much was checked*, and an absent row as nothing at all.

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
| CBDB-D-001 | P0 | CONFIRMED | Three of the thirteen forms are completely inert: a stray quote leaves their whole script unparsed |
| CBDB-D-002 | P0 | CONFIRMED | The Association Pairs dynasty filter does nothing: the shared picker changed shape and this one page did not |
| CBDB-D-004 | P0 | CONFIRMED | Looking a person up in the Browser silently replaces the Kinship form's result, and the export then describes two people at once |
| CBDB-D-005 | P0 | CONFIRMED | Every multi-file export reports the server's file count as though the browser had saved them all |
| CBDB-D-006 | P0 | CONFIRMED | The ASCII Pajek export begins with a UTF-8 byte order mark |
| CBDB-D-007 | P3 | CONFIRMED | A uniqueness the Kinship code declares is missing from the shipped table |
| CBDB-D-003 | P5 | CONFIRMED | Three forms accept an unfiltered query and give no way to ask for one -- and two of them offer the button for it |

## Table of contents

- [CBDB-D-001 — Three of the thirteen forms are completely inert: a stray quote leaves their whole script unparsed](#cbdb-d-001--three-of-the-thirteen-forms-are-completely-inert-a-stray-quote-leaves-their-whole-script-unparsed)
- [CBDB-D-002 — The Association Pairs dynasty filter does nothing: the shared picker changed shape and this one page did not](#cbdb-d-002--the-association-pairs-dynasty-filter-does-nothing-the-shared-picker-changed-shape-and-this-one-page-did-not)
- [CBDB-D-004 — Looking a person up in the Browser silently replaces the Kinship form's result, and the export then describes two people at once](#cbdb-d-004--looking-a-person-up-in-the-browser-silently-replaces-the-kinship-forms-result-and-the-export-then-describes-two-people-at-once)
- [CBDB-D-005 — Every multi-file export reports the server's file count as though the browser had saved them all](#cbdb-d-005--every-multi-file-export-reports-the-servers-file-count-as-though-the-browser-had-saved-them-all)
- [CBDB-D-006 — The ASCII Pajek export begins with a UTF-8 byte order mark](#cbdb-d-006--the-ascii-pajek-export-begins-with-a-utf-8-byte-order-mark)
- [CBDB-D-007 — A uniqueness the Kinship code declares is missing from the shipped table](#cbdb-d-007--a-uniqueness-the-kinship-code-declares-is-missing-from-the-shipped-table)
- [CBDB-D-003 — Three forms accept an unfiltered query and give no way to ask for one -- and two of them offer the button for it](#cbdb-d-003--three-forms-accept-an-unfiltered-query-and-give-no-way-to-ask-for-one----and-two-of-them-offer-the-button-for-it)
- [Severity legend](#severity-legend)
- [Reproducing this report](#reproducing-this-report)

## CBDB-D-001 — Three of the thirteen forms are completely inert: a stray quote leaves their whole script unparsed

**Affected area:** Association Pairs, Entry and Group Data pages (/LookAtAssociationPairs, /LookAtEntry, /LookAtGroupData)

**Severity:** P0 — Silent wrong answer — the application returns wrong or empty results, or produces a file nothing can read, with no error shown to the user.

**Where it comes from:** `software` — In the application: cbdb.exe, its Go sources, its page templates, or the database builder's logic.  Fixed by the CBDB-Desktop developers.

**Status in this run:** CONFIRMED

#### Description

Nine lines across the three pages open a JavaScript string that the line never closes.  All nine are the same shape -- a sentence about downloads that was rewritten across the build, where the opening quote of the second fragment went missing and a stray `'"` was left at the end.  A JavaScript string may not span a line, so each of these is a syntax error; and because every one of these pages keeps the whole of its behaviour in a single inline `<script>`, the browser discards the entire block.  Every function the page declares then does not exist.  The page still loads, still draws every control, and does nothing at all.

#### Evidence

Measured in a real Chromium: of the functions each page's own buttons are wired to, 0 of 14 exist on Association Pairs, 0 of 15 on Entry and 0 of 10 on Group Data, while the other ten pages lose none.  Every enabled button fires and raises `ReferenceError: <name> is not defined`; the twenty controls that ship disabled can never be un-greyed, because the code that would enable them is gone.  The server answers HTTP 200 for all three and serves the broken text verbatim.  The same sentence is written correctly twelve times across seven other pages, which is what identifies this as a botched search-and-replace rather than a change anyone chose; the previous build's three pages parse clean.

#### Impact

A historian who opens any of these three forms can do nothing on it.  Run Query does not run, the pickers do not open, the language buttons do not switch, the tabs do not change, and every export button is dead -- with no error message anywhere, because the function that would show one was discarded with the rest.  Twenty endpoints are reachable from no page at all as a result.  It is filed P0 under the band's own words -- the application returns empty results with no error shown to the user -- and the reason for saying so plainly is that nothing is computed wrongly here: nothing is computed at all.

#### Steps to reproduce

1. Open the Entry form (/LookAtEntry).
2. Press any button -- Choose an entry code, Run Query, or one of the language buttons.
3. Nothing happens, and no message appears.
4. Open the browser's developer console: it shows 'SyntaxError: missing ) after argument list' from the page itself, and a ReferenceError for each button pressed.
5. The same on /LookAtAssociationPairs and /LookAtGroupData.

#### Suggested fix

One character per line, nine lines.  Each reads

    showSuccess('X: ' + n +  file(s) offered for download — check each Save dialog.'");

and should read

    showSuccess('X: ' + n + ' file(s) offered for download — check each Save dialog.');

-- the opening quote restored before ` file(s)`, and the trailing `'");` reduced to `');`.  Worth running the three pages through `node --check` afterwards, or simply opening each one and watching the browser console: a page whose script parsed logs nothing.

#### Where it lives in the build

- `Templates/association_pairs/index.html:968`
- `Templates/association_pairs/index.html:993`
- `Templates/association_pairs/index.html:1014`
- `Templates/association_pairs/index.html:1037`
- `Templates/entry/index.html:1063`
- `Templates/entry/index.html:1088`
- `Templates/group_data/index.html:923`
- `Templates/group_data/index.html:956`
- `Templates/group_data/index.html:982`

#### Demonstrated by

- 5 × failed: `test_every_page_script_closes_every_string_it_opens`, `test_every_page_the_build_serves_loads_without_throwing`, `test_every_button_is_wired_to_a_function_that_exists`, `test_a_control_is_enabled_once_its_precondition_is_met[entry-btnExportResults+btnGIS+btnNeo4j+btnStoreIDs]` (+1)
- 5 × passed: `test_a_control_is_enabled_once_its_precondition_is_met[networks-btn-run+chk-kin-param]`, `test_a_control_is_enabled_once_its_precondition_is_met[associations-btnRunQuery]`, `test_a_control_is_enabled_once_its_precondition_is_met[kinship-btn-export-results+btn-tab+btn-kml+btn-neo4j+btn-pajek+btn-gephi+btn-uci-net]`, `test_a_control_is_enabled_once_its_precondition_is_met[office-btnRunQuery]` (+1)

## CBDB-D-002 — The Association Pairs dynasty filter does nothing: the shared picker changed shape and this one page did not

**Affected area:** Association Pairs page and its query (/LookAtAssociationPairs, POST /api/assocpairs/query)

**Severity:** P0 — Silent wrong answer — the application returns wrong or empty results, or produces a file nothing can read, with no error shown to the user.

**Where it comes from:** `software` — In the application: cbdb.exe, its Go sources, its page templates, or the database builder's logic.  Fixed by the CBDB-Desktop developers.

**Status in this run:** CONFIRMED

#### Description

`dynasty_picker.html` became multi-select in this build.  It now hands its opener a single array of chosen dynasties -- `handleDynastySelection(records)`.  Seven of the eight pages that open it were rewritten to match.  Association Pairs was not: it still declares `handleDynastySelection(dynasty, type)`, so it stores the whole array where it expects one dynasty, reads `.code` off it and gets `undefined`, and `JSON.stringify` then drops the key from the request altogether.  The query runs with no dynasty filter, and the form's own From and To boxes stay blank, so the page does not even show what was chosen.

#### Evidence

Read from both sides of the contract in the shipped pages: the picker calls its opener with one argument, and Association Pairs is the only page of the eight that declares two.  The handler half agrees -- of the eight request structs in the build that decode a dynasty, `AssocPairsQueryParams` is the only one that does not declare `dynastyCodes`, and it still declares the retired From/To pair.  Two of the six fields it does declare, `fromDynastyEnd` and `toDynastyBegin`, are read by no line of Go in the build, so they would be inert even if the page spoke the right vocabulary.

#### Impact

A researcher who restricts an Association Pairs query to one or more dynasties gets the unrestricted answer.  Nothing warns them: the popup closes normally, the query runs, and the result looks like a result.  This is the shape of error that is hardest to catch downstream, because the numbers are plausible and only wrong.

#### Steps to reproduce

1. Open the Association Pairs form and pick two people.
2. Set the year filter to Dynasty and press Pick beside From.
3. Choose a dynasty in the popup and press Select.
4. The From boxes stay blank -- the first sign.
5. Press Run Query and compare the row count with the same query run with no dynasty filter at all: they are the same.

#### Suggested fix

Bring the page to the contract the other seven already use: declare `handleDynastySelection(records)`, keep the array in a `selectedDynasties` variable, and send `dynastyCodes: selectedDynasties.map(d => d.code)`.  On the handler side, replace the six From/To fields on `AssocPairsQueryParams` with `DynastyCodes []int `json:"dynastyCodes"`` and the year-overlap branch with the `c_dy IN (...)` the other seven forms now use.  The Office, Status and Texts backends are the model.

#### Where it lives in the build

- `Templates/pickers/dynasty_picker.html:139`
- `Templates/association_pairs/index.html:624`
- `Templates/association_pairs/index.html:700`
- `Code/assocpairs_form_backend.go:49`

#### Demonstrated by

- 3 × failed: `test_a_field_the_json_declares_is_a_field_the_program_uses`, `test_every_page_accepts_the_arguments_its_picker_hands_it`, `test_every_form_reads_the_dynasty_choice_the_picker_now_sends`

## CBDB-D-004 — Looking a person up in the Browser silently replaces the Kinship form's result, and the export then describes two people at once

**Affected area:** Kinship form and the Browser (GET /api/browser/person/{id}/kinship, POST /api/kinship/export-results)

**Severity:** P0 — Silent wrong answer — the application returns wrong or empty results, or produces a file nothing can read, with no error shown to the user.

**Where it comes from:** `software` — In the application: cbdb.exe, its Go sources, its page templates, or the database builder's logic.  Fixed by the CBDB-Desktop developers.

**Status in this run:** CONFIRMED

#### Description

`handleGetKinship` begins by deleting `ZZ_KIN_LIST`, `ZZ_KIN_LIST_TMP`, `ZZ_SCRATCH_KIN` and `ZZ_SCRATCH_KINNET` -- which is where the Kinship form's query put its answer.  So looking somebody up in the Browser, or pressing Export Profile there, overwrites a result the Kinship form is still displaying.  The form's Export Query Results then reads those tables and gets the new person's traversal, while `KinshipPeople.tsv` comes from `ZZ_SP_KINSHIP`, which that handler does not touch, and still describes the old one.

#### Evidence

Driven: with a Kinship result for person 1 on screen, a GET of person 10's kinship changes what Export Query Results returns -- `EgoRelativeKinship.tsv` goes from 920 to 9,795 characters and `KinshipNetwork.tsv` from 1,067 to 295 -- while `KinshipPeople.tsv` comes back byte for byte the same.  Neither page says anything.  Re-running the Kinship query returns 6 records, so the result was replaced rather than damaged: the user is exporting somebody else's traversal.  The form's five other exports build their rows from what the page posts to them and are unaffected; this is Export Query Results alone.

#### Impact

The three files in one download describe two different people, and nothing in them says so.  A researcher who runs a kinship query, glances somebody up in the Browser and then exports -- an ordinary sequence -- gets a bundle whose parts disagree.  Because the file names and the row shapes are unchanged, the mistake survives into whatever is built from them.

#### Steps to reproduce

1. On the Kinship form, choose a person and run a query.
2. Press Export Query Results and keep the three files.
3. Open the Browser, look up a different person, and open their Kinship tab -- or simply press Export Profile.
4. Return to the Kinship form, which still shows the first result, and export again: EgoRelativeKinship and KinshipNetwork now describe the person who was looked up, while KinshipPeople still describes the first one.

#### Suggested fix

Either give the Browser its own scratch tables for the kinship tab, as the 2026-09-07 build did for the forms that used to share theirs, or have it build the tab's answer without truncating anything.  If the sharing has to stay, the Kinship page at least needs to know its displayed result is no longer the one in the tables -- and Export Query Results should refuse rather than export a mixture.

#### Where it lives in the build

- `Code/browser_form_backend.go:2104`
- `Code/kinship_form_backend.go:153`
- `Templates/browser/index.html:182`

#### Demonstrated by

- 1 × failed: `test_looking_a_person_up_does_not_discard_a_kinship_result`
- 1 × passed: `test_export_profile_loads_the_kinship_tab_it_lists`

## CBDB-D-005 — Every multi-file export reports the server's file count as though the browser had saved them all

**Affected area:** Ten pages, 22 export handlers

**Severity:** P0 — Silent wrong answer — the application returns wrong or empty results, or produces a file nothing can read, with no error shown to the user.

**Where it comes from:** `software` — In the application: cbdb.exe, its Go sources, its page templates, or the database builder's logic.  Fixed by the CBDB-Desktop developers.

**Status in this run:** CONFIRMED

#### Description

Every export that produces more than one file delivers them by calling a download helper once per element of a list, from a single click.  The page then reports the count the *server* returned -- '3 file(s) offered for download' -- without asking the browser what it accepted.  Chrome treats several downloads from one gesture as a permission to be granted, and a user who does not grant it gets fewer files than the page says they got.

#### Evidence

Read from the pages: 22 handlers across ten pages loop a list and trigger one download per element, and 21 of them then print the server's count as a success message.  The counting half is confirmed under automation; the blocking half is not reproducible there and is not claimed to be -- a headless browser with `accept_downloads` accepts every file, so Chrome's multiple-download permission never engages.  What the browser test does establish is that the page never consults the browser at all: the number it prints comes only from the response.

#### Impact

A user can be told an export succeeded with three files when one arrived.  The missing files are not named and no error is shown, so the gap is discovered later, in the tool that needed them -- if at all.

#### Steps to reproduce

1. Open any form with a Neo4j export and run a query.
2. Press Export Neo4j CSVs.
3. The page reports the number of files the server built.
4. In a browser that has not been given the multiple-download permission for this site, fewer files are saved, and the message does not change.

#### Suggested fix

Report what was delivered rather than what was built.  The download helper can resolve per file, and the message can then name the count the browser accepted, or say plainly that several files are on their way and a prompt may appear.  Offering one archive per export instead of N files would remove the permission question altogether.

#### Where it lives in the build

- `Templates/office/index.html:847`
- `Templates/status/index.html:797`
- `Templates/texts/index.html:833`

#### Demonstrated by

- 2 × failed: `test_no_page_asks_the_browser_for_more_than_one_download`, `test_an_export_does_not_claim_more_files_than_it_delivered`

## CBDB-D-006 — The ASCII Pajek export begins with a UTF-8 byte order mark

**Affected area:** Networks form, Pajek export (POST /api/networks/export-pajek)

**Severity:** P0 — Silent wrong answer — the application returns wrong or empty results, or produces a file nothing can read, with no error shown to the user.

**Where it comes from:** `software` — In the application: cbdb.exe, its Go sources, its page templates, or the database builder's logic.  Fixed by the CBDB-Desktop developers.

**Status in this run:** CONFIRMED

#### Description

`handleExportPajek` writes `utf8BOM` before anything else, whatever encoding was asked for.  The body honours the request -- the ASCII file's labels really are pinyin -- but the first three bytes of a file a user asked to be ASCII are a UTF-8 marker.

#### Evidence

`network_ascii.net` and `network_UTF8.net`, built from the same records in the same run, both open with the same three bytes.  Past the mark the ASCII file holds 0 byte values above 0x7F against 18 in the Unicode one, so the encoding flag reached the body and was ignored only for the mark.

#### Impact

A Pajek reader that takes the file as plain ASCII meets three unexpected bytes before `*Vertices`, which is either a parse error or a first line that reads as rubbish, depending on the tool.  The user asked for ASCII precisely to avoid that class of problem.

#### Steps to reproduce

1. Run a Networks query.
2. Export to Pajek with the ASCII (pinyin) option.
3. Open the resulting .net file in a hex viewer: it begins EF BB BF, then `*Vertices`.

#### Suggested fix

Write the mark only on the Unicode path, as the same file's Neo4j writers already do -- they omit it deliberately, because `LOAD CSV` reads it as part of the first column's name.  The condition is already available at that point in `handleExportPajek`.

#### Where it lives in the build

- `Code/networks_form_backend.go:2413`

#### Demonstrated by

- 1 × failed: `test_an_export_named_ascii_contains_ascii`

## CBDB-D-007 — A uniqueness the Kinship code declares is missing from the shipped table

**Affected area:** ZZ_SP_KINSHIP, built by CBDB_AdditionalTablesViewsIndices.sql

**Severity:** P3 — Packaging — the released files contain something they should not, or lack something they should.

**Where it comes from:** `release` — In how this particular release was assembled -- a working copy shipped in place of a freshly built one, a file that was not regenerated.  Fixed in the release process by whoever builds the distribution.

**Status in this run:** CONFIRMED

#### Description

The Kinship backend declares `ZZ_SP_KINSHIP` with `UNIQUE(c_person_id)` and inserts into it with `INSERT OR IGNORE`.  The table that actually ships is created by the database builder without that constraint, and `CREATE TABLE IF NOT EXISTS` makes the Go declaration a no-op, so the `OR IGNORE` ignores nothing.

#### Evidence

Compared the `UNIQUE(...)` declarations in the shipped Go against `sqlite_master` and `PRAGMA index_list` for each table.  Five constraints are declared; four are enforced by the shipped database and this one is not.  `ZZ_SIP_NETWORK` was in the same state in the previous build and has been repaired in this one, in the same file, which is what shows the omission is an oversight rather than a policy.

#### Impact

No user-visible consequence was found: importing a duplicate inflates the Kinship person-count, which reads a different table, but the query deduplicates downstream and the exported people are correct.  It is recorded because the declaration is untrue, and the next query written against this table will inherit the assumption that it is true.

#### Steps to reproduce

1. Open Data/cbdb.db and run: SELECT sql FROM sqlite_master WHERE name = 'ZZ_SP_KINSHIP';
2. The definition has no UNIQUE clause.
3. Compare with the CREATE TABLE in the Kinship backend, which declares one.

#### Suggested fix

Add `UNIQUE(c_person_id)` to the `ZZ_SP_KINSHIP` definition in CBDB_AdditionalTablesViewsIndices.sql, exactly as `ZZ_SIP_NETWORK` received it in this build.

#### Where it lives in the build

- `Code/kinship_form_backend.go:153`
- `CBDBSetUpCode/CBDB_AdditionalTablesViewsIndices.sql`

#### Demonstrated by

- 1 × failed: `test_a_uniqueness_a_form_declares_is_one_the_table_enforces`

## CBDB-D-003 — Three forms accept an unfiltered query and give no way to ask for one -- and two of them offer the button for it

**Affected area:** Office, Associations and Status pages (/LookAtOffice, /LookAtAssociations, /LookAtStatus)

**Severity:** P5 — Unreachable feature — the application implements something no page can ask for.  The band says only that no user can get to it.  Whether the code behind it is correct is a separate question with a separate answer, so an unreachable feature that is also broken is recorded in both places rather than argued about in one.

**Where it comes from:** `software` — In the application: cbdb.exe, its Go sources, its page templates, or the database builder's logic.  Fixed by the CBDB-Desktop developers.

**Status in this run:** CONFIRMED

#### Description

Each of these three handlers adds its primary code filter only when the list is non-empty -- `if len(p.OfficeCodes) > 0` -- so an empty list means *every code*, and the Office page's own variable says so: `let _officeCodes = [];   // [] = all offices`.  Each page then greys out Run Query whenever that list is empty, which is exactly the state the handler reads as 'no filter'.  On Office and Associations the button that puts the form into that state -- *All Offices*, and *All* -- calls a clear function that empties the list and re-greys Run Query.  Pressing the control for 'everything' disables the control for 'go'.

#### Evidence

Swept over the build rather than observed on one form: six of the handlers are written to accept an empty primary list, and three of the pages grey Run Query on `.length === 0` -- associations (`assocCodes`), office (`_officeCodes`), status (`selectedStatusCodes`).  The Office case is confirmed end to end in a browser: pick an office and Run Query is enabled; press *All Offices* and it is disabled again, while the same request sent over HTTP with `officeCodes: []` answers 200.  The Associations page has carried this since at least the 2026-09-10 build and its own comment says it copied the Office pattern deliberately.

#### Impact

Three of the six main forms cannot be asked for their unfiltered result.  A researcher who wants every office posting in a place, or every association of a person, or every status in a dynasty, has no way to say so through the page -- and on two of them the button that appears to offer it makes the form less usable rather than more.  The work behind that query is written, tested and reachable over HTTP; only the interface refuses.

#### Steps to reproduce

1. Open the Office form (/LookAtOffice).
2. Press Select Office and choose any office; Run Query becomes available.
3. Press All Offices.
4. Run Query is greyed out again, and there is no way to run the query the button just asked for.
5. On the Associations form the same sequence with Select Associations and the All button does the same thing.

#### Suggested fix

Decide per form what an empty selection means and make the page agree with the handler.  If the unfiltered query is intended -- and the Office page's own comment says it is -- then Run Query should not be gated on the list being non-empty, and the *All* buttons should leave it enabled.  If it is not intended, the handlers should refuse an empty list with a message, the way the Places form now refuses an empty category selection, rather than accepting a request no user can send.

#### Where it lives in the build

- `Templates/office/index.html:343`
- `Templates/office/index.html:357`
- `Code/office_form_backend.go:659`
- `Templates/associations/index.html:304`
- `Templates/status/index.html:474`
- `Code/associations_form_backend.go:534`
- `Code/status_form_backend.go:496`

#### Demonstrated by

- 2 × failed: `test_a_form_that_accepts_an_unfiltered_query_has_a_way_to_ask_for_one`, `test_all_offices_leaves_the_office_form_able_to_query`

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

That stages the archive, launches the shipped binary against a private copy of the shipped database, runs 1382 tests, and rewrites these files. The suite never writes to the reference copy of `Data/CBDB.db` — every test runs against a per-session copy, so a run leaves the distribution exactly as it found it.

The test that demonstrates each issue is named under it. To run just one:

```powershell
python -m pytest tests -k test_searching_people_by_name_finds_them -v
```


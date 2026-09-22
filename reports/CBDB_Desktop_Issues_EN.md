# CBDB-Desktop — Issues Report

_A respectful summary of issues uncovered during automated regression testing._

_Build under test: CBDB-Desktop_20260916_2.7z_

_Generated 2026-09-22 06:21 UTC from a run of 1382 tests (442s)._

Dear maintainer,

Below is a summary of the issues we uncovered while building an automated regression-test suite for CBDB-Desktop. We hope this report is useful as you continue your wonderful stewardship of this dataset, and we sincerely thank you for the immense work that has gone into building it.

Most of the issues below were found by launching the shipped `cbdb.exe` and driving its own HTTP endpoints against the shipped database; the rest were found by reading the shipped page templates, Go sources and release archive, which is the honest way to describe a defect that needs no query to demonstrate. Either way, nothing here re-implements the application's logic, so what is described is what the released program does. The band on each issue is a kind as much as a rank: P0 to P2 run from worse to less bad, but P3 onwards name categories -- packaging, data integrity, a feature no page can reach -- so a P5 is not milder than a P3, and the text printed beside each band says what it means. Each entry includes a short description, the measurement that establishes it, step-by-step reproduction, and a suggested fix.

We have not tried to set your priorities: the bands describe what we measured, not what your users are asking for, and you are far better placed than we are to judge which of these matter. Several are silent -- the application gives a wrong or partial answer with no error shown -- and we have said so plainly where that is the case, because it is the kind of thing that is easy to miss and hard to notice later. Nothing here needs to be answered today.

## How this run went

| outcome | count |
| --- | --- |
| passed | 1188 |
| failed | 10 |
| xfailed (a known defect, still present) | 3 |
| skipped | 181 |

Every one of the 10 failures is a test that demonstrates an issue below.

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
| CBDB-D-001 | P0 | CONFIRMED | The Group Data form is completely inert: three unclosed quotes leave its whole script unparsed |
| CBDB-D-002 | P0 | CONFIRMED | Looking a person up in the Browser silently replaces the Kinship form's result, and the export then describes two people at once |
| CBDB-D-003 | P0 | CONFIRMED | Every multi-file export reports the server's file count as though the browser had saved them all |
| CBDB-D-004 | P0 | CONFIRMED | The ASCII Pajek export begins with a UTF-8 byte order mark |
| CBDB-D-007 | P3 | CONFIRMED | A uniqueness the Kinship code declares is missing from the shipped table |
| CBDB-D-005 | P5 | CONFIRMED | Three forms accept an unfiltered query and give no way to ask for one -- and two of them offer the button for it |
| CBDB-D-006 | P5 | CONFIRMED | Two lookup endpoints were orphaned by the picker rework: implemented, routed, and called by no page |

## Table of contents

- [CBDB-D-001 — The Group Data form is completely inert: three unclosed quotes leave its whole script unparsed](#cbdb-d-001--the-group-data-form-is-completely-inert-three-unclosed-quotes-leave-its-whole-script-unparsed)
- [CBDB-D-002 — Looking a person up in the Browser silently replaces the Kinship form's result, and the export then describes two people at once](#cbdb-d-002--looking-a-person-up-in-the-browser-silently-replaces-the-kinship-forms-result-and-the-export-then-describes-two-people-at-once)
- [CBDB-D-003 — Every multi-file export reports the server's file count as though the browser had saved them all](#cbdb-d-003--every-multi-file-export-reports-the-servers-file-count-as-though-the-browser-had-saved-them-all)
- [CBDB-D-004 — The ASCII Pajek export begins with a UTF-8 byte order mark](#cbdb-d-004--the-ascii-pajek-export-begins-with-a-utf-8-byte-order-mark)
- [CBDB-D-007 — A uniqueness the Kinship code declares is missing from the shipped table](#cbdb-d-007--a-uniqueness-the-kinship-code-declares-is-missing-from-the-shipped-table)
- [CBDB-D-005 — Three forms accept an unfiltered query and give no way to ask for one -- and two of them offer the button for it](#cbdb-d-005--three-forms-accept-an-unfiltered-query-and-give-no-way-to-ask-for-one----and-two-of-them-offer-the-button-for-it)
- [CBDB-D-006 — Two lookup endpoints were orphaned by the picker rework: implemented, routed, and called by no page](#cbdb-d-006--two-lookup-endpoints-were-orphaned-by-the-picker-rework-implemented-routed-and-called-by-no-page)
- [Severity legend](#severity-legend)
- [Reproducing this report](#reproducing-this-report)

## CBDB-D-001 — The Group Data form is completely inert: three unclosed quotes leave its whole script unparsed

**Affected area:** Group Data page (/LookAtGroupData)

**Severity:** P0 — Silent wrong answer — the application returns wrong or empty results, or produces a file nothing can read, with no error shown to the user.

**Where it comes from:** `software` — In the application: cbdb.exe, its Go sources, its page templates, or the database builder's logic.  Fixed by the CBDB-Desktop developers.

**Status in this run:** CONFIRMED

#### Description

Three lines on this page open a JavaScript string that the line never closes.  All three are the same shape -- a sentence about downloads where the opening quote of the second fragment is missing and a stray `'"` was left at the end.  A JavaScript string may not span a line, so each is a syntax error; and because this page keeps the whole of its behaviour in a single inline `<script>`, the browser discards the entire block.  Every function the page declares then does not exist.  The page still loads, still draws every control, and does nothing at all.

The same three lines were among nine across three pages in the 2026-09-15_2 build.  The Association Pairs and Entry pages were repaired in 2026-09-16_2; Group Data was not.

#### Evidence

Measured in a real Chromium: of the ten functions this page's own buttons are wired to, none exists after the page has loaded, while the other fifteen pages lose none.  Every enabled button fires and raises `ReferenceError: <name> is not defined`; the thirteen controls that ship disabled can never be un-greyed, because the code that would enable them is gone.  The page logs `SyntaxError: missing ) after argument list` on load and the server answers HTTP 200, serving the broken text verbatim.  The same sentence is written correctly eighteen times elsewhere in the build, which is what identifies this as an unfinished repair rather than a change anyone chose.

#### Impact

A historian who opens this form can do nothing on it.  Run Query does not run, Import does not import, the language buttons do not switch, the tabs do not change, and every export button is dead -- with no error message anywhere, because the function that would show one was discarded with the rest.  Seven endpoints are reachable from no page at all as a result.  It is filed P0 under the band's own words -- the application returns empty results with no error shown to the user -- and the reason for saying so plainly is that nothing is computed wrongly here: nothing is computed at all.

#### Steps to reproduce

1. Open the Group Data form (/LookAtGroupData).
2. Press any button -- Import, Run Query, or one of the language buttons.
3. Nothing happens, and no message appears.
4. Open the browser's developer console: it shows 'SyntaxError: missing ) after argument list' from the page itself, and a ReferenceError for each button pressed.

#### Suggested fix

One character per line, three lines.  Each reads

    showSuccess('X: ' + (j.files || []).length +  file(s) offered for download — check each Save dialog.'");

and should read

    showSuccess('X: ' + (j.files || []).length + ' file(s) offered for download — check each Save dialog.');

-- the opening quote restored before ` file(s)`, and the trailing `'");` reduced to `');`.  The Entry and Association Pairs pages already carry the repaired form and can be copied from.  Worth running the page through `node --check` afterwards, or opening it and watching the browser console: a page whose script parsed logs nothing.

#### Where it lives in the build

- `Templates/group_data/index.html:923`
- `Templates/group_data/index.html:956`
- `Templates/group_data/index.html:982`

#### Demonstrated by

- 3 × failed: `test_every_page_script_closes_every_string_it_opens`, `test_every_page_the_build_serves_loads_without_throwing`, `test_every_button_is_wired_to_a_function_that_exists`

## CBDB-D-002 — Looking a person up in the Browser silently replaces the Kinship form's result, and the export then describes two people at once

**Affected area:** Kinship form and the Browser's kinship tab

**Severity:** P0 — Silent wrong answer — the application returns wrong or empty results, or produces a file nothing can read, with no error shown to the user.

**Where it comes from:** `software` — In the application: cbdb.exe, its Go sources, its page templates, or the database builder's logic.  Fixed by the CBDB-Desktop developers.

**Status in this run:** CONFIRMED

#### Description

`handleGetKinship` begins by deleting `ZZ_KIN_LIST`, `ZZ_KIN_LIST_TMP`, `ZZ_SCRATCH_KIN` and `ZZ_SCRATCH_KINNET` -- which is where the Kinship form's query put its answer.  So looking somebody up in the Browser, or pressing Export Profile there, overwrites a result the Kinship form is still displaying.  The form's Export Query Results then reads those tables and gets the new person's traversal, while `KinshipPeople.tsv` comes from `ZZ_SP_KINSHIP`, which that handler does not touch, and still describes the old one.

#### Evidence

Driven: with a Kinship result for person 1 on screen, a GET of person 10's kinship changes what Export Query Results returns -- `EgoRelativeKinship.tsv` and `KinshipNetwork.tsv` both come back with different content -- while `KinshipPeople.tsv` comes back byte for byte the same.  Neither page says anything.  Re-running the Kinship query returns its rows, so the result was replaced rather than damaged: the user is exporting somebody else's traversal.  The form's five other exports build their rows from what the page posts to them and are unaffected; this is Export Query Results alone.

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
- `Code/browser_form_backend.go:2117`
- `Templates/browser/index.html:182`

#### Demonstrated by

- 1 × failed: `test_looking_a_person_up_does_not_discard_a_kinship_result`
- 1 × passed: `test_export_profile_loads_the_kinship_tab_it_lists`

## CBDB-D-003 — Every multi-file export reports the server's file count as though the browser had saved them all

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

- `Templates/office/index.html:854`
- `Templates/status/index.html:797`
- `Templates/texts/index.html:833`

#### Demonstrated by

- 1 × failed: `test_no_page_asks_the_browser_for_more_than_one_download`
- 1 × passed: `test_an_export_does_not_claim_more_files_than_it_delivered`

## CBDB-D-004 — The ASCII Pajek export begins with a UTF-8 byte order mark

**Affected area:** Networks form, Pajek export

**Severity:** P0 — Silent wrong answer — the application returns wrong or empty results, or produces a file nothing can read, with no error shown to the user.

**Where it comes from:** `software` — In the application: cbdb.exe, its Go sources, its page templates, or the database builder's logic.  Fixed by the CBDB-Desktop developers.

**Status in this run:** CONFIRMED

#### Description

`handleExportPajek` writes `utf8BOM` before anything else, whatever encoding was asked for.  The body honours the request -- the ASCII file's labels really are pinyin -- but the first three bytes of a file a user asked to be ASCII are a UTF-8 marker.

#### Evidence

`network_ascii.net` and `network_UTF8.net`, built from the same records in the same run, both open with the same three bytes.  Past the mark the ASCII file holds no byte values above 0x7F while the Unicode one holds eighteen, so the encoding flag reached the body and was ignored only for the mark.

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

**Affected area:** The Kinship result scratch table ZZ_SP_KINSHIP, built by the database setup script

**Severity:** P3 — Packaging — the released files contain something they should not, or lack something they should.

**Where it comes from:** `software` — In the application: cbdb.exe, its Go sources, its page templates, or the database builder's logic.  Fixed by the CBDB-Desktop developers.

**Status in this run:** CONFIRMED

#### Description

The Kinship backend declares `ZZ_SP_KINSHIP` with `UNIQUE(c_person_id)` and inserts into it with `INSERT OR IGNORE`.  The table that actually ships is created by the database builder without that constraint, and `CREATE TABLE IF NOT EXISTS` makes the Go declaration a no-op, so the `OR IGNORE` ignores nothing.

#### Evidence

Compared the `UNIQUE(...)` declarations in the shipped Go against `sqlite_master` and `PRAGMA index_list` for each table.  Five constraints are declared; four are enforced by the shipped database and this one is not.  `ZZ_SIP_NETWORK` was in the same state two builds ago and has since been repaired in the same file, which is what shows the omission is an oversight rather than a policy.

Origin is `software`, not `release`, and the deciding experiment is what settles it: the constraint is missing from the *builder's source*, so a clean rebuild from the current CBDB data using this same code reproduces it exactly.  Nothing about how the archive was assembled would have prevented it, and the fix below is a source edit.  The band still reads P3 because that describes the symptom -- a released file lacking something it should have -- while the origin says who fixes it.

#### Impact

No user-visible consequence was found: importing a duplicate inflates the Kinship person-count, which reads a different table, but the query deduplicates downstream and the exported people are correct.  It is recorded because the declaration is untrue, and the next query written against this table will inherit the assumption that it is true.

#### Steps to reproduce

1. Open Data/cbdb.db and run: SELECT sql FROM sqlite_master WHERE name = 'ZZ_SP_KINSHIP';
2. The definition has no UNIQUE clause.
3. Compare with the CREATE TABLE in the Kinship backend, which declares one.

#### Suggested fix

Add `UNIQUE(c_person_id)` to the `ZZ_SP_KINSHIP` definition in CBDB_AdditionalTablesViewsIndices.sql, exactly as `ZZ_SIP_NETWORK` received it.

#### Where it lives in the build

- `Code/kinship_form_backend.go:479`
- `CBDBSetUpCode/CBDB_AdditionalTablesViewsIndices.sql:895`

#### Demonstrated by

- 1 × failed: `test_a_uniqueness_a_form_declares_is_one_the_table_enforces`

## CBDB-D-005 — Three forms accept an unfiltered query and give no way to ask for one -- and two of them offer the button for it

**Affected area:** Office, Associations and Status pages

**Severity:** P5 — Unreachable feature — the application implements something no page can ask for.  The band says only that no user can get to it.  Whether the code behind it is correct is a separate question with a separate answer, so an unreachable feature that is also broken is recorded in both places rather than argued about in one.

**Where it comes from:** `software` — In the application: cbdb.exe, its Go sources, its page templates, or the database builder's logic.  Fixed by the CBDB-Desktop developers.

**Status in this run:** CONFIRMED

#### Description

Each of these three handlers adds its primary code filter only when the list is non-empty -- `if len(p.OfficeCodes) > 0` -- so an empty list means *every code*, and the Office page's own variable says so: `let _officeCodes = [];   // [] = all offices`.  Each page then greys out Run Query whenever that list is empty, which is exactly the state the handler reads as 'no filter'.  On Office and Associations the button that puts the form into that state -- *All Offices*, and *All* -- calls a clear function that empties the list and re-greys Run Query.  Pressing the control for 'everything' disables the control for 'go'.

#### Evidence

Swept over the build rather than observed on one form, and the chain is followed all three steps: the quantity each page's Run Query gate tests, the request field the page builds from it, and the Go field that field decodes into.  Three forms meet on all three -- associations (`assocCodes`), office (`_officeCodes` sent as `officeCodes`), status (`selectedStatusCodes` sent as `statusCodes`).  The Office case is confirmed end to end in a browser: pick an office and Run Query is enabled; press *All Offices* and it is disabled again, while the same request sent over HTTP with `officeCodes: []` answers 200.

#### Impact

Three of the six main forms cannot be asked for their unfiltered result.  A researcher who wants every office posting in a place, or every association of a person, or every status in a dynasty, has no way to say so through the page -- and on two of them the button that appears to offer it makes the form less usable rather than more.  The work behind that query is written, tested and reachable over HTTP; only the interface refuses.

#### Steps to reproduce

1. Open the Office form (/LookAtOffice).
2. Press Select Office and choose any office; Run Query becomes available.
3. Press All Offices.
4. Run Query is greyed out again, and there is no way to run the query the button just asked for.
5. On the Associations form the same sequence with Select Associations and the All button does the same thing.

#### Suggested fix

Decide per form what an empty selection means and make the page agree with the handler.  If the unfiltered query is intended -- and the Office page's own comment says it is -- then Run Query should not be gated on the list being non-empty, and the *All* buttons should leave it enabled.  If it is not intended, the handlers should refuse an empty list with a message, the way the Places form refuses an empty category selection, rather than accepting a request no user can send.

#### Where it lives in the build

- `Templates/office/index.html:343`
- `Templates/office/index.html:357`
- `Code/office_form_backend.go:659`
- `Templates/associations/index.html:304`
- `Templates/status/index.html:473`
- `Code/associations_form_backend.go:534`
- `Code/status_form_backend.go:496`

#### Demonstrated by

- 2 × failed: `test_a_form_that_accepts_an_unfiltered_query_has_a_way_to_ask_for_one`, `test_all_offices_leaves_the_office_form_able_to_query`

## CBDB-D-006 — Two lookup endpoints were orphaned by the picker rework: implemented, routed, and called by no page

**Affected area:** /api/entry-code-type-rel and /api/status-code-type-rel

**Severity:** P5 — Unreachable feature — the application implements something no page can ask for.  The band says only that no user can get to it.  Whether the code behind it is correct is a separate question with a separate answer, so an unreachable feature that is also broken is recorded in both places rather than argued about in one.

**Where it comes from:** `software` — In the application: cbdb.exe, its Go sources, its page templates, or the database builder's logic.  Fixed by the CBDB-Desktop developers.

**Status in this run:** CONFIRMED

#### Description

The entry and status pickers each had their search reworked in this build -- it now filters the codes already loaded rather than stepping through matches, and the *Next* button is gone.  Both pickers stopped fetching the code-to-type relation they had been loading alongside the type tree.  The two endpoints, their handlers and their SQL are all still in the build; nothing calls them.

#### Evidence

Surveyed rather than noticed: every `/api/` route the build registers, against every shipped page including the pickers.  116 routes, two of them called by nothing.  Both still answer when requested directly, so this is work that runs and cannot be reached rather than work that is broken.  The same survey found and reported two Networks autocomplete helpers in the same state two builds earlier; those were removed, which is one of the two reasonable answers here.

#### Impact

No user-visible consequence today: the pickers work, and what they stopped fetching they no longer need.  It is reported because dead-but-live code is a maintenance cost that grows quietly -- the handler, its SQL and its route will be read, updated and tested by somebody who does not know nothing calls them.

#### Steps to reproduce

1. Search the shipped Templates directory for 'entry-code-type-rel' or 'status-code-type-rel': no page mentions either.
2. Request either endpoint directly: it answers 200 with its rows.

#### Suggested fix

Either delete the two handlers and their routes, as was done with the Networks search helpers, or wire them back to whatever still needs the relation.  Worth checking first whether the reworked search lost a capability along with the fetch: the old picker used the relation to search across types, and the new one filters within the loaded node.

#### Where it lives in the build

- `Code/entry_form_backend.go:182`
- `Code/status_form_backend.go:170`
- `Templates/pickers/entry_picker.html`
- `Templates/pickers/status_picker.html`

#### Demonstrated by

- 1 × failed: `test_every_api_endpoint_the_build_routes_has_a_page_that_calls_it`

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


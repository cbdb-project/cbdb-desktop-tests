# CBDB-Desktop — Issues Report

_A respectful summary of issues uncovered during automated regression testing._

_Build under test: CBDB-Desktop_20261021.7z_

_Generated 2026-10-23 10:43 UTC from a run of 1540 tests (566s)._

Dear maintainer,

Below is a summary of the issues we uncovered while building an automated regression-test suite for CBDB-Desktop. We hope this report is useful as you continue your wonderful stewardship of this dataset, and we sincerely thank you for the immense work that has gone into building it.

Most of the issues below were found by launching the shipped `cbdb.exe` and driving its own HTTP endpoints against the shipped database; the rest were found by reading the shipped page templates, Go sources and release archive, which is the honest way to describe a defect that needs no query to demonstrate. Either way, nothing here re-implements the application's logic, so what is described is what the released program does. The band on each issue is a kind as much as a rank: P0 to P2 run from worse to less bad, but P3 onwards name categories -- packaging, data integrity, a feature no page can reach -- so a P5 is not milder than a P3, and the text printed beside each band says what it means. Each entry includes a short description, the measurement that establishes it, step-by-step reproduction, and a suggested fix.

We have not tried to set your priorities: the bands describe what we measured, not what your users are asking for, and you are far better placed than we are to judge which of these matter. Several are silent -- the application gives a wrong or partial answer with no error shown -- and we have said so plainly where that is the case, because it is the kind of thing that is easy to miss and hard to notice later. Nothing here needs to be answered today.

## How this run went

| outcome | count |
| --- | --- |
| passed | 1326 |
| failed | 29 |
| xfailed (agreed to leave for now) | 4 |
| skipped | 181 |

Every one of the 29 failures is a test that demonstrates an issue below.

## What the suite covers

| Area | Tests | What it checks |
| --- | --- | --- |
| The distribution itself | 63 | That the tree under test really is the shipped archive, file by file |
| The application process | 13 | That the shipped binary starts, serves, and releases its database |
| Every registered route | 17 | Every route read out of the shipped Go source, driven for real |
| Passing a result from one form to another | 21 | The stored-person list: what one form stores, another recalls |
| The Association Pairs form's intermediaries | 4 | That every person a 2-node query reports lies on a path between the two seeds, read off the reply's own network, in all four shapes of the query |
| Each page against its own handler | 18 | Whether the two halves of a form agree about the request and the reply -- a control the handler never reads, a reply the page cannot read, a capability with no way in |
| Whether each page's JavaScript still parses | 30 | A form keeps all its behaviour in one inline script, so a syntax error in it leaves every control on the page dead while the page still loads -- read out of the shipped templates, with no browser |
| The code and address lists | 38 | The dropdowns each form offers before a query is run |
| The Group Data form | 7 | Its five section switches driven one at a time, and what it answers when every one of them is off |
| The Entry and Status pickers | 4 | Their type trees: that every type offered has codes somewhere beneath it, and that every parent named is a type that exists |
| The Networks form's filters | 11 | Its kin and non-kin switches, the sex filter, and each of the association categories that select anything, driven on its own |
| The Query Builder's grid, cell by cell | 34 | Its eleven operators, four aggregates, sort row, join kinds and what it does with a cell it cannot parse |
| The Query Builder | 21 | Its whitelist, the SQL it shows the user, and its guards |
| The six single-query forms | 57 | Entry, office, status, texts, associations, places — queries and exports |
| The forms that remember | 19 | Kinship, networks, association pairs, group data — working lists |
| Index-address rankings | 12 | The only endpoints that rewrite CBDB data rather than scratch |
| Every filter, on inputs read from the data | 420 | One query per populated combination the shipped database has, plus every switch turned both ways |
| Every export button | 498 | Every file-producing endpoint pressed, and the files they return read back |
| The pages in a real browser | 20 | That every page loads without throwing, and that a control waiting on the user un-greys when they do it |
| English, Traditional and Simplified labels | 103 | Every translated label, from the templates and from the screen: all three languages present, each Chinese text in its own script, and agreement with the CBDB label glossary and across forms |
| The shipped source | 19 | That the Go source shipped in Code/ is the source of the shipped cbdb.exe |
| The developers' release notes | 8 | That the notes shipped beside the tree convert to Markdown faithfully, and identically every time |
| Two tabs at once | 3 | Whether one query can replace what another was about to export |
| The working tables | 7 | Which form owns which scratch table, read out of the shipped Go |
| This run's own coverage | 5 | That every endpoint the shipped pages can reach was actually requested by this run |
| What was agreed to leave alone | 28 | That every waived outcome still names a check this run has, and that nothing else in the suite tolerates a failure |
| This report's own sources | 25 | That every issue below still cites real code, in both languages |
| This report itself | 35 | That it is reproducible from the run above, invents no issue, and drops none that was not agreed to be left alone |
| every test in this run | 1540 |  |

### What this round did not reach

The table above counts what was checked; it is not a list of what the application does.  A feature can appear in it because one narrow thing about it is checked -- that a button un-greys when it should, say -- while what the button produces is never read.  Where that is true of something this build added, the issue below says so in its own words.  Read a row as *this much was checked*, and an absent row as nothing at all.

## Summary

| ID | Priority | Status in this run | Issue |
| --- | --- | --- | --- |
| CBDB-D-002 | P2 | CONFIRMED | Group Data throws whenever no query has run: importing a list reports "Import error" on an import that succeeded, Recall IDs reports an error, and Clear does not clear |
| CBDB-D-001 | P3 | CONFIRMED | The Go source shipped in Code/ is not the source of the shipped cbdb.exe: only office_form_backend.go changed since 20260925, while the binary carries the revisions the notes describe |
| CBDB-D-004 | P6 | CONFIRMED | On ten of the eleven translated forms, Chinese labels differ from the CBDB glossary's terms -- some of them changing the meaning: the Office form's Index Years filter is labelled 生卒年 (birth and death years), and five forms call the index year 索引年 |
| CBDB-D-005 | P6 | CONFIRMED | Twelve labels on four forms pair English and Chinese the glossary does not pair -- among them the Browser tab captioned Basic Information whose Chinese says 生卒年 (birth and death years) |
| CBDB-D-006 | P6 | CONFIRMED | Seven forms show text in the wrong script for the language chosen: bilingual labels written into the page that the language switch never rewrites, and 指數 left in Simplified text |
| CBDB-D-007 | P6 | CONFIRMED | One English label, several Chinese words: 23 labels are translated differently on different forms (Save to GIS three ways, Index Year four ways) |

## Table of contents

- [CBDB-D-002 — Group Data throws whenever no query has run: importing a list reports "Import error" on an import that succeeded, Recall IDs reports an error, and Clear does not clear](#cbdb-d-002--group-data-throws-whenever-no-query-has-run-importing-a-list-reports-import-error-on-an-import-that-succeeded-recall-ids-reports-an-error-and-clear-does-not-clear)
- [CBDB-D-001 — The Go source shipped in Code/ is not the source of the shipped cbdb.exe: only office_form_backend.go changed since 20260925, while the binary carries the revisions the notes describe](#cbdb-d-001--the-go-source-shipped-in-code-is-not-the-source-of-the-shipped-cbdbexe-only-office-form-backendgo-changed-since-20260925-while-the-binary-carries-the-revisions-the-notes-describe)
- [CBDB-D-004 — On ten of the eleven translated forms, Chinese labels differ from the CBDB glossary's terms -- some of them changing the meaning: the Office form's Index Years filter is labelled 生卒年 (birth and death years), and five forms call the index year 索引年](#cbdb-d-004--on-ten-of-the-eleven-translated-forms-chinese-labels-differ-from-the-cbdb-glossarys-terms----some-of-them-changing-the-meaning-the-office-forms-index-years-filter-is-labelled-生卒年-birth-and-death-years-and-five-forms-call-the-index-year-索引年)
- [CBDB-D-005 — Twelve labels on four forms pair English and Chinese the glossary does not pair -- among them the Browser tab captioned Basic Information whose Chinese says 生卒年 (birth and death years)](#cbdb-d-005--twelve-labels-on-four-forms-pair-english-and-chinese-the-glossary-does-not-pair----among-them-the-browser-tab-captioned-basic-information-whose-chinese-says-生卒年-birth-and-death-years)
- [CBDB-D-006 — Seven forms show text in the wrong script for the language chosen: bilingual labels written into the page that the language switch never rewrites, and 指數 left in Simplified text](#cbdb-d-006--seven-forms-show-text-in-the-wrong-script-for-the-language-chosen-bilingual-labels-written-into-the-page-that-the-language-switch-never-rewrites-and-指數-left-in-simplified-text)
- [CBDB-D-007 — One English label, several Chinese words: 23 labels are translated differently on different forms (Save to GIS three ways, Index Year four ways)](#cbdb-d-007--one-english-label-several-chinese-words-23-labels-are-translated-differently-on-different-forms-save-to-gis-three-ways-index-year-four-ways)
- [Severity legend](#severity-legend)
- [Reproducing this report](#reproducing-this-report)

## CBDB-D-002 — Group Data throws whenever no query has run: importing a list reports "Import error" on an import that succeeded, Recall IDs reports an error, and Clear does not clear

**Affected area:** Group Data form (/LookAtGroupData), its page script

**Severity:** P2 — Visible failure — the user's action fails with an error they see.  Usually a server error; sometimes a page that reports failure on a request that in fact succeeded.  The band is about what the user is shown, not about which half of the application went wrong.

**Where it comes from:** `software` — In the application: cbdb.exe, its Go sources, its page templates, or the database builder's logic.  Fixed by the CBDB-Desktop developers.

**Status in this run:** CONFIRMED

#### Description

`updateRunButton()` decides which buttons to enable.  Its first half guards against there being no result yet (`queryData !== null && ...`); six lines added in this build, which enable the per-dataset GIS checkboxes, read `queryData.statusRecords`, `.officeRecords` and so on without that guard.  `queryData` is `null` when the page loads and again after Clear, so every call before the first query -- on load, after Import, after Recall IDs, on ticking a category, and inside Clear -- throws `TypeError: Cannot read properties of null (reading 'statusRecords')` and stops the function that called it part-way.

#### Evidence

Driven in Chromium.  `test_every_page_the_build_serves_loads_without_throwing`: the page logs exactly that error on load.  `test_group_data_can_be_used_before_its_first_query` imports a one-person file through the page's own file input: the server answers 200 and loads the person, and the page shows "Import error: Cannot read properties of null (reading 'statusRecords')" with Clear still disabled and Import still enabled.  The six lines are absent from the 20260925 template and no revision note mentions them.

#### Impact

The first thing a user does on Group Data -- import or recall a list of people -- reports a failure that did not happen, and leaves the buttons in the wrong state; Clear then fails silently, so the form cannot be reset without reloading it.  A query can still be run, so the form is usable by someone who ignores the error, which is not something to ask of a user.

#### Steps to reproduce

1. Open Look At Group Data.
2. Import from File a text file holding one person ID.
3. The page says "Import error: Cannot read properties of null (reading 'statusRecords')"; Clear stays disabled.

#### Suggested fix

Guard the six lines like the ones above them (`queryData && ...`), or compute them from the `hasData` already in scope.

#### Where it lives in the build

- `Templates/group_data/index.html:365 (chkGisStatus, first of the six unguarded lines)`
- `Templates/group_data/index.html:161 (queryData = null)`
- `Templates/group_data/index.html:479 (clearPeople resets it to null and calls updateRunButton)`

#### Demonstrated by

- 2 × failed: `test_every_page_the_build_serves_loads_without_throwing`, `test_group_data_can_be_used_before_its_first_query`

## CBDB-D-001 — The Go source shipped in Code/ is not the source of the shipped cbdb.exe: only office_form_backend.go changed since 20260925, while the binary carries the revisions the notes describe

**Affected area:** The distribution archive: Code/*.go against cbdb.exe

**Severity:** P3 — Packaging — the released files contain something they should not, or lack something they should.

**Where it comes from:** `release` — In how this particular release was assembled -- a working copy shipped in place of a freshly built one, a file that was not regenerated.  Fixed in the release process by whoever builds the distribution.

**Status in this run:** CONFIRMED

#### Description

`cbdb.exe` was rebuilt on 2026-10-20, but every file in `Code/` except `office_form_backend.go` is byte-identical to the 20260925 archive (and `CBDBSetUpCode/` is unchanged, though `CBDBsetup.exe` was rebuilt too).  The binary contains functions declared nowhere in the shipped source -- `InlineArgsForDisplay` and `sqlLiteral` (QBE-3), `PlaceHandler.fillIndexAddresses` (PLC-4), `fmtOptFloat` (ASP-6) -- and the source still declares `NetworkHandler.handleRerun` and registers `/api/networks/rerun`, which the binary no longer has (NET-4 removed them).  So the published source does not build the published program, and none of the Go revisions in the nine notes shipped as source.

#### Evidence

`test_the_shipped_source_is_the_source_of_the_shipped_binary` compares the `main.` function names in cbdb.exe's function-name table with the `func` declarations in `Code/*.go` (compiler wrappers and functions the linker drops excluded, by rules tested on written-down cases; the 20260925 archive compares clean).  Only in the binary: InlineArgsForDisplay, PlaceHandler.fillIndexAddresses, fmtOptFloat, sqlLiteral.  Only in the source: NetworkHandler.handleRerun.  Behaviourally, `test_every_registered_api_route_still_exists` finds `/api/networks/rerun` registered in the source and answering 404 from the binary, and `test_every_api_endpoint_the_build_routes_has_a_page_that_calls_it` finds it routed in the source and called by no page.

#### Impact

Anyone who reads, audits or rebuilds from the shipped source gets last month's program.  For this test suite it means every check that reads the Go source as data -- the route inventory, scratch-table ownership, the source lines cited in this report for Go code -- describes the previous build wherever the two differ; the findings here that matter were therefore established by driving the binary.

#### Steps to reproduce

1. Open Code/networks_form_backend.go from the archive: it registers /api/networks/rerun (line 326).
2. Run cbdb.exe and send any request to /api/networks/rerun: 404.

#### Suggested fix

Ship the `Code/` (and `CBDBSetUpCode/`) the binaries were built from, and make copying it part of the release step that builds them.

#### Where it lives in the build

- `Code/networks_form_backend.go:326 (registers /api/networks/rerun, absent from the binary)`
- `Code/networks_form_backend.go:823 (handleRerun)`

#### Demonstrated by

- 3 × failed: `test_the_shipped_source_is_the_source_of_the_shipped_binary`, `test_every_api_endpoint_the_build_routes_has_a_page_that_calls_it`, `test_every_registered_api_route_still_exists`

## CBDB-D-004 — On ten of the eleven translated forms, Chinese labels differ from the CBDB glossary's terms -- some of them changing the meaning: the Office form's Index Years filter is labelled 生卒年 (birth and death years), and five forms call the index year 索引年

**Affected area:** The translation tables of every form with a language switch (Templates/*/index.html)

**Severity:** P6 — Wording — a label on a page says the wrong thing, or says it in the wrong script, in one of the three display languages (English, Traditional or Simplified Chinese).  Judged against the CBDB label glossary by fixed rules; nothing the application computes is affected, but a reader can be misled about what a control does.

**Where it comes from:** `software` — In the application: cbdb.exe, its Go sources, its page templates, or the database builder's logic.  Fixed by the CBDB-Desktop developers.

**Status in this run:** CONFIRMED

#### Description

When a label's English is a term the CBDB label glossary (the Access front end's FormLabels table, docs/labels/FormLabels.xlsx in the test repository) defines for that form, its Chinese should be one of the glossary's renderings of that term.  116 labels on ten of the eleven translated forms (all but the Browser) are not.  Most are wording the glossary words differently (`執行查詢` for *Run Query*, glossary `查詢`; `儲存人物ID` for *Store Person IDs*, glossary `存儲人物代碼`; `起`/`終` for *From*/*To*, glossary `始年`/`終年`).  Some change what the reader is told:

- Office: the date filter *Index Years* is `生卒年` (birth and death years) in both Chinese languages; the filter is on index year.
- Association Pairs, Associations, Entry, Networks, Texts: *Index Year* is `索引年` / `索引年份`; the glossary's term is `指數年`, and the developers' own 2026-10-16 note says `指數` is correct and `索引` is to be reverted.
- Status and Group Data: *Status* is `身份`; the glossary's term is `社會區分`.
- Kinship: *Mourning Circle* is `服制圈`; the glossary's term is `五服`.
- Networks: the association-type checkboxes use their own translations (`友誼`, `對立`, `支持`, `學術隸屬`, `推薦／贊助`) where the glossary has `朋友`, `軍事對抗`, `軍事支持`, `學術交往`, `薦舉保任`.

The full list, with the glossary row each judgement rests on, is in `reports/CBDB_Desktop_Translations.md` / `.xlsx`.

#### Evidence

`test_chinese_labels_use_the_glossary_term`, one test per form, fails on ten of eleven.  The labels are read as data from each template's translation object, and only labels the page actually reads are judged; a label is compared only with the glossary rows of its own Access form (Office with LAO, Status with LAS, the Browser with BIO and BROWSE -- its subforms' short column headers never decide an English word), and wording is compared after reducing both sides to one script and allowing Taiwan/mainland vocabulary (匯出/导出, 儲存/保存), so neither a script slip nor a regional word can produce a finding here.  Counts per form: networks 32, group_data 15, status 14, association_pairs 11, entry 9, office 9, kinship 8, texts 8, associations 7, places 3 (as measured on this build; the report is the authority).

#### Impact

A reader of the Chinese interface is told something different from what the English reader is told, and different from the vocabulary CBDB uses everywhere else.  Where the meaning changes, it misleads: a historian who reads 生卒年 on the Office form will believe the filter selects by birth and death years.  Nothing the application computes is affected.

#### Steps to reproduce

1. Open Look At Office and press 繁 (or 简).
2. Read the date-filter option that the English page calls Index Years: it says 生卒年.
3. Open Look At Entry, press 繁: the index-year option says 索引年, where CBDB's term is 指數年.

#### Suggested fix

Replace each listed Chinese label with the glossary's term (the report gives it), starting with the ones that change the meaning.  Where the developers prefer their wording, the glossary is what should change -- in the spreadsheet, so the two stay one vocabulary.

#### Where it lives in the build

- `Templates/office/index.html:245 (indexYearsFilter: '生卒年')`
- `Templates/entry/index.html:299 (indexYear: '索引年')`
- `Templates/status/index.html:218 (status: '身份')`
- `Templates/kinship/index.html:170 (Mourning Circle: '服制圈')`

#### Demonstrated by

- 10 × failed: `test_chinese_labels_use_the_glossary_term[association_pairs]`, `test_chinese_labels_use_the_glossary_term[associations]`, `test_chinese_labels_use_the_glossary_term[entry]`, `test_chinese_labels_use_the_glossary_term[group_data]` (+6)
- 1 × passed: `test_chinese_labels_use_the_glossary_term[browser]`

## CBDB-D-005 — Twelve labels on four forms pair English and Chinese the glossary does not pair -- among them the Browser tab captioned Basic Information whose Chinese says 生卒年 (birth and death years)

**Affected area:** Browser, Kinship, Networks and Office translation tables

**Severity:** P6 — Wording — a label on a page says the wrong thing, or says it in the wrong script, in one of the three display languages (English, Traditional or Simplified Chinese).  Judged against the CBDB label glossary by fixed rules; nothing the application computes is affected, but a reader can be misled about what a control does.

**Where it comes from:** `software` — In the application: cbdb.exe, its Go sources, its page templates, or the database builder's logic.  Fixed by the CBDB-Desktop developers.

**Status in this run:** CONFIRMED

#### Description

When a label's Chinese is a glossary term for its form and its English is not a glossary term at all, the English should be the glossary's English for that Chinese -- or the Chinese is the wrong half.  Twelve are not: Browser *Basic Information* over `生卒年` (glossary *Birth/Death Years*), *Social Institutions* over `社交機構` (*Institutions*), *ID:* and *CBDB ID* over `人物代碼` (*Person ID*), *Birth:*/*Death:* over `生年`/`卒年` (*Born*/*Died*), *Age* over `享年` (*Age at Death*), *Offices* over `職官` (*Postings*); Kinship *Kin Network* (*Kinship Network*); Networks *Biography* and *Ritual* (*Biographical Texts*, *Ritual Texts*); Office *Query* (*Run Query*).  The first is a mismatch between the two languages, not only with the glossary: the page's own comment says the English caption was renamed and "no new Chinese caption supplied yet".

#### Evidence

`test_english_labels_use_the_glossary_term` fails for browser (8), networks (2), kinship (1) and office (1).  Only labels whose English is *not* a glossary term are judged this way, so a pair that is wrong is reported once (by D-004 or here), never from both sides.

#### Impact

Mostly wording.  The Browser's first tab is the exception: an English reader and a Chinese reader are told the tab holds different things.

#### Steps to reproduce

1. Open the Browser, select a person, and read the first tab in English (Basic Information), then press 繁: 生卒年.

#### Suggested fix

Use the glossary's English for these twelve, or supply the Chinese caption the Browser comment is waiting for and add both to the glossary.

#### Where it lives in the build

- `Templates/browser/index.html:406 (tabBasicInfo: '生卒年', with the comment about the renamed caption)`
- `Templates/kinship/index.html:163 (Kin Network)`

#### Demonstrated by

- 4 × failed: `test_english_labels_use_the_glossary_term[browser]`, `test_english_labels_use_the_glossary_term[kinship]`, `test_english_labels_use_the_glossary_term[networks]`, `test_english_labels_use_the_glossary_term[office]`
- 7 × passed: `test_english_labels_use_the_glossary_term[association_pairs]`, `test_english_labels_use_the_glossary_term[associations]`, `test_english_labels_use_the_glossary_term[entry]`, `test_english_labels_use_the_glossary_term[group_data]` (+3)

## CBDB-D-006 — Seven forms show text in the wrong script for the language chosen: bilingual labels written into the page that the language switch never rewrites, and 指數 left in Simplified text

**Affected area:** Association Pairs, Associations, Networks, Office, Places, Status and Texts pages

**Severity:** P6 — Wording — a label on a page says the wrong thing, or says it in the wrong script, in one of the three display languages (English, Traditional or Simplified Chinese).  Judged against the CBDB label glossary by fixed rules; nothing the application computes is affected, but a reader can be misled about what a control does.

**Where it comes from:** `software` — In the application: cbdb.exe, its Go sources, its page templates, or the database builder's logic.  Fixed by the CBDB-Desktop developers.

**Status in this run:** CONFIRMED

#### Description

With 繁 chosen, the Office form still shows `Office 官职`, `Type 类型`, `Place 地点` and its title `官职查询`; Texts shows `查询模式`, `(全部地点)` and `日期筛选`; Associations shows `(关系)`.  With 简 chosen, Places, Associations and Networks keep traditional titles (`查看地點`, `查看關係`, `查看人際網絡`), Status keeps `Place / 地點`, Texts keeps `書名`, and Association Pairs keeps the placeholder `[漢字]`.  These are labels written straight into the HTML, which `setLanguage` does not touch.  Separately, four Simplified translations contain the traditional `數`: Places `指數年份范围`, `相关人物指數地点`, `亲属指數地点`, and Status `使用指數年份` (in both Chinese tables).

#### Evidence

Two checks in two places.  `test_each_chinese_language_shows_only_its_own_script` presses each page's own 繁 and 简 buttons in Chromium and judges what is on screen (only strings that occur in the template, so CBDB data shown on the page is not judged, and not strings the table check already judges, so nothing is counted twice): 14 strings on 7 pages.  `test_every_chinese_label_is_written_in_its_own_script` reads the translation tables: the four `數` above.  A character is flagged only when every OpenCC conversion into the chosen script -- mainland, Taiwan and Hong Kong standards -- changes it, in context and on its own.

#### Impact

A reader who chose one script sees the other in labels and titles.  Cosmetic, but it is exactly what a reader who chooses 繁 or 简 notices first.

#### Steps to reproduce

1. Open Look At Office and press 繁.
2. Read the left panel: 'Office 官职', 'Type 类型', 'Place 地点' are still in Simplified Chinese.

#### Suggested fix

Give each hard-coded bilingual label an id and a key in the page's translation table, as the translated labels already have; replace `數` with `数` in the four Simplified strings.

#### Where it lives in the build

- `Templates/office/index.html:34 (<label>Office 官职</label>)`
- `Templates/status/index.html:49 (<h3>Place / 地點</h3>)`
- `Templates/places/index.html:202 (indexYearRange: '指數年份范围')`
- `Templates/status/index.html:239 (useIndexYears: '使用指數年份')`

#### Demonstrated by

- 9 × failed: `test_every_chinese_label_is_written_in_its_own_script[places]`, `test_every_chinese_label_is_written_in_its_own_script[status]`, `test_each_chinese_language_shows_only_its_own_script[association_pairs]`, `test_each_chinese_language_shows_only_its_own_script[associations]` (+5)
- 13 × passed: `test_every_chinese_label_is_written_in_its_own_script[association_pairs]`, `test_every_chinese_label_is_written_in_its_own_script[associations]`, `test_every_chinese_label_is_written_in_its_own_script[browser]`, `test_every_chinese_label_is_written_in_its_own_script[entry]` (+9)

## CBDB-D-007 — One English label, several Chinese words: 23 labels are translated differently on different forms (Save to GIS three ways, Index Year four ways)

**Affected area:** Translation tables across all forms

**Severity:** P6 — Wording — a label on a page says the wrong thing, or says it in the wrong script, in one of the three display languages (English, Traditional or Simplified Chinese).  Judged against the CBDB label glossary by fixed rules; nothing the application computes is affected, but a reader can be misled about what a control does.

**Where it comes from:** `software` — In the application: cbdb.exe, its Go sources, its page templates, or the database builder's logic.  Fixed by the CBDB-Desktop developers.

**Status in this run:** CONFIRMED

#### Description

Grouping every translated label by its English shows 23 that the forms translate in more than one way, among them: *Save to GIS* `儲存至GIS` (Association Pairs, Entry, Group Data), `保存到GIS` (Associations, Networks, Places, Status, Texts), `存至GIS` (Kinship); *Index Year* `索引年`, `索引年份`, `指數年`, `生卒年`; *Recall IDs* `召回ID`, `調出ID`, `調取ID`; *Status* `社會區分` (Browser) and `身份` (Group Data, Status); *Offices* `職官` and `官職`; *From:*/*To:* `從:`/`至:` and `起`/`終`.  Taiwan/mainland vocabulary is not counted as a difference (the maintainer's ruling of 2026-10-22).

#### Evidence

`test_one_english_label_is_translated_one_way_across_pages` (needs no glossary).  Wordings are grouped by OpenCC's script and Taiwan/mainland equivalence plus the pairs in docs/labels/regional_terms.tsv, so 儲存/保存, 匯出/导出 or 連結/连接 count as one word; several Chinese labels under one short English word on the *same* form (the Browser's Range → 生年時限 / 卒年時限) are fields named in context and are not counted.

#### Impact

A reader learns several words for one action or one concept as they move between forms, and cannot tell whether the forms mean the same thing.

#### Steps to reproduce

1. Press 繁 on Look At Entry, Look At Networks and Look At Kinship, and compare the Save to GIS buttons: 儲存至GIS, 保存到GIS, 存至GIS.

#### Suggested fix

Choose one wording per label -- the glossary's, where it has one (D-004) -- and use it on every form.

#### Where it lives in the build

- `Templates/entry/index.html:308 (saveGIS: '儲存至GIS')`
- `Templates/networks/index.html:482 (saveToGIS: '保存到GIS')`
- `Templates/kinship/index.html:150 (Save to GIS: '存至GIS')`

#### Demonstrated by

- 1 × failed: `test_one_english_label_is_translated_one_way_across_pages`

## Severity legend

- **P0** — Silent wrong answer — the application returns wrong or empty results, or produces a file nothing can read, with no error shown to the user.
- **P1** — Destructive write — a request rewrites stored data that it should not, and the previous state cannot be recovered.
- **P2** — Visible failure — the user's action fails with an error they see.  Usually a server error; sometimes a page that reports failure on a request that in fact succeeded.  The band is about what the user is shown, not about which half of the application went wrong.
- **P3** — Packaging — the released files contain something they should not, or lack something they should.
- **P4** — Data integrity — a reference in the shipped data does not resolve.
- **P5** — Unreachable feature — the application implements something no page can ask for.  The band says only that no user can get to it.  Whether the code behind it is correct is a separate question with a separate answer, so an unreachable feature that is also broken is recorded in both places rather than argued about in one.
- **P6** — Wording — a label on a page says the wrong thing, or says it in the wrong script, in one of the three display languages (English, Traditional or Simplified Chinese).  Judged against the CBDB label glossary by fixed rules; nothing the application computes is affected, but a reader can be misled about what a control does.

## Reproducing this report

The whole report is generated from one command. With the distribution zip named in `.env` as `CBDB_DESKTOP_ZIP`:

```powershell
.\run_tests.ps1
```

That stages the archive, launches the shipped binary against a private copy of the shipped database, runs 1540 tests, and rewrites these files. The suite never writes to the reference copy of `Data/CBDB.db` — every test runs against a per-session copy, so a run leaves the distribution exactly as it found it.

The test that demonstrates each issue is named under it. To run just one:

```powershell
python -m pytest tests -k test_searching_people_by_name_finds_them -v
```


# CBDB-Desktop — Issues Report

_A respectful summary of issues uncovered during automated regression testing._

_Build under test: CBDB-Desktop_20260925.7z_

_Generated 2026-10-01 03:48 UTC from a run of 1381 tests (436s)._

Dear maintainer,

Below is a summary of the issues we uncovered while building an automated regression-test suite for CBDB-Desktop. We hope this report is useful as you continue your wonderful stewardship of this dataset, and we sincerely thank you for the immense work that has gone into building it.

Most of the issues below were found by launching the shipped `cbdb.exe` and driving its own HTTP endpoints against the shipped database; the rest were found by reading the shipped page templates, Go sources and release archive, which is the honest way to describe a defect that needs no query to demonstrate. Either way, nothing here re-implements the application's logic, so what is described is what the released program does. The band on each issue is a kind as much as a rank: P0 to P2 run from worse to less bad, but P3 onwards name categories -- packaging, data integrity, a feature no page can reach -- so a P5 is not milder than a P3, and the text printed beside each band says what it means. Each entry includes a short description, the measurement that establishes it, step-by-step reproduction, and a suggested fix.

We have not tried to set your priorities: the bands describe what we measured, not what your users are asking for, and you are far better placed than we are to judge which of these matter. Several are silent -- the application gives a wrong or partial answer with no error shown -- and we have said so plainly where that is the case, because it is the kind of thing that is easy to miss and hard to notice later. Nothing here needs to be answered today.

## How this run went

| outcome | count |
| --- | --- |
| passed | 1190 |
| failed | 4 |
| xfailed (agreed to leave for now) | 4 |
| skipped | 183 |

Every one of the 4 failures is a test that demonstrates an issue below.

## What the suite covers

| Area | Tests | What it checks |
| --- | --- | --- |
| The distribution itself | 63 | That the tree under test really is the shipped archive, file by file |
| The application process | 13 | That the shipped binary starts, serves, and releases its database |
| Every registered route | 17 | Every route read out of the shipped Go source, driven for real |
| Passing a result from one form to another | 22 | The stored-person list: what one form stores, another recalls |
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
| Every export button | 503 | Every file-producing endpoint pressed, and the files they return read back |
| The pages in a real browser | 12 | That every page loads without throwing, and that a control waiting on the user un-greys when they do it |
| Two tabs at once | 3 | Whether one query can replace what another was about to export |
| The working tables | 7 | Which form owns which scratch table, read out of the shipped Go |
| This run's own coverage | 5 | That every endpoint the shipped pages can reach was actually requested by this run |
| What was agreed to leave alone | 28 | That every waived outcome still names a check this run has, and that nothing else in the suite tolerates a failure |
| This report's own sources | 10 | That every issue below still cites real code, in both languages |
| This report itself | 27 | That it is reproducible from the run above, invents no issue, and drops none that was not agreed to be left alone |
| every test in this run | 1381 |  |

### What this round did not reach

The table above counts what was checked; it is not a list of what the application does.  A feature can appear in it because one narrow thing about it is checked -- that a button un-greys when it should, say -- while what the button produces is never read.  Where that is true of something this build added, the issue below says so in its own words.  Read a row as *this much was checked*, and an absent row as nothing at all.

## Summary

| ID | Priority | Status in this run | Issue |
| --- | --- | --- | --- |
| CBDB-D-002 | P0 | CONFIRMED | The Places form's "Export as ASCII (pinyin)" checkbox is ignored by Save to GIS and Save to KML |
| CBDB-D-003 | P5 | CONFIRMED | The Places form's Pajek, Gephi/GUESS and UCINet exports are implemented and no control on its page calls them |

## Table of contents

- [CBDB-D-002 — The Places form's "Export as ASCII (pinyin)" checkbox is ignored by Save to GIS and Save to KML](#cbdb-d-002--the-places-forms-export-as-ascii-pinyin-checkbox-is-ignored-by-save-to-gis-and-save-to-kml)
- [CBDB-D-003 — The Places form's Pajek, Gephi/GUESS and UCINet exports are implemented and no control on its page calls them](#cbdb-d-003--the-places-forms-pajek-gephiguess-and-ucinet-exports-are-implemented-and-no-control-on-its-page-calls-them)
- [Severity legend](#severity-legend)
- [Reproducing this report](#reproducing-this-report)

## CBDB-D-002 — The Places form's "Export as ASCII (pinyin)" checkbox is ignored by Save to GIS and Save to KML

**Affected area:** Places form (/LookAtPlace): /api/places/export-gis

**Severity:** P0 — Silent wrong answer — the application returns wrong or empty results, or produces a file nothing can read, with no error shown to the user.

**Where it comes from:** `software` — In the application: cbdb.exe, its Go sources, its page templates, or the database builder's logic.  Fixed by the CBDB-Desktop developers.

**Status in this run:** CONFIRMED

#### Description

The Places page sends the checkbox as `encoding: "ascii"` with each export beside it (`getExportEncoding`).  Of those three buttons, Export Neo4j CSVs honours it and the other two do not: `handleExportGIS` decodes `Encoding` and never reads it, and both of its writers put the Chinese fields in the file whatever was asked -- `writePlaceTab` writes every `*Chn` column beside its pinyin twin, and `writePlaceKML` writes `NameChn` into each placemark's description.  A user who ticks the box and presses Save to GIS or Save to KML gets the Unicode file, byte for byte, with nothing to say so.

The same form's Gephi writer honours the choice in part: its edge labels switch to pinyin and its node labels stay `NameChn`.  No button reaches that export on this build (CBDB-D-003); it is recorded here too so that wiring one up does not ship the same fault.

#### Evidence

`test_an_export_asked_for_ascii_contains_only_ascii` posts two records in which every Chinese field has an ASCII pinyin twin, once with `encoding=unicode` and once with `encoding=ascii`, and reads each file past any leading byte-order mark.  With ascii: `places:gis` delivered `places_export.tsv` with 72 bytes above 0x7F and `places:kml` delivered `places_export.kml` with 18 -- both byte-for-byte the unicode export.  `places:gephi` delivered `network_ascii.gdf` with 42, different from its unicode file.  `places:neo4j` and `places:pajek` passed (pure ASCII past the mark); `places:ucinet` writes no Chinese in either mode and has nothing to judge.

#### Impact

The checkbox is there for a user whose GIS or mapping tool cannot read Chinese, and those are exactly the files it does nothing to.  They get Unicode names they asked not to get, in a file that looks like the one they asked for, and the only sign is the tool that then shows them garbage.  Medium: the files are not wrong for anyone who did not tick the box, and Neo4j does honour it.

#### Steps to reproduce

1. Open Places and run any query that returns rows with Chinese names.
2. Tick "Export as ASCII (pinyin) instead of Unicode".
3. Press Save to KML, and separately Save to GIS.
4. Open either file: it carries the Chinese -- the KML in each placemark's description, the GIS file in its *Chn columns -- and is identical to the one saved with the box unticked.

#### Suggested fix

In `handleExportGIS`, read `Encoding` and pass it to both writers, which in ascii mode should leave the Chinese out, as `buildPlaceNeo4jFiles` already does: `writePlaceTab` by omitting or blanking its `*Chn` columns, `writePlaceKML` by leaving `NameChn` out of the description.  In `handleExportGephi`, use `n.NamePY` as the node label in ascii mode, as its edge labels already do.

#### Where it lives in the build

- `Code/places_form_backend.go:handleExportGIS (decodes Encoding, never reads it)`
- `Code/places_form_backend.go:writePlaceTab (every *Chn column beside its pinyin twin)`
- `Code/places_form_backend.go:writePlaceKML (NameChn in the placemark description)`
- `Code/places_form_backend.go:handleExportGephi (NameChn as the node label in both modes)`
- `Templates/places/index.html:727 (getExportEncoding)`

#### Demonstrated by

- 3 × failed: `test_an_export_asked_for_ascii_contains_only_ascii[places:gis]`, `test_an_export_asked_for_ascii_contains_only_ascii[places:kml]`, `test_an_export_asked_for_ascii_contains_only_ascii[places:gephi]`
- 2 × passed: `test_an_export_asked_for_ascii_contains_only_ascii[places:neo4j]`, `test_an_export_asked_for_ascii_contains_only_ascii[places:pajek]`
- 1 × skipped: `test_an_export_asked_for_ascii_contains_only_ascii[places:ucinet]`

## CBDB-D-003 — The Places form's Pajek, Gephi/GUESS and UCINet exports are implemented and no control on its page calls them

**Affected area:** Places form (/LookAtPlace): /api/places/export-pajek, /api/places/export-gephi, /api/places/export-ucinet

**Severity:** P5 — Unreachable feature — the application implements something no page can ask for.  The band says only that no user can get to it.  Whether the code behind it is correct is a separate question with a separate answer, so an unreachable feature that is also broken is recorded in both places rather than argued about in one.

**Where it comes from:** `software` — In the application: cbdb.exe, its Go sources, its page templates, or the database builder's logic.  Fixed by the CBDB-Desktop developers.

**Status in this run:** CONFIRMED

#### Description

The Places page defines `exportPajek`, `exportGephi` and `exportUCINet`, each posting the query result and the ASCII choice to its endpoint and downloading the answer, and the three handlers are routed and answer.  Nothing on the page invokes any of the three functions: its buttons are Run Query, Store Person IDs, Export Query Results, Save to KML, Save to GIS and Export Neo4j CSVs, and no listener or load-time code calls them either.  So three network exports -- the formats the other network forms offer -- exist on both sides and no user can reach them.  Whether their output is right is a separate question: the Gephi one keeps Chinese node labels in ASCII mode (CBDB-D-002).

#### Evidence

`test_every_endpoint_a_page_calls_is_reachable_from_something_a_user_does` walks each page's call graph from everything that can run -- buttons, every inline `on...=` handler, load-time code, listeners registered by name, and the `window.X` callbacks popups call back into.  Across every page the build ships, these three are the only endpoints a page mentions that the walk never reaches.  The textual survey (`test_every_api_endpoint_the_build_routes_has_a_page_that_calls_it`) counts them as called, because the fetches are there, inside functions nothing runs.

#### Impact

A historian working in Places cannot produce the Pajek, Gephi or UCINet files the other network forms offer, and there is nothing on the page to say the feature exists.  No wrong answer is given; the feature is simply unreachable.

#### Steps to reproduce

1. Open Places and run a query that returns rows.
2. Look for a Pajek, Gephi/GUESS or UCINet export: there is none, though the page's script defines exportPajek, exportGephi and exportUCINet.

#### Suggested fix

Add the three buttons the functions were written for, as the Kinship and Networks pages have, or delete the functions and handlers if the Places form is not meant to offer these formats.  Fix the Gephi ASCII labels (CBDB-D-002) before wiring it up.

#### Where it lives in the build

- `Templates/places/index.html:825 (exportUCINet, called by nothing)`
- `Templates/places/index.html:842 (exportPajek, called by nothing)`
- `Templates/places/index.html:859 (exportGephi, called by nothing)`
- `Templates/places/index.html:92 (the page's action buttons)`

#### Demonstrated by

- 1 × failed: `test_every_endpoint_a_page_calls_is_reachable_from_something_a_user_does`

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

That stages the archive, launches the shipped binary against a private copy of the shipped database, runs 1381 tests, and rewrites these files. The suite never writes to the reference copy of `Data/CBDB.db` — every test runs against a per-session copy, so a run leaves the distribution exactly as it found it.

The test that demonstrates each issue is named under it. To run just one:

```powershell
python -m pytest tests -k test_searching_people_by_name_finds_them -v
```


# CBDB-Desktop — Issues Report

_A respectful summary of issues uncovered during automated regression testing._

_Build under test: CBDB-Desktop_Build_20261124.7z_

_Generated 2026-11-24 06:18 UTC from a run of 1619 tests (751s)._

Dear maintainer,

Below is a summary of the issues we uncovered while building an automated regression-test suite for CBDB-Desktop. We hope this report is useful as you continue your wonderful stewardship of this dataset, and we sincerely thank you for the immense work that has gone into building it.

Most of the issues below were found by launching the shipped `cbdb.exe` and driving its own HTTP endpoints against the shipped database; the rest were found by reading the shipped page templates, Go sources and release archive, which is the honest way to describe a defect that needs no query to demonstrate. Either way, nothing here re-implements the application's logic, so what is described is what the released program does. The band on each issue is a kind as much as a rank: P0 to P2 run from worse to less bad, but P3 onwards name categories -- packaging, data integrity, a feature no page can reach -- so a P5 is not milder than a P3, and the text printed beside each band says what it means. Each entry includes a short description, the measurement that establishes it, step-by-step reproduction, and a suggested fix.

We have not tried to set your priorities: the bands describe what we measured, not what your users are asking for, and you are far better placed than we are to judge which of these matter. Several are silent -- the application gives a wrong or partial answer with no error shown -- and we have said so plainly where that is the case, because it is the kind of thing that is easy to miss and hard to notice later. Nothing here needs to be answered today.

## How this run went

| outcome | count |
| --- | --- |
| passed | 1414 |
| xfailed (agreed to leave for now) | 24 |
| skipped | 181 |

## What the suite covers

| Area | Tests | What it checks |
| --- | --- | --- |
| The distribution itself | 65 | That the tree under test really is the shipped archive, file by file |
| The application process | 13 | That the shipped binary starts, serves, and releases its database |
| Every registered route | 17 | Every route read out of the shipped Go source, driven for real |
| Passing a result from one form to another | 21 | The stored-person list: what one form stores, another recalls |
| The Association Pairs form's intermediaries | 4 | That every person a 2-node query reports lies on a path between the two seeds, read off the reply's own network, in all four shapes of the query |
| Each page against its own handler | 19 | Whether the two halves of a form agree about the request and the reply -- a control the handler never reads, a reply the page cannot read, a capability with no way in |
| Whether each page's JavaScript still parses | 38 | A form keeps all its behaviour in one inline script, so a syntax error in it leaves every control on the page dead while the page still loads -- read out of the shipped templates, with no browser |
| The code and address lists | 38 | The dropdowns each form offers before a query is run |
| The Group Data form | 7 | Its five section switches driven one at a time, and what it answers when every one of them is off |
| The Entry and Status pickers | 4 | Their type trees: that every type offered has codes somewhere beneath it, and that every parent named is a type that exists |
| The Networks form's filters | 11 | Its kin and non-kin switches, the sex filter, and each of the association categories that select anything, driven on its own |
| The Query Builder's grid, cell by cell | 34 | Its eleven operators, four aggregates, sort row, join kinds and what it does with a cell it cannot parse |
| The Query Builder | 21 | Its whitelist, the SQL it shows the user, and its guards |
| The six single-query forms | 57 | Entry, office, status, texts, associations, places — queries and exports |
| The forms that remember | 24 | Kinship, networks, association pairs, group data — working lists |
| Index-address rankings | 12 | The only endpoints that rewrite CBDB data rather than scratch |
| Every filter, on inputs read from the data | 420 | One query per populated combination the shipped database has, plus every switch turned both ways |
| Every export button | 498 | Every file-producing endpoint pressed, and the files they return read back |
| The pages in a real browser | 25 | That every page loads without throwing, and that a control waiting on the user un-greys when they do it |
| English, Traditional and Simplified labels | 117 | Every translated label, from the templates and from the screen: all three languages present, each Chinese text in its own script, and agreement with the CBDB label glossary and across forms |
| The language a form opens in | 44 | That every form opens in the language the reader's browser asks for, applies the mapping the developers specified, and remembers a choice made on one form when the next one is opened |
| Each form's Help button | 3 | That every help file a page names is served, and that Help opens the file for the language on screen |
| The shipped source | 19 | That the Go source shipped in Code/ is the source of the shipped cbdb.exe |
| The developers' release notes | 8 | That the notes shipped beside the tree convert to Markdown faithfully, and identically every time |
| Two tabs at once | 3 | Whether one query can replace what another was about to export |
| The working tables | 7 | Which form owns which scratch table, read out of the shipped Go |
| This run's own coverage | 5 | That every endpoint the shipped pages can reach was actually requested by this run |
| What was agreed to leave alone | 28 | That every waived outcome still names a check this run has, and that nothing else in the suite tolerates a failure |
| This report's own sources | 22 | That every issue below still cites real code, in both languages |
| This report itself | 35 | That it is reproducible from the run above, invents no issue, and drops none that was not agreed to be left alone |
| every test in this run | 1619 |  |

### What this round did not reach

The table above counts what was checked; it is not a list of what the application does.  A feature can appear in it because one narrow thing about it is checked -- that a button un-greys when it should, say -- while what the button produces is never read.  Where that is true of something this build added, the issue below says so in its own words.  Read a row as *this much was checked*, and an absent row as nothing at all.

No issues are recorded for this build.

# CBDB-Desktop — Issues Report

_A respectful summary of issues uncovered during automated regression testing._

_Build under test: CBDB-Desktop_Build_20261102.7z_

_Generated 2026-11-05 09:22 UTC from a run of 1546 tests (566s)._

Dear maintainer,

Below is a summary of the issues we uncovered while building an automated regression-test suite for CBDB-Desktop. We hope this report is useful as you continue your wonderful stewardship of this dataset, and we sincerely thank you for the immense work that has gone into building it.

Most of the issues below were found by launching the shipped `cbdb.exe` and driving its own HTTP endpoints against the shipped database; the rest were found by reading the shipped page templates, Go sources and release archive, which is the honest way to describe a defect that needs no query to demonstrate. Either way, nothing here re-implements the application's logic, so what is described is what the released program does. The band on each issue is a kind as much as a rank: P0 to P2 run from worse to less bad, but P3 onwards name categories -- packaging, data integrity, a feature no page can reach -- so a P5 is not milder than a P3, and the text printed beside each band says what it means. Each entry includes a short description, the measurement that establishes it, step-by-step reproduction, and a suggested fix.

We have not tried to set your priorities: the bands describe what we measured, not what your users are asking for, and you are far better placed than we are to judge which of these matter. Several are silent -- the application gives a wrong or partial answer with no error shown -- and we have said so plainly where that is the case, because it is the kind of thing that is easy to miss and hard to notice later. Nothing here needs to be answered today.

## How this run went

| outcome | count |
| --- | --- |
| passed | 1346 |
| failed | 1 |
| xfailed (agreed to leave for now) | 18 |
| skipped | 181 |

Of the 1 failures, **0** are the tests that demonstrate the issues below -- they are how those issues are established, and they will pass again when the issues are fixed.  The remaining **1** are accounted for underneath, so that a reader does not have to reconcile these numbers against the list of issues and find that they do not add up.

**1 failure(s) in this run are not yet classified.**  They are not among the issues below and they are not one of our known coverage gaps, which means this run found something nobody has looked at yet.  Each may turn out to be a defect worth filing or a problem with the check itself; please read them rather than trusting this list to be complete.

| Check | What it reported |
| --- | --- |
| `test_no_page_hides_its_javascript_where_this_check_cannot_read_it` | these pages load JavaScript from a file, which this scan does not read: {'association_pairs': 1, 'associations': 1, 'browser': 1, 'entry': 1, 'group_data': 1, 'kinship': 1, 'networks': 1, 'office': 1, |

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
| The pages in a real browser | 25 | That every page loads without throwing, and that a control waiting on the user un-greys when they do it |
| English, Traditional and Simplified labels | 110 | Every translated label, from the templates and from the screen: all three languages present, each Chinese text in its own script, and agreement with the CBDB label glossary and across forms |
| The shipped source | 19 | That the Go source shipped in Code/ is the source of the shipped cbdb.exe |
| The developers' release notes | 8 | That the notes shipped beside the tree convert to Markdown faithfully, and identically every time |
| Two tabs at once | 3 | Whether one query can replace what another was about to export |
| The working tables | 7 | Which form owns which scratch table, read out of the shipped Go |
| This run's own coverage | 5 | That every endpoint the shipped pages can reach was actually requested by this run |
| What was agreed to leave alone | 28 | That every waived outcome still names a check this run has, and that nothing else in the suite tolerates a failure |
| This report's own sources | 19 | That every issue below still cites real code, in both languages |
| This report itself | 35 | That it is reproducible from the run above, invents no issue, and drops none that was not agreed to be left alone |
| every test in this run | 1546 |  |

### What this round did not reach

The table above counts what was checked; it is not a list of what the application does.  A feature can appear in it because one narrow thing about it is checked -- that a button un-greys when it should, say -- while what the button produces is never read.  Where that is true of something this build added, the issue below says so in its own words.  Read a row as *this much was checked*, and an absent row as nothing at all.

## Summary

| ID | Priority | Status in this run | Issue |
| --- | --- | --- | --- |
| CBDB-D-006 | P6 | APPARENTLY FIXED | Three pages show text in the wrong script for the language chosen: a fixed bilingual title and placeholders written into the page that the language switch never rewrites |

## Table of contents

- [CBDB-D-006 — Three pages show text in the wrong script for the language chosen: a fixed bilingual title and placeholders written into the page that the language switch never rewrites](#cbdb-d-006--three-pages-show-text-in-the-wrong-script-for-the-language-chosen-a-fixed-bilingual-title-and-placeholders-written-into-the-page-that-the-language-switch-never-rewrites)
- [Severity legend](#severity-legend)
- [Reproducing this report](#reproducing-this-report)

## CBDB-D-006 — Three pages show text in the wrong script for the language chosen: a fixed bilingual title and placeholders written into the page that the language switch never rewrites

**Affected area:** Association Pairs, Associations and Texts pages

**Severity:** P6 — Wording — a label on a page says the wrong thing, or says it in the wrong script, in one of the three display languages (English, Traditional or Simplified Chinese).  Judged against the CBDB label glossary by fixed rules; nothing the application computes is affected, but a reader can be misled about what a control does.

**Where it comes from:** `software` — In the application: cbdb.exe, its Go sources, its page templates, or the database builder's logic.  Fixed by the CBDB-Desktop developers.

**Status in this run:** APPARENTLY FIXED

> The tests that demonstrated this no longer fail. Please confirm, and this entry can be retired.

#### Description

Five strings, all written straight into the HTML where `setLanguage` does not reach them.  With 繁 chosen, Associations shows the placeholder `(关系)` and Texts `(全部地点)`, both Simplified.  With 简 chosen, Associations keeps its fixed bilingual title `CBDB: Look At Associations / 查看關係`, Texts keeps the column header `書名`, and Association Pairs keeps the placeholder `[漢字]`, all Traditional.  Down from 14 strings on seven pages in 20261021, and the four Simplified labels containing `數` are gone.  The developers' conventions note lists both causes as open across forms: "Page titles are fixed text on Associations and Browser" and "Placeholders ... are English or fixed Chinese on every form".

#### Evidence

`test_each_chinese_language_shows_only_its_own_script` presses each page's own 繁 and 简 buttons in Chromium and judges what is on screen -- only strings that occur in the template and are not in its translation table, so CBDB data shown on the page is not judged and nothing is counted twice.  A character is flagged only when every OpenCC conversion into the chosen script -- mainland, Taiwan and Hong Kong standards -- changes it, in context and on its own.  The table check, `test_every_chinese_label_is_written_in_its_own_script`, passes on every page.

#### Impact

A reader who chose one script sees the other in a title, two placeholders and one column header.  Cosmetic, but it is what a reader who chooses 繁 or 简 notices first.

#### Steps to reproduce

1. Open Look At Associations and press 简.
2. Read the title bar: CBDB: Look At Associations / 查看關係, still in Traditional characters.

#### Suggested fix

Give the Associations title, the three placeholders and the Texts column header a key in the page's translation table, as the other labels already have.

#### Where it lives in the build

- `Templates/associations/index.html:11 (the fixed title)`
- `Templates/associations/index.html:38 (placeholder="(关系)")`
- `Templates/texts/index.html:90 (placeholder="(全部地点)")`
- `Templates/texts/index.html:170 (<th>書名</th>)`
- `Templates/association_pairs/index.html:50 (placeholder="[漢字]")`

#### Demonstrated by

- 12 × passed: `test_each_chinese_language_shows_only_its_own_script[association_pairs]`, `test_each_chinese_language_shows_only_its_own_script[associations]`, `test_each_chinese_language_shows_only_its_own_script[browser]`, `test_each_chinese_language_shows_only_its_own_script[entry]` (+8)

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

That stages the archive, launches the shipped binary against a private copy of the shipped database, runs 1546 tests, and rewrites these files. The suite never writes to the reference copy of `Data/CBDB.db` — every test runs against a per-session copy, so a run leaves the distribution exactly as it found it.

The test that demonstrates each issue is named under it. To run just one:

```powershell
python -m pytest tests -k test_searching_people_by_name_finds_them -v
```


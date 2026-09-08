# cbdb-desktop-tests

Automated regression tests for **CBDB-Desktop** — the Go + SQLite
rewrite of the China Biographical Database front end, shipped as
`cbdb-desktop_<YYYYMMDD>.zip` (`Bin/cbdb.exe`, `Data/CBDB.db`,
`Templates/`, `Static/`, and the `Code/` Go sources).

The suite tests **the shipped build itself**. It stages the archive,
launches the real `cbdb.exe` against the real 1.2 GB `CBDB.db`, and
drives its real HTTP endpoints. Nothing in this repo re-implements an
application query in Python: where a test needs an oracle it uses the
shipped database, a second endpoint of the same app, or a frozen golden
— never a hand-written transcription of the Go logic, which would only
test the transcription.

**On the 2026-09-07 build it finds nine defects.** Four of the six it
reported against 2026-09-01 are fixed; one is not, for a reason the
remediation could not have found by the method it used. The nine:

- every exported CSV is UTF-8 with no byte-order mark, so Excel opens it
  in the system code page and every Chinese name is mojibake;
- a multi-file export saves only the first file and reports that it
  saved them all;
- Run Query stays greyed out on the Networks form after the page is
  reopened, with the person still selected;
- four export buttons fail on every input (three on Networks, one on
  Associations);
- two KML exports produce a file no mapping tool will open;
- thirty Query Builder columns do not exist under the names it offers;
- two browser tabs share one result;
- unticking every category on the Places form still returns
  biographical addresses.

Where they cluster is the point. Six are about exports and three are in
the pages' own JavaScript — the two places the suite had no coverage at
all, and between them most of where a user's experience of the
application actually happens. Runs against the previous build reported
no export problems while driving 6 of the 42 file-producing endpoints;
the first run that pressed the other 36 found four defect families in
one go. So the suite now enumerates its own coverage from the build
rather than trusting a test plan, and drives the pages in a real browser
for the layer HTTP cannot reach.

The findings are reported in English and Traditional Chinese, as
Markdown, Word and PDF, all regenerated from every run:
[`CBDB_Desktop_Issues_EN.md`](./reports/CBDB_Desktop_Issues_EN.md) ·
[`CBDB_Desktop_Issues_ZH-Hant.md`](./reports/CBDB_Desktop_Issues_ZH-Hant.md).

---

## Setup

```powershell
git clone <this repo>
cd cbdb-desktop-tests
python -m pip install -r requirements.txt
copy .env.example .env      # then edit CBDB_DESKTOP_ZIP
.\run_tests.ps1
```

The only required setting is the archive under test:

```ini
CBDB_DESKTOP_ZIP=C:\Users\<you>\Dropbox\cbdb-desktop_20260901.zip
```

Everything else in [`.env.example`](./.env.example) is optional and
documented inline (work directory, timeouts, browser suppression, or
`CBDB_APP_DIR` to test an already-unpacked tree).

`run_tests.ps1` archives the previous run, stages the distribution, runs
the tests with a JSON report, and regenerates the issues report. Useful
flags: `-Restage`, `-Fast` (skip everything needing the running app),
`-Filter <k>` (pass `-k` to pytest), `-DryRun`. Or drive pytest directly
with `python -m pytest tests -q` (~68 s; `-m "not slow"` runs in ~28 s,
leaving out the index-address rebuilds and the master's `quick_check`).
The full `run_tests.ps1` takes ~87 s — the extra is report generation,
most of it Word starting twice to write the PDFs.

---

## What it covers

| file | what it tests |
|---|---|
| `test_staging.py` | that the tree under test really is the shipped archive |
| `test_app_driver.py` | that the binary starts, serves, and lets go cleanly |
| `test_routes.py` | all 141 registered routes, pages, navigation, pickers, static |
| `test_lookups.py` | the code and address lists the forms offer before a query |
| `test_qbe.py` | the Query Builder: whitelist, generated SQL, and its guards |
| `test_form_queries.py` | the six forms that keep no working list: queries and exports |
| `test_stateful_forms.py` | kinship, networks, association pairs, group data — the forms that keep a working list |
| `test_index_addr.py` | index-address rankings: the only endpoints that rewrite CBDB data |
| `test_exports.py` | **every one of the 42 file-producing endpoints**, driven for real: envelope, file names, format, the people named, repeatability, and what happens with nothing to export |
| `test_query_matrix.py` | every form × dynasty × half-century × address combination the shipped data has rows for, discovered rather than hand-picked |
| `test_scratch_tables.py` | who owns each `ZZ_*` table, and whether the code's declarations match the database |
| `test_sessions.py` | what happens when the application is used from two tabs, or launched twice |
| `test_ui_pages.py` | the pages in a real Chromium: do they load without throwing, and does each control un-grey when its precondition is met |
| `test_zz_controls.py` | every button in every template, and whether this run actually requested what each can reach |
| `test_defect_registry.py` | that every recorded defect still cites real code, in both languages |

The route list is not maintained by hand: `cbdb_desktop/routes.py` reads
the registrations out of the shipped `Code/*.go` and the tests drive
whatever it finds, so a route that disappears in a future build fails
here rather than going unnoticed.

### How a defect is recorded

A test that has found a real defect has to do three things at once: stay
out of the way of a green run, say what is wrong on every run, and
*notice when the defect is fixed*.

So each one is `xfail(strict=True, raises=KnownShippedDefect)`, quoting
the registry in `tests/cbdb_desktop/defects.py`, and raises that
exception only after confirming the exact known signature. The known
failure is tolerated; a *different* failure of the same test is still a
failure; and a fix turns the test green-unexpectedly, which pytest
reports as an error so the marker gets removed.
`reports/generate_report.py` then writes both language editions from
that registry plus the outcomes of an actual run — so a report cannot
claim a defect the tests no longer show, and the two translations cannot
drift from each other either.

```powershell
python reports\generate_report.py                # .md + .docx + .pdf, both languages
python reports\generate_report.py --format md    # Markdown only
python reports\generate_report.py --lang zh      # Chinese only
```

The `.md` files are committed; the `.docx` and `.pdf` are generated on
demand and gitignored, because their internal timestamps change on every
regeneration and would dirty the tree on every run. The PDF is produced
by Word itself through COM: these documents are bilingual, and Word
already has the CJK fonts and line-breaking rules. Without Word the
Markdown and Word files are still written and the generator says which
format it could not produce.

### Staging

The archive unpacks to `work/stage/<name>_<size>_<fingerprint>/`, where
the fingerprint is a SHA-256 of the archive's bytes (~0.3 s for 430 MB).
Keying on content rather than timestamps matters here: the archive lives
in Dropbox, which rewrites mtimes on re-download, and a rebuild must
never be served from the previous build's cache.

Staging is crash-safe — extraction goes to a process-unique `.partial-*`
directory and the existing tree is only moved aside once the new one is
complete, so an interrupted or failed restage never destroys the build
you already had. Superseded trees of the same archive are pruned; other
archives' trees are left alone. Nothing under `work/` is committed.

```powershell
python stage.py                  # stage (or reuse a cached tree), print the path
python stage.py --force          # discard the cached tree and restage
python -m pytest tests --restage # same, from inside a run
```

`staging.integrity_mismatches()` then verifies the staged tree against
the archive's own central directory — size and CRC for every shipped
file (~0.1 s for the whole 122 MB immutable payload), plus a SHA-256 of
the master database and a check that nothing the archive never shipped
is sitting in the tree. This runs on **every cache hit**, not only when
a test asks, so a tree damaged after extraction is restaged rather than
served. It is the provenance guarantee the rest of the suite rests on.

The database is pinned to the hash it had when staging finished rather
than to the archive's CRC, because staging may legitimately have changed
it: if a distribution ever ships a non-empty write-ahead log, it is
checkpointed into the database before the sidecars are dropped — the
oracle opens the master with `immutable=1`, which would otherwise ignore
those committed frames without a word.

### The pristine master

The staged tree is never run against. Each session copies
`Data/CBDB.db` into `work/run/<id>/` and points the app there, because
a form query can rewrite the shared `ZZ_SCRATCH_*` tables in whatever
database the app was given — entry and associations do during a query,
and the stateful forms do far more. That split keeps the master byte-stable
(usable as an oracle, and comparable to the archive) and stops one
session's scratch state from contaminating the next. Set
`CBDB_KEEP_RUN_DIR=1` to keep a session's copy for post-mortem.

---

## Layout

```
cbdb-desktop-tests/
├── .env.example              # every setting, documented
├── tests/
│   ├── cbdb_desktop/         # infrastructure only — no oracle SQL
│   │   ├── config.py         # .env / environment resolution
│   │   ├── staging.py        # cached, crash-safe unpack + integrity check
│   │   ├── app.py            # launches and drives the real cbdb.exe
│   │   ├── routes.py         # reads the routing table out of Code/*.go
│   │   ├── forms.py          # how to phrase each form's query and export
│   │   └── defects.py        # the registry of what has been found
│   ├── conftest.py           # session fixtures: layout, app_db, app, oracle
│   └── test_*.py
├── AGENTS.md                 # context for future agent sessions
├── docs/skills/              # read the relevant one before starting
├── stage.py                  # stage the archive without running pytest
├── run_tests.ps1             # stage → test → report, in one command
├── reports/
│   ├── generate_report.py    # run + defect registry → both reports
│   ├── CBDB_Desktop_Issues_EN.md
│   └── CBDB_Desktop_Issues_ZH-Hant.md
└── work/                     # gitignored — the staged distribution
```

---

## Working on this suite

[`AGENTS.md`](./AGENTS.md) is the context file for anyone — human or
agent — picking this up: what the system under test is, the landmines
that have already cost time here, and the workflow after a new
distribution zip.

Four repo-local skills in [`docs/skills/`](./docs/skills):

| Skill | Read it before |
|---|---|
| [`oracle-discipline.md`](./docs/skills/oracle-discipline.md) | writing or reviewing any assertion |
| [`cbdb-desktop-probe.md`](./docs/skills/cbdb-desktop-probe.md) | driving the real binary, or writing a probe script |
| [`issue-report-maintainer.md`](./docs/skills/issue-report-maintainer.md) | adding, changing or retiring a defect |
| [`programmer-self-review-template.md`](./docs/skills/programmer-self-review-template.md) | reporting any change back |

`oracle-discipline.md` is the one that matters most. Two oracles in this
repo were written, reviewed, and only then found to be true by
construction; that skill is how to spot the shape before it is committed.

---

## Design rules

1. **No transcription.** The code under test is `Bin/cbdb.exe`. Tests
   exercise it through HTTP and judge it by invariants, cross-endpoint
   agreement, the shipped database, and frozen goldens.
2. **Loud, not skipped.** A missing zip, an incomplete tree, or an app
   that will not start fails the session. A suite that silently tests
   nothing is worse than one that fails.
3. **Read-only on the shipped data.** The oracle opens the master
   `mode=ro&immutable=1` — so consulting it creates no sidecars — and the
   app writes only to its per-session copy of the database. The oracle
   may query base tables for invariants and cross-checks; it must never
   read `ZZ_*` tables or reproduce a backend's join/filter chain, which
   would test the transcription instead of the application.
4. **Everything machine-specific lives in `.env`.** No path is hardcoded
   in a test.
5. **An existence check must not run the application's queries.** No form
   query applies a LIMIT, so an unfiltered probe is a query over the
   whole database — and it leaves the shared scratch tables full, which
   makes every later test order-dependent.

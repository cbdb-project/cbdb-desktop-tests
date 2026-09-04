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

**On the 2026-09-01 build it finds six defects**, two of them high
severity: one breaks the main way of finding a person, one silently hands
the user an empty export, and one lets a malformed request rewrite the
index address of every person in the database. See
[`reports/CBDB_Desktop_Issues.md`](./reports/CBDB_Desktop_Issues.md),
which is regenerated from every run.

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
with `python -m pytest tests -q` (~70 s; `-m "not slow"` skips the index-address rebuilds and runs in ~25 s).

---

## What it covers

| file | what it tests |
|---|---|
| `test_staging.py` | that the tree under test really is the shipped archive |
| `test_app_driver.py` | that the binary starts, serves, and lets go cleanly |
| `test_routes.py` | all 141 registered routes, pages, navigation, pickers, static |
| `test_lookups.py` | the code and address lists the forms offer before a query |
| `test_qbe.py` | the Query Builder: whitelist, generated SQL, and its guards |
| `test_form_queries.py` | the six read-only form queries and their exports |
| `test_stateful_forms.py` | kinship, networks, association pairs, group data — the forms that keep a working list |
| `test_index_addr.py` | index-address rankings: the only endpoints that rewrite CBDB data |

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
every form query rewrites the shared `ZZ_SCRATCH_*` tables in whatever
database the app was given. That split keeps the master byte-stable
(usable as an oracle, and comparable to the archive) and stops one
session's scratch state from contaminating the next. Set
`CBDB_KEEP_RUN_DIR=1` to keep a session's copy for post-mortem.

---

## Layout

```
cbdb-desktop-tests/
├── .env.example              # every setting, documented
├── tests/
│   ├── cbdb_desktop/         # infrastructure only — no query logic
│   │   ├── config.py         # .env / environment resolution
│   │   ├── staging.py        # cached, crash-safe unpack + integrity check
│   │   ├── app.py            # launches and drives the real cbdb.exe
│   │   ├── routes.py         # reads the routing table out of Code/*.go
│   │   ├── forms.py          # how to phrase each form's query and export
│   │   └── defects.py        # the registry of what has been found
│   ├── conftest.py           # session fixtures: layout, app_db, app, oracle
│   └── test_*.py
├── stage.py                  # stage the archive without running pytest
├── run_tests.ps1             # stage → test → report, in one command
├── reports/
│   ├── generate_report.py    # run + defect registry → both reports
│   ├── CBDB_Desktop_Issues_EN.md
│   └── CBDB_Desktop_Issues_ZH-Hant.md
└── work/                     # gitignored — the staged distribution
```

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

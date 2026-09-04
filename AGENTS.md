# AGENTS.md — context for future agent sessions on this project

Read this before touching anything. It is the accumulated cost of the
mistakes already made here, written down so nobody pays for them twice.

Sibling project: `../cbdb-user-mdb-tests` tests the Access `.mdb` front
end. Same purpose, completely different system under test, **no shared
code**. Do not import from it, and do not assume anything you know from
it applies here.

---

## What this project is

CBDB-Desktop is the Go + SQLite rewrite of the China Biographical
Database front end, shipped to historians as
`cbdb-desktop_<YYYYMMDD>.zip`:

```
Bin/cbdb.exe          a Go HTTP server (gorilla/mux), ~33 MB
Data/CBDB.db          1.2 GB SQLite, 658,941 people; 124 tables (incl.
                      sqlite_stat1 and four ZZZ_NAMES_FTS_* shadow
                      tables) and 19 views
Data/qbe_schema.json  the Query Builder's table/column whitelist
Templates/<form>/     one index.html per form, plus pickers/ and qbe/
Static/               one stylesheet
Code/*.go             the full source of the binary above
CBDBSetUpCode/*.go    the source of the separate database builder
```

This repo runs that binary and asks it questions over HTTP. It exists to
catch what a data refresh or a rebuild breaks, and to hand the CBDB team
a report they can act on.

**Current state: 253 tests, 212 passing, 41 xfailed against six
confirmed defects.**  Measured: the tests take ~68 s, and
`.\run_tests.ps1` takes ~87 s end to end -- the extra ~13 s is
`generate_report.py`, most of it Word starting twice to write the PDFs.

New here?  `README.md` has the three-line setup (install, copy
`.env.example` to `.env`, point `CBDB_DESKTOP_ZIP` at the distribution
zip).  Nothing below works until that is done.

---

## ⛔ ABSOLUTE PROHIBITION: never re-implement the application in Python

The code under test is `Bin/cbdb.exe`. If a test computes what the answer
*should* be by running its own version of the handler's SQL, that test
checks the copy — and the copy will be written by reading the original,
so it will agree with it, including where the original is wrong.

This has been violated twice in this repo and caught both times in
review. Both times the reasoning that led there sounded fine:

1. A search test counted matching rows in `ZZZ_NAMES` with the same two
   `LIKE` clauses the handler uses. It was not merely a copy — it was
   *guaranteed* to agree, because for short patterns SQLite scans that
   very table on both sides. It could only ever confirm the SQL had been
   transcribed correctly.
2. An address test re-ran one of the handler's two inner joins to predict
   how many rows a picker returns. Passing today, and it would have
   raised a false alarm against the handler the day a `c_belongs_to` did
   not resolve.

### What IS allowed as an oracle

| Oracle | Example |
|---|---|
| The HTTP contract | status codes, declared JSON keys, 405 on the wrong verb |
| Agreement between two of the app's own outputs | the export vs. the grid it rendered; kinship's person-count vs. networks' |
| **Base facts** from the shipped DB | `COUNT(*)` of one table; "is this code in `ADDR_CODES`" |
| The Go source read as **data** | the list of registered routes; the `/{page}` map |
| Frozen goldens | "the address picker returns 37,118 rows for 29,932 addresses" |
| Internal invariants of one response | every returned row carries a code that was asked for |
| Choosing a cheap **input** from the data | "which entry codes have 2–12 rows" — selects an input, predicts nothing |

### The test that decides

Ask: **would this assertion still be meaningful if the handler were
rewritten from scratch to the same specification?** If yes, it is an
oracle. If it would have to be rewritten alongside the handler, it is a
transcription.

Second test, just as important: **could this assertion fail?** Several
tests here were written, reviewed, and found to be true by construction:

- `count == len(records)` — the Go assigns the count from the slice length.
- `edge endpoints ⊆ node list` — the node list is built *from* the edges.
- `one_code_result ⊆ both_codes_result` — holds when the filter is
  ignored entirely, and when it returns nothing.

The fix for the third was to compare `Counter` of `(person, code)` pairs
for A, B and A+B and assert `a + b == together`, which is false in both
degenerate cases. Look for that shape.

---

## ⭐ Mission-critical landmines

### 1. Never run the application against the staged master

`work/stage/<key>/Data/CBDB.db` is the reference copy. The application
writes shared `ZZ_SCRATCH_*` tables — which queries do so is set out in
§3 — so a single run against the master can make it differ from the
archive and poison every later comparison. Merely opening it in WAL mode
already leaves sidecars behind.

The suite copies it per session (`app_db` fixture, ~0.5 s). If you write
an ad-hoc probe script, copy the database first.

Two guards, and it is worth knowing which is which:

* `sqlite_conn` calls `pytest.fail` if a `-wal` sits beside the master
  (`conftest.py:223`). Fast, but partial: it fails the tests that
  *request that fixture*, not the run; SQLite removes the `-wal` on a
  clean close, so a probe that ran against the master and exited
  tidily slips past it; and it is skipped entirely under
  `CBDB_APP_DIR`.
* `integrity_mismatches()` re-checks `master_db_sha256` on **every**
  cache hit (`staging.py:329`). That is the guard that actually
  notices a modified master, and it restages rather than serving it.

A probe of mine tripped the first one exactly once; the second is what
would have caught it either way.

### 2. No form query applies a LIMIT

There is no server-side cap anywhere. One entry code returned **89 MB of
JSON**. A route-existence check that POSTed `{}` to every endpoint took
**143 seconds** and left the shared scratch tables full of whatever those
probes computed — quietly making every later test order-dependent.

- Existence probes use `PATCH`, a verb no route registers: mux answers
  405 if the path exists and 404 if it does not, and no handler runs.
- Query tests pick filter codes with 2–12 rows in the base table, **and
  then verify against the app that the code returns something** — four of
  five candidate text ids have base rows and produce no result.

### 3. The scratch tables are global, and shared across forms

One `ZZ_SCRATCH_IMPORT_PEOPLE`, one `ZZ_STORE_PERSON_ID`, one
`ZZ_SOCIAL_NETWORK` for the whole application. Consequences:

- Kinship and Networks are two views of one working list.
- Associations' export re-reads `ZZ_SOCIAL_NETWORK`, which Association
  Pairs and Networks clear — that is defect **CBDB-D-004**.
- `GET /api/browser/person/{id}/kinship` **writes**: it truncates
  `ZZ_KIN_LIST`, `ZZ_KIN_LIST_TMP`, `ZZ_SCRATCH_KIN`, `ZZ_SCRATCH_KINNET`.
  It is the only read-looking endpoint that does.
- Of the six forms that keep no working list (entry, office, status,
  texts, places, associations), only **entry** (`ZZ_SCRATCH_ENTRY`) and
  **associations** (`ZZ_SOCIAL_NETWORK`, `ZZ_SCRATCH_PEOPLE`) write
  during a query; the other four build their result in one SELECT. Do
  not repeat the claim that "every query mutates" — it is wrong, and it
  sat in a docstring here for a while.

`pytest.ini` sets `-p no:randomly -p no:xdist`. Module order is load
bearing: `test_stateful_forms.py` must run last, and one server over one
global namespace cannot be parallelised.

### 4. IndexAddr rewrites real CBDB data

`/api/indexaddr/update` and `/reset` are the only endpoints that write to
`BIOG_MAIN` rather than scratch — 659k rows, and the rebuild is **not
atomic across its two transactions**. `test_index_addr.py` therefore gets
its own `CbdbApp` on its own database copy. Never point those endpoints
at the session database.

### 5. The app opens a browser on startup

`main.go`'s `openBrowser` fires 300 ms after the port is announced and
only *logs* a failure. Launching with `PATH=""` makes `rundll32`
unresolvable, so the window never opens and the app is otherwise
unaffected (its own DLLs load from the loader's search path, not PATH).
`CBDB_SUPPRESS_BROWSER=0` turns this off.

### 6. The port is only knowable from stderr

`-port 0` lets the OS choose. The app prints
`CBDB server started: http://localhost:<port>` through Go's `log`, i.e.
to **stderr**. The driver must keep draining that pipe for the whole run
or a full buffer stalls the server mid-suite. `CbdbApp` reads it on a
thread and hands the thread its own process handle — reading
`self.process` raced with `stop()` clearing it and lost the app's dying
words exactly when they were needed.

### 7. This box's shell quirks

- The Bash tool mangles `\n` and `\r` inside heredocs. A `.\run_tests.ps1`
  written that way became `.` + newline + `un_tests.ps1` in the README.
  Use the Edit/Write tools for anything containing backslash escapes.
- PowerShell 5.1: no `&&`, no ternary. `Invoke-Expression $cmd` returns
  the command's stdout *and* the exit code — pipe to `Out-Host` first, or
  `$code -ne 0` compares an array and is always true.
- `Set-StrictMode` makes reading an absent JSON property fatal;
  pytest-json-report omits `failed` entirely when it is zero.

---

## Repo layout

```
tests/cbdb_desktop/     infrastructure only — no *oracle* SQL lives here
  config.py             .env resolution; nothing else reads os.environ
  staging.py            content-addressed, crash-safe unpack + integrity
  app.py                launches and drives the real cbdb.exe
  routes.py             reads the routing table out of Code/*.go as DATA
  forms.py              how to phrase each form's query and export
  defects.py            the defect registry, in English and Chinese
tests/test_*.py         the tests themselves
reports/generate_report.py   registry + one run → both reports, 3 formats
run_tests.ps1           stage → test → report, one command
stage.py                stage without running pytest
work/                   gitignored: the staged distribution (1.4 GB)
```

---

## Build-test cycle

```powershell
.\run_tests.ps1              # everything: stage, test, both reports
.\run_tests.ps1 -Restage     # discard the cached tree first
.\run_tests.ps1 -Fast        # skip everything needing the running app
python -m pytest tests -q                 # ~68 s
python -m pytest tests -q -m "not slow"   # ~28 s
```

`-m "not slow"` deselects 10 tests: the nine index-address ones (each
update is a ~659k-row rebuild) **and**
`test_master_database_is_clean_and_valid`, which is the master's
`PRAGMA quick_check`. Use it while iterating, not to certify a build.

Staging is content-addressed on a SHA-256 of the archive's bytes, and a
**cache hit re-verifies every immutable file** against the archive's
recorded CRCs (~0.1 s) plus a SHA-256 of the database. A tree damaged
after extraction is restaged, not served.

---

## Confirmed defects in the shipped build

Full accounts, in both languages, in `reports/CBDB_Desktop_Issues_*.md`.
The registry is `tests/cbdb_desktop/defects.py`.

| id | pri | what |
|---|---|---|
| CBDB-D-001 | P0 | Person search finds nothing for terms of three or more characters |
| CBDB-D-004 | P0 | Another form's query silently empties the Associations export |
| CBDB-D-006 | P1 | A malformed ranking is accepted and applied to every person |
| CBDB-D-002 | P2 | The Query Builder offers 30 columns that do not exist |
| CBDB-D-005 | P3 | The release ships a previous session's working state |
| CBDB-D-003 | P4 | A name is indexed for a person the database does not contain |

Those titles are copied from the registry verbatim, and
`test_defect_registry.py` keeps the rest of each entry honest -- it
checks that every `source` reference still resolves in the staged
build, that both languages are filled in, and that the named tests
exist. Do not paraphrase a title here: "an Association Pairs query"
and "an 8-slot ranking" were both wrong, because Networks and Kinship
trigger D-004 too and an 11-slot ranking is accepted as well.

**Two things that look like defects and are not** — check before filing:

- `/api/addresses` returns 37,118 rows for 29,932 addresses. The handler
  inner-joins `ADDR_BELONGS_DATA`; each row carries its own year range.
- IndexAddr's duplicate check stops at the first disabled slot. So does
  the code that writes the ranks, *and* the rebuild. All three agree, so
  a duplicate hidden behind a gap is accepted and then ignored.

---

## How a defect is recorded

Never a bare `assert`. Every defect is:

```python
@pytest.mark.xfail(strict=True, raises=KnownShippedDefect,
                   reason=BY_NAME["name-search"].reason)
def test_...:
    ...
    if <the exact known signature>:
        raise KnownShippedDefect("...")
    assert <what should happen>
```

That combination is doing three jobs: the run stays green (a permanently
red suite trains people to ignore it), the reason prints on every run,
and a **fix** turns the test green-unexpectedly, which pytest reports as
an error so the marker gets removed. Narrowing to `raises=` is what stops
the marker from swallowing a *different* failure of the same test.

See `docs/skills/issue-report-maintainer.md` before adding or changing
one.

---

## Standard workflow after a new distribution zip

```powershell
# 1. Point .env at the new archive
#    CBDB_DESKTOP_ZIP=...\cbdb-desktop_<new date>.zip

# 2. Run everything.  Staging notices the new fingerprint by itself.
.\run_tests.ps1

# 3. Read the failures, in this order:
#    - XPASS  → a defect was fixed.  Confirm, then remove its marker and
#               its registry entry.
#    - FAILED on a pinned count (141 routes, 1350 QBE columns, 37,118
#               addresses, the form-template set) → the build changed
#               shape.  Decide whether that is intended, then update the
#               pin in the same commit as the reason.
#    - FAILED anywhere else → a new regression, or a new defect.

# 4. New defect?  Verify it end to end BEFORE filing (see the skill),
#    add it to defects.py in both languages, wire the xfail, rerun.

# 5. Commit the regenerated reports/*.md alongside the code.
```

---

## Operating principles

These are the ones that actually bit during this project.

1. **Send every increment through review before moving on.** Agents
   first, then `codex exec --dangerously-bypass-approvals-and-sandbox`,
   until neither has a serious finding. This caught a 7.5 GB temp leak, a
   transcription, and several oracles that were true by construction.
2. **Mutation-test the infrastructure.** Break `staging.py` on purpose
   and see whether the suite notices. Nine deliberate breaks were tried;
   **six survived** the first version of the tests.
3. **Verify a defect before writing it down.** For CBDB-D-001 the
   decisive experiment was running the rebuild on a copy and re-testing
   through the same binary. Do the equivalent every time, and try hard to
   find the innocent explanation first.
4. **A reviewer's claim is a hypothesis.** One review said the IndexAddr
   duplicate check had a hole. Reading two more call sites showed it did
   not. Another said an 8-element ranks array would be applied — that one
   was real, and became CBDB-D-006.
5. **Pin exactly, not with a floor.** `>= 10 forms` survives a build that
   drops four of them. Every count in this suite is exact, and a
   legitimate change is expected to fail a test and be read.
6. **Say what a test actually proves.** Four of the six export
   comparisons here only check that JSON field names still line up. The
   docstrings say so. A docstring that overstates is worse than none.

---

## Skills

`docs/skills/` — read the relevant one before starting:

| Skill | Read it before |
|---|---|
| `cbdb-desktop-probe.md` | driving the real binary, or writing a probe script |
| `oracle-discipline.md` | writing or reviewing any assertion |
| `issue-report-maintainer.md` | adding, changing or retiring a defect |
| `programmer-self-review-template.md` | reporting any change back |

---

## Memory

Anything true only of one person's machine -- local paths, personal
preferences -- lives in the assistant's own memory directory, not here.

§7 is the deliberate exception: those quirks belong to *Windows plus
this harness*, not to one laptop, and every agent working on this repo
will hit them. Anything else that is genuinely machine-specific should
not be added to this file.

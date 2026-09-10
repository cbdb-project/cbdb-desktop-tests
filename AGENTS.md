# AGENTS.md — context for future agent sessions on this project

Read this before touching anything. It is the accumulated cost of the
mistakes already made here, written down so nobody pays for them twice.

Sibling project: `../cbdb-user-mdb-tests` tests the Access `.mdb` front
end. Same purpose, completely different system under test, **no shared
code**. Do not import from it, and do not assume anything you know from
it applies here.

**Do not go and read it, either.** Everything from that project that
applies to this one has been absorbed into this file and into
`docs/skills/`: the data-driven input rule (§ *Inputs come from the
data*), the per-control coverage rule (§ *Coverage is the program's job*),
the build-independence rule (§ *Every run is a fresh assessment*), and
the prohibition on re-implementing the system under test (§ *ABSOLUTE
PROHIBITION*). If you find yourself wanting an answer from over there,
the answer belongs here and is missing — add it here.

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

**Current state: 1135 tests collected, and the defect registry
holds this round's findings.**  It was cleared on 2026-09-08, together
with the previous round's reports and every run artefact, so that this
distribution was assessed with no carried-over knowledge of what an
earlier build did -- and it has since been filled by *this* round, which
is the whole of its intended life: it is emptied again before the next
one.  Do not read it as an inventory of what CBDB-Desktop does wrong --
§ *Every run is a fresh assessment*, taken to its limit at the
maintainer's request.  What was removed is the *expectation*: the nine
registry entries and every `xfail` marker that quoted them.  What was
kept is the *detection*: the tests still raise `KnownShippedDefect` on
the exact signatures they check for, so a defect that is still there
reports as an ordinary **failure** with its signature in the message,
and is triaged and re-filed from scratch.  Expect the first run on a new
build to be red, and read every failure as a lead rather than a
regression.

For scale, from the last measured round (2026-09-07 build, cold
restage): ~280 s for the tests, of which the browser tests are ~110 s,
plus ~15 s for `generate_report.py` (most of that is Word starting twice
to write the PDFs).  Every skip says what it could not judge and why -- a discovered
combination with no rows, a file with no non-ASCII text, a switch whose
two positions this data cannot distinguish -- which is also why the
passed/skipped split moves by one or two between runs.

There is no expected-failure count to read any more, and that is
deliberate -- see § *How a defect is recorded, and how one is
tolerated*. A failure is either something to fix, something to file, or
something to agree to leave alone in the waiver table; it is never
something the suite quietly expects.

Of those tests, 254 are generated from the shipped data
(`test_query_matrix.py`, including the switch sweep) and 247 from the
build's own export and control inventories -- see § *Coverage is the
program's job*.  The run's measured endpoint coverage is written to
`artifacts/endpoint_coverage.json`; last measured, on the 2026-09-07
build, **105 of 105** endpoints reachable from the user interface were
actually requested, with nothing excused.
Enable-state coverage is the honest counterpart: 14 of the 106 controls
that ship `disabled` have a declared precondition, and the other 92 are
pinned in `test_ui_pages.UNDECLARED`, which may only shrink.

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

## ⭐ Where a defect comes from — and therefore who fixes it

Every defect this suite files carries an **origin**, and it is not a
label for tidiness: it decides who the finding is sent to. The
maintainer of this repo fixes the data problems himself, in the CBDB
source, and does **not** want them going to the CBDB-Desktop
developers. Sending a data problem to a programmer wastes the one
channel this project has, and it also reads as a false accusation about
code that is working correctly.

`ORIGINS` in `tests/cbdb_desktop/defects.py` is the machine-readable
version; the report prints it beside the priority.

| origin | means | fixed by |
|---|---|---|
| `software` | the application: `cbdb.exe`, the Go sources, the page templates, or the database builder's *logic* | the CBDB-Desktop developers |
| `data` | the data arriving from the CBDB (MariaDB) source: a missing row, a dangling reference, a column whose values are not what its name suggests | **the CBDB data team — this repo's maintainer.** Not a programmer's problem |
| `release` | how this particular archive was assembled: a working copy shipped instead of a fresh build, a file not regenerated | whoever builds the distribution |

### The deciding experiment

Always the same one, and it is worth actually running rather than
reasoning about:

> **Would this survive a rebuild of the database from the current CBDB
> source, using this same code?**

If yes, it is in the code. If a clean rebuild makes it disappear, it was
in the data or in the packaging, and no code change would have prevented
it. Two of the six defects in the 2026-09-01 build were settled exactly
this way:

- **The orphaned indexed name** (a name indexed for a person
  `BIOG_MAIN` did not contain) looked like a bug in the name
  derivation. Rebuilding
  `ZZZ_NAMES` from a clean copy made the orphan vanish — every row the
  derivation writes is read out of `BIOG_MAIN` or reached through an
  INNER JOIN against it, so it *cannot* invent an orphan. Origin:
  `data`. The 2026-09-07 build ships zero orphans, as a clean rebuild
  should.
- **The shipped working state** (fourteen scratch tables holding a
  previous session's work) looked like a provisioning bug. It was a working copy sent out
  in place of a built one. Origin: `release`. Nothing was patched, and
  `test_a_fresh_install_starts_with_no_working_state` is now the only
  thing that would notice it happening again — which is the reason to
  keep that test rather than delete it with the defect.

### Where it goes wrong

The trap is a `data` problem that *looks* like `software` because the
application handles it badly.  **The Associations Neo4j export** is
the model: it dies scanning `ADDR_CODES.c_admin_type` into
an integer, and that column has held text in every build — names like
`State` and `Shengshi`, all 30,100 rows. The data is doing nothing
wrong. The code assumed a code where the schema declares
`varchar(255)`. Origin: `software`, and the fix is one `Scan`.

So the question is not "which side is unusual" but the experiment
above: no refresh of the source data will ever make that scan succeed.

---

## ⭐ Coverage is the program's job, not the agent's

The rule the maintainer stated, and the one that shapes this repo:

> **Put repeatable test logic into the program. Do not rely on an agent
> devising a fresh test plan each round.**

A plan an agent writes each time is a plan that covers what that agent
happened to think of. Measured against the build, it was covering 6 of
the 42 file-producing endpoints while every run reported no export
problems. The first run that pressed the other 36 found four defect
families, two of them buttons that answer HTTP 500 on every input and
always have.

So the suite carries **four inventories, each derived from the build
under test, each with a gate that fails when the build grows something
the inventory does not know about**:

| inventory | derived from | gate |
|---|---|---|
| `routes.py` | `Code/*.go` route registrations | `test_routes.py` — every route driven or probed, counts pinned |
| `exports.py` | the same, filtered to file-producing endpoints | `test_exports.py::test_every_export_route_is_driven` |
| `controls.py` | `Templates/*/index.html` buttons and their JS call graphs | `test_zz_controls.py` — every UI-reachable endpoint was **actually requested** in this run |
| `discovery.py` | the shipped database's own row counts | `test_query_matrix.py::test_the_discovered_matrix_covers_every_form_and_dimension` |

Three properties make these worth more than a checklist:

1. **They are extracted, not written.** A new export button, a new
   route, a new page appears in the inventory by itself and fails the
   gate until someone declares how to drive it. Nobody has to remember.
2. **Coverage is measured, not claimed.** `CbdbApp.requested` records
   every `(method, path)` the run issues; `test_zz_controls.py` compares
   that record against every endpoint the shipped pages can reach and
   writes the number to `artifacts/endpoint_coverage.json`. "We tested
   the exports" is not evidence. A count is.
3. **An empty parametrization is a failure, not a pass.** pytest reports
   "0 tests collected for this parameter" as green. Every generated
   matrix here therefore has a companion test asserting the matrix is
   populated — that is what `test_the_discovered_matrix_covers_every_form
   _and_dimension` is for, and it is not optional decoration.
4. **A gate that can skip itself is not a gate.** The endpoint-coverage
   gate refuses to judge a filtered run, and its first version decided
   "filtered" by comparing pytest's path argument against the literal
   `"tests"` — while `run_tests.ps1` passes an *absolute* path. So the
   gate skipped in every canonical run, two cold runs went green with
   no coverage measured, and the only trace was a missing
   `artifacts/endpoint_coverage.json`. The predicate now has its own
   unit test (`test_the_filter_predicate_recognises_the_canonical_run`)
   because no assertion *inside* a skipping test can catch this. If a
   test can decide not to run, something else has to check that
   decision.

### Inputs come from the data

Never hand-pick a code, a dynasty or a year window. Half the time it
lands on sparse data, the query returns nothing, and the assertions run
against an empty list — a test that proves nothing and looks exactly
like one that passes.

`cbdb_desktop/discovery.py` asks the shipped database which
`(code, dynasty)`, `(code, half-century)` and `(code, address)`
combinations are populated, caches the answer against the database's own
SHA-256, and `test_query_matrix.py` generates one test per combination
(234 of them on this build). A data refresh moves the inputs by itself.

**Choosing an input from the data is not an oracle. Predicting a count
from the data is.** The discovery queries do join a base table to
`BIOG_MAIN`, which is also what a handler does, and the distinction is
exactly this:

- allowed: *"which (entry code, dynasty) pairs have at least 20 rows"* —
  the answer is a request to send. If it is wrong, the test still checks
  what it claims, on a less interesting input.
- forbidden: *"the join says 47 rows, so the form must return 47"* —
  that is the handler's SQL retyped, agreeing with the original wherever
  the original is wrong.

What the matrix asserts instead are properties that hold whatever CBDB
contains and that a handler cannot satisfy by accident: every row
satisfies the filter it was given (ask for dynasty 15, get only dynasty
15; ask for 1000–1049, get no nulls and nothing outside it), narrowing
never adds rows, and two adjacent half-centuries stay disjoint while
their union fits inside the span covering both.

### Vary every adjustable option, and compare against what should have happened

The matrix has two halves, because the forms' controls do.

**Filters with a value** — codes, dynasty, year window, address — are
covered by `discovery.py` feeding `test_query_matrix.py`: observe the
data, classify it by density, sample the populated combinations, drive
each one, and check the properties that must hold (every row satisfies
the filter, narrowing never adds, adjacent windows stay disjoint).

**Filters with a switch** — 21 booleans and modes across the six forms
— are covered by `forms.TOGGLES` feeding
`test_a_switch_changes_the_result_in_the_direction_it_claims`. Each
switch is declared with a **direction** read off the request struct's
own meaning:

| direction | means | example |
|---|---|---|
| `WIDENS` | turning it on can only add rows | `includeSubUnits` |
| `NARROWS` | turning it on can only remove rows | `mainSourceOnly` |
| `DIFFERS` | it changes the result, in no fixed direction | `addressFrame` (person's address vs. the entry's) |

The test runs the query twice, off and on, and checks the direction —
plus a second property that is the one that actually catches a dead
option: **the two results must differ**. A handler that decodes a field
and never uses it satisfies every direction check, in both directions,
for ever.

**A skip here is a lead, not a pass.** When the two results are
identical the test skips, because "the option is ignored" and "this data
has nothing on the other side of it" look the same from one switch. Read
those skips. Five of the Places form's seven category switches skipped
on every input tried, and the way to settle it was not a better input
but a different experiment: **turn all seven off at once.** A user who
selects no categories has asked for nothing, so nothing is the only
defensible answer, and the request needs no special data. That found
the Places form's category substitution in one call.

That is the general shape when a per-option sweep cannot decide:
> find the combination whose *correct* answer is fixed regardless of the
> data, and ask for that.

All-off, all-on, a filter value nothing matches, two disjoint windows —
each has an answer that does not depend on what CBDB contains, which is
what makes it an oracle.

### The browser layer: what only a browser can see

Everything except `test_ui_pages.py` talks HTTP, and that covers what
the server computes and nothing about what the user gets. Four of the
2026-09-07 round's findings lived in that gap, and three of them arrived
as the maintainer's own reports rather than as a test failure. The
*shapes* are what to carry forward, not the ids:

| the server | the user |
|---|---|
| answers every request correctly | a button is grey with its precondition met |
| returns both files, identically, every time | gets one file and is told it got two |
| writes valid UTF-8 | opens it in Excel and sees mojibake |
| applies a documented fallback | gets a category they unticked |

`cbdb_desktop/browser.py` drives the shipped pages in a real Chromium
through Playwright and reports three things a page cannot hide: what it
logged, what it downloaded, and which of its controls are disabled.
`test_ui_pages.py` uses it for the two questions nothing else can ask:

1. **Does every page load without throwing?** A page that raises while
   attaching its handlers leaves every control inert — and every HTTP
   test still passes. Thirteen page loads, and the page list is read
   out of the routing table.
2. **Is every control that ships disabled enabled by its
   precondition?** 106 controls ship `disabled`. `PRECONDITIONS`
   declares what a user does and what that must un-grey;
   `UNDECLARED` pins the rest, may only shrink, and is the honest count
   of what this file does *not* check.

Three traps, all paid for:

* **Use `127.0.0.1`, never `localhost`.** A Chromium that resolves the
  name to `::1` against a server bound to IPv4 reports
  `ERR_CONNECTION_REFUSED`, which reads exactly like a broken
  application. `browser.open_page` rewrites it.
* **A headless browser with `accept_downloads=True` is not the user's
  browser.** It saves every file, so Chrome's multiple-download
  permission — the whole blocking half of the multi-file download
  finding — never engages.
  Anything that turns on a browser *permission* has to be checked
  another way; for that one, by reading the page's delivery code.
* **Skip, do not fail, when Chromium is absent.** Playwright downloads
  its own browser and a fresh checkout has none. `browser.available()`
  returns the reason and the tests skip with it; a suite that goes red
  on a missing optional dependency teaches people to ignore it.

### Reproduce it yourself — including your own findings

The rule the maintainer stated, and it applies to a report from him just
as much as to one from you:

> Do not just take my word for it; reproduce it. And not only the one
> problem — find all of them.

Two of this round's defects were filed from a mechanism read out of the
source plus the maintainer's observation, and reproducing them changed
what they say:

* **The multi-file download finding.** Driving the real page in
  headless Chromium showed the page attempting two downloads per
  press and the browser accepting
  **both**, on both presses. The count-reporting half is confirmed by
  automation; the blocking half is not reproducible that way. The
  defect's evidence now says which is which, and that is a better bug
  report than the confident version was.
* **The Places category substitution.** The "no categories selected"
  result looked like an ignored switch. Reading `places_form_backend.go:204` showed a
  deliberate fallback, so the defect is not "the switch does nothing"
  but "the page lets you reach a request the backend has to guess at" —
  a different fix, in a different file.

Two mistakes of my own from the same session, in the same spirit:

* I derived `/LookAtPlaces` from the `places/` template directory, got a
  404, and briefly had a "broken page" finding. The route is
  `/LookAtPlace`. `routes.py` exists so that nothing has to guess at the
  build; the test now reads the page list from it.
* I read Chrome's own error page — `chrome-error://chromewebdata/`,
  every element missing, every function undefined — and nearly
  concluded that the Networks form was structurally destroyed. Check
  `location.href` before believing a DOM.

### Every run is a fresh assessment

`defects.py` describes **the build under test**, not the history of the
project. When a defect is fixed, its entry is deleted and its markers
come off in the same commit — it does not become an entry saying "fixed
in 2026-09-07". The git history of that file is the record of what each
build did, and it is a better record than a growing list of resolved
items that nobody re-reads and that makes a reader of the current report
guess which half applies to them.

Corollary, and it has teeth: **never drop a finding because a previous
build called it fixed.** Judge each build on its own run and its own
source. The three dead Networks exports predate every build
this suite has seen; it survived a remediation session aimed at the very
tables it touches, and it would have been reasoned away by anyone
diffing against the last report.

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

### 3. The scratch tables are per form since 2026-09-07 — and still global per *request*

This changed under the suite, and both halves matter.

**What the 2026-09-07 build fixed.** The shared tables behind the
cross-form interference were split into one copy per form: `ZZ_SOCIAL_NETWORK` →
`ZZ_SN_ASSOC` / `ZZ_SN_ASSOC_PAIR` / `ZZ_SN_NETWORK`,
`ZZ_SCRATCH_PEOPLE` → `ZZ_SP_*`, `ZZ_SCRATCH_IMPORT_PEOPLE` →
`ZZ_SIP_*`. So:

- Associations' export is no longer emptied by an Association Pairs,
  Networks or Kinship query. `test_another_form_does_not_empty_the_
  associations_export` drives all three and is an ordinary assertion now.
- **Kinship and Networks no longer share a working list.** They used to
  be two views of one table and always reported the same
  `person-count`; each now has its own `ZZ_SIP_*`. Any fixture that
  "resets the application" by calling one form's clear endpoint leaves
  the others populated — that bit exactly once, and
  `test_stateful_forms.py::WORKING_LIST_RESETS` is the fix.
- Kinship has **no** clear endpoint (its page has no Clear button;
  both list-filling endpoints truncate first). Emptying its list means
  importing an empty one.
- The three old tables still ship, still empty, used by nothing.
  `test_scratch_tables.py::EXPECTED_ORPHANS` pins that, plus five more
  left over from the VBA original.
- `ZZ_STORE_PERSON_ID` is still global and is now the *only* cross-form
  channel. That is the feature: it is how a result travels between forms.

**What it did not fix.** Nothing in a request identifies the tab or the
session it came from, so two browser tabs still share one result — the
developers' own open finding, driven here by `test_sessions.py` and
tolerated in the waiver table. `main.go` also takes no single-instance lock and
uses port 0, so `cbdb.exe` can be launched twice against the same
database; the in-process mutexes protect nothing across processes.

**Still true, and still worth not re-learning:**

- `GET /api/browser/person/{id}/kinship` **writes**: it truncates
  `ZZ_KIN_LIST`, `ZZ_KIN_LIST_TMP`, `ZZ_SCRATCH_KIN`, `ZZ_SCRATCH_KINNET`.
  It is the only read-looking endpoint that does.
- Of the six forms that keep no working list (entry, office, status,
  texts, places, associations), only **entry** (`ZZ_SCRATCH_ENTRY`) and
  **associations** (`ZZ_SN_ASSOC`, `ZZ_SP_ASSOC`) write during a query;
  the other four build their result in one SELECT. Do not repeat the
  claim that "every query mutates" — it is wrong, and it sat in a
  docstring here for a while.

`test_scratch_tables.py` is where all of this is asserted rather than
believed: the ownership map is extracted from the shipped Go and pinned,
so a refactor that re-shares a table fails there.

`pytest.ini` sets `-p no:randomly -p no:xdist`. Module order is load
bearing: `test_stateful_forms.py` must run late and `test_zz_controls.py`
must run **last** (it judges the whole run's request record), and one
server over one global namespace cannot be parallelised.

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

- The Bash tool mangles backslash escapes inside heredocs. A
  `.\run_tests.ps1` written that way became `.` + newline +
  `un_tests.ps1` in the README; a `re.compile(r"\bZZ_...")` written the
  same way became a literal backspace character (`\x08`), so the pattern
  silently matched nothing and a coverage test reported perfect
  coverage of zero tables. Both cost half an hour. **Use the
  Edit/Write tools for anything containing a backslash escape**, and if
  you must patch through Bash, check afterwards:
  `python -c "import pathlib; [print(p) for p in pathlib.Path('tests').rglob('*.py') if any(c < 9 for c in p.read_bytes())]"`
- PowerShell 5.1: no `&&`, no ternary. `Invoke-Expression $cmd` returns
  the command's stdout *and* the exit code — pipe to `Out-Host` first, or
  `$code -ne 0` compares an array and is always true.
- **Never `2>&1` a native command in PowerShell 5.1.** It wraps every
  stderr line in a `NativeCommandError`, which with
  `$ErrorActionPreference = "Stop"` aborts the script. `stage.py` prints
  its progress to stderr, so `.\run_tests.ps1 -Restage 2>&1 | Tee-Object`
  fails at staging with a `RemoteException` and no test ever runs.
  Redirect stdout only (`> file`); stderr is captured anyway.
- `Set-StrictMode` makes reading an absent JSON property fatal;
  pytest-json-report omits `failed` entirely when it is zero.

---

## Repo layout

```
tests/cbdb_desktop/     infrastructure only — no *oracle* SQL lives here
  config.py             .env resolution; nothing else reads os.environ
  archives.py           reads a .zip or a .7z distribution as members
  staging.py            content-addressed, crash-safe unpack + integrity
  app.py                launches and drives the real cbdb.exe; records
                        every (method, path) for the coverage gate
  routes.py             reads the routing table out of Code/*.go as DATA
  forms.py              how to phrase each form's query, export and filters
  exports.py            the 45-endpoint export inventory (envelope, files)
  controls.py           every button in Templates/, and what it calls
  discovery.py          picks populated inputs out of the shipped database
  defects.py            this round's findings, in English and Chinese --
                        read only while its report is written
  waivers.py            the optional CBDB_WAIVERS table: outcomes agreed
                        to leave alone, keyed by test function name
tests/test_*.py         the tests themselves
  test_waivers.py         the waiver table, and the ban on any other
                          way to tolerate a failure
  test_reports.py         the report: reproducible, invents nothing,
                          drops nothing, hides no waiver
  test_zz_controls.py     ...runs LAST: judges the whole run's coverage
reports/generate_report.py   registry + one run → both reports, 3 formats
run_tests.ps1           stage → test → report, one command
stage.py                stage without running pytest
artifacts/              gitignored: app logs, test_inputs.json,
                        endpoint_coverage.json, waivers_applied.json —
                        a run's measurements
work/                   gitignored: the staged distribution (1.4 GB)
```

The five modules above the registry are the whole of § *Coverage is the
program's job*: four inventories derived from the build, plus the driver
that records what was actually requested. Adding a test that drives
something new by hand, instead of adding it to the inventory that
covers its kind, is how this decays.

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

**Not listed here, deliberately.**  The registry
(`tests/cbdb_desktop/defects.py`) was emptied on 2026-09-08 for a
stateless assessment of this distribution, and now holds that
assessment's findings.  Read it there, or read the generated reports;
copying the list into this file is what would turn one round's findings
into an expectation the next round starts from.

There is no *inventory* here of what earlier builds did, and that is the
point.  The record is the git history of `defects.py` and of
`reports/CBDB_Desktop_Issues_*.md`; reading it before a fresh round is
exactly what this clearing exists to prevent, because a reader who knows
last round's nine findings looks for those nine.  If you want to know
what an earlier build did *after* forming your own judgement,
`git log -p tests/cbdb_desktop/defects.py` has it.

Be exact about what that forbids, because this file does describe past
defects and has to.  A **checklist** is banned: nothing here may read as
"these are the things to look for in this build".  A past defect used to
teach **method** stays — how an origin was decided, why a landmine is a
landmine, what a reviewer's claim turned out to be worth — because that
is what a context file is for, and losing it costs the next round the
same afternoon twice.  The examples in § *Where a defect comes from* and
§ *Operating principles* are there on that basis; none of them names an
identifier, because an identifier belongs to one round's report and
points at a different finding by the next.

What survived the clearing is every mechanism that finds a defect: the
inventories, the discovered matrix, the browser layer, and each test's
`raise KnownShippedDefect(<the exact signature>)`.  Only the `xfail`
markers and the registry entries came off, so the first run on a new
build reports its findings as **failures**.  Triage each one, verify it
end to end (§ *Reproduce it yourself*), and file it into the empty
registry in both languages -- see
`docs/skills/issue-report-maintainer.md`.

Two things from earlier rounds that are method, not findings, and worth
carrying:

* **Where defects clustered was not a coincidence:** the exports and the
  pages' own JavaScript, which is where most of a user's experience of
  this application actually happens.  Press every export and load every
  page before concluding a build is clean.
* **Never drop a finding because a previous build called it fixed**, and
  equally never re-add one because an earlier report had it.  Both are
  the same mistake: judging this build by the last one.

One piece of *build* knowledge worth keeping, because it changes how a
test must be read rather than asserting anything about a defect: as of
the 2026-09-07 build, `buildCleanRanks` does **not** reject a malformed
index-address ranking, it reinterprets it.  A short array's zero padding
is "not set" rather than address type 0; a repeated address type is
silently folded to its first occurrence instead of rejecting the whole
request; and a gap no longer truncates the ranking, because survivors
are packed to the front.  That is why several tests in
`test_index_addr.py` assert the new behaviour rather than a 400, and why
one (`test_a_short_ranking_is_applied_as_exactly_what_it_named`) asserts
the thing that actually mattered: nothing the request did not name comes
back as a priority.  Read it before touching that file.

`test_defect_registry.py` is what keeps a filed entry honest -- it
checks that every `source` reference still resolves in the staged build,
that both languages are filled in, and that the named tests exist.  With
an empty registry it collects one test and reports the rest as an empty
parameter set, which pytest prints as a skip; that is the correct
reading of "there is nothing to check yet", and those skips should come
back as tests the moment a defect is filed.  Do not paraphrase a title
when you file one: "an Association Pairs query" and "an 8-slot ranking"
were both wrong in an earlier round, and a wrong title in a report costs
the whole report its credibility.

**Things that look like defects and are not** — check before filing.
Each of these was investigated and left alone; the reasoning is in the
named test, and re-deriving it costs an hour.

- `/api/addresses` returns 37,118 rows for 29,932 addresses. The handler
  inner-joins `ADDR_BELONGS_DATA`; each row carries its own year range.
- `/api/indexaddr/codes` returns 20 rows while `/rankings` returns 22.
  Deliberate as of 2026-09-07: `[Missing Data]` (-1) and `unknown` (0)
  are real `BIOG_ADDR_CODES` rows and not valid choices, and offering a
  value the backend must discard is what installed the bogus rank in
  a ranking sent with fewer slots than the form offers. The contract is
  now inclusion in each
  direction, not
  equality — see `test_the_dropdown_offers_only_address_types_that_can_
  be_ranked`.
- A duplicate address type behind a disabled slot is accepted and
  ignored. It used to be safe by coincidence (all three functions that
  walked the array stopped at the first gap); it is now safe on purpose
  (`buildCleanRanks` drops repeats before any of them runs). Same
  observable result, which is why the test did not change.
- `ZZ_KIN_LIST_TMP` is declared with 3 columns in the Networks backend
  and 32 in the Kinship backend. Latent, not live: the table ships with
  all 32 and `CREATE TABLE IF NOT EXISTS` is a no-op, so nothing is
  broken today. It would bite on the first database that did not
  already have the table. Pinned in `test_scratch_tables.py`, worth
  mentioning to the developers, not worth a P-band in a report of
  things users can see.
- A form query with an **empty** code list returns the whole table
  (264,775 entry rows). No filter, no LIMIT, and the page never sends
  it. Do not construct "export nothing" that way — use a code no table
  contains (`test_exports.py::_NO_SUCH_CODE`).
- The export envelopes are inconsistent — `{status, files}` on seven
  forms, `{files}` on two, a bare `{name, url}` for every SNA export,
  and a raw file stream for six of the GIS exports. Nobody chose that,
  and it is pinned per endpoint in `exports.py` rather than filed,
  because on most forms no user can see it. A form that *changed* which
  one it answers with would break its own page, and that is what the pin
  catches.

  **Amended 2026-09-10, and this is the shape of the correction rather
  than an exception to the rule.** The ruling above turned on "no user
  can see it", and it was never checked against the pages — only against
  the handlers, which agree with themselves. One page does not agree with
  its handlers: Association Pairs throws unless the reply carries
  `status === 'ok'`, so on that form the bare `{name, url}` is four
  export buttons that report an error on exports that succeeded, and it
  is filed. (No identifier here on purpose: the number belongs to one
  round's report and would point at something else by the next.) The pin
  in `exports.py` still
  stands for the other forms and still describes what they answer with;
  what changed is that a *page* now has to be read before "no user can
  see it" may be said. The old ruling's last sentence had the answer in
  it — "a form that changed which one it answers with would break its
  own page" — and nobody had asked whether a form already had.

---

## ⭐ How a defect is recorded, and how one is tolerated

Two different things, deliberately in two different places, and neither
of them is a marker next to a test.

### Found: the test says which failure it found

```python
def test_...:
    ...
    if <the exact known signature>:
        raise KnownShippedDefect("<the signature, in the message>")
    assert <what should happen>
```

`KnownShippedDefect` is an `AssertionError`, so this **fails**. That is
the point: the suite reports what the build does, and a finding stays a
failure until somebody fixes it or somebody agrees to leave it. What the
`raise` buys over a bare `assert` is the message -- the exact signature
that was recognised, so triage starts from "this is the known shape"
rather than from a diff of two numbers.

There is no `xfail` anywhere in this suite, and
`test_waivers.py::test_no_test_file_expects_a_failure_of_its_own` reads
every test module's syntax tree to keep it that way. The reason is worth
stating, because the marker model is what this repo used until
2026-09-08 and it fails in a specific way: a marker quotes a registry
entry, the registry entry survives into the next round, and from then on
the suite measures the registry rather than the build. The first agent
to assess a new distribution starts by reading nine findings and looks
for those nine.

### Filed: the registry, for as long as it takes to write the report

`tests/cbdb_desktop/defects.py` holds one round's findings while that
round writes its report, in both languages, each entry citing where it
lives in the build and which tests demonstrate it.
`reports/generate_report.py` renders it plus that run's JSON; the next
round starts empty. Nothing else reads it, and
`test_waivers.py::test_the_registry_is_not_wired_into_any_expectation`
enforces that: no test module may import anything from the registry but
`KnownShippedDefect`. `test_defect_registry.py` keeps a filed entry
honest -- the sources it cites resolve in the staged build, both
languages are filled in, the tests it names exist -- and
`test_reports.py` keeps the report honest about the registry: rendered
twice it is byte-identical, it names no issue the registry does not
hold, it drops none, and it hides nothing that was waived.

See `docs/skills/issue-report-maintainer.md` before adding or changing
an entry.

### Tolerated: the waiver table, keyed by the program's own names

Some findings are negotiated rather than fixed -- "yes, that is wrong;
for our readers it does not matter this year". That is legitimate, and
it is the one thing that has to persist across rounds, so it lives in a
table **outside** the suite, at `CBDB_WAIVERS` — pointed by
`.env.example` at this repo's own committed `waivers.toml`, so a fresh
checkout judges the build the way the maintainer does:

```toml
[test_an_export_produces_a_well_formed_file]
params    = ["entry:kml", "places:kml"]
reason    = "Agreed 2026-09-10: the KML preamble is cosmetic for us."
reason_zh = "2026-09-10 協商：KML 檔頭對我們的使用者只是外觀問題。"
agreed_by = "maintainer"
agreed_on = 2026-09-10
expires   = 2026-12-01          # optional; past it, the run goes red
```

**The key is a test function's name, plus the parametrisation ids it
ran with, and that is not a convenience.** It is the only address that
survives a stateless round: an id of our own -- `W-001`, or one of the
`CBDB-D-0NN` numbers a round assigns -- is given out while one report
is written and points at nothing the next time the table is read, or
worse, at whatever the next round gave that number to. A function name is part of the program; rename
or delete the test and the table stops matching and says so, which is
exactly the failure mode a waiver list must have. (Quote the key when it
carries a module: `["test_exports.py::test_x"]`.)

The rest of the design, in one place -- `tests/cbdb_desktop/waivers.py`:

| | |
|---|---|
| `mode = "tolerate"` (default) | the test still runs; a failure becomes a **strict** xfail, so the waived thing going away is reported and the waiver gets retired. A waiver is not a way to stop measuring |
| `mode = "skip"` | the test does not run. Costs coverage: a skipped test issues no requests, so `test_zz_controls.py` may fail *because* of the waiver -- correctly. Needs a `note` saying why `tolerate` would not do |
| `raises = "KnownShippedDefect"` | narrows the tolerance to the recognised signature, so an unrelated crash of the same test still fails. The only value allowed |
| unset `CBDB_WAIVERS` | no waivers at all. Comment the line out of `.env` to see what a build really does, with nothing tolerated |
| set but missing or malformed | the run stops. A table that silently fails to load would quietly re-expose everything in it, with the run looking normal |
| a waiver matching nothing | `test_waivers.py` fails, naming the collected ids it could not match. A mistyped waiver un-waives what it meant to cover, and the failure then reads as a fresh regression |
| every applied waiver | recorded in `artifacts/waivers_applied.json` and printed in **both** reports with its reason, who agreed and when. Nothing is tolerated invisibly |

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
3. **Verify a defect before writing it down.** For the unbuilt name
   index, the decisive experiment was running the rebuild on a copy
   and re-testing
   through the same binary. Do the equivalent every time, and try hard to
   find the innocent explanation first.
4. **A reviewer's claim is a hypothesis.** One review said the IndexAddr
   duplicate check had a hole. Reading two more call sites showed it did
   not. Another said an 8-element ranks array would be applied — that
   one was real: a ranking sent with fewer slots than the form offers
   had the rest filled from whatever was there before.
5. **Pin exactly, not with a floor.** `>= 10 forms` survives a build that
   drops four of them. Every count in this suite is exact, and a
   legitimate change is expected to fail a test and be read.
6. **Say what a test actually proves.** Four of the six export
   comparisons here only check that JSON field names still line up. The
   docstrings say so. A docstring that overstates is worse than none.
7. **Write the check into the program, not into the plan.** If you find
   yourself deciding *which* buttons to press, *which* codes to use or
   *which* endpoints matter, stop: that decision belongs in an
   inventory the next run inherits. An agent's judgement is the part
   that does not survive to the next build. See § *Coverage is the
   program's job*.
8. **Prefer the check that needs no query.** An unclosed XML
   declaration and a column that does not exist are both findable by
   reading the shipped source, and both have a test
   that does exactly that alongside the one that drives the endpoint.
   A defect that cannot depend on data should not need data to find,
   and a source-level test says *where* the fix goes.
9. **Two checks in two places beat one.** The developers shipped
   `Code/qbe_schema_test.go` against the Query Builder offering a
   column the database lacks — a correct check, using
   `PRAGMA table_info`, that would have caught what their other
   verification missed — and it skips itself unless run from the
   project root, so it never ran. Independent duplication is cheap
   insurance; a check that can silently skip is not a check.

---

## Skills

`docs/skills/` — read the relevant one before starting:

| Skill | Read it before |
|---|---|
| `cbdb-desktop-probe.md` | driving the real binary, or writing a probe script |
| `oracle-discipline.md` | writing or reviewing any assertion |
| `coverage-inventories.md` | adding coverage of anything — an endpoint, a button, a filter |
| `issue-report-maintainer.md` | adding, changing or retiring a defect, or waiving one |
| `programmer-self-review-template.md` | reporting any change back |

---

## Memory

Anything true only of one person's machine -- local paths, personal
preferences -- lives in the assistant's own memory directory, not here.

§7 is the deliberate exception: those quirks belong to *Windows plus
this harness*, not to one laptop, and every agent working on this repo
will hit them. Anything else that is genuinely machine-specific should
not be added to this file.

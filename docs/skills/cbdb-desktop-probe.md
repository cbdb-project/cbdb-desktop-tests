# Skill: cbdb-desktop-probe

**Status:** repo-local (2026-09-04). Read before launching the real
`cbdb.exe`, writing a probe script, or adding a test that drives an
endpoint the suite has not touched yet.

## When to use

- Investigating whether a suspected defect actually fires
- Writing a new test against an endpoint with no coverage
- Reproducing something a maintainer reported
- Measuring what an endpoint costs before committing to a test

If the question can be answered from the shipped `Code/*.go`, from
`Data/qbe_schema.json`, or from a read-only SQLite query against the
staged master, do that first — it is faster and it cannot break anything.

## The three rules

### 1. Never run the application against the staged master

`work/stage/<key>/Data/CBDB.db` is the reference. A single query against
it rewrites `ZZ_SCRATCH_*` and makes it differ from the archive, which
poisons the provenance check and every oracle that reads it.

In a test, use the fixtures. `app` is the session's server, already on a
per-session copy of the database (`app_db`). The one exception is
`index_addr_app` in `test_index_addr.py`: those endpoints rewrite
`BIOG_MAIN`, so they get their own server on their own copy. If you add
a test that writes real CBDB data, follow that pattern rather than
reaching for `app`.

In a scratch script, copy first:

```python
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]   # or the repo root, however you got here
sys.path.insert(0, str(REPO / "tests"))

from cbdb_desktop.app import CbdbApp
from cbdb_desktop.config import load_config
from cbdb_desktop.staging import stage_once

cfg = load_config()
layout = stage_once(cfg)     # stage_once, not stage: never stage twice
                             # in one process (see staging.stage_once)

# A fresh copy every time, outside the repo.  Reusing a leftover
# probe.db inherits the last run's ZZ_SCRATCH_* state and produces a
# wrong answer with no symptom -- which is the whole hazard this skill
# exists to prevent.  And .gitignore has no *.db rule, so a copy left in
# the working tree is 1.2 GB that `git add -A` will happily stage.
scratch = Path(tempfile.mkdtemp(prefix="cbdb-probe-"))
try:
    work = scratch / "CBDB.db"
    shutil.copyfile(layout.db, work)         # ~0.5 s -- inside the try, so
                                             # an interrupted copy is cleaned
                                             # up rather than left at 1.2 GB
    with CbdbApp(layout, work, cfg) as app:  # always a context manager
        print(app.json("GET", "/api/health"))
finally:
    shutil.rmtree(scratch, ignore_errors=True)
```

There are two guards. `sqlite_conn` calls `pytest.fail` if a `-wal` sits
beside the master — fast, but it only fails the tests that request that
fixture, it is skipped under `CBDB_APP_DIR`, and a probe that exits
cleanly leaves no `-wal` to find. The one that always catches a modified
master is `integrity_mismatches()`, which re-checks the database's
SHA-256 on every cache hit and restages rather than serving it. If
either fires, find what ran against the master, then
`python stage.py --force`.

Read-only inspection of the master is fine, with `immutable=1` so no
sidecars are created:

```python
conn = sqlite3.connect(layout.db.resolve().as_uri() + "?mode=ro&immutable=1",
                       uri=True)
```

### 2. Assume every query is unbounded

No form query applies a `LIMIT`. Measured here: one entry code returned
**89 MB**; POSTing `{}` to every endpoint took **143 seconds**.

- Pick filter codes with a handful of base rows, then confirm through the
  app that they return something — base rows do not guarantee results.
- Bound every traversal: `maxLoop: 1`, `maxNodeDist: 1`, kinship
  distances at 1. They come straight off the request with no server-side
  cap.
- Never probe existence with a real call. `PATCH` gives 405 (exists) or
  404 (gone) and reaches no handler.

### 3. Leave no process behind

`CbdbApp.stop()` is what releases the database; a leaked `cbdb.exe` keeps
a 1.2 GB copy locked and undeletable on Windows. Use `with`, or
`try/finally`. To check afterwards:

```powershell
Get-CimInstance Win32_Process -Filter "Name='cbdb.exe'" |
    Select-Object ProcessId, CommandLine
```

## What the driver already handles

`tests/cbdb_desktop/app.py`:

- **Browser suppression.** `openBrowser` runs 300 ms after startup and
  only logs a failure, so the app is launched with `PATH=""` and
  `rundll32` cannot be resolved. Its own DLLs are unaffected.
- **Port discovery.** `-port 0`, and the port is read from
  `CBDB server started: http://localhost:<port>` on **stderr**. The
  output is drained continuously on a thread — Go logs every request, and
  a full pipe buffer stalls the server mid-run.
- **Failure messages that quote the app.** Every `AppError` carries the
  application's own output. If you add a code path that can fail, keep
  that property; "connection refused" without the `log.Fatalf` line
  behind it is an hour of guessing.
- **Explicit flags.** Every path is passed on the command line rather
  than relying on `main.go`'s defaults, so a changed default fails a test
  instead of silently repointing the app at the master.

## Endpoint facts worth knowing before you probe

| Thing | Fact |
|---|---|
| Response shape | Some forms answer with a bare array (entry, office, texts, places), some with an object (status → `{status, people}`, associations → `{records, people}`, kinship → three keys, networks → three keys) |
| Status form | Registers at the top level: `/api/query-status`, `/api/export-results` — not under `/api/status/` |
| Status query | Uses `yearFilter`, not `yearFilterType`, and a different vocabulary |
| Networks query | `kinParam` is a **bool**, not an int |
| Kinship / networks | Take their subject from `ZZ_SCRATCH_IMPORT_PEOPLE`, set by `set-person` / `import-people` — not from the query body |
| Exports | Two families: base64 data URLs inside JSON (most), and streamed `Content-Disposition` (the `export-gis` of six forms) |
| Entry + associations exports | Ignore the request body entirely and dump the scratch tables |
| `store-person-ids` | Kinship and Networks answer **409** if the store is non-empty; the other six overwrite silently |
| `GET .../person/{id}/kinship` | Writes. The only read-looking endpoint that does |
| IndexAddr | The only endpoints that rewrite `BIOG_MAIN`. Use a separate app on a separate copy |

## Useful probe recipes

**Small filter codes for a form**

```python
codes = [r[0] for r in conn.execute(
    'SELECT c_entry_code FROM ENTRY_DATA GROUP BY c_entry_code '
    'HAVING COUNT(*) BETWEEN 2 AND 12 ORDER BY COUNT(*) DESC LIMIT 5')]
```

...then keep only those that actually return rows through the app.

**Decode an export**

```python
import base64, csv, io
text = base64.b64decode(url.split("base64,", 1)[1]).decode("utf-8")
rows = list(csv.reader(io.StringIO(text), delimiter="\t"))
```

**Time an endpoint before trusting it in a test**

Everything in this suite is measured. If a call takes more than a second,
say so in the docstring and mark the test `slow`.

## Where to put a scratch script

The scratchpad directory, never the repo — a stray 1.2 GB `.db` in the
working tree is not gitignored, and `git add -A` will stage it. The
recipe above puts its copy under `tempfile.mkdtemp()` and deletes it in a
`finally` for that reason; keep that shape rather than reusing a copy
between runs.

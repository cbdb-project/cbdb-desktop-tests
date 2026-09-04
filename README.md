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
captured from a blessed build — never a hand-written transcription of
the Go logic, which would only test the transcription.

---

## Setup

```powershell
git clone <this repo>
cd cbdb-desktop-tests
python -m pip install -r requirements.txt
copy .env.example .env      # then edit CBDB_DESKTOP_ZIP
python -m pytest tests -q
```

The only required setting is the archive under test:

```ini
CBDB_DESKTOP_ZIP=C:\Users\<you>\Dropbox\cbdb-desktop_20260901.zip
```

Everything else in [`.env.example`](./.env.example) is optional and
documented inline (work directory, timeouts, browser suppression, or
`CBDB_APP_DIR` to test an already-unpacked tree).

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
│   │   └── staging.py        # cached, crash-safe unpack + integrity check
│   ├── conftest.py           # session fixtures: layout, app_db, sqlite_conn
│   └── test_staging.py       # staging unit tests + distribution integrity
├── stage.py                  # stage the archive without running pytest
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

"""Choose test inputs from the data, not from memory.

A query test is only as good as what it queries.  Pick an entry code and
a dynasty by hand and half the time the combination has no rows at all:
the test passes, the assertions never run against anything, and nothing
has been checked.  That failure is silent and it looks exactly like
success, which is what makes it worth a module of its own.

So the inputs are **discovered**: this module asks the shipped database
which combinations are populated, and the tests are generated from the
answer.  Every code, dynasty, century and address the matrix drives came
out of the build under test, so a data refresh that moves the mass of
CBDB from one century to another moves the tests with it, and a code
table that gains rows gets covered without anybody editing a list.

**This is input selection, and nothing here is an oracle.**  The
distinction is the one AGENTS.md turns on, and it is worth being exact
about, because the queries below do join a base table to ``BIOG_MAIN``
-- which is also what a handler does.

    Allowed: "which (entry code, dynasty) pairs have at least 30 rows in
    ENTRY_DATA joined to BIOG_MAIN" -- a question whose answer is a
    *request to send*.  If the answer is wrong, or the join is not the
    one the handler uses, the test still checks exactly what it claims:
    it just checks it on a less interesting input.

    Not allowed, and not done here: "ENTRY_DATA joined to BIOG_MAIN has
    47 rows for this pair, therefore the form must return 47".  That
    would be the handler's SQL retyped, agreeing with the original
    wherever the original is wrong, and it would false-alarm the day the
    handler legitimately adds a join.

What the tests do with these inputs is assert properties that hold
whatever the counts are -- every row satisfies the filter it was given,
narrowing a filter cannot add rows, two disjoint windows cannot overlap.
See test_query_matrix.py.

**Freshness is explicit, not silent.**  The result is cached in
``artifacts/test_inputs.json`` alongside the SHA-256 of the database it
came from, and re-computed when that no longer matches.  A stale cache
would defeat the whole point, and a cache keyed on anything less exact
than the database's own hash is a stale cache waiting to happen.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .forms import FORMS, FormSpec

#: How many rows a (code, ...) combination needs in the base data before
#: it is worth driving.  Not a prediction of the result size -- the
#: handler may return more rows (one per address) or fewer (an inner
#: join that drops people) -- just a floor that keeps the matrix off
#: combinations with nothing in them.
MIN_ROWS = 20

#: And a ceiling, because no form query applies a LIMIT: one popular
#: entry code returned 89 MB of JSON while this suite was being written.
MAX_ROWS = 400

#: How many values to keep per dimension.  Three is enough for the
#: properties being checked (a subset relation, a partition, a pair of
#: disjoint windows) and keeps the matrix inside a minute.
KEEP = 3

CACHE_VERSION = 2


@dataclass(frozen=True)
class Combination:
    """One row of the matrix: a form, a code, and the filter to add."""

    form: str
    #: The code values to filter on.
    codes: tuple[int, ...]
    #: Which dimension this combination exercises: "code", "dynasty",
    #: "century" or "address".
    dimension: str
    #: The dynasty code, when dimension == "dynasty".
    dynasty: int | None = None
    #: The (from, to) index-year window, when dimension == "century".
    years: tuple[int, int] | None = None
    #: The address id, when dimension == "address".
    addr_id: int | None = None
    #: Rows the base data has for this combination.  Reported in test
    #: ids and failure messages so a reader can see what was asked for;
    #: never asserted against.
    base_rows: int = 0

    @property
    def id(self) -> str:
        parts = [self.form, self.dimension, "+".join(str(c) for c in self.codes)]
        if self.dynasty is not None:
            parts.append(f"dy{self.dynasty}")
        if self.years is not None:
            parts.append(f"{self.years[0]}-{self.years[1]}")
        if self.addr_id is not None:
            parts.append(f"addr{self.addr_id}")
        return "-".join(parts)


def _one_column(conn: sqlite3.Connection, sql: str, params=()) -> list:
    return [row[0] for row in conn.execute(sql, params)]


def _dense_codes(conn: sqlite3.Connection, form: FormSpec) -> list[tuple[int, int]]:
    """``[(code, rows)]`` for the codes with a workable number of rows."""
    return [(row[0], row[1]) for row in conn.execute(
        f'SELECT "{form.code_column}", COUNT(*) FROM "{form.code_table}" '
        f'WHERE "{form.code_column}" IS NOT NULL '
        f'GROUP BY "{form.code_column}" '
        "HAVING COUNT(*) BETWEEN ? AND ? "
        "ORDER BY COUNT(*) DESC LIMIT ?",
        (MIN_ROWS, MAX_ROWS, KEEP * 4))]


def _dense_dynasties(conn: sqlite3.Connection, form: FormSpec,
                     code: int) -> list[tuple[int, int]]:
    """``[(dynasty code, rows)]`` for one code, densest first."""
    return [(row[0], row[1]) for row in conn.execute(
        f'SELECT bm.c_dy, COUNT(*) FROM "{form.code_table}" d '
        f'JOIN BIOG_MAIN bm ON bm.c_personid = d."{form.person_column}" '
        f'WHERE d."{form.code_column}" = ? AND bm.c_dy IS NOT NULL '
        "AND bm.c_dy > 0 GROUP BY bm.c_dy "
        "HAVING COUNT(*) >= 2 ORDER BY COUNT(*) DESC LIMIT ?",
        (code, KEEP))]


def _dense_year_windows(conn: sqlite3.Connection, form: FormSpec,
                        code: int) -> list[tuple[int, int, int]]:
    """``[(from year, to year, rows)]`` -- populated half-centuries.

    Half-centuries rather than centuries because CBDB's mass is
    concentrated in the Song, and a century-wide window there returns
    more rows than a test wants to download.
    """
    rows = conn.execute(
        f"SELECT (bm.c_index_year / 50) * 50 AS bucket, COUNT(*) "
        f'FROM "{form.code_table}" d '
        f'JOIN BIOG_MAIN bm ON bm.c_personid = d."{form.person_column}" '
        f'WHERE d."{form.code_column}" = ? AND bm.c_index_year IS NOT NULL '
        "AND bm.c_index_year > 0 GROUP BY bucket "
        "HAVING COUNT(*) >= 2 ORDER BY COUNT(*) DESC LIMIT ?",
        (code, KEEP)).fetchall()
    return [(int(row[0]), int(row[0]) + 49, row[1]) for row in rows]


def _dense_addresses(conn: sqlite3.Connection, form: FormSpec,
                     code: int) -> list[tuple[int, int]]:
    """``[(addr id, rows)]`` -- addresses the code's people are indexed at."""
    return [(row[0], row[1]) for row in conn.execute(
        f"SELECT bm.c_index_addr_id, COUNT(*) "
        f'FROM "{form.code_table}" d '
        f'JOIN BIOG_MAIN bm ON bm.c_personid = d."{form.person_column}" '
        f'WHERE d."{form.code_column}" = ? AND bm.c_index_addr_id IS NOT NULL '
        "AND bm.c_index_addr_id > 0 GROUP BY bm.c_index_addr_id "
        "HAVING COUNT(*) >= 2 ORDER BY COUNT(*) DESC LIMIT ?",
        (code, KEEP)).fetchall()]


def address_filter_is_the_code_filter(form: FormSpec) -> bool:
    """True when a form's address filter *is* its code filter.

    The Places form is about addresses, so its codes are address ids and
    ``addrIds`` carries them.  Adding an address filter there does not
    narrow the query, it replaces the subject -- so the address
    dimension is not a monotonicity test on that form, it is a different
    query, and asserting a subset relation on it fails for a reason that
    is not a defect.

    Detected rather than declared: ask the form to build a body for a
    made-up code and see whether it arrives in the address field.  A
    build that renamed the field would change both halves at once and
    this would still be right.
    """
    probe = 424242
    return form.body([probe]).get(form.addr_field) == [probe]


def discover(conn: sqlite3.Connection) -> dict:
    """The whole matrix, as plain data ready to serialise."""
    out: dict = {"version": CACHE_VERSION, "forms": {}}
    for form in FORMS:
        codes = _dense_codes(conn, form)
        entry: dict = {"codes": [], "dynasties": {}, "years": {},
                       "addresses": {}}
        for code, rows in codes[:KEEP]:
            entry["codes"].append([code, rows])
            entry["dynasties"][str(code)] = [
                list(pair) for pair in _dense_dynasties(conn, form, code)]
            entry["years"][str(code)] = [
                list(window) for window in _dense_year_windows(conn, form, code)]
            if not address_filter_is_the_code_filter(form):
                entry["addresses"][str(code)] = [
                    list(pair) for pair in _dense_addresses(conn, form, code)]
        out["forms"][form.name] = entry
    return out


def _database_fingerprint(db: Path) -> str:
    """SHA-256 of the database the inputs were discovered from.

    The whole 1.2 GB, not a size-and-mtime shortcut: the point of the
    cache key is to be exact, and a wrong answer here means the matrix
    silently drives last month's data.  It takes about two seconds.
    """
    digest = hashlib.sha256()
    with db.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(conn: sqlite3.Connection, db: Path, cache: Path,
         *, refresh: bool = False) -> dict:
    """Discovered inputs for this database, from cache when still valid."""
    fingerprint = _database_fingerprint(db)
    if not refresh and cache.is_file():
        try:
            cached = json.loads(cache.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            cached = None
        if (cached
                and cached.get("version") == CACHE_VERSION
                and cached.get("database") == fingerprint):
            return cached

    discovered = discover(conn)
    discovered["database"] = fingerprint
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(discovered, indent=1), encoding="utf-8")
    return discovered


def combinations(discovered: dict) -> list[Combination]:
    """The matrix as a flat list, in a stable order."""
    out: list[Combination] = []
    for form_name, entry in sorted(discovered["forms"].items()):
        for code, rows in entry["codes"]:
            out.append(Combination(form=form_name, codes=(code,),
                                   dimension="code", base_rows=rows))
        for code_text, dynasties in sorted(entry["dynasties"].items()):
            for dynasty, rows in dynasties:
                out.append(Combination(
                    form=form_name, codes=(int(code_text),),
                    dimension="dynasty", dynasty=dynasty, base_rows=rows))
        for code_text, windows in sorted(entry["years"].items()):
            for start, end, rows in windows:
                out.append(Combination(
                    form=form_name, codes=(int(code_text),),
                    dimension="century", years=(start, end), base_rows=rows))
        for code_text, addresses in sorted(entry["addresses"].items()):
            for addr_id, rows in addresses:
                out.append(Combination(
                    form=form_name, codes=(int(code_text),),
                    dimension="address", addr_id=addr_id, base_rows=rows))
    return out

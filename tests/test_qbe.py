"""The Query Builder (QBE): the whitelist, the generated SQL, and its guards.

QBE is the one part of the application that lets a user compose their own
query, so its whitelist is a security boundary as well as a usability
one.  It is also self-contained -- ``GenerateSQL`` only ever emits
SELECT, and no handler here writes to the shared ``ZZ_SCRATCH_*`` tables
-- which makes this file order-independent and fast.

Two oracles are used, neither of them a transcription:

* the shipped database's own catalogue (``PRAGMA table_info``), to ask
  whether a column the application offers actually exists; and
* the application's answers to its own ``/api/qbe/schema``, driven back
  into ``/api/qbe/run``.

Every query below aggregates with COUNT so the response is one row.  A
plain column select would be unbounded: QBE applies no LIMIT, so
selecting one column of BIOG_MAIN would materialise 658 941 rows.
"""
from __future__ import annotations

import pytest

from cbdb_desktop.app import CbdbApp
from cbdb_desktop.defects import KnownShippedDefect
from cbdb_desktop.staging import AppLayout

pytestmark = pytest.mark.app

# The columns the shipped whitelist offers that the database does not
# have.  Pinned exactly: this is a defect report, and a build that fixes
# some of them (or breaks new ones) must not slip past silently.
PHANTOM_COLUMNS = {
    "View_BiogInstAddrData": ["c_personid", "c_notes"],
    "View_BiogInstData": ["c_personid", "c_notes"],
    "View_BiogSourceData": ["c_notes"],
    "View_BiogTextData": ["c_source", "c_pages", "c_notes"],
    "View_Entry": ["c_personid", "c_entry_code", "c_assoc_code", "c_notes"],
    "View_EventData": ["c_event_code", "c_addr_id", "c_source", "c_pages"],
    "View_KinAddr": ["c_personid", "c_index_year", "c_index_year_type_desc",
                     "c_index_year_type_hz", "c_dy", "c_dynasty",
                     "c_dynasty_chn", "c_female", "c_notes"],
    "View_PostingOfficeData": ["c_office_id", "c_source", "c_pages", "c_notes",
                               "c_dy"],
}


def _count_query(table: str, column: str, **extra) -> dict:
    """A QBE request that counts one column: always exactly one row back."""
    body = {
        "tables": [{"alias": "t", "table": table}],
        "columns": [{"table_alias": "t", "field": column,
                     "show": True, "group": "COUNT"}],
    }
    body.update(extra)
    return body


@pytest.fixture(scope="module")
def qbe_schema(app: CbdbApp) -> list[dict]:
    schema = app.json("GET", "/api/qbe/schema")
    assert schema, "the QBE whitelist is empty"
    return schema


@pytest.fixture(scope="module")
def db_catalogue(layout: AppLayout) -> dict[str, set[str]]:
    """Every table/view the shipped database really has, and its columns.

    Read straight from SQLite's catalogue -- a base fact about the
    artefact, with no application logic reproduced.
    """
    import sqlite3

    conn = sqlite3.connect(layout.db.resolve().as_uri() + "?mode=ro&immutable=1",
                           uri=True)
    try:
        names = [row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view')")]
        return {name: {row[1] for row in conn.execute(
            f'PRAGMA table_info("{name}")')} for name in names}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# the whitelist itself
# ---------------------------------------------------------------------------

def test_the_whitelist_has_the_documented_shape(qbe_schema):
    # 102 tables and 1386 columns in the 2026-09-07 build, against 99
    # and 1350 in 2026-09-01.  Pinned exactly, like every count here: a
    # whitelist that lost a third of its columns would satisfy any floor
    # loose enough to survive a data refresh.
    assert len(qbe_schema) == 102, len(qbe_schema)
    assert [t["name"] for t in qbe_schema] == sorted(t["name"] for t in qbe_schema), \
        "the grid shows tables in the order it receives them; they are not sorted"

    for table in qbe_schema:
        assert set(table) >= {"name", "label", "columns"}, sorted(table)
        assert table["columns"], f"{table['name']} offers no columns"
        for column in table["columns"]:
            assert set(column) == {"name", "label", "sql_type"}, sorted(column)

    total = sum(len(t["columns"]) for t in qbe_schema)
    assert total == 1386, total


def test_no_view_resolves_two_columns_to_the_same_name(db_catalogue,
                                                       qbe_schema):
    """The root cause of the phantom-column defect, asserted where it
    lives.

    SQLite gives a view's output columns the names its SELECT produces,
    and when a SELECT produces the same name twice it disambiguates by
    appending ``:1`` to the second.  A column called ``c_personid:1``
    cannot be selected by the Query Builder, by the QBE SQL generator,
    or by any other client -- the identifier is unquotable in the
    generator's ``quoteIdent`` and meaningless to a user reading a
    header -- so a view that produces one has an output column nobody
    can ask for.

    Eight views do, and the correspondence with the whitelist's 30
    phantom columns is one-to-one: every phantom ``X`` has a sibling
    ``X:1`` in the same view.  That is what identifies the mechanism as
    duplicate-name resolution rather than a stale schema file, and it is
    why regenerating ``qbe_schema.json`` from the same ``CREATE VIEW``
    text does not fix it -- the JSON and the SQL agree with each other,
    and SQLite disagrees with both.

    Read from ``PRAGMA table_info``, which is how SQLite itself resolves
    a view's columns at query time.  No handler logic is reproduced.
    """
    mangled = {name: sorted(column for column in columns if ":" in column)
               for name, columns in db_catalogue.items()}
    mangled = {name: columns for name, columns in mangled.items() if columns}

    phantom_pairs = []
    for table in qbe_schema:
        real = db_catalogue.get(table["name"], set())
        for column in table["columns"]:
            if column["name"] not in real:
                if f"{column['name']}:1" in real:
                    phantom_pairs.append(f"{table['name']}.{column['name']}")

    assert mangled == {
        "View_BiogInstAddrData": ["c_notes:1", "c_personid:1"],
        "View_BiogInstData": ["c_notes:1", "c_personid:1"],
        "View_BiogSourceData": ["c_notes:1"],
        "View_BiogTextData": ["c_notes:1", "c_pages:1", "c_source:1"],
        "View_Entry": ["c_assoc_code:1", "c_entry_code:1", "c_notes:1",
                       "c_personid:1"],
        "View_EventData": ["c_addr_id:1", "c_event_code:1", "c_pages:1",
                           "c_source:1"],
        "View_KinAddr": ["c_dy:1", "c_dynasty:1", "c_dynasty_chn:1",
                         "c_female:1", "c_index_year:1",
                         "c_index_year_type_desc:1",
                         "c_index_year_type_hz:1", "c_notes:1",
                         "c_personid:1"],
        "View_PostingOfficeData": ["c_dy:1", "c_notes:1", "c_office_id:1",
                                   "c_pages:1", "c_source:1"],
    }, (
        "the set of views with duplicate output column names changed -- "
        f"update the defect report:\n{mangled}")

    # The link between the two halves, so a partial fix cannot leave the
    # report describing a mechanism that no longer applies.
    assert len(phantom_pairs) == sum(len(v) for v in mangled.values()) == 30, (
        f"{len(phantom_pairs)} of the whitelist's phantom columns have a "
        f"':1' sibling, against {sum(len(v) for v in mangled.values())} "
        "mangled columns in the database")


def test_every_offered_table_exists_in_the_database(qbe_schema, db_catalogue):
    missing = [t["name"] for t in qbe_schema if t["name"] not in db_catalogue]
    assert not missing, f"the grid offers tables the database lacks: {missing}"


def test_every_offered_column_exists_in_the_database(qbe_schema, db_catalogue):
    """The whitelist must not offer a column that cannot be selected.

    The marker is narrowed to the exact known set: a build that fixes
    some of them, or breaks a new one, fails here rather than xfailing
    quietly.
    """
    phantom: dict[str, list[str]] = {}
    for table in qbe_schema:
        real = db_catalogue.get(table["name"], set())
        absent = [c["name"] for c in table["columns"] if c["name"] not in real]
        if absent:
            phantom[table["name"]] = absent

    if phantom == PHANTOM_COLUMNS:
        raise KnownShippedDefect(
            f"the Query Builder offers "
            f"{sum(len(v) for v in phantom.values())} columns across "
            f"{len(phantom)} views that do not exist in the database")
    assert not phantom, (
        "the set of phantom columns changed -- update PHANTOM_COLUMNS and the "
        f"defect report:\n{phantom}")


# ---------------------------------------------------------------------------
# running queries
# ---------------------------------------------------------------------------

def test_every_offered_table_can_actually_be_queried(app: CbdbApp, qbe_schema):
    """Count the first column of all 99 tables through the running app.

    Cheap (~3 s for the whole whitelist) and the broadest end-to-end
    check available: it proves the generated SQL is valid against every
    table the grid offers.
    """
    failures = []
    for table in qbe_schema:
        column = table["columns"][0]["name"]
        response = app.post("/api/qbe/run", json=_count_query(table["name"], column))
        if response.status_code != 200:
            failures.append(f"{table['name']}.{column} -> {response.status_code} "
                            f"{response.json().get('message', '')[:100]}")

    known = {f"{table}.{columns[0]}" for table, columns in PHANTOM_COLUMNS.items()
             if columns[0] == "c_personid"}
    unexpected = [f for f in failures
                  if not any(f.startswith(k) for k in known)]
    assert not unexpected, "\n".join(unexpected)

    if failures:
        raise KnownShippedDefect(
            f"{len(failures)} whitelisted tables cannot be queried on their "
            f"first offered column:\n" + "\n".join(failures))


@pytest.mark.parametrize("table,column", [
    (table, column)
    for table, columns in sorted(PHANTOM_COLUMNS.items())
    for column in columns
])
def test_a_phantom_column_gives_the_user_a_server_error(app: CbdbApp, table: str,
                                                        column: str):
    """What the defect looks like from the grid: a 500, not a validation error.

    Any *other* failure -- a 400, a hang, a different message -- is a real
    failure, because the marker only tolerates the signature below.  And
    fixing the whitelist, or the views, turns these green-unexpectedly and
    forces the pinned list to be revisited.
    """
    response = app.post("/api/qbe/run", json=_count_query(table, column))
    if response.status_code == 500 and "no such column" in response.text:
        raise KnownShippedDefect(
            f"{table}.{column} is offered by the grid but does not exist: "
            f"{response.json()['message']}")
    assert response.status_code == 200, response.text[:300]


def test_a_simple_query_returns_rows_and_the_sql_it_ran(app: CbdbApp):
    """The grid shows users the SQL; it must match what came back."""
    payload = app.json("POST", "/api/qbe/run", json={
        "tables": [{"alias": "t", "table": "EXTANT_CODES"}],
        "columns": [
            {"table_alias": "t", "field": "c_extant_code", "show": True},
            {"table_alias": "t", "field": "c_extant_desc", "show": True},
        ],
    })

    assert payload["status"] == "ok"
    assert payload["columns"] == ["t.c_extant_code", "t.c_extant_desc"]
    assert payload["rows"], "no rows from a table that has some"
    assert all(len(row) == len(payload["columns"]) for row in payload["rows"]), \
        "a row has a different width than the column list"

    sql = payload["sql"]
    assert sql.startswith("SELECT"), sql
    assert '"EXTANT_CODES"' in sql and '"c_extant_code"' in sql


def test_a_hidden_column_is_not_returned(app: CbdbApp):
    """`show: false` means "use it, do not display it"."""
    payload = app.json("POST", "/api/qbe/run", json={
        "tables": [{"alias": "t", "table": "EXTANT_CODES"}],
        "columns": [
            {"table_alias": "t", "field": "c_extant_code", "show": True},
            {"table_alias": "t", "field": "c_extant_desc", "show": False},
        ],
    })
    assert payload["columns"] == ["t.c_extant_code"]
    assert all(len(row) == 1 for row in payload["rows"])


def test_distinct_never_returns_more_rows(app: CbdbApp):
    """DISTINCT collapses duplicates and changes nothing else."""
    body = {
        "tables": [{"alias": "t", "table": "BIOG_MAIN"}],
        "columns": [{"table_alias": "t", "field": "c_dy", "show": True,
                     "group": "GROUP_BY"}],
    }
    grouped = app.json("POST", "/api/qbe/run", json=body)
    distinct = app.json("POST", "/api/qbe/run", json={**body, "distinct": True})

    assert "DISTINCT" in distinct["sql"] and "DISTINCT" not in grouped["sql"]
    assert len(distinct["rows"]) <= len(grouped["rows"])
    assert {tuple(r) for r in distinct["rows"]} == {tuple(r) for r in grouped["rows"]}


def test_a_count_through_the_grid_agrees_with_the_shipped_data(app: CbdbApp,
                                                               sqlite_conn):
    """The grid counting a table agrees with the table's row count.

    A base fact on both sides: COUNT(*) of one table, asked of the
    application and of the database.  No join, filter or projection of
    the handler's is reproduced.
    """
    for table, column in [("BIOG_MAIN", "c_personid"),
                          ("ADDR_CODES", "c_addr_id"),
                          ("DYNASTIES", "c_dy")]:
        payload = app.json("POST", "/api/qbe/run", json=_count_query(table, column))
        through_grid = payload["rows"][0][0]
        in_database = sqlite_conn.execute(
            f'SELECT COUNT("{column}") FROM "{table}"').fetchone()[0]
        assert through_grid == in_database, \
            f"{table}.{column}: grid says {through_grid}, data has {in_database}"


def test_a_join_between_two_whitelisted_tables_runs(app: CbdbApp):
    payload = app.json("POST", "/api/qbe/run", json={
        "tables": [
            {"alias": "b", "table": "BIOG_MAIN"},
            {"alias": "d", "table": "DYNASTIES",
             "join_to": {"kind": "INNER", "left_alias": "b", "left_col": "c_dy",
                         "right_alias": "d", "right_col": "c_dy"}},
        ],
        "columns": [
            {"table_alias": "d", "field": "c_dynasty", "show": True,
             "group": "GROUP_BY"},
            {"table_alias": "b", "field": "c_personid", "show": True,
             "group": "COUNT", "sort": "DESC"},
        ],
    })
    assert payload["status"] == "ok"
    assert "JOIN" in payload["sql"].upper()
    assert payload["rows"], "no rows from a join every person participates in"

    counts = [row[1] for row in payload["rows"]]
    assert counts == sorted(counts, reverse=True), "the DESC sort was not applied"


# ---------------------------------------------------------------------------
# guards
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("label,body,fragment", [
    ("no tables", {"tables": [], "columns": []},
     "at least one table"),
    ("no shown column",
     {"tables": [{"alias": "t", "table": "EXTANT_CODES"}],
      "columns": [{"table_alias": "t", "field": "c_extant_code", "show": False}]},
     "Show"),
    ("unknown table",
     {"tables": [{"alias": "t", "table": "NO_SUCH_TABLE"}],
      "columns": [{"table_alias": "t", "field": "x", "show": True}]},
     "unknown table"),
    ("unknown column",
     {"tables": [{"alias": "t", "table": "EXTANT_CODES"}],
      "columns": [{"table_alias": "t", "field": "no_such_column", "show": True}]},
     "unknown field"),
    ("unknown alias",
     {"tables": [{"alias": "t", "table": "EXTANT_CODES"}],
      "columns": [{"table_alias": "zz", "field": "c_extant_code", "show": True}]},
     "unknown table alias"),
    ("unsupported join",
     {"tables": [{"alias": "a", "table": "EXTANT_CODES"},
                 {"alias": "b", "table": "YEAR_RANGE_CODES",
                  "join_to": {"kind": "RIGHT", "left_alias": "a",
                              "left_col": "c_extant_code", "right_alias": "b",
                              "right_col": "c_range_code"}}],
      "columns": [{"table_alias": "a", "field": "c_extant_code", "show": True}]},
     "unsupported kind"),
    ("invalid sort",
     {"tables": [{"alias": "t", "table": "EXTANT_CODES"}],
      "columns": [{"table_alias": "t", "field": "c_extant_code", "show": True,
                   "sort": "SIDEWAYS"}]},
     "invalid sort"),
    ("invalid aggregate",
     {"tables": [{"alias": "t", "table": "EXTANT_CODES"}],
      "columns": [{"table_alias": "t", "field": "c_extant_code", "show": True,
                   "group": "MEDIAN"}]},
     "invalid group"),
])
def test_a_malformed_query_is_refused_with_an_explanation(app: CbdbApp, label: str,
                                                          body: dict, fragment: str):
    """Every guard answers 400 and says which part of the grid was wrong."""
    response = app.post("/api/qbe/run", json=body)
    assert response.status_code == 400, f"{label}: {response.status_code}"

    payload = response.json()
    assert payload["status"] == "error"
    assert fragment.lower() in payload["message"].lower(), payload["message"]


def test_a_table_outside_the_whitelist_cannot_be_reached(app: CbdbApp,
                                                         db_catalogue, qbe_schema):
    """The whitelist is a boundary, not a convenience.

    A table that exists in the database but is deliberately not offered
    must be unreachable -- including the scratch tables the forms use
    internally.
    """
    offered = {t["name"] for t in qbe_schema}
    hidden = sorted(set(db_catalogue) - offered)
    assert hidden, "every table in the database is exposed by the grid"

    for table in ["ZZ_SCRATCH_ENTRY", "ZZ_STORE_PERSON_ID", "sqlite_master"]:
        if table not in db_catalogue and table != "sqlite_master":
            continue
        response = app.post("/api/qbe/run", json=_count_query(table, "rowid"))
        assert response.status_code == 400, \
            f"{table} was reachable through the grid: {response.status_code}"
        assert "unknown table" in response.json()["message"]


def test_criteria_are_parameterised_not_interpolated(app: CbdbApp, app_db):
    """A criterion that looks like SQL is treated as a value.

    The survival check reads the database the application actually writes
    to -- its per-session copy -- not the pristine master.  Checking the
    master would prove nothing: the app never opens it, so a successful
    DROP in the copy would leave the master serenely intact and the test
    green.
    """
    import sqlite3

    def table_count() -> int:
        conn = sqlite3.connect(app_db.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            return conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
        finally:
            conn.close()

    before = table_count()
    people_before = app.json("POST", "/api/qbe/run",
                             json=_count_query("BIOG_MAIN", "c_personid"))["rows"]

    payload = app.json("POST", "/api/qbe/run", json={
        "tables": [{"alias": "t", "table": "EXTANT_CODES"}],
        "columns": [{"table_alias": "t", "field": "c_extant_code", "show": True,
                     "criteria_text": ["1; DROP TABLE BIOG_MAIN--"]}],
    })

    assert payload["status"] == "ok"
    assert "?" in payload["sql"], payload["sql"]
    assert "DROP" not in payload["sql"].upper()

    assert table_count() == before, "a table disappeared from the app's database"
    assert app.json("POST", "/api/qbe/run",
                    json=_count_query("BIOG_MAIN", "c_personid"))["rows"] == \
        people_before, "BIOG_MAIN changed after the injection attempt"


def test_the_grid_only_ever_reads(app: CbdbApp):
    """No spelling of a request may produce anything but a SELECT."""
    for field in ("c_extant_code", "c_extant_desc"):
        payload = app.json("POST", "/api/qbe/run",
                           json=_count_query("EXTANT_CODES", field))
        sql = payload["sql"].upper()
        assert sql.lstrip().startswith("SELECT")
        for verb in ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
                     "ATTACH", "PRAGMA"):
            assert verb not in sql, f"{verb} appeared in generated SQL: {payload['sql']}"

"""The scratch tables: who owns each one, and does its declaration match.

The application keeps its working state in ``ZZ_*`` tables inside the
database it serves.  Two things about them have caused defects, and both
are checkable without running a query.

**Who owns a table.**  Until 2026-09-07 several of these were shared by
unrelated forms, and one form's query cleared what another form's export
was about to read (CBDB-D-004).  The fix was to give each form its own
copy.  Nothing but the *name* keeps them apart now, so the ownership map
is pinned here, read out of the shipped Go source as data: a later
refactor that pointed two forms at one table again would fail this file
rather than being found by whichever user hit it.

**Whether a declaration is true.**  This is the more interesting one.
Every form re-declares the tables it uses with ``CREATE TABLE IF NOT
EXISTS`` at startup -- and against an existing table that statement is a
no-op, column list and all.  The tables ship in the database, so those
declarations never run to completion, and a declaration can therefore
disagree with the real table indefinitely without anything noticing.
The developers found the same thing during the CBDB-D-004 remediation:
three forms carried three mutually inconsistent declarations of one
shared table, "and whichever declaration happened to run first silently
determined the real column set".

Their fix gave each form its own table with the union of every column
any of them had declared.  What no fix can do is make a declaration
*true*: that needs a comparison against the database, and this file is
it.  Two directions, and only one of them is a defect:

* a column the code **reads** that the table does not have is a query
  that fails at runtime -- CBDB-D-008 is exactly this, three dead export
  buttons asking ``ZZ_SN_NETWORK`` for ``c_node_dist``;
* a column the code **declares** that the table does not have is
  harmless until something reads it, and is reported here as a warning
  rather than a failure, because the code may be describing a table for
  a database that has not been rebuilt yet.

The oracle throughout is ``PRAGMA table_info`` on the shipped database,
which is how SQLite resolves a name at query time, plus the Go source
read as data.  No handler's SQL is reproduced.
"""
from __future__ import annotations

import re

import pytest

from cbdb_desktop.staging import AppLayout

# ---------------------------------------------------------------------------
# reading the Go source as data
# ---------------------------------------------------------------------------

_CREATE_TABLE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
    r"[\"`]?(?P<name>ZZ_?[A-Za-z0-9_]+)[\"`]?\s*\((?P<body>.*?)\)\s*[`\"]",
    re.IGNORECASE | re.DOTALL)

#: Any mention of a scratch table name in code (comments stripped).
#: Deliberately a mention rather than an attempt to classify reads and
#: writes.  Classifying needs a SQL parser to be right, and being wrong
#: in the direction of *missing* a use would hide exactly the sharing
#: this file exists to catch; a mention that turns out to be inert costs
#: one line in the pinned map below and nothing else.
_TABLE_MENTION = re.compile(r"\bZZ_[A-Z0-9_]+\b")

#: Which form each backend file belongs to.  A file per form plus two
#: shared ones, whose contents belong to no single form.
_SHARED_FILES = {"main.go", "cbdb_shared_utils.go",
                 "cbdb_navigation_backend.go"}


def _form_of(filename: str) -> str:
    if filename in _SHARED_FILES:
        return "<shared>"
    return (filename.removesuffix("_form_backend.go")
            .removesuffix("_form_query.go")
            .removesuffix(".go"))


def _strip_comments(source: str) -> str:
    """Blank line and block comments, preserving offsets is not needed here."""
    source = re.sub(r"/\*.*?\*/", " ", source, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", " ", source)


@pytest.fixture(scope="module")
def go_declarations(layout: AppLayout) -> dict[str, dict[str, set[str]]]:
    """``{table: {file: {declared columns}}}`` from every CREATE TABLE."""
    out: dict[str, dict[str, set[str]]] = {}
    for path in layout.go_sources():
        text = _strip_comments(path.read_text(encoding="utf-8",
                                              errors="replace"))
        for match in _CREATE_TABLE.finditer(text):
            name = match.group("name").upper()
            columns = set()
            for line in match.group("body").split(","):
                line = line.strip()
                if not line or line.upper().startswith(
                        ("PRIMARY", "UNIQUE", "FOREIGN", "CHECK", "CONSTRAINT")):
                    continue
                columns.add(line.split()[0].strip('"`').lower())
            if columns:
                out.setdefault(name, {})[path.name] = columns
    assert out, "no CREATE TABLE for a ZZ_ table found in the Go source"
    return out


@pytest.fixture(scope="module")
def table_users(layout: AppLayout, db_columns) -> dict[str, set[str]]:
    """``{table: {form whose source names it}}``, comments excluded.

    Restricted to names the shipped database actually has, because the
    Go source also contains SQL aliases that look like table names
    (``ZZ_SCRATCH_ADDR_1``, ``ZZ_NETWORK_LIST_TMP_1``) and reporting
    those as untracked tables would bury the real map in noise.
    """
    out: dict[str, set[str]] = {}
    for path in layout.go_sources():
        text = _strip_comments(path.read_text(encoding="utf-8",
                                              errors="replace"))
        for name in {m.group(0).upper()
                     for m in _TABLE_MENTION.finditer(text)}:
            if name in db_columns:
                out.setdefault(name, set()).add(_form_of(path.name))
    assert out, "no ZZ_ table is named anywhere in the Go source"
    return out


@pytest.fixture(scope="module")
def db_columns(sqlite_conn) -> dict[str, set[str]]:
    """Every ``ZZ_*`` table in the shipped database, and its real columns."""
    names = [row[0] for row in sqlite_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name LIKE 'ZZ!_%' ESCAPE '!'")]
    assert names, "the shipped database has no ZZ_ scratch tables"
    return {name.upper(): {row[1].lower() for row in sqlite_conn.execute(
        f'PRAGMA table_info("{name}")')} for name in names}


# ---------------------------------------------------------------------------
# ownership
# ---------------------------------------------------------------------------

#: Which forms may touch each scratch table.  Pinned exactly.  Derived
#: from the shipped source and then read: a table used by two forms is
#: not automatically a defect -- three entries below are shared on
#: purpose -- but it is always a decision, and this is where the decision
#: is recorded.
#:
#: Written as a map rather than a rule because the rule has three
#: exceptions and a rule with three exceptions hides more than it says.
EXPECTED_OWNERS: dict[str, set[str]] = {
    # -- shared on purpose -------------------------------------------------
    # The cross-form channel: one stored list, which is how a result
    # travels from one form to another and, since the working lists were
    # split, the only such channel.  Every form names it; that is the
    # feature, and test_stateful_forms.py pins the behaviour.
    "ZZ_STORE_PERSON_ID": {"<shared>", "associations", "assocpairs", "entry",
                           "groupdata", "kinship", "networks", "office",
                           "places", "status", "texts"},
    # Filled and consumed inside one request by a common helper that
    # clears before each use, so shared by name and never across
    # requests -- the developers' own conclusion during the CBDB-D-004
    # remediation, reached the same way and recorded here so a reader
    # does not have to re-derive it.
    "ZZ_SCRATCH_ADDR": {"associations", "entry", "networks", "places",
                        "status", "texts"},
    "ZZ_SCRATCH_ADDR_LIST": {"associations", "entry", "networks", "office",
                             "places", "status", "texts"},
    # The people browser and the Kinship form both walk kin, and the
    # Networks form's export reads the same temporary.  Left shared: a
    # narrow, low-probability race in a single-user desktop application,
    # every write site clearing and consuming within one request.  Note
    # that CBDB-D-010 is the reason "single-user" is doing work in that
    # sentence.
    "ZZ_KIN_LIST": {"browser", "kinship"},
    "ZZ_KIN_LIST_TMP": {"browser", "kinship", "networks"},
    "ZZ_SCRATCH_KIN": {"browser", "kinship"},
    "ZZ_SCRATCH_KINNET": {"browser", "kinship"},

    # -- one form each -----------------------------------------------------
    "ZZ_ADDRESSES": {"office"},
    "ZZ_ADDRESSES_TMP": {"office"},
    "ZZ_ENTRY_CODE": {"entry"},
    "ZZ_ENTRY_CODE_TMP": {"entry"},
    "ZZ_NETWORK_LIST": {"networks"},
    "ZZ_NETWORK_LIST_TMP": {"networks"},
    "ZZ_OFFICE_CODE": {"office"},
    "ZZ_OFFICE_CODE_TMP": {"office"},
    "ZZ_SCRATCH_ADDR_LIST_PEOPLE": {"office"},
    "ZZ_SCRATCH_ADDR_OFFICE": {"office"},
    "ZZ_SCRATCH_ADDR_PEOPLE": {"office"},
    "ZZ_SCRATCH_ASSOC_FILTER": {"networks"},
    "ZZ_SCRATCH_ENTRY": {"entry"},
    "ZZ_SCRATCH_ENTRY_CODE": {"entry"},
    "ZZ_SCRATCH_PAIR_NETWORK": {"assocpairs"},
    "ZZ_SCRATCH_PAIR_PEOPLE": {"assocpairs"},
    # Named only by the Networks form, despite the name: the Texts form
    # builds its result in one SELECT and keeps no scratch of its own.
    "ZZ_SCRATCH_P_TEXT": {"networks"},
    "ZZ_SOCIAL_NETWORK_AGGREGATE": {"networks"},

    # -- the per-form copies the CBDB-D-004 remediation created ------------
    # Ten tables, each named by exactly one form.  That one-to-one
    # property is the whole content of the fix, and this is where it is
    # checked; the report's claim that "each new table name now appears
    # in exactly one form's files" is otherwise nobody's to verify.
    "ZZ_SN_ASSOC": {"associations"},
    "ZZ_SP_ASSOC": {"associations"},
    "ZZ_SN_ASSOC_PAIR": {"assocpairs"},
    "ZZ_SP_ASSOC_PAIR": {"assocpairs"},
    "ZZ_SIP_ASSOC_PAIR": {"assocpairs"},
    "ZZ_SP_KINSHIP": {"kinship"},
    "ZZ_SIP_KINSHIP": {"kinship"},
    "ZZ_SN_NETWORK": {"networks"},
    "ZZ_SP_NETWORK": {"networks"},
    "ZZ_SIP_NETWORK": {"networks"},
}

#: Scratch tables that ship in the database and that no Go file names.
#: Recorded rather than ignored: a table nothing uses still ships, still
#: holds whatever it last held, and is exactly what CBDB-D-005 looked
#: like.  Three of these are the shared tables the 2026-09-07 per-form
#: split replaced; the other five are left over from the VBA original,
#: whose Pajek and Gephi writers staged rows in the database while the
#: Go ones build the file in memory.
EXPECTED_ORPHANS: dict[str, str] = {
    "ZZ_SOCIAL_NETWORK": "replaced by ZZ_SN_ASSOC / ZZ_SN_ASSOC_PAIR / "
                         "ZZ_SN_NETWORK (CBDB-D-004)",
    "ZZ_SCRATCH_PEOPLE": "replaced by ZZ_SP_* (CBDB-D-004)",
    "ZZ_SCRATCH_IMPORT_PEOPLE": "replaced by ZZ_SIP_* (CBDB-D-004)",
    "ZZ_SCRATCH_PAJEK": "the Go Pajek writer builds the file in memory",
    "ZZ_SCRATCH_PAJEK_EDGE": "as above",
    "ZZ_SCRATCH_GEPHI_NODE": "the Go Gephi writer builds the file in memory",
    "ZZ_SCRATCH_GEPHI_NODE_DISTINCT": "as above",
    "ZZ_SCRATCH_KINNET_EDGE": "no Go file names it",
}


def test_each_scratch_table_is_touched_by_the_forms_it_should_be(table_users):
    """The ownership map, pinned.

    A table appearing under a second form is how CBDB-D-004 happened,
    and there is nothing in the code that would prevent it recurring --
    the tables are addressed by name, in string literals, in ten
    separate files.  So the map is asserted whole: both a new sharing
    and a form quietly *stopping* using a table fail here and get read.
    """
    actual = {name: owners for name, owners in table_users.items()
              if name in EXPECTED_OWNERS or name in EXPECTED_ORPHANS}

    unexpected = {name: sorted(owners) for name, owners in table_users.items()
                  if name not in EXPECTED_OWNERS
                  and name not in EXPECTED_ORPHANS}
    assert not unexpected, (
        "the build uses scratch tables this map does not know about -- "
        f"decide who should own them and add them:\n{unexpected}")

    differences = {
        name: {"expected": sorted(expected),
               "actual": sorted(actual.get(name, set()))}
        for name, expected in EXPECTED_OWNERS.items()
        if actual.get(name, set()) != expected
    }
    assert not differences, (
        "the set of forms touching a scratch table changed.  If two forms "
        "now share one, that is CBDB-D-004 again; if a form stopped using "
        "one, the table is now dead weight that still ships with data in "
        f"it:\n{differences}")


def test_the_tables_the_split_left_behind_are_unused_and_empty(
        table_users, db_columns, sqlite_conn):
    """The old shared tables still ship.  They must at least be inert.

    ``ZZ_SOCIAL_NETWORK``, ``ZZ_SCRATCH_PEOPLE`` and
    ``ZZ_SCRATCH_IMPORT_PEOPLE`` were the three tables the 2026-09-07
    build replaced with per-form copies.  The tables themselves were not
    dropped from the schema, so they are still in every release.  That
    is harmless only while nothing writes them and they ship empty --
    and a half-finished future refactor pointing one form back at one of
    them is precisely the failure this catches.
    """
    for name in sorted(EXPECTED_ORPHANS):
        assert name in db_columns, \
            f"{name} is no longer in the shipped schema -- remove it here too"
        users = table_users.get(name, set())
        assert not users, (
            f"{name} was replaced by per-form tables in 2026-09-07 but "
            f"{sorted(users)} still use it")
        rows = sqlite_conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
        assert rows == 0, \
            f"{name} is unused by the code and ships holding {rows} rows"


# ---------------------------------------------------------------------------
# declarations against the database
# ---------------------------------------------------------------------------

def test_every_declared_scratch_table_exists_in_the_shipped_database(
        go_declarations, db_columns):
    """A table the code declares must be in the database that ships.

    ``CREATE TABLE IF NOT EXISTS`` in ``ensureAppTables`` means a missing
    table is created empty at startup rather than reported, so a table
    that was never added to the schema works -- until the next release,
    on the next machine, where it is created with whatever column list
    that form happens to declare, and the *other* form that reads it
    finds columns missing.  Which is the CBDB-D-004 follow-up the
    developers described, one step earlier.
    """
    missing = sorted(name for name in go_declarations if name not in db_columns)
    assert not missing, (
        f"the code declares scratch tables the shipped database does not "
        f"have: {missing}.  They will be created at startup from whichever "
        "form's declaration runs first.")


def test_no_two_forms_declare_the_same_table_differently(go_declarations):
    """Two declarations of one table must agree, column for column.

    This is the defect the 2026-09-07 remediation found and fixed by
    giving each form its own table: three files each carried their own
    ``CREATE TABLE IF NOT EXISTS`` for one shared table, none of them
    matching, and because the statement is a no-op against an existing
    table, whichever ran first silently decided the real column set.

    The fix removed the *sharing*.  It did not remove the pattern -- the
    statement is still a no-op and tables are still declared in more
    than one file -- and one instance survives, pinned below.

    That instance is latent rather than live, which is why it is pinned
    here and not filed as a defect: ``ZZ_KIN_LIST_TMP`` ships in the
    database with the full 32 columns, so the three-column declaration
    in the Networks backend is a no-op and nothing is currently broken.
    It would matter on the first database that did *not* already have
    the table -- the Networks form would create it with three columns
    and the Kinship form's queries would then fail on the other
    twenty-nine.  Worth mentioning to the developers as a one-line
    alignment; not worth a P-band in a report of things users can see.
    """
    disagreements = {}
    for name, per_file in go_declarations.items():
        if len(per_file) < 2:
            continue
        columns = list(per_file.values())
        if any(other != columns[0] for other in columns[1:]):
            union = set().union(*columns)
            disagreements[name] = {
                file: sorted(union - declared)
                for file, declared in per_file.items()
                if union - declared
            }
    assert disagreements == {
        "ZZ_KIN_LIST_TMP": {
            "networks_form_backend.go": [
                "c_addr_dist", "c_col", "c_col_total", "c_delete",
                "c_distance", "c_down", "c_down_total", "c_female",
                "c_kin_female", "c_kin_id", "c_kin_sex", "c_kinrel_len",
                "c_kinrel_root_text", "c_kinrel_root_text_simplified",
                "c_kinrel_test_text", "c_kinrel_total_raw",
                "c_kinrel_total_simplified", "c_mar", "c_mar_total",
                "c_notes", "c_personid", "c_personid_root",
                "c_prior_female", "c_sex", "c_source", "c_source_text",
                "c_source_text_chn", "c_up", "c_up_total"],
        },
    }, (
        "the set of scratch tables declared with different columns in two "
        "files changed.  CREATE TABLE IF NOT EXISTS is a no-op against an "
        "existing table, so on any database that does not already have the "
        "table, whichever declaration runs first decides the real column "
        "set and the other form's queries are one 'no such column' away:\n"
        f"{disagreements}")


def test_every_declared_column_exists_in_the_shipped_table(
        go_declarations, db_columns):
    """A declaration must describe the table that actually ships.

    Reported as a warning, not a failure, and the asymmetry is the
    point.  A declared-but-absent column is inert until something reads
    it -- the declaration is a defensive re-statement, and the code may
    legitimately be ahead of a database that has not been rebuilt.  A
    column the code *reads* and the table lacks is a different matter
    and fails in
    ``test_no_export_query_asks_a_scratch_table_for_a_column_it_lacks``.

    Pinned as an exact set anyway, so "these two are known and
    understood" cannot quietly become twenty.
    """
    extra = {}
    for name, per_file in go_declarations.items():
        real = db_columns.get(name)
        if real is None:
            continue
        for file, declared in per_file.items():
            absent = sorted(declared - real)
            if absent:
                extra.setdefault(name, {})[file] = absent

    assert extra == {}, (
        "the code declares columns the shipped tables do not have.  "
        "Harmless until something selects one, and a sign the database "
        "and the code were built from different revisions:\n"
        f"{extra}")


# ---------------------------------------------------------------------------
# the columns the code actually reads
# ---------------------------------------------------------------------------

#: ``SELECT <list> FROM ZZ_TABLE`` where the list is simple enough to
#: read without a SQL parser: bare column names and COALESCE(col, x).
#: Anything with a join, a subquery, a wildcard or a function call other
#: than COALESCE is skipped rather than guessed at -- a false alarm here
#: would be worse than a miss, because it would train a reader to ignore
#: this test, and the misses are covered by driving the endpoints.
_SIMPLE_SELECT = re.compile(
    r"SELECT\s+(?P<columns>[^;]*?)\s+FROM\s+[\"`]?(?P<table>ZZ_[A-Z0-9_]+)"
    r"[\"`]?(?P<tail>\s*(?:WHERE|ORDER|GROUP|LIMIT|\)|`|$))",
    re.IGNORECASE | re.DOTALL)

#: ``COALESCE(col, <literal>)`` -- by far the commonest wrapper in these
#: handlers, and the only one unwrapped here.  Unwrapping it first is
#: what lets the rest of the list be read as bare column names.
_COALESCE = re.compile(
    r"COALESCE\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,\s*(?:'[^']*'|-?[\d.]+)\s*\)",
    re.IGNORECASE)

_BARE_COLUMN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _selected_columns(column_list: str) -> set[str] | None:
    """The columns a simple SELECT list names, or None if it is not simple.

    "Simple" means: after unwrapping ``COALESCE(col, literal)``, every
    comma-separated item is a bare column name.  Anything else -- a
    wildcard, an alias, an arithmetic expression, a nested call -- makes
    the whole query unreadable *by this function*, and it returns None
    so the caller skips it.

    Skipping is the right failure.  A guessed column name that does not
    exist would report a defect that is not there, and one false alarm
    teaches a reader to skim past this test; a query this cannot read is
    still driven over HTTP by test_exports.py like every other.
    """
    if "*" in column_list:
        return None
    unwrapped = _COALESCE.sub(r"\1", column_list)
    out = set()
    for item in unwrapped.split(","):
        item = item.strip()
        if not item:
            continue
        if not _BARE_COLUMN.fullmatch(item):
            return None
        out.add(item.lower())
    return out or None


def test_no_query_asks_a_scratch_table_for_a_column_it_lacks(layout,
                                                             db_columns):
    """Every column a simple SELECT reads must exist in that table.

    This is CBDB-D-008 found in the source rather than by pressing a
    button: three of the Networks form's export handlers select
    ``c_node_dist`` from ``ZZ_SN_NETWORK``, which has ``c_edge_dist``
    instead, so SQLite refuses the query and the handler answers HTTP
    500 for every input there is.  A defect that cannot depend on data
    should not need a query to find, and finding it here means a build
    can be rejected before anyone runs it.

    Only the SELECTs simple enough to read exactly are considered, and
    the known failures are pinned as an exact set: a fix reports here,
    and a new one fails.
    """
    problems: dict[str, list[str]] = {}
    for path in layout.go_sources():
        text = _strip_comments(path.read_text(encoding="utf-8",
                                              errors="replace"))
        for match in _SIMPLE_SELECT.finditer(text):
            table = match.group("table").upper()
            real = db_columns.get(table)
            if real is None:
                continue
            selected = _selected_columns(match.group("columns"))
            if selected is None:
                continue
            absent = sorted(selected - real)
            if absent:
                line = text.count("\n", 0, match.start()) + 1
                problems[f"{path.name}:{line}"] = [f"{table}.{c}"
                                                   for c in absent]

    assert problems == {
        "networks_form_backend.go:2089": ["ZZ_SN_NETWORK.c_node_dist"],
        "networks_form_backend.go:2212": ["ZZ_SN_NETWORK.c_node_dist"],
        "networks_form_backend.go:2337": ["ZZ_SN_NETWORK.c_node_dist"],
    }, (
        "the set of queries reading a column their scratch table does not "
        "have changed.  Each one is a handler that answers HTTP 500 for "
        f"every input:\n{problems}")

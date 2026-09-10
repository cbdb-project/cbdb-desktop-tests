"""The Query Builder's grid: the operators, aggregates and ordering.

``test_qbe.py`` establishes that the Query Builder is safe -- its
whitelist holds, its criteria are parameterised, it never writes.  This
file asks the next question, which is whether the grid does what the
user filled in.  A researcher builds a query here by typing into cells,
exactly as in the Access original: a criterion like ``> 1100`` under a
column, a group function like ``Max`` under another, ``Ascending`` in
the sort row.  Until now the suite drove one criterion shape and two of
the six group functions, so most of what a user can type had never been
sent.

Most checks below are a **response-internal invariant**: the rows that
come back are compared with the criterion that asked for them, and with
each other.  Two use a second oracle and say so where they do -- the
aggregate test compares the grid's grouped answer against the grid's
own ungrouped one, and the HAVING test runs *the statement the grid
itself printed*, unaltered, to establish whether the SQL or only the
value bound into it is at fault.  Neither retypes a handler's query.

That is the oracle AGENTS.md allows, and it is the right
one here for a reason worth stating -- the Query Builder has no fixed
correct answer to compare against.  It builds arbitrary SQL over 124
tables, so there is nothing to freeze and nothing to look up.  What
there is, is a promise: *if you type ``> 1100`` you get rows greater
than 1100, and if you also type ``Max`` you get the largest in each
group*.  Checking the answer against the question is not a
re-implementation of the handler; it is the only thing the handler
claims.

Two things this file deliberately does not do.  It does not predict
row counts -- the counts belong to the data and change with it.  And
it does not build the SQL it expects and compare strings, which would
be a transcription of ``qbe_sqlgen.go`` and would agree with it
wherever it is wrong.  The generated SQL *is* read, in four places --
for ``OR``, ``HAVING``, ``ORDER BY`` and ``LEFT`` -- and every time
only to confirm that a clause was emitted, never to check its text.
"""
from __future__ import annotations

import json
import pathlib
import re

import pytest

from cbdb_desktop.app import CbdbApp
from cbdb_desktop.defects import KnownShippedDefect

pytestmark = pytest.mark.app

#: A table with a numeric column, plenty of rows, and no dependence on
#: any other -- so a criterion can be judged without a join confusing
#: what the filter did.  ``c_dy`` is the dynasty code and ``c_index_year``
#: a year; both are numeric and both have nulls, which is what makes
#: the IS NULL operators worth sending.
#:
#: Choosing the table and column here is deliberate and is not the
#: thing AGENTS.md's input rule is about: that rule is about filter
#: *values*, which land on sparse data and quietly make a test assert
#: nothing.  The threshold below is therefore discovered, while the
#: column it applies to is fixed -- one numeric, nullable, join-free
#: column is needed and this is the obvious one.
_TABLE = "BIOG_MAIN"
_NUMERIC = "c_index_year"
_GROUPING = "c_dy"

#: The sort directions this module drives.  A constant rather than a
#: literal in the decorator because the coverage gate below compares
#: the build's declared list against it -- and the gate used to learn
#: that by regexing this file for the decorator, which credits any
#: text of the right shape and is satisfied by the search's own line.
#: What the tests *send* is the honest source, and this is it: change
#: the parametrisation and the gate moves with it, because they are
#: the same object.
_SORT_DIRECTIONS = ("ASC", "DESC")

#: The LIKE criteria this module drives, as a parametrisation.  A
#: one-element list looks odd until you ask what the coverage gate
#: below can safely believe.
#:
#: Three versions of that credit searched source text -- the whole
#: module, then one function, then one line -- and each was satisfied
#: by a *mention* of the operator rather than a use of it, because a
#: text search cannot tell those apart.  The fourth took the operator
#: from a constant, which fixed the mention problem and left a
#: quieter one: nothing tied the constant to the request, so editing
#: the test to send something else kept the credit alive.
#:
#: A parametrisation cannot come apart that way.  The decorator *is*
#: the use, so there is no state in which the gate credits LIKE and
#: no test sends one.  Same reasoning as ``_SORT_DIRECTIONS``.
_LIKE_CRITERIA = ('Like "%shi%"',)

#: The group functions the HAVING test drives, each mapped to the
#: criterion that should keep groups and the one that should exclude
#: them.  ``{t}`` is filled with the discovered threshold.
#:
#: COUNT is here rather than in ``_AGGREGATES`` because it counts rows
#: instead of summarising the values in them, so it has no predicate
#: over those values -- and the two functions are here rather than
#: written into the test body because the coverage gate credits
#: ``set(_HAVING_PROBES)``.  The test builds its requests by iterating
#: this mapping and reads the answers back by name, so a row that
#: stops being sent stops being credited, and the test says so by
#: raising on the lookup.
_HAVING_PROBES = {
    "MAX": ("> {t}", "< {t}"),
    "COUNT": ("> 5", "< 5"),
}

#: A small whitelisted table for the vocabulary gate to drive every
#: declared token against.  498 rows, so eighteen probes cost about
#: as much as one query on ``BIOG_MAIN``; ``c_subgroup_code`` carries
#: 3 NULLs among 495 values, so ``Is Null`` and ``Is Not Null`` both
#: return something and neither is vacuous.
_PROBE_TABLE = "ETHNICITY_TRIBE_CODES"
_PROBE_NUMERIC = "c_subgroup_code"
_PROBE_TEXT = "c_name"

#: How a user writes each operator the build declares.  Contract
#: knowledge -- the grammar the criteria cell accepts -- not a copy of
#: anything the handler computes.  The gate sends one of each, so a
#: declared operator with no spelling here fails loudly rather than
#: going undriven.
_PROBE_CRITERIA = {
    "=": "= 5",
    "<>": "<> 5",
    "<": "< 5",
    "<=": "<= 5",
    ">": "> 5",
    ">=": ">= 5",
    "BETWEEN": "Between 1 And 999",
    "IN": "In (1, 5)",
    "LIKE": 'Like "%a%"',
    "IS NULL": "Is Null",
    "IS NOT NULL": "Is Not Null",
}


@pytest.fixture(scope="module")
def threshold(sqlite_conn) -> int:
    """A value with plenty of rows on both sides of it.

    Every operator test needs that: ``> x`` and ``< x`` must both
    return something, or half the table is asserting nothing.  The
    median of the non-null values is read from the column being
    filtered, so a data refresh moves it instead of hollowing the
    tests out.
    """
    row = sqlite_conn.execute(
        f"SELECT {_NUMERIC} FROM {_TABLE} WHERE {_NUMERIC} IS NOT NULL "
        f"AND {_NUMERIC} > 0 ORDER BY {_NUMERIC} "
        f"LIMIT 1 OFFSET (SELECT COUNT(*) / 2 FROM {_TABLE} "
        f"WHERE {_NUMERIC} IS NOT NULL AND {_NUMERIC} > 0)").fetchone()
    assert row and row[0], (
        f"{_TABLE}.{_NUMERIC} has no positive values, so no threshold "
        "can be chosen and every operator test below would be vacuous")
    value = int(row[0])

    # A median exists on a column holding one value repeated, and the
    # tests below would then find nothing above it and nothing under
    # it -- and say so in the words "this column has values on both
    # sides of every operator here", asserting as fact the thing
    # nothing had checked.  A wrong diagnosis costs more than a
    # missing one in a round where every red line is triaged as a
    # lead, so the claim is established here, where it is cheap.
    above, below = sqlite_conn.execute(
        f"SELECT SUM({_NUMERIC} > ?), SUM({_NUMERIC} < ?) FROM {_TABLE} "
        f"WHERE {_NUMERIC} IS NOT NULL AND {_NUMERIC} > 0",
        (value, value)).fetchone()
    assert above and below, (
        f"{_TABLE}.{_NUMERIC} is degenerate around its own median "
        f"{value}: {above or 0} row(s) above it and {below or 0} below. "
        "An empty answer from a comparison would then be correct, and "
        "the operator tests below -- which read an empty answer as the "
        "grid failing to understand the criterion -- would report a "
        "defect that is not there.  This is the data, not the build.")

    # The same claim for the other two operators.  ``IS NULL`` and
    # ``IS NOT NULL`` are parametrised alongside the comparisons and
    # their answers are read the same way -- but nothing above says
    # this column has a NULL in it, so on a column with none an empty
    # answer would be *correct* and would be reported as the grid
    # failing to parse the criterion.
    nulls, present = sqlite_conn.execute(
        f"SELECT SUM({_NUMERIC} IS NULL), SUM({_NUMERIC} IS NOT NULL) "
        f"FROM {_TABLE}").fetchone()
    assert nulls and present, (
        f"{_TABLE}.{_NUMERIC} has {nulls or 0} NULL and "
        f"{present or 0} non-NULL rows.  The IS NULL and IS NOT NULL "
        "parametrisations need both: with one of them empty, the "
        "operator test reads a correct empty answer as a parse "
        "failure and files a defect that is not there.")
    return value


def _run(app: CbdbApp, columns: list[dict], **extra) -> dict:
    """One grid query, with the table row filled in."""
    payload = app.json("POST", "/api/qbe/run", json={
        "tables": [{"alias": "t", "table": _TABLE}],
        "columns": columns,
        **extra,
    })
    assert payload["status"] == "ok", payload
    return payload


def _column(field: str, **extra) -> dict:
    return {"table_alias": "t", "field": field, "show": True, **extra}


def _values(payload: dict, index: int = 0) -> list:
    return [row[index] for row in payload["rows"]]


# ---------------------------------------------------------------------------
# the operators a criterion cell accepts
# ---------------------------------------------------------------------------

#: ``operator -> (how a user writes it, what its rows must satisfy)``.
#: The eleven the parser recognises, in the spelling a user types.  The
#: predicate is the operator's meaning, not a copy of the SQL: it is
#: what the user believes they asked for, which is the thing worth
#: checking.  Both halves are functions of the discovered threshold,
#: so no filter value is written down here.
_OPERATORS: dict[str, object] = {
    "bare": (lambda t: f"{t}", lambda v, t: v == t),
    "=": (lambda t: f"= {t}", lambda v, t: v == t),
    "<>": (lambda t: f"<> {t}", lambda v, t: v != t),
    ">": (lambda t: f"> {t}", lambda v, t: v > t),
    ">=": (lambda t: f">= {t}", lambda v, t: v >= t),
    "<": (lambda t: f"< {t}", lambda v, t: v < t),
    "<=": (lambda t: f"<= {t}", lambda v, t: v <= t),
    "BETWEEN": (lambda t: f"Between {t - 50} And {t}",
                lambda v, t: t - 50 <= v <= t),
    "IN": (lambda t: f"In ({t - 50}, {t}, {t + 50})",
           lambda v, t: v in (t - 50, t, t + 50)),
    "IS NULL": (lambda t: "Is Null", lambda v, t: v is None),
    "IS NOT NULL": (lambda t: "Is Not Null", lambda v, t: v is not None),
}


@pytest.mark.parametrize("operator", list(_OPERATORS))
def test_every_row_a_criterion_returns_satisfies_it(
        app: CbdbApp, operator: str, threshold: int):
    """Type an operator into the cell; every row back must match it.

    Eleven operators, of which the suite drove one.  A criterion the
    parser does not recognise is the interesting failure: the grid
    could refuse it, which a user would see, or it could drop the
    condition and answer the unfiltered query, which a user would not.
    Both are caught here -- the first as a non-``ok`` status, the
    second by the rows themselves.

    Nulls are excluded from the comparison for every operator except
    the two that ask about them, because SQL's three-valued logic is
    not what this is testing: ``NULL > x`` is unknown rather than
    false, and a row with no index year is correctly absent from both
    ``> x`` and ``<= x``.
    """
    write, predicate = _OPERATORS[operator]
    criterion = write(threshold)
    payload = _run(app, [_column(_NUMERIC, criteria_text=[criterion])])

    rows = _values(payload)
    if operator not in ("IS NULL", "IS NOT NULL"):
        rows = [value for value in rows if value is not None]

    assert payload["rows"], (
        f"the criterion {criterion!r} returned no rows at all; this "
        "column has values on both sides of every operator here, so an "
        "empty answer means the criterion was not understood")

    wrong = [value for value in rows if not predicate(value, threshold)]
    assert not wrong, (
        f"{len(wrong)} of {len(payload['rows'])} rows do not satisfy "
        f"{criterion!r}: {sorted(set(wrong), key=str)[:8]}")


def test_a_criterion_narrows_what_the_same_query_returns_without_one(
        app: CbdbApp, threshold: int):
    """The rows a criterion admits are a subset of the rows without it.

    Stated separately because the per-operator check above cannot see
    it: a handler that answered *only* the matching rows and a handler
    that answered a different query which happens to match would both
    pass.  This pins the criterion to the query it was typed into.
    """
    unfiltered = _run(app, [_column(_NUMERIC)])
    filtered = _run(app, [_column(_NUMERIC,
                                  criteria_text=[f"> {threshold}"])])

    # Both assertions below hold when `filtered` is empty, which is the
    # third true-by-construction shape AGENTS.md names.  An empty answer
    # is a different failure from an ignored criterion and is caught by
    # the operator tests; here it would merely make this one vacuous.
    assert filtered["rows"], (
        "the criterion returned nothing, so the two assertions below "
        "would hold for the wrong reason")
    assert len(filtered["rows"]) < len(unfiltered["rows"]), (
        "the criterion returned as many rows as no criterion at all")
    assert set(map(tuple, filtered["rows"])) <= set(map(tuple, unfiltered["rows"])), \
        "the criterion returned rows the unfiltered query does not have"


def test_several_criteria_on_one_column_are_alternatives(
        app: CbdbApp, threshold: int):
    """The extra criteria rows are the grid's *Or*, and are ORed.

    ``criteria_text`` is a list because the grid has an "or" row under
    every column, exactly as the Access original does: each entry is
    another alternative for that column, and the handler joins them
    with ``" OR "``.  Reading the list as a conjunction is the natural
    mistake -- this test made it first -- so it is worth pinning which
    way round it goes, because the two differ in the direction a user
    would not notice: an OR read as an AND returns *more* rows, not an
    error.

    Checked as a partition rather than by predicting a count: each
    alternative on its own, and the two together, taken from the same
    grid.
    """
    # Two disjoint bands either side of the discovered median, so a
    # data refresh moves them together rather than emptying one.
    under, over = threshold - 50, threshold + 50
    low = _run(app, [_column(_NUMERIC, criteria_text=[f"< {under}"])])
    high = _run(app, [_column(_NUMERIC, criteria_text=[f"> {over}"])])
    either = _run(app, [_column(_NUMERIC,
                                criteria_text=[f"< {under}", f"> {over}"])])

    assert " OR " in either["sql"].upper(), (
        "two criteria under one column no longer produce an OR; if the "
        f"grid now ANDs them this test has the semantics backwards: "
        f"{either['sql']}")

    lows, highs = set(_values(low)), set(_values(high))
    both = set(_values(either))
    assert lows and highs, "one of the two alternatives returned nothing"
    assert both == lows | highs, (
        f"the two alternatives together returned {len(both)} distinct "
        f"values and separately {len(lows | highs)}; an Or row must "
        "return exactly the union of its alternatives")


def test_criteria_on_two_columns_are_both_applied(
        app: CbdbApp, sqlite_conn, threshold: int):
    """A criterion under each of two columns narrows on both.

    The other half of the same question: one cell with two criteria,
    against two cells with one each.  A grid that applied only the
    last column's criterion would pass every test above.
    """
    # Both values come from the data.  A hand-picked grouping code
    # that stops matching would report a defect against a correct
    # build, and a hand-picked year band would empty on a refresh --
    # which is the whole reason the threshold is discovered.  Take the
    # grouping value with the most rows above the threshold, so the
    # pair is guaranteed to have something on both sides.
    picked = sqlite_conn.execute(
        f"SELECT {_GROUPING} FROM {_TABLE} WHERE {_GROUPING} IS NOT NULL "
        f"AND {_NUMERIC} > ? GROUP BY {_GROUPING} "
        f"ORDER BY COUNT(*) DESC LIMIT 1", (threshold,)).fetchone()
    assert picked, (
        f"no {_GROUPING} value has any row with {_NUMERIC} above "
        f"{threshold}, so there is no input for which both criteria "
        "can hold and this test cannot say anything")
    group_value = picked[0]

    payload = _run(app, [
        _column(_NUMERIC, criteria_text=[f"> {threshold}"]),
        _column(_GROUPING, criteria_text=[f"= {group_value}"]),
    ])
    assert payload["rows"], (
        f"a criterion on each of two columns returned nothing, for "
        f"{_NUMERIC} > {threshold} and {_GROUPING} = {group_value} -- "
        "a pair chosen from the data precisely because rows satisfy "
        "both")

    bad_year = [row[0] for row in payload["rows"]
                if row[0] is None or row[0] <= threshold]
    bad_dynasty = [row[1] for row in payload["rows"]
                   if row[1] != group_value]
    assert not bad_year, (
        f"rows outside the year criterion {_NUMERIC} > {threshold}: "
        f"{bad_year[:8]}")
    assert not bad_dynasty, (
        f"rows outside the grouping criterion {_GROUPING} = "
        f"{group_value}: {bad_dynasty[:8]}")


# ---------------------------------------------------------------------------
# the group functions under a column
# ---------------------------------------------------------------------------

#: The four aggregates the grid offers, and how each relates to the
#: values it was computed over.  ``COUNT`` is left out: it is already
#: driven in ``test_qbe.py`` against the shipped data.
_AGGREGATES = {
    "MAX": lambda values, got: got == max(values),
    "MIN": lambda values, got: got == min(values),
    "SUM": lambda values, got: got == sum(values),
    "AVG": lambda values, got: abs(got - sum(values) / len(values)) < 1e-6,
}


@pytest.mark.parametrize("function", sorted(_AGGREGATES))
def test_an_aggregate_agrees_with_the_rows_it_was_computed_over(
        app: CbdbApp, function: str):
    """``Max`` under a column, against the values in that group.

    The oracle is the grid's own ungrouped answer: run the query once
    grouped and once not, and check the aggregate against the rows the
    same grid returns for the same group.  Nothing is computed from
    the database directly, so a rebuilt handler that grouped correctly
    would still pass.

    One group is checked rather than all of them, chosen as the one the
    grouped query itself reports first: this is about whether the
    function is wired to the right rows, and the second group would
    ask the same question again more slowly.
    """
    grouped = _run(app, [
        _column(_GROUPING, group="GROUP_BY"),
        _column(_NUMERIC, group=function),
    ])
    assert grouped["rows"], f"grouping by {_GROUPING} returned nothing"

    # The first group with a key that can be asked for again: `c_dy`
    # is null for people whose dynasty is unrecorded, and "= null" is
    # not a criterion any grid can express, so that group cannot be
    # re-selected to check the aggregate against.
    candidates = [(key, value) for key, value in grouped["rows"]
                  if key is not None and value is not None]
    if not candidates:
        pytest.skip(f"no group has both a key and a {function} to compare")
    group_value, aggregated = candidates[0]

    members = _run(app, [
        _column(_NUMERIC, criteria_text=["Is Not Null"]),
        _column(_GROUPING, show=False,
                criteria_text=[f"= {group_value}"]),
    ])
    values = [value for value in _values(members) if value is not None]
    assert values, (
        f"the grid reports a {function} for group {group_value} and no "
        "rows in it")

    assert _AGGREGATES[function](values, aggregated), (
        f"{function} over group {group_value} came back as {aggregated}, "
        f"which does not match the {len(values)} rows the same grid "
        f"returns for that group (min {min(values)}, max {max(values)}, "
        f"mean {sum(values) / len(values):.2f})")


def test_a_criterion_under_an_aggregate_filters_the_groups(
        app: CbdbApp, sqlite_conn, threshold: int):
    """A criterion beside a group function is never actually applied.

    ``buildHavingClause`` fires only where a column has both criteria
    and a group function, and nothing in the suite had ever produced
    that combination -- so the whole HAVING path was unreached.  It is
    the natural way to ask *which dynasties have more than five
    people*.

    Both directions are driven, because the failure is not symmetric
    and the asymmetry is the interesting part.  The operand is bound
    as a string; SQLite orders every integer before every string; so
    an aggregate compared with ``>`` matches no group and the same
    aggregate compared with ``<`` matches every group, including the
    ones that plainly contradict the criterion.  A test that sent only
    ``>`` would report "returns nothing" and miss the half that
    returns a wrong answer instead of no answer.

    The statement the grid printed is then run unaltered, with a
    number and with the string, to show that the SQL is right and only
    the binding is wrong.  That is a second oracle and not a
    transcription: nothing is retyped, and the statement is the
    grid's own.
    """
    def grouped(function: str, criterion: str) -> dict:
        column = _NUMERIC if function == "MAX" else "c_personid"
        return _run(app, [
            _column(_GROUPING, group="GROUP_BY"),
            _column(column, group=function, criteria_text=[criterion]),
        ])

    # Both functions, because the entry claims both and because COUNT
    # is the one the developers' own comment above buildHavingClause
    # uses as its worked example -- "how many people per dynasty, keep
    # the dynasties with more than five".
    #
    # Driven by iterating _HAVING_PROBES rather than by four written
    # calls: the coverage gate credits the functions in that mapping,
    # and iterating it is what makes the credit true rather than
    # merely stated.  The lookups below fail loudly if a row goes.
    answers = {
        function: (grouped(function, keeps.format(t=threshold)),
                   grouped(function, drops.format(t=threshold)))
        for function, (keeps, drops) in _HAVING_PROBES.items()
    }
    above, below = answers["MAX"]
    counted_above, counted_below = answers["COUNT"]

    assert "HAVING" in above["sql"].upper(), (
        "a criterion beside a group function did not produce a HAVING "
        f"clause; the grid ran: {above['sql']}")

    kept_above = above.get("rows") or []
    kept_below = below.get("rows") or []
    violating = [row for row in kept_below
                 if row[1] is not None and row[1] >= threshold]
    counted_violating = [row for row in (counted_below.get("rows") or [])
                         if row[1] is not None and row[1] >= 5]

    # Re-run the grid's own printed statement, binding the same
    # threshold the grid was asked for, once as a number and once as
    # text.  This is the file's only second oracle and it is the
    # sanctioned one: the app's own SQL, re-executed, nothing retyped.
    #
    # An earlier version of the guard below wrote out the grouped
    # HAVING query in Python instead, with the correct integer
    # binding, and let its count decide whether an empty grid answer
    # was a defect.  That is the prohibited shape -- predicting the
    # answer by re-implementing the query under test -- and this
    # statement answers the same question without it.
    statement = above["sql"]
    assert statement.count("?") == 1, (
        "the grid's HAVING statement now carries "
        f"{statement.count('?')} placeholders, so binding one value "
        f"below would raise instead of measuring: {statement}")
    as_number = len(sqlite_conn.execute(statement, (threshold,)).fetchall())
    as_text = len(sqlite_conn.execute(statement, (str(threshold),)).fetchall())

    # A build with the binding fixed and no group clearing the
    # threshold would leave kept_above empty, and reading that as a
    # symptom would report a defect against a correct build.
    # ``as_number`` is how many groups the grid's own statement
    # returns when its parameter is bound the way a working build
    # would bind it, so it says whether any group should have come
    # back at all.
    assert as_number, (
        f"the grid's own HAVING statement returns nothing even when "
        f"its parameter is bound as the number {threshold}, so no "
        f"group of {_TABLE} by {_GROUPING} has a maximum {_NUMERIC} "
        "above it and an empty answer from the grid would be correct. "
        "This test cannot tell a working build from a broken one on "
        "this data; the threshold moved.")

    if kept_above and not violating and not counted_violating:
        # Both halves behave: every group above the threshold came
        # back, and none below it kept a group that contradicts.
        wrong = [row for row in kept_above
                 if row[1] is None or row[1] <= threshold]
        assert not wrong, (
            f"{len(wrong)} group(s) came back whose maximum is not above "
            f"{threshold}: {wrong[:5]}")
        # And the COUNT half, which is computed either way and used to
        # be read only inside the finding: a build where `Count > 5`
        # returns nothing while MAX behaves took this branch and went
        # green under a docstring promising both were driven.
        assert counted_above.get("rows"), (
            "MAX behaves but COUNT does not: asking for the groups "
            "with more than five members returned none, though "
            f"{len(counted_below.get('rows') or [])} groups exist.  "
            "That is the same binding fault in the other function, "
            "with nothing above it to contradict.")
        return

    biggest = max((row[1] for row in counted_violating if row[1]), default=0)
    raise KnownShippedDefect(
        "a criterion on a group function never matches what it says.  "
        f"Grouping by {_GROUPING} gives "
        f"{len(counted_below.get('rows') or [])} groups.  Asking for "
        f"those whose Max is > {threshold} returns {len(kept_above)}; "
        f"asking for < {threshold} returns {len(kept_below)}, of which "
        f"{len(violating)} have a maximum of {threshold} or more -- for "
        f"example {violating[:3]}, with the contradicting number in the "
        f"next column.  Count behaves the same way: > 5 returns "
        f"{len(counted_above.get('rows') or [])} groups and < 5 returns "
        f"{len(counted_below.get('rows') or [])}, of which "
        f"{len(counted_violating)} have five or more members and the "
        f"largest has {biggest:,}.  "
        f"The grid printed {' '.join(statement.split())}, and that "
        f"statement returns {as_number} rows when its parameter is the "
        f"number {threshold} and {as_text} when it is the string "
        f"\"{threshold}\", "
        "which is what the grid binds: a criterion's operand is parsed "
        "out of the typed text and never converted.  A column's INTEGER "
        "affinity hides that in a WHERE clause; MAX(...) is an "
        "expression and has none, so SQLite compares an integer with a "
        "string and orders every integer first -- false for every group "
        "under >, true for every group under <")


# ---------------------------------------------------------------------------
# the sort row
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("direction", _SORT_DIRECTIONS)
def test_the_sort_row_orders_the_rows(app: CbdbApp, direction: str):
    """Ascending and descending, checked on the rows themselves.

    ``test_qbe.py`` sends a descending sort already, as part of a join
    query, and never looks at the order that came back -- so the sort
    row was requested and had never been *checked*.  Order is the one
    property of a result that is entirely self-evident: no oracle, no
    knowledge of the data, and a user notices it immediately.
    """
    payload = _run(app, [_column(_NUMERIC, sort=direction,
                                 criteria_text=["Is Not Null"])])
    values = _values(payload)
    assert values, f"sorting {direction} returned no rows"

    expected = sorted(values, reverse=(direction == "DESC"))
    assert values == expected, (
        f"the rows are not in {direction} order; first disagreement at "
        f"index {next(i for i, (a, b) in enumerate(zip(values, expected)) if a != b)}")


def test_two_sorted_columns_order_by_the_first_then_the_second(
        app: CbdbApp):
    """Two sort columns, and the grid must honour both, left to right.

    A grid that emitted only the last sorted column would pass the
    single-column test above.  The pairs are compared as tuples, which
    is what "then by" means and needs nothing from the data.
    """
    payload = _run(app, [
        _column(_GROUPING, sort="ASC", criteria_text=["Is Not Null"]),
        _column(_NUMERIC, sort="DESC", criteria_text=["Is Not Null"]),
    ])
    rows = [(row[0], row[1]) for row in payload["rows"]]
    assert rows, "sorting on two columns returned no rows"

    ordered = sorted(rows, key=lambda pair: (pair[0], -pair[1]))
    assert rows == ordered, (
        "the rows are not ordered by the first sorted column and then the "
        f"second: first disagreement at index "
        f"{next(i for i, (a, b) in enumerate(zip(rows, ordered)) if a != b)}")


def test_a_column_can_sort_the_result_without_appearing_in_it(
        app: CbdbApp):
    """``show: false`` with a sort: order by it, do not display it.

    This is how a user sorts by something they do not want in the
    output, and it is a combination the suite had not sent.  What
    could go wrong is specific: a grid that builds ORDER BY from the
    *displayed* columns would silently drop the ordering, and the
    result would look perfectly reasonable.
    """
    payload = _run(app, [
        _column(_NUMERIC, show=True, criteria_text=["Is Not Null"]),
        _column(_GROUPING, show=False, sort="DESC",
                criteria_text=["Is Not Null"]),
    ])
    assert payload["columns"] == [f"t.{_NUMERIC}"], (
        f"a hidden column appeared in the output: {payload['columns']}")
    assert payload["rows"], "sorting by a hidden column returned no rows"
    assert "ORDER BY" in payload["sql"].upper(), (
        "the hidden column's sort produced no ORDER BY clause; the grid "
        f"ran: {payload['sql']}")

    # And the rows are actually in that order.  The clause appearing is
    # not the claim -- a grid that emitted ORDER BY on the *visible*
    # column, or in the wrong direction, would satisfy that and leave
    # the user with an order they did not ask for.  The hidden column
    # cannot be read from this answer, so the same query is run once
    # more with it shown: same rows, same order, and now inspectable.
    shown = _run(app, [
        _column(_NUMERIC, show=True, criteria_text=["Is Not Null"]),
        _column(_GROUPING, show=True, sort="DESC",
                criteria_text=["Is Not Null"]),
    ])
    keys = [row[1] for row in shown["rows"]]
    assert keys == sorted(keys, reverse=True), (
        "with the sort column shown, the rows are not in descending "
        "order by it, so the hidden-column sort above cannot be trusted "
        "either")
    assert [row[0] for row in shown["rows"]] == _values(payload), (
        "showing the sort column changed the order of the rows; the "
        "hidden and shown queries are meant to differ only in what is "
        "displayed")


# ---------------------------------------------------------------------------
# the join kind
# ---------------------------------------------------------------------------

def test_a_left_join_keeps_the_rows_an_inner_join_drops(app: CbdbApp):
    """INNER and LEFT, over the same two tables and the same key.

    The grid offers both and the suite drove only INNER.  The
    difference is the whole reason a user picks one: a LEFT join keeps
    the rows on the left that have no partner, and a grid that emitted
    INNER for both would silently drop exactly the people a historian
    was looking for -- here, the ones with no dynasty recorded.

    Which people those are is worth naming precisely, because the
    first version of this test named the wrong ones.  It said the
    extra rows were people "whose dynasty code is not in
    ``DYNASTIES``"; there are none of those.  Every non-null
    ``c_dy`` in ``BIOG_MAIN`` resolves.  The rows only a LEFT join
    keeps are the people whose ``c_dy`` is NULL.

    The property needs no oracle and cannot be satisfied by a grid
    that ignores the setting: LEFT must return at least as many rows
    as INNER, and the extra rows must be the ones with nothing on the
    right.  Both are checked, because the first alone would pass if
    the two were identical.
    """
    def joined(kind: str) -> dict:
        return app.json("POST", "/api/qbe/run", json={
            "tables": [
                {"alias": "b", "table": "BIOG_MAIN"},
                {"alias": "d", "table": "DYNASTIES",
                 "join_to": {"kind": kind, "left_alias": "b",
                             "left_col": "c_dy", "right_alias": "d",
                             "right_col": "c_dy"}},
            ],
            "columns": [
                {"table_alias": "b", "field": "c_personid", "show": True},
                {"table_alias": "d", "field": "c_dynasty", "show": True},
            ],
        })

    inner = joined("INNER")
    left = joined("LEFT")
    assert inner["status"] == left["status"] == "ok", (inner, left)
    assert "LEFT" in left["sql"].upper(), (
        f"asking for a LEFT join produced: {left['sql']}")
    assert "LEFT" not in inner["sql"].upper(), (
        f"asking for an INNER join produced a LEFT one: {inner['sql']}")

    inner_rows = {tuple(row) for row in inner["rows"]}
    left_rows = {tuple(row) for row in left["rows"]}

    assert inner_rows <= left_rows, (
        f"{len(inner_rows - left_rows)} rows are in the INNER join and "
        "not in the LEFT join, which cannot drop anything the INNER "
        "join kept")

    # The load-bearing half.  That the extra rows carry NULL on the
    # right is guaranteed by SQL itself and asserting it would prove
    # nothing; that there *are* extra rows is the claim, and it holds
    # here because some people in BIOG_MAIN have no dynasty recorded.
    # If that ever stops being true this test needs a different pair
    # of tables, and the message says so.
    unmatched = left_rows - inner_rows
    assert unmatched, (
        "the LEFT join returned exactly the INNER join's rows.  Either "
        "every person in BIOG_MAIN now has a dynasty recorded -- in "
        "which case this test needs a pair of tables where some row on "
        "the left has no partner -- or the join kind is being ignored. "
        "Check the first: SELECT COUNT(*) FROM BIOG_MAIN WHERE c_dy IS "
        "NULL.")


# ---------------------------------------------------------------------------
# what the grid does with a cell it cannot parse
# ---------------------------------------------------------------------------

#: Criterion text that is not a criterion, and what the grid does with
#: each.  Split by outcome, because the two outcomes are different
#: findings: refusing is correct, and quietly turning the text into a
#: value is not.
_REFUSED = [
    "Between 1100",             # BETWEEN with one operand
    "In (",                     # an unclosed list
    ">",                        # an operator with nothing to compare
    "> 1100 And",               # a dangling conjunction
]

#: Text the parser turns into an equality against itself.  Each of
#: these names an operator; none is a value.  Pinned exactly, so a
#: build that starts refusing one of them fails here and the entry can
#: be shrunk.
_REINTERPRETED = {
    "Like": "the operator alone: the dispatcher accepts the prefix, the "
            "parse requires a trailing space",
    "Between1100And1200": "the same disagreement, one character wide",
}

#: A criterion whose parts are separated by tabs rather than spaces.
#: The tokenizer splits on the space character only, so everything
#: after the first comparison is swallowed into that comparison's
#: operand: ``>1434	And	<1534`` is bound as the single string
#: ``"1434	And	<1534"``.  A criteria cell is a plain text input, so
#: a tab arrives by pasting out of a spreadsheet.
#:
#: Which way that goes wrong depends on the column, and the first
#: version of this file guessed the wrong one.  On a column with
#: INTEGER affinity -- ``c_index_year`` is ``smallint(6)`` -- SQLite
#: tries the column's affinity on the bound text, cannot make a number
#: of it, leaves it TEXT, and sorts every integer before every string:
#: the comparison is false for every row and the answer is *empty*.
#: The upper bound is indeed dropped from the SQL, but the result is
#: not a wider band, it is no band at all.
_TAB_SEPARATED = ">{low}	And	<{high}"


@pytest.mark.parametrize("criterion", _REFUSED)
def test_a_criterion_that_cannot_be_parsed_is_refused(
        app: CbdbApp, criterion: str):
    """These four are handled correctly, and this holds them there.

    A criterion cell the grid cannot read has to be reported.  These
    four are: each comes back as an HTTP 400 with a message a user can
    act on.  Worth a test because the alternative -- treating an
    unreadable cell as an empty one and running the unfiltered query --
    is what the next test finds the grid doing with three other
    spellings.
    """
    response = app.post("/api/qbe/run", json={
        "tables": [{"alias": "t", "table": _TABLE}],
        "columns": [_column(_NUMERIC, criteria_text=[criterion])],
    })

    # 400 specifically, not "anything that is not 200".  A 500 is the
    # server falling over on input it should have rejected politely,
    # and an error-contract test that accepts a crash as a pass is
    # checking the wrong thing.
    assert response.status_code == 400, (
        f"the grid answered {criterion!r} with HTTP "
        f"{response.status_code}; an unreadable criterion should be "
        f"refused with 400 and a message.  It said: "
        f"{response.text[:200]}")
    assert response.text.strip(), (
        f"the grid refused {criterion!r} with an empty body, so the user "
        "is told nothing about what to fix")


def test_a_criterion_the_grid_cannot_parse_is_not_silently_reinterpreted(
        app: CbdbApp, threshold: int):
    """``Like`` on its own becomes a search for the word "Like".

    The parser recognises an operator only when a space follows it and
    otherwise falls through to a branch that treats the whole cell as a
    value.  So a user who types an operator name and stops -- or who
    types it without spaces -- gets an equality test against their own
    typing, an empty grid, and no message.

    The comparison here is with the four spellings the grid *does*
    refuse: the parser is not missing validation in general, so these
    are not a gap in it so much as a branch that answers a question
    nobody asked.  The SQL is read to show what the criterion became,
    which is the part that makes the finding legible.
    """
    became: dict[str, tuple[int, str]] = {}
    refused: list[str] = []
    surprising: list[str] = []
    for criterion in _REINTERPRETED:
        response = app.post("/api/qbe/run", json={
            "tables": [{"alias": "t", "table": _TABLE}],
            "columns": [_column(_NUMERIC, criteria_text=[criterion])],
        })
        payload = {}
        if response.status_code == 200:
            payload = response.json()
        if response.status_code == 400 or payload.get("status") == "error":
            refused.append(criterion)      # the correct answer
            continue
        if response.status_code != 200 or payload.get("status") != "ok":
            surprising.append(
                f"{criterion!r} -> HTTP {response.status_code}, "
                f"status {payload.get('status')!r}")
            continue
        sql = " ".join(payload.get("sql", "").split())
        if " = ?" in sql:
            became[criterion] = (len(payload.get("rows") or []), sql[-46:])
        else:
            surprising.append(
                f"{criterion!r} -> accepted, but the SQL has no bound "
                f"equality: ...{sql[-60:]}")

    # Every spelling has to land somewhere.  Without this the test had
    # no assertion at all: a build answering HTTP 500 to all of them,
    # or one whose SQL shape changed, fell through every branch and
    # passed green while the docstring claimed the opposite.
    assert not surprising, (
        f"a criterion in _REINTERPRETED did neither of the two things "
        f"this test knows how to read -- it was not refused with a "
        f"message and it was not turned into an equality against its "
        f"own text: {surprising}.  Read the response before deciding "
        f"whether this is a fix or a new defect.")

    # The tab case, driven separately because it goes wrong through a
    # different route: not "the grid did not recognise this operator"
    # but "the grid recognised the first one and ate the rest".
    low, high = threshold - 50, threshold + 50
    tabbed = app.post("/api/qbe/run", json={
        "tables": [{"alias": "t", "table": _TABLE}],
        "columns": [_column(_NUMERIC, criteria_text=[
            _TAB_SEPARATED.format(low=low, high=high)])],
    })
    spaced = _run(app, [_column(_NUMERIC,
                                criteria_text=[f">{low} And <{high}"])])
    correct = len(spaced["rows"])
    assert correct, (
        f"the band {low} < {_TABLE}.{_NUMERIC} < {high}, written with "
        "spaces, returned nothing, so the tab comparison below has no "
        "reference to be read against.  The threshold fixture picks a "
        "median, so this means the data moved, not that the grid is "
        "wrong.")

    if tabbed.status_code != 200 or tabbed.json().get("status") != "ok":
        pass                        # refused: the correct answer
    else:
        tab_rows = len(tabbed.json().get("rows") or [])
        tab_sql = " ".join(tabbed.json().get("sql", "").split())
        if tab_rows != correct:
            became["a tab where a space was meant"] = (
                tab_rows,
                f"{correct} rows for the same band written with spaces; "
                f"...{tab_sql[-44:]}")

    if became:
        raise KnownShippedDefect(
            "criterion text the grid cannot parse becomes an equality "
            "against that text rather than an error: "
            + "; ".join(f"{text!r} -> {rows} rows, ...{sql}"
                        for text, (rows, sql) in sorted(became.items()))
            + f".  Driven against {_TABLE}.{_NUMERIC}.  Of the "
              f"{len(_REINTERPRETED)} spellings sent, {len(refused)} "
              f"were refused properly ({sorted(refused)}) and the rest "
              f"are above.  The grid also refuses {sorted(_REFUSED)}, "
              "with a message, so "
              "the validation is not missing in general -- these reach a "
              "branch that treats anything it does not recognise as a "
              "value, and the user is shown an empty grid for a query "
              "they did not write.  The tab row, where present, is the "
              "one case that is not an equality: there the first "
              "comparison survives and swallows the rest of the cell as "
              "its operand, so on a column with INTEGER affinity the "
              "bound text never compares true and the band comes back "
              "empty rather than wide")


def test_an_in_list_keeps_a_value_that_contains_a_comma(
        app: CbdbApp, sqlite_conn):
    """``In("Chen Shi (Mother, Nominal of Lie)")`` finds nobody.

    The list inside the parentheses is split on every comma, without
    regard for the quotes around each value -- so a name containing one
    becomes two operands, neither of which matches anything.  In this
    data that is not a curiosity: a woman identified by her
    relationships is recorded exactly that way, and 690 names in
    ``BIOG_MAIN`` alone contain a comma.

    The control is the same value under ``=``, which works.  That is
    what makes this a defect in the list parser rather than a claim
    about the name or the data: one operator finds the person and the
    other does not.
    """
    row = sqlite_conn.execute(
        "SELECT c_name FROM BIOG_MAIN WHERE c_name LIKE '%, %' "
        "AND c_name IS NOT NULL ORDER BY LENGTH(c_name), c_name "
        "LIMIT 1").fetchone()
    if row is None:
        pytest.skip("no name in BIOG_MAIN contains a comma, so the list "
                    "parser cannot be tested on one")
    name = row[0]

    def rows_for(criterion: str) -> tuple[int, str]:
        payload = app.json("POST", "/api/qbe/run", json={
            "tables": [{"alias": "t", "table": _TABLE}],
            "columns": [{"table_alias": "t", "field": "c_name",
                         "show": True, "criteria_text": [criterion]}],
        })
        return len(payload.get("rows") or []), " ".join(payload["sql"].split())

    quoted = f'"{name}"'
    by_equals, _ = rows_for(f"={quoted}")
    by_list, list_sql = rows_for(f"In ({quoted})")

    assert by_equals, (
        f"the control failed: {name!r} is in the database and `=` did "
        "not find it, so this test cannot say anything about `In`")

    if by_list != by_equals:
        placeholders = list_sql.count("?")
        raise KnownShippedDefect(
            f"`=` finds {name!r} and returns {by_equals} row(s); the same "
            f"value in an In(...) list returns {by_list}.  The list was "
            f"split at the comma inside the name -- the SQL carries "
            f"{placeholders} placeholders for one value -- so neither "
            "half matches anything, and the query answers without "
            "saying so")


# ---------------------------------------------------------------------------
# the lists above, against the enums the build declares
# ---------------------------------------------------------------------------

#: Where each closed enum lives in the shipped Go, and the Python name
#: that is supposed to cover it.  The grid's vocabulary is finite and
#: declared, so there is no reason for this file to keep its own copy
#: unchecked -- a twelfth operator or a sixth aggregate would otherwise
#: appear in the build and go on being untested in silence.
_ENUMS = {
    "operators": ("qbe_criteria.go", r"Op\w+\s+CompOp\s+=\s+\"([^\"]+)\""),
    "aggregates": ("qbe_gridstate.go", r"Group\w+\s+GroupFunc\s+=\s+\"([^\"]+)\""),
    "sorts": ("qbe_gridstate.go", r"Sort\w+\s+SortOrder\s+=\s+\"([^\"]*)\""),
}


def test_the_columns_with_no_affinity_are_the_ones_the_entry_names(
        sqlite_conn, layout):
    """Which offered columns have no declared type: measured, not assumed.

    The group-function finding turns on affinity.  A criterion's
    operand is bound as text, and a column's declared type hides that
    by converting it -- so the places where the string binding is
    *visible* in a WHERE clause are exactly the offered columns whose
    declared type is empty.  The entry says there are three and names
    them, and that scope claim is what keeps the finding from reading
    as "the Query Builder cannot filter numbers at all".

    A claim carried only in an entry's prose is the part a cleared
    registry deletes, so it is derived here from the two things the
    build ships -- the grid's own column whitelist and the database's
    own declared types -- and pinned.

    One column is deliberately not in the answer.  ``View_KinAddr``
    offers ``c_index_year_type_desc``; the view exposes it as
    ``c_index_year_type_desc:1``, so the name the grid sends matches
    no column and the query errors before any comparison happens.
    That is the renamed-column defect, not this one, and a reader
    recounting from the schema alone would make it a fourth.
    """
    schema = json.loads(layout.schema_json.read_text(encoding="utf-8"))
    offered = {(table["name"], column["name"])
               for table in schema
               for column in table["columns"]}
    assert offered, "the shipped qbe_schema.json offers no columns at all"

    declared: dict[tuple[str, str], str] = {}
    unresolved: list[str] = []
    for table, column in sorted(offered):
        rows = sqlite_conn.execute(
            f'PRAGMA table_info("{table}")').fetchall()
        types = {row[1]: (row[2] or "") for row in rows}
        if column not in types:
            unresolved.append(f"{table}.{column}")
            continue
        declared[(table, column)] = types[column]

    no_affinity = sorted(f"{table}.{column}"
                         for (table, column), kind in declared.items()
                         if not kind.strip())

    assert no_affinity == [
        "View_BiogSourceData.c_hyperlink",
        "View_KinAddr.c_node_index_year_type_desc",
        "View_PeopleData.c_index_year_type_desc",
    ], (
        f"the offered columns with no declared type are now "
        f"{no_affinity}, and the registry entry on group-function "
        "criteria names three.  If the list grew, the entry's scope "
        "sentence is too narrow; if it shrank, the entry may be "
        "reporting a defect on a column that no longer exists.  "
        f"({len(offered)} columns offered, {len(unresolved)} of which "
        "name nothing in the view they belong to -- those are the "
        "renamed-column defect and are counted separately.)")

    # And the reason the first of the three is a weak example, said
    # here rather than discovered again: it holds no values.
    total, present = sqlite_conn.execute(
        'SELECT COUNT(*), COUNT(c_hyperlink) FROM "View_BiogSourceData"'
    ).fetchone()
    assert total and not present, (
        f"View_BiogSourceData.c_hyperlink now has {present} non-null "
        f"values of {total} rows.  It had none when the entry was "
        "written, which is why the entry rests on the other two: a "
        "comparison against an all-NULL column returns nothing "
        "whatever the operand is bound as, so it cannot show the "
        "difference this finding is about.")


def test_the_grid_vocabulary_the_build_declares_is_one_it_accepts(
        app: CbdbApp, layout):
    """Send every token the build's own enums declare, and see.

    The inventory comes from the shipped Go -- the ``CompOp``,
    aggregate and ``SortOrder`` constants -- so a token the build
    gains is a token this test starts sending, without anyone
    remembering to add it.  AGENTS.md § *Coverage is the program's
    job*: the decision of what to exercise belongs to the build, not
    to a list somebody kept by hand, because a hand-kept list is how
    the *Use XY* switches went unsent for the life of the suite.

    What this asks is narrow on purpose: does the grid accept each
    token it advertises?  What each token *means* is checked by the
    tests above, against real data on ``BIOG_MAIN``.  This one exists
    so those cannot quietly stop covering the vocabulary.

    It sends the tokens itself, and that is the point.  Four earlier
    versions instead asked whether some *other* test drove each one --
    by grepping this module's text (its own line matched), then one
    function's source (the docstring matched), then a single line of
    it (a comment would match), then by reading a shared constant and
    a parametrisation (edit the request and the credit outlives it).
    Every one of those is a claim *about* a request made elsewhere,
    and such a claim can always be falsified by editing that request.
    Tightening the claim never fixed it; removing the distance did.
    After this test runs, each declared token has been through
    ``/api/qbe/run`` because this test put it there.

    The probes go against a small table (``_PROBE_TABLE``) so that
    eighteen of them cost about what one query on ``BIOG_MAIN`` does.
    """
    found = {}
    for name, (source, pattern) in _ENUMS.items():
        text = (layout.code_dir / source).read_text(
            encoding="utf-8", errors="replace")
        found[name] = {m for m in re.findall(pattern, text)}
        assert found[name], f"no {name} enum found in {source}"

    def probe(columns: list[dict]) -> tuple[int, str, str]:
        """One request against the small table; how it was answered.

        The SQL the grid printed comes back too, because "accepted"
        is too weak a question to ask here.  The criteria parser
        treats anything it does not recognise as a bare value and
        answers 200 for it -- that is CBDB-D-023 -- so a probe that
        only checked the status would pass on a build that had
        stopped understanding the token entirely.  What the grid put
        in its SQL is what says the token was understood.
        """
        response = app.post("/api/qbe/run", json={
            "tables": [{"alias": "p", "table": _PROBE_TABLE}],
            "columns": columns,
        })
        if response.status_code != 200:
            return response.status_code, "", ""
        payload = response.json() or {}
        return (200, payload.get("status", ""),
                " ".join(str(payload.get("sql", "")).split()).upper())

    def cell(field: str, **extra) -> dict:
        return {"table_alias": "p", "field": field, "show": True, **extra}

    # Operators.  Every declared one is *sent*, here, now.  A spelling
    # must exist for each, so an operator the build gains fails on the
    # lookup rather than passing unnoticed.
    unspellable = sorted(found["operators"] - set(_PROBE_CRITERIA))
    assert not unspellable, (
        f"the build declares operator(s) {unspellable} that this file "
        "has no spelling for, so they cannot be driven.  Add each to "
        "_PROBE_CRITERIA as a user would type it.")
    stale = sorted(set(_PROBE_CRITERIA) - found["operators"])
    assert not stale, (
        f"this file spells operator(s) {stale} the build no longer "
        f"declares.  The build declares {sorted(found['operators'])}.")

    refused = {}

    def used(token: str, sql: str) -> bool:
        """Is ``token`` in ``sql`` as a token, not as a fragment?

        Plain containment credits the wrong operator.  ``<`` is a
        substring of both ``<=`` and ``<>``, so a probe that sent
        ``<= 5`` would satisfy a check for ``<`` and the gate would
        report ``<`` as exercised by a request that never used it --
        which is the whole failure this gate exists to prevent,
        reappearing one level down.  ``>`` and ``>=`` are the same
        pair.  Word operators have the matching hazard: ``IN`` sits
        inside ``JOIN`` and inside any identifier spelled with it.

        So a symbolic operator must not be flanked by more operator
        characters, and a word operator must not be flanked by more
        word characters -- digits included, because an identifier may
        end in one and ``IN2`` is no more an ``IN`` than ``JOIN`` is.

        One limit, stated rather than fixed: this is not quote-aware,
        so a token appearing as a quoted identifier or inside a
        string literal in the emitted SQL would count.  No probe here
        can produce that -- their operands are bound parameters, and
        neither the probe table's name nor its two columns contain an
        operator token -- but a future probe on a differently named
        column would need this to look at unquoted SQL only.
        """
        if token[0].isalpha():
            pattern = rf"(?<![A-Z0-9_]){re.escape(token)}(?![A-Z0-9_])"
        else:
            pattern = rf"(?<![<>=!]){re.escape(token)}(?![<>=!])"
        return re.search(pattern, sql) is not None

    def record(label, sent, code, status, sql, expected):
        """Keep the probe unless the grid both accepted and used it."""
        if code != 200 or status != "ok":
            refused[label] = (sent, code, status, "")
        elif not used(expected, sql):
            refused[label] = (sent, code, status, sql[-70:])

    for operator in sorted(found["operators"]):
        field = _PROBE_TEXT if operator == "LIKE" else _PROBE_NUMERIC
        written = _PROBE_CRITERIA[operator]
        code, status, sql = probe([cell(field, criteria_text=[written])])
        record(operator, written, code, status, sql, operator)

    # Group functions, the same way.  GROUP_BY and the empty default
    # are not functions; each real one is sent beside a GROUP_BY.
    functions = found["aggregates"] - {"", "GROUP_BY"}
    for function in sorted(functions):
        code, status, sql = probe([cell(_PROBE_TEXT, group="GROUP_BY"),
                                   cell(_PROBE_NUMERIC, group=function)])
        record(f"{function}()", function, code, status, sql, function)

    # And the sort directions.
    for direction in sorted(found["sorts"] - {""}):
        code, status, sql = probe([cell(_PROBE_NUMERIC, sort=direction)])
        record(f"sort {direction}", direction, code, status, sql, direction)

    assert not refused, (
        f"the build declares {len(found['operators'])} operators, "
        f"{len(functions)} group functions and "
        f"{len(found['sorts'] - {''})} sort directions, and refused "
        f"{len(refused)} of them against "
        f"{_PROBE_TABLE}: "
        + "; ".join(
            f"{name} (sent {sent!r}, HTTP {code}, status {status!r}"
            + (f", and the SQL it built ends ...{sql}" if sql else "")
            + ")"
            for name, (sent, code, status, sql) in sorted(refused.items()))
        + ".  Each of these is a token the build's own enums declare. "
        "A row with SQL shown was accepted and then not used -- the "
        "grid answered 200 without putting the token in the statement, "
        "which is what happens when the criteria parser falls through "
        "to treating a cell as a bare value.  A row without SQL was "
        "refused outright.  Either the grid has stopped honouring "
        "something it advertises, or the spelling in _PROBE_CRITERIA "
        "is wrong.")

    # What each token *means* is checked by the tests above, on the
    # real table.  This one exists so that the meaning-checks cannot
    # quietly stop covering the vocabulary: every declared token has
    # now been through the endpoint in this run, because this test
    # sent it -- not because a list somewhere says it did.  Every
    # earlier version asked instead whether some *other* test drove
    # each token, first by searching source text and then by reading
    # a value the test was supposed to send, and each could be left
    # crediting a token no request carried.  AGENTS.md records the
    # two kinds under § Coverage is the program job.


@pytest.mark.parametrize("criterion", _LIKE_CRITERIA)
def test_the_like_operator_matches_a_pattern(app: CbdbApp, criterion: str):
    """``Like "%shi%"`` -- the one operator the page's help advertises.

    Left out of the operator table above because it is the only one
    whose meaning is not a comparison: it takes a pattern, and the
    check is that every row returned contains what was asked for.
    Driven on a text column, which is also the control for
    the claim that the string binding is only wrong where the
    left operand has no affinity -- here the operand *should* be text,
    and is.

    Parametrised over a one-element list so that the coverage gate
    can credit LIKE from the same object that sends it; see
    ``_LIKE_CRITERIA``.
    """
    payload = _run(app, [{"table_alias": "t", "field": "c_name",
                          "show": True,
                          "criteria_text": [criterion]}])
    names = [value for value in _values(payload) if value is not None]
    assert names, f"{criterion} returned no rows on c_name"

    pattern = criterion.split('"')[1].strip("%").lower()
    wrong = [name for name in names if pattern not in name.lower()]
    assert not wrong, (
        f"{len(wrong)} of {len(names)} rows do not contain the pattern "
        f"{pattern!r} asked for by {criterion}: {wrong[:5]}")

    assert "LIKE" in payload["sql"].upper(), (
        f"a Like criterion did not produce a LIKE clause: {payload['sql']}")


def test_two_comparisons_in_one_cell_are_both_applied(
        app: CbdbApp, threshold: int):
    """``> 1100 And < 1200`` in a single cell, which is the documented shape.

    The grammar at the top of ``qbe_criteria.go`` is explicit:
    ``criterion := comparison (("And" | "Or") comparison)*``.  A user
    typing a band into one cell is the ordinary way to ask for one,
    and it is a different path from the *Or* rows the test above
    covers -- those are separate entries in the list, this is one
    entry with a conjunction inside it, and the parser splits them at
    different places.

    Both halves must bind.  A grid that kept only the first
    comparison would return a set that is too *large*, which is the
    direction a user does not notice.
    """
    low, high = threshold - 50, threshold + 50
    payload = _run(app, [_column(_NUMERIC,
                                 criteria_text=[f"> {low} And < {high}"])])

    values = [value for value in _values(payload) if value is not None]
    assert values, (
        f"'> {low} And < {high}' returned no rows, though the threshold "
        "was chosen to have values on both sides")

    outside = [value for value in values if not low < value < high]
    assert not outside, (
        f"{len(outside)} of {len(values)} rows are outside the band both "
        f"comparisons describe: {sorted(set(outside))[:8]}.  If only the "
        "first comparison bound, the answer is wider than the user asked "
        "for and nothing on screen says so")

    # And it is genuinely narrower than either half alone, which is
    # what says both were applied rather than one of them twice.
    just_low = _run(app, [_column(_NUMERIC, criteria_text=[f"> {low}"])])
    assert len(payload["rows"]) < len(just_low["rows"]), (
        f"the band returned {len(payload['rows'])} rows and its lower "
        f"half alone returned {len(just_low['rows'])}; the upper "
        "comparison is not being applied")

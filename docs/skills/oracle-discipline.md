# Skill: oracle-discipline

**Status:** repo-local (2026-09-04). Read this before writing or
reviewing any assertion in this suite.

This is the skill that matters most here. Everything else is mechanics.

## When to use

- Writing any new test, of anything
- Reviewing a test someone else wrote
- Deciding whether a difference you have found is a defect or your own
  expectation being wrong

If you are only changing infrastructure with no assertions about the
application's answers, skip it.

## The rule

**The code under test is `Bin/cbdb.exe`.** A test may never compute what
the answer should be by re-running the application's own logic.

The reason is not purity. It is that the copy gets written by reading the
original, so it agrees with the original — including everywhere the
original is wrong. A transcription oracle cannot find a bug; it can only
confirm that the transcription was done carefully.

## The one place the rule bends: choosing an input

Reading the data to decide **what to ask** is allowed, and encouraged.
Reading it to decide **what the answer should be** is the prohibition
above.

    allowed:    "which (entry code, dynasty) pairs have at least 20 rows
                 in ENTRY_DATA joined to BIOG_MAIN?"
                 -> the answer is a request to send.  If it is wrong, or
                 the join is not the handler's, the test still checks
                 exactly what it claims, on a duller input.

    forbidden:  "that join says 47 rows, so the form must return 47."
                 -> the handler's SQL retyped, agreeing with the
                 original wherever the original is wrong, and a false
                 alarm the day the handler legitimately adds a join.

`cbdb_desktop/discovery.py` lives on the allowed side of that line and
says so at length in its own docstring. The properties the matrix then
asserts hold whatever the data contains: every row satisfies the filter
it was given, narrowing never adds rows, adjacent windows stay disjoint.
None of them is a count.

Two rules that come with it:

- **Never hand-pick an input.** Half the time it lands on sparse data,
  the response is empty, and the assertions run against nothing while
  looking exactly like a pass. Discover it.
- **Then verify the input is live, against the application.** A code can
  have rows in its base table and contribute nothing to a form's result
  — four of five candidate text ids did, until the discovery query was
  pointed at the table the form's default mode actually reads. Asking
  the app which of its own codes return rows is still input selection;
  no expectation is derived from the answer.

## Two questions that settle it

### 1. Would this assertion survive a rewrite?

If `handleQuery` were thrown away and rewritten from scratch to the same
specification, would this assertion still be meaningful and still be
right?

- "every returned person exists in `BIOG_MAIN`" — yes. Oracle.
- "the result has exactly the rows this SELECT returns" — no; it would
  have to be rewritten alongside. Transcription.

### 2. Could this assertion fail?

Write down what a broken build would have to do to make it red. If you
cannot describe such a build, the assertion is decoration.

Real examples from this repo, all of which passed review at first:

| Assertion | Why it cannot fail |
|---|---|
| Group Data's `statusCount == len(statusRecords)` | the Go assigns each count *from* its slice length (`groupdata_form_backend.go:492`) |
| edge endpoints ⊆ node list | the node list is built from the edges by the same pipeline |
| `people(one_code) <= people(both_codes)` | true when the filter is ignored *and* when it returns nothing |
| kinship count == networks count | both handlers run the same `SELECT COUNT(*)` on the same table |
| exported row count == grid row count (office/status/texts/places) | the export serialises the array the test just posted to it |

### When the two questions disagree

An assertion can survive a rewrite and still be unable to fail. The
four export comparisons for office, status, texts and places are
exactly that: the export serialises the array the test posted to it, so
the row counts cannot differ -- but the pair does pin something real,
that the export struct's JSON tags still match the query response's.
If they drifted, Go would decode zero-valued structs and the person ids
would come back as 0.

So the rule is not "delete anything that cannot fail". It is:

1. Work out what the assertion *does* pin, if anything.
2. If the answer is nothing, remove it.
3. If it is something narrower than the name suggests, keep it and say
   so in the docstring -- `test_form_queries.py`'s module docstring
   ranks its own export comparisons for this reason.

The fix, where one exists, is usually to find the *asymmetric* version:

- Counts: turn one request flag off and assert only that section emptied.
- Subset: compare `Counter` of `(person, code)` for A, B and A+B and
  assert `a + b == together` — false in both degenerate cases.
- Shared table: assert a write through *one* form is visible through the
  *other*, not that two readers agree.
- Traversal: assert the distance limits were applied
  (`max(nodeDist) <= maxNodeDist`), not that the graph is self-consistent.

## What counts as an oracle

| Kind | Example here |
|---|---|
| HTTP contract | 405 for an unregistered verb; declared JSON keys; page returns HTML |
| App-vs-app agreement | `store-person-ids` in Entry, then `store-count` in Kinship |
| Base facts from the shipped DB | `COUNT(*) FROM BIOG_MAIN`; "is this id in `ADDR_CODES`" |
| Go source as data | the 141 registered routes; the `/{page}` map |
| Frozen goldens | 37,118 address rows; 1,350 QBE columns |
| Internal invariants | every row carries a code that was requested |
| Monotonicity | a deeper kinship search cannot lose relatives |
| Idempotence | the same query twice gives the same answer |

### The base-fact boundary

A base fact is a property of the *data*: how many rows a table has,
whether an id exists in a code table. It stays true however the
application is written.

It stops being a base fact the moment it starts reproducing the
handler's *filtering*. The tell is usually that you have written the
same `WHERE` clause, or that you had to add a join to make the numbers
agree. If you find yourself tuning the query until it matches, stop: an
oracle tuned until it agrees with the implementation is the
implementation.

## Choosing inputs is not an oracle

Asking the database "which entry codes have between 2 and 12 rows" to
keep a response small is fine — it selects an input and predicts nothing
about the output. Asking the *application* which of its codes return rows
is also fine, and necessary: four of five candidate text ids have base
rows and produce no result.

Keep the two apart in your head. Input selection may look at anything.
Output judgement may not look at the handler.

## Before calling something a defect

1. **Reproduce it through the running binary**, not only in SQL. The
   shipped `cbdb.exe` embeds its own SQLite build; a check with the
   system `sqlite3` disagreed with the app about `LIKE` on an FTS table
   and nearly hid the unbuilt-name-index finding.
2. **Try to refute it.** Is it intended? Documented? A test artefact? A
   misread of the schema? Two things that looked like defects here were
   not: the address picker's repeated rows, and IndexAddr's duplicate
   check stopping at a disabled slot.
3. **Find the decisive experiment.** For that one it was running
   `INSERT INTO ZZZ_NAMES_FTS(...) VALUES('rebuild')` on a copy and
   re-testing through the same binary: every search then returned exactly
   the counts the data supports. That converts "looks broken" into
   "here is the fix, verified".
4. **Then** write it into `defects.py` — see
   `issue-report-maintainer.md`.

## Cost discipline

Nothing here has a LIMIT. Before adding a test that runs a real query:

- Pick a filter that keeps the result in the tens of rows.
- Add a resource guard (`assert len(rows) < 5000`) so a future fan-out
  join fails fast and legibly instead of downloading for five minutes.
- Never probe existence by calling a handler. `PATCH` gets you 405 (path
  exists) or 404 (it does not) without running anything.

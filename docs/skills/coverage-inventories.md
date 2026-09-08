# Skill: adding coverage — through an inventory, never by hand

**Read this before adding a test that drives anything new**: an
endpoint, a button, a filter, an export format, a page.

The rule, from the maintainer:

> Put repeatable test logic into the program. Do not rely on an agent
> devising a fresh test plan each round.

This is not a style preference. It is the difference between the two
states this suite has actually been in:

- **Before.** Each round, an agent read the code, decided what looked
  worth testing, and wrote tests for that. Result: 6 of the 42
  file-producing endpoints driven, and every run reporting "no export
  problems found".
- **After.** The endpoints are enumerated from the build and a gate
  fails if any is undriven. The first run under that regime found four
  defect families, two of them buttons that answer HTTP 500 on every
  input and always have.

Nobody was careless. The plan simply covered what the planner thought
of, and there was no mechanism that could notice the difference.

---

## The four inventories

| module | enumerates | from | gate |
|---|---|---|---|
| `cbdb_desktop/routes.py` | every route the binary registers | `Code/*.go` | `test_routes.py` |
| `cbdb_desktop/exports.py` | every endpoint that hands the user a file | the same routes, name-filtered | `test_exports.py::test_every_export_route_is_driven` |
| `cbdb_desktop/controls.py` | every `<button>` and the endpoints its click can reach | `Templates/**/*.html` | `test_zz_controls.py` |
| `cbdb_desktop/discovery.py` | populated `(code, dynasty)`, `(code, half-century)`, `(code, address)` combinations | the shipped database's row counts | `test_query_matrix.py::test_the_discovered_matrix_covers_every_form_and_dimension` |

## What to do, by what you are adding

**A new endpoint the build registers.** Nothing, if it is not an
export: `test_routes.py` already drives or probes the whole route
surface, and its counts are pinned, so a new route fails there and gets
read. If it produces a file, add an `ExportSpec` — see below.

**A new export.** Add an `ExportSpec` to `exports.py`. You need four
things, and three of them are observations, not decisions:

1. the request body, from the handler's request struct in the Go source;
2. the **envelope** — `STATUS_FILES`, `FILES`, `SINGLE_FILE` or `RAW`.
   Do not guess: three shapes are in live use and the choice is not
   systematic. Drive the endpoint once and look.
3. the **file names**, pinned exactly. A dropped or renamed file is a
   file somebody's next step cannot find.
4. whether it `reads_scratch`. If it does, the test must re-run the
   form's query immediately before, and the order is the contract.

**A new button.** `test_zz_controls.py::EXPECTED_BUTTONS` will fail with
the new count. Then decide: does the button reach an endpoint? If so,
the endpoint gate fails until something drives it — and driving it is
the answer, even where that is awkward. `/api/indexaddr/update` rewrites
`BIOG_MAIN` for 659,000 people and is still driven, against a private
copy of the database in `test_index_addr.py`. `ENDPOINTS_NOT_DRIVEN` is
currently empty and should stay that way: an entry there is a hole in
the gate.

**A new filter or parameter on a form.** Add its field name to
`FormSpec` (`year_filter_field`, `addr_field`, `subunit_field` and
friends exist because every form spells the same filter differently),
add a dimension to `discovery.py`, and add the property the filter must
have to `test_query_matrix.py`. Do not write a test that drives one
hand-chosen value.

**A new page.** `controls.py::_pages` picks up form templates, pickers
and QBE automatically; the button count and the endpoint gate will fail
until it is accounted for.

---

## Rules that make an inventory worth having

### 1. Extract, do not transcribe

An inventory written by reading the code is a snapshot of what someone
saw. An inventory *extracted* from the build is a fact about the build,
and it moves when the build moves. Everything in the four modules above
is parsed out of the shipped artefacts. Where extraction is impossible
— the exact request body a handler wants — the value is small, explicit,
and pinned.

### 2. An empty parametrization is a failure, not a pass

pytest reports "0 tests collected for this parameter set" as green. Any
generated matrix therefore needs a companion test asserting it is
populated, per form and per dimension. `test_query_matrix.py` has one;
without it, a discovery query that returned nothing would silently empty
234 tests and the run would still be green.

The same trap in another shape: a test whose result set is empty asserts
nothing. Prefer `pytest.skip` with the reason and the base row count
over an assertion that passes vacuously, and make the *matrix-level*
test the thing that fails when a whole dimension goes quiet.

### 3. Measure coverage; do not assert it

`CbdbApp.requested` records every `(method, path)` the run issues.
`test_zz_controls.py` compares that record against every endpoint the
pages can reach, and writes the numbers to
`artifacts/endpoint_coverage.json`. "The exports are covered" is a
claim. A count is evidence.

That test refuses to judge a filtered run (`-k`, `-m`, an explicit path)
and skips with an explanation, because a subset run legitimately has a
short record. Coverage is certified by `.\run_tests.ps1`.

### 4. Choosing an input is allowed; predicting an answer is not

`discovery.py` joins base tables to `BIOG_MAIN` — the same shape a
handler uses — and that is fine **because the answer is only ever used
as a request to send**. The moment a count from that join becomes an
expected value, it is a transcription of the handler and will agree with
it wherever the handler is wrong. See `oracle-discipline.md`.

### 5. Prefer a check that needs nothing running

Two of this build's defects are visible in the source alone: an
unclosed XML declaration (`test_every_kml_writer_closes_its_xml_
declaration`) and a query selecting a column its table does not have
(`test_no_query_asks_a_scratch_table_for_a_column_it_lacks`). Both also
have a test that drives the endpoint. Keep both: the source-level test
says *where the fix goes* and cannot be flaky, and the HTTP test proves
the user-visible symptom.

### 6. Exclusions are explicit, with a reason each

`NOT_EXPORTS` and `ENDPOINTS_NOT_DRIVEN` are dictionaries mapping the
excluded thing to why. Never a pattern: a pattern is how a genuine
export gets excluded by accident, and neither dictionary is allowed to
name something the build no longer has (both are asserted).

---

## The mistake to avoid

The tempting shortcut is to add one test for the thing in front of you.
It passes review, it works, and it leaves the next build's version of
the same thing untested. If you find yourself deciding *which* buttons
to press, *which* codes to use, or *which* endpoints matter — stop.
That decision belongs in an inventory the next run inherits. Your
judgement is the part that does not survive to the next build.

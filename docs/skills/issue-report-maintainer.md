# Skill: issue-report-maintainer

**Status:** repo-local (updated 2026-09-09). Read before adding,
changing or retiring anything in the defect registry or the issue
reports, and before waiving anything.

**What changed on 2026-09-08, and it changes this whole skill.** The
registry is no longer persistent state. It holds one round's findings
for as long as it takes that round to write its report, and the next
round starts empty. There are no `xfail` markers any more: a finding is
a **failure** until it is fixed or until it is agreed away in the
`CBDB_WAIVERS` table, which is keyed by test function names because no
identifier of ours survives a stateless round. AGENTS.md § *How a
defect is recorded, and how one is tolerated* is the short version.

## When to use

- A test has found something new and you think it is a defect
- An existing defect looks fixed (a test XPASSed)
- A defect's numbers changed (a new build, a new data release)
- You are correcting the wording, the priority, or the Chinese
- You are about to hand the reports to the CBDB team

If your change touches no assertion about the application and no registry
entry, this skill does not apply.

## The single source of truth

`tests/cbdb_desktop/defects.py` owns **everything** about a defect: its
identifier, priority, both titles, both descriptions, both sets of
reproduction steps, the suggested fix in both languages, the source
references, and the names of the tests that demonstrate it.

Nothing else may state a defect's content. In particular:

| File | What it may say |
|---|---|
| `reports/CBDB_Desktop_Issues_*.{md,docx,pdf}` | **generated** — never hand-edit |
| a test | the signature it recognised, in the `KnownShippedDefect` message. Never a registry lookup: `test_waivers.py` fails on any test module that imports more of the registry than that one exception |
| `README.md`, `AGENTS.md` | nothing per-defect. The registry is emptied between rounds, and a table of last round's findings in a context file is how the next round gets anchored to them |

The reports are rewritten from the registry plus one real run, so a
hand-edit is lost on the next run and, worse, is invisible until then.
`test_reports.py` is the mechanical half of this: rendered twice from
one run the report is byte-identical, it names no issue the registry
does not hold, it drops none, and it prints every waiver.

## Before you file: verify

A wrong entry in this report costs the CBDB team real time, and it costs
this suite its credibility. The bar:

1. **Reproduce through the running binary.** Not in SQL alone. The
   shipped `cbdb.exe` embeds its own SQLite; a system `sqlite3` check
   disagreed with the app about `LIKE` on an FTS table and would have
   hidden CBDB-D-001 entirely.
2. **Try to refute it.** Intended? Documented in `CBDBSetUpCode`? A
   quirk of your test? Two candidates here turned out to be correct
   behaviour — the address picker's repeated rows, and IndexAddr's
   duplicate check stopping at a disabled slot (three separate call
   sites agree on where a ranking ends).
3. **Find the decisive experiment.** Something that would change the
   outcome if your explanation is right. For CBDB-D-001 that was running
   the FTS rebuild on a copy and re-querying through the same binary.
4. **Get numbers.** "Search is broken" is a complaint. "`Wang` returns 0
   of 50,493, `wa` returns 56,504 correctly, the cutoff is exactly three
   characters" is a bug report.
5. **Reproduce it yourself — even when the maintainer reported it.**
   A report from him is a symptom observed once, in one browser, and it
   is evidence; it is not yet a mechanism, and the entry you write is
   about the mechanism. Two of this build's defects changed materially
   when reproduced:

   - CBDB-D-012 was filed as "the browser blocks the second download".
     Driving the real page in headless Chromium showed both files
     arriving on both presses -- the blocking half is a browser
     *permission* and does not reproduce under automation. The entry now
     says which half was established how, which is a better bug report
     than the confident version.
   - CBDB-D-014 looked like an ignored switch. The source showed a
     deliberate fallback, so the defect moved from "the switch does
     nothing" to "the page lets you send a request the backend has to
     guess at" -- a different fix, in a different file.

   Say in `evidence` which observations are yours, which are the
   maintainer's, and which are readings of the source. A reader deciding
   whether to spend an afternoon on it needs to know.

6. **Decide the origin, by experiment.** Every entry carries one of
   `software`, `data` or `release` (`ORIGINS` in `defects.py`), and it
   decides who the finding is *sent to*. The maintainer of this repo
   fixes data problems himself, in the CBDB source, and does not want
   them going to the application developers.

   The experiment is always: **would this survive a rebuild of the
   database from the current CBDB source, using this same code?** Yes →
   `software`. A clean rebuild makes it disappear → `data` or
   `release`. Run it; do not reason about it. Two of the six defects in
   the 2026-09-01 build were settled this way and both went the way the
   symptom did *not* suggest.

   The trap is a data problem that looks like a code problem because the
   application handles it badly, and its mirror image. CBDB-D-009 dies
   scanning `ADDR_CODES.c_admin_type` into an integer; that column has
   held text in every build and the schema declares `varchar(255)`, so
   no refresh will ever make the scan succeed. Origin `software`, one
   `Scan` to fix. CBDB-D-003 looked like a bug in the name derivation
   and was a snapshot taken after a `BIOG_MAIN` row was deleted; the
   derivation cannot invent an orphan, because every row it writes is
   read out of `BIOG_MAIN`. Origin `data`.

## Adding a defect

### 1. Write the registry entry

Every field is required in both languages. Fill them like this:

| Field | What belongs in it |
|---|---|
| `key` | `CBDB-D-00N`, next free number. Never reuse one. |
| `priority` | see the ladder below |
| `severity` | `high` / `medium` / `low`, consistent with the priority |
| `title` / `title_zh` | one line a maintainer can scan |
| `area` / `area_zh` | the form or file, with its route |
| `summary` / `summary_zh` | what is wrong and why, mechanism included |
| `evidence` / `evidence_zh` | the measurements. Numbers, not adjectives |
| `impact` / `impact_zh` | what it means for a historian using CBDB |
| `fix` / `fix_zh` | concrete, and say if the fix already exists in their code |
| `steps` / `steps_zh` | what a person does, in order, to see it |
| `source` | `file:line` or `file:symbolName` into the shipped build. Prefer the symbol: it survives the line drift every new build brings. `test_defect_registry.py` checks both forms resolve |
| `tests` | the test function names, bare (matched file-qualified) |

The priority ladder (`PRIORITIES` in the same file):

- **P0** silent wrong answer — wrong or empty results, no error shown
- **P1** destructive write — stored data rewritten, previous state gone
- **P2** visible runtime error — the action fails with a server error
- **P3** packaging — the released files contain something they should not
- **P4** data integrity — a reference in the shipped data does not resolve

Severity argument worth keeping straight: CBDB-D-005 (shipped scratch
state) is *medium* rather than high because every form truncates its
scratch tables before writing, so the state dies at the user's first
query. That reasoning is written into its `impact` — do the same for any
call that could look inconsistent.

### 2. Write the Chinese as Chinese

Traditional (ZH-Hant), addressed to the CBDB maintainers. Write it, do
not translate it word for word — an English sentence rendered literally
reads like a machine and undermines the report. Terms already in use:

| English | 中文 |
|---|---|
| person / people | 人物 |
| index address | 索引地址 |
| scratch table | 暫存表 |
| the shipped build / release | 釋出版本、發行檔 |
| working list | 工作清單 |
| Query Builder | 查詢建構器 |
| export | 匯出 |

Keep identifiers, SQL, routes and file paths in English inside backticks.

### 3. Leave the test failing, and make it say what it found

```python
def test_the_thing_that_should_work(app):
    result = app.json(...)
    if <the exact known-bad signature>:
        raise KnownShippedDefect(f"...with the numbers...")
    assert <what a correct build would do>
```

There is **no marker to add**. `KnownShippedDefect` is an
`AssertionError`, so this fails, and it should: the run reports what the
build does. Two properties are still load-bearing:

- **The signature check** — raise only on the exact known state, and
  include the measured numbers in the message. Anything else about the
  same test still arrives as a plain assertion failure, which is how a
  *new* problem stays visible instead of wearing this one's name.
- **The plain assertion underneath** — what a correct build does. The
  day the defect is fixed, that is the test that keeps it fixed.

Do not wire the test to the registry. Filing the entry is a separate
act, and the test must read the same whether or not anything is filed.

### 4. Regenerate and read

```powershell
.\run_tests.ps1
```

Then actually read both reports. Check: the entry appears under the right
priority, the status is CONFIRMED, the Chinese reads naturally, and the
`.docx`/`.pdf` are produced (Word is used for the PDF because these are
bilingual documents).

## Retiring a defect

A test that used to fail now passes → the defect is *apparently* fixed.
(If it was waived in `tolerate` mode the run tells you loudly: a strict
xfail that passes is an XPASS, and that fails the run.) Do not delete
anything yet.

1. Confirm by hand, through the running binary, that the behaviour is
   genuinely correct now — not merely different.
2. Remove the `KnownShippedDefect` branch, leaving the plain assertion.
   The test is now an ordinary regression test and should stay.
3. Remove its waiver from the `CBDB_WAIVERS` table, if it had one, and
   the registry entry if the current round had filed it.
4. Regenerate. The count in `README.md` and `AGENTS.md` changes too.
5. Say in the commit message which build fixed it.

Never retire a defect because it became inconvenient, and never widen a
marker to make an unrelated failure go away.

**Delete it; do not mark it fixed.** The registry describes the build in
front of you, not the project's history. An entry that says "resolved in
2026-09-07" pollutes the report for every reader who has to work out
which half applies to them, and the git history of `defects.py` is a
better record than a list nobody re-reads. `AGENTS.md` keeps a short
table of what was retired and how, which is where a reader of an older
report is pointed.

The inverse has teeth too: **never drop a finding because a previous
build called it fixed, or because a previous report did not mention it.**
Judge each build on its own run and its own source. CBDB-D-008 — three
Networks export buttons that answer HTTP 500 on every input — predates
every build this suite has seen, survived a remediation session aimed at
the very tables it touches, and would have been reasoned away by anyone
diffing against the last report.

**A fixed defect leaves its test behind.** The assertion stays as an
ordinary regression test, and where the origin was `release` or `data`
that test is the *only* thing that would notice a recurrence — a process
fix is exactly the kind that quietly stops being followed.

## Waiving something instead of fixing it

Sometimes the answer is "yes, that is wrong, and we are not doing
anything about it this year". That is a legitimate outcome, and it is
the only thing allowed to persist between rounds — but it is an
*agreement*, so it is recorded as one, outside the suite, in the file
`CBDB_WAIVERS` points at:

```toml
[test_an_export_produces_a_well_formed_file]
params    = ["entry:kml", "places:kml"]   # the ids pytest prints
reason    = "Agreed 2026-09-10: the KML preamble is cosmetic for us."
reason_zh = "2026-09-10 協商：KML 檔頭對我們的使用者只是外觀問題。"
agreed_by = "maintainer"
agreed_on = 2026-09-10
expires   = 2026-12-01                    # optional; past it the run goes red
```

Rules worth knowing before writing one:

- **Address it by the program's name, never by ours.** The key is the
  test function (quoted if it carries a module:
  `["test_exports.py::test_x"]`), plus the parametrisation ids in
  `params`. A `CBDB-D-0NN` is assigned while one report is written and
  points at nothing by the next round; a function name is part of the
  program, and if it is renamed the waiver fails loudly instead of
  silently covering nothing.
- **`tolerate` (the default) keeps measuring.** The test still runs and
  its failure is tolerated, so the day the problem disappears the run
  says so. `mode = "skip"` stops the test entirely, costs endpoint
  coverage, and needs a `note` justifying it.
- **Narrow it.** `raises = "KnownShippedDefect"` tolerates only the
  recognised signature, so an unrelated crash of the same test still
  fails.
- **It will be printed.** Every waiver appears in both reports with its
  reason, who agreed and when. If you would not want the CBDB team to
  read it, do not write it.
- **File it as well, when it is a real finding.** A waiver says "not
  now"; a report entry says "here is what is wrong". A round that waives
  something worth knowing about should still describe it.

## When the numbers change

A new data release moves counts. `evidence` and `steps` contain figures
like "0 of 50,493" and "383,322 → 379,051". Re-measure them on the new
build and update both languages in the same commit. Stale numbers in a
bug report get the whole report distrusted.

## Checklist before handing the reports over

- [ ] `.\run_tests.ps1` has been read failure by failure: each one is
      fixed, filed, or waived by agreement — none left unexplained
- [ ] every recorded issue is CONFIRMED (or its status is explained)
- [ ] no `NOT EXERCISED` — that means a test was deselected or renamed
- [ ] both `.md` files committed; `.docx`/`.pdf` regenerated and *not*
      committed (their timestamps churn)
- [ ] the Chinese has been read start to finish by someone who reads
      Chinese
- [ ] `test_defect_registry.py` passes — it checks mechanically that
      every `source` reference resolves in the staged build, that both
      languages are filled in, and that the named tests exist
- [ ] `test_reports.py` and `test_waivers.py` pass — the report is
      reproducible and invents nothing, and every waiver still names a
      check this run has
- [ ] no issue says "we think" — if it is not verified, it is not filed

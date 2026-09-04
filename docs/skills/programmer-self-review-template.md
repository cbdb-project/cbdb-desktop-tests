# Programmer self-review template

Repo-local workflow checklist (NOT a skill). Run this before reporting
any change back — to a reviewer, to `codex`, or to the user.

Keep it short. If a section is genuinely N/A for the shape of the change
(a docs-only change has no oracle to evaluate under C), write
"N/A — <one-line reason>" rather than deleting the section.

## A. Scope

- [ ] `git diff --name-only` contains only files this task should touch.
- [ ] Nothing under `work/` was committed (it is 1.4 GB and gitignored).
- [ ] `.env` is not staged. `.env.example` is, if a setting was added.
- [ ] Generated artefacts follow the rule: `reports/*.md` committed,
      `reports/*.{docx,pdf,json}` not.

One line on anything touched that the task did not obviously require.

## B. It runs

- [ ] `python -m pytest tests -q` — paste the last line.
- [ ] `.\run_tests.ps1` if reports or the runner changed — paste the
      summary line and the report paths.
- [ ] No `cbdb.exe` left running:
      `Get-CimInstance Win32_Process -Filter "Name='cbdb.exe'"`.
- [ ] No `-wal` beside the staged master:
      `ls work/stage/*/Data/CBDB.db-wal` finds nothing.
- [ ] Runtime did not grow surprisingly. If it did, say by how much and
      why (`--durations=5`).

## C. The oracles hold up

For each assertion added or changed — this is the section that matters:

- [ ] **Could it fail?** Describe the broken build that turns it red.
      If you cannot, work out what it *does* pin. Nothing at all → remove
      it. Something narrower than its name suggests → keep it and say so
      in the docstring. See "When the two questions disagree" in
      `oracle-discipline.md`; four assertions here are in that category
      deliberately, so do not delete them citing this checklist.
- [ ] **Would it survive a rewrite** of the handler to the same
      specification? If it would have to be rewritten alongside, it is a
      transcription — see `oracle-discipline.md`.
- [ ] No handler SQL was reproduced. Base facts (row counts, membership)
      and app-vs-app agreement only.
- [ ] Any `if rows:` / `if x:` guard around an assertion is justified, or
      replaced by `assert rows`.
- [ ] Pinned counts are exact, not floors.

State plainly what each new test *actually* proves. "The export
comparison for office/status/texts/places checks JSON field-name
agreement, not that two renderings match" is the right level of honesty.

## D. State and cost

- [ ] Any new endpoint call is bounded — a filter that keeps the result
      small, a traversal depth of 1, or a resource guard.
- [ ] No existence check invokes a handler (use `PATCH` → 405/404).
- [ ] If the change touches shared `ZZ_*` state, say which tables and why
      the test still holds under `-k` selection and in file order.
- [ ] Anything that rewrites `BIOG_MAIN` runs on its own app and its own
      database copy.

## E. If a defect was added, changed or retired

- [ ] `issue-report-maintainer.md` was followed end to end.
- [ ] The defect was verified through the running binary, and the
      innocent explanation was actively looked for and ruled out.
- [ ] Both languages written; the Chinese reads as Chinese.
- [ ] `xfail(strict=True, raises=KnownShippedDefect)`, reason quoted from
      the registry, and the raise happens only on the exact signature.
- [ ] Reports regenerated and read.

## F. Documentation

- [ ] Docstrings say what the code *does*, including where it is weaker
      than it looks.
- [ ] A comment explains any non-obvious choice, with the reason, not
      just the rule.
- [ ] `AGENTS.md` updated if a new landmine was found.
- [ ] `README.md` counts still match reality (tests, defects, runtime).

## G. Report back

Include:

1. What changed, in two or three sentences.
2. The test-run line, verbatim.
3. Anything you found and did **not** fix, and why.
4. Anything you are unsure about — especially an assertion you suspect
   might be true by construction. Reviewers here have caught several;
   flagging one costs nothing and hiding one costs the suite its value.

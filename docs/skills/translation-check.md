# Skill: the translation check — English, 繁體, 简体 against the glossary

**Read this before** touching `tests/cbdb_desktop/i18n.py`,
`tests/test_translations.py` or `docs/labels/FormLabels.xlsx`, and
before filing or waiving a translation finding.

The maintainer's request, which shapes everything here:

> 基于这份翻译表，建立对英文、简中、繁中译名的检查程序……确保多次重复检查得到的结果是类似的，而不是每次都不同。

So the check is **rules in a program**, against **a committed
reference**, with **every external table pinned**.  An agent reading the
labels and deciding which look wrong would produce a different list each
round, and that is the thing being replaced.

---

## The pieces

| piece | what it is |
|---|---|
| `docs/labels/FormLabels.xlsx` | the reference: Access `FormLabels`, 643 rows over 29 forms |
| `docs/labels/regional_terms.tsv` | Taiwan/mainland pairs OpenCC does not know, treated as one word |
| `docs/labels/accepted_characters.tsv` | characters never flagged in a script by ruling (`于` in Traditional) |
| `i18n.FORM_PAGES` | Access form code → desktop page.  Every code in the sheet must be declared |
| `i18n.translation_tables` | reads each page's `translations` / `T` / `LABELS` object out of the shipped template, as data |
| `i18n.check_label` | the five per-label rules |
| `i18n.inconsistencies` | the cross-page rule |
| `i18n.rendered_findings` | judges what a real Chromium shows after the page's 繁 / 简 buttons are pressed |
| `i18n_report` / `check_translations.py` | writes the full list: `reports/CBDB_Desktop_Translations.md` (committed) and `.xlsx` |

## The rules, and the reason for each

| kind | finding | why it is decided that way |
|---|---|---|
| `missing` | a key absent from one language's table | that reader gets English or `undefined` |
| `script` | a simplified character in 繁 text, or a traditional one in 简 | flagged only when **every** OpenCC conversion into the right script (`s2t`, `s2tw`, `s2hk` / `t2s`, `tw2s`, `hk2s`) changes it, **in context and alone**.  One converter alone is unfair: `s2t` would flag Taiwan's `群`; phrase tables prefer `孃家` over `娘家` |
| `chinese_disagree` | 繁 and 简 use different words | compared through `chinese_forms`: script conversion, OpenCC's Taiwan↔mainland phrase tables (`tw2sp`, `s2twp`), and the pairs in `docs/labels/regional_terms.tsv`.  **A Taiwan/mainland difference is never a finding** (the maintainer's ruling, 2026-10-22): `匯出`/`导出`, `資料庫`/`数据库`, `儲存`/`保存`, `連結`/`连接` are one word localised |
| `glossary_chinese` | the label's English is a glossary term **for this page's forms** and its Chinese is none of the glossary's renderings | looked up only in the page's own forms — never the whole sheet.  `Occasion` is an association's occasion on the Browser and a genre of writing on Networks |
| `glossary_english` | the English is not a glossary term but the Chinese is, and the English differs from the glossary's | only then, so one wrong pair is reported once, not once from each side |
| `inconsistent` | one English label translated more than one way **across pages** | needs no glossary.  Within one page, a short English word over several Chinese labels is fields named in context (`Range` → 生年時限 / 卒年時限) |
| `rendered_script` | on screen, after choosing 繁 or 简, text in the other script | only strings that occur in the template are judged: names fetched from CBDB are data |

English is normalised by case, punctuation and a fixed crude
singulariser (`Index Years` = `Index Year`), so number is not wording.

## Reading a finding

Every failing test raises `KnownShippedDefect` with the full list.  The
report has the same rows plus **the glossary rows each judgement rests
on** — read those before agreeing with a finding.  Three things to try
first, because they are the innocent explanations:

1. **Is it a regional word?**  A Taiwan vs. mainland difference is not a
   problem -- the maintainer's ruling of 2026-10-22, prompted by
   `二階連結` / `二阶连接`.  If OpenCC's tables do not know the pair, add
   it to `docs/labels/regional_terms.tsv` (one `Taiwan<TAB>mainland`
   line) and rerun; never special-case a string in `i18n.py`.  The table
   is part of the checker's fingerprint, so on-screen results measured
   before the edit are not merged into the next report.
2. **Is the glossary row really the same concept?**  Scoping to the
   page's forms makes this rare, but the Browser owns sixteen subforms.
   The `glossary rows` column shows which row decided it.
3. **Is the glossary itself wrong?**  The sheet has problems of its
   own (143 as supplied; listed at the end of the report).  They cannot cause a page
   finding by script, because comparisons are script-blind, but a wrong
   *word* in the sheet will.  That is the maintainer's fix, in the sheet.

## Filing and tolerating

Origin is `software` — the strings are in the page templates.  File by
kind and page, the way the tests are parametrised, naming the tests
(`test_chinese_labels_use_the_glossary_term[office]`, …).  Quote counts
from the report and give the most serious examples verbatim (a wrong
*meaning*, like `生卒年` for *Index Years*, before a wording preference
like `執行查詢` for *Run Query*).

A finding the maintainer accepts ("we prefer 執行查詢") is a waiver keyed
by the test and its page id — or, if it is the glossary that should
change, an edit to the sheet.  Never a special case in `i18n.py`: a rule
with exceptions for particular strings is exactly the per-round judgement
this check exists to replace.

## Changing the instrument

* **OpenCC is pinned exactly** in `requirements.txt`.  Upgrading it can
  move findings.  Do it on purpose, rerun, and read
  `test_the_script_rule_on_characters_whose_answer_is_known` first.
* **A new table shape** (a page that stores its labels some new way)
  fails `test_the_pages_with_a_language_switch_are_the_pages_checked`.
  Teach `_labels_from` the shape, and add it to `_TABLE_PAGE` in the
  tests: an extractor is tested against an answer written down.
* **Determinism is tested, not asserted**:
  `test_the_check_gives_the_same_answer_every_time` runs the whole check
  in two processes under different `PYTHONHASHSEED`s and compares the
  serialised result and the rendered Markdown.  Anything that iterates a
  set unsorted fails it.  (The `.xlsx` is made byte-stable by fixed
  timestamps; that is not compared by the test.)
* **Coverage is measured**: the report's per-page table says how many
  labels the glossary could judge.  A label whose English and Chinese
  are both absent from its forms' rows is checked only by the rules that
  need no glossary — that is the honest limit, and the table is where it
  shows.

# The CBDB label glossary

`FormLabels.xlsx` is the reference the translation check judges the
pages against: the Access front end's `FormLabels` table, supplied by
the maintainer on 2026-10-22.  One sheet, 643 rows, five columns:

| column | holds |
|---|---|
| `c_form` | the Access form the label belongs to (`LAO` = Look At Office, `SF_ADDR` = the biography form's address subform, …) |
| `c_label_id` | the label's number on that form |
| `c_english` | English |
| `c_jianti` | Simplified Chinese (简体) |
| `c_fanti` | Traditional Chinese (繁體) |

## How it is used

`tests/cbdb_desktop/i18n.py` reads it (the header row is checked, not
assumed) and `FORM_PAGES` there says which desktop page each Access form
became.  A page's labels are compared only with its own forms' rows,
never with the whole sheet: one English word can mean different things
on different forms.  The rules, and why each is the way it is, are in
that module's docstring and in `docs/skills/translation-check.md`.

Run `python check_translations.py` for the full list of findings
(`reports/CBDB_Desktop_Translations.md` and `.xlsx`).  The same rules run as
tests in `tests/test_translations.py`.

## Regional vocabulary: `regional_terms.tsv`

A Taiwan/mainland difference between the Traditional and Simplified
pages is not a translation problem (the maintainer's ruling of
2026-10-22).  OpenCC's regional phrase tables already treat the common
pairs as one word (匯出/导出, 資料庫/数据库, 儲存/保存); any pair they do
not know goes in `regional_terms.tsv`, one `Taiwan<TAB>mainland` line
each (`連結	连接` is the first).  Every comparison of wording uses it --
繁 against 简, labels against this glossary, one form against another.

## Accepted characters: `accepted_characters.tsv`

Characters that OpenCC would convert but that are acceptable in a
script by the maintainer's ruling, one `script<TAB>character` line each.
`于` in Traditional is the first (2026-10-22): every OpenCC conversion
writes `於`, and `于` is nonetheless fine.  A character listed here is
never flagged -- on the pages, on screen, or in the glossary self-check.

## Replacing or editing it

Overwrite the file in place and rerun.  `test_the_glossary_loads_as_
the_table_it_is` pins the row count, so a deliberate edit fails it once
and you change `GLOSSARY_ROWS` in the same commit.  A new `c_form` code
fails `test_every_glossary_form_is_assigned_a_page` until it is added to
`i18n.FORM_PAGES`.  The report prints the glossary's SHA-256, so two
reports made from different versions say so.

## Its own problems

The sheet is the reference, not a defect-free one.  As supplied, its
Simplified column holds traditional characters in 122 cells (`終于`,
`無時限`, `刪除`, `頁碼/條目`); its Traditional column has simplified
characters in 8 (`類别`, `帮助`, `清除查询結果`); 8 rows differ in
*wording* between the two Chinese columns (`綜合多種` / `總合多種`,
`選擇所有官名` / `選擇所有官明`); 4 English cells hold Chinese; and one
cell (`LAE#18`) holds two terms joined by an Excel line-break escape --
143 problems in all.  (`保存于` in the Traditional column is not one:
`于` is accepted in Traditional by the maintainer's ruling, see below.)  None of these can make a page
look wrong, because pages are compared with it after both sides are
reduced to one script.  They are listed in full at the end of the
translation report (*Problems in the glossary itself*) so the sheet can
be corrected.  A `?` in a cell is a real question mark (`女?` is the
yes/no field "Female?"), not a lost character.

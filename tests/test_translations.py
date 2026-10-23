"""Are the pages' English, 繁體 and 简体 labels right?

The maintainer found terms mistranslated in all three languages, and
asked for the check to be a program rather than a reading: the same
build checked twice must give the same answer, on any machine.  So the
judgement lives in ``cbdb_desktop/i18n.py`` as fixed rules, the
reference is a committed spreadsheet (``docs/labels/FormLabels.xlsx``,
the CBDB label glossary from the Access front end), and this module
asks those rules about every label the build ships.

Two layers, because there are two places a label can live
(AGENTS.md, operating principle 9: two checks in two places).

* **The translation tables** -- each form's ``translations``/``T``/
  ``LABELS`` object, read as data from the shipped template.  Needs no
  browser and no running application, so it runs in every checkout,
  and it answers with the page, the key and the line.
* **What the page shows** -- a real Chromium presses the page's own
  繁 and 简 buttons and reads what is on screen.  That is the only way to
  see a label the language switch never touches: a bilingual label
  written into the HTML (``Office 官职``) shows its simplified Chinese
  to a reader who chose Traditional, and no translation table holds it.
  Skipped, not failed, when Chromium is absent.

**How a finding is reported.**  Every test here raises
``KnownShippedDefect`` when it finds something, with the whole list in
the message: the checks are narrow by construction, so anything they
find *is* the finding they exist for, and an unrelated crash still
arrives as an ordinary error.  The full list across all pages, with the
glossary rows each judgement rests on, is written by ``python
check_translations.py`` to ``reports/CBDB_Desktop_Translations.md`` and
``.xlsx``.

**What a pass does not mean.**  A label whose English is not a glossary
term, and whose Chinese is not one either, is checked only for script,
completeness and 繁/简 agreement -- the glossary cannot judge wording it
does not contain.  How many labels per page the glossary could judge is
in the report's coverage table, and ``test_every_translated_page_is_
judged_against_the_glossary`` keeps that from being zero.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from cbdb_desktop import browser, controls, i18n, i18n_report
from cbdb_desktop.app import CbdbApp
from cbdb_desktop.config import REPO_ROOT
from cbdb_desktop.defects import KnownShippedDefect
from cbdb_desktop.staging import AppLayout

#: The glossary as supplied on 2026-10-22: 643 labels.  Exact, not a
#: floor (operating principle 5): a sheet that loaded half its rows would
#: still pass ``>= 1``, and quietly judge half as much.  When the
#: maintainer edits the glossary this fails, and the new count is the
#: one-line change that says the reference moved.
GLOSSARY_ROWS = 643

#: How many pages offer a choice of language: 11 on the 20261021 build.
#: The pages themselves are *derived* from the build at collection time
#: (``pytest_generate_tests`` below) -- no page name is written here --
#: and this count is the floor-free check on that derivation: a build
#: that dropped a page's switch, or a reader that stopped recognising
#: one, would otherwise shrink every per-page test below to fewer pages
#: and stay green.
TRANSLATED_PAGE_COUNT = 11


def pytest_generate_tests(metafunc):
    """Parametrise the per-page tests over the pages the build translates.

    At collection, through the same cached staging the session uses (a
    cache hit is ~0.1 s), as ``test_query_matrix.py`` does for its inputs:
    pytest decides which tests exist before any fixture runs.
    """
    if "page" in metafunc.fixturenames:
        metafunc.parametrize("page", _translated_pages(metafunc.config))


_PAGES_CACHE: dict[int, list[str]] = {}


def _translated_pages(config) -> list[str]:
    key = id(config)
    if key not in _PAGES_CACHE:
        from cbdb_desktop.config import load_config
        from cbdb_desktop.staging import stage_once
        layout = stage_once(load_config(), force=config.getoption("--restage"))
        _PAGES_CACHE[key] = sorted(
            page for page, path in controls.pages(layout).items()
            if i18n.has_language_switch(
                path.read_text(encoding="utf-8", errors="replace")))
    return _PAGES_CACHE[key]


@pytest.fixture(scope="module")
def glossary() -> i18n.Glossary:
    return i18n.Glossary.build(i18n.load_glossary())


@pytest.fixture(scope="module")
def checked(layout: AppLayout, glossary):
    """``({page: labels}, findings)`` for the staged build."""
    return i18n.check_pages(controls.pages(layout), glossary)


def _lines(findings: list[i18n.Finding]) -> str:
    out = []
    for f in findings:
        where = f"{f.ref} (line {f.line})" if f.line else f.ref
        out.append(f"  {where}: EN '{f.english}' / 繁 '{f.traditional}' / "
                   f"简 '{f.simplified}' -- {f.detail}")
    return "\n".join(out)


def _raise_if_any(findings: list[i18n.Finding], kind: str, page: str,
                  why: str) -> None:
    found = [f for f in findings if f.kind == kind and f.page == page]
    if found:
        raise KnownShippedDefect(
            f"{page}: {len(found)} label(s) with {i18n.KIND_TITLES[kind]}.  "
            f"{why}\n{_lines(found)}")


# ---------------------------------------------------------------------------
# the reference, and what it covers
# ---------------------------------------------------------------------------

def test_the_glossary_loads_as_the_table_it_is():
    rows = i18n.load_glossary()
    assert len(rows) == GLOSSARY_ROWS, (
        f"{i18n.GLOSSARY_PATH.name} has {len(rows)} labels, not "
        f"{GLOSSARY_ROWS}.  If the glossary was edited on purpose, update "
        "GLOSSARY_ROWS in the same commit; if not, it did not load whole")
    blank = [r.ref for r in rows if not (r.form and r.english.strip())]
    assert not blank, f"glossary rows with no form or no English: {blank}"


def test_every_glossary_form_is_assigned_a_page():
    """A form the mapping does not know is half the glossary going unused.

    Labels are looked up only in the page's own forms (see
    ``i18n.Glossary``), so a form missing from ``FORM_PAGES`` would have
    its labels silently judge nothing.  A mapping entry for a form the
    glossary no longer has is stale in the other direction.
    """
    forms = {row.form for row in i18n.load_glossary()}
    assert forms == set(i18n.FORM_PAGES), (
        f"glossary forms with no page: {sorted(forms - set(i18n.FORM_PAGES))}; "
        f"pages mapped from forms the glossary lacks: "
        f"{sorted(set(i18n.FORM_PAGES) - forms)}.  Declare each in "
        "i18n.FORM_PAGES (None for a form with no desktop counterpart)")


def test_the_pages_with_a_language_switch_are_the_pages_checked(
        layout: AppLayout):
    """Every page that offers 繁/简 has a table this check can read.

    Derived from the build two ways -- which pages call a language
    switch (the per-page tests run over these), and which have a
    translation table the extractor parses -- and the two must agree.  A
    page that gains a switch with a table written some new way would
    otherwise be checked by nothing while every test here stayed green.
    The count is pinned so the derivation itself cannot quietly shrink.
    """
    switch, tables = set(), set()
    for page, path in controls.pages(layout).items():
        html = path.read_text(encoding="utf-8", errors="replace")
        if i18n.has_language_switch(html):
            switch.add(page)
        if i18n.translation_tables(page, html):
            tables.add(page)
    assert switch == tables, (
        f"pages with a language switch and no readable translation table: "
        f"{sorted(switch - tables)}; tables on pages with no switch: "
        f"{sorted(tables - switch)}")
    assert len(switch) == TRANSLATED_PAGE_COUNT, (
        f"the build has {len(switch)} pages with a language switch "
        f"({sorted(switch)}), not {TRANSLATED_PAGE_COUNT}.  If a page "
        "gained or lost its switch on purpose, update TRANSLATED_PAGE_COUNT")


def test_no_translation_table_is_too_unusual_to_read(layout: AppLayout):
    """A table the reader cannot parse is reported, not skipped.

    The reader understands plain string values.  A table that grew a
    template literal, a spread or a function value would otherwise drop
    out of every check here while its page's other tables kept the
    page-level gate green.
    """
    unreadable = []
    for page, path in sorted(controls.pages(layout).items()):
        unreadable += i18n.unreadable_tables(
            page, path.read_text(encoding="utf-8", errors="replace"))
    assert not unreadable, (
        "these look like translation tables and could not be read, so none "
        f"of their labels is checked: {unreadable}.  Teach i18n._labels_from "
        "the shape, and add it to _TABLE_PAGE in this module")


def test_every_page_the_glossary_mapping_names_exists(layout: AppLayout):
    """A misspelt page in FORM_PAGES scopes that form's rows to nothing."""
    pages = set(controls.pages(layout))
    named = {page for targets in i18n.FORM_PAGES.values() if targets
             for page in targets}
    assert named <= pages, (
        f"i18n.FORM_PAGES names pages the build does not have: "
        f"{sorted(named - pages)}")


def test_the_script_converter_is_the_pinned_one():
    """Determinism across machines rests on one dictionary version.

    ``requirements.txt`` pins OpenCC exactly, but a pin is a request, and
    ``opencc-python-reimplemented`` also imports as ``opencc``.  This is
    where a machine with another one finds out, before its findings
    quietly differ from everyone else's.
    """
    from importlib import metadata
    assert metadata.version("opencc") == "1.1.9", (
        f"OpenCC {metadata.version('opencc')} is installed; the translation "
        "check is pinned to 1.1.9 (requirements.txt).  Install it, or move "
        "the pin deliberately and read what changes")


def test_every_translated_page_is_judged_against_the_glossary(
        page, checked, glossary):
    """Scoping to a page's own forms must never mean "against nothing"."""
    labels, _ = checked
    assert labels.get(page), f"{page}: no translation labels were read"
    assert glossary.by_page.get(page), (
        f"{page}: no glossary form maps to this page, so none of its "
        "labels can be judged against the glossary -- add its Access form "
        "to i18n.FORM_PAGES")
    judged = [label for label in labels[page]
              if label.english and glossary.for_english(label.english, page)]
    assert judged, (
        f"{page}: not one of its {len(labels[page])} labels has an English "
        "the glossary defines for this page's forms; the glossary check "
        "would pass it by having nothing to compare")


# ---------------------------------------------------------------------------
# the translation tables
# ---------------------------------------------------------------------------


def test_every_label_is_written_in_all_three_languages(page, checked):
    _, findings = checked
    _raise_if_any(findings, "missing", page,
                  "A key absent from one language's table leaves that "
                  "language's reader the English, or 'undefined'.")


def test_every_chinese_label_is_written_in_its_own_script(page, checked):
    _, findings = checked
    _raise_if_any(findings, "script", page,
                  "A character is flagged only when no standard of the "
                  "script writes it that way (OpenCC's mainland, Taiwan "
                  "and Hong Kong conversions all change it, in context "
                  "and alone) -- so it is a slip, not a regional variant.")


def test_traditional_and_simplified_say_the_same_thing(page, checked):
    _, findings = checked
    _raise_if_any(findings, "chinese_disagree", page,
                  "Compared after reducing both to simplified and allowing "
                  "Taiwan/mainland vocabulary (匯出/导出, 資料庫/数据库), so "
                  "these are different words, not one word localised.")


def test_chinese_labels_use_the_glossary_term(page, checked):
    _, findings = checked
    _raise_if_any(findings, "glossary_chinese", page,
                  "Each label's English is a term the CBDB label glossary "
                  "(docs/labels/FormLabels.xlsx) defines for this page's "
                  "Access form, and the Chinese shown is none of the "
                  "glossary's renderings of it.")


def test_english_labels_use_the_glossary_term(page, checked):
    _, findings = checked
    _raise_if_any(findings, "glossary_english", page,
                  "Each label's Chinese is a glossary term for this page's "
                  "Access form, and its English is not the glossary's "
                  "English for that term (nor any glossary term at all).")


def test_one_english_label_is_translated_one_way_across_pages(checked):
    """The same button, the same word, on every form.

    Needs no glossary.  A reader who learns 保存到GIS on Places and meets
    儲存至GIS on Entry and 存至GIS on Kinship is learning three words for
    one action.  Within one page several Chinese labels under one short
    English word are fields named in context, and are not counted.
    """
    _, findings = checked
    found = [f for f in findings if f.kind == "inconsistent"]
    if found:
        raise KnownShippedDefect(
            f"{len(found)} English label(s) are translated more than one way "
            "across the forms:\n" + "\n".join(f"  {f.detail}" for f in found))


# ---------------------------------------------------------------------------
# what the pages show
# ---------------------------------------------------------------------------

_USABLE, _WHY_NOT = browser.available()


def _route_of(layout: AppLayout) -> dict[str, str]:
    from cbdb_desktop.routes import page_map
    return {page: "/" + target for page, target in page_map(layout).items()}


#: Findings from the rendered pages, gathered for the report, and which
#: pages were measured.  Written after every page with the staged tree's
#: key and the checker's fingerprint, so the report can tell a complete
#: measurement from a filtered or interrupted one, and never merges one
#: taken on another build or by other rules.
_RENDERED: list[i18n.Finding] = []
_MEASURED: set[str] = set()


@pytest.mark.app
@pytest.mark.browser
@pytest.mark.skipif(not _USABLE, reason=_WHY_NOT)
def test_each_chinese_language_shows_only_its_own_script(
        page, app: CbdbApp, layout: AppLayout, artifacts_dir):
    """Choose 繁 or 简 and read the screen: is all of it in that script?

    The page's own language buttons are found in the control inventory
    and clicked, as a reader would.  Only text the page's author wrote is
    judged -- a string must occur in the template -- because names and
    titles fetched from CBDB are data in whatever script the data holds.
    The usual culprit is a bilingual label written into the HTML that the
    language switch never rewrites, so it shows 简 to a 繁 reader or the
    reverse; the finding names the template line.
    """
    buttons, _ = controls.inventory(layout)[page]
    switch = i18n.language_buttons(buttons)
    assert set(switch) >= {"traditional", "simplified"}, (
        f"{page}: no 繁/简 buttons found in the control inventory "
        f"({switch}); the page cannot be read in each language")
    route = _route_of(layout).get(page)
    assert route, f"{page}: no route in the navigation map"
    html = controls.pages(layout)[page].read_text(encoding="utf-8",
                                                  errors="replace")

    # The page's own translations, per language: after a click, at least
    # one must be on screen, or the switch did not happen (a page whose
    # setLanguage throws stays in English, and English has nothing in the
    # wrong script -- that would pass for the wrong reason).
    own = {language: {" ".join(label.text(language).split())
                      for labels in i18n.translation_tables(page, html).values()
                      for label in labels
                      if label.used and label.text(language)
                      and i18n.has_cjk(label.text(language))}
           for language in ("traditional", "simplified")}

    found: list[i18n.Finding] = []
    with browser.open_page(app.base_url, route) as (tab, _log):
        for language in ("traditional", "simplified"):
            tab.click(f"#{switch[language]}")
            shown = tab.evaluate(i18n.RENDERED_TEXT_JS)
            on_screen = {" ".join(s.split()) for s in shown}
            assert on_screen & own[language], (
                f"{page}: after pressing its {language} button, none of the "
                f"page's own {language} labels is on screen -- the language "
                f"switch did not run (page errors: {_log.page_errors})")
            found += i18n.rendered_findings(page, language, shown, html)

    _RENDERED[:] = [f for f in _RENDERED if f.page != page] + found
    _MEASURED.add(page)
    i18n_report.write_rendered(artifacts_dir, layout.root.name,
                               sorted(_MEASURED), _RENDERED)
    if found:
        raise KnownShippedDefect(
            f"{page}: {len(found)} string(s) on screen in the wrong script "
            "for the language the reader chose -- labels the language "
            "switch does not rewrite:\n" + _lines(found))


# ---------------------------------------------------------------------------
# the instrument itself
# ---------------------------------------------------------------------------

_TABLE_PAGE = r"""
<span data-lbl-idx="1"></span><span data-lbl-idx="3"></span>
<script>
const notATable = { english: 'x', other: 1 };
/* const T = { english: { dead: 'Dead' }, traditional: { dead: '死' },
               simplified: { dead: '死' } }; */
// a comment with 'quotes' and a } brace
const translations = {
  english:     { runQuery: 'Run Query', note: "It's here", only: 'Only EN',
                 hint: 'Step 1: go', spare: 'Spare' },
  traditional: { runQuery: '執行查詢', note: '在這', hint: '步驟', spare: '備' },
  simplified:  { runQuery: '执行查询', note: '在这', hint: '步骤', spare: '备' }  /* trailing } */
};
const LABELS = {
  // 1: the person picker
  1: { E: 'Select Person', T: '選擇人名', S: '选择人名' },
  2: { E: 'Count', T: `數量`, S: '数量' },
  3: { E: 'Half', T: '半' }
};
function setLanguage(lang) {
  const t = translations[lang];
  el.textContent = t.runQuery; other.textContent = t['note'];
  hint.textContent = T2('hint'); only.textContent = t.only;
}
</script>
<script>
const translations = {
  english: { runQuery: 'Run' }, traditional: { runQuery: '執行' },
  simplified: { runQuery: '执行' }
};
</script>
"""


def test_the_extractor_reads_both_table_shapes():
    """An extractor is tested against an answer written down.

    AGENTS.md, coverage property 6.  Both shapes the build ships, plus
    the shapes that make a hand-rolled reader drift silently: a decoy
    object, a commented-out table, comments holding quotes and braces, a
    ``\\u`` escape, a template literal, a key missing from two languages,
    a key-major entry missing one, a comment above a key and a string
    holding ``1:`` (both must not move a key's line), two tables with one
    name, and labels the page never reads.
    """
    tables = i18n.translation_tables("demo", _TABLE_PAGE)
    assert sorted(tables) == ["LABELS", "translations", "translations#2"]
    by_key = {label.key: label for label in tables["translations"]}
    assert by_key["note"].traditional == "在這"
    assert by_key["note"].english == "It's here"
    assert (by_key["only"].traditional, by_key["only"].simplified) == (None, None)
    assert [(l.key, l.english, l.traditional, l.simplified)
            for l in tables["LABELS"]] == [
        ("1", "Select Person", "選擇人名", "选择人名"),
        ("2", "Count", "數量", "数量"),
        ("3", "Half", "半", None)]
    assert by_key["runQuery"].line == _TABLE_PAGE.count(
        "\n", 0, _TABLE_PAGE.index("runQuery")) + 1
    one = next(l for l in tables["LABELS"] if l.key == "1")
    assert one.line == _TABLE_PAGE.count(
        "\n", 0, _TABLE_PAGE.index("1: { E")) + 1
    used = {l.ref: l.used for labels in tables.values() for l in labels}
    assert used == {
        "demo:translations.runQuery": True, "demo:translations.note": True,
        "demo:translations.only": True, "demo:translations.hint": True,
        "demo:translations.spare": False,
        "demo:LABELS.1": True, "demo:LABELS.2": False, "demo:LABELS.3": True,
        "demo:translations#2.runQuery": True}
    assert i18n.unreadable_tables("demo", _TABLE_PAGE) == []


def test_a_translation_table_that_cannot_be_read_is_reported():
    page = ("<script>const translations = {\n  english: { n: `${x} rows` },"
            "\n  traditional: {}, simplified: {} };</script>")
    assert i18n.translation_tables("demo", page) == {}
    assert len(i18n.unreadable_tables("demo", page)) == 1


@pytest.mark.parametrize("text,script,expected", [
    # Every OpenCC conversion writes 於 here, but 于 is accepted in
    # Traditional by the maintainer's ruling (docs/labels/
    # accepted_characters.tsv); 后 is not, and is still caught.
    ("保存于GIS", "traditional", []),
    ("之后", "traditional", ["后"]),
    ("群組", "traditional", []),            # Taiwan writes 群 (s2t alone says 羣)
    ("台北", "traditional", []),            # Hong Kong writes 台
    ("娘家地址", "traditional", []),        # a phrase table's 孃家 is a preference
    ("指數年", "simplified", ["數"]),
    ("著述", "simplified", []),             # 著 is simplified as well
    ("乾隆", "simplified", []),             # phrase context keeps 乾
    ("選擇", "simplified", ["選", "擇"]),
    # The rule's known limit, pinned so it is visible: OpenCC's phrase
    # tables do not know this era name, and 咸 is flagged although 咸平
    # is correct Traditional.  No label hits this; data would.
    ("咸平", "traditional", ["咸"]),
])
def test_the_script_rule_on_characters_whose_answer_is_known(text, script,
                                                             expected):
    """The script rule, pinned on cases a reader can verify by eye.

    Also the alarm for a different OpenCC: its dictionaries are what the
    rule consults, so a version that judged these differently would
    change findings everywhere -- this is where that shows first.
    """
    assert i18n.wrong_script(text, script) == expected


@pytest.mark.parametrize("a,b,same", [
    ("匯出查詢結果", "导出查询结果", True),    # Taiwan / mainland vocabulary
    ("儲存至GIS", "保存至GIS", True),
    ("中國歷代人物傳記資料庫", "中国历代人物传记数据库", True),
    ("指數年", "索引年", False),               # different words
    # Taiwan / mainland vocabulary OpenCC does not know, accepted through
    # docs/labels/regional_terms.tsv (the maintainer's ruling, 2026-10-22).
    ("二階連結", "二阶连接", True),
    ("紀錄", "记录", True),
])
def test_two_chinese_labels_are_the_same_wording_when_they_should_be(a, b,
                                                                    same):
    assert i18n.same_wording(a, b) is same


_SAME_ANSWER = r"""
import json, sys
sys.path.insert(0, sys.argv[2])
from pathlib import Path
from cbdb_desktop import controls, i18n_report
from cbdb_desktop.staging import AppLayout
layout = AppLayout(Path(sys.argv[1]))
data = i18n_report.build(controls.pages(layout), "build")
sys.stdout.buffer.write(json.dumps(data, ensure_ascii=False,
                                   sort_keys=True).encode("utf-8"))
"""


def test_the_check_gives_the_same_answer_every_time(layout: AppLayout):
    """Two separate processes, two hash seeds, one answer.

    The maintainer's requirement in a form that can fail: set iteration
    order changes with ``PYTHONHASHSEED``, so a result that leaned on it
    anywhere would differ between these runs.  The report's bytes are
    compared, not a summary of them.
    """
    outputs = []
    for seed in ("1", "2"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        proc = subprocess.run(
            [sys.executable, "-c", _SAME_ANSWER, str(layout.root),
             str(REPO_ROOT / "tests")],
            capture_output=True, env=env, timeout=300, cwd=str(REPO_ROOT))
        assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
        outputs.append(proc.stdout)
    assert outputs[0] == outputs[1], (
        "the translation check gave different answers under two hash "
        "seeds; something in i18n iterates a set or dict without sorting")
    data = json.loads(outputs[0])
    assert data["coverage"], "the check read no pages"
    assert i18n_report.render_markdown(data) == i18n_report.render_markdown(
        json.loads(outputs[1]))

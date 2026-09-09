#!/usr/bin/env python
"""Turn one test run into the issue reports, in English and Chinese.

Two inputs, and neither of them is written by hand:

* ``tests/cbdb_desktop/defects.py`` -- the registry of what has been
  found, in both languages, which the tests themselves quote in their
  xfail reasons; and
* the JSON report of an actual run, which says whether each of those
  tests still demonstrates its defect.

So a report cannot claim a defect the tests no longer show, nor go stale
about one that has been fixed: a fixed defect turns its strict xfail into
an unexpected pass, which shows up here as APPARENTLY FIXED.  And because
both languages come from one registry, the translations cannot drift
apart either.

    python reports/generate_report.py                 # .md + .docx + .pdf
    python reports/generate_report.py --format md     # Markdown only
    python reports/generate_report.py --lang en

Writes reports/CBDB_Desktop_Issues_EN.*  and  _ZH-Hant.*
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

from cbdb_desktop.defects import (  # noqa: E402
    DEFECTS, ORIGINS, PRIORITIES, Defect)

DEFAULT_JSON = ROOT / "reports" / "pytest_report.json"
REPORTS = ROOT / "reports"

LANGS = ("en", "zh")
STEM = {"en": "CBDB_Desktop_Issues_EN", "zh": "CBDB_Desktop_Issues_ZH-Hant"}

_STATUS_ORDER = {"CONFIRMED": 0, "INCONCLUSIVE": 1,
                 "APPARENTLY FIXED": 2, "NOT EXERCISED": 3}

#: Everything the reports say in their own voice.  Kept together so the
#: two languages are edited side by side and cannot drift.
STRINGS: dict[str, dict] = {
    "title": {
        "en": "CBDB-Desktop — Issues Report",
        "zh": "CBDB-Desktop —— 問題彙報",
    },
    "subtitle": {
        "en": "A respectful summary of issues uncovered during automated "
              "regression testing.",
        "zh": "自動化迴歸測試過程中發現的問題彙總，謹呈維護團隊斧正。",
    },
    "build": {"en": "Build under test: {build}", "zh": "受測版本：{build}"},
    "generated": {
        "en": "Generated {when} from a run of {total} tests ({duration}s).",
        "zh": "本報告產生於 {when}，依據一次 {total} 項測試的執行結果"
              "（耗時 {duration} 秒）。",
    },
    "letter": {
        "en": "Dear maintainer,\n\nBelow is a summary of the issues we "
              "uncovered while building an automated regression-test suite "
              "for CBDB-Desktop. We hope this report is useful as you "
              "continue your wonderful stewardship of this dataset, and we "
              "sincerely thank you for the immense work that has gone into "
              "building it.\n\nEvery issue below was found by launching the "
              "shipped `Bin/cbdb.exe` and driving its own HTTP endpoints "
              "against the shipped database — nothing here re-implements the "
              "application's logic, so what is described is what the released "
              "program does. The issues are ordered by severity (P0 highest). "
              "Each entry includes a short description, the measurement that "
              "establishes it, step-by-step reproduction, and a suggested "
              "fix. None of these are urgent; they are documented so they can "
              "be addressed at your convenience.",
        "zh": "尊敬的維護者：\n\n以下是我們在為 CBDB-Desktop 編寫自動化迴歸"
              "測試套件的過程中，陸續整理出來的問題清單。我們希望這份報告能"
              "在您繼續主持這份寶貴資料集時有所助益；同時，對您多年來在這套"
              "資料與程式上的辛勤付出，我們由衷表示感謝與敬意。\n\n"
              "以下每一項問題，都是實際啟動釋出的 `Bin/cbdb.exe`、以它自己的 "
              "HTTP 介面搭配釋出的資料庫實測出來的——我們沒有用 Python 重寫"
              "任何應用邏輯，因此這裡描述的就是釋出程式的真實行為。問題按"
              "嚴重程度排序（P0 最高），每一條都包含：簡要說明、據以認定的"
              "實測數據、逐步復現方式，以及一份建議的修復方案。這些問題都"
              "不緊急，整理於此只是方便您在合適的時候逐一處理。",
    },
    "run_summary": {"en": "How this run went", "zh": "本次執行結果"},
    "outcome": {"en": "outcome", "zh": "結果"},
    "count": {"en": "count", "zh": "數量"},
    "outcomes": {
        "en": {"passed": "passed", "failed": "failed", "error": "error",
               "xfailed": "xfailed (a known defect, still present)",
               "xpassed": "xpassed (a known defect appears fixed)",
               "skipped": "skipped"},
        "zh": {"passed": "通過", "failed": "失敗", "error": "錯誤",
               "xfailed": "預期失敗（已知缺陷，仍然存在）",
               "xpassed": "非預期通過（已知缺陷似乎已修復）",
               "skipped": "略過"},
    },
    "coverage": {"en": "What the suite covers", "zh": "測試套件的涵蓋範圍"},
    "coverage_head": {"en": ("Area", "Tests", "What it checks"),
                      "zh": ("範圍", "測試數", "檢查內容")},
    "coverage_total": {"en": "every test in this run", "zh": "本次執行的全部測試"},
    "coverage_undescribed": {
        "en": "(no description yet -- add one to reports/generate_report.py)",
        "zh": "（尚無說明——請在 reports/generate_report.py 中補上）",
    },
    "waived": {"en": "Agreed to leave for now",
               "zh": "已協商暫時擱置的項目"},
    "waived_intro": {
        "en": "These outcomes are known and were agreed to be left as they "
              "are for the time being.  They are listed so that nothing is "
              "tolerated invisibly: each one names the check that reports "
              "it, so it can be picked up again at any time.",
        "zh": "以下項目均為已知情形，並已協商暫時維持現狀。列於此處是為了"
              "避免任何問題被無聲地忽略：每一項都指明了對應的檢查名稱，"
              "隨時可以重新處理。",
    },
    "waived_head": {
        "en": ("Check", "Applies to", "Effect", "Agreed", "Until", "Why"),
        "zh": ("對應檢查", "適用範圍", "處理方式", "協商紀錄", "有效期至",
               "原因"),
    },
    "waived_none": {"en": "None -- nothing was waived in this run.",
                    "zh": "無——本次執行沒有任何擱置項目。"},
    "waived_all": {"en": "all cases", "zh": "全部情況"},
    "waived_modes": {
        "en": {"tolerate": "still checked, failure tolerated",
               "skip": "not checked in this run"},
        "zh": {"tolerate": "仍然檢查，失敗予以容忍", "skip": "本次未檢查"},
    },
    "waived_forever": {"en": "no end date", "zh": "未設期限"},
    "toc": {"en": "Table of contents", "zh": "目錄"},
    "summary_table": {"en": "Summary", "zh": "問題總覽"},
    "summary_head": {
        "en": ("ID", "Priority", "Status in this run", "Issue"),
        "zh": ("編號", "等級", "本次執行狀態", "問題"),
    },
    "legend": {"en": "Severity legend", "zh": "嚴重等級說明"},
    "affected": {"en": "Affected area:", "zh": "涉及範圍："},
    "severity": {"en": "Severity:", "zh": "嚴重等級："},
    "origin": {"en": "Where it comes from:", "zh": "問題來源："},
    "status": {"en": "Status in this run:", "zh": "本次執行狀態："},
    "h_description": {"en": "Description", "zh": "問題描述"},
    "h_evidence": {"en": "Evidence", "zh": "實測依據"},
    "h_impact": {"en": "Impact", "zh": "影響"},
    "h_steps": {"en": "Steps to reproduce", "zh": "復現步驟"},
    "h_fix": {"en": "Suggested fix", "zh": "建議修復方式"},
    "h_where": {"en": "Where it lives in the build", "zh": "對應的程式位置"},
    "h_tests": {"en": "Demonstrated by", "zh": "對應的測試"},
    "status_note": {
        "en": {
            "APPARENTLY FIXED": "The tests that demonstrated this no longer "
                                "fail. Please confirm, and this entry can be "
                                "retired.",
            "INCONCLUSIVE": "The tests for this issue failed for some other "
                            "reason, so this run neither confirms nor clears "
                            "it.",
            "NOT EXERCISED": "No test in this run exercised this issue, so "
                             "the run says nothing about whether it is still "
                             "present.",
        },
        "zh": {
            "APPARENTLY FIXED": "用來證明這項問題的測試已不再失敗。"
                                "煩請確認後，本條即可撤下。",
            "INCONCLUSIVE": "這項問題對應的測試因其他原因失敗，"
                            "因此本次執行既無法確認、也無法排除它。",
            "NOT EXERCISED": "本次執行沒有跑到這項問題對應的測試，"
                             "因此無法判斷它是否仍然存在。",
        },
    },
    "reproduce": {"en": "Reproducing this report", "zh": "如何重現這份報告"},
    "reproduce_body": {
        "en": "The whole report is generated from one command. With the "
              "distribution zip named in `.env` as `CBDB_DESKTOP_ZIP`:\n\n"
              "@@run_tests@@\n\n"
              "That stages the archive, launches the shipped binary against a "
              "private copy of the shipped database, runs {total} tests, and "
              "rewrites these files. The suite never writes to the reference "
              "copy of `Data/CBDB.db` — every test runs against a per-session "
              "copy, so a run leaves the distribution exactly as it found "
              "it.\n\nThe test that demonstrates each issue is named under "
              "it. To run just one:\n\n@@one_test@@",
        "zh": "整份報告由一道指令產生。只要在 `.env` 中以 `CBDB_DESKTOP_ZIP` "
              "指定發行壓縮檔：\n\n@@run_tests@@\n\n"
              "這道指令會解開壓縮檔、以釋出資料庫的私有複本啟動釋出的執行檔、"
              "執行 {total} 項測試，並重新產生這幾份檔案。測試套件不會寫入"
              "作為對照基準的 `Data/CBDB.db`——每次執行都使用各自的複本，"
              "因此跑完之後，發行檔與執行前完全相同。\n\n每一項問題底下都"
              "列出了對應的測試名稱。若只想執行其中一項：\n\n@@one_test@@",
    },
    "no_issues": {
        "en": "No issues are recorded for this build.",
        "zh": "本版本未記錄任何問題。",
    },
}

RUN_COMMAND = ".\\run_tests.ps1"
ONE_TEST_COMMAND = ("python -m pytest tests -k "
                    "test_searching_people_by_name_finds_them -v")

#: A short, human description of what each test file covers.  Counts come
#: from the run itself.
COVERAGE: tuple[tuple[str, str, str], ...] = (
    ("test_staging.py",
     "The distribution itself",
     "That the tree under test really is the shipped archive, file by file"),
    ("test_app_driver.py",
     "The application process",
     "That the shipped binary starts, serves, and releases its database"),
    ("test_routes.py",
     "Every registered route",
     "All 141 routes read out of the shipped Go source, driven for real"),
    ("test_lookups.py",
     "The code and address lists",
     "The dropdowns each form offers before a query is run"),
    ("test_qbe.py",
     "The Query Builder",
     "Its whitelist, the SQL it shows the user, and its guards"),
    ("test_form_queries.py",
     "The six single-query forms",
     "Entry, office, status, texts, associations, places — queries and exports"),
    ("test_stateful_forms.py",
     "The forms that remember",
     "Kinship, networks, association pairs, group data — working lists"),
    ("test_index_addr.py",
     "Index-address rankings",
     "The only endpoints that rewrite CBDB data rather than scratch"),
    ("test_query_matrix.py",
     "Every filter, on inputs read from the data",
     "One query per populated combination the shipped database has, plus "
     "every switch turned both ways"),
    ("test_exports.py",
     "Every export button",
     "All 45 file-producing endpoints pressed, and the files they return "
     "read back"),
    ("test_ui_pages.py",
     "The pages in a real browser",
     "That every page loads without throwing, and that a control waiting "
     "on the user un-greys when they do it"),
    ("test_sessions.py",
     "Two tabs at once",
     "Whether one query can replace what another was about to export"),
    ("test_scratch_tables.py",
     "The working tables",
     "Which form owns which scratch table, read out of the shipped Go"),
    ("test_zz_controls.py",
     "This run's own coverage",
     "That every endpoint the shipped pages can reach was actually "
     "requested by this run"),
    ("test_waivers.py",
     "What was agreed to leave alone",
     "That every waived outcome still names a check this run has, and "
     "that nothing else in the suite tolerates a failure"),
    ("test_defect_registry.py",
     "This report's own sources",
     "That every issue below still cites real code, in both languages"),
    ("test_reports.py",
     "This report itself",
     "That it is reproducible from the run above, invents no issue, drops "
     "none, and hides nothing that was waived"),
)

COVERAGE_ZH: dict[str, tuple[str, str]] = {
    "test_staging.py": ("發行檔本身", "受測的檔案樹確實逐一符合釋出的壓縮檔"),
    "test_app_driver.py": ("應用程式行程",
                           "釋出的執行檔能啟動、能服務、並能釋放資料庫"),
    "test_routes.py": ("所有已註冊的路由",
                       "從釋出的 Go 原始碼讀出的全部 141 條路由，逐一實測"),
    "test_lookups.py": ("代碼與地址清單", "各表單在查詢前提供的下拉選單"),
    "test_qbe.py": ("查詢建構器", "白名單、顯示給使用者的 SQL，以及各項防護"),
    "test_form_queries.py": ("六個單次查詢的表單",
                             "入仕、官職、社會地位、著述、社會關係、地點"
                             "——查詢與匯出"),
    "test_stateful_forms.py": ("具狀態的表單",
                               "親屬關係、社會網路、關係配對、群組資料"
                               "——工作清單"),
    "test_index_addr.py": ("索引地址排序",
                           "唯一會改寫 CBDB 正式資料（而非暫存表）的端點"),
    "test_query_matrix.py": ("每一個篩選條件，輸入取自資料本身",
                             "依釋出資料庫中實際有資料的組合各跑一次查詢，"
                             "並將每個開關的兩種狀態都測過"),
    "test_exports.py": ("所有匯出按鈕",
                        "45 個會產生檔案的端點全部按過，並回讀所得檔案"),
    "test_ui_pages.py": ("在真實瀏覽器中的頁面",
                         "每個頁面載入時不拋錯；等待使用者操作的控制項"
                         "在條件滿足後確實解除停用"),
    "test_sessions.py": ("同時開兩個分頁",
                         "一次查詢是否會取代另一個分頁即將匯出的內容"),
    "test_scratch_tables.py": ("暫存工作表",
                               "各表單各自擁有哪些暫存表——從釋出的 Go "
                               "原始碼讀出並釘住"),
    "test_zz_controls.py": ("本次執行自身的覆蓋率",
                            "釋出頁面能觸及的每一個端點，本次執行是否"
                            "真的都請求過"),
    "test_waivers.py": ("已協商擱置的項目",
                        "每一條擱置項目是否仍對應到本次執行中存在的檢查，"
                        "以及套件中沒有其他地方私自容忍失敗"),
    "test_defect_registry.py": ("本報告自身的依據",
                                "以下每一項問題所引用的程式位置仍然存在，"
                                "且中英文皆已填寫"),
    "test_reports.py": ("本報告本身",
                        "本報告可由上述執行結果完整重現，不會憑空產生問題、"
                        "不會遺漏問題，也不會隱藏任何擱置項目"),
}

STATUS_TEXT = {
    "en": {"CONFIRMED": "CONFIRMED", "APPARENTLY FIXED": "APPARENTLY FIXED",
           "INCONCLUSIVE": "INCONCLUSIVE", "NOT EXERCISED": "NOT EXERCISED"},
    "zh": {"CONFIRMED": "已確認", "APPARENTLY FIXED": "似已修復",
           "INCONCLUSIVE": "無法判定", "NOT EXERCISED": "本次未測"},
}


# ---------------------------------------------------------------------------
# reading the run
# ---------------------------------------------------------------------------

def load_run(path: Path) -> dict:
    if not path.is_file():
        raise SystemExit(
            f"no test run to report on: {path} does not exist.\n"
            "Run:  python -m pytest tests --json-report "
            f"--json-report-file={path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def outcomes_for(run: dict, defect: Defect) -> dict[str, list[str]]:
    """Group the run's outcomes for the tests that demonstrate a defect.

    Tests are matched file-qualified: matching on the bare function name
    would let a same-named test in another file confirm -- or silently
    "fix" -- the wrong defect.
    """
    grouped: dict[str, list[str]] = {}
    for test in run["tests"]:
        node = test["nodeid"]
        stem = node.split("[", 1)[0]
        if any(stem.endswith(name) for name in defect.tests):
            grouped.setdefault(test["outcome"], []).append(node)
    return grouped


def status_of(grouped: dict[str, list[str]]) -> str:
    if not grouped:
        return "NOT EXERCISED"
    if grouped.get("xfailed"):
        # Any test still demonstrating the defect means it is still there.
        return "CONFIRMED"
    if grouped.get("failed") or grouped.get("error"):
        # The test ran and neither confirmed the defect nor passed: it
        # broke on something else.  Saying "not exercised" would be a
        # lie, and "apparently fixed" would be a worse one.
        return "INCONCLUSIVE"
    if grouped.get("xpassed") or grouped.get("passed"):
        return "APPARENTLY FIXED"
    return "NOT EXERCISED"


def tests_per_file(run: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    for test in run["tests"]:
        name = test["nodeid"].split("::", 1)[0].replace("\\", "/").split("/")[-1]
        counts[name] = counts.get(name, 0) + 1
    return counts


def ranked(run: dict) -> list[Defect]:
    order = list(PRIORITIES)
    return sorted(
        DEFECTS.values(),
        key=lambda d: (_STATUS_ORDER[status_of(outcomes_for(run, d))],
                       order.index(d.priority) if d.priority in order else 9,
                       d.key))


def anchor(text: str) -> str:
    """A GitHub-flavoured heading anchor, CJK included."""
    out = []
    for char in text.lower():
        if char.isalnum() or ord(char) > 0x2E7F:
            out.append(char)
        elif char in " -_":
            out.append("-")
    return "".join(out).strip("-")


def _describe(filename: str, lang: str) -> tuple[str, str]:
    """How one test file is described, in one language."""
    for name, area_en, what_en in COVERAGE:
        if name == filename:
            if lang == "en":
                return area_en, what_en
            return COVERAGE_ZH.get(filename, (area_en, what_en))
    # Not described.  Named anyway, rather than dropped: a coverage table
    # that quietly omits a test file understates the suite, which is the
    # failure this function replaced -- the hand-written list had grown
    # stale and accounted for 277 of 823 tests while looking complete.
    # ``test_reports.py`` fails until every file in the run is described.
    return filename, STRINGS["coverage_undescribed"][lang]


def undescribed_files(run: dict) -> list[str]:
    """Test files this run has and the coverage table does not describe."""
    described = {name for name, _area, _what in COVERAGE}
    return sorted(set(tests_per_file(run)) - described)


def coverage_rows(run: dict, lang: str) -> list[tuple[str, int, str]]:
    """The coverage table, derived from the run rather than declared.

    Every file the run collected gets a row, in the declared order first
    and then whatever else appeared, and the last row is the run's own
    total -- so the rows have to add up to the number of tests reported
    above them, and a file nobody described cannot hide by being absent.
    """
    counts = tests_per_file(run)
    declared = [name for name, _area, _what in COVERAGE]
    order = declared + [name for name in sorted(counts) if name not in declared]

    rows = []
    for filename in order:
        area, what = _describe(filename, lang)
        rows.append((area, counts.get(filename, 0), what))
    rows.append((STRINGS["coverage_total"][lang], sum(counts.values()), ""))
    return rows


# ---------------------------------------------------------------------------
# waived outcomes
# ---------------------------------------------------------------------------

DEFAULT_WAIVERS = ROOT / "artifacts" / "waivers_applied.json"


def load_waivers(path: Path = DEFAULT_WAIVERS) -> dict | None:
    """What this run agreed to leave alone, or None if nothing was recorded.

    Written by ``tests/conftest.py`` on every run (see
    ``cbdb_desktop/waivers.py``).  Absent means the suite ran before this
    existed, or outside pytest -- not "nothing was waived", so the
    section is omitted rather than claiming a zero it cannot vouch for.
    """
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def waived_rows(waivers: dict, lang: str) -> list[tuple[str, ...]]:
    """One row per agreed-tolerated outcome, in the report's language."""
    modes = STRINGS["waived_modes"][lang]
    rows = []
    for entry in waivers.get("entries", ()):
        params = ", ".join(entry.get("params") or ())             or STRINGS["waived_all"][lang]
        agreed = entry.get("agreed_on") or ""
        by = entry.get("agreed_by") or ""
        rows.append((
            entry["test"],
            params,
            modes.get(entry.get("mode", "tolerate"), entry.get("mode", "")),
            f"{agreed} ({by})" if by else agreed,
            entry.get("expires") or STRINGS["waived_forever"][lang],
            entry.get("reason_zh" if lang == "zh" else "reason", ""),
        ))
    return rows


# ---------------------------------------------------------------------------
# markdown
# ---------------------------------------------------------------------------

def render_markdown(run: dict, lang: str, build: str,
                    waivers: dict | None = None) -> str:
    def S(key):
        return STRINGS[key][lang]

    summary = run["summary"]
    created = datetime.fromtimestamp(run["created"], tz=timezone.utc)
    labels = STRINGS["outcomes"][lang]
    total = summary.get("total", 0)
    out: list[str] = []

    out.append(f"# {S('title')}")
    out.append("")
    out.append(f"_{S('subtitle')}_")
    out.append("")
    out.append(f"_{S('build').format(build=build)}_")
    out.append("")
    when = f"{created:%Y-%m-%d %H:%M UTC}"
    duration = f"{run['duration']:.0f}"
    out.append("_" + S("generated").format(when=when, total=total,
                                           duration=duration) + "_")
    out.append("")
    out.append(S("letter"))
    out.append("")

    out.append(f"## {S('run_summary')}")
    out.append("")
    out.append(f"| {S('outcome')} | {S('count')} |")
    out.append("| --- | --- |")
    for key in ("passed", "failed", "error", "xfailed", "xpassed", "skipped"):
        if summary.get(key):
            out.append(f"| {labels[key]} | {summary[key]} |")
    out.append("")

    out.append(f"## {S('coverage')}")
    out.append("")
    head = S("coverage_head")
    out.append(f"| {head[0]} | {head[1]} | {head[2]} |")
    out.append("| --- | --- | --- |")
    for area, count, what in coverage_rows(run, lang):
        out.append(f"| {area} | {count} | {what} |")
    out.append("")

    if waivers is not None:
        out.append(f"## {S('waived')}")
        out.append("")
        rows = waived_rows(waivers, lang)
        if not rows:
            out.append(S("waived_none"))
            out.append("")
        else:
            out.append(S("waived_intro"))
            out.append("")
            head = S("waived_head")
            out.append("| " + " | ".join(head) + " |")
            out.append("| " + " | ".join(["---"] * len(head)) + " |")
            for row in rows:
                out.append("| " + " | ".join(row) + " |")
            out.append("")

    issues = ranked(run)
    if not issues:
        out.append(S("no_issues"))
        return "\n".join(out) + "\n"

    out.append(f"## {S('summary_table')}")
    out.append("")
    head = S("summary_head")
    out.append(f"| {head[0]} | {head[1]} | {head[2]} | {head[3]} |")
    out.append("| --- | --- | --- | --- |")
    for defect in issues:
        state = STATUS_TEXT[lang][status_of(outcomes_for(run, defect))]
        out.append(f"| {defect.key} | {defect.priority} | {state} | "
                   f"{defect.text('title', lang)} |")
    out.append("")

    out.append(f"## {S('toc')}")
    out.append("")
    for defect in issues:
        title = f"{defect.key} — {defect.text('title', lang)}"
        out.append(f"- [{title}](#{anchor(title)})")
    out.append(f"- [{S('legend')}](#{anchor(S('legend'))})")
    out.append(f"- [{S('reproduce')}](#{anchor(S('reproduce'))})")
    out.append("")

    for defect in issues:
        grouped = outcomes_for(run, defect)
        state = status_of(grouped)
        priority_text = PRIORITIES[defect.priority][0 if lang == "en" else 1]

        out.append(f"## {defect.key} — {defect.text('title', lang)}")
        out.append("")
        out.append(f"**{S('affected')}** {defect.text('area', lang)}")
        out.append("")
        out.append(f"**{S('severity')}** {defect.priority} — {priority_text}")
        out.append("")
        # Who the entry is addressed to.  Printed beside the severity
        # because the two together are what a reader needs before
        # deciding whether the rest of the section is theirs to act on:
        # a data-origin finding is fixed in the CBDB source, not in the
        # application, and sending it to the developers wastes the only
        # channel this project has.
        origin_text = ORIGINS[defect.origin][0 if lang == "en" else 1]
        out.append(f"**{S('origin')}** `{defect.origin}` — {origin_text}")
        out.append("")
        out.append(f"**{S('status')}** {STATUS_TEXT[lang][state]}")
        out.append("")

        note = STRINGS["status_note"][lang].get(state)
        if note:
            out.append(f"> {note}")
            out.append("")

        for heading, body in ((S("h_description"), defect.text("summary", lang)),
                              (S("h_evidence"), defect.text("evidence", lang)),
                              (S("h_impact"), defect.text("impact", lang))):
            out.append(f"#### {heading}")
            out.append("")
            out.append(body)
            out.append("")

        steps = defect.steps_zh if lang == "zh" and defect.steps_zh else defect.steps
        if steps:
            out.append(f"#### {S('h_steps')}")
            out.append("")
            for index, step in enumerate(steps, 1):
                out.append(f"{index}. {step}")
            out.append("")

        out.append(f"#### {S('h_fix')}")
        out.append("")
        out.append(defect.text("fix", lang))
        out.append("")

        if defect.source:
            out.append(f"#### {S('h_where')}")
            out.append("")
            for reference in defect.source:
                out.append(f"- `{reference}`")
            out.append("")

        if grouped:
            out.append(f"#### {S('h_tests')}")
            out.append("")
            for outcome in sorted(grouped):
                nodes = grouped[outcome]
                shown = ", ".join(f"`{n.split('::', 1)[-1]}`" for n in nodes[:4])
                more = f" (+{len(nodes) - 4})" if len(nodes) > 4 else ""
                out.append(f"- {len(nodes)} × {labels.get(outcome, outcome)}: "
                           f"{shown}{more}")
            out.append("")

    out.append(f"## {S('legend')}")
    out.append("")
    for code, (text_en, text_zh) in PRIORITIES.items():
        out.append(f"- **{code}** — {text_en if lang == 'en' else text_zh}")
    out.append("")

    out.append(f"## {S('reproduce')}")
    out.append("")
    body = S("reproduce_body").format(total=total)
    body = body.replace("@@run_tests@@", f"```powershell\n{RUN_COMMAND}\n```")
    body = body.replace("@@one_test@@",
                        f"```powershell\n{ONE_TEST_COMMAND}\n```")
    out.append(body)
    out.append("")

    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# word
# ---------------------------------------------------------------------------

def _set_fonts(document, lang: str) -> None:
    """Give the document a font that can render what is in it.

    python-docx sets only the Latin font; a Chinese run needs the East
    Asian font set too, or Word substitutes one and the result looks
    wrong in ways nobody notices until it is printed.
    """
    from docx.oxml.ns import qn

    latin = "Calibri"
    east_asian = "Microsoft JhengHei" if lang == "zh" else "Calibri"
    for style_name in ("Normal", "Title", "Heading 1", "Heading 2",
                       "Heading 3", "Heading 4", "List Bullet", "List Number",
                       "Intense Quote"):
        try:
            style = document.styles[style_name]
        except KeyError:
            continue
        style.font.name = latin
        rpr = style.element.get_or_add_rPr()
        rfonts = rpr.get_or_add_rFonts()
        rfonts.set(qn("w:ascii"), latin)
        rfonts.set(qn("w:hAnsi"), latin)
        rfonts.set(qn("w:eastAsia"), east_asian)


def _rich_runs(paragraph, text: str, lang: str) -> None:
    """Add text to a paragraph, honouring **bold** and `code`."""
    from docx.oxml.ns import qn
    from docx.shared import Pt

    east_asian = "Microsoft JhengHei" if lang == "zh" else "Calibri"
    for piece in re.split(r"(\*\*[^*]+\*\*|`[^`]+`)", text):
        if not piece:
            continue
        if piece.startswith("**") and piece.endswith("**"):
            run = paragraph.add_run(piece[2:-2])
            run.bold = True
        elif piece.startswith("`") and piece.endswith("`"):
            run = paragraph.add_run(piece[1:-1])
            run.font.name = "Consolas"
            run.font.size = Pt(9.5)
        else:
            run = paragraph.add_run(piece)
        # A fresh run has no rPr at all, and setting .font.name only
        # writes the Latin face; the East Asian face has to be set on the
        # element or Word substitutes a font for the Chinese.
        rpr = run._element.get_or_add_rPr()
        rpr.get_or_add_rFonts().set(qn("w:eastAsia"), east_asian)


def render_docx(run: dict, lang: str, build: str, out_path: Path,
                waivers: dict | None = None) -> Path:
    """Write the Word version, from the same content as the Markdown."""
    import docx
    from docx.shared import Pt

    def S(key):
        return STRINGS[key][lang]

    summary = run["summary"]
    created = datetime.fromtimestamp(run["created"], tz=timezone.utc)
    labels = STRINGS["outcomes"][lang]
    total = summary.get("total", 0)

    document = docx.Document()
    _set_fonts(document, lang)

    document.add_heading(S("title"), level=0)
    for line in (S("subtitle"),
                 S("build").format(build=build),
                 S("generated").format(when=f"{created:%Y-%m-%d %H:%M UTC}",
                                       total=total,
                                       duration=f"{run['duration']:.0f}")):
        paragraph = document.add_paragraph()
        _rich_runs(paragraph, line, lang)
        for run_ in paragraph.runs:
            run_.italic = True

    for block in S("letter").split("\n\n"):
        _rich_runs(document.add_paragraph(), block, lang)

    def table_of(headings, rows):
        table = document.add_table(rows=1, cols=len(headings))
        table.style = "Light Grid Accent 1"
        for index, title in enumerate(headings):
            table.rows[0].cells[index].text = str(title)
        for row in rows:
            cells = table.add_row().cells
            for index, value in enumerate(row):
                cells[index].text = str(value)
        return table

    document.add_heading(S("run_summary"), level=1)
    table_of((S("outcome"), S("count")),
             [(labels[key], summary[key])
              for key in ("passed", "failed", "error", "xfailed", "xpassed",
                          "skipped") if summary.get(key)])

    document.add_heading(S("coverage"), level=1)
    table_of(S("coverage_head"), coverage_rows(run, lang))

    if waivers is not None:
        document.add_heading(S("waived"), level=1)
        rows = waived_rows(waivers, lang)
        if not rows:
            document.add_paragraph(S("waived_none"))
        else:
            _rich_runs(document.add_paragraph(), S("waived_intro"), lang)
            table_of(S("waived_head"), rows)

    issues = ranked(run)
    if not issues:
        document.add_paragraph(S("no_issues"))
        document.save(str(out_path))
        return out_path

    document.add_heading(S("summary_table"), level=1)
    table_of(S("summary_head"),
             [(defect.key, defect.priority,
               STATUS_TEXT[lang][status_of(outcomes_for(run, defect))],
               defect.text("title", lang)) for defect in issues])

    for defect in issues:
        grouped = outcomes_for(run, defect)
        state = status_of(grouped)
        priority_text = PRIORITIES[defect.priority][0 if lang == "en" else 1]

        document.add_page_break()
        document.add_heading(f"{defect.key} — {defect.text('title', lang)}",
                             level=1)

        for label, value in ((S("affected"), defect.text("area", lang)),
                             (S("severity"),
                              f"{defect.priority} — {priority_text}"),
                             (S("status"), STATUS_TEXT[lang][state])):
            paragraph = document.add_paragraph()
            _rich_runs(paragraph, f"**{label}** {value}", lang)

        note = STRINGS["status_note"][lang].get(state)
        if note:
            paragraph = document.add_paragraph(style="Intense Quote")
            _rich_runs(paragraph, note, lang)

        for heading, body in ((S("h_description"), defect.text("summary", lang)),
                              (S("h_evidence"), defect.text("evidence", lang)),
                              (S("h_impact"), defect.text("impact", lang))):
            document.add_heading(heading, level=2)
            _rich_runs(document.add_paragraph(), body, lang)

        steps = defect.steps_zh if lang == "zh" and defect.steps_zh else defect.steps
        if steps:
            document.add_heading(S("h_steps"), level=2)
            for step in steps:
                _rich_runs(document.add_paragraph(style="List Number"),
                           step, lang)

        document.add_heading(S("h_fix"), level=2)
        _rich_runs(document.add_paragraph(), defect.text("fix", lang), lang)

        if defect.source:
            document.add_heading(S("h_where"), level=2)
            for reference in defect.source:
                _rich_runs(document.add_paragraph(style="List Bullet"),
                           f"`{reference}`", lang)

        if grouped:
            document.add_heading(S("h_tests"), level=2)
            for outcome in sorted(grouped):
                for node in grouped[outcome]:
                    _rich_runs(document.add_paragraph(style="List Bullet"),
                               f"`{node.split('::', 1)[-1]}` "
                               f"({labels.get(outcome, outcome)})", lang)

    document.add_page_break()
    document.add_heading(S("legend"), level=1)
    for code, (text_en, text_zh) in PRIORITIES.items():
        _rich_runs(document.add_paragraph(style="List Bullet"),
                   f"**{code}** — {text_en if lang == 'en' else text_zh}", lang)

    document.add_heading(S("reproduce"), level=1)
    body = S("reproduce_body").format(total=total)
    for block in body.split("\n\n"):
        if block in ("@@run_tests@@", "@@one_test@@"):
            command = (RUN_COMMAND if block == "@@run_tests@@"
                       else ONE_TEST_COMMAND)
            paragraph = document.add_paragraph()
            code = paragraph.add_run(command)
            code.font.name = "Consolas"
            code.font.size = Pt(9.5)
        else:
            _rich_runs(document.add_paragraph(), block, lang)

    document.save(str(out_path))
    return out_path


# ---------------------------------------------------------------------------
# pdf
# ---------------------------------------------------------------------------

def render_pdf(docx_path: Path, out_path: Path) -> Path:
    """Convert the Word file with Word itself.

    Word is used rather than a Python PDF library because these reports
    are bilingual: laying Chinese out correctly needs the fonts and the
    line-breaking rules, and Word already has both.  If Word is missing
    the caller is told plainly rather than handed a PDF with boxes where
    the Chinese should be.
    """
    try:
        import pythoncom
        import win32com.client
    except ImportError as exc:  # pragma: no cover - platform dependent
        raise RuntimeError(
            "PDF output needs Word via pywin32 (pip install pywin32); "
            "use --format md,docx to skip it") from exc

    wd_export_format_pdf = 17
    pythoncom.CoInitialize()
    word = None
    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        document = word.Documents.Open(str(docx_path), ReadOnly=True)
        try:
            document.ExportAsFixedFormat(str(out_path), wd_export_format_pdf)
        finally:
            document.Close(False)
    except Exception as exc:  # pragma: no cover - depends on the box
        raise RuntimeError(f"Word could not write {out_path.name}: {exc}") from exc
    finally:
        if word is not None:
            try:
                word.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()
    return out_path


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

def _build_name() -> str:
    try:
        from cbdb_desktop.config import load_config

        configured = load_config().zip_path
        return configured.name if configured else "unknown"
    except Exception:  # pragma: no cover - the report must not need a .env
        return "unknown"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON,
                        help="pytest JSON report to read (default: %(default)s)")
    parser.add_argument("--out-dir", type=Path, default=REPORTS)
    parser.add_argument("--waivers", type=Path, default=DEFAULT_WAIVERS,
                        help="the run's waiver record, written by pytest "
                             "(default: %(default)s).  Absent means the "
                             "section is omitted rather than claimed empty.")
    parser.add_argument("--lang", default="en,zh",
                        help="languages to write (default: %(default)s)")
    parser.add_argument("--format", default="md,docx,pdf",
                        help="formats to write (default: %(default)s)")
    args = parser.parse_args(argv)

    run = load_run(args.json)
    build = _build_name()
    waivers = load_waivers(args.waivers)
    langs = [lang.strip() for lang in args.lang.split(",") if lang.strip()]
    formats = [fmt.strip() for fmt in args.format.split(",") if fmt.strip()]

    unknown = set(langs) - set(LANGS)
    if unknown:
        raise SystemExit(f"unknown language(s): {sorted(unknown)}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    problems: list[str] = []

    for lang in langs:
        stem = args.out_dir / STEM[lang]

        if "md" in formats:
            # Write beside the target and rename: a crash halfway through
            # must not leave a truncated report where the good one was.
            scratch = stem.with_suffix(".md.new")
            scratch.write_text(render_markdown(run, lang, build, waivers),
                               encoding="utf-8")
            os.replace(scratch, stem.with_suffix(".md"))
            written.append(stem.with_suffix(".md"))

        if "docx" in formats or "pdf" in formats:
            try:
                docx_path = render_docx(run, lang, build,
                                        stem.with_suffix(".docx"), waivers)
                written.append(docx_path)
            except Exception as exc:
                problems.append(f"{STEM[lang]}.docx: {exc}")
                continue

            if "pdf" in formats:
                try:
                    written.append(render_pdf(docx_path,
                                              stem.with_suffix(".pdf")))
                except Exception as exc:
                    problems.append(f"{STEM[lang]}.pdf: {exc}")

    for path in written:
        print(path)

    confirmed = sum(1 for d in DEFECTS.values()
                    if status_of(outcomes_for(run, d)) == "CONFIRMED")
    # stdout, not stderr: a caller that treats any stderr output as a
    # failure (PowerShell does) would otherwise report a successful run
    # as an error.
    print(f"{confirmed} of {len(DEFECTS)} recorded issues confirmed by this run")
    if waivers:
        print(f"{len(waivers.get('entries', ()))} waived outcome(s) listed "
              f"from {args.waivers.name}")
    missing = undescribed_files(run)
    if missing:
        # Printed rather than raised: the report is still better written
        # than not, and tests/test_reports.py is what makes this fail.
        print("test files with no description in the coverage table: "
              + ", ".join(missing))

    if problems:
        print("could not write:")
        for problem in problems:
            print(f"  {problem}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

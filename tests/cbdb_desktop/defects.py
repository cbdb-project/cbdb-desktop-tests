"""How this suite records a defect in the shipped build.

A test that has found a real defect must do three things at once: stay
out of the way of a green run (a permanently red suite teaches people to
ignore it), say loudly what is wrong on every run, and *notice when the
defect is fixed* so the marker can be removed.

``pytest.mark.xfail(strict=True)`` does all three -- but on its own it
also swallows any *other* failure of the same test.  A test marked
"expected to fail because the search index is empty" would go on quietly
xfailing if the endpoint started returning 500, or malformed JSON, or a
different wrong answer entirely.

So a defect is signalled by raising :class:`KnownShippedDefect` after the
test has confirmed the *exact* known signature, and the marker is
narrowed to that exception::

    @pytest.mark.xfail(strict=True, raises=KnownShippedDefect,
                       reason=BY_NAME["name-search"].reason)
    def test_something(app):
        result = app.json(...)
        if result == the_known_wrong_answer:
            raise KnownShippedDefect("...")
        assert result == the_right_answer

Now the known defect xfails; anything else fails as a failure; and a fix
turns the test green-unexpectedly, which pytest reports as an error.

The registry below is the single source of truth for what has been found,
**in both languages**.  ``reports/generate_report.py`` turns it, plus the
outcomes of one run, into the English and Traditional Chinese reports --
so the bug report and the tests can never drift apart, and neither can
the two translations.

**Every run is a fresh assessment.**  This registry describes *the build
under test*, not the history of the project.  When a defect is fixed its
entry is deleted and its markers come off in the same commit; it does
not become an entry that says "fixed in 2026-09-07".  The git history of
this file is the record of what each build did, and it is a better one
than a growing list of resolved items, which nobody re-reads and which
makes a reader of the current report guess which half applies to them.

**Every defect says where it comes from** (``origin``), because that
decides who fixes it -- see the ``ORIGINS`` table below and AGENTS.md
§ "Where a defect comes from".  A problem in the data that arrives from
the CBDB source is not a problem the application developers can fix, and
sending it to them wastes the one channel this project has.
"""
from __future__ import annotations

from dataclasses import dataclass


class KnownShippedDefect(AssertionError):
    """Raised when a test confirms a defect already known to be shipped.

    Subclasses AssertionError so the message reads like a normal test
    failure when it does escape (for instance under ``--runxfail``).
    """


#: Priority bands, in the shape the CBDB team already receives them from
#: the .mdb suite, adapted to a web application.  Ordered: P0 first.
PRIORITIES: dict[str, tuple[str, str]] = {
    "P0": ("Silent wrong answer — the application returns wrong or empty "
           "results, or produces a file nothing can read, with no error "
           "shown to the user.",
           "靜默的錯誤結果——程式回傳錯誤或空白的結果，或產生任何軟體都讀不了"
           "的檔案，而且沒有任何錯誤提示。"),
    "P1": ("Destructive write — a request rewrites stored data that it "
           "should not, and the previous state cannot be recovered.",
           "破壞性寫入——一次請求改寫了本不該改寫的既存資料，原本的狀態無法復原。"),
    "P2": ("Visible runtime error — the user's action fails with a server "
           "error.",
           "可見的執行時錯誤——使用者的操作以伺服器錯誤收場。"),
    "P3": ("Packaging — the released files contain something they should "
           "not.",
           "封裝問題——釋出的檔案裡含有不該出現的內容。"),
    "P4": ("Data integrity — a reference in the shipped data does not "
           "resolve.",
           "資料完整性——釋出資料中存在無法解析的參照。"),
}

#: Where a defect comes from, which is the same question as who can fix
#: it.  Recorded per defect and printed in the report, because the two
#: audiences are different people and a report that mixes them makes
#: both of them read past the half that is not theirs.
#:
#: The deciding experiment is always the same one: **would this survive a
#: rebuild of the database from the current CBDB source, using this same
#: code?**  If yes, it is in the code (``software``).  If a clean rebuild
#: makes it disappear, it was in the data or in how the release was put
#: together, and no code change would have prevented it.
ORIGINS: dict[str, tuple[str, str]] = {
    "software": (
        "In the application: cbdb.exe, its Go sources, its page "
        "templates, or the database builder's logic.  Fixed by the "
        "CBDB-Desktop developers.",
        "程式本身的問題：cbdb.exe、其 Go 原始碼、頁面模板，或資料庫建置程式"
        "的邏輯。由 CBDB-Desktop 的開發者修正。"),
    "data": (
        "In the data that arrives from the CBDB (MariaDB) source: a "
        "missing row, a dangling reference, a column whose values are "
        "not what its name suggests.  The application is reporting it "
        "faithfully.  Fixed in the source data by the CBDB data team, "
        "**not** by the application developers.",
        "來自 CBDB（MariaDB）上游資料的問題：缺列、無法解析的參照、欄位內容"
        "與名稱不符等。程式只是忠實地把資料呈現出來。由 CBDB 資料團隊在來源"
        "資料端修正，**不需要**交給程式開發者。"),
    "release": (
        "In how this particular release was assembled -- a working copy "
        "shipped in place of a freshly built one, a file that was not "
        "regenerated.  Fixed in the release process by whoever builds "
        "the distribution.",
        "這一次釋出的組裝流程問題——例如把開發用的工作副本當成正式建置成果"
        "送出、某個檔案沒有重新產生。由負責建置發行檔的人在流程上修正。"),
}


@dataclass(frozen=True)
class Defect:
    """One confirmed defect in the shipped build, in both languages."""

    key: str
    priority: str            # "P0" … "P4"
    severity: str            # "high" | "medium" | "low"
    #: One of ORIGINS.  Decides who the defect is reported to.
    origin: str
    title: str
    title_zh: str
    area: str                # which part of the application
    area_zh: str
    summary: str             # what is wrong, in a sentence or two
    summary_zh: str
    evidence: str            # the measurement that establishes it
    evidence_zh: str
    impact: str              # what it means for someone using CBDB
    impact_zh: str
    fix: str                 # what would resolve it
    fix_zh: str
    steps: tuple[str, ...] = ()      # how a person reproduces it
    steps_zh: tuple[str, ...] = ()
    source: tuple[str, ...] = ()     # file:line references into the build
    tests: tuple[str, ...] = ()      # test names that demonstrate it

    @property
    def reason(self) -> str:
        """The line pytest prints for this defect in an xfail summary.

        Deliberately one line.  The full account -- evidence, impact,
        reproduction, suggested fix -- lives in the generated reports;
        repeating it per test made a run's summary unreadable, which
        defeats the point of saying it at all.
        """
        return (f"SHIPPED DEFECT [{self.key}] {self.title} "
                f"(reports/CBDB_Desktop_Issues_EN.md)")

    def text(self, field: str, lang: str) -> str:
        """One field in one language, falling back to English."""
        if lang == "zh":
            return getattr(self, f"{field}_zh", "") or getattr(self, field)
        return getattr(self, field)


_DEFECTS: tuple[Defect, ...] = (
    Defect(
        key="CBDB-D-014",
        priority="P0",
        severity="low",
        origin="software",
        title="Unticking every category on the Places form still returns "
              "biographical addresses",
        title_zh="在地點表單把所有類別都取消勾選後，仍然會回傳籍貫類地址",
        area="Places form (/LookAtPlace)",
        area_zh="地點表單（/LookAtPlace）",
        summary=(
            "The Places form offers seven category checkboxes -- "
            "Biography, Association Place, Association Person, Entry, "
            "Kinship, Office, Institution -- and the query handler "
            "substitutes Biography when it finds all seven switched off "
            "(places_form_backend.go:204-206).  As a guard against an "
            "empty request that is reasonable.  What makes it a defect is "
            "that the page lets a user get there: nothing requires at "
            "least one category, so unticking all seven and pressing "
            "Query returns the biographical addresses the user has just "
            "excluded, with no message saying so."),
        summary_zh=(
            "地點表單提供七個類別核取方框——籍貫、社會關係地點、社會關係人物、"
            "入仕、親屬關係、官職、機構——而查詢處理程式在發現七個全部關閉時，"
            "會自行代入「籍貫」（places_form_backend.go:204-206）。作為對"
            "空白請求的防護，這樣做是合理的。真正構成缺陷的是頁面允許使用者"
            "走到這一步：沒有任何規則要求至少勾選一個類別，因此把七個全部"
            "取消後按下查詢，回傳的正是使用者剛剛排除掉的籍貫類地址，而且"
            "沒有任何提示。"),
        evidence=(
            "For address code 5121, all seven off returns 60 rows and "
            "Biography alone returns the same 60; all seven on returns "
            "69.  The five categories that contribute nothing for that "
            "code are indistinguishable from ignored options in a "
            "one-switch-at-a-time sweep, which is what made the all-off "
            "case the decisive experiment.  In the page, ``inc-biog`` "
            "merely starts checked and no code path prevents the empty "
            "selection."),
        evidence_zh=(
            "以地址代碼 5121 為例：七個全部關閉會回傳 60 列，只開「籍貫」也"
            "同樣是那 60 列；七個全開則是 69 列。對這個代碼而言，那五個沒有"
            "貢獻任何資料的類別，在「一次只切換一個開關」的掃描中與被忽略的"
            "選項無法區分——這正是為什麼「全部關閉」才是決定性的實驗。在頁面"
            "端，``inc-biog`` 只是預設為勾選，並沒有任何程式碼阻止使用者送出"
            "空白的選擇。"),
        impact=(
            "Narrow.  A user has to untick all seven categories, which is "
            "an odd thing to do deliberately -- but it is what somebody "
            "does when they want to start from nothing and add one back, "
            "and the result they get is silently not what they asked "
            "for.  Recorded because it is cheap to fix and because "
            "\"the form returned a category I excluded\" is the kind of "
            "thing that costs a historian a day when they eventually "
            "notice."),
        impact_zh=(
            "影響範圍很窄。使用者必須把七個類別全部取消勾選，刻意這樣做的"
            "情況不多——但當有人想「先全部清空、再一個一個加回來」時就會這麼"
            "做，而他得到的結果並不是他要求的，卻沒有任何提示。之所以記錄"
            "下來，是因為修起來很便宜，而且「表單回傳了我排除掉的類別」這種"
            "問題，等到研究者真的發現時，往往已經浪費了一整天。"),
        fix=(
            "Either honour the empty selection (return nothing, which is "
            "what was asked) or refuse it in the page -- keep Run Query "
            "disabled until at least one category is ticked, the way the "
            "Networks form gates on its relation checkboxes.  The second "
            "is the smaller change and gives the user an explanation "
            "instead of a surprise.  Leave the backend's fallback where "
            "it is: it is a sensible guard for a request that arrives "
            "empty from somewhere else."),
        fix_zh=(
            "兩種做法皆可：一是尊重空白的選擇（回傳空結果，那正是使用者要求"
            "的），二是在頁面端就拒絕——在至少勾選一個類別之前保持 Run Query "
            "為停用，就像社會網絡表單以關係核取方框作為前置條件那樣。後者改"
            "動較小，而且能給使用者一個說明，而不是一個意外。後端的預設代入"
            "可以保留：對於從別處送來的空白請求，那是一道合理的防護。"),
        steps=(
            "Open the Places form (/LookAtPlace) and select an address "
            "with a few dozen people.",
            "Untick all seven category checkboxes, Biography included.",
            "Press Run Query.",
            "Rows come back, and they are exactly the ones Biography "
            "alone returns.",
        ),
        steps_zh=(
            "開啟地點表單（/LookAtPlace），選一個有數十人的地址。",
            "把七個類別核取方框全部取消勾選，包含「籍貫」。",
            "按下 Run Query。",
            "結果回傳了資料，而且正是只開「籍貫」時會得到的那一批。",
        ),
        source=("Code/places_form_backend.go:204",
                "Templates/places/index.html"),
        tests=("test_turning_every_category_off_returns_nothing",),
    ),
    Defect(
        key="CBDB-D-013",
        priority="P0",
        severity="high",
        origin="software",
        title="Run Query stays greyed out on the Networks form after the "
              "page is reopened",
        title_zh="重新開啟社會網絡表單後，Run Query 仍然是灰色的",
        area="Networks form (/LookAtNetworks)",
        area_zh="社會網絡表單（/LookAtNetworks）",
        summary=(
            "The Networks page decides whether Run Query may be pressed in "
            "one function, checkRunCriteria(), which reads the flags that "
            "say whether a person or a place has been selected.  Five "
            "places set those flags and four of them call that function "
            "afterwards.  The fifth is the page's own restore path, which "
            "runs on load: it asks the server how many people are in the "
            "working list, sets the flag, enables the All People button -- "
            "and never re-runs the check.  So a user who returns to the "
            "form with a person already selected has met the precondition, "
            "can see the person count on screen, and cannot press Run "
            "Query until they happen to touch one of the checkboxes."),
        summary_zh=(
            "社會網絡頁面用一個函式 checkRunCriteria() 決定 Run Query 是否"
            "可按，它讀取「是否已選擇人物或地點」這些旗標。共有五處會設定"
            "這些旗標，其中四處在設定後會呼叫該函式。第五處是頁面自己的狀態"
            "還原流程，在載入時執行：它向伺服器詢問工作清單裡有多少人、設定"
            "旗標、啟用 All People 按鈕——卻沒有重新執行那個檢查。因此，"
            "使用者重新回到這個表單、明明已經選好人物、畫面上也看得到人數，"
            "卻要等到碰巧去點某個核取方框，Run Query 才會變成可按。"),
        evidence=(
            "Reproduced in a real browser (Chromium, driven by "
            "tests/test_ui_pages.py).  With person 1762 registered on the "
            "server and the page reloaded: gUsePersonID is true, "
            "gPersonCount is 1, the person count is displayed, All People "
            "is enabled -- and btn-run is disabled.  Ticking any of the "
            "four relation checkboxes fires its onchange, which calls "
            "checkRunCriteria(), and Run Query enables immediately.  The "
            "asymmetry is visible in the source: the restore path sets the "
            "flag and enables one button, while every other flag-setting "
            "path ends in checkRunCriteria()."),
        evidence_zh=(
            "已在真實瀏覽器中重現（Chromium，由 tests/test_ui_pages.py "
            "驅動）。在伺服器端已登記人物 1762、並重新載入頁面的情況下："
            "gUsePersonID 為 true、gPersonCount 為 1、畫面顯示人數、"
            "All People 為可按——而 btn-run 是灰的。只要勾選四個關係核取"
            "方框中的任何一個，就會觸發它的 onchange、呼叫 "
            "checkRunCriteria()，Run Query 立刻變成可按。這種不對稱在原始碼"
            "中看得很清楚：還原流程設定旗標並啟用了一個按鈕，而其他每一條"
            "設定旗標的路徑最後都會呼叫 checkRunCriteria()。"),
        impact=(
            "The user has done everything the form asks and the button "
            "does not work, with nothing on screen to explain why -- the "
            "person is listed, the filters are set, and Run Query is grey. "
            " There is no error and no hint that touching an unrelated "
            "checkbox would fix it.  Reported by the maintainer as \"I "
            "entered a person, chose the relations and the dynasty, and "
            "Run Query is always grey\"."),
        impact_zh=(
            "使用者已經照表單要求做完了每一步，按鈕卻不能用，畫面上也沒有"
            "任何說明——人物列在那裡、篩選條件都設好了，Run Query 卻是灰的。"
            "沒有錯誤訊息，也沒有任何提示說「去碰一下某個無關的核取方框就好"
            "了」。維護者的原話是：「輸入了人名、選擇了關係和朝代之後，"
            "run query 始終是灰的」。"),
        fix=(
            "Call checkRunCriteria() at the end of the restore path, as "
            "the other four flag-setting paths already do.  Worth doing "
            "the same in reverse: have the *only* writer of "
            "btn-run.disabled be that one function, so a future path "
            "cannot set the flag and forget -- the bug is not the missing "
            "line so much as its being possible to omit."),
        fix_zh=(
            "在還原流程的最後呼叫 checkRunCriteria()，就像另外四條設定旗標"
            "的路徑那樣。也建議反過來加一道保障：讓 btn-run.disabled 的"
            "*唯一*寫入者就是那個函式，這樣未來新增的路徑就不可能設了旗標"
            "卻忘了刷新——真正的問題不只是少了一行，而是這一行有可能被漏掉。"),
        steps=(
            "Open the Networks form (/LookAtNetworks) and select a person "
            "with Select Person.  Run Query enables, as it should.",
            "Navigate away and come back, or simply reload the page.",
            "The person count is still shown and All People is enabled, so "
            "the selection survived.",
            "Tick Kinship Relations, Non-Kinship Relations, Male and "
            "Female. Run Query is still grey.",
            "Untick and re-tick any one of those checkboxes: Run Query "
            "enables. Nothing else changed.",
        ),
        steps_zh=(
            "開啟社會網絡表單（/LookAtNetworks），用 Select Person 選一位"
            "人物。此時 Run Query 會如預期變成可按。",
            "離開頁面再回來，或直接重新載入頁面。",
            "人數仍然顯示著、All People 也還是可按，可見選擇並沒有遺失。",
            "勾選親屬關係、非親屬關係、男、女。Run Query 仍然是灰的。",
            "把其中任何一個核取方框取消再勾選一次：Run Query 就變成可按了。"
            "其他什麼都沒有改變。",
        ),
        source=("Templates/networks/index.html",),
        tests=("test_a_control_is_enabled_once_its_precondition_is_met",),
    ),
    Defect(
        key="CBDB-D-011",
        priority="P0",
        severity="high",
        origin="software",
        title="Every exported CSV is UTF-8 without a byte-order mark, so "
              "Excel shows Chinese names as mojibake",
        title_zh="所有匯出的 CSV 都是不帶 BOM 的 UTF-8，在 Excel 開啟時中文"
                 "名字全變亂碼",
        area="Every export on every form",
        area_zh="所有表單的所有匯出功能",
        summary=(
            "The exported files are named EntryData_UTF8.csv, "
            "AssociationsPeople_UTF8.csv and so on, and their bytes really "
            "are UTF-8 -- but none of them carries a UTF-8 byte-order "
            "mark.  Excel on Windows decides a .csv's encoding by looking "
            "for that mark and, finding none, reads the file in the "
            "system ANSI code page.  Every Chinese name, place and title "
            "in the file is then displayed as mojibake."),
        summary_zh=(
            "匯出的檔案名為 EntryData_UTF8.csv、AssociationsPeople_UTF8.csv "
            "之類，內容的位元組也確實是 UTF-8——但沒有任何一個檔案帶上 UTF-8 "
            "的位元組順序記號（BOM）。Windows 版 Excel 判斷 .csv 編碼的方式"
            "就是找這個記號，找不到就改用系統的 ANSI 代碼頁來讀。於是檔案裡"
            "所有中文人名、地名與書名，開起來全都是亂碼。"),
        evidence=(
            "Every export in the suite is decoded and its first bytes "
            "inspected: not one of the 42 file-producing endpoints emits "
            "EF BB BF, and a search of the shipped Go source for a "
            "byte-order mark in any spelling (\\xEF, \\uFEFF, \"BOM\") "
            "returns nothing at all.  The files contain non-ASCII in "
            "every case that matters -- a Neo4j People file for one "
            "kinship network carries names in Chinese in its second "
            "column."),
        evidence_zh=(
            "測試會把每一個匯出檔解碼並檢查開頭的位元組：42 個會產生檔案的"
            "端點裡，沒有一個輸出 EF BB BF；在釋出的 Go 原始碼中以各種寫法"
            "搜尋 BOM（\\xEF、\\uFEFF、\"BOM\"）也完全找不到。而檔案內容在"
            "所有真正會用到的情況下都含有非 ASCII 字元——例如一個親屬網絡的 "
            "Neo4j People 檔，第二欄就是中文姓名。"),
        impact=(
            "This is the whole point of the application for most of its "
            "users: they export a result and open it.  The application "
            "reports success, the file downloads, and what appears on "
            "screen is unreadable -- which looks like corrupt data rather "
            "than an encoding default, so the natural next step is to "
            "doubt CBDB.  The workaround (Data > From Text/CSV, choose "
            "UTF-8) is not discoverable, and three bytes at the front of "
            "each file would remove the need for it."),
        impact_zh=(
            "對多數使用者而言，這正是這個程式存在的目的：匯出結果，然後打開"
            "來看。程式顯示成功、檔案順利下載，畫面上卻是一片無法閱讀的內容"
            "——看起來像資料壞了，而不是編碼預設值的問題，於是最自然的反應會"
            "是懷疑 CBDB 的資料。變通做法（資料 > 從文字/CSV，選 UTF-8）並"
            "不容易被發現，而只要在每個檔案開頭加上三個位元組就不再需要它。"),
        fix=(
            "Write EF BB BF at the start of every text export whose "
            "consumer is a spreadsheet -- the .csv, .tab and .txt "
            "families.  One shared helper, since the buffers are all "
            "built the same way (cbdb_shared_utils.go's toDataURL is the "
            "natural place for the CSV ones).  Leave the KML and the "
            "SNA formats alone: XML declares its own encoding, and Pajek, "
            "GDF and VNA readers do not expect a mark."),
        fix_zh=(
            "在每一個以試算表為使用對象的文字匯出檔開頭寫入 EF BB BF——也就"
            "是 .csv、.tab 與 .txt 這幾類。由於這些緩衝區的建立方式相同，"
            "可以集中在一個共用函式處理（CSV 類最自然的位置是 "
            "cbdb_shared_utils.go 的 toDataURL）。KML 與社會網絡格式請保持"
            "原狀：XML 會自行宣告編碼，而 Pajek、GDF、VNA 的讀取程式並不預期"
            "有這個記號。"),
        steps=(
            "Open the Entry form (/LookAtEntry), pick an entry code and "
            "press Query.",
            "Press Export Results and save EntryPeopleData_UTF8.csv.",
            "Double-click the file so Excel opens it: the Chinese columns "
            "are mojibake.",
            "Inspect the first bytes -- `certutil -dump "
            "EntryPeopleData_UTF8.csv | more`, or open it in a hex editor "
            "-- and there is no EF BB BF.",
            "Re-open the same file through Data > From Text/CSV and choose "
            "65001 / UTF-8: the text is correct, which is what identifies "
            "the missing mark as the whole problem.",
        ),
        steps_zh=(
            "開啟入仕表單（/LookAtEntry），選一個入仕代碼並按下查詢。",
            "按下匯出結果，儲存 EntryPeopleData_UTF8.csv。",
            "直接雙擊該檔讓 Excel 開啟：中文欄位是亂碼。",
            "檢視檔案開頭的位元組——執行 `certutil -dump "
            "EntryPeopleData_UTF8.csv | more`，或用十六進位編輯器開啟"
            "——會發現沒有 EF BB BF。",
            "改用「資料 > 從文字/CSV」重新開啟同一個檔案並選擇 65001 / "
            "UTF-8：文字就正確了。這正說明缺少那個記號就是問題的全部。",
        ),
        source=("Code/cbdb_shared_utils.go:60", "Code/entry_form_backend.go",
                "Code/kinship_form_backend.go"),
        tests=("test_a_spreadsheet_export_can_be_opened_by_a_spreadsheet",
               "test_no_export_writes_a_byte_order_mark"),
    ),
    Defect(
        key="CBDB-D-012",
        priority="P0",
        severity="high",
        origin="software",
        title="A multi-file export saves only the first file and reports "
              "that it saved them all",
        title_zh="多檔匯出只存下第一個檔案，卻回報「全部完成」",
        area="Export Results and Neo4j, on every form that returns more "
             "than one file",
        area_zh="所有會回傳多個檔案的表單匯出功能（匯出結果、Neo4j）",
        summary=(
            "An export that produces several files downloads them by "
            "creating one hidden <a download> per file and clicking each "
            "in turn, all inside a single user gesture.  Browsers permit "
            "one automatic download per gesture and block the rest, so "
            "the first file is saved and the others are not, unless the "
            "user has granted the site permission to download several "
            "files at once.  The page then reports the number of files "
            "the *server* returned -- \"2 file(s) ready\" -- because it "
            "counts the response and never asks what the browser did.  "
            "That second half is a defect on its own: the message is "
            "wrong whenever the browser declines, and the page has no way "
            "to know that it is."),
        summary_zh=(
            "會產生多個檔案的匯出，做法是為每個檔案建立一個隱藏的 "
            "<a download> 並依序點擊，而且全部發生在同一次使用者操作中。"
            "瀏覽器每次操作只允許一個自動下載，其餘會被封鎖，因此只有第一個"
            "檔案被存下來，其他都沒有。接著頁面回報的是*伺服器*送回的檔案"
            "數量——「2 file(s) ready」——因為它數的是回應內容，而不是實際"
            "完成的下載。一旦觸發封鎖，瀏覽器連後續的匯出也會一併拒絕，這就"
            "是為什麼第二次按下匯出看起來毫無反應。"),
        evidence=(
            "Three separate observations, and it matters which is which.  "
            "(1) The maintainer, in Chrome, at "
            "http://localhost:8042/LookAtEntry: Export Results reported "
            "\"Query results export complete - 2 file(s) ready\", one file "
            "arrived, and pressing Export again saved nothing at all.  "
            "(2) The mechanism, in the shipped templates: Entry's two "
            "multi-file handlers fire their clicks in one tick -- "
            "`(j.files || []).forEach(f => triggerDownload(f.url, "
            "f.name))` -- and then report `(j.files || []).length`, which "
            "is the server's count and not the browser's.  Four pages do "
            "the same; Associations and Networks stagger their clicks by "
            "150 ms per file, which is an attempt at the same problem and "
            "still one gesture.  Group Data's Neo4j export returns ten "
            "files this way.  (3) Driving the real page in headless "
            "Chromium with downloads auto-accepted: the page attempts two "
            "downloads per press and the browser accepts **both**, on both "
            "presses.  So the count-reporting half is confirmed by "
            "automation and the blocking half is not reproducible that "
            "way -- an automated browser with a download policy of "
            "\"always accept\" is not the user's browser.  Chrome treats "
            "several programmatic downloads from one gesture as automatic "
            "multiple downloads, which is a per-site permission that "
            "defaults to asking, and once it is not granted the page's "
            "later exports save nothing."),
        evidence_zh=(
            "三項各自獨立的觀察，而它們的分別很重要。"
            "(1) 維護者在自己的 Chrome 上、於 "
            "http://localhost:8042/LookAtEntry 按下匯出結果：畫面顯示"
            "「Query results export complete — 2 file(s) ready」，實際只"
            "收到一個檔案；再按一次匯出則完全沒有存下任何東西。"
            "(2) 機制就在釋出的頁面模板裡：入仕表單的兩個多檔處理函式在同一"
            "個事件迴圈裡連續點擊——`(j.files || []).forEach(f => "
            "triggerDownload(f.url, f.name))`——然後回報 `(j.files || "
            "[]).length`，那是伺服器的數量，不是瀏覽器的。共有四個頁面採用"
            "同樣寫法；社會關係與社會網絡頁面會以每個檔案 150 毫秒的間隔"
            "錯開點擊，那是針對同一問題的嘗試，但仍屬於同一次使用者操作。"
            "群體資料的 Neo4j 匯出就是這樣一次回傳十個檔案。"
            "(3) 以自動化的無介面 Chromium（下載設定為一律接受）驅動真正的"
            "頁面：頁面每次按下都嘗試兩個下載，而瀏覽器兩次按下都**全部"
            "接受**。也就是說，「回報數量錯誤」這一半可由自動化確認，而"
            "「被封鎖」那一半無法用這種方式重現——一個下載政策設為「一律"
            "接受」的自動化瀏覽器，並不是使用者的瀏覽器。Chrome 會把同一次"
            "操作觸發的多個程式化下載視為「自動下載多個檔案」，那是一項"
            "以站台為單位、預設會詢問的權限；一旦沒有取得，該頁面之後的匯出"
            "就什麼都不會存下。"),
        impact=(
            "The file that goes missing is the second one, and on every "
            "form that is the people file -- the names, index years and "
            "coordinates.  A user who trusts the message believes they "
            "have a complete export and discovers otherwise, if at all, "
            "much later.  It also makes the export button appear broken "
            "on the second press, which is how it was noticed."),
        impact_zh=(
            "遺失的是第二個檔案，而在每個表單裡那都是人物檔——姓名、指標年"
            "與座標。相信畫面訊息的使用者會以為自己拿到了完整的匯出結果，"
            "若真的發現不對，往往也已經過了很久。此外，它也讓匯出按鈕在第二"
            "次按下時看起來壞掉了——這個問題就是這樣被發現的。值得注意的是，"
            "自動化測試單憑自己不可能發現這一點：無介面瀏覽器會接受全部下載，"
            "使用者的瀏覽器不會。"),
        fix=(
            "Two independent halves.  (1) Deliver a multi-file export as "
            "**one** download: a zip built server-side is the usual "
            "answer and needs no browser cooperation.  (2) Stop reporting "
            "a count the page cannot know: say what was requested "
            "(\"preparing 2 files\") or nothing, never \"2 file(s) "
            "downloaded\".  The second half is a one-line change per "
            "handler and removes the part of this that misleads."),
        fix_zh=(
            "分成兩個彼此獨立的部分。(1) 讓多檔匯出變成**一次**下載：最常"
            "見的做法是在伺服器端打包成 zip，完全不需要瀏覽器配合。"
            "(2) 不要回報頁面無從得知的數量：可以說明「正在準備 2 個檔案」"
            "或什麼都不說，但絕不要說「已下載 2 個檔案」。後者每個處理函式"
            "只需改一行，就能去掉這個問題中會誤導使用者的部分——而且那一半"
            "無論瀏覽器是否放行都是錯的。"),
        steps=(
            "Open the Entry form (/LookAtEntry), pick an entry code and "
            "press Query.",
            "Press Export Results.  The status line reads \"Query results "
            "export complete - 2 file(s) ready\".",
            "Look in the download folder: one file, not two.",
            "Press Export Results again.  Nothing is saved, and the "
            "status line says the same thing.  (If Chrome has been "
            "granted \"automatic downloads\" for the site, both files "
            "arrive and only the misreported count remains -- which is "
            "how an automated browser sees it.)",
            "The same happens for Neo4j on Entry, Association Pairs and "
            "Group Data, where the file sets are six, four and ten files.",
        ),
        steps_zh=(
            "開啟入仕表單（/LookAtEntry），選一個入仕代碼並按下查詢。",
            "按下匯出結果，狀態列顯示「Query results export complete — "
            "2 file(s) ready」。",
            "查看下載資料夾：只有一個檔案，不是兩個。",
            "再按一次匯出結果，什麼都沒有存下來，狀態列仍顯示同樣的訊息。"
            "（若該站台已被授予「自動下載多個檔案」的權限，兩個檔案都會"
            "到齊，只剩下數量回報錯誤的問題——自動化瀏覽器看到的就是這樣。）",
            "入仕、人物配對與群體資料表單的 Neo4j 匯出也一樣，它們的檔案組"
            "分別是六個、四個與十個檔案。",
        ),
        source=("Templates/entry/index.html", "Templates/group_data/index.html",
                "Templates/association_pairs/index.html",
                "Templates/associations/index.html"),
        tests=("test_no_page_asks_the_browser_for_more_than_one_download",),
    ),
    Defect(
        key="CBDB-D-008",
        priority="P2",
        severity="high",
        origin="software",
        title="Three of the Networks form's export buttons always fail",
        title_zh="社會網絡表單有三個匯出按鈕永遠失敗",
        area="Networks form (/LookAtNetworks) — Pajek, Gephi and UCINet",
        area_zh="社會網絡表單（/LookAtNetworks）——Pajek、Gephi 與 UCINet",
        summary=(
            "The Pajek, Gephi and UCINet exports each read the edges of "
            "the network out of ZZ_SN_NETWORK and ask that table for a "
            "column called c_node_dist.  ZZ_SN_NETWORK has no such "
            "column -- the distance it carries per edge is called "
            "c_edge_dist -- so SQLite refuses the query and the handler "
            "answers HTTP 500.  There is no input for which any of the "
            "three can succeed."),
        summary_zh=(
            "Pajek、Gephi 與 UCINet 三個匯出功能都從 ZZ_SN_NETWORK 讀取網絡"
            "的邊，並向這張表要一個叫 c_node_dist 的欄位。ZZ_SN_NETWORK 沒有"
            "這個欄位——它每一條邊帶的距離叫 c_edge_dist——所以 SQLite 直接"
            "拒絕這個查詢，處理程式回傳 HTTP 500。無論輸入什麼，這三個按鈕都"
            "不可能成功。"),
        evidence=(
            "Run a Networks query for a person with kin at depth 1, then "
            "press Pajek, Gephi or UCINet: each answers HTTP 500 "
            "'Database error: no such column: c_node_dist'.  The three "
            "node queries in the same handlers read c_node_dist from "
            "ZZ_SP_NETWORK, which does have it; only the edge queries "
            "against ZZ_SN_NETWORK are wrong.  Confirmed against the "
            "shipped database with PRAGMA table_info: ZZ_SN_NETWORK's 89 "
            "columns include c_edge_dist and not c_node_dist."),
        evidence_zh=(
            "先為一位在距離 1 以內有親屬的人物執行社會網絡查詢，再按下 "
            "Pajek、Gephi 或 UCINet：三者都回傳 HTTP 500「Database error: "
            "no such column: c_node_dist」。同一批處理程式裡的節點查詢是向 "
            "ZZ_SP_NETWORK 要 c_node_dist，那張表確實有；出錯的只有對 "
            "ZZ_SN_NETWORK 的邊查詢。以 PRAGMA table_info 在釋出的資料庫上"
            "確認：ZZ_SN_NETWORK 的 89 個欄位裡有 c_edge_dist，沒有 "
            "c_node_dist。"),
        impact=(
            "Three of the seven export formats on the form whose entire "
            "purpose is social-network analysis cannot be used at all.  "
            "Anyone wanting to take a CBDB network into Pajek, Gephi or "
            "UCINet has to go through the Kinship or Association Pairs "
            "form instead, where the same three formats work.  The "
            "defect predates the 2026-09-07 per-form scratch tables: the "
            "shared ZZ_SOCIAL_NETWORK these tables replaced did not have "
            "c_node_dist either, so these buttons have never worked and "
            "no test had pressed them."),
        impact_zh=(
            "在一個以社會網絡分析為全部目的的表單上，七種匯出格式裡有三種"
            "完全不能用。想把 CBDB 的網絡帶進 Pajek、Gephi 或 UCINet 的人，"
            "只能改走親屬關係或人物配對表單——同樣的三種格式在那裡是正常的。"
            "這個問題比 2026-09-07 的「每個表單自有暫存表」更早：被取代的共用"
            "表 ZZ_SOCIAL_NETWORK 同樣沒有 c_node_dist，也就是說這三個按鈕"
            "從來沒有正常運作過，只是先前沒有任何測試按下它們。"),
        fix=(
            "In networks_form_backend.go, change the three edge queries "
            "to select c_edge_dist (the column ZZ_SN_NETWORK actually "
            "has) rather than c_node_dist, or join the node distance in "
            "from ZZ_SP_NETWORK if edge distance is not what the colour "
            "scale is meant to express.  Both readings are defensible "
            "and the code cannot say which was intended, which is why "
            "this is reported rather than patched here."),
        fix_zh=(
            "在 networks_form_backend.go 裡，把這三個邊查詢改成選取 "
            "c_edge_dist（ZZ_SN_NETWORK 真正擁有的欄位），或者若配色其實要"
            "表達的是節點距離，就從 ZZ_SP_NETWORK 併入。兩種解讀都說得通，"
            "程式本身無法判斷原意，因此這裡只報告而不逕行修改。"),
        steps=(
            "Open the Networks form (/LookAtNetworks) and set a person "
            "who has relatives.",
            "Press Run with the smallest distances (maxLoop 1, "
            "maxNodeDist 1) so a graph comes back.",
            "Press Pajek. The response is HTTP 500 'Database error: no "
            "such column: c_node_dist'.",
            "The same happens for Gephi and for UCINet.  Export Results, "
            "GIS, KML and Neo4j on the same form all work.",
        ),
        steps_zh=(
            "開啟社會網絡表單（/LookAtNetworks），設定一位有親屬的人物。",
            "以最小的距離參數（maxLoop 1、maxNodeDist 1）按下執行，讓查詢"
            "回傳一個圖。",
            "按下 Pajek，回應是 HTTP 500「Database error: no such column: "
            "c_node_dist」。",
            "Gephi 與 UCINet 也一樣。同一表單上的匯出結果、GIS、KML 與 "
            "Neo4j 都正常。",
        ),
        # The three edge queries that ask ZZ_SN_NETWORK for c_node_dist
        # (GUESS/Gephi, UCINet, Pajek), and the table's own declaration.
        source=("Code/networks_form_backend.go:2089",
                "Code/networks_form_backend.go:2212",
                "Code/networks_form_backend.go:2337",
                "Code/networks_form_backend.go:419"),
        tests=("test_an_export_produces_a_well_formed_file",
               "test_an_export_is_repeatable"),
    ),
    Defect(
        key="CBDB-D-009",
        priority="P2",
        severity="high",
        origin="software",
        title="The Associations form's Neo4j export always fails",
        title_zh="社會關係表單的 Neo4j 匯出永遠失敗",
        area="Associations form (/LookAtAssociations) — Neo4j",
        area_zh="社會關係表單（/LookAtAssociations）——Neo4j",
        summary=(
            "Building the Neo4j files reads ADDR_CODES and scans "
            "c_admin_type into a Go int.  In the shipped database that "
            "column is text: its values are administrative-type names "
            "like 'State', 'Shengshi' and '[Unknown]', in all 30,100 "
            "rows.  The scan fails on the first address, the handler "
            "gives up, and the response is HTTP 500."),
        summary_zh=(
            "產生 Neo4j 檔案時會讀取 ADDR_CODES，並把 c_admin_type 掃描成 "
            "Go 的 int。但在釋出的資料庫裡這個欄位是文字：全部 30,100 列的"
            "內容都是行政層級的名稱，例如「State」、「Shengshi」、"
            "「[Unknown]」。第一筆地址就掃描失敗，處理程式放棄，回傳 "
            "HTTP 500。"),
        evidence=(
            "Run any Associations query and press Neo4j: HTTP 500 'Neo4j "
            "export error: scan addrRow: sql: Scan error on column index "
            "3'.  Column index 3 is c_admin_type.  In the shipped "
            "database `SELECT DISTINCT typeof(c_admin_type) FROM "
            "ADDR_CODES` returns only 'text', and the schema declares it "
            "varchar(255) -- so no data refresh will make the scan "
            "succeed.  The same export on five other forms reads "
            "ADDR_CODES without asking for this column and works."),
        evidence_zh=(
            "執行任何社會關係查詢後按下 Neo4j：HTTP 500「Neo4j export "
            "error: scan addrRow: sql: Scan error on column index 3」。"
            "索引 3 就是 c_admin_type。在釋出的資料庫上執行 `SELECT "
            "DISTINCT typeof(c_admin_type) FROM ADDR_CODES` 只會得到 "
            "'text'，結構定義也是 varchar(255)——換言之，再怎麼更新資料，"
            "這個掃描都不會成功。其他五個表單的同一種匯出並沒有要這個欄位，"
            "因此正常運作。"),
        impact=(
            "Association networks cannot be taken into Neo4j at all.  "
            "The Associations form's other three exports work, so the "
            "data is reachable another way, but the button a user "
            "presses for this reports a server error every time."),
        impact_zh=(
            "社會關係網絡完全無法匯入 Neo4j。這個表單的其他三種匯出正常，"
            "資料仍有別的取得方式，但使用者為此按下的那個按鈕每次都以伺服器"
            "錯誤收場。"),
        fix=(
            "Scan c_admin_type into a string (and, if a number is wanted "
            "downstream, resolve it through ADDR_CODES' own type table "
            "rather than assuming the column is numeric).  Worth "
            "checking every other Scan against ADDR_CODES in the same "
            "pass: this column's name reads like a code and its contents "
            "are not one."),
        fix_zh=(
            "把 c_admin_type 掃描成字串；若下游確實需要數字，應透過 "
            "ADDR_CODES 自己的類型表換算，而不是假設這個欄位是數值。建議"
            "同時檢查其他所有對 ADDR_CODES 的 Scan：這個欄位的名字看起來"
            "像代碼，內容卻不是。"),
        steps=(
            "Open the Associations form (/LookAtAssociations) and pick "
            "any association code with a handful of records.",
            "Press Query; the grid fills.",
            "Press Neo4j. The response is HTTP 500 'Neo4j export error: "
            "scan addrRow'.",
        ),
        steps_zh=(
            "開啟社會關係表單（/LookAtAssociations），選一個記錄不多的關係"
            "代碼。",
            "按下查詢，格線填入結果。",
            "按下 Neo4j，回應是 HTTP 500「Neo4j export error: scan "
            "addrRow」。",
        ),
        source=("Code/associations_form_backend.go:1384",
                "Code/associations_form_backend.go:1395"),
        tests=("test_an_export_produces_a_well_formed_file",
               "test_an_export_is_repeatable"),
    ),
    Defect(
        key="CBDB-D-007",
        priority="P0",
        severity="medium",
        origin="software",
        title="Two KML exports produce a file no mapping tool will open",
        title_zh="兩個 KML 匯出產生的檔案，任何地圖軟體都打不開",
        area="Entry form and Places form — KML",
        area_zh="入仕表單與地點表單——KML",
        summary=(
            "The Entry and Places KML writers open the file with "
            "`<?xml version=\"1.0\" encoding=\"UTF-8\">` -- closing the "
            "XML declaration with `>` instead of `?>`.  That is not "
            "well-formed XML, so every reader rejects the entire file at "
            "the first line.  The application reports success and the "
            "download completes normally."),
        summary_zh=(
            "入仕表單與地點表單的 KML 寫出程式，檔案開頭寫成 "
            "`<?xml version=\"1.0\" encoding=\"UTF-8\">`——XML 宣告的結尾用 "
            "`>` 而不是 `?>`。這不是合法的 XML，任何讀取程式都會在第一行就"
            "整檔拒絕。而程式端顯示成功，下載也完全正常。"),
        evidence=(
            "Query either form, press KML, and the file begins "
            "`<?xml version=\"1.0\" encoding=\"UTF-8\">`.  Python's XML "
            "parser reports 'unclosed token: line 1, column 0'; Google "
            "Earth and QGIS refuse the file.  Five other KML writers in "
            "the same build (associations, kinship, networks, group data "
            "and office) close the declaration correctly, which is what "
            "makes this a slip rather than a decision -- and what makes "
            "it findable in the source without running anything: "
            "entry_form_backend.go:1002 and places_form_backend.go:763."),
        evidence_zh=(
            "在任一表單查詢後按下 KML，檔案開頭是 "
            "`<?xml version=\"1.0\" encoding=\"UTF-8\">`。Python 的 XML "
            "解析器報「unclosed token: line 1, column 0」；Google Earth 與 "
            "QGIS 直接拒絕此檔。同一版程式裡另外五處 KML 寫出（社會關係、"
            "親屬關係、社會網絡、群體資料、官職）都正確地收尾，可見這是筆誤"
            "而非設計——也因此不必執行程式就能在原始碼裡找到："
            "entry_form_backend.go:1002 與 places_form_backend.go:763。"),
        impact=(
            "A historian exports the geography of an entry route or a "
            "set of places, opens it in Google Earth, and is told the "
            "file is corrupt.  Nothing in the application suggests "
            "anything went wrong, so the natural conclusion is that the "
            "mapping tool is at fault or the data is bad.  The same two "
            "forms' GIS (.tab) exports are unaffected, which is the "
            "workaround."),
        impact_zh=(
            "研究者匯出某條入仕途徑或一組地點的地理資料，在 Google Earth 裡"
            "打開，卻被告知檔案損壞。程式端沒有任何跡象顯示出錯，於是最自然"
            "的結論會是地圖軟體有問題或資料有問題。同兩個表單的 GIS（.tab）"
            "匯出不受影響，可作為替代做法。"),
        fix=(
            "Write `?>` in both places.  Worth adding one shared helper "
            "that emits the KML preamble, since there are now seven "
            "copies of it and two of them were wrong."),
        fix_zh=(
            "把這兩處補上 `?>`。並建議抽出一個共用的函式來輸出 KML 檔頭："
            "目前這段序言已經有七份副本，其中兩份是錯的。"),
        steps=(
            "Open the Entry form (/LookAtEntry), pick an entry code and "
            "press Query.",
            "Press KML and save the file.",
            "Open it in Google Earth, QGIS, or any XML parser: the file "
            "is rejected at line 1.",
            "The Places form (/LookAtPlaces) behaves identically.",
        ),
        steps_zh=(
            "開啟入仕表單（/LookAtEntry），選一個入仕代碼並按下查詢。",
            "按下 KML 並儲存檔案。",
            "用 Google Earth、QGIS 或任何 XML 解析器開啟：檔案在第 1 行就"
            "被拒絕。",
            "地點表單（/LookAtPlaces）的情況完全相同。",
        ),
        source=("Code/entry_form_backend.go:1002",
                "Code/places_form_backend.go:763"),
        tests=("test_an_export_produces_a_well_formed_file",
               "test_every_kml_writer_closes_its_xml_declaration"),
    ),
    Defect(
        key="CBDB-D-002",
        priority="P2",
        severity="medium",
        origin="software",
        title="The Query Builder offers 30 columns that do not exist",
        title_zh="查詢建構器提供了 30 個並不存在的欄位",
        area="Query Builder (/QBE)",
        area_zh="查詢建構器（/QBE）",
        summary=(
            "Data/qbe_schema.json lists 30 columns across 8 views that "
            "Data/cbdb.db does not have under those names.  Each of the "
            "eight views selects the same column name twice -- "
            "KIN_DATA.c_personid and View_PeopleData.c_personid, say -- "
            "and SQLite resolves that collision by renaming the second "
            "one `c_personid:1`.  The whitelist generator reads the "
            "CREATE VIEW text and does not model that rename, so it "
            "offers a name the database does not answer to.  "
            "ValidateGridState checks a request against the JSON alone, "
            "so each one passes validation and then fails in SQLite."),
        summary_zh=(
            "Data/qbe_schema.json 列出 8 個檢視表下的 30 個欄位，而 "
            "Data/cbdb.db 並沒有以這些名稱存在的欄位。這 8 個檢視表都各自"
            "把同一個欄位名選了兩次——例如 KIN_DATA.c_personid 與 "
            "View_PeopleData.c_personid——SQLite 解決撞名的方式是把後者改名"
            "為 `c_personid:1`。白名單產生程式是讀 CREATE VIEW 的文字，並未"
            "模擬這個改名，於是提供了資料庫並不認得的名稱。"
            "ValidateGridState 只拿 JSON 驗證請求，所以這些欄位都能通過"
            "驗證，最後在 SQLite 執行時才失敗。"),
        evidence=(
            "Comparing the whitelist against PRAGMA table_info for all "
            "102 offered tables finds 30 absent columns, in "
            "View_BiogInstAddrData, View_BiogInstData, "
            "View_BiogSourceData, View_BiogTextData, View_Entry, "
            "View_EventData, View_KinAddr and View_PostingOfficeData.  "
            "Every one of the 30 has a sibling in the same view with "
            "':1' appended -- a one-to-one correspondence, which is what "
            "identifies duplicate-name resolution as the mechanism "
            "rather than a stale file.  Selecting any of them through "
            "/api/qbe/run answers HTTP 500 'Query failed: no such "
            "column'.  Four of them are the first column their view "
            "offers, so the failure is one click away."),
        evidence_zh=(
            "以 PRAGMA table_info 比對白名單中全部 102 張表，找出 30 個不存"
            "在的欄位，分布於 View_BiogInstAddrData、View_BiogInstData、"
            "View_BiogSourceData、View_BiogTextData、View_Entry、"
            "View_EventData、View_KinAddr 與 View_PostingOfficeData。"
            "這 30 個欄位每一個都在同一個檢視表裡有一個加了「:1」的兄弟"
            "欄位——一對一完全對應，這正說明機制是撞名改名，而不是檔案過期。"
            "透過 /api/qbe/run 選用其中任一個，都會得到 HTTP 500"
            "「Query failed: no such column」。其中四個還正好是該檢視表清單"
            "中的第一個欄位，使用者點一下就會踩到。"),
        impact=(
            "A user building a query picks a column from the grid's own "
            "dropdown and gets a server error with no indication that "
            "the column was never available.  The eight affected views "
            "are otherwise usable.  Because the mechanism is duplicate "
            "output names rather than a stale file, regenerating "
            "qbe_schema.json from the same CREATE VIEW text -- which is "
            "what was done for the 2026-09-07 build -- does not change "
            "anything: the JSON and the SQL agree with each other and "
            "both disagree with SQLite."),
        impact_zh=(
            "使用者從查詢建構器自己提供的下拉選單中挑了一個欄位，換來的卻是"
            "伺服器錯誤，而且完全看不出這個欄位其實從一開始就不可用。"
            "這 8 個檢視表的其他欄位仍可正常使用。由於根本原因是輸出欄位"
            "撞名、而不是檔案過期，因此再從同一份 CREATE VIEW 文字重新產生 "
            "qbe_schema.json（2026-09-07 版就是這麼做的）並不會有任何改變："
            "JSON 與 SQL 彼此一致，卻都與 SQLite 不一致。"),
        fix=(
            "Two independent halves, and the first is the real fix.  "
            "(1) Give the eight views unambiguous output names -- alias "
            "the second occurrence in the CREATE VIEW, in "
            "CBDBSetUpCode/CBDB_AdditionalTablesViewsIndices.sql -- so "
            "there is nothing for SQLite to rename.  A column called "
            "`c_personid:1` cannot be selected by any client, so this is "
            "worth doing whatever the Query Builder does.  (2) Generate "
            "qbe_schema.json from PRAGMA table_info against the built "
            "database rather than by parsing CREATE VIEW text, so the "
            "whitelist cannot describe columns the database does not "
            "have.  The build already ships a Go test that would have "
            "caught this -- Code/qbe_schema_test.go, added for this very "
            "defect, which does read PRAGMA table_info -- but it skips "
            "itself unless run from the project root and had not been "
            "run against this database."),
        fix_zh=(
            "有兩個彼此獨立的部分，而第一個才是真正的修法。"
            "(1) 讓這 8 個檢視表的輸出欄位名稱不再撞名——在 "
            "CBDBSetUpCode/CBDB_AdditionalTablesViewsIndices.sql 的 "
            "CREATE VIEW 中為重複出現的那一個加上別名——這樣 SQLite 就沒有"
            "東西需要改名。名為 `c_personid:1` 的欄位任何客戶端都無法選取，"
            "所以無論查詢建構器怎麼做，這件事都值得做。"
            "(2) 改由對已建好的資料庫執行 PRAGMA table_info 來產生 "
            "qbe_schema.json，而不是解析 CREATE VIEW 的文字，白名單就不可能"
            "描述出資料庫沒有的欄位。這一版其實已經附了一個能抓到這個問題的 "
            "Go 測試——Code/qbe_schema_test.go，正是為這個缺陷而寫，而且確實"
            "使用 PRAGMA table_info——但它在非專案根目錄執行時會自行跳過，"
            "而且並未對這個資料庫執行過。"),
        steps=(
            "Open the Query Builder (/QBE).",
            "Add the view `View_Entry` to the grid.",
            "From its column list — the one the page itself supplies — "
            "pick `c_personid`.",
            "Press Run. The result is HTTP 500: 'Query failed: no such "
            "column: v.c_personid'.",
            "In the shipped database, `PRAGMA table_info(View_Entry)` "
            "lists `c_personid:1` and no `c_personid`.",
            "The same happens for 30 columns across 8 views; the full "
            "list is pinned in tests/test_qbe.py.",
        ),
        steps_zh=(
            "開啟查詢建構器（/QBE）。",
            "把檢視表 `View_Entry` 加入查詢格線。",
            "從欄位清單——也就是頁面自己提供的那一份——選擇 `c_personid`。",
            "按下執行，得到 HTTP 500：「Query failed: no such column: "
            "v.c_personid」。",
            "在釋出的資料庫上執行 `PRAGMA table_info(View_Entry)`，看到的是 "
            "`c_personid:1`，沒有 `c_personid`。",
            "8 個檢視表下共 30 個欄位都是如此；完整清單釘在 "
            "tests/test_qbe.py 中。",
        ),
        source=("Code/qbe_schema.go:89", "Code/qbe_schema_test.go",
                "Data/gen_qbe_schema.py", "Data/qbe_schema.json",
                "CBDBSetUpCode/CBDB_AdditionalTablesViewsIndices.sql"),
        tests=("test_every_offered_column_exists_in_the_database",
               "test_a_phantom_column_gives_the_user_a_server_error",
               "test_every_offered_table_can_actually_be_queried",
               "test_no_view_resolves_two_columns_to_the_same_name"),
    ),
    Defect(
        key="CBDB-D-010",
        priority="P0",
        severity="medium",
        origin="software",
        title="Two browser tabs, or two copies of the application, share "
              "one result",
        title_zh="兩個瀏覽器分頁、或同時開兩份程式，會共用同一份查詢結果",
        area="Every form with a working list or a scratch result",
        area_zh="所有具備工作清單或暫存結果的表單",
        summary=(
            "Nothing in a request identifies the tab or the session it "
            "came from.  The scratch tables a query fills and an export "
            "reads are one set per database, so a query run in one tab "
            "replaces what another tab's export is about to read.  "
            "Worse, main.go takes no single-instance lock and defaults "
            "to port 0, so cbdb.exe can be launched twice against the "
            "same Data/cbdb.db; the in-process mutexes then protect "
            "nothing, because the two processes have their own."),
        summary_zh=(
            "請求裡沒有任何東西能辨識它來自哪個分頁或哪個工作階段。查詢寫入、"
            "匯出讀取的暫存表，每個資料庫只有一組，因此在一個分頁執行查詢，"
            "就會覆蓋另一個分頁即將匯出的內容。更嚴重的是，main.go 沒有取得"
            "單一實例鎖，而且預設使用 port 0，因此 cbdb.exe 可以對同一個 "
            "Data/cbdb.db 啟動兩次；此時程式內的 mutex 完全失去作用，因為兩"
            "個行程各有自己的一份。"),
        evidence=(
            "This is the CBDB-Desktop developers' own finding from the "
            "2026-09-07 remediation session, logged there as open and "
            "confirmed here from the shipped source: the per-form "
            "scratch tables added for CBDB-D-004 remove cross-*form* "
            "sharing and leave cross-*request* sharing exactly as it "
            "was.  Two requests to the same endpoint are "
            "indistinguishable to the handler, and a grep of main.go "
            "finds no mutex, lock file, PID file or port pinning."),
        evidence_zh=(
            "這是 CBDB-Desktop 開發者在 2026-09-07 修復工作中自己找到的問題，"
            "當時記錄為未解決，這裡再從釋出的原始碼確認：為 CBDB-D-004 增加"
            "的「每個表單自有暫存表」消除了*跨表單*共用，但*跨請求*共用完全"
            "沒有改變。對處理程式而言，兩個打到同一端點的請求無從區分；"
            "而在 main.go 中搜尋，找不到任何 mutex、鎖檔、PID 檔或固定通訊埠"
            "的處理。"),
        impact=(
            "A user with the Associations form open in two tabs -- an "
            "ordinary way to compare two queries -- can export the wrong "
            "one, with no error.  The two-process case is worse than "
            "overwriting: SQLite's WAL mode permits both to write, so "
            "the two can interleave writes into the same scratch tables "
            "and produce a result that is neither query's answer."),
        impact_zh=(
            "使用者在兩個分頁裡開著社會關係表單——這是比較兩個查詢再自然不過"
            "的做法——就可能匯出錯的那一份，而且沒有任何錯誤提示。兩個行程的"
            "情況比覆蓋更糟：SQLite 的 WAL 模式允許兩者同時寫入，於是兩邊的"
            "寫入可能交錯進同一組暫存表，產生的結果不屬於任何一次查詢。"),
        fix=(
            "Namespace the scratch state per session rather than per "
            "form: a session id in a cookie, and either per-session "
            "table names or a session column in each scratch table.  "
            "Separately, and much cheaper, refuse to start a second "
            "instance against the same database (a lock file beside "
            "Data/cbdb.db, checked at startup) -- that alone removes the "
            "interleaved-write half of the problem."),
        fix_zh=(
            "把暫存狀態改成依工作階段（session）而非依表單命名空間：在 "
            "cookie 中放一個 session id，並採用依 session 命名的表、或在每張"
            "暫存表中加一個 session 欄位。另外一個便宜得多的做法是：拒絕對"
            "同一個資料庫啟動第二個實例（在 Data/cbdb.db 旁放一個鎖檔，啟動"
            "時檢查）——僅此一項就能消除交錯寫入的那一半問題。"),
        steps=(
            "Open the Associations form in two browser tabs.",
            "In tab A, run a query; the grid fills.",
            "In tab B, run a different query.",
            "Back in tab A, press Export Results: the file describes tab "
            "B's query.",
            "Separately: launch Bin/cbdb.exe twice. Both start, both "
            "open the same Data/cbdb.db, and neither mentions the other.",
        ),
        steps_zh=(
            "在兩個瀏覽器分頁中開啟社會關係表單。",
            "在分頁 A 執行一次查詢，格線填入結果。",
            "在分頁 B 執行另一次不同的查詢。",
            "回到分頁 A 按下匯出結果：檔案的內容是分頁 B 的查詢結果。",
            "另外：把 Bin/cbdb.exe 啟動兩次。兩者都會啟動、都會開啟同一個 "
            "Data/cbdb.db，而且都不會提到對方的存在。",
        ),
        source=("Code/main.go", "Code/associations_form_backend.go:233",
                "Code/networks_form_backend.go:411"),
        tests=("test_a_second_query_replaces_what_the_first_would_export",
               "test_nothing_stops_a_second_instance_opening_the_database"),
    ),
)

DEFECTS: dict[str, Defect] = {defect.key: defect for defect in _DEFECTS}

#: Convenient aliases, so a test can name the defect it demonstrates
#: without repeating an identifier.
BY_NAME: dict[str, Defect] = {
    "qbe-phantom-columns": DEFECTS["CBDB-D-002"],
    "missing-utf8-bom": DEFECTS["CBDB-D-011"],
    "multi-file-download": DEFECTS["CBDB-D-012"],
    "stale-enable-state": DEFECTS["CBDB-D-013"],
    "ignored-empty-selection": DEFECTS["CBDB-D-014"],
    "kml-declaration": DEFECTS["CBDB-D-007"],
    "networks-sna-exports": DEFECTS["CBDB-D-008"],
    "associations-neo4j-export": DEFECTS["CBDB-D-009"],
    "shared-session-state": DEFECTS["CBDB-D-010"],
}

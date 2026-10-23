"""The registry the report is written from -- and nothing else.\n\n"
This module holds one round's findings **for as long as it takes to
write that round's report**.  It is not a record of what this project
has ever found, it is not consulted to decide whether a test may fail,
and it carries nothing from one run to the next.  Each round starts
empty, the round's own evidence fills it, ``reports/generate_report.py``
turns it plus that run's JSON into the English and Chinese reports, and
the next round starts empty again.

Why so narrow.  A registry that persists becomes an expectation: once a
finding is written down, a marker somewhere says "this test may fail
because of entry X", and from then on the suite is measuring the
registry rather than the build.  Two consequences, both paid for here:
a defect quietly stays tolerated long after anyone agreed to tolerate
it, and a *fresh* assessment of a new distribution is impossible
because the agent doing it starts by reading last round's nine
findings.  The git history of this file is the only history worth
having; ``git log -p`` is where to look for it, deliberately not the
working copy.

What replaces it, for the one case where persistence is legitimate --
"we discussed this and agreed to leave it for now" -- is
``cbdb_desktop/waivers.py``: an optional table, outside the suite,
addressed by the **program's own names** (a test function, plus the
parametrisation ids it ran with) because no identifier this suite
invents survives a stateless round.  It is dated, bilingual, printed in
the report, and absent unless someone configures ``CBDB_WAIVERS``.

So a defect is detected the same way it always was -- the test confirms
an exact signature and raises :class:`KnownShippedDefect`, which is an
``AssertionError`` and therefore an ordinary failure with the signature
in its message.  Nothing in this file makes that failure expected.

``PRIORITIES`` and ``ORIGINS`` below are not per-round state: they are
the vocabulary the report is written in, and ``origin`` in particular
decides *who a finding is sent to* -- see AGENTS.md § "Where a defect
comes from".  A problem in the data arriving from the CBDB source is
not one the application developers can fix, and sending it to them
wastes the one channel this project has.
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
    "P2": ("Visible failure — the user's action fails with an error they "
           "see.  Usually a server error; sometimes a page that reports "
           "failure on a request that in fact succeeded.  The band is about "
           "what the user is shown, not about which half of the application "
           "went wrong.",
           "可見的失敗——使用者的操作以他看得到的錯誤收場。多半是伺服器"
           "錯誤，有時則是頁面把一次其實已經成功的請求回報為失敗。這個"
           "級別看的是使用者看到什麼，而不是程式的哪一半出了問題。"),
    "P3": ("Packaging — the released files contain something they should "
           "not, or lack something they should.",
           "封裝問題——釋出的檔案裡含有不該出現的內容，或缺少了應該有的"
           "內容。"),
    "P4": ("Data integrity — a reference in the shipped data does not "
           "resolve.",
           "資料完整性——釋出資料中存在無法解析的參照。"),
    "P5": ("Unreachable feature — the application implements something no "
           "page can ask for.  The band says only that no user can get to "
           "it.  Whether the code behind it is correct is a separate "
           "question with a separate answer, so an unreachable feature that "
           "is also broken is recorded in both places rather than argued "
           "about in one.",
           "無法觸及的功能——程式實作了某項功能，卻沒有任何頁面可以呼叫它。"
           "這個級別只說明「沒有任何使用者到得了」。至於背後的程式碼是否"
           "正確，是另一個問題、也有另一個答案；因此一項既到不了、本身又"
           "有錯的功能會在兩處分別記錄，而不是在同一處爭論該算哪一種。"),
    "P6": ("Wording — a label on a page says the wrong thing, or says it "
           "in the wrong script, in one of the three display languages "
           "(English, Traditional or Simplified Chinese).  Judged against "
           "the CBDB label glossary by fixed rules; nothing the "
           "application computes is affected, but a reader can be misled "
           "about what a control does.",
           "用語問題——頁面上的標籤在三種顯示語言（英文、繁體、簡體中文）"
           "之一說錯了意思，或用錯了字體。依固定規則對照 CBDB 標籤對照表"
           "判定；不影響程式的計算結果，但可能讓讀者誤解控制項的作用。"),
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
    #: One of PRIORITIES.  The ladder is not fixed in length: it gains
    #: a band when a round finds a kind of defect the existing ones would
    #: have to be stretched to cover, because stretching a band is worse
    #: than adding one -- a reader told that P2 means "server error" and
    #: then shown an entry that is not one stops trusting the glossary.
    priority: str
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
    #: Where the defect lives, as ``path:line`` into the build -- or a
    #: bare ``path`` in the one case where that is the whole finding: a
    #: file whose *existence* is the problem, for which a line number
    #: would be noise.  ``test_defect_registry.py`` checks each path
    #: exists and each line is inside its file.
    source: tuple[str, ...] = ()
    tests: tuple[str, ...] = ()      # test names that demonstrate it

    def text(self, field: str, lang: str) -> str:
        """One field in one language, falling back to English."""
        if lang == "zh":
            return getattr(self, f"{field}_zh", "") or getattr(self, field)
        return getattr(self, field)


#: Empty, and empty is the normal state.  A round fills this in while
#: it writes its report -- one :class:`Defect` per finding, in both
#: languages, each citing where it lives in the build and which tests
#: demonstrate it -- and the next round starts from empty again.  See
#: docs/skills/issue-report-maintainer.md for what an entry has to say
#: and what has to be verified before it is written.
#:
#: Filling this in does **not** make any test tolerate a failure.  There
#: is no marker to wire up any more: a finding stays a failure until it
#: is fixed, or until it is waived by agreement in the table described
#: in ``cbdb_desktop/waivers.py``.
_DEFECTS: tuple[Defect, ...] = (
    Defect(
        key="CBDB-D-001",
        priority="P3", severity="high", origin="release",
        title="The Go source shipped in Code/ is not the source of the "
              "shipped cbdb.exe: only office_form_backend.go changed since "
              "20260925, while the binary carries the revisions the notes "
              "describe",
        title_zh="Code/ 中隨附的 Go 原始碼並不是隨附 cbdb.exe 的原始碼：自 "
                 "20260925 以來只有 office_form_backend.go 有變動，而執行檔卻"
                 "已包含修訂說明所描述的修改",
        area="The distribution archive: Code/*.go against cbdb.exe",
        area_zh="發行壓縮檔：Code/*.go 與 cbdb.exe 的對應",
        summary="`cbdb.exe` was rebuilt on 2026-10-20, but every file in "
                "`Code/` except `office_form_backend.go` is byte-identical "
                "to the 20260925 archive (and `CBDBSetUpCode/` is "
                "unchanged, though `CBDBsetup.exe` was rebuilt too).  The "
                "binary contains functions declared nowhere in the shipped "
                "source -- `InlineArgsForDisplay` and `sqlLiteral` (QBE-3), "
                "`PlaceHandler.fillIndexAddresses` (PLC-4), `fmtOptFloat` "
                "(ASP-6) -- and the source still declares "
                "`NetworkHandler.handleRerun` and registers "
                "`/api/networks/rerun`, which the binary no longer has "
                "(NET-4 removed them).  So the published source does not "
                "build the published program, and none of the Go revisions "
                "in the nine notes shipped as source.",
        summary_zh="`cbdb.exe` 於 2026-10-20 重新建置，但 `Code/` 中除了 "
                   "`office_form_backend.go` 之外，每個檔案都與 20260925 的"
                   "壓縮檔逐位元組相同（`CBDBSetUpCode/` 也未變動，儘管 "
                   "`CBDBsetup.exe` 同樣重新建置過）。執行檔中含有隨附原始碼"
                   "裡沒有宣告的函式——`InlineArgsForDisplay` 與 `sqlLiteral`"
                   "（QBE-3）、`PlaceHandler.fillIndexAddresses`（PLC-4）、"
                   "`fmtOptFloat`（ASP-6）——而原始碼仍宣告 "
                   "`NetworkHandler.handleRerun` 並註冊 `/api/networks/rerun`，"
                   "執行檔中卻已沒有這些（NET-4 已將其移除）。因此公開的原始碼"
                   "建置不出公開的程式，九份說明中的 Go 修訂沒有一項以原始碼"
                   "形式隨附。",
        evidence="`test_the_shipped_source_is_the_source_of_the_shipped_"
                 "binary` compares the `main.` function names in cbdb.exe's "
                 "function-name table with the `func` declarations in "
                 "`Code/*.go` (compiler wrappers and functions the linker "
                 "drops excluded, by rules tested on written-down cases; "
                 "the 20260925 archive compares clean).  Only in the "
                 "binary: InlineArgsForDisplay, PlaceHandler."
                 "fillIndexAddresses, fmtOptFloat, sqlLiteral.  Only in the "
                 "source: NetworkHandler.handleRerun.  Behaviourally, "
                 "`test_every_registered_api_route_still_exists` finds "
                 "`/api/networks/rerun` registered in the source and "
                 "answering 404 from the binary, and "
                 "`test_every_api_endpoint_the_build_routes_has_a_page_that_"
                 "calls_it` finds it routed in the source and called by no "
                 "page.",
        evidence_zh="`test_the_shipped_source_is_the_source_of_the_shipped_"
                    "binary` 比對 cbdb.exe 函式名稱表中的 `main.` 函式與 "
                    "`Code/*.go` 中的 `func` 宣告（排除編譯器產生的包裝函式與"
                    "連結器捨棄的函式，規則以寫定答案的案例測試；20260925 的"
                    "壓縮檔比對結果一致）。只在執行檔中：InlineArgsForDisplay、"
                    "PlaceHandler.fillIndexAddresses、fmtOptFloat、"
                    "sqlLiteral。只在原始碼中：NetworkHandler.handleRerun。"
                    "從行為上看，`test_every_registered_api_route_still_exists` "
                    "發現 `/api/networks/rerun` 在原始碼中有註冊、執行檔卻回應 "
                    "404；`test_every_api_endpoint_the_build_routes_has_a_page_"
                    "that_calls_it` 發現它在原始碼中有路由、卻沒有任何頁面呼叫。",
        impact="Anyone who reads, audits or rebuilds from the shipped "
               "source gets last month's program.  For this test suite it "
               "means every check that reads the Go source as data -- the "
               "route inventory, scratch-table ownership, the source lines "
               "cited in this report for Go code -- describes the previous "
               "build wherever the two differ; the findings here that "
               "matter were therefore established by driving the binary.",
        impact_zh="任何閱讀、稽核或以隨附原始碼重新建置的人，得到的都是上個月"
                  "的程式。對本測試套件而言，凡是把 Go 原始碼當作資料讀取的"
                  "檢查——路由清單、暫存表歸屬、本報告中引用的 Go 程式行——在"
                  "兩者有差異之處描述的都是前一個版本；因此本報告中重要的發現"
                  "都是透過實際操作執行檔確立的。",
        fix="Ship the `Code/` (and `CBDBSetUpCode/`) the binaries were "
            "built from, and make copying it part of the release step that "
            "builds them.",
        fix_zh="隨附建置執行檔時實際使用的 `Code/`（與 `CBDBSetUpCode/`），並把"
               "複製原始碼列為建置執行檔的發行步驟之一。",
        steps=(
            "Open Code/networks_form_backend.go from the archive: it "
            "registers /api/networks/rerun (line 326).",
            "Run cbdb.exe and send any request to /api/networks/rerun: "
            "404.",
        ),
        steps_zh=(
            "打開壓縮檔中的 Code/networks_form_backend.go：它註冊了 "
            "/api/networks/rerun（第 326 行）。",
            "執行 cbdb.exe，對 /api/networks/rerun 發出任何請求：回應 404。",
        ),
        source=(
            "Code/networks_form_backend.go:326 (registers "
            "/api/networks/rerun, absent from the binary)",
            "Code/networks_form_backend.go:823 (handleRerun)",
        ),
        tests=("test_the_shipped_source_is_the_source_of_the_shipped_binary",
               "test_every_registered_api_route_still_exists",
               "test_every_api_endpoint_the_build_routes_has_a_page_that_"
               "calls_it"),
    ),
    Defect(
        key="CBDB-D-002",
        priority="P2", severity="high", origin="software",
        title="Group Data throws whenever no query has run: importing a "
              "list reports \"Import error\" on an import that succeeded, "
              "Recall IDs reports an error, and Clear does not clear",
        title_zh="群體資料表單在尚未執行查詢時會拋出錯誤：匯入名單明明成功卻"
                 "顯示「Import error」，召回 ID 也顯示錯誤，而「清除」無法清除",
        area="Group Data form (/LookAtGroupData), its page script",
        area_zh="群體資料表單（/LookAtGroupData）的頁面程式碼",
        summary="`updateRunButton()` decides which buttons to enable.  Its "
                "first half guards against there being no result yet "
                "(`queryData !== null && ...`); six lines added in this "
                "build, which enable the per-dataset GIS checkboxes, read "
                "`queryData.statusRecords`, `.officeRecords` and so on "
                "without that guard.  `queryData` is `null` when the page "
                "loads and again after Clear, so every call before the first "
                "query -- on load, after Import, after Recall IDs, on "
                "ticking a category, and inside Clear -- throws "
                "`TypeError: Cannot read properties of null (reading "
                "'statusRecords')` and stops the function that called it "
                "part-way.",
        summary_zh="`updateRunButton()` 負責決定哪些按鈕可用。它的前半段有防範"
                   "尚無結果的情況（`queryData !== null && ...`）；但這個版本"
                   "新增、用來啟用各資料集 GIS 勾選框的六行程式，讀取 "
                   "`queryData.statusRecords`、`.officeRecords` 等時沒有這個"
                   "防範。頁面載入時以及按「清除」之後，`queryData` 都是 "
                   "`null`，因此在第一次查詢之前的每一次呼叫——載入時、匯入後、"
                   "召回 ID 後、勾選類別時，以及在「清除」之中——都會拋出 "
                   "`TypeError: Cannot read properties of null (reading "
                   "'statusRecords')`，並讓呼叫它的函式中途停止。",
        evidence="Driven in Chromium.  "
                 "`test_every_page_the_build_serves_loads_without_throwing`: "
                 "the page logs exactly that error on load.  "
                 "`test_group_data_can_be_used_before_its_first_query` "
                 "imports a one-person file through the page's own file "
                 "input: the server answers 200 and loads the person, and "
                 "the page shows \"Import error: Cannot read properties of "
                 "null (reading 'statusRecords')\" with Clear still disabled "
                 "and Import still enabled.  The six lines are absent from "
                 "the 20260925 template and no revision note mentions them.",
        evidence_zh="以 Chromium 實際操作。"
                    "`test_every_page_the_build_serves_loads_without_throwing`："
                    "頁面載入時就記錄了這個錯誤。"
                    "`test_group_data_can_be_used_before_its_first_query` 透過"
                    "頁面自己的檔案輸入匯入一個只含一人的檔案：伺服器回應 200 "
                    "並載入了該人物，頁面卻顯示「Import error: Cannot read "
                    "properties of null (reading 'statusRecords')」，「清除」"
                    "仍不可用，「匯入」仍可用。這六行在 20260925 的模板中並不"
                    "存在，也沒有任何修訂說明提到它們。",
        impact="The first thing a user does on Group Data -- import or "
               "recall a list of people -- reports a failure that did not "
               "happen, and leaves the buttons in the wrong state; Clear "
               "then fails silently, so the form cannot be reset without "
               "reloading it.  A query can still be run, so the form is "
               "usable by someone who ignores the error, which is not "
               "something to ask of a user.",
        impact_zh="使用者在群體資料表單上做的第一件事——匯入或召回一份人物名單——"
                  "會回報一個並未發生的失敗，並讓按鈕停在錯誤的狀態；之後"
                  "「清除」也會無聲地失敗，表單無法在不重新載入的情況下重設。"
                  "查詢仍然可以執行，所以忽略錯誤訊息的人還是能用這個表單——"
                  "但這不是可以要求使用者做的事。",
        fix="Guard the six lines like the ones above them (`queryData && "
            "...`), or compute them from the `hasData` already in scope.",
        fix_zh="像上面那幾行一樣防範這六行（`queryData && ...`），或改用作用域內"
               "已有的 `hasData` 來計算。",
        steps=(
            "Open Look At Group Data.",
            "Import from File a text file holding one person ID.",
            "The page says \"Import error: Cannot read properties of null "
            "(reading 'statusRecords')\"; Clear stays disabled.",
        ),
        steps_zh=(
            "開啟群體資料表單（Look At Group Data）。",
            "以「從檔案匯入」匯入一個只含一個人物 ID 的文字檔。",
            "頁面顯示「Import error: Cannot read properties of null (reading "
            "'statusRecords')」；「清除」仍不可用。",
        ),
        source=(
            "Templates/group_data/index.html:365 (chkGisStatus, first of "
            "the six unguarded lines)",
            "Templates/group_data/index.html:161 (queryData = null)",
            "Templates/group_data/index.html:479 (clearPeople resets it to "
            "null and calls updateRunButton)",
        ),
        tests=("test_every_page_the_build_serves_loads_without_throwing",
               "test_group_data_can_be_used_before_its_first_query"),
    ),
    Defect(
        key="CBDB-D-003",
        priority="P5", severity="low", origin="software",
        title="The Places form's Pajek, Gephi/GUESS and UCINet exports "
              "are implemented and no control on its page calls them",
        title_zh="地點表單的 Pajek、Gephi/GUESS 與 UCINet 匯出已經實作，但"
                 "頁面上沒有任何控制項會呼叫它們",
        area="Places form (/LookAtPlace): /api/places/export-pajek, "
             "/api/places/export-gephi, /api/places/export-ucinet",
        area_zh="地點表單（/LookAtPlace）的 Pajek、Gephi/GUESS 與 UCINet 三種網絡匯出",
        summary="The Places page defines `exportPajek`, `exportGephi` and "
                "`exportUCINet`, each posting the query result to its "
                "endpoint and downloading the answer, and the three "
                "handlers are routed and answer.  Nothing on the page "
                "invokes any of the three functions: its buttons are Run "
                "Query, Store Person IDs, Export Query Results, Save to KML, "
                "Save to GIS and Export Neo4j CSVs, and no listener or "
                "load-time code calls them either.  The developers' "
                "2026-10-15 revision note (PLC-6) says this is deliberate: "
                "the functions and routes are \"kept, although the form has "
                "no buttons for them\", because a Places query builds no "
                "social or kinship network and these exports would be "
                "fragmentary, in case the steering committee later wants "
                "the buttons.  Filed so that decision is visible in the "
                "report; it is the maintainer's to accept.",
        summary_zh="地點表單頁面定義了 `exportPajek`、`exportGephi` 與 "
                   "`exportUCINet`，各自把查詢結果送到對應的端點並下載回應，"
                   "三個後端處理函式也都有路由、能夠回應。但頁面上沒有任何"
                   "東西會呼叫這三個函式：它的按鈕只有執行查詢、儲存人物ID、"
                   "導出查詢結果、保存到KML、保存到GIS 與導出Neo4j CSV，也沒有"
                   "任何事件監聽或載入時執行的程式碼呼叫它們。開發者 2026-10-15 "
                   "的修訂說明（PLC-6）表示這是刻意的：雖然表單上沒有按鈕，"
                   "這些函式與路由仍「保留」，因為地點查詢不建立社會或親屬網絡，"
                   "這些匯出只會產生片段的網絡；保留是為了日後指導委員會若要"
                   "加上按鈕時備用。列入報告是為了讓這個決定可見；是否接受由"
                   "維護者決定。",
        evidence="`test_every_endpoint_a_page_calls_is_reachable_from_"
                 "something_a_user_does` walks each page's call graph from "
                 "everything that can run -- buttons, every inline "
                 "`on...=` handler, load-time code, listeners registered "
                 "by name, and the `window.X` callbacks popups call back "
                 "into.  Across every page the build ships, these three "
                 "are the only endpoints a page mentions that the walk "
                 "never reaches.  The PLC-6 note confirms the intent and "
                 "lists, as an open item, adding a comment above "
                 "`exportUCINet()` saying they are kept on purpose.",
        evidence_zh="`test_every_endpoint_a_page_calls_is_reachable_from_"
                    "something_a_user_does` 從每個頁面上所有可能執行的地方"
                    "出發——按鈕、每個行內 `on...=` 處理函式、載入時執行的"
                    "程式碼、以名稱註冊的事件監聽，以及彈出視窗回呼的 "
                    "`window.X`——沿著頁面的呼叫關係走訪。在這個版本的所有"
                    "頁面中，只有這三個端點是頁面提到、卻走訪不到的。PLC-6 "
                    "說明證實這是刻意的，並把「在 `exportUCINet()` 上方加註解"
                    "說明刻意保留」列為待辦事項。",
        impact="A historian working in Places cannot produce the Pajek, "
               "Gephi or UCINet files the other network forms offer, and "
               "there is nothing on the page to say the feature exists.  "
               "No wrong answer is given; the feature is simply "
               "unreachable, by the developers' choice.",
        impact_zh="在地點表單中工作的研究者，無法產生其他網絡類表單都能產生的 "
                  "Pajek、Gephi 或 UCINet 檔案，頁面上也沒有任何跡象顯示這項"
                  "功能存在。這不會給出錯誤的結果，只是功能到不了——而這是開發者"
                  "的選擇。",
        fix="Either accept it as designed (a waiver keyed on the test "
            "above records that), or add the three buttons, or delete the "
            "functions and handlers.  The comment PLC-6 proposes would "
            "tell a reader of the page why they are there.",
        fix_zh="可以接受為既定設計（以上述測試為鍵登錄一筆豁免即可記錄這個決定），"
               "或補上三個按鈕，或刪除這些函式與後端處理函式。PLC-6 提議的"
               "註解可讓閱讀頁面程式碼的人知道它們為何存在。",
        steps=(
            "Open Places and run a query that returns rows.",
            "Look for a Pajek, Gephi/GUESS or UCINet export: there is "
            "none, though the page's script defines exportPajek, "
            "exportGephi and exportUCINet.",
        ),
        steps_zh=(
            "開啟地點表單，執行一個有結果的查詢。",
            "尋找 Pajek、Gephi/GUESS 或 UCINet 匯出：一個都沒有，儘管頁面"
            "程式碼中定義了 exportPajek、exportGephi 與 exportUCINet。",
        ),
        source=(
            "Templates/places/index.html:853 (exportUCINet, called by "
            "nothing)",
            "Templates/places/index.html:870 (exportPajek, called by "
            "nothing)",
            "Templates/places/index.html:887 (exportGephi, called by "
            "nothing)",
            "Templates/places/index.html:93 (the page's action buttons)",
        ),
        tests=("test_every_endpoint_a_page_calls_is_reachable_from_"
               "something_a_user_does",),
    ),
    Defect(
        key="CBDB-D-004",
        priority="P6", severity="medium", origin="software",
        title="On ten of the eleven translated forms, Chinese labels differ from "
              "the CBDB glossary's terms -- some of them changing the "
              "meaning: the Office form's Index Years filter is labelled "
              "生卒年 (birth and death years), and five forms call the "
              "index year 索引年",
        title_zh="十一個有翻譯的表單中有十個，中文標籤與 CBDB 標籤對照表的用語"
                 "不同——其中有些改變了意思：官職表單的「指數年」篩選被標為"
                 "「生卒年」，另有五個表單把指數年寫成「索引年」",
        area="The translation tables of every form with a language switch "
             "(Templates/*/index.html)",
        area_zh="所有具語言切換的表單的翻譯表（Templates/*/index.html）",
        summary="When a label's English is a term the CBDB label glossary "
                "(the Access front end's FormLabels table, "
                "docs/labels/FormLabels.xlsx in the test repository) "
                "defines for that form, its Chinese should be one of the "
                "glossary's renderings of that term.  116 labels on ten of "
                "the eleven translated forms (all but the Browser) are "
                "not.  Most are wording "
                "the glossary words differently (`執行查詢` for *Run "
                "Query*, glossary `查詢`; `儲存人物ID` for *Store Person "
                "IDs*, glossary `存儲人物代碼`; `起`/`終` for *From*/*To*, "
                "glossary `始年`/`終年`).  Some change what the reader is "
                "told:\n\n"
                "- Office: the date filter *Index Years* is `生卒年` "
                "(birth and death years) in both Chinese languages; the "
                "filter is on index year.\n"
                "- Association Pairs, Associations, Entry, Networks, "
                "Texts: *Index Year* is `索引年` / `索引年份`; the "
                "glossary's term is `指數年`, and the developers' own "
                "2026-10-16 note says `指數` is correct and `索引` is to be "
                "reverted.\n"
                "- Status and Group Data: *Status* is `身份`; the "
                "glossary's term is `社會區分`.\n"
                "- Kinship: *Mourning Circle* is `服制圈`; the glossary's "
                "term is `五服`.\n"
                "- Networks: the association-type checkboxes use their own "
                "translations (`友誼`, `對立`, `支持`, `學術隸屬`, "
                "`推薦／贊助`) where the glossary has `朋友`, `軍事對抗`, "
                "`軍事支持`, `學術交往`, `薦舉保任`.\n\n"
                "The full list, with the glossary row each judgement rests "
                "on, is in `reports/CBDB_Desktop_Translations.md` / "
                "`.xlsx`.",
        summary_zh="當一個標籤的英文是 CBDB 標籤對照表（Access 前端的 "
                   "FormLabels 表，即測試儲存庫中的 docs/labels/FormLabels.xlsx）"
                   "為該表單定義的用語時，它的中文應當是對照表為該用語給出的"
                   "譯名之一。十一個有翻譯的表單中有十個（人物瀏覽除外），共 116 "
                   "個標籤不是如此。多數"
                   "是措辭與對照表不同（*Run Query* 寫作 `執行查詢`，對照表為 "
                   "`查詢`；*Store Person IDs* 寫作 `儲存人物ID`，對照表為 "
                   "`存儲人物代碼`；*From*/*To* 寫作 `起`/`終`，對照表為 "
                   "`始年`/`終年`）。但也有一些改變了告訴讀者的意思：\n\n"
                   "- 官職表單：日期篩選 *Index Years* 在兩種中文中都寫作 "
                   "`生卒年`；實際篩選的是指數年。\n"
                   "- 兩兩關係、社會關係、入仕、社會網絡、著述表單：*Index "
                   "Year* 寫作 `索引年`／`索引年份`；對照表的用語是 `指數年`，"
                   "而開發者自己 2026-10-16 的說明也指出 `指數` 才正確、"
                   "`索引` 應改回。\n"
                   "- 社會區分與群體資料表單：*Status* 寫作 `身份`；對照表的"
                   "用語是 `社會區分`。\n"
                   "- 親屬表單：*Mourning Circle* 寫作 `服制圈`；對照表的用語"
                   "是 `五服`。\n"
                   "- 社會網絡表單：社會關係類別的勾選框自行翻譯（`友誼`、"
                   "`對立`、`支持`、`學術隸屬`、`推薦／贊助`），對照表則為 "
                   "`朋友`、`軍事對抗`、`軍事支持`、`學術交往`、`薦舉保任`。\n\n"
                   "完整清單及每項判定所依據的對照表列，見 "
                   "`reports/CBDB_Desktop_Translations.md`／`.xlsx`。",
        evidence="`test_chinese_labels_use_the_glossary_term`, one test "
                 "per form, fails on ten of eleven.  The labels are read as "
                 "data from each template's translation object, and only "
                 "labels the page actually reads are judged; a label is "
                 "compared only with the glossary rows of its own Access "
                 "form (Office with LAO, Status with LAS, the Browser with "
                 "BIO and BROWSE -- its subforms' short column headers never "
                 "decide an English word), and wording is compared after "
                 "reducing both sides to one script and allowing "
                 "Taiwan/mainland vocabulary (匯出/导出, 儲存/保存), so "
                 "neither a script slip nor a regional word can produce a "
                 "finding here.  Counts per form: networks 32, group_data "
                 "15, status 14, association_pairs 11, entry 9, office 9, "
                 "kinship 8, texts 8, associations 7, places 3 "
                 "(as measured on this build; the report is the "
                 "authority).",
        evidence_zh="`test_chinese_labels_use_the_glossary_term` 每個表單一個"
                    "測試，十一個中有十個失敗。標籤是從每個模板的翻譯物件中以資料"
                    "方式讀出，只判定頁面實際使用的標籤；每個標籤只和它自己的 "
                    "Access 表單的對照表列比較（官職對 LAO、社會區分對 LAS、人物"
                    "瀏覽對 BIO 與 BROWSE——其子表單的簡短欄位標題不用來決定英文"
                    "詞的譯法），"
                    "比較措辭時先把兩邊轉成同一種字體，並容許兩岸用語差異"
                    "（匯出／导出、儲存／保存），因此字體錯誤或地區用語都不會"
                    "在這裡造成判定。各表單筆數：社會網絡 32、群體資料 15、"
                    "社會區分 14、兩兩關係 11、入仕 9、官職 9、親屬 8、著述 8、"
                    "社會關係 7、地點 3（此版本的量測結果；以報告為準）。",
        impact="A reader of the Chinese interface is told something "
               "different from what the English reader is told, and "
               "different from the vocabulary CBDB uses everywhere else.  "
               "Where the meaning changes, it misleads: a historian who "
               "reads 生卒年 on the Office form will believe the filter "
               "selects by birth and death years.  Nothing the application "
               "computes is affected.",
        impact_zh="中文介面的讀者所得到的訊息，與英文讀者不同，也與 CBDB 其他"
                  "地方使用的用語不同。在意思被改變之處會造成誤導：在官職表單"
                  "上讀到「生卒年」的研究者，會以為該篩選是依生卒年選取。程式"
                  "的計算結果不受影響。",
        fix="Replace each listed Chinese label with the glossary's term "
            "(the report gives it), starting with the ones that change the "
            "meaning.  Where the developers prefer their wording, the "
            "glossary is what should change -- in the spreadsheet, so the "
            "two stay one vocabulary.",
        fix_zh="把清單中的每個中文標籤換成對照表的用語（報告中已列出），"
               "先處理改變意思的那些。若開發者偏好自己的措辭，應改的是對照表"
               "——在試算表中修改，讓兩者維持同一套用語。",
        steps=(
            "Open Look At Office and press 繁 (or 简).",
            "Read the date-filter option that the English page calls "
            "Index Years: it says 生卒年.",
            "Open Look At Entry, press 繁: the index-year option says "
            "索引年, where CBDB's term is 指數年.",
        ),
        steps_zh=(
            "開啟官職表單（Look At Office），按「繁」（或「简」）。",
            "閱讀英文頁面稱為 Index Years 的日期篩選選項：它寫著「生卒年」。",
            "開啟入仕表單（Look At Entry），按「繁」：指數年選項寫著「索引年」，"
            "而 CBDB 的用語是「指數年」。",
        ),
        source=(
            "Templates/office/index.html:245 (indexYearsFilter: '生卒年')",
            "Templates/entry/index.html:299 (indexYear: '索引年')",
            "Templates/status/index.html:218 (status: '身份')",
            "Templates/kinship/index.html:170 (Mourning Circle: '服制圈')",
        ),
        tests=("test_chinese_labels_use_the_glossary_term",),
    ),
    Defect(
        key="CBDB-D-005",
        priority="P6", severity="low", origin="software",
        title="Twelve labels on four forms pair English and Chinese the "
              "glossary does not pair -- among them the "
              "Browser tab captioned Basic Information whose Chinese says "
              "生卒年 (birth and death years)",
        title_zh="四個表單上有十二個標籤，其英文與中文的配對與對照表不符——"
                 "其中包括人物瀏覽中英文標為 Basic Information、中文卻寫"
                 "「生卒年」的分頁",
        area="Browser, Kinship, Networks and Office translation tables",
        area_zh="人物瀏覽、親屬、社會網絡與官職表單的翻譯表",
        summary="When a label's Chinese is a glossary term for its form "
                "and its English is not a glossary term at all, the English "
                "should be the glossary's English for that Chinese -- or "
                "the Chinese is the wrong half.  Twelve are not: Browser "
                "*Basic Information* over `生卒年` (glossary *Birth/Death "
                "Years*), *Social Institutions* over `社交機構` "
                "(*Institutions*), *ID:* and *CBDB ID* over `人物代碼` "
                "(*Person ID*), *Birth:*/*Death:* over `生年`/`卒年` "
                "(*Born*/*Died*), *Age* over `享年` (*Age at Death*), "
                "*Offices* over `職官` (*Postings*); Kinship *Kin Network* "
                "(*Kinship Network*); Networks *Biography* and *Ritual* "
                "(*Biographical Texts*, *Ritual Texts*); Office *Query* "
                "(*Run Query*).  The first is a mismatch between the two "
                "languages, not only with the glossary: the page's own "
                "comment says the English caption was renamed and \"no new "
                "Chinese caption supplied yet\".",
        summary_zh="當一個標籤的中文是其表單的對照表用語、而英文完全不是對照表"
                   "用語時，英文應是對照表為該中文所給的英文——否則就是中文那一半"
                   "有誤。有十二個不是：人物瀏覽的 *Basic Information* 對應 "
                   "`生卒年`（對照表為 *Birth/Death Years*）、*Social "
                   "Institutions* 對應 `社交機構`（*Institutions*）、*ID:* 與 "
                   "*CBDB ID* 對應 `人物代碼`（*Person ID*）、*Birth:*／"
                   "*Death:* 對應 `生年`／`卒年`（*Born*／*Died*）、*Age* 對應 "
                   "`享年`（*Age at Death*）、*Offices* 對應 `職官`"
                   "（*Postings*）；親屬的 *Kin Network*（*Kinship "
                   "Network*）；社會網絡的 *Biography* 與 *Ritual*"
                   "（*Biographical Texts*、*Ritual Texts*）；官職的 *Query*"
                   "（*Run Query*）。第一項不只與對照表不符，也是兩種語言之間"
                   "互不相符：頁面自己的註解寫著英文標題已改名，「尚未提供新的"
                   "中文標題」。",
        evidence="`test_english_labels_use_the_glossary_term` fails for "
                 "browser (8), networks (2), kinship (1) and office (1).  "
                 "Only labels whose English is *not* a glossary term are "
                 "judged this way, so a pair that is wrong is reported once "
                 "(by D-004 or here), never from both sides.",
        evidence_zh="`test_english_labels_use_the_glossary_term` 在人物瀏覽（8）、"
                    "社會網絡（2）、親屬（1）與官職（1）上失敗。只有英文「不是」"
                    "對照表用語的標籤才以這種方式判定，因此一組錯誤的對應只會"
                    "被報告一次（在 D-004 或這裡），不會兩邊各報一次。",
        impact="Mostly wording.  The Browser's first tab is the exception: "
               "an English reader and a Chinese reader are told the tab "
               "holds different things.",
        impact_zh="多半是措辭問題。人物瀏覽的第一個分頁是例外：英文讀者與中文"
                  "讀者被告知這個分頁的內容不同。",
        fix="Use the glossary's English for these twelve, or supply the "
            "Chinese caption the Browser comment is waiting for and add "
            "both to the glossary.",
        fix_zh="這十二個標籤改用對照表的英文；或為人物瀏覽補上註解中所等待的"
               "中文標題，並將兩者一併加入對照表。",
        steps=(
            "Open the Browser, select a person, and read the first tab in "
            "English (Basic Information), then press 繁: 生卒年.",
        ),
        steps_zh=(
            "開啟人物瀏覽，選擇一個人物，以英文閱讀第一個分頁（Basic "
            "Information），再按「繁」：顯示為「生卒年」。",
        ),
        source=(
            "Templates/browser/index.html:406 (tabBasicInfo: '生卒年', with "
            "the comment about the renamed caption)",
            "Templates/kinship/index.html:163 (Kin Network)",
        ),
        tests=("test_english_labels_use_the_glossary_term",),
    ),
    Defect(
        key="CBDB-D-006",
        priority="P6", severity="low", origin="software",
        title="Seven forms show text in the wrong script for the language "
              "chosen: bilingual labels written into the page that the "
              "language switch never rewrites, and 指數 left in "
              "Simplified text",
        title_zh="七個表單顯示的文字與所選語言的字體不符：寫死在頁面上、"
                 "語言切換不會改寫的雙語標籤，以及簡體文字中殘留的「指數」",
        area="Association Pairs, Associations, Networks, Office, Places, "
             "Status and Texts pages",
        area_zh="兩兩關係、社會關係、社會網絡、官職、地點、社會區分與著述表單",
        summary="With 繁 chosen, the Office form still shows `Office 官职`, "
                "`Type 类型`, `Place 地点` and its title `官职查询`; Texts "
                "shows `查询模式`, `(全部地点)` and `日期筛选`; Associations "
                "shows `(关系)`.  With 简 chosen, Places, Associations and "
                "Networks keep traditional titles (`查看地點`, `查看關係`, "
                "`查看人際網絡`), Status keeps `Place / 地點`, Texts keeps "
                "`書名`, and Association Pairs keeps the placeholder "
                "`[漢字]`.  These are labels written straight into the "
                "HTML, which `setLanguage` does not touch.  Separately, "
                "four Simplified translations contain the traditional "
                "`數`: Places `指數年份范围`, `相关人物指數地点`, "
                "`亲属指數地点`, and Status `使用指數年份` (in both "
                "Chinese tables).",
        summary_zh="選擇「繁」時，官職表單仍顯示 `Office 官职`、`Type 类型`、"
                   "`Place 地点` 以及標題 `官职查询`；著述表單顯示 `查询模式`、"
                   "`(全部地点)` 與 `日期筛选`；社會關係表單顯示 `(关系)`。"
                   "選擇「简」時，地點、社會關係與社會網絡表單保留繁體標題"
                   "（`查看地點`、`查看關係`、`查看人際網絡`），社會區分保留 "
                   "`Place / 地點`，著述保留 `書名`，兩兩關係保留提示文字 "
                   "`[漢字]`。這些都是直接寫在 HTML 中、`setLanguage` 不會"
                   "改寫的標籤。另外有四個簡體翻譯含有繁體的「數」：地點的 "
                   "`指數年份范围`、`相关人物指數地点`、`亲属指數地点`，以及"
                   "社會區分的 `使用指數年份`（兩個中文表中皆同）。",
        evidence="Two checks in two places.  "
                 "`test_each_chinese_language_shows_only_its_own_script` "
                 "presses each page's own 繁 and 简 buttons in Chromium and "
                 "judges what is on screen (only strings that occur in the "
                 "template, so CBDB data shown on the page is not judged, "
                 "and not strings the table check already judges, so "
                 "nothing is counted twice): "
                 "14 strings on 7 pages.  "
                 "`test_every_chinese_label_is_written_in_its_own_script` "
                 "reads the translation tables: the four `數` above.  A "
                 "character is flagged only when every OpenCC conversion "
                 "into the chosen script -- mainland, Taiwan and Hong Kong "
                 "standards -- changes it, in context and on its own.",
        evidence_zh="兩處各有一項檢查。"
                    "`test_each_chinese_language_shows_only_its_own_script` "
                    "在 Chromium 中按下每個頁面自己的「繁」與「简」按鈕，判讀"
                    "畫面上的文字（只判讀出現在模板中、且不屬於翻譯表的字串——"
                    "翻譯表中的字串已由另一項檢查判讀，不重複計算；頁面上顯示的 "
                    "CBDB 資料不在判讀之列）：7 個頁面共 14 個字串。"
                    "`test_every_chinese_label_is_written_in_its_own_script` "
                    "讀取翻譯表：即上述四個「數」。只有當 OpenCC 轉換為所選字體"
                    "的每一種標準——大陸、台灣與香港——不論在上下文中或單獨"
                    "看都會改動某個字時，該字才會被標出。",
        impact="A reader who chose one script sees the other in labels and "
               "titles.  Cosmetic, but it is exactly what a reader who "
               "chooses 繁 or 简 notices first.",
        impact_zh="選擇了某一種字體的讀者，在標籤與標題中看到另一種字體。屬於"
                  "外觀問題，但正是選擇「繁」或「简」的讀者最先注意到的地方。",
        fix="Give each hard-coded bilingual label an id and a key in the "
            "page's translation table, as the translated labels already "
            "have; replace `數` with `数` in the four Simplified strings.",
        fix_zh="為每個寫死的雙語標籤加上 id，並在頁面的翻譯表中加入對應的"
               "鍵（已翻譯的標籤本來就是這樣做）；把四個簡體字串中的「數」改為"
               "「数」。",
        steps=(
            "Open Look At Office and press 繁.",
            "Read the left panel: 'Office 官职', 'Type 类型', 'Place 地点' "
            "are still in Simplified Chinese.",
        ),
        steps_zh=(
            "開啟官職表單（Look At Office），按「繁」。",
            "閱讀左側面板：'Office 官职'、'Type 类型'、'Place 地点' 仍是"
            "簡體字。",
        ),
        source=(
            "Templates/office/index.html:34 (<label>Office 官职</label>)",
            "Templates/status/index.html:49 (<h3>Place / 地點</h3>)",
            "Templates/places/index.html:202 (indexYearRange: '指數年份范围')",
            "Templates/status/index.html:239 (useIndexYears: '使用指數年份')",
        ),
        tests=("test_each_chinese_language_shows_only_its_own_script",
               "test_every_chinese_label_is_written_in_its_own_script"),
    ),
    Defect(
        key="CBDB-D-007",
        priority="P6", severity="low", origin="software",
        title="One English label, several Chinese words: 23 labels are "
              "translated differently on different forms (Save to GIS "
              "three ways, Index Year four ways)",
        title_zh="同一個英文標籤、好幾種中文：23 個標籤在不同表單上譯法不同"
                 "（Save to GIS 有三種、Index Year 有四種）",
        area="Translation tables across all forms",
        area_zh="所有表單的翻譯表",
        summary="Grouping every translated label by its English shows 23 "
                "that the forms translate in more than one way, among "
                "them: *Save to GIS* `儲存至GIS` (Association Pairs, "
                "Entry, Group Data), `保存到GIS` (Associations, Networks, "
                "Places, Status, Texts), `存至GIS` (Kinship); *Index "
                "Year* `索引年`, `索引年份`, `指數年`, `生卒年`; *Recall "
                "IDs* `召回ID`, `調出ID`, `調取ID`; *Status* `社會區分` "
                "(Browser) and `身份` (Group Data, Status); *Offices* "
                "`職官` and `官職`; *From:*/*To:* `從:`/`至:` and "
                "`起`/`終`.  Taiwan/mainland vocabulary is not counted as "
                "a difference (the maintainer's ruling of 2026-10-22).",
        summary_zh="把所有翻譯標籤依英文分組，有 23 個在不同表單上有多於一種"
                   "譯法，例如：*Save to GIS* 有 `儲存至GIS`（兩兩關係、入仕、"
                   "群體資料）、`保存到GIS`（社會關係、社會網絡、地點、社會"
                   "區分、著述）、`存至GIS`（親屬）；*Index Year* 有 `索引年`、"
                   "`索引年份`、`指數年`、`生卒年`；*Recall IDs* 有 `召回ID`、"
                   "`調出ID`、`調取ID`；*Status* 有 `社會區分`（人物瀏覽）與 "
                   "`身份`（群體資料、社會區分）；*Offices* 有 `職官` 與 "
                   "`官職`；*From:*／*To:* 有 `從:`／`至:` 與 `起`／`終`。兩岸"
                   "用語差異不算作不同（維護者 2026-10-22 的裁定）。",
        evidence="`test_one_english_label_is_translated_one_way_across_"
                 "pages` (needs no glossary).  Wordings are grouped by "
                 "OpenCC's script and Taiwan/mainland equivalence plus the "
                 "pairs in docs/labels/regional_terms.tsv, so 儲存/保存, "
                 "匯出/导出 or 連結/连接 count as one word; several Chinese "
                 "labels under one short "
                 "English word on the *same* form (the Browser's Range → "
                 "生年時限 / 卒年時限) are fields named in context and are not "
                 "counted.",
        evidence_zh="`test_one_english_label_is_translated_one_way_across_"
                    "pages`（不需對照表）。措辭依 OpenCC 的字體與兩岸用語對應，"
                    "加上 docs/labels/regional_terms.tsv 中的詞對歸類，因此 "
                    "儲存／保存、匯出／导出 或 連結／连接 視為同一個詞；同一表單內一個簡短英文詞對應數個中文標籤（人物"
                    "瀏覽的 Range → 生年時限／卒年時限）是依上下文命名的欄位，"
                    "不計入。",
        impact="A reader learns several words for one action or one "
               "concept as they move between forms, and cannot tell "
               "whether the forms mean the same thing.",
        impact_zh="讀者在表單間移動時，對同一個動作或概念要認識好幾個詞，"
                  "也無法分辨各表單指的是否是同一件事。",
        fix="Choose one wording per label -- the glossary's, where it has "
            "one (D-004) -- and use it on every form.",
        fix_zh="每個標籤選定一種措辭——對照表有的就用對照表的（見 D-004）——"
               "並在所有表單上一致使用。",
        steps=(
            "Press 繁 on Look At Entry, Look At Networks and Look At "
            "Kinship, and compare the Save to GIS buttons: 儲存至GIS, "
            "保存到GIS, 存至GIS.",
        ),
        steps_zh=(
            "在入仕、社會網絡與親屬表單上按「繁」，比較 Save to GIS 按鈕："
            "儲存至GIS、保存到GIS、存至GIS。",
        ),
        source=(
            "Templates/entry/index.html:308 (saveGIS: '儲存至GIS')",
            "Templates/networks/index.html:482 (saveToGIS: '保存到GIS')",
            "Templates/kinship/index.html:150 (Save to GIS: '存至GIS')",
        ),
        tests=("test_one_english_label_is_translated_one_way_across_pages",),
    ),
    Defect(
        key="CBDB-D-008",
        priority="P0", severity="low", origin="software",
        title="The Places UCINet export writes some people with their "
              "attributes blanked -- index year 0, no sex, coordinates "
              "0.0 0.0 -- so those rows of network.vna are a field short",
        title_zh="地點表單的 UCINet 匯出把部分人物的屬性寫成空白——指數年 0、"
                 "性別空白、座標 0.0 0.0——使 network.vna 中這些列少了一個欄位",
        area="Places form, /api/places/export-ucinet (network.vna)",
        area_zh="地點表單的 UCINet 網絡匯出（輸出檔 network.vna）",
        summary="In the `*node data` section, some people are written as "
                "`<id> 0  0.0 0.0`: index year 0, an empty unquoted sex "
                "field, and zero coordinates.  They are people who are in "
                "the result with a real sex and index year -- the writer "
                "appears to take their attributes from a record where they "
                "occur only as the associate.  Because VNA is whitespace-"
                "delimited, the empty sex disappears and every later column "
                "shifts left, so the row is malformed as well as wrong.  "
                "PLC-3 (Kinship now reads KIN_DATA) adds many associate-"
                "only appearances, which is why it shows now.  No control "
                "on the page reaches this export (CBDB-D-003), so no user "
                "can produce the file today; it is filed because the "
                "developers have kept the export to be wired up later.",
        summary_zh="在 `*node data` 區段中，部分人物被寫成 `<id> 0  0.0 0.0`："
                   "指數年 0、性別欄空白且未加引號、座標為零。這些人其實在"
                   "查詢結果中有真實的性別與指數年——寫出程式似乎是從他們只"
                   "以「關係人」身分出現的那筆記錄取屬性。由於 VNA 以空白分隔，"
                   "空白的性別欄會消失，後面每一欄都往左移，因此這些列不只是"
                   "錯誤，格式也壞了。PLC-3（親屬改讀 KIN_DATA）增加了大量只以"
                   "關係人身分出現的情形，所以現在才顯現。頁面上沒有任何控制項"
                   "到得了這個匯出（CBDB-D-003），目前沒有使用者能產生這個檔案；"
                   "列入是因為開發者保留了這個匯出，打算日後接上。",
        evidence="`test_an_export_produces_a_well_formed_file[places:"
                 "ucinet]`, after the suite's own discovered Places query: "
                 "11 node rows in that shape, every short row matching it "
                 "exactly.  On a denser input (address 14504, all seven "
                 "categories, 932 records, on a private database copy) 155 "
                 "of 465 node rows, e.g. person 145689, who is in the "
                 "result as sex F, index year 747.  The binary's Places "
                 "code is not in the shipped source (CBDB-D-001), so the "
                 "writer could not be read; the mechanism is inferred from "
                 "the output.",
        evidence_zh="`test_an_export_produces_a_well_formed_file[places:"
                    "ucinet]`，以套件自己找出的地點查詢執行：有 11 個節點列是"
                    "這種形式，所有欄位不足的列都完全符合。在較密集的輸入上"
                    "（地址 14504、七個類別全選、932 筆記錄，於私有資料庫副本上）"
                    "465 個節點列中有 155 列，例如人物 145689，在結果中為性別 "
                    "F、指數年 747。執行檔的地點程式碼不在隨附原始碼中"
                    "（CBDB-D-001），因此無法閱讀寫出程式；機制是由輸出推斷的。",
        impact="None today, because nothing on the page calls the export.  "
               "If it is wired up as it stands, UCINet would read the "
               "file's attribute columns misaligned for those people, "
               "without any error.",
        impact_zh="目前沒有影響，因為頁面上沒有任何東西呼叫這個匯出。若照現狀"
                  "接上，UCINet 會在沒有任何錯誤提示的情況下，把這些人的屬性欄位"
                  "錯位讀入。",
        fix="Take each person's node attributes from their own record (or "
            "BIOG_MAIN), not from a record where they appear as the "
            "associate, and quote empty values, before wiring the export "
            "to a button.",
        fix_zh="每個人的節點屬性應取自他自己的記錄（或 BIOG_MAIN），而不是他以"
               "關係人身分出現的記錄；並在接上按鈕之前為空值加上引號。",
        steps=(
            "POST a Places query result to /api/places/export-ucinet (no "
            "button does this) and open network.vna: some *node data rows "
            "read '<id> 0  0.0 0.0'.",
        ),
        steps_zh=(
            "把一次地點查詢的結果 POST 到 /api/places/export-ucinet（沒有"
            "任何按鈕會這樣做），打開 network.vna：部分 *node data 列為 "
            "'<id> 0  0.0 0.0'。",
        ),
        source=(
            "Code/places_form_backend.go:1348 (handleExportUCINet, as "
            "shipped -- the source the binary was built from was not)",
            "Templates/places/index.html:853 (exportUCINet, called by "
            "nothing)",
        ),
        tests=("test_an_export_produces_a_well_formed_file",),
    ),
)

#: What the report iterates.  Keyed by ``Defect.key`` (CBDB-D-0NN),
#: which is assigned while writing one report and means nothing outside
#: it -- that is why the waiver table is keyed by test names instead.
DEFECTS: dict[str, Defect] = {defect.key: defect for defect in _DEFECTS}

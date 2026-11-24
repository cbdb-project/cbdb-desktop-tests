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
                "Save to GIS and Save to Neo4j, and no listener or "
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
                   "導出查詢結果、保存到KML、保存到GIS 與保存到Neo4j，也沒有"
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
            "Templates/places/index.html:953 (exportUCINet, called by "
            "nothing)",
            "Templates/places/index.html:970 (exportPajek, called by "
            "nothing)",
            "Templates/places/index.html:987 (exportGephi, called by "
            "nothing)",
            "Templates/places/index.html:94 (the page's action buttons)",
        ),
        tests=("test_every_endpoint_a_page_calls_is_reachable_from_"
               "something_a_user_does",),
    ),
    Defect(
        key="CBDB-D-004",
        priority="P6", severity="low", origin="software",
        title="On six of the twelve translated pages, 16 Chinese labels "
              "differ from the CBDB glossary's terms -- every one a "
              "wording the developers chose in their 2026-10-26/28 label "
              "review, such as 保存于… for every Save to … button",
        title_zh="十二個有翻譯的頁面中有六個，共 16 個中文標籤與 CBDB 標籤"
                 "對照表的用語不同——每一個都是開發者在 2026-10-26／28 標籤"
                 "審查中選定的措辭，例如所有 Save to … 按鈕都寫作「保存于…」",
        area="The translation tables of Association Pairs, Browser, "
             "Networks, Office, Places and Status",
        area_zh="兩兩關係、人物瀏覽、社會網絡、官職、地點與社會區分頁面的翻譯表",
        summary="When a label's English is a term the CBDB label glossary "
                "(the Access front end's FormLabels table, "
                "docs/labels/FormLabels.xlsx in the test repository) "
                "defines for that form, its Chinese should be one of the "
                "glossary's renderings of that term.  16 labels on six "
                "pages are not, down from 116 on ten forms in 20261021: "
                "the developers reviewed every form against the same table "
                "between 2026-10-26 and 2026-10-28 and recorded where they "
                "departed from it.  What is left is those departures:\n\n"
                "- Save to UCINet / GIS / Gephi / Pajek: `保存于…` on "
                "Association Pairs (1) and Networks (4), the wording their "
                "conventions note fixes for every form.\n"
                "- Browser (6): the pinyin and English columns beside a "
                "Chinese one -- `出處拼音`, `地名拼音`, `機構拼音`, "
                "`社會機構拼音`, `社會區分(英文)`, `入仕法(英文)`.\n"
                "- Office: *Office* `官名`, *Office Postings* `任官記錄`.\n"
                "- Places: *Institutional* `社會機構`, *Aggregated People "
                "and Places* `綜合人地關係` (the HTML wording kept and the "
                "Chinese rewritten to match, 2026-10-28).\n"
                "- Status: *People* `有社會區分的人`, which the notes "
                "propose as a correction to the glossary's LAS 10.\n\n"
                "Every one of these wordings appears in the developers' "
                "label-revision notes shipped beside the tree.",
        summary_zh="當一個標籤的英文是 CBDB 標籤對照表（Access 前端的 "
                   "FormLabels 表，即測試儲存庫中的 docs/labels/FormLabels.xlsx）"
                   "為該表單定義的用語時，它的中文應當是對照表為該用語給出的"
                   "譯名之一。六個頁面共 16 個標籤不是如此，比 20261021 版十個"
                   "表單 116 個大幅減少：開發者在 2026-10-26 至 2026-10-28 "
                   "之間依同一份對照表逐一審查了所有表單，並記錄了與對照表"
                   "不同之處。剩下的就是這些刻意的差異：\n\n"
                   "- Save to UCINet／GIS／Gephi／Pajek：兩兩關係（1）與社會"
                   "網絡（4）寫作 `保存于…`，這是開發者的慣例說明為所有表單"
                   "定下的措辭。\n"
                   "- 人物瀏覽（6）：中文欄旁的拼音欄與英文欄——`出處拼音`、"
                   "`地名拼音`、`機構拼音`、`社會機構拼音`、`社會區分(英文)`、"
                   "`入仕法(英文)`。\n"
                   "- 官職：*Office* 寫作 `官名`，*Office Postings* 寫作 "
                   "`任官記錄`。\n"
                   "- 地點：*Institutional* 寫作 `社會機構`，*Aggregated People "
                   "and Places* 寫作 `綜合人地關係`（保留 HTML 的英文，改寫"
                   "中文以符合之，2026-10-28）。\n"
                   "- 社會區分：*People* 寫作 `有社會區分的人`，開發者的說明"
                   "建議據此更正對照表的 LAS 10。\n\n"
                   "這些措辭全都出現在隨版本附上的開發者標籤修訂說明中。",
        evidence="`test_chinese_labels_use_the_glossary_term`, one test "
                 "per page, fails on six of twelve: networks 4, browser 6, "
                 "office 2, places 2, association_pairs 1, status 1.  "
                 "Labels are read as data from each template's translation "
                 "object, only labels the page reads are judged, and each is "
                 "compared only with its own Access form's glossary rows, "
                 "after reducing both sides to one script and allowing "
                 "Taiwan/mainland vocabulary.  Each Chinese wording above "
                 "was searched for in the fourteen revision notes and found.",
        evidence_zh="`test_chinese_labels_use_the_glossary_term` 每個頁面一個"
                    "測試，十二個中有六個失敗：社會網絡 4、人物瀏覽 6、官職 2、"
                    "地點 2、兩兩關係 1、社會區分 1。標籤是從每個模板的翻譯物件"
                    "中以資料方式讀出，只判定頁面實際使用的標籤，且每個標籤只和"
                    "它自己的 Access 表單的對照表列比較，比較前先把兩邊轉成同一種"
                    "字體，並容許兩岸用語差異。上述每個中文措辭都在十四份修訂"
                    "說明中搜尋過，均有記錄。",
        impact="None for a reader beyond wording: none of these changes "
               "what a label says the control does.  The meaning-changing "
               "labels of 20261021 (生卒年 for Index Years, 索引年, 身份 "
               "for Status, 服制圈) are gone.",
        impact_zh="對讀者而言只是措辭差異：沒有一個改變標籤所說明的控制項"
                  "作用。20261021 版中改變意思的標籤（Index Years 寫作生卒年、"
                  "索引年、Status 寫作身份、服制圈）都已不存在。",
        fix="Accepted by the maintainer on 2026-10-29 as the developers' "
            "decisions.  Where a wording is meant to be CBDB's term from "
            "now on, change the glossary to it, so the two stay one "
            "vocabulary.",
        fix_zh="維護者已於 2026-10-29 接受為開發者的決定。若某個措辭今後即為 "
               "CBDB 的用語，應據此修改對照表，讓兩者維持同一套用語。",
        steps=(
            "Open Look At Social Networks and press 繁: the export "
            "buttons read 保存于GIS, 保存于Gephi, 保存于UCINet, 保存于Pajek.",
        ),
        steps_zh=(
            "開啟社會網絡表單，按「繁」：匯出按鈕寫作 保存于GIS、保存于Gephi、"
            "保存于UCINet、保存于Pajek。",
        ),
        source=(
            "Templates/networks/index.html:453 (saveToGIS: '保存于GIS')",
            "Templates/office/index.html:224 (office: '官名')",
            "Templates/status/index.html:230 (people: '有社會區分的人')",
        ),
        tests=("test_chinese_labels_use_the_glossary_term",),
    ),
    Defect(
        key="CBDB-D-005",
        priority="P6", severity="low", origin="software",
        title="32 labels on six pages pair English and Chinese the glossary "
              "does not pair -- the Browser's column headers, written-out "
              "abbreviations such as Max Ancestor Generations over 先世值≤, "
              "and Run Query over 查詢",
        title_zh="六個頁面上有 32 個標籤，其英文與中文的配對與對照表不符——"
                 "人物瀏覽的欄位標題、寫全的縮寫（如 Max Ancestor Generations "
                 "對應「先世值≤」），以及 Run Query 對應「查詢」",
        area="Browser, Entry, Group Data, Kinship, Networks and Places "
             "translation tables",
        area_zh="人物瀏覽、入仕、群體資料、親屬、社會網絡與地點頁面的翻譯表",
        summary="When a label's Chinese is a glossary term for its form "
                "and its English is not a glossary term at all, the English "
                "should be the glossary's English for that Chinese.  32 "
                "are not:\n\n"
                "- Browser (21): column headers named in context -- *First "
                "Year*/*Last Year* over `始年`/`終年` on four tabs, *CBDB "
                "ID* and *ID:* over `人物代碼`, *Birth:*/*Death:* over "
                "`生年`/`卒年`, *Age* over `享年`, *Offices* over `職官`, "
                "*Exam Rank* over `科第名次` and others.\n"
                "- Kinship and Networks (4): *Max Ancestor Generations* / "
                "*Max Descendant Generations* over `先世值≤` / `後世值≤`, "
                "the glossary's \"Max Ancestor Gen.\" written out (LBL-72); "
                "Networks also *Max Node Distance:* over `距離限制：`.\n"
                "- Entry (2): *Use Person Address* / *Use Entry Address* "
                "over `使用指數地址` / `使用入仕地址` (\"Use Person Addr\" "
                "written out).\n"
                "- Group Data (2): *Run Query* over `查詢` and *Save to GIS* "
                "over `保存于GIS`, the conventions note's wording for every "
                "form.\n"
                "- Places (2): *From year* / *To year* over `始年` / `終年`.\n\n"
                "The Browser was checked by the maintainer on 2026-10-27; "
                "the other wordings are recorded in the developers' notes.",
        summary_zh="當一個標籤的中文是其表單的對照表用語、而英文完全不是對照表"
                   "用語時，英文應是對照表為該中文所給的英文。有 32 個不是：\n\n"
                   "- 人物瀏覽（21）：依上下文命名的欄位標題——四個分頁上的 "
                   "*First Year*／*Last Year* 對應 `始年`／`終年`，*CBDB ID* 與 "
                   "*ID:* 對應 `人物代碼`，*Birth:*／*Death:* 對應 `生年`／"
                   "`卒年`，*Age* 對應 `享年`，*Offices* 對應 `職官`，*Exam "
                   "Rank* 對應 `科第名次` 等。\n"
                   "- 親屬與社會網絡（4）：*Max Ancestor Generations*／*Max "
                   "Descendant Generations* 對應 `先世值≤`／`後世值≤`，即把"
                   "對照表的「Max Ancestor Gen.」寫全（LBL-72）；社會網絡另有 "
                   "*Max Node Distance:* 對應 `距離限制：`。\n"
                   "- 入仕（2）：*Use Person Address*／*Use Entry Address* 對應 "
                   "`使用指數地址`／`使用入仕地址`（把「Use Person Addr」寫全）。\n"
                   "- 群體資料（2）：*Run Query* 對應 `查詢`，*Save to GIS* 對應 "
                   "`保存于GIS`，皆為慣例說明為所有表單定下的措辭。\n"
                   "- 地點（2）：*From year*／*To year* 對應 `始年`／`終年`。\n\n"
                   "人物瀏覽已由維護者於 2026-10-27 檢查；其餘措辭都記錄在開發者"
                   "的說明中。",
        evidence="`test_english_labels_use_the_glossary_term` fails for "
                 "browser (21), networks (3), entry (2), group_data (2), "
                 "kinship (2) and places (2).  Only labels whose English is "
                 "*not* a glossary term are judged this way, so a pair is "
                 "reported once (by D-004 or here), never from both sides.  "
                 "Kinship's two are measured for the first time on this "
                 "build: the page moved to named label keys "
                 "(data-lbl=\"maxUp\", KIN-2), which the checker read as "
                 "unused until it was taught the new shape.",
        evidence_zh="`test_english_labels_use_the_glossary_term` 在人物瀏覽"
                    "（21）、社會網絡（3）、入仕（2）、群體資料（2）、親屬（2）"
                    "與地點（2）上失敗。只有英文「不是」對照表用語的標籤才以這種"
                    "方式判定，因此一組對應只會被報告一次（在 D-004 或這裡）。"
                    "親屬的兩個是在此版本首次量測到：該頁改用具名的標籤鍵"
                    "（data-lbl=\"maxUp\"，KIN-2），檢查程式在學會這種寫法之前"
                    "把它們當成未使用。",
        impact="Wording only.  The 20261021 mismatch that told the two "
               "readers different things -- the Browser tab captioned "
               "Basic Information over 生卒年 -- is gone.",
        impact_zh="只是措辭差異。20261021 版中讓兩種讀者得到不同訊息的配對——"
                  "人物瀏覽英文為 Basic Information、中文卻為「生卒年」的分頁——"
                  "已不存在。",
        fix="Accepted by the maintainer on 2026-10-29 as the developers' "
            "decisions.  Where the written-out English is to be CBDB's "
            "label from now on, add it to the glossary.",
        fix_zh="維護者已於 2026-10-29 接受為開發者的決定。若寫全的英文今後即為 "
               "CBDB 的標籤，應將其加入對照表。",
        steps=(
            "Open Look At Kinship in English: the step limits read Max "
            "Ancestor Generations: etc.; press 繁: 先世值≤, the glossary's "
            "Chinese for Max Ancestor Gen.",
        ),
        steps_zh=(
            "以英文開啟親屬表單：步數限制寫作 Max Ancestor Generations: 等；"
            "按「繁」：寫作「先世值≤」，即對照表中 Max Ancestor Gen. 的中文。",
        ),
        source=(
            "Templates/kinship/index.html:167 (maxUp: '先世值≤')",
            "Templates/browser/index.html:432 (adFirst: '始年')",
        ),
        tests=("test_english_labels_use_the_glossary_term",),
    ),
    Defect(
        key="CBDB-D-007",
        priority="P6", severity="low", origin="software",
        title="One English label, several Chinese words: 9 labels are "
              "translated differently on different pages (People six "
              "ways, Type four ways)",
        title_zh="同一個英文標籤、好幾種中文：9 個標籤在不同頁面上譯法不同"
                 "（People 有六種、Type 有四種）",
        area="Translation tables across all pages",
        area_zh="所有頁面的翻譯表",
        summary="Grouping every translated label by its English shows 9 "
                "that the pages translate in more than one way: *People* "
                "(`社會關係的人`, `人物`, `於地址有關係的人`, "
                "`有社會區分的人`, ... -- the results tab of each query "
                "form named for what links its people), *Type*, "
                "*Chinese*, *Addresses*, *Entry*, *Offices*, *Status*, "
                "*Texts* and *Place*.  Most of the other wordings are the "
                "Browser's column headers, a short English word over a "
                "field named in context (*Chinese* over `親戚姓名`), and "
                "the QBE's *Status* heading `狀態`, which is a query's "
                "status rather than CBDB's social distinction.  Down from "
                "23 in 20261021; Save to GIS, Index Year and Recall IDs "
                "are now one wording each.",
        summary_zh="把所有翻譯標籤依英文分組，有 9 個在不同頁面上有多於一種"
                   "譯法：*People*（`社會關係的人`、`人物`、`於地址有關係的人`、"
                   "`有社會區分的人`……——每個查詢表單的結果分頁依其人物之間的"
                   "關聯命名）、*Type*、*Chinese*、*Addresses*、*Entry*、"
                   "*Offices*、*Status*、*Texts* 與 *Place*。其他譯法大多是人物"
                   "瀏覽的欄位標題，即一個簡短英文詞對應依上下文命名的欄位"
                   "（*Chinese* 對應 `親戚姓名`），以及 QBE 的 *Status* 標題 "
                   "`狀態`，指的是查詢的狀態，而非 CBDB 的社會區分。比 20261021 "
                   "版的 23 個減少；Save to GIS、Index Year 與 Recall IDs 現在"
                   "各只有一種譯法。",
        evidence="`test_one_english_label_is_translated_one_way_across_"
                 "pages` (needs no glossary).  Wordings are grouped by "
                 "OpenCC's script and Taiwan/mainland equivalence plus the "
                 "pairs in docs/labels/regional_terms.tsv; several Chinese "
                 "labels under one English word on the *same* page are "
                 "fields named in context and are not counted.",
        evidence_zh="`test_one_english_label_is_translated_one_way_across_"
                    "pages`（不需對照表）。措辭依 OpenCC 的字體與兩岸用語對應，"
                    "加上 docs/labels/regional_terms.tsv 中的詞對歸類；同一頁面"
                    "內一個英文詞對應數個中文標籤，是依上下文命名的欄位，不計入。",
        impact="Wording only: each Chinese label is right for its own "
               "page, and the English is the shorter, shared word.",
        impact_zh="只是措辭差異：每個中文標籤在它自己的頁面上都正確，英文則是"
                  "較短、共用的詞。",
        fix="Accepted by the maintainer on 2026-10-29 as the developers' "
            "decisions.",
        fix_zh="維護者已於 2026-10-29 接受為開發者的決定。",
        steps=(
            "Press 繁 on Look At Associations, Look At Place and Look At "
            "Status and compare the People results tab: 社會關係的人, "
            "於地址有關係的人, 有社會區分的人.",
        ),
        steps_zh=(
            "在社會關係、地點與社會區分表單上按「繁」，比較 People 結果分頁："
            "社會關係的人、於地址有關係的人、有社會區分的人。",
        ),
        source=(
            "Templates/status/index.html:230 (people: '有社會區分的人')",
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
                "the result with a real sex and index year.  The writer "
                "keeps the first attributes it sees for each person, and "
                "when that person first appears as another row's associate "
                "it records them with no index year, an empty sex and no "
                "coordinates; their own row, later, is ignored.  Because "
                "VNA is whitespace-delimited, the empty sex disappears and "
                "every later column shifts left, so the row is malformed "
                "as well as wrong.  No control on the page reaches this "
                "export (CBDB-D-003), so no user can produce the file "
                "today; it is filed because the developers have kept the "
                "export to be wired up later.",
        summary_zh="在 `*node data` 區段中，部分人物被寫成 `<id> 0  0.0 0.0`："
                   "指數年 0、性別欄空白且未加引號、座標為零。這些人其實在查詢"
                   "結果中有真實的性別與指數年。寫出程式對每個人只保留第一次看到"
                   "的屬性；若此人第一次出現時是另一列的關係人，就會被記成沒有"
                   "指數年、性別空白、沒有座標，之後他自己的那一列則被忽略。由於 "
                   "VNA 以空白分隔，空白的性別欄會消失，後面每一欄都往左移，因此"
                   "這些列不只是錯誤，格式也壞了。頁面上沒有任何控制項到得了這個"
                   "匯出（CBDB-D-003），目前沒有使用者能產生這個檔案；列入是因為"
                   "開發者保留了這個匯出，打算日後接上。",
        evidence="`test_an_export_produces_a_well_formed_file[places:"
                 "ucinet]`, after the suite's own discovered Places query: "
                 "node rows in that shape, every short row matching it "
                 "exactly.  On a denser input (address 14504, all seven "
                 "categories, 932 records, on a private database copy) 155 "
                 "of 465 node rows in 20261021, e.g. person 145689, who is "
                 "in the result as sex F, index year 747.  The binary is "
                 "unchanged in this build, and its source now ships: "
                 "`handleExportUCINet` adds each associate as "
                 "`addNode(rec.AssocID, nil, \"\", ...)`, `addNode` keeps "
                 "only a person's first appearance, and the row is written "
                 "with `%s` for sex, unquoted.",
        evidence_zh="`test_an_export_produces_a_well_formed_file[places:"
                    "ucinet]`，以套件自己找出的地點查詢執行：有節點列是這種"
                    "形式，所有欄位不足的列都完全符合。在較密集的輸入上（地址 "
                    "14504、七個類別全選、932 筆記錄，於私有資料庫副本上），"
                    "20261021 版 465 個節點列中有 155 列，例如人物 145689，在"
                    "結果中為性別 F、指數年 747。此版本的執行檔未變，而它的原始碼"
                    "現在隨附了：`handleExportUCINet` 以 "
                    "`addNode(rec.AssocID, nil, \"\", ...)` 加入每個關係人，"
                    "`addNode` 只保留一個人第一次出現時的屬性，寫出時性別欄用 "
                    "`%s`，未加引號。",
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
            "Code/places_form_backend.go:1438 (an associate added with no "
            "attributes)",
            "Code/places_form_backend.go:1420 (only the first appearance "
            "is kept)",
            "Templates/places/index.html:953 (exportUCINet, called by "
            "nothing)",
        ),
        tests=("test_an_export_produces_a_well_formed_file",),
    ),
)

#: What the report iterates.  Keyed by ``Defect.key`` (CBDB-D-0NN),
#: which is assigned while writing one report and means nothing outside
#: it -- that is why the waiver table is keyed by test names instead.
DEFECTS: dict[str, Defect] = {defect.key: defect for defect in _DEFECTS}

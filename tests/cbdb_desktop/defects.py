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
        priority="P0", severity="high", origin="software",
        title="Both KML exports write an XML declaration that is never "
              "closed, so no reader accepts the file",
        title_zh="兩個 KML 匯出功能寫出的 XML 宣告沒有結尾，任何軟體都無法讀取"
                 "這個檔案",
        area="Entry form and Places form, KML export",
        area_zh="入仕表單與地點表單的 KML 匯出",
        summary="The Entry and Places forms write their KML with the opening "
                "line `<?xml version=\"1.0\" encoding=\"UTF-8\">`.  An XML "
                "declaration has to end `?>`; this one ends `>`.  Every XML "
                "parser therefore rejects the document at its first line, so "
                "the file cannot be opened in Google Earth, QGIS or ArcGIS "
                "-- and the application reports the export as successful.",
        summary_zh="入仕與地點兩個表單寫出的 KML，開頭一行是 "
                   "`<?xml version=\"1.0\" encoding=\"UTF-8\">`。XML 宣告必須"
                   "以 `?>` 結尾，這裡卻只有 `>`。因此任何 XML 解析器都會在"
                   "第一行就拒絕整份文件，Google Earth、QGIS、ArcGIS 都打不開"
                   "——而程式卻回報匯出成功。",
        evidence="Measured twice, independently.  Driving the two endpoints "
                 "through the shipped binary returns files beginning with "
                 "that exact string (`entry:kml/entry_gis_UTF8.kml` and "
                 "`places:kml/places_export.kml`).  Reading the shipped Go "
                 "finds the same two writers and no others, so this cannot "
                 "depend on the data: it is wrong for every input.",
        evidence_zh="以兩種互相獨立的方式各測一次。透過釋出的執行檔實際呼叫"
                    "這兩個端點，取回的檔案開頭就是上述字串（"
                    "`entry:kml/entry_gis_UTF8.kml` 與 "
                    "`places:kml/places_export.kml`）；直接讀釋出的 Go 原始碼，"
                    "也只找到這兩處寫法。因此與資料內容無關：任何輸入都是錯的。",
        impact="Two of the application's geographic exports produce nothing "
               "usable, and nothing tells the user.  Anyone mapping entry or "
               "place addresses gets a download that their GIS silently "
               "refuses to open.",
        impact_zh="程式的兩項地理匯出完全不可用，而且不會有任何提示。想把入仕"
                  "或地點的地址繪成地圖的使用者，只會拿到一個 GIS 軟體打不開"
                  "的檔案。",
        fix="Add the missing `?` in both writers: "
            "`<?xml version=\"1.0\" encoding=\"UTF-8\"?>`.  Worth checking "
            "the other KML writers in the same commit -- they are already "
            "correct, which is why only these two are listed.",
        fix_zh="在兩處各補上缺少的 `?`，寫成 "
               "`<?xml version=\"1.0\" encoding=\"UTF-8\"?>`。建議同時檢查其餘"
               "的 KML 輸出處——它們目前是正確的，所以這裡只列出這兩處。",
        steps=(
            "Open the Entry form (/LookAtEntry), pick any entry code and run "
            "the query.",
            "Press KML and save the file.",
            "Open it in Google Earth, or run any XML parser over it: it "
            "fails on line 1.",
            "Repeat on the Places form (/LookAtPlace) for the same result.",
        ),
        steps_zh=(
            "開啟入仕表單（/LookAtEntry），任選一個入仕代碼並執行查詢。",
            "按下 KML 並儲存檔案。",
            "用 Google Earth 開啟，或用任何 XML 解析器讀取：第一行即失敗。",
            "在地點表單（/LookAtPlace）重複一次，結果相同。",
        ),
        source=("Code/entry_form_backend.go:1006",
                "Code/places_form_backend.go:764"),
        tests=("test_an_export_produces_a_well_formed_file",
               "test_every_kml_writer_closes_its_xml_"
               "declaration"),
    ),
    Defect(
        key="CBDB-D-002",
        priority="P0", severity="high",
        origin="software",
        title="The Places page lets a user switch every category off, and "
              "then answers with the Biography rows they excluded",
        title_zh="地點頁面允許使用者取消勾選全部類別，然後回傳他們已排除的"
                 "「傳記」資料",
        area="Places form, category switches",
        area_zh="地點表單的類別勾選項",
        summary="The Places query handler substitutes `IncludeBiog = true` "
                "when it finds all seven category switches off.  As a guard "
                "against an empty request that is defensible; what makes it "
                "a defect is that the page lets a user reach it.  The seven "
                "checkboxes enforce no \"at least one\" rule, so unticking "
                "all of them and pressing Query returns biographical "
                "addresses the user has explicitly excluded, with no "
                "message.",
        summary_zh="地點查詢的處理程式發現七個類別全部未勾選時，會自動改成 "
                   "`IncludeBiog = true`。若只是為了避免空請求，這樣的保護"
                   "尚屬合理；問題在於頁面允許使用者真的走到這個狀態。七個"
                   "勾選框沒有「至少選一項」的限制，因此全部取消後按下查詢，"
                   "回傳的是使用者明確排除掉的傳記地址，而且沒有任何提示。",
        evidence="Measured on address code 20056, chosen by the suite from "
                 "the shipped data rather than by hand.  "
                 "With every category switched off the query returned 396 "
                 "rows, and the same request with Biography alone switched "
                 "on returned the same 396 rows -- the empty selection is "
                 "not merely non-empty, it is exactly the Biography "
                 "branch's own result.  Measured through the running "
                 "binary; the substitution is then visible in the source.",
        evidence_zh="本次量測使用的地址代碼是 20056——由測試套件從釋出資料中"
                    "自行挑選，而非人工指定。七個類別全部取消勾選時，查詢回傳 396 列；把同一個請求"
                    "改成只勾選「傳記」，回傳的也是同樣的 396 列——空選擇"
                    "不只是「並非真的空」，而是恰好等於傳記那一支的結果。"
                    "此結果是透過執行中的程式實測，之後在原始碼中看到對應的"
                    "替換邏輯。",
        impact="A researcher who narrows the query by unticking categories "
               "gets results from a category they excluded, presented as "
               "the answer to the question they asked.  Nothing in the "
               "interface indicates that the selection was overridden.",
        impact_zh="研究者以取消類別的方式縮小查詢範圍，卻拿到自己排除掉的"
                  "類別的資料，並且被當成所提問題的答案。介面上沒有任何地方"
                  "顯示選擇已被覆寫。",
        fix="Either refuse an empty selection in the page (keep Run Query "
            "disabled until at least one category is ticked, the way this "
            "build's Associations form now does for its picker), or answer "
            "an empty selection with no rows and say so.  The server-side "
            "default can stay as a guard once the page cannot send that "
            "request.",
        fix_zh="兩種做法皆可：一是在頁面端拒絕空選擇（在至少勾選一項之前，"
               "讓「執行查詢」保持停用——正如這一版的關聯表單對其選取器所做"
               "的），二是對空選擇回傳零列並明確告知使用者。只要頁面不會再"
               "送出這種請求，伺服器端的預設值可以留著當作保護。",
        steps=(
            "Open the Places form (/LookAtPlace) and select an address "
            "-- address code 20056 is the one measured above.",
            "Untick all seven category checkboxes, including Biography.",
            "Press Run Query: rows come back.",
            "Tick Biography only and run again: the same rows, in the same "
            "number.",
        ),
        steps_zh=(
            "開啟地點表單（/LookAtPlace），選擇一個地址——上文量測使用的是地址代碼 20056。",
            "取消七個類別勾選框的全部勾選，包含「傳記」。",
            "按下執行查詢：仍有資料回傳。",
            "改為只勾選「傳記」再查一次：得到相同的資料、相同的列數。",
        ),
        source=("Code/places_form_backend.go:205",
                "Templates/places/index.html:90",
                "Templates/places/index.html:540"),
        tests=("test_turning_every_category_off_"
               "returns_nothing",),
    ),
    Defect(
        key="CBDB-D-003",
        priority="P0", severity="high", origin="software",
        title="Twenty-two export buttons ask the browser to save several "
              "files at once, and twenty-one of them report every file as "
              "saved when only the first arrived",
        title_zh="二十二個匯出按鈕會一次要求瀏覽器儲存多個檔案，其中二十一個"
                 "更在只有第一個檔案下載成功時，回報所有檔案都已儲存",
        area="Export buttons on ten form pages",
        area_zh="十個表單頁面上的匯出按鈕",
        summary="These handlers loop over the file list the server returned "
                "and trigger a download per element from a single click.  A "
                "browser permits one automatic download per user gesture and "
                "blocks the rest, and once blocked the restriction applies "
                "to later exports from the same page -- which is why "
                "pressing Export a second time can save nothing at all.  "
                "Twenty-one of the twenty-two then print the count the *server* "
                "returned (\"2 file(s) ready\"), having never asked the "
                "browser what it accepted.",
        summary_zh="這些處理函式會走訪伺服器回傳的檔案清單，在單一次點擊中"
                   "為每個項目各觸發一次下載。瀏覽器對每個使用者手勢只允許"
                   "一次自動下載，其餘一律封鎖；而且一旦被封鎖，同一頁面之後"
                   "的匯出也會受限——這正是第二次按下匯出時可能完全存不到"
                   "檔案的原因。二十二個之中有二十一個接著印出的是「伺服器」回傳"
                   "的數量（例如「2 file(s) ready」），從未詢問瀏覽器實際接受"
                   "了幾個。",
        evidence="Counted in the shipped templates: 22 such handlers across "
                 "all 10 pages that export more than one file "
                 "(association_pairs 4, associations 2, entry 2, "
                 "group_data 3, kinship 2, networks 2, office 2, places 2, "
                 "status 2, texts 1), of which 21 report a server-side count "
                 "as though it were the outcome (the same, less one of "
                 "networks').  Three spellings of the same loop are in use "
                 "and all three are counted; a fourth would fail the check "
                 "rather than shrink these numbers.\n\n"
                 "The server side is faultless: the same endpoints return "
                 "every file, identically, on repeated requests.  Under "
                 "automation downloads are auto-accepted and every file "
                 "arrives, so the blocking half is established by reading "
                 "the delivery code and was reported from real use; the "
                 "misreported count is measured in the browser.",
        evidence_zh="在釋出的模板中逐一計數：所有 10 個會匯出多個檔案的頁面"
                    "共 22 處這樣的處理函式（association_pairs 4、"
                    "associations 2、entry 2、group_data 3、kinship 2、"
                    "networks 2、office 2、places 2、status 2、texts 1），"
                    "其中 21 處會把伺服器端的數量當成實際結果回報（與上面"
                    "相同，只少了 networks 的一處）。同一種迴圈在這些頁面裡"
                    "有三種寫法，三種都已計入；若出現第四種，檢查會直接失敗，"
                    "而不是讓這些數字悄悄變小。\n\n"
                    "伺服器端本身沒有問題：同樣的端點在重複請求下都會完整、"
                    "一致地回傳每個檔案。在自動化環境中下載會被自動接受、"
                    "每個檔案都會到齊，因此「被封鎖」這一半是透過閱讀頁面的"
                    "下載程式碼確認的，並且來自實際使用時的回報；"
                    "「數量回報錯誤」這一半則是在瀏覽器中實測的。",
        impact="A user presses Export, is told two or five files are ready, "
               "and finds one on disk.  The files that did not arrive are "
               "not named, and there is no error to search for.",
        impact_zh="使用者按下匯出，被告知已備妥兩個或五個檔案，實際磁碟上只有"
                  "一個。沒有到齊的檔案不會被列出，也沒有任何錯誤訊息可供"
                  "追查。",
        fix="Deliver a multi-file export as one download -- a zip archive is "
            "the usual answer and needs no browser permission -- or save the "
            "files one user gesture at a time.  Either way, report what was "
            "actually delivered rather than what the response contained.",
        fix_zh="把多檔匯出改成單一次下載——通常做成 zip 壓縮檔即可，且不需要"
               "瀏覽器授權——或是每個使用者手勢只儲存一個檔案。無論採用哪種"
               "方式，回報的都應該是實際送達的內容，而不是回應中包含的數量。",
        steps=(
            "Open the Kinship form, run a query, and press Export Results.",
            "Note the message: three files ready.",
            "Look in the download folder: one file.",
            "Press Export Results again -- on a default browser profile "
            "nothing is saved this time.",
        ),
        steps_zh=(
            "開啟親屬表單，執行查詢，按下匯出結果。",
            "留意訊息：顯示已備妥三個檔案。",
            "檢查下載資料夾：只有一個檔案。",
            "再按一次匯出結果——在預設的瀏覽器設定下，這一次什麼也不會存下。",
        ),
        source=("Templates/kinship/index.html:630",
                "Templates/association_pairs/index.html:936",
                "Templates/group_data/index.html:914",
                "Templates/entry/index.html:1093",
                "Templates/associations/index.html:680",
                "Templates/networks/index.html:1551",
                "Templates/places/index.html:691",
                "Templates/office/index.html:850",
                "Templates/status/index.html:795",
                "Templates/texts/index.html:823"),
        tests=("test_no_page_asks_the_browser_for_more_"
               "than_one_download",),
    ),
    Defect(
        key="CBDB-D-004",
        priority="P2", severity="high", origin="software",
        title="Three of the Networks form's four network exports answer "
              "HTTP 500 for every input: they select a column their own "
              "scratch table does not have",
        title_zh="網絡表單四個網絡匯出中有三個對任何輸入都回傳 HTTP 500："
                 "它們查詢了自己的暫存表所沒有的欄位",
        area="Networks form: Pajek, Gephi/GUESS and UCINet exports",
        area_zh="網絡表單的 Pajek、Gephi/GUESS 與 UCINet 匯出",
        summary="All three read `c_node_dist` from `ZZ_SN_NETWORK`.  That "
                "table is created by this same file and its column list does "
                "not contain `c_node_dist` -- it has `c_edge_dist` and "
                "`c_distance`.  SQLite refuses the query, so the three "
                "buttons fail for every query result there can be.  The "
                "sibling forms (Associations, Association Pairs) do declare "
                "a `c_node_dist`, which is the likely origin of the name.",
        summary_zh="三者都從 `ZZ_SN_NETWORK` 讀取 `c_node_dist`。這個表由同一"
                   "個檔案建立，欄位清單中並沒有 `c_node_dist`，只有 "
                   "`c_edge_dist` 與 `c_distance`。SQLite 因此拒絕該查詢，"
                   "使得這三個按鈕對任何可能的查詢結果都失敗。相鄰的表單"
                   "（關聯、關聯配對）確實有宣告 `c_node_dist`，這很可能就是"
                   "欄位名稱的來源。",
        evidence="Each endpoint answers `500 Database error: no such column: "
                 "c_node_dist`, including when there is nothing to export -- "
                 "so the failure is in the statement, not in the data.  "
                 "Reading the shipped Go independently finds the same three "
                 "SELECTs and the CREATE TABLE they contradict.",
        evidence_zh="每個端點都回應 `500 Database error: no such column: "
                    "c_node_dist`，即使在沒有任何資料可匯出的情況下也一樣"
                    "——可見問題出在 SQL 敘述本身，而不是資料。另外獨立閱讀"
                    "釋出的 Go 原始碼，也找到同樣的三段 SELECT 以及與之矛盾的 "
                    "CREATE TABLE。",
        impact="The Networks form is the application's social-network tool "
               "and three of its four network formats cannot produce a file "
               "at all.  Only Neo4j works.",
        impact_zh="網絡表單是本程式的社會網絡分析工具，而它四種網絡格式中"
                  "有三種完全無法產出檔案，只有 Neo4j 可用。",
        fix="Decide which distance the three exports mean and use that "
            "column -- `c_edge_dist` is the one `ZZ_SN_NETWORK` populates "
            "for an edge -- or add `c_node_dist` to the CREATE TABLE and "
            "populate it.  A `PRAGMA table_info` check over each scratch "
            "table's declared columns at build time would have caught this, "
            "as `Code/qbe_schema_test.go` does for the Query Builder.",
        fix_zh="請先確定這三個匯出所指的「距離」究竟是什麼，然後改用對應的"
               "欄位——`ZZ_SN_NETWORK` 為每條邊所填入的是 `c_edge_dist`"
               "——或者在 CREATE TABLE 中加入 `c_node_dist` 並確實填值。"
               "若在建置階段對每個暫存表的宣告欄位做一次 `PRAGMA table_info` "
               "檢查，就能提前發現這個問題，正如 `Code/qbe_schema_test.go` "
               "對查詢建構器所做的那樣。",
        steps=(
            "Open the Networks form (/LookAtNetworks), select a person and "
            "run a query that returns edges.",
            "Press Pajek.  The request answers HTTP 500.",
            "Repeat with Gephi/GUESS and UCINet: the same error.",
            "Press Neo4j: that one produces its files.",
        ),
        steps_zh=(
            "開啟網絡表單（/LookAtNetworks），選定一個人物並執行一次會回傳"
            "邊的查詢。",
            "按下 Pajek：請求回傳 HTTP 500。",
            "以 Gephi/GUESS 與 UCINet 重複，得到相同錯誤。",
            "按下 Neo4j：這一個可以正常產生檔案。",
        ),
        source=("Code/networks_form_backend.go:2093",
                "Code/networks_form_backend.go:2216",
                "Code/networks_form_backend.go:2341",
                "Code/networks_form_backend.go:419"),
        tests=("test_an_export_produces_a_well_formed_file",
               "test_an_export_describes_the_people_the_"
               "grid_did",
               "test_an_export_is_repeatable",
               "test_an_export_with_no_result_does_not_"
               "invent_one",
               "test_no_query_asks_a_scratch_table_"
               "for_a_column_it_lacks",
               "test_a_delimited_file_uses_the_delimiter_its_suffix_"
               "promises",
               "test_every_row_of_a_delimited_file_is_as_wide_as_its_"
               "header",
               "test_a_column_that_has_to_hold_a_number_holds_one",
               "test_a_files_byte_order_mark_is_what_its_format_"
               "needs"),
    ),
    Defect(
        key="CBDB-D-005",
        priority="P2", severity="high", origin="software",
        title="The Associations form's Neo4j export answers HTTP 500 "
              "whenever the result has an address: a text column is scanned "
              "into an integer",
        title_zh="只要查詢結果帶有地址，關聯表單的 Neo4j 匯出就回傳 HTTP 500："
                 "程式把一個文字欄位讀進整數變數",
        area="Associations form, Neo4j export",
        area_zh="關聯表單的 Neo4j 匯出",
        summary="The export reads `ADDR_CODES.c_admin_type` into a Go struct "
                "field declared `AdminType int`.  That column is text: every "
                "one of its 30,100 rows holds a string such as \"Xian\" or "
                "\"Zhou\".  The scan therefore fails on the first address "
                "row and the whole export returns HTTP 500.",
        summary_zh="這個匯出把 `ADDR_CODES.c_admin_type` 讀進宣告為 "
                   "`AdminType int` 的 Go 結構欄位。該欄位其實是文字："
                   "全部 30,100 列都存放像 \"Xian\"、\"Zhou\" 這樣的字串。"
                   "因此第一列地址就讀取失敗，整個匯出回傳 HTTP 500。",
        evidence="The endpoint answers `500 Neo4j export error: scan "
                 "addrRow: sql: Scan error on column index 3, name "
                 "\"admin_type\": converting driver.Value type string "
                 "(\"Xian\") to a int: invalid syntax`.  The shipped schema "
                 "declares the column `varchar(255)`, and a read-only count "
                 "over the shipped database finds all 30,100 values are of "
                 "type text, the commonest being \"Xian\" (13,687 rows).  So "
                 "a rebuild of the data would not change it: the declared "
                 "type in the Go struct is wrong.\n\n"
                 "**The same column is read the same "
                 "wrong way a second time**, in "
                 "`networks_form_backend.go:handlePlaceSearch`, and the two "
                 "are worth reading together because they fail differently. "
                 " There the scan sits in a row loop whose error arm is `if "
                 "err := rows.Scan(...); err != nil { continue }`, so every "
                 "row is discarded along with the reason it failed, and the "
                 "handler encodes the empty slice with a 200: `GET "
                 "/api/networks/place-search?q=Zhou` returns `[]` where "
                 "20 rows were asked for and 5,136 match the predicate, so "
                 "not one row of the table can be found through it.  That instance is latent in this build, because "
                 "no page calls the endpoint (CBDB-D-011) -- which is why it "
                 "is recorded here rather than filed as something users can "
                 "see.  Both sites need the same small change -- scan "
                 "the column into the string it already is -- and the "
                 "`continue` is the more dangerous half: it turns a schema mismatch into a "
                 "search that succeeds and finds nothing.",
        evidence_zh="端點回應 `500 Neo4j export error: scan addrRow: sql: "
                    "Scan error on column index 3, name \"admin_type\": "
                    "converting driver.Value type string (\"Xian\") to a "
                    "int: invalid syntax`。釋出的結構描述把該欄位宣告為 "
                    "`varchar(255)`；以唯讀方式統計釋出的資料庫，30,100 個值"
                    "全部都是文字型別，最常見的是 \"Xian\"（13,687 列）。"
                    "因此重建資料不會改變結果：問題在於 Go 結構中宣告的型別"
                    "有誤。\n\n"
                    "**同一個欄位還有第二處以同樣錯誤的方式被讀取**，位於 "
                    "`networks_form_backend.go:handlePlaceSearch`；兩者值得"
                    "對照著看，因為它們失敗的方式並不相同。在那裡，讀取動作"
                    "位於一個逐列處理的迴圈中，錯誤分支是 `if err := "
                    "rows.Scan(...); err != nil { continue }`，於是每一列都"
                    "連同失敗的原因一起被丟棄，處理常式最後以 200 回傳一個"
                    "空陣列：`GET /api/networks/place-search?q=Zhou` "
                    "要求的是 20 列、符合其述詞的有 5,136 列，回傳的卻是 `[]`"
                    "——透過這個端點，資料表中沒有任何一列找得到。在這一版中該處是潛伏的，因為沒有任何頁面呼叫"
                    "這個端點（見 CBDB-D-011）——這也正是此處只作記錄、"
                    "而不另列為使用者看得到的缺陷的原因。兩處需要的是同一個小修正——把該欄位讀進"
                    "它本來就是的字串型別；而 `continue` 才是更危險的"
                    "一半："
                    "它把結構不符變成一次「成功卻什麼都找不到」的搜尋。",
        impact="The Associations form cannot export to Neo4j for any query "
               "whose people have addresses, which is almost all of them.  "
               "The user sees a server error.",
        impact_zh="只要查詢結果中的人物帶有地址（幾乎都會帶有），關聯表單就"
                  "無法匯出到 Neo4j，使用者只會看到伺服器錯誤。",
        fix="Declare the field `string` and read it as text -- the "
            "`COALESCE(c_admin_type, 0)` in the same SELECT should become "
            "`COALESCE(c_admin_type, '')` to match.\n\n"
            "The same mistake is in the build a second time, and it is not "
            "in another Neo4j export -- no other one scans this column.  It "
            "is `handlePlaceSearch` in `networks_form_backend.go`, which "
            "selects `COALESCE(c_admin_type, 0)` into an `AdminType int` and "
            "then `continue`s on a scan error, so it returns an empty list "
            "for every search instead of an error.  Nothing in the shipped "
            "templates calls that route today, which is why no user has "
            "reported it; it is worth fixing in the same commit rather than "
            "left to be found once something does.",
        fix_zh="把該欄位宣告為 `string` 並以文字讀取；同一段 SELECT 中的 "
               "`COALESCE(c_admin_type, 0)` 也應一併改為 "
               "`COALESCE(c_admin_type, '')` 以相符。\n\n"
               "同樣的錯誤在這一版中還有第二處，但不在別的 Neo4j 匯出裡"
               "——沒有其他匯出會讀這個欄位。那一處是 "
               "`networks_form_backend.go` 的 `handlePlaceSearch`：它同樣把 "
               "`COALESCE(c_admin_type, 0)` 讀進 `AdminType int`，而且在讀取"
               "失敗時直接 `continue`，因此任何搜尋都會回傳空清單，而不是"
               "回報錯誤。目前釋出的模板沒有任何地方會呼叫這個路由，這也是"
               "至今沒有使用者回報的原因；建議在同一次修改中一併處理，"
               "而不要留到某天真的有人用到它才被發現。",
        steps=(
            "Open the Associations form (/LookAtAssociations), pick an "
            "association code and run the query.",
            "Press Neo4j.",
            "The request answers HTTP 500 with the scan error above.",
        ),
        steps_zh=(
            "開啟關聯表單（/LookAtAssociations），選一個關聯代碼並執行查詢。",
            "按下 Neo4j。",
            "請求回傳 HTTP 500，錯誤訊息即為上述的讀取錯誤。",
        ),
        source=("Code/associations_form_backend.go:1377",
                "Code/associations_form_backend.go:1388",
                "Code/networks_form_backend.go:2987",
                "Data/cbdb.db.schema.sql:42"),
        tests=("test_an_export_produces_a_well_formed_file",
               "test_an_export_describes_the_people_the_"
               "grid_did",
               "test_an_export_is_repeatable",
               "test_a_spreadsheet_export_can_be_opened_"
               "by_a_spreadsheet",
               "test_a_delimited_file_uses_the_delimiter_its_suffix_"
               "promises",
               "test_every_row_of_a_delimited_file_is_as_wide_as_its_"
               "header",
               "test_a_column_that_has_to_hold_a_number_holds_one",
               "test_a_files_byte_order_mark_is_what_its_format_"
               "needs"),
    ),
    Defect(
        key="CBDB-D-006",
        priority="P2", severity="high", origin="software",
        title="The Query Builder offers 30 columns that the shipped views "
              "expose under a different name, and every one of them gives "
              "the user a server error",
        title_zh="查詢建構器提供了 30 個欄位，而釋出的檢視表其實是以另一個"
                 "名稱呈現它們；每一個都會讓使用者得到伺服器錯誤",
        area="The generated Query Builder schema, and the view definitions "
             "in CBDBSetUpCode",
        area_zh="產生出來的查詢建構器結構檔，以及 CBDBSetUpCode 中的"
                "檢視表定義",
        summary="Eight of the shipped views name 30 of their columns with a "
                "`:1` suffix -- `c_personid:1`, `c_notes:1`, `c_dy:1` and so "
                "on.  SQLite generates those names itself, because each of "
                "these views is a deeply nested Access-style join tree whose "
                "selected columns are not aliased explicitly.\n\n"
                "The column list the grid offers comes from "
                "`Data/qbe_schema.json`, generated by `gen_qbe_schema.py`.  "
                "That script *knows about this*: it detects the duplicate "
                "names, keeps only the first occurrence with the suffix "
                "removed, prints a warning, and its own header says \"the "
                "real fix is adding an explicit AS alias to the view "
                "definition\".  But it keeps the unsuffixed name on the "
                "assumption that this is \"how SQLite itself resolves an "
                "unqualified reference to one of several same-named "
                "columns\" -- and for these views that assumption is wrong.  "
                "The suffixed name is the one that works: "
                "`SELECT t.\"c_personid:1\" FROM View_Entry t` returns rows, "
                "while the unsuffixed `SELECT t.c_personid FROM View_Entry t` "
                "is refused.  So the generator took a name that could be "
                "queried and wrote down one that cannot, and for four of the "
                "views it is the first column offered, which makes the whole "
                "view look unusable.",
        summary_zh="釋出的檢視表中有八個，其 30 個欄位的名稱帶有 `:1` 後綴"
                   "——例如 `c_personid:1`、`c_notes:1`、`c_dy:1` 等。這些"
                   "名稱是 SQLite 自己產生的：這幾個檢視表都是層層嵌套的 "
                   "Access 風格連接（join）結構，而所選欄位又沒有明確取"
                   "別名。\n\n"
                   "介面提供的欄位清單來自 `Data/qbe_schema.json`，由 "
                   "`gen_qbe_schema.py` 產生。這支腳本其實**知道這個問題**："
                   "它會偵測到重複名稱，只保留第一個並去掉後綴，同時印出"
                   "警告，而且它自己的檔頭就寫著「真正的修法是在檢視表定義"
                   "中加上明確的 AS 別名」。但它保留不帶後綴的名稱，是基於"
                   "「SQLite 自己就是這樣解析對多個同名欄位的未限定參照」"
                   "這個假設——而對這幾個檢視表來說，這個假設是錯的。真正"
                   "可用的是帶後綴的名稱："
                   "`SELECT t.\"c_personid:1\" FROM View_Entry t` 可以取回"
                   "資料，而不帶後綴的 "
                   "`SELECT t.c_personid FROM View_Entry t` 則被拒絕。也就是"
                   "說，產生腳本把一個查得到的名稱換成了一個查不到的名稱；"
                   "其中四個檢視表受影響的還是清單中的第一個欄位，整個表"
                   "看起來就像完全不能用。",
        evidence="Driving the Query Builder through the running binary, all "
                 "30 combinations answer `500 Query failed: no such column`, "
                 "and for View_BiogInstAddrData, View_BiogInstData, "
                 "View_Entry and View_KinAddr that is the first column the "
                 "grid offers.  Reading the shipped database read-only, "
                 "`PRAGMA table_info` reports exactly those 30 columns with "
                 "a `:1` suffix across exactly those 8 views.  The naming is "
                 "reproducible from the view's own SELECT alone; the "
                 "suffixed name is queryable when quoted, the unsuffixed one "
                 "is not, and adding "
                 "an explicit `AS c_personid` to that SELECT removes the "
                 "suffix and makes `SELECT t.c_personid` succeed -- which "
                 "identifies the fix as well as the cause.",
        evidence_zh="透過執行中的程式操作查詢建構器，全部 30 種組合都回應 "
                    "`500 Query failed: no such column`；而對 "
                    "View_BiogInstAddrData、View_BiogInstData、View_Entry 與 "
                    "View_KinAddr 而言，那正是介面提供的第一個欄位。以唯讀"
                    "方式讀取釋出的資料庫，`PRAGMA table_info` 回報的正是這 8 "
                    "個檢視表中的這 30 個帶 `:1` 後綴的欄位。此命名僅由檢視表"
                    "自己的 SELECT 即可重現；在該 SELECT 中加上明確的 "
                    "`AS c_personid` 後，後綴消失，`SELECT t.c_personid` 也"
                    "隨即成功——這同時指出了原因與修法。",
        impact="A user of the Query Builder picks a column from the list the "
               "application itself offers and gets a server error.  Four "
               "views look entirely broken because their first offered "
               "column is one of these.",
        impact_zh="使用者從程式自己提供的清單中挑選欄位，卻得到伺服器錯誤。"
                  "其中四個檢視表因為第一個可選欄位就是這類欄位，看起來像是"
                  "整個壞掉了。",
        fix="`gen_qbe_schema.py`'s own header already names it: alias the "
            "colliding columns explicitly in the eight view definitions "
            "(`ENTRY_DATA.c_personid AS c_personid`).  That is the fix "
            "verified above -- it removes the suffix and makes "
            "`SELECT t.c_personid` succeed -- and it leaves the generated "
            "column list correct as it stands.\n\n"
            "Until that happens, the generator should not emit a name it "
            "cannot verify.  Its warning is printed at generation time, "
            "where nobody sees it again; a column whose name does not "
            "survive `SELECT t.<name> FROM <view> t LIMIT 0` would be "
            "better omitted from the JSON than offered to the user, and "
            "that check costs one query per column at generation time.  "
            "Emitting the real, suffixed name and quoting it in the "
            "generated SQL would also work -- it is the name that resolves "
            "-- but the alias is the better fix, because the label a "
            "scholar reads should not have a `:1` in it.",
        fix_zh="`gen_qbe_schema.py` 自己的檔頭已經指出修法：在這八個檢視表"
               "定義中為衝突的欄位明確取別名（例如 "
               "`ENTRY_DATA.c_personid AS c_personid`）。這正是上文已驗證"
               "有效的修法——後綴會消失，`SELECT t.c_personid` 也隨即成功"
               "——而且能讓已產生的欄位清單維持正確。\n\n"
               "在那之前，產生腳本不應輸出自己無法驗證的名稱。它的警告只在"
               "產生時印出一次，之後就再也沒人看到；若某個欄位名稱通不過 "
               "`SELECT t.<欄位> FROM <檢視表> t LIMIT 0`，那麼把它從 JSON "
               "中略去，會比提供給使用者更好——而這項檢查在產生階段只需要"
               "每個欄位一次查詢的成本。另一種可行做法是輸出真正的、帶"
               "後綴的名稱，並在產生的 SQL 中加上引號——因為那才是能解析"
               "的名稱；但取別名仍是更好的修法，畢竟研究者看到的欄位標題"
               "不該帶著 `:1`。",
        steps=(
            "Open the Query Builder (/QBE).",
            "Choose the view View_Entry.",
            "Select its first offered column, c_personid, and run.",
            "The request answers 500 `no such column: t.c_personid`.",
            "In the shipped database, PRAGMA table_info(View_Entry) shows "
            "the column is named `c_personid:1`.",
        ),
        steps_zh=(
            "開啟查詢建構器（/QBE）。",
            "選擇檢視表 View_Entry。",
            "選取它提供的第一個欄位 c_personid，然後執行。",
            "請求回傳 500 `no such column: t.c_personid`。",
            "在釋出的資料庫中執行 PRAGMA table_info(View_Entry)，可見該欄位"
            "的名稱其實是 `c_personid:1`。",
        ),
        source=("Data/gen_qbe_schema.py:52",
                "Data/qbe_schema.json:5456",
                "CBDBSetUpCode/CBDB_AdditionalTablesViewsIndices.sql:1254",
                "Code/qbe_schema.go:53"),
        tests=("test_every_offered_column_exists_in_the_"
               "database",
               "test_every_offered_table_can_actually_be_"
               "queried",
               "test_a_phantom_column_gives_the_user_a_server_"
               "error"),
    ),
    Defect(
        key="CBDB-D-007",
        priority="P3", severity="low", origin="release",
        title="The distribution ships ten dated working copies of its own "
              "templates",
        title_zh="發行檔中一併附上了十份帶日期的模板工作副本",
        area="Packaging: Templates/",
        area_zh="封裝內容：Templates/",
        summary="Ten of the archive's 85 members are dated backups of "
                "templates that ship alongside the live file -- "
                "`entry/entry.index.20260906.html` next to "
                "`entry/index.html`, `qbe/qbe.20260827.html` next to "
                "`qbe/qbe.html`, and so on.  No route serves them and only "
                "`Static/` is file-served, so they are not reachable pages; "
                "they are a working directory that was packaged as it "
                "stood.",
        summary_zh="壓縮檔 85 個成員中有 10 個，是與正式檔案並存的帶日期模板"
                   "備份——例如 `entry/entry.index.20260906.html` 與 "
                   "`entry/index.html` 並列、`qbe/qbe.20260827.html` 與 "
                   "`qbe/qbe.html` 並列等。沒有任何路由會提供這些檔案，且"
                   "只有 `Static/` 是以檔案伺服方式對外，因此它們並不是可被"
                   "存取的頁面；這是把工作目錄照原樣打包的結果。",
        evidence="Read from the archive's own directory, not from the "
                 "unpacked tree: `Templates/associations/associations.index."
                 "20260906.html`, `associations.index.20260908.html`, "
                 "`entry/entry.index.20260906.html`, `networks/networks."
                 "index.20260813.html`, `office/office.index.20260815.html`, "
                 "`pickers/address_picker.20260729.html`, `places/places."
                 "index.20260906.html`, `qbe/qbe.20260827.html`, "
                 "`status/status.index.20260816.html` and `texts/texts."
                 "index.20260815.html`.  Diffing one against its live "
                 "sibling shows it is genuinely older: the 20260906 copy of "
                 "the Entry page has no `chkUseXY` control, which the "
                 "shipped page has.",
        evidence_zh="以下清單讀自壓縮檔自身的目錄，而非解開後的目錄樹："
                    "`Templates/associations/associations.index.20260906."
                    "html`、`associations.index.20260908.html`、"
                    "`entry/entry.index.20260906.html`、`networks/networks."
                    "index.20260813.html`、`office/office.index.20260815."
                    "html`、`pickers/address_picker.20260729.html`、"
                    "`places/places.index.20260906.html`、"
                    "`qbe/qbe.20260827.html`、`status/status.index.20260816."
                    "html`、`texts/texts.index.20260815.html`。把其中一份與"
                    "其正式版本相比，可確認確實較舊：20260906 版的入仕頁面"
                    "沒有 `chkUseXY` 這個控制項，而釋出的頁面有。",
        impact="Small but not nil.  It makes the released tree ambiguous "
               "about which template is current, it puts pre-release working "
               "state in users' hands, and it is the kind of slip that "
               "eventually ships a stale file *as* the live one.  Here it "
               "also shows up as three test failures, because the suite "
               "enumerates the pages and buttons it finds in the build "
               "rather than a list of its own.",
        impact_zh="影響不大，但並非沒有影響。它使釋出的目錄樹難以判斷哪一份"
                  "模板才是最新版本，也把未正式發行的工作狀態交到使用者手上；"
                  "而且正是這類疏漏，最終可能讓過時的檔案「以正式檔案的身分」"
                  "被釋出。在本次測試中，它同時造成三項測試失敗，因為本套件"
                  "是依據建置內容自行列舉頁面與按鈕，而不是比對一份自備清單。",
        fix="Build the distribution from a clean export rather than from the "
            "working directory, or exclude `*.<date>.html` when packaging.  "
            "The backups themselves are useful; they just belong in version "
            "control rather than in the release.",
        fix_zh="請以乾淨的匯出結果來製作發行檔，而不要直接打包工作目錄；"
               "或在封裝時排除 `*.<日期>.html`。這些備份本身有其用處，只是"
               "它們該放在版本控制中，而不是發行檔裡。",
        steps=(
            "List the archive's contents: 7z l CBDB-Desktop_20260908.7z",
            "Note the ten Templates/ members whose names carry a date.",
            "Diff any one of them against index.html in the same directory.",
        ),
        steps_zh=(
            "列出壓縮檔內容：7z l CBDB-Desktop_20260908.7z",
            "留意 Templates/ 之下十個名稱帶日期的成員。",
            "任選其中一個，與同目錄下的 index.html 進行比對。",
        ),
        source=("Templates/pickers/address_picker.20260729.html",
                "Templates/qbe/qbe.20260827.html",
                "Templates/entry/entry.index.20260906.html"),
        tests=("test_the_distribution_ships_no_dated_working_copies",
               "test_distribution_ships_the_expected_pieces",
               "test_every_page_has_the_buttons_it_"
               "shipped_with",
               "test_every_disabled_control_has_a_"
               "declared_precondition"),
    ),
    Defect(
        key="CBDB-D-008",
        priority="P0", severity="high", origin="software",
        title="The Networks page drops the four year fields its dynasty "
              "filter is built on, and a two-dynasty span collapses to a "
              "single person",
        title_zh="網絡表單遺漏了朝代篩選所依據的四個年份欄位，"
                 "跨兩個朝代的區間因而只剩下一個人",
        area="Networks: dynasty range",
        area_zh="網絡表單：朝代範圍",
        summary="`buildDynastyConditions` filters on the *years* a dynasty "
                "spans, not on its code: `DYNASTIES_1.c_end > "
                "FromDynastyBegin` and `DYNASTIES_1.c_start < "
                "ToDynastyEnd`.  The page computes those four numbers when "
                "the dynasty picker returns -- `gFromDynastyBegin` and "
                "friends -- and then builds `const params={...}` without "
                "them, so the handler reads all four as 0.  Three "
                "user-visible consequences follow, and there is no fourth "
                "way to choose a dynasty on this page: every dynasty "
                "choice goes through this one path.",
        summary_zh="`buildDynastyConditions` 篩選的是朝代所跨越的**年份**，"
                   "而不是朝代代碼：`DYNASTIES_1.c_end > FromDynastyBegin` "
                   "與 `DYNASTIES_1.c_start < ToDynastyEnd`。頁面在朝代選擇"
                   "視窗回傳時已算出這四個數字（`gFromDynastyBegin` 等），"
                   "但組 `const params={...}` 時並未帶上，因此後端讀到的四個"
                   "值都是 0。由此產生三種使用者可見的後果；而這個頁面並沒有"
                   "第四種選擇朝代的方式：所有朝代選擇都走這同一條路徑。",
        evidence="Driven against person 1762 at depth 1, all four kinship "
                 "limits at 1, counting distinct people in `nodeRecords`, "
                 "with the two dynasties and their year bounds read out of "
                 "`DYNASTIES` rather than hand-picked -- Song (960-1279) to "
                 "Western Xia (1032-1227):  no dynasty filter, 441; one "
                 "dynasty, 429; **From only, 439** -- `c_end > 0` holds for 80 of "
                 "the 85 rows in `DYNASTIES`, so the filter the user asked "
                 "for is very nearly a no-op, and the two people it does "
                 "drop are the measurable trace of that; **two dynasties, 1** -- `c_start < 0` is true of "
                 "five dynasties out of eighty-five, so the answer collapses "
                 "with no message; **All Dynasties, HTTP 500** `Database "
                 "error: no such column: DYNASTIES_1.c_end` -- the page's "
                 "own button sets both codes to a `-2` sentinel that slips "
                 "past the handler's \"neither boundary set\" guard and "
                 "builds a condition on a table the chosen FROM clause never "
                 "joined.  The decisive comparison is the last: sending the "
                 "identical request **with** the four year fields the page "
                 "computed gives 433, so the handler is right and the page "
                 "is what is broken.  The build contains its own control -- "
                 "the Association Pairs page solves the same problem "
                 "correctly, sending `allDynasties: true` as a boolean "
                 "instead of an out-of-band code, and sending both year "
                 "bounds with each dynasty into nil-able `*int` fields that "
                 "can tell \"unset\" from \"0\".  The pattern that works is "
                 "one form away.",
        evidence_zh="以人物 1762、深度 1、四項親屬上限皆為 1 進行實測，統計 "
                    "`nodeRecords` 中的不重複人數；所用的兩個朝代及其年份界線"
                    "是從 `DYNASTIES` 讀出、而非人工挑選——宋（960-1279）至"
                    "西夏（1032-1227）：不加朝代篩選為 441；單一朝代為 429；"
                    "**只設起始朝代為 439**——`c_end > 0` 在 `DYNASTIES` 的 85 列中"
                    "有 80 列成立，因此使用者要求的篩選幾乎等於沒有生效，"
                    "而少掉的那兩個人正是它留下的可量測痕跡；**跨兩個朝代為 1**——"
                    "`c_start < 0` 在八十五個朝代中只有五個成立，結果因而塌縮，"
                    "且沒有任何提示；**「All Dynasties」為 HTTP 500**，訊息為 "
                    "`Database error: no such column: DYNASTIES_1.c_end`——"
                    "頁面本身的按鈕把兩個代碼都設成 `-2` 哨兵值，繞過了後端"
                    "「兩端皆未設定」的判斷，於是對一張所選 FROM 子句根本沒有"
                    "連接的資料表加上了條件。最關鍵的是最後一組對照：把同一個"
                    "請求**補上**頁面已算好的四個年份欄位後得到 433，"
                    "可見後端是對的，出問題的是頁面。建置本身也提供了對照組"
                    "——關聯配對頁面把同一個問題處理對了：它以布林值送出 "
                    "`allDynasties: true`，而不是把「全部」編碼成一個額外的"
                    "代碼；而且每選一個朝代，都會連同兩個年份界線一併送出，"
                    "接收端是可為 nil 的 `*int`，分得出「未設定」與「0」。"
                    "可行的作法，就在隔壁一張表單上。",
        impact="A researcher who narrows a network to a span of two "
               "dynasties gets one person back and no indication that "
               "anything went wrong; the natural reading is that the data "
               "is thin, and the result is publishable-looking and false.  "
               "From-only returns 439 of the 441 people an unfiltered "
               "query returns, so the filter the user set is very nearly "
               "not applied at all.  All "
               "Dynasties fails outright.",
        impact_zh="研究者若把網絡限縮在橫跨兩個朝代的區間，只會得到一個人，"
                  "而且沒有任何跡象顯示出了問題；最自然的解讀是「資料本來就"
                  "少」，於是得到一份看起來可以發表、實際上卻是錯的結果。"
                  "只設起始朝代時，未篩選查詢回傳 441 人，它回傳 439 人，"
                  "等於使用者所設的篩選幾乎完全沒有生效。而「All "
                  "Dynasties」則直接失敗。",
        fix="Send `fromDynastyBegin`, `fromDynastyEnd`, `toDynastyBegin` and "
            "`toDynastyEnd` in `params`; the page already has all four in "
            "globals, and the Association Pairs page shows the shape.  "
            "Separately, give the handler an explicit `-2` case, or stop the "
            "page sending a sentinel the handler does not define -- and make "
            "the guard reject an unrecognised code rather than build SQL "
            "from it.",
        fix_zh="請在 `params` 中一併送出 `fromDynastyBegin`、`fromDynastyEnd`、"
               "`toDynastyBegin` 與 `toDynastyEnd`；這四個值頁面已存於全域"
               "變數中，而關聯配對頁面也已示範了正確的寫法。另外，請在後端"
               "明確處理 `-2` 這個情形，或不要讓頁面送出後端未定義的哨兵值"
               "——並讓判斷式在遇到無法識別的代碼時直接拒絕，而不是拿它去"
               "組 SQL。",
        steps=(
            "Open Networks, choose a person with a large network (1762).",
            "Set From Dynasty = Song and To Dynasty = Western Xia, then "
            "press Run Query.",
            "Note the result: one node, no message.",
            "Press All Dynasties and Run Query: HTTP 500.",
        ),
        steps_zh=(
            "開啟網絡表單，選一位網絡較大的人物（1762）。",
            "將起始朝代設為宋、迄止朝代設為西夏，然後按 Run Query。",
            "觀察結果：只有一個節點，且沒有任何提示。",
            "改按「All Dynasties」再執行查詢：HTTP 500。",
        ),
        source=("Code/networks_form_query.go:buildDynastyConditions",
                "Templates/networks/index.html:704",
                "Templates/networks/index.html:1054"),
        tests=("test_the_networks_page_sends_the_dynasty_span_its_handler_"
               "needs",),
    ),
    Defect(
        key="CBDB-D-009",
        priority="P2", severity="high", origin="software",
        title="Four Association Pairs export buttons report \"Unknown "
              "error\" on exports that succeeded",
        title_zh="關聯配對頁面有四個匯出按鈕，在匯出其實已成功時仍回報"
                 "「Unknown error」",
        area="Association Pairs: exports",
        area_zh="關聯配對：匯出",
        summary="`exportGIS`, `exportSNA` and `exportNeo4j` in the page "
                "share one recipe: post, then `if (j.status !== 'ok') throw "
                "new Error(j.status || 'Unknown error')`, then "
                "`j.files.forEach(...)`.  Two of the four handlers answer "
                "`{\"status\":\"ok\",\"files\":[...]}`, which that reads.  "
                "`handleExportGIS` and `handleExportSNA` answer "
                "`{\"url\":...,\"name\":...}` instead, so `undefined !== "
                "'ok'` is true and the page throws -- on an HTTP 200 whose "
                "body holds the finished file, correctly built.",
        summary_zh="頁面中的 `exportGIS`、`exportSNA` 與 `exportNeo4j` 共用"
                   "同一套寫法：送出請求，接著 `if (j.status !== 'ok') throw "
                   "new Error(j.status || 'Unknown error')`，然後 "
                   "`j.files.forEach(...)`。四個處理常式中有兩個回傳 "
                   "`{\"status\":\"ok\",\"files\":[...]}`，正好是這套寫法讀"
                   "得懂的格式。但 `handleExportGIS` 與 `handleExportSNA` "
                   "回傳的是 `{\"url\":...,\"name\":...}`，於是 `undefined "
                   "!== 'ok'` 成立、頁面丟出例外——而該次請求其實是 HTTP "
                   "200，內容正是已經正確產生好的檔案。",
        evidence="Posting the smallest body each handler's own guard admits "
                 "(`people` with one row): `/api/assocpairs/export-gis` and "
                 "`/api/assocpairs/export-sna` both answer 200 with keys "
                 "`['name', 'url']`; `/api/assocpairs/export-neo4j`, in the "
                 "same file, answers with `status` and `files`, as does "
                 "`export-results` beside it.  So this is "
                 "a disagreement inside one file rather than a convention "
                 "imposed from outside.  Four buttons are affected: Save to "
                 "GIS, and the three SNA formats (Pajek, Gephi, UCINet) that "
                 "share `export-sna`.\n\nThis reverses a judgement recorded "
                 "in this project's own AGENTS.md, which listed the "
                 "inconsistent export envelopes as *not* a defect \"because "
                 "no user can see it\".  That was decided by reading the "
                 "handlers, which agree with each other; no page had been "
                 "read.  On this form a user does see it, and AGENTS.md is "
                 "amended in the same change.",
        evidence_zh="以各處理常式自身判斷所能接受的最小請求主體（`people` "
                    "只有一列）送出：`/api/assocpairs/export-gis` 與 "
                    "`/api/assocpairs/export-sna` 都回傳 200，鍵為 "
                    "`['name', 'url']`；而同一個檔案中的 "
                    "`/api/assocpairs/export-neo4j` 回傳的則是 `status` 與 "
                    "`files`，與它並列的 `export-results` 也是如此。可見這是"
                    "同一個檔案內部的不一致，而不是外部強加"
                    "的規範。受影響的按鈕共四個：Save to GIS，以及共用 "
                    "`export-sna` 的三種 SNA 格式（Pajek、Gephi、UCINet）。"
                    "\n\n本項推翻了本專案 AGENTS.md 中原有的判斷——該文件曾"
                    "把匯出封裝格式不一致列為「並非缺陷」，理由是「使用者看"
                    "不到」。當初那個判斷只讀了後端，而後端彼此是一致的，"
                    "並沒有讀任何頁面。在這個表單上使用者確實看得到，因此"
                    "本次一併修訂了 AGENTS.md。",
        impact="Four of this form's six export buttons cannot be used.  The "
               "message names no cause, so a user has nothing to act on, and "
               "because the server side is in fact correct the fault is "
               "invisible to anything that tests handlers alone.",
        impact_zh="這個表單六個匯出按鈕中有四個無法使用。錯誤訊息沒有指出"
                  "任何原因，使用者無從處理；又因為伺服器端其實是正確的，"
                  "任何只測試後端的方法都看不見這個問題。",
        fix="Make the two odd handlers answer in the shape the page reads "
            "-- `{\"status\":\"ok\",\"files\":[{name,url}]}` -- which is "
            "what their two siblings already do.  Changing the page instead "
            "would mean three call sites diverging again the next time an "
            "export is added.",
        fix_zh="請讓這兩個格式不同的處理常式改以頁面讀得懂的形式回應——"
               "`{\"status\":\"ok\",\"files\":[{name,url}]}`——這也正是"
               "另外兩個同類處理常式已經在用的格式。若改頁面而不改後端，"
               "下次新增匯出功能時，三處呼叫點又會再度分歧。",
        steps=(
            "Open Look At Association Pairs and run any query.",
            "Press Save to GIS.  The page shows \"GIS export error: Unknown "
            "error\" and downloads nothing.",
            "Watch the same request in the browser's network panel: 200, "
            "with the file base64-encoded in the body.",
        ),
        steps_zh=(
            "開啟關聯配對頁面，執行任一查詢。",
            "按下 Save to GIS。頁面顯示「GIS export error: Unknown error」，"
            "且沒有任何檔案下載。",
            "在瀏覽器的網路面板中觀察同一個請求：狀態為 200，內容正是以 "
            "base64 編碼的檔案。",
        ),
        source=("Code/assocpairs_form_backend.go:handleExportGIS",
                "Code/assocpairs_form_backend.go:handleExportSNA",
                "Templates/association_pairs/index.html:960",
                "Templates/association_pairs/index.html:1002"),
        tests=("test_an_assocpairs_export_answers_in_the_envelope_its_page_"
               "reads",),
    ),
    Defect(
        key="CBDB-D-010",
        priority="P0", severity="high", origin="software",
        title="Three controls the user can set change nothing: the "
              "Association Pairs KML checkbox, and Networks' Max Loops and "
              "Include ID",
        title_zh="有三個使用者可以設定的控制項不起作用：關聯配對的 KML "
                 "核取方塊，以及網絡表單的 Max Loops 與 Include ID",
        area="Association Pairs, Networks: dead controls",
        area_zh="關聯配對、網絡表單：無作用的控制項",
        summary="Each is read from the DOM, sent in the request, and then "
                "not read.  The Association Pairs page posts `useKML`; "
                "`AssocPairsExportParams` declares `format`, `network` and "
                "`people`, so the key never binds and `handleExportGIS` "
                "branches on a `format` this page never sends.  The Networks "
                "page posts `maxLoop` and `includeID`; `NetworkQuery` "
                "declares `MaxLoop` and `IncludeID`, and no line of Go under "
                "`Code/` mentions either identifier again.",
        summary_zh="這三者都會從 DOM 讀出、隨請求送出，然後就沒有人讀它了。"
                   "關聯配對頁面送出 `useKML`，而 `AssocPairsExportParams` "
                   "宣告的是 `format`、`network` 與 `people`，這個鍵因此從未"
                   "生效，`handleExportGIS` 所判斷的 `format` 則是該頁面從不"
                   "送出的欄位。網絡表單送出 `maxLoop` 與 `includeID`，"
                   "`NetworkQuery` 也確實宣告了 `MaxLoop` 與 `IncludeID`，"
                   "但 `Code/` 之下的 Go 原始碼中，這兩個識別字再也沒有"
                   "出現過。",
        evidence="**KML.**  The page's request to `export-gis` carries "
                 "`['useKML']`; the handler's params struct declares "
                 "`['format', 'network', 'people']`.  Driven both ways, the "
                 "reply names `assocpairs_network.tsv` either way, so "
                 "`assocWriteKML` is unreachable from the only page that "
                 "offers it (CBDB-D-011 counts it among the capabilities "
                 "with no way in).\n\n**Max Loops and Include ID.**  "
                 "Surveying every `json:`-tagged field in `Code/*.go` "
                 "against every mention of its name turns up exactly three "
                 "whose identifier occurs once, in its own declaration.  Two "
                 "are `NetworkQuery.MaxLoop` and `NetworkQuery.IncludeID`, "
                 "and the Networks page sends both -- `maxLoop: "
                 "parseInt(document.getElementById('txt-max-loop').value,10)"
                 "||2` and `includeID: "
                 "document.getElementById('chk-include-id').checked`.  The "
                 "third, `KinRecord.KinRel0`, is a response field no page "
                 "reads: inert rather than a defect, and named here so the "
                 "count above can be checked.",
        evidence_zh="**KML。**頁面送往 `export-gis` 的請求帶的是 "
                    "`['useKML']`，而後端參數結構宣告的是 `['format', "
                    "'network', 'people']`。兩種情況都實際呼叫過，回傳的"
                    "檔名都是 `assocpairs_network.tsv`，可見 "
                    "`assocWriteKML` 從唯一提供該選項的頁面根本到不了"
                    "（CBDB-D-011 已把它計入沒有任何入口的功能之中）。"
                    "\n\n**Max Loops 與 Include ID。**把 `Code/*.go` 中"
                    "所有帶 `json:` 標籤的欄位與其名稱的所有出現次數逐一"
                    "比對，恰好有三個欄位的識別字只出現過一次，就是它自己"
                    "的宣告。其中兩個是 `NetworkQuery.MaxLoop` 與 "
                    "`NetworkQuery.IncludeID`，而網絡表單兩者都會送出——"
                    "`maxLoop: parseInt(document.getElementById"
                    "('txt-max-loop').value,10)||2` 與 `includeID: "
                    "document.getElementById('chk-include-id').checked`。"
                    "第三個 `KinRecord.KinRel0` 是回應欄位、沒有任何頁面"
                    "會讀取，屬於無害而非缺陷；此處一併點名，是為了讓上面"
                    "那個數字可以被查核。",
        impact="Max Loops is a numeric input offered between 1 and 10 whose "
               "traversal depth is fixed by something else, and Include ID "
               "in Output changes no output: both are settings a user can "
               "change, and changing them changes nothing.  The KML "
               "checkbox is the same fault with a further consequence -- "
               "because it never binds, the KML writer behind it can only "
               "be reached by calling the endpoint directly.  On this build "
               "a user does not even get the TSV: CBDB-D-009 means the page "
               "reports \"GIS export error: Unknown error\" and downloads "
               "nothing.  Fixing that envelope alone would hand the user a "
               "TSV with the KML box ticked, which is why the two belong in "
               "the same change.",
        impact_zh="Max Loops 是一個標示範圍 1 到 10 的數值輸入框，但它所指"
                  "的展開深度其實由別的東西決定；Include ID in Output 則不會"
                  "改變任何輸出：兩者都是使用者可以更動的設定，而更動它們"
                  "不會有任何效果。KML 核取方塊是同一種毛病，但還多了一層"
                  "後果——因為它從未生效，它背後的 KML 輸出程式就只能靠"
                  "直接呼叫端點才到得了。而在這一版上，使用者連 TSV 都拿"
                  "不到：依 CBDB-D-009，頁面會顯示「GIS export error: "
                  "Unknown error」且不會下載任何東西。若只修好那個封裝格式，"
                  "使用者就會在勾選 KML 的情況下拿到一個 TSV——這正是"
                  "兩者應該在同一次修改中一併處理的原因。",
        fix="For KML: send `format` from this page as its siblings do, or "
            "have the handler read `useKML` -- and fix CBDB-D-009 in the "
            "same change, or the box still appears to do nothing.  For the "
            "two Networks fields: wire them to the traversal and the "
            "writers, or remove the controls.  A control that is present "
            "and inert is worse than one that is absent, because a user who "
            "sets it believes the result reflects it.",
        fix_zh="關於 KML：請讓這個頁面比照同類頁面送出 `format`，或讓後端"
               "改為讀取 `useKML`——並請在同一次修改中一併處理 "
               "CBDB-D-009，否則這個核取方塊看起來仍然毫無作用。關於網絡"
               "表單的兩個欄位：請將它們實際接到展開邏輯與輸出程式，否則"
               "就把控制項移除。一個存在卻毫無作用的控制項，比根本沒有這個"
               "控制項更糟，因為使用者設定了它，就會相信結果反映了它。",
        steps=(
            "Open Networks, set Max Loops to 1, run a query, then set it to "
            "10 and run again.  Compare the two result sets.",
            "Tick Include ID in Output, export, and compare the columns.",
            "For KML, read the request the Association Pairs page builds: "
            "it posts useKML, and AssocPairsExportParams has no such field.",
        ),
        steps_zh=(
            "開啟網絡表單，將 Max Loops 設為 1 執行查詢，再設為 10 執行"
            "一次，比較兩次的結果集。",
            "勾選 Include ID in Output，執行匯出，再比較欄位。",
            "至於 KML，請直接檢視關聯配對頁面所組出的請求：它送的是 "
            "useKML，而 AssocPairsExportParams 並沒有這個欄位。",
        ),
        source=("Code/assocpairs_form_backend.go:handleExportGIS",
                "Code/networks_form_backend.go:NetworkQuery",
                "Templates/association_pairs/index.html:173",
                "Templates/networks/index.html:1071"),
        tests=("test_the_assocpairs_kml_checkbox_changes_what_comes_back",
               "test_a_field_the_json_declares_is_a_field_the_program_uses"),
    ),
    Defect(
        key="CBDB-D-011",
        priority="P5", severity="medium", origin="software",
        title="Five shipped capabilities have no way in: Group Data's KML "
              "exports, Association Pairs' KML writer, two autocomplete "
              "endpoints, and the Places ASCII encoding",
        title_zh="有五項已隨版釋出的功能沒有任何入口：分群資料的 KML 匯出、"
                 "關聯配對的 KML 輸出程式、兩個自動完成端點，"
                 "以及地點表單的 ASCII 編碼",
        area="Group Data, Association Pairs, Networks, Places: unreachable "
             "features",
        area_zh="分群資料、關聯配對、網絡表單、地點：無法觸及的功能",
        summary="Five pieces of finished work that no user of this build can "
                "reach.  `groupdata_form_backend.go` has six `req.Format == "
                "\"kml\"` branches and `Templates/group_data/index.html` "
                "does not contain the letters `kml` at all.  Association "
                "Pairs has the letters and not the binding: its checkbox "
                "sends a key the handler does not read (CBDB-D-010), so "
                "`assocWriteKML` is unreachable too.  "
                "`/api/networks/place-search` and "
                "`/api/networks/person-search` are routed, implemented, and "
                "called by no template.  And `handleExportPajek` accepts "
                "`encoding: \"ascii\"` while all five of the Places page's "
                "export calls send the literal `'unicode'`.",
        summary_zh="這是五項已經完成、但這一版的使用者都到不了的工作。"
                   "`groupdata_form_backend.go` 有六處 `req.Format == "
                   "\"kml\"` 分支，而 `Templates/group_data/index.html` "
                   "之中根本沒有出現 `kml` 這三個字母。關聯配對則是有字母"
                   "而沒有接線：它的核取方塊送出的鍵，後端並不讀取"
                   "（見 CBDB-D-010），因此 `assocWriteKML` 同樣到不了。"
                   "`/api/networks/place-search` 與 "
                   "`/api/networks/person-search` 都已有路由、已實作，"
                   "卻沒有任何模板呼叫。而 `handleExportPajek` 接受 "
                   "`encoding: \"ascii\"`，但地點頁面五處匯出呼叫送出的"
                   "都是寫死的 `'unicode'`。",
        evidence="Every backend that branches on `\"kml\"` was checked "
                 "against its own page for any mention of `kml` in any form "
                 "-- a control id, a value, a comment.  Nine backends carry "
                 "such a branch and eight pass that test; `group_data` is "
                 "the one that fails it outright, with six branches and no "
                 "mention.  Association Pairs passes it only on the literal "
                 "`chkKML` in its markup, which CBDB-D-010 shows is a "
                 "mention and not a route: hence five here rather than "
                 "four.\n\nFor the endpoints, every `/api/` route in "
                 "`Code/*.go` was matched against every live template under "
                 "`Templates/`, **pickers included** -- which matters, since "
                 "both endpoints name a picker as their caller, and a survey "
                 "reading only the form pages would have got the right "
                 "answer for the wrong reason.  Exactly two routes have no "
                 "caller, and they are those two.\n\nFor the encoding, "
                 "`grep` finds `encoding: 'unicode'` at five call sites in "
                 "`Templates/places/index.html` (656, 683, 747, 764, 781) "
                 "and the string `ascii` in no template at all.  Driving "
                 "the endpoint directly shows the branch works and one "
                 "thing in it does not: with `encoding=\"ascii\"` the "
                 "labels do switch to pinyin -- past the mark the file holds "
                 "0 byte values above 0x7F against 18 in the unicode one -- "
                 "yet `handleExportPajek` prepends `utf8BOM` "
                 "unconditionally, so the file it names `network_ascii.net` "
                 "opens with `EF BB BF`.  That last part is a defect in "
                 "unreachable code, recorded here for whoever connects the "
                 "control rather than filed as something users can see.",
        evidence_zh="所有會依 `\"kml\"` 分支的後端檔案，都與其對應頁面"
                    "比對過「頁面中是否以任何形式出現 `kml`」——控制項 id、"
                    "值、註解皆可。共有九個後端含有這類分支，其中八個通過；"
                    "`group_data` 是徹底沒通過的那一個，有六處分支而頁面中"
                    "完全沒有提及。關聯配對之所以通過，只因為它的標記中有 "
                    "`chkKML` 這個字面；而 CBDB-D-010 已說明那只是「提到」"
                    "而非「接通」——因此這裡是五項而不是四項。\n\n至於"
                    "端點，則是把 `Code/*.go` 中所有 `/api/` 路由，與 "
                    "`Templates/` 之下所有仍在使用的模板逐一比對，**且包含"
                    "各選擇視窗**——這一點很重要，因為這兩個端點都指名某個"
                    "選擇視窗為其呼叫者，若只讀表單頁面，即使結論正確也是"
                    "碰巧。結果恰好有兩條路由沒有任何呼叫者，正是這兩個。"
                    "\n\n關於編碼，以 `grep` 檢索可見 "
                    "`Templates/places/index.html` 有五處呼叫送出 "
                    "`encoding: 'unicode'`（第 656、683、747、764、781 行），"
                    "而 `ascii` 這個字串則不存在於任何模板中。直接呼叫端點"
                    "可以看出這個分支是有作用的，但其中有一件事沒做到："
                    "以 `encoding=\"ascii\"` 呼叫時，標籤確實改用拼音"
                    "——記號之後，該檔案中沒有任何位元組值超過 0x7F，"
                    "unicode 檔案則有 18 個——然而 `handleExportPajek` "
                    "是無條件加上 `utf8BOM` 的，因此它命名為 "
                    "`network_ascii.net` 的檔案，開頭是 `EF BB BF`。"
                    "最後這一點是「到不了的程式碼中的缺陷」，記在此處是"
                    "留給日後接上該控制項的人參考，而不是列為使用者看得到"
                    "的問題。",
        impact="The GIS output a Group Data user can actually obtain is "
               "tab-separated only, so `groupWriteKMLStatus`, "
               "`groupWriteKMLOffice` and `groupWriteKMLOfficePeople` are "
               "code no user can run, and the mapping workflow the other "
               "forms offer is missing there.  Neither picker has the "
               "autocomplete that was written for it.  The Places export "
               "offers one encoding of the two it implements.  None of this "
               "puts a wrong answer on screen -- it is finished work that "
               "shipped without its last connection.  Whether the "
               "unreachable code is itself correct is a separate question, "
               "and twice here the answer is no: the BOM above, and the "
               "scan bug in `place-search` recorded under CBDB-D-005.  That "
               "is the cost of an unreachable feature -- nothing exercises "
               "it, so nothing tells anyone it is broken.",
        impact_zh="分群資料的使用者實際上只能拿到定位字元分隔的 GIS 輸出，"
                  "因此 `groupWriteKMLStatus`、`groupWriteKMLOffice` 與 "
                  "`groupWriteKMLOfficePeople` 是任何使用者都執行不到的"
                  "程式碼，其他表單所提供的地圖工作流程在該處也付之闕如。"
                  "兩個選擇視窗都沒有原本為它們寫好的自動完成功能。地點的"
                  "匯出實作了兩種編碼，卻只提供其中一種。這些都不會在畫面上"
                  "產生錯誤的結果——它們是少接了最後一段線路就釋出的成果。"
                  "至於這些到不了的程式碼本身是否正確，是另一個問題；"
                  "而此處有兩個地方答案是否定的：上述的位元組順序記號，"
                  "以及記錄在 CBDB-D-005 之下、`place-search` 中的讀取"
                  "錯誤。這正是「功能到不了」的代價——沒有任何東西會執行"
                  "到它，於是也沒有任何東西會告訴別人它壞了。",
        fix="Add the format control to the Group Data GIS exports, matching "
            "the other forms; make the Association Pairs checkbox bind "
            "(CBDB-D-010); give the Places export an encoding control, or "
            "drop the branch.  For the two search endpoints, either wire "
            "the pickers to them or remove the routes.  Whichever way each "
            "one goes, decide it deliberately: an endpoint nothing calls is "
            "a maintenance cost with no user, and two of these have been "
            "carrying bugs nobody could have hit.",
        fix_zh="請比照其他表單，為分群資料的 GIS 匯出加上格式選擇控制項；"
               "讓關聯配對的核取方塊真正生效（見 CBDB-D-010）；為地點的"
               "匯出加上編碼選擇控制項，否則就移除該分支。至於兩個搜尋"
               "端點，請將對應的選擇視窗接上它們，或是移除這些路由。"
               "無論每一項最後如何處置，都請是有意識地決定：一個沒有任何"
               "呼叫者的端點，只是有維護成本而沒有使用者；而這幾項之中"
               "有兩項，一直帶著沒有人碰得到的錯誤。",
        steps=(
            "Open Group Data and look for a KML option beside any GIS "
            "export.  There is none; searching the page for \"kml\" finds "
            "nothing either.",
            "Search every file under Templates/ for \"place-search\" and "
            "\"person-search\": no hits outside the Go source.",
            "Search Templates/places/index.html for \"encoding\": five "
            "hits, all the literal 'unicode'.",
        ),
        steps_zh=(
            "開啟分群資料頁面，在任一 GIS 匯出旁尋找 KML 選項——找不到；"
            "在頁面中搜尋「kml」同樣毫無所獲。",
            "在 Templates/ 之下所有檔案中搜尋「place-search」與"
            "「person-search」：除 Go 原始碼外沒有任何命中。",
            "在 Templates/places/index.html 中搜尋「encoding」：五處命中，"
            "全部都是寫死的 'unicode'。",
        ),
        source=("Code/groupdata_form_backend.go:1084",
                "Templates/group_data/index.html",
                "Code/networks_form_backend.go:handlePlaceSearch",
                "Code/networks_form_backend.go:handlePersonSearch",
                "Code/places_form_backend.go:handleExportPajek",
                "Templates/places/index.html:656"),
        tests=("test_a_kml_the_handler_can_write_is_a_kml_the_page_can_ask_"
               "for",
               "test_every_api_endpoint_the_build_routes_has_a_page_that_"
               "calls_it",
               "test_an_export_named_ascii_contains_ascii"),
    ),
    Defect(
        key="CBDB-D-012",
        priority="P0", severity="high", origin="software",
        title="\"Select All Filtered\" returns the first hundred addresses "
              "and reports them as the whole filter",
        title_zh="「Select All Filtered」只回傳前一百筆地址，卻宣稱那是整個"
                 "篩選結果",
        area="Address picker",
        area_zh="地址選擇視窗",
        summary="The picker keeps `filteredAddresses` (its own comment: "
                "*\"full match set (all rows matching the filter)\"*) and "
                "`renderedAddresses = filteredAddresses.slice(0, "
                "MAX_RENDER)` with `MAX_RENDER = 100`.  Only the rendered "
                "slice becomes `<option>` elements.  `selectAllFiltered()` "
                "walks `sel.options`, and `sendResult` walks `sel.options` "
                "again to build what it hands back -- so on a filter "
                "matching more than a hundred addresses the button returns "
                "the first hundred, and returns them with "
                "`isSelectAllFiltered: true` plus the filter text, which "
                "every host page reads as \"the user chose the whole "
                "filter\".",
        summary_zh="這個選擇視窗同時維護 `filteredAddresses`（其註解自述為"
                   "「完整的比對結果集（所有符合篩選條件的列）」）與 "
                   "`renderedAddresses = filteredAddresses.slice(0, "
                   "MAX_RENDER)`，其中 `MAX_RENDER = 100`。只有被繪出的這"
                   "一段會變成 `<option>` 元素。`selectAllFiltered()` 走訪"
                   "的是 `sel.options`，而 `sendResult` 也再一次走訪 "
                   "`sel.options` 來組出要回傳的內容——因此，當篩選結果超過"
                   "一百筆時，這個按鈕回傳的是前一百筆，而且回傳時帶著 "
                   "`isSelectAllFiltered: true` 與篩選文字，所有呼叫端頁面"
                   "都會把它解讀為「使用者選擇了整個篩選結果」。",
        evidence="Read from `Templates/pickers/address_picker.html`, with "
                 "each function's body taken by brace matching rather than "
                 "by pattern, so that what is attributed to "
                 "`selectAllFiltered` is what that function does: the cap "
                 "(`const MAX_RENDER = 100`), the slice that applies it, and "
                 "both functions walking `sel.options`.  The button's own "
                 "comment says it *\"selects every visible (filtered) "
                 "item\"*.  The status bar does say *\"Showing first 100 of "
                 "N -- refine your search\"*, but the button is not disabled "
                 "in that state and nothing in the result it sends records "
                 "the truncation.  The scale is measurable, and has to "
                 "be measured against the right population: the picker "
                 "does not filter `ADDR_CODES`.  It filters "
                 "`allAddresses`, loaded once from `/api/addresses` -- "
                 "37,118 rows, because that endpoint joins "
                 "`ADDR_BELONGS_DATA` and each row carries its own year "
                 "range -- and it matches case-insensitively on the pinyin "
                 "name.  Filtered the way the page filters, \"Zhou\" gives "
                 "5,373 rows, \"Xian\" 7,166 and \"Fu\" 2,007, so the "
                 "button returns 1.9%, 1.4% and 5.0% of what the user "
                 "asked for.",
        evidence_zh="讀自 `Templates/pickers/address_picker.html`；每個函式"
                    "的主體是以大括號配對取出，而非以樣式比對，因此歸給 "
                    "`selectAllFiltered` 的內容確實是該函式所做的事：上限"
                    "（`const MAX_RENDER = 100`）、套用該上限的切片，以及"
                    "兩個函式都在走訪 `sel.options`。按鈕自身的註解寫著它"
                    "「選取所有可見（已篩選）的項目」。狀態列確實會顯示"
                    "「Showing first 100 of N — refine your search」，但在"
                    "該狀態下按鈕並未停用，而且它送出的結果裡沒有任何地方"
                    "記錄了這次截斷。其規模可以量化，但必須對著正確的母體來量："
                    "這個選擇視窗篩選的並不是 `ADDR_CODES`，而是 "
                    "`allAddresses`——它一次性載自 `/api/addresses`，"
                    "共 37,118 列（因為該端點會連接 `ADDR_BELONGS_DATA`，"
                    "每一列各自帶有年份範圍），而且比對的是拼音名稱、"
                    "不分大小寫。依照頁面實際的篩選方式：「Zhou」得到 "
                    "5,373 列，「Xian」7,166 列，「Fu」2,007 列。這個按鈕"
                    "各自只回傳其中 100 列，也就是使用者所要求的 1.9%、"
                    "1.4% 與 5.0%。",
        impact="The query then runs on a hundred addresses while the page "
               "displays the filter text, so the result looks like an answer "
               "about the whole filter and is an answer about a small "
               "fraction of it.  Which hundred depends on the order the list "
               "arrived in, which is not the user's choice and is not shown.",
        impact_zh="接下來的查詢是在一百筆地址上執行，而頁面顯示的卻是篩選"
                  "文字，於是結果看起來像是針對整個篩選範圍的答案，實際上"
                  "只是其中一小部分的答案。至於是哪一百筆，取決於清單送達"
                  "時的順序——那既不是使用者的選擇，也不會顯示出來。",
        fix="Build the result from `filteredAddresses` rather than from "
            "`sel.options`; the full set is already in memory and the render "
            "cap exists only to keep the `<select>` manageable.  If sending "
            "thousands of ids is not wanted, send the filter itself and let "
            "the host page resolve it -- but do not send a hundred rows "
            "labelled as the filter.",
        fix_zh="請改以 `filteredAddresses` 而非 `sel.options` 來組出結果；"
               "完整集合本來就已在記憶體中，繪製上限的存在只是為了讓 "
               "`<select>` 不至於過大。若不希望送出數千個 id，可以改送"
               "篩選條件本身、由呼叫端頁面自行解析——但請不要送出一百列"
               "卻標示成整個篩選結果。",
        steps=(
            "Open any form that offers an address picker and open it.",
            "Filter on \"Zhou\" so the status bar reads \"Showing first 100 "
            "of 5373\".",
            "Press Select All Filtered, and count the addresses the host "
            "page received: 100.",
        ),
        steps_zh=(
            "開啟任一提供地址選擇視窗的表單，並打開該視窗。",
            "以「Zhou」進行篩選，使狀態列顯示「Showing first 100 of 5373」。",
            "按下 Select All Filtered，再清點呼叫端頁面實際收到的地址筆數："
            "100 筆。",
        ),
        source=("Templates/pickers/address_picker.html:118",
                "Templates/pickers/address_picker.html:223",
                "Templates/pickers/address_picker.html:344",
                "Templates/pickers/address_picker.html:381"),
        tests=("test_select_all_filtered_selects_every_address_the_filter_"
               "matched",
               "test_the_function_body_reader_stops_at_the_function"),
    ),
    Defect(
        key="CBDB-D-013",
        priority="P0", severity="medium", origin="software",
        title="Recall on the Association Pairs page fills the pair with "
              "two people nothing chose, and says nothing about the "
              "rest of the stored list",
        title_zh="關聯配對頁面的 Recall 以無所依據的方式挑出兩個人填入"
                 "配對欄位，對已儲存清單中其餘的人則隻字未提",
        area="Association Pairs: recall-ids",
        area_zh="關聯配對：recall-ids",
        summary="`handleRecallIDs` answers *GET "
                "/api/assocpairs/recall-ids* with `SELECT s.c_personid, ... "
                "FROM ZZ_STORE_PERSON_ID s LEFT JOIN BIOG_MAIN bm ON ... "
                "LIMIT 2` and no `ORDER BY`.  `ZZ_STORE_PERSON_ID` is the "
                "application's stored-person list -- the one channel by "
                "which a result travels between forms -- and it can hold any "
                "number of people.  Two come back, chosen by the query plan.",
        summary_zh="`handleRecallIDs` 以 `SELECT s.c_personid, ... FROM "
                   "ZZ_STORE_PERSON_ID s LEFT JOIN BIOG_MAIN bm ON ... "
                   "LIMIT 2`（沒有 `ORDER BY`）回應 *GET "
                   "/api/assocpairs/recall-ids*。`ZZ_STORE_PERSON_ID` 是整個"
                   "程式的已儲存人物清單——也是查詢結果在各表單之間傳遞的"
                   "唯一管道——它可以存放任意數量的人。回來的只有兩個，"
                   "而且是由查詢計畫挑的。",
        evidence="Driven, not merely read, and counted "
                 "through a second endpoint rather than through the reply "
                 "to the write.  Storing five people via `POST "
                 "/api/assocpairs/store-ids` answers `{\"count\":5}`, but "
                 "that number is `len(req.PersonIDs)` -- the request handed "
                 "back, which would say five whatever the table did.  `POST "
                 "/api/networks/recall-person-ids`, which reads the same "
                 "global `ZZ_STORE_PERSON_ID`, independently answers "
                 "`{\"count\":5}`; `GET "
                 "/api/assocpairs/recall-ids` then returns two, the same "
                 "two on three consecutive calls.  "
                 "So *two of the five come back and the other three "
                 "are neither returned nor mentioned* -- measured "
                 "against the list as another form still sees it, "
                 "which is also what shows those three are still "
                 "stored rather than lost.\n\nThe handler's own comment says "
                 "*\"Returns people stored in ZZ_STORE_PERSON_ID (up to 2 "
                 "for pair mode)\"*, so the cap is deliberate and this "
                 "report does not ask for it to be lifted.  What is not "
                 "deliberate is the rest: nothing orders the rows, so which "
                 "two is left to the query plan, and nothing tells the user "
                 "that the other three are still in the list, waiting, "
                 "and not in front of them.  That the choice is unspecified rather than "
                 "unstable is what the missing `ORDER BY` establishes: "
                 "SQLite is not obliged to keep returning these two, and "
                 "nothing in the code asks it to.  Every `SELECT` in "
                 "`Code/*.go` that caps its rows without ordering them was "
                 "surveyed; the build has three, and the other two are "
                 "correlated subqueries in `kinrelReductionUpdate` keyed on "
                 "`kr.c_kinrel_target` with `c_required = 1`, where the "
                 "predicate already selects the intended row.",
        evidence_zh="本項是實際呼叫驗證的，不只是讀原始碼；而且"
                    "筆數是透過另一個端點去數的，而不是看寫入時的回應。"
                    "以 `POST /api/assocpairs/store-ids` 存入五個人，"
                    "回應是 `{\"count\":5}`，但這個數字是 "
                    "`len(req.PersonIDs)`——也就是把請求原樣回報，不論"
                    "資料表實際如何都會是五。改用讀取同一張全域 "
                    "`ZZ_STORE_PERSON_ID` 的 `POST "
                    "/api/networks/recall-person-ids`，得到的同樣是 "
                    "`{\"count\":5}`；接著 `GET "
                    "/api/assocpairs/recall-ids` 只回傳兩個，連續三次呼叫"
                    "回傳的都是同樣那兩個。也就是說，**五個人裡回來兩個，"
                    "另外三個既沒有回傳、也沒有被提及**——這是對照另一"
                    "個表單目前仍看得到的清單量測出來的，而這同時也證明"
                    "那三個人仍存放著、並未遺失。\n\n處理常式自己的註解寫著"
                    "「Returns people stored in ZZ_STORE_PERSON_ID (up to "
                    "2 for pair mode)」，可見這個上限是刻意的，本報告也"
                    "不是要求取消它。不是刻意的是其餘的部分：沒有任何"
                    "地方為這些列排序，因此是哪兩個交由查詢計畫決定；"
                    "也沒有任何地方告訴使用者，另外三個人仍在清單裡"
                    "等著，只是沒有出現在他眼前。至於這個選擇是「未明確"
                    "指定」而非「不穩定」，則是由缺少 `ORDER BY` 所確立的："
                    "SQLite 並沒有義務一直回傳這兩個，程式裡也沒有任何地方"
                    "要求它這麼做。`Code/*.go` 中所有「限制列數卻未排序」的 "
                    "`SELECT` 都已清查，共三處；另外兩處是 "
                    "`kinrelReductionUpdate` 中的相關子查詢，以 "
                    "`kr.c_kinrel_target` 為鍵並搭配 `c_required = 1`，"
                    "述詞本身已經選定了目標列。",
        impact="A user who sent five people to this form from another one, "
               "then pressed Recall, is working on two of them and is not "
               "told which two or why.  The pair is filled and the page "
               "looks correct.  Nothing is destroyed -- the stored list "
               "still holds all five, and another form still reads them "
               "back -- so this is a failure to report rather than data "
               "loss; but the two the user ends up working on were chosen "
               "by the query plan, and because nothing orders the rows it "
               "is not a choice they could learn to predict either.",
        impact_zh="使用者若從另一個表單把五個人送到這個表單，再按下 Recall，"
                  "實際上是在其中兩個人身上作業，卻不知道是哪兩個、也不知道"
                  "為什麼。配對欄位填滿了，頁面看起來一切正常。這裡沒有任何"
                  "資料被破壞——已儲存清單仍完整保有五個人，其他表單也仍然"
                  "讀得回來——所以這是「沒有據實告知」，而不是「資料遺失」；"
                  "但使用者最後實際處理的那兩個人，是由查詢計畫挑出來的，"
                  "而且因為沒有任何排序，他也無從歸納出其中的規律。",
        fix="Decide what Recall means when the stored list holds more than "
            "two, and say it in the code: an `ORDER BY` that names the "
            "intended rows (insertion order if the table records it, "
            "`c_personid` otherwise), and a message when rows are dropped.  "
            "Better still, let the user pick which two.",
        fix_zh="請先確定當已儲存清單超過兩人時，Recall 的語意究竟為何，"
               "並在程式中明確表達出來：加上能指明目標列的 `ORDER BY`"
               "（若資料表有記錄寫入順序就依寫入順序，否則依 `c_personid`），"
               "並在有資料被捨棄時給出提示。更好的做法是讓使用者自行選擇"
               "是哪兩個。",
        steps=(
            "POST /api/assocpairs/store-ids with five personIds; the reply "
            "says count: 5.",
            "GET /api/assocpairs/recall-ids: two people come back.",
            "On the page, the same sequence fills the pair and reports "
            "nothing about the other three.",
        ),
        steps_zh=(
            "以五個 personId 呼叫 POST /api/assocpairs/store-ids，"
            "回應顯示 count: 5。",
            "呼叫 GET /api/assocpairs/recall-ids：只有兩個人回來。",
            "在頁面上執行同一串操作，配對欄位被填滿，另外三個人則完全"
            "沒有任何交代。",
        ),
        source=("Code/assocpairs_form_backend.go:handleRecallIDs",),
        tests=("test_a_query_that_keeps_only_some_rows_says_which_ones",),
    ),
    Defect(
        key="CBDB-D-014",
        priority="P3", severity="low", origin="release",
        title="The front page's Users Guide link is a 404: the PDF is not in "
              "the distribution",
        title_zh="首頁的 Users Guide 連結是 404：該 PDF 並不在發行檔中",
        area="Packaging: Static/",
        area_zh="封裝內容：Static/",
        summary="`Templates/navigation/index.html` offers a *Users Guide* "
                "link pointing at `../../static/CBDB_UserGuide.pdf`.  "
                "`Static/` ships one file, `cbdb_styles.css`.",
        summary_zh="`Templates/navigation/index.html` 提供了一個 *Users "
                   "Guide* 連結，指向 `../../static/CBDB_UserGuide.pdf`；"
                   "然而 `Static/` 只釋出了一個檔案，就是 "
                   "`cbdb_styles.css`。",
        evidence="Every same-origin link on the navigation page was "
                 "followed.  All resolve except this one, which answers HTTP "
                 "404.  `Static/` is the only file-served directory in the "
                 "build, so there is nowhere else the file could be reached "
                 "from.\n\nThe distribution settles for itself which side "
                 "this belongs on.  `The directory structure for "
                 "CBDB-Desktop.txt`, shipped at the root of the archive, "
                 "lists `PDF files: "
                 "CBDB-Desktop\\Static\\xxx.pdf` at its last line, and "
                 "`cbdb_navigation_backend.go:62` describes the directory it "
                 "serves as \"Static files (PDF user guide, images, "
                 "etc.)\".  So the layout expects PDFs in `Static/`, the "
                 "code that serves it expects the guide among them, the "
                 "template links to it accordingly, and what is missing is "
                 "the file: this is the packaging step, not a template "
                 "pointing somewhere it never should have.",
        evidence_zh="已逐一走訪首頁上所有同源連結。除了這一個回傳 HTTP 404 "
                    "之外，其餘皆可正常解析。`Static/` 是整個建置中唯一以"
                    "檔案方式對外提供的目錄，因此這個檔案也不可能從別處"
                    "取得。\n\n這個問題該歸屬哪一邊，發行檔自己就給了答案。"
                    "隨壓縮檔根目錄一併釋出的 `The directory structure for "
                    "CBDB-Desktop.txt`，在最後一行列有 `PDF files: "
                    "CBDB-Desktop\\Static\\xxx.pdf`；而 "
                    "`cbdb_navigation_backend.go:62` 也把它所提供的這個"
                    "目錄描述為「Static files (PDF user guide, images, "
                    "etc.)」。可見依照既定的目錄結構，PDF 本就該放在 "
                    "`Static/`，負責提供該目錄的程式也預期使用手冊在其中，"
                    "模板同樣是照著這個結構去連結的，缺的是檔案本身："
                    "問題出在封裝這一步，而不是模板指向了一個它本來就"
                    "不該指向的位置。",
        impact="The documentation the application points its users at is not "
               "there.  This is a desktop distribution aimed at researchers "
               "rather than developers, and the guide is one of only two "
               "links the front page offers outside the forms themselves.",
        impact_zh="程式指引使用者前往的說明文件並不存在。這是一套以研究者"
                  "而非開發者為對象的桌面發行版，而在各表單之外，首頁總共"
                  "也只提供兩個連結，這是其中之一。",
        fix="Ship `CBDB_UserGuide.pdf` in `Static/`, which is where the "
            "distribution's own layout document says PDFs go.  If the guide "
            "lives elsewhere -- a project website -- make the link point "
            "there and say so.",
        fix_zh="請把 `CBDB_UserGuide.pdf` 一併放進 `Static/`，這也正是發行檔"
               "自身的目錄結構文件所指定的 PDF 存放位置。若這份指南另有存放"
               "之處（例如專案網站），請將連結改指向該處並加以說明。",
        steps=(
            "Start the application and open the front page.",
            "Press Users Guide.",
            "Or: 7z l CBDB-Desktop_20260908.7z | findstr Static",
        ),
        steps_zh=(
            "啟動程式並開啟首頁。",
            "按下 Users Guide。",
            "或執行：7z l CBDB-Desktop_20260908.7z | findstr Static",
        ),
        source=("Templates/navigation/index.html:75",
                "The directory structure for CBDB-Desktop.txt:82",
                "Code/cbdb_navigation_backend.go:62",
                "Static/"),
        tests=("test_every_link_the_navigation_offers_resolves",),
    ),
    Defect(
        key="CBDB-D-015",
        priority="P0", severity="high", origin="software",
        title="A person imported twice is counted twice, queried twice, "
              "and written twice into six of the seven Networks exports",
        title_zh="同一個人若被匯入兩次，就會被計數兩次、查詢兩次，"
                 "並在社會網絡七種匯出中的六種裡被寫出兩次",
        area="Networks: the imported working list",
        area_zh="社會網絡：匯入的工作清單",
        summary="`networks_form_backend.go` declares its working list as "
                "`CREATE TABLE IF NOT EXISTS ZZ_SIP_NETWORK (... UNIQUE "
                "(c_person_id))` and inserts into it with `INSERT OR "
                "IGNORE` in all four places that fill it.  The table ships "
                "in the database without that constraint, and `CREATE "
                "TABLE IF NOT EXISTS` against a table that already exists "
                "is a no-op -- so the guard never runs, and the `OR IGNORE` "
                "has nothing to ignore.  A repeated id is ordinary input: "
                "the page builds its list from a file one line at a time "
                "and does not deduplicate.",
        summary_zh="`networks_form_backend.go` 把它的工作清單宣告為 "
                   "`CREATE TABLE IF NOT EXISTS ZZ_SIP_NETWORK (... UNIQUE "
                   "(c_person_id))`，並且在四處填入資料的地方全都使用 "
                   "`INSERT OR IGNORE`。但這張表在釋出的資料庫中並沒有這個"
                   "約束，而 `CREATE TABLE IF NOT EXISTS` 對一張已經存在的"
                   "表而言是空操作——因此這道防護從未生效，`OR IGNORE` 也"
                   "沒有東西可以忽略。重複的 id 是很平常的輸入：頁面是逐行"
                   "從檔案讀出清單的，並不會去除重複。",
        evidence="Driven through the shipped binary.  Importing person 0 "
                 "once: `/api/networks/person-count` says 1, and the "
                 "smallest query returns 19 rows for 19 distinct people.  "
                 "Importing the same person *twice*: person-count says **2 "
                 "for one person**, and the same query returns **20 rows "
                 "for 19 distinct people**, person 0 appearing twice.  The "
                 "duplicate is not confined to the working list: "
                 "`networks_form_query.go` seeds `ZZ_SP_NETWORK` from it "
                 "with no `DISTINCT`, and the result rows and six of the "
                 "seven export writers read `ZZ_SP_NETWORK` with no "
                 "`DISTINCT` either -- Export Results, GIS, KML, "
                 "Gephi/GUESS, UCINet and Pajek.  The seventh, Neo4j, is "
                 "unaffected, and how it escapes is the fix in miniature: "
                 "it collects its people into `ZZ_SCRATCH_P_TEXT` with "
                 "`INSERT OR IGNORE ... SELECT DISTINCT`, and that table "
                 "*does* ship with the unique constraint its declaration "
                 "asks for.\n\nThe constraint is missing in the shipped "
                 "table and not in the Go: `PRAGMA index_list` finds no "
                 "unique index on `ZZ_SIP_NETWORK`, `ZZ_SIP_KINSHIP` or "
                 "`ZZ_SIP_ASSOC_PAIR`, while `ZZ_SCRATCH_ADDR` -- declared "
                 "the same way, in the same file -- does have one.  So this "
                 "is an omission in the database builder rather than a "
                 "decision.  Kinship and Association Pairs escape the "
                 "visible half by luck: their working lists duplicate too, "
                 "and their person-counts are wrong in the same way, but "
                 "their queries deduplicate downstream.",
        evidence_zh="以釋出的執行檔實測。將人物 0 匯入一次："
                    "`/api/networks/person-count` 回報 1，最小查詢回傳 19 "
                    "列、19 個不重複人物。將同一個人匯入**兩次**："
                    "person-count 回報 **一個人卻是 2**，同一個查詢回傳 "
                    "**20 列、19 個不重複人物**，人物 0 出現了兩次。這個"
                    "重複並不止於工作清單：`networks_form_query.go` 由它"
                    "填入 `ZZ_SP_NETWORK` 時沒有 `DISTINCT`，而結果列與"
                    "七個匯出程式中的六個在讀取 `ZZ_SP_NETWORK` 時同樣"
                    "沒有 `DISTINCT`——分別是 Export Results、GIS、KML、"
                    "Gephi/GUESS、UCINet 與 Pajek。第七個 Neo4j 不受影響，"
                    "而它之所以能倖免，正是這個修正的縮影：它以 "
                    "`INSERT OR IGNORE ... SELECT DISTINCT` 把人物收進 "
                    "`ZZ_SCRATCH_P_TEXT`，而那張表確實依其宣告帶有唯一"
                    "約束。\n\n缺少約束的是釋出的資料表而不是 Go："
                    "`PRAGMA index_list` 在 `ZZ_SIP_NETWORK`、"
                    "`ZZ_SIP_KINSHIP` 與 `ZZ_SIP_ASSOC_PAIR` 上都找不到"
                    "唯一索引，而以同樣方式、在同一個檔案中宣告的 "
                    "`ZZ_SCRATCH_ADDR` 卻有。可見這是資料庫建置程式的疏漏，"
                    "而不是刻意的決定。親屬關係與關聯配對只是僥倖避開了"
                    "可見的那一半：它們的工作清單同樣會重複、person-count "
                    "也同樣錯誤，只是它們的查詢在後續步驟中去除了重複。",
        impact="A network is a count of people and a set of relationships, "
               "and both are wrong.  The person appears twice in the "
               "result grid, twice in Export Results, twice in the GIS "
               "table, twice in the KML, and twice in the Gephi, UCINet "
               "and Pajek files -- where a duplicated vertex is not "
               "merely cosmetic, since the network measures those tools "
               "compute are defined over the vertex set.  Only the Neo4j "
               "bundle comes out right.  The points-per-coordinate "
               "figure the GIS and "
               "KML exports carry counts rows, so it inflates too.  "
               "Nothing on screen marks any of it, and the input that "
               "causes it -- a list file with a repeated id -- is one a "
               "historian would have no reason to think twice about.",
        impact_zh="一個網絡就是一組人數與一組關係，而這兩者都錯了。這個人"
                  "會在結果表格中出現兩次、在 Export Results 中兩次、在 "
                  "GIS 表中兩次、在 KML 中兩次，在 Gephi、UCINet 與 Pajek "
                  "檔案中也各出現兩次——在那些工具裡，重複的節點並不只是"
                  "外觀問題，因為它們計算的網絡指標正是定義在節點集合"
                  "之上的。只有 Neo4j 匯出是正確的。GIS 與 KML 匯出所帶的"
                  "「每個座標點的人數」是以列數計算的，因此也會膨脹。"
                  "畫面上沒有任何地方標示這件事，而造成它的輸入——一個"
                  "帶有重複 id 的清單檔——正是歷史學者不會多想一秒的東西。",
        fix="Add `UNIQUE (c_person_id)` to `ZZ_SIP_NETWORK` in "
            "`CBDB_AdditionalTablesViewsIndices.sql`, which is what "
            "actually creates it; the Go already declares the constraint "
            "and every insert into that table is already `INSERT OR "
            "IGNORE`, so nothing else has to change.\n\n**Only that "
            "table.**  `ZZ_SIP_KINSHIP` and `ZZ_SIP_ASSOC_PAIR` duplicate "
            "in the same way and their person-counts are wrong in the same "
            "way, but neither declares the constraint and neither inserts "
            "with `OR IGNORE` -- so adding `UNIQUE` to them would turn a "
            "silent duplicate into a failed insert, which is a worse "
            "outcome and a decision for whoever owns those forms.  If "
            "their counts are to be fixed, `SELECT DISTINCT` at the point "
            "of insert is the safe way.  Worth a look in the other "
            "direction too: every `CREATE TABLE IF NOT EXISTS` in the Go "
            "describes a table that already ships, so any constraint "
            "declared there and missing from the builder is inert in "
            "exactly this way.",
        fix_zh="請在實際負責建立資料表的 "
               "`CBDB_AdditionalTablesViewsIndices.sql` 中，為 "
               "`ZZ_SIP_NETWORK` 加上 `UNIQUE (c_person_id)`；Go 端本來就"
               "宣告了這個約束，對該表的所有插入也早已是 `INSERT OR "
               "IGNORE`，因此不需要再改動其他地方。\n\n**僅限這一張表。**"
               "`ZZ_SIP_KINSHIP` 與 `ZZ_SIP_ASSOC_PAIR` 同樣會重複、"
               "person-count 也同樣錯誤，但這兩張表既沒有宣告該約束，"
               "插入時也沒有使用 `OR IGNORE`——因此若替它們加上 `UNIQUE`，"
               "只會把「靜默的重複」變成「插入失敗」，那是更糟的結果，"
               "也應由這兩個表單的負責人自行決定。若要修正它們的計數，"
               "在插入處加上 `SELECT DISTINCT` 才是安全的作法。另外也"
               "值得往反方向檢查一遍：Go 中每一處 `CREATE TABLE IF NOT "
               "EXISTS` 所描述的資料表都已隨版釋出，因此凡是宣告於該處、"
               "卻不存在於建置程式中的約束，都會以完全相同的方式失效。",
        steps=(
            "Open Networks and import a list file with the same person id "
            "on two lines (or POST /api/networks/import-people with "
            "{\"personIds\": [1, 1]}).",
            "Read the count under the list: it says 2 for one person.",
            "Run the query and look for that person in the results grid: "
            "two rows.",
            "Save to GIS and count the person's rows in the file: two.  "
            "Save to Neo4j and count them there: one.",
        ),
        steps_zh=(
            "開啟社會網絡頁面，匯入一個同一個人物 id 出現在兩行的清單檔"
            "（或以 {\"personIds\": [1, 1]} 呼叫 POST "
            "/api/networks/import-people）。",
            "看清單下方的人數：一個人卻顯示 2。",
            "執行查詢，在結果表格中找這個人：有兩列。",
            "執行 Save to GIS，數一數檔案中這個人的列數：兩列。"
            "再執行 Save to Neo4j，在那裡數一數：一列。",
        ),
        source=("Code/networks_form_backend.go:384",
                "Code/networks_form_backend.go:handleExportNeo4j",
                "CBDBSetUpCode/CBDB_AdditionalTablesViewsIndices.sql",
                "Code/networks_form_query.go"),
        tests=("test_importing_the_same_person_twice_imports_one_person",
               "test_a_uniqueness_a_form_declares_is_one_the_table_enforces"),
    ),
    Defect(
        key="CBDB-D-016",
        priority="P0", severity="medium", origin="software",
        title="Association Pairs reports how many ids were in the file, not "
              "how many people it loaded",
        title_zh="關聯配對回報的是檔案裡有多少個 id，而不是實際載入了"
                 "多少人",
        area="Association Pairs: import-list",
        area_zh="關聯配對：import-list",
        summary="`handleImportList` inserts by joining `BIOG_MAIN`, so an "
                "id the database does not have inserts nothing -- and then "
                "answers `\"count\": len(req.PersonIDs)`, the request "
                "handed back.  The page prints that number: *\"Imported N "
                "person IDs\"*, *\"N people loaded\"*.",
        summary_zh="`handleImportList` 是以連接 `BIOG_MAIN` 的方式插入的，"
                   "因此資料庫中沒有的 id 什麼也不會插入——然後它卻回應 "
                   "`\"count\": len(req.PersonIDs)`，也就是把請求原樣送回。"
                   "頁面直接把這個數字顯示出來：「Imported N person IDs」、"
                   "「N people loaded」。",
        evidence="Three ids sent, of which two exist in `BIOG_MAIN` and one "
                 "is past the largest id the table holds.  Association "
                 "Pairs answers `{\"count\": 3}` and the following query "
                 "returns exactly what sending only the two real ids "
                 "returns.\n\nThe oracle is the three sibling endpoints "
                 "that load the same kind of list, because they disagree "
                 "with it and with nothing else: Kinship answers "
                 "`{\"count\": 2, \"errorCount\": 1}`, Networks reads "
                 "`COUNT(*)` back out of its own table and answers "
                 "`{\"count\": 2}`, and Group Data answers `{\"count\": 2}` "
                 "with the rows it found.  Three of the four report what "
                 "happened; the fourth reports what it was asked to do.",
        evidence_zh="送出三個 id，其中兩個存在於 `BIOG_MAIN`，另一個大於"
                    "該表中最大的 id。關聯配對回應 `{\"count\": 3}`，"
                    "而隨後的查詢所回傳的結果，與只送出那兩個真實 id 時"
                    "完全相同。\n\n判準來自另外三個載入同類清單的端點，"
                    "因為不一致的只有這一個：親屬關係回應 `{\"count\": 2, "
                    "\"errorCount\": 1}`，社會網絡從自己的資料表把 "
                    "`COUNT(*)` 讀回來、回應 `{\"count\": 2}`，分群資料"
                    "回應 `{\"count\": 2}` 並附上實際找到的資料列。"
                    "四者之中有三個回報的是實際發生的事，第四個回報的則是"
                    "它被要求做的事。",
        impact="A historian importing an id list from an older CBDB "
               "release, or from a colleague's spreadsheet, is told the "
               "whole list loaded and then queries a subset.  Nothing "
               "later contradicts it: the result simply has fewer people "
               "in it than the source list had, which looks like a finding "
               "about the data rather than about the import.",
        impact_zh="歷史學者若從舊版 CBDB、或從同事的試算表匯入一份 id "
                  "清單，系統會告訴他整份清單都載入了，實際上查詢的卻只是"
                  "其中一部分。後續也沒有任何地方會推翻這個說法：結果裡的"
                  "人數就是比來源清單少，看起來像是關於資料本身的發現，"
                  "而不是匯入出了問題。",
        fix="Report what was inserted, not what was asked for.  The three "
            "sibling handlers show two ways: count `RowsAffected` as "
            "Kinship does and return an `errorCount` beside it, or read "
            "`COUNT(*)` back as Networks does.  Kinship's shape is the "
            "more useful of the two, because a user who is told one id "
            "failed can go and look for it.",
        fix_zh="請回報實際插入的筆數，而不是被要求的筆數。另外三個同類的"
               "處理常式示範了兩種作法：像親屬關係那樣統計 `RowsAffected` "
               "並附上 `errorCount`，或像社會網絡那樣把 `COUNT(*)` 讀回來。"
               "其中親屬關係的形式較為實用，因為使用者一旦被告知有一個 id "
               "載入失敗，就能自己去找出是哪一個。",
        steps=(
            "On Look At Association Pairs, import a list containing two "
            "real person ids and one that does not exist.",
            "The page says three people were loaded.",
            "Run the query: the answer is the one for two people.",
            "Send the same three ids to /api/kinship/import-people for "
            "comparison: it answers count 2, errorCount 1.",
        ),
        steps_zh=(
            "在關聯配對頁面上，匯入一份含有兩個真實人物 id 與一個不存在 "
            "id 的清單。",
            "頁面顯示載入了三個人。",
            "執行查詢：得到的是兩個人的結果。",
            "把同樣這三個 id 送到 /api/kinship/import-people 作為對照："
            "它回應 count 2、errorCount 1。",
        ),
        source=("Code/assocpairs_form_backend.go:handleImportList",
                "Templates/association_pairs/index.html:513"),
        tests=("test_a_list_loader_reports_how_many_people_it_loaded",),
    ),
    Defect(
        key="CBDB-D-017",
        priority="P0", severity="high", origin="software",
        title="A year window admits every record whose year was never "
              "recorded, because the database writes that as 0",
        title_zh="年份區間會納入所有年份從未被記錄的資料，"
                 "因為資料庫是以 0 表示「未記錄」",
        area="Entry and Office: the entry-year and office-year filters",
        area_zh="入仕與官職：入仕年份與任官年份篩選",
        summary="`ENTRY_DATA.c_year` is 0 where the year is unknown, in "
                "164,443 of its 264,775 rows, and "
                "`POSTED_TO_OFFICE_DATA` uses 0 the same way.  Both "
                "filters compare against the column directly -- entry "
                "with `ED.c_year >= ?` / `<= ?`, office with "
                "`POD.c_firstyear >= ?` and `POD.c_lastyear <= ?` -- so "
                "`0 <= 1100` is true and every undated record satisfies "
                "any upper bound.",
        summary_zh="`ENTRY_DATA.c_year` 在年份未知時為 0，264,775 列中"
                   "有 164,443 列如此；`POSTED_TO_OFFICE_DATA` 也以同樣"
                   "方式使用 0。兩邊的篩選都是直接與該欄位比較——入仕是 "
                   "`ED.c_year >= ?` / `<= ?`，官職則是 "
                   "`POD.c_firstyear >= ?` 與 `POD.c_lastyear <= ?`——"
                   "於是 `0 <= 1100` 成立，所有沒有年份的紀錄都會滿足"
                   "任何上界。",
        evidence="Driven against the shipped binary, on the century "
                 "each code most densely populates -- read from the "
                 "column being filtered rather than chosen by hand.\n\n"
                 "**Entry**, entryyear.  A closed window over "
                 "1100-1199 is clean: 254 rows, none outside it.  The "
                 "same query with the From box empty -- *up to 1199* "
                 "-- returns 303 rows of which **42 are outside**, and "
                 "every one of those has an entry year of 0.  On a "
                 "sparser code the effect is total: code 37 filtered "
                 "to 1100 returns four rows and all four have "
                 "entryYear 0, so not one dated entry comes back.\n\n"
                 "**Office**, officeyear.  A closed 1300-1399 window "
                 "is likewise clean (135 rows, none outside), and *up "
                 "to 1399* returns 383 rows of which **215 are "
                 "outside**.  Office fails the closed case too "
                 "wherever the data allows it, because its lower bound "
                 "tests `c_firstyear` and its upper tests "
                 "`c_lastyear`: code 790 over 1000-1100 returns three "
                 "postings whose (first, last) years are (1135, 0), "
                 "(1136, 0) and (1166, 0) -- every row returned for a "
                 "window ending in 1100 began after it, because a "
                 "posting whose end was never recorded passes the "
                 "upper bound however late it started.\n\n"
                 "So a To-only window is wrong on both forms whatever "
                 "the data holds, and a closed window is wrong on "
                 "Office wherever an end year is missing.",
        evidence_zh="以釋出的執行檔實測，所用的世紀區間取自各代碼"
                    "在被篩選欄位上分布最密的一段，而非人工挑選。\n\n"
                    "**入仕**，entryyear。1100-1199 這個兩端俱全的"
                    "區間是乾淨的：254 列，沒有一列落在區間外。"
                    "同一個查詢若把「起」的欄位留白——也就是"
                    "「至 1199 年」——回傳 303 列，其中 **42 列在區間"
                    "之外**，而且這些列的入仕年份全都是 0。在較稀疏的"
                    "代碼上更是全軍覆沒：代碼 37 篩選至 1100 年，"
                    "回傳四列，四列的 entryYear 都是 0，沒有任何一筆"
                    "有年份的紀錄回來。\n\n"
                    "**官職**，officeyear。1300-1399 的封閉區間同樣"
                    "乾淨（135 列，無一在外），而「至 1399 年」回傳 "
                    "383 列，其中 **215 列在區間之外**。只要資料條件"
                    "允許，官職連封閉區間也會出錯，因為它的下界比對的"
                    "是 `c_firstyear`、上界比對的是 `c_lastyear`："
                    "代碼 790 查詢 1000-1100，回傳三筆任官，其（起、"
                    "迄）年份分別是 (1135, 0)、(1136, 0) 與 (1166, "
                    "0)——在一個以 1100 年為終點的區間裡，回傳的每一"
                    "列都是在那之後才開始的，因為只要結束年未被記錄，"
                    "無論多晚開始都能通過上界。\n\n"
                    "因此，只設「迄」的區間在兩個表單上都是錯的，"
                    "無論資料如何；而封閉區間則在官職表單上，只要"
                    "結束年缺漏就會出錯。",
        impact="A historian asking for Northern Song office postings gets "
               "a majority of rows from the wrong period, and loses the "
               "postings whose only recorded year is the one they asked "
               "about.  On Entry, a To-only window returns precisely the "
               "records that cannot answer the question.  Neither says "
               "anything is wrong, and both look like a finding about the "
               "data rather than about the filter.",
        impact_zh="研究者若查詢北宋時期的任官紀錄，得到的多數列都來自"
                  "錯誤的時代，而那些唯一被記錄下來的年份正落在他所詢問"
                  "區間內的任官，反而會漏掉。在入仕表單上，只設定「迄」"
                  "的查詢，回傳的恰好是完全無法回答該問題的那些紀錄。"
                  "兩者都不會顯示任何異常，看起來都像是關於資料本身的"
                  "發現，而不是篩選出了問題。",
        fix="Exclude the sentinel from the comparison: add `AND "
            "ED.c_year <> 0` (and the equivalent on each office bound) "
            "wherever a year condition is built, or treat 0 as NULL when "
            "the column is read.  Which of the two is right is a "
            "question about intent -- should an undated record appear in "
            "a dated window at all? -- and it is worth answering once and "
            "applying to both forms, since they have made the same "
            "choice by accident rather than on purpose.",
        fix_zh="請把這個哨兵值排除在比較之外：在每一處建立年份條件的地方"
               "加上 `AND ED.c_year <> 0`（官職端的兩個界線亦同），"
               "或在讀取該欄位時把 0 視為 NULL。這兩種作法孰是孰非，"
               "牽涉到意圖的問題——沒有年份的紀錄究竟該不該出現在一個"
               "有年份的區間裡？——這個問題值得一次想清楚，然後同時套用"
               "到兩個表單，因為它們目前的一致並非出於刻意，而是巧合。",
        steps=(
            "Open Look At Entry, choose entry code 37 and set the year "
            "type to Entry Year.",
            "Leave the From box empty and put 1100 in the To box.  Run "
            "the query.",
            "Every row's Entry Year column reads 0.",
            "For Office: choose office code 790, year type Office Year, "
            "1000 to 1100.  Every posting returned began after 1100.",
        ),
        steps_zh=(
            "開啟入仕查詢頁面，選擇入仕代碼 37，並將年份類型設為入仕年份。",
            "「起」的欄位留白，「迄」填入 1100，執行查詢。",
            "每一列的入仕年份欄位都是 0。",
            "官職表單：選擇官職代碼 790，年份類型設為任官年份，"
            "查詢 1000 至 1100。回傳的每一筆任官都是 1100 年之後開始的。",
        ),
        source=("Code/entry_form_backend.go:511",
                "Code/office_form_backend.go:690"),
        tests=("test_a_year_window_does_not_admit_rows_whose_year_is_"
               "unknown",),
    ),
    Defect(
        key="CBDB-D-018",
        priority="P0", severity="medium", origin="software",
        title="Two dynasties the picker offers cannot be filtered on: one "
              "end returns everything, the other returns nothing",
        title_zh="朝代選擇視窗提供的兩個朝代根本無法用來篩選："
                 "當作起點會回傳全部，當作終點則什麼都沒有",
        area="All six query forms: the dynasty range",
        area_zh="六個查詢表單：朝代範圍",
        summary="Every form resolves a dynasty range through "
                "`DYNASTIES.c_start` and `c_end`.  Three rows have both "
                "at 0 -- code 0 (*unknown*), 58 (*Korea*) and 67 "
                "(*Xinluo (Korea)*) -- and the guard the handlers apply "
                "is `> 0` on the dynasty *code*, not on its years.  So 58 "
                "and 67 pass the guard and then produce a comparison "
                "against zero: `c_end > 0` is true of every dynasty that "
                "has a span, and `c_start < 0` is true of none.  The "
                "picker lists all eighty-five without filtering, so both "
                "are one click away.",
        summary_zh="每個表單都是透過 `DYNASTIES.c_start` 與 `c_end` 來"
                   "解析朝代範圍。其中有三列的這兩個值都是 0——代碼 0"
                   "（未詳）、58（高麗）與 67（新羅））——而各處理常式"
                   "所做的檢查是針對朝代**代碼**的 `> 0`，而不是針對它的"
                   "年份。於是 58 與 67 通過了檢查，接著產生一個與零的"
                   "比較：`c_end > 0` 對所有有年份區間的朝代都成立，"
                   "而 `c_start < 0` 則對任何朝代都不成立。選擇視窗會"
                   "毫無篩選地列出全部八十五個朝代，因此這兩個都只差"
                   "一次點擊。",
        evidence="Driven on the Status form, status code 3.  Unfiltered: "
                 "34 rows.  With Korea (58) as the *From* dynasty: 33 "
                 "rows -- the filter removes one row, which is a person "
                 "the join drops rather than anything the filter chose.  "
                 "With Korea as the *To* dynasty: 0 rows.  A dynasty with "
                 "a real span, used as a control in the same test, "
                 "returns a sensible subset.\n\nThe same shape is in "
                 "every form, in two spellings: office, places and texts "
                 "prefetch the years in Go with `SELECT COALESCE(c_start, "
                 "0) ...`, which turns a missing boundary into 0; entry "
                 "and status inline the lookup as a subquery, where a "
                 "code absent from `DYNASTIES` yields NULL and drops the "
                 "row instead.  No page can reach a code that is absent, "
                 "so the reachable half of this is the two Korean "
                 "dynasties.",
        evidence_zh="在社會地位表單上以身分代碼 3 實測。未篩選：34 列。"
                    "以高麗（58）作為**起始**朝代：33 列——篩選只少掉"
                    "一列，而那是連接時被捨去的人，並不是篩選挑出來的。"
                    "以高麗作為**迄止**朝代：0 列。同一個測試中以一個"
                    "確實有年份區間的朝代作為對照，回傳的是合理的子集。"
                    "\n\n每個表單都有同樣的結構，只是寫法有兩種："
                    "官職、地點與著述是在 Go 端以 `SELECT "
                    "COALESCE(c_start, 0) ...` 預先取值，這會把缺漏的"
                    "界線變成 0；入仕與社會地位則是以子查詢內嵌查找，"
                    "此時若代碼不存在於 `DYNASTIES` 就會得到 NULL 而把"
                    "該列剔除。由於沒有任何頁面能送出不存在的代碼，"
                    "實際會被碰到的就是這兩個朝鮮半島的朝代。",
        impact="A user who selects Korea as one end of a dynasty range is "
               "shown either the unfiltered result or an empty grid, with "
               "nothing to distinguish either from a real answer.  The "
               "empty case is the worse of the two: it reads as \"CBDB "
               "has no Korean records of this kind\", which is a "
               "conclusion about the data drawn from a filter that never "
               "ran.",
        impact_zh="使用者若把高麗選為朝代範圍的任一端，看到的不是未經"
                  "篩選的完整結果，就是一片空白，而且沒有任何線索能把"
                  "這兩者與真正的答案區分開來。其中空白的那種更糟："
                  "它讀起來像是「CBDB 沒有這一類的朝鮮半島紀錄」，"
                  "而這是從一個根本沒有執行的篩選，推導出關於資料的結論。",
        fix="Decide what a dynasty with no year span means to a filter "
            "written in years, and make the code and the picker agree.  "
            "Either the picker should not offer a dynasty whose "
            "`c_start`/`c_end` are unset, or the handlers should test the "
            "*years* rather than the code before building the condition "
            "and say so when they cannot.  Filling in the years for the "
            "two Korean dynasties in the source data would also do it, "
            "and is the only one of the three that makes them usable "
            "rather than merely unavailable.",
        fix_zh="請先決定：對一個以年份寫成的篩選而言，一個沒有年份區間的"
               "朝代究竟代表什麼，並讓程式與選擇視窗的行為一致。"
               "可行的作法是：選擇視窗不要提供 `c_start`/`c_end` 未設定"
               "的朝代；或是各處理常式在組出條件之前改為檢查**年份**"
               "而非代碼，並在無法處理時明確告知。另外，在來源資料中"
               "為這兩個朝鮮半島的朝代補上年份也可以解決，而且是三者中"
               "唯一能讓它們真正可用、而不只是不再出現的作法。",
        steps=(
            "Open any query form and choose a code that returns rows.",
            "Set the year type to Dynasty and pick Korea as the From "
            "dynasty.  The result is the unfiltered one.",
            "Pick Korea as the To dynasty instead.  The result is empty.",
            "SELECT c_dy, c_dynasty, c_start, c_end FROM DYNASTIES WHERE "
            "c_dy IN (0, 58, 67);",
        ),
        steps_zh=(
            "開啟任一查詢表單，選一個會回傳資料的代碼。",
            "把年份類型設為朝代，並選擇高麗作為起始朝代。得到的是"
            "未經篩選的結果。",
            "改以高麗作為迄止朝代。得到的是空白結果。",
            "執行：SELECT c_dy, c_dynasty, c_start, c_end FROM DYNASTIES "
            "WHERE c_dy IN (0, 58, 67);",
        ),
        source=("Code/status_form_backend.go:511",
                "Code/places_form_backend.go:250",
                "Templates/pickers/dynasty_picker.html:66"),
        tests=("test_a_dynasty_the_picker_offers_is_one_the_filter_can_"
               "use",),
    ),
    Defect(
        key="CBDB-D-019",
        priority="P0", severity="medium", origin="software",
        title="The Places form and the other five disagree about a "
              "dynasty that begins in the year the range ends",
        title_zh="地點表單與其餘五個表單，對於「起始年正好是範圍結束年」"
                 "的朝代是否納入，看法並不一致",
        area="Places: the upper bound of a dynasty range",
        area_zh="地點：朝代範圍的上界",
        summary="Five forms write the upper half of a dynasty range as "
                "`D.c_start < ?` and Places writes `D.c_start <= ?`.  On "
                "a boundary year the two disagree: the strict form "
                "excludes a dynasty that begins exactly where the range "
                "ends, and Places includes it.  Thirty-five of the "
                "eighty-five dynasties begin in the year another ends, so "
                "this is not a corner nobody reaches.",
        summary_zh="五個表單把朝代範圍的上界寫成 `D.c_start < ?`，"
                   "而地點表單寫的是 `D.c_start <= ?`。在邊界年份上"
                   "兩者就會分歧：嚴格的那種會排除「起始年正好等於範圍"
                   "結束年」的朝代，地點表單則會納入。八十五個朝代中有"
                   "三十五個的起始年正好是另一個朝代的結束年，因此這並"
                   "不是無人會碰到的角落。",
        evidence="Driven on the two forms whose rows carry a dynasty "
                 "code, so that *which* dynasties came back can be "
                 "compared rather than merely how many.  A range ending "
                 "at Ming (19), which ends in the year Qing (20) begins: "
                 "the Entry form's answer contains no Qing rows, and the "
                 "Places form's does.  Both were given a code covering "
                 "people of both dynasties, and both returned rows, so "
                 "neither answer is empty for an unrelated reason.\n\n"
                 "Which of the two is right is not asserted here.  That "
                 "is a question about what a historian means by \"to the "
                 "Ming\", and the developers should answer it; what can "
                 "be said from outside is that one dynasty range, asked "
                 "on two forms, admits different dynasties.",
        evidence_zh="在兩個資料列帶有朝代代碼的表單上實測，如此才能比較"
                    "**哪些**朝代回來了，而不只是回來幾列。以明（19）"
                    "作為範圍終點，而清（20）的起始年正好是明的結束年："
                    "入仕表單的結果中沒有任何清代的資料列，地點表單則"
                    "有。兩者所用的代碼都涵蓋這兩個朝代的人物，也都確實"
                    "回傳了資料，因此不存在某一方因無關原因而為空的情況。"
                    "\n\n本項並不主張兩者之中誰才正確。那牽涉到研究者"
                    "說「到明代為止」時究竟指什麼，應由開發者決定；"
                    "從外部能夠確定的是：同一個請求交給兩個表單，"
                    "會得到兩組不同的人。",
        impact="A researcher who runs the same dynasty range on two forms "
               "and compares the results -- which is the ordinary way to "
               "cross-check a finding -- sees a discrepancy that belongs "
               "to the software and reads as one in the data.  Whichever "
               "boundary convention is intended, one of the six forms is "
               "applying the other.",
        impact_zh="研究者若在兩個表單上執行同一個朝代範圍並比對結果"
                  "——而這正是交叉驗證一項發現最普通的做法——會看到一處"
                  "本屬於軟體的差異，卻讀起來像是資料上的差異。無論"
                  "原本想採用的是哪一種邊界慣例，六個表單中都有一個"
                  "用的是另一種。",
        fix="Pick one convention and use it in all six.  The strict `<` "
            "is what five of them already do, so making Places match is "
            "the smaller change; but the choice is a historical one -- "
            "whether a dynasty that begins in the closing year of the "
            "range belongs to it -- and it should be made deliberately "
            "rather than by counting call sites.",
        fix_zh="請選定一種慣例，並在六個表單中一致採用。嚴格的 `<` 是"
               "其中五個已經在用的寫法，因此把地點表單改成一致是較小的"
               "改動；但這個選擇本身是史學上的判斷——一個在範圍結束當年"
               "才開始的朝代，究竟算不算在範圍之內——應該是有意識地做出"
               "決定，而不是靠數哪一種寫法比較多來決定。",
        steps=(
            "On Look At Entry, choose a code covering Ming and Qing "
            "people, set the year type to Dynasty, and run a range "
            "ending at Ming.  No Qing rows come back.",
            "Run the same range on Look At Places.  Qing rows come back.",
            "SELECT c_dy, c_dynasty, c_start, c_end FROM DYNASTIES WHERE "
            "c_dy IN (19, 20);",
        ),
        steps_zh=(
            "在入仕查詢頁面選一個涵蓋明、清人物的代碼，把年份類型設為"
            "朝代，執行一個以明代為終點的範圍查詢。沒有任何清代的資料列。",
            "在地點查詢頁面執行同樣的範圍查詢。清代的資料列出現了。",
            "執行：SELECT c_dy, c_dynasty, c_start, c_end FROM DYNASTIES "
            "WHERE c_dy IN (19, 20);",
        ),
        source=("Code/places_form_backend.go:298",
                "Code/office_form_backend.go:720",
                "Code/entry_form_backend.go:538"),
        tests=("test_the_forms_agree_where_one_dynasty_ends_and_the_next_"
               "begins",),
    ),
    Defect(
        key="CBDB-D-020",
        priority="P0", severity="medium", origin="software",
        title="Use XY treats the unmapped corner at 0,0 as a place, so it "
              "merges hundreds of unrelated addresses",
        title_zh="Use XY 把 0,0 這個「未定位」的角落當成一個真實地點，"
                 "因而把數百個彼此無關的地址合併在一起",
        area="All six query forms: the Use XY address widening",
        area_zh="六個查詢表單：Use XY 地址擴展",
        summary="*Use XY* gathers every address within 0.03 degrees of "
                "the ones the user chose -- about three kilometres, and "
                "the right idea for catching one place recorded under two "
                "codes.  `ADDR_CODES` stores 316 addresses at exactly "
                "`x_coord = 0, y_coord = 0`, which is how this data records "
                "a place whose coordinates were never established.  Nothing else is "
                "anywhere near that point, so the box collapses all 316 "
                "into a single location.",
        summary_zh="*Use XY* 會蒐集所有位於使用者所選地址 0.03 度以內的"
                   "地址——約三公里，這個構想本身是對的，用來把同一個"
                   "地方在兩個代碼下的紀錄合併起來。但 `ADDR_CODES` 中"
                   "有 316 個地址的座標正好是 `x_coord = 0, y_coord = "
                   "0`：那是一些從未確定座標的明代衛所。而那個點附近"
                   "再無其他任何東西，於是這個範圍框就把這 316 個地址"
                   "全部併成了同一個地點。",
        evidence="Driven on the Places form with a single unmapped "
                 "address chosen from `ADDR_CODES`.  With Use XY off the "
                 "query returns nothing -- that address has no rows of "
                 "its own.  With Use XY on it returns rows drawn from "
                 "dozens of different addresses, none of which is near "
                 "the one asked for in any sense except that neither has "
                 "a coordinate.\n\nThe widening itself is correct as "
                 "written: 0.03 degrees is 2 to 3.5 kilometres anywhere "
                 "in China, the null-coordinate rows are carried forward "
                 "by a separate LEFT JOIN rather than dropped, and an "
                 "address with coordinates always matches itself.  What "
                 "the code does not do is distinguish \"at 0,0\" from "
                 "\"not located\", and the shipped data uses the first "
                 "to mean the second.",
        evidence_zh="在地點表單上，以從 `ADDR_CODES` 挑出的單一未定位"
                    "地址實測。關閉 Use XY 時查詢沒有回傳任何資料——"
                    "該地址本身沒有任何資料列。開啟 Use XY 後，回傳的"
                    "資料列來自數十個不同的地址，而這些地址與所查詢的"
                    "那一個，除了同樣沒有座標之外，在任何意義上都談不上"
                    "鄰近。\n\n這個擴展機制本身寫得是對的：0.03 度在"
                    "中國境內各地約當 2 至 3.5 公里，沒有座標的資料列"
                    "會由另一個 LEFT JOIN 一併帶入而不會被丟棄，"
                    "而有座標的地址一定會匹配到它自己。程式沒有做到的"
                    "是區分「位於 0,0」與「未定位」，而釋出的資料正是"
                    "以前者表示後者。",
        impact="A user ticks a box that means *catch the same place under "
               "a different code* and gets a query about every unmapped "
               "garrison in the database.  The addresses it added are not "
               "shown anywhere, so the result cannot be recognised as "
               "wrong from the screen; and because the switch legitimately "
               "widens, nothing about the row count looks out of place.",
        impact_zh="使用者勾選的是一個意思為「把同一個地方在其他代碼下的"
                  "紀錄一併找出來」的選項，得到的卻是一個涵蓋資料庫中"
                  "所有未定位衛所的查詢。它額外加入了哪些地址並不會顯示"
                  "在任何地方，因此單看畫面無法察覺結果有誤；又因為這個"
                  "選項本來就會擴大範圍，資料列變多這件事看起來也毫無"
                  "異常。",
        fix="Exclude the sentinel from the widening: require `x_coord <> "
            "0 OR y_coord <> 0` on both sides of the join, or treat 0,0 "
            "as unlocated the way the null coordinates are already "
            "treated -- carried forward as themselves and not matched "
            "against anything.  The second is the closer parallel to what "
            "the code already does for NULL, and would need no new "
            "concept.",
        fix_zh="請把這個哨兵值排除在擴展之外：在連接的兩側都要求 "
               "`x_coord <> 0 OR y_coord <> 0`；或是比照程式目前對待 "
               "NULL 座標的方式，把 0,0 視為未定位——原樣帶入，不與任何"
               "其他地址匹配。後者與程式現有的 NULL 處理最為相近，"
               "也不需要引入任何新的概念。",
        steps=(
            "SELECT c_addr_id, c_name FROM ADDR_CODES WHERE x_coord = 0 "
            "AND y_coord = 0 LIMIT 5;",
            "On Look At Places, filter on one of those addresses with Use "
            "XY off: the query returns nothing.",
            "Tick Use XY and run it again: rows come back, from dozens of "
            "unrelated garrisons.",
        ),
        steps_zh=(
            "執行：SELECT c_addr_id, c_name FROM ADDR_CODES WHERE "
            "x_coord = 0 AND y_coord = 0 LIMIT 5;",
            "在地點查詢頁面上以其中一個地址進行篩選，並關閉 Use XY："
            "查詢不會回傳任何資料。",
            "勾選 Use XY 後重新執行：資料列出現了，來自數十個彼此無關"
            "的衛所。",
        ),
        source=("Code/office_form_backend.go:480",
                "Code/office_form_backend.go:496"),
        tests=("test_use_xy_does_not_treat_the_unmapped_corner_as_a_place",),
    ),
)

#: What the report iterates.  Keyed by ``Defect.key`` (CBDB-D-0NN),
#: which is assigned while writing one report and means nothing outside
#: it -- that is why the waiver table is keyed by test names instead.
DEFECTS: dict[str, Defect] = {defect.key: defect for defect in _DEFECTS}

"""The registry the report is written from -- and nothing else.

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
        title="The Places form runs the Biography branch when the user has "
              "switched every category off",
        title_zh="使用者把所有類別都取消勾選時，地點表單仍然執行「傳記」那一支"
                 "查詢",
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
        evidence="With every category switched off the query returned 396 "
                 "rows, and the same request with Biography alone switched "
                 "on returned the same 396 rows -- the empty selection is "
                 "not merely non-empty, it is exactly the Biography "
                 "branch's own result.  Measured through the running "
                 "binary; the substitution is then visible in the source.",
        evidence_zh="七個類別全部取消勾選時，查詢回傳 396 列；把同一個請求"
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
            "Open the Places form (/LookAtPlace) and select any address.",
            "Untick all seven category checkboxes, including Biography.",
            "Press Run Query: rows come back.",
            "Tick Biography only and run again: the same rows, in the same "
            "number.",
        ),
        steps_zh=(
            "開啟地點表單（/LookAtPlace），任選一個地址。",
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
        title="Seventeen export buttons ask the browser to save several "
              "files at once, and thirteen of them report every file as "
              "saved when only the first arrived",
        title_zh="十七個匯出按鈕會一次要求瀏覽器儲存多個檔案，其中十三個更"
                 "在只有第一個檔案下載成功時，回報所有檔案都已儲存",
        area="Export buttons on seven form pages",
        area_zh="七個表單頁面上的匯出按鈕",
        summary="These handlers loop over the file list the server returned "
                "and trigger a download per element from a single click.  A "
                "browser permits one automatic download per user gesture and "
                "blocks the rest, and once blocked the restriction applies "
                "to later exports from the same page -- which is why "
                "pressing Export a second time can save nothing at all.  "
                "Thirteen of the seventeen then print the count the *server* "
                "returned (\"2 file(s) ready\"), having never asked the "
                "browser what it accepted.",
        summary_zh="這些處理函式會走訪伺服器回傳的檔案清單，在單一次點擊中"
                   "為每個項目各觸發一次下載。瀏覽器對每個使用者手勢只允許"
                   "一次自動下載，其餘一律封鎖；而且一旦被封鎖，同一頁面之後"
                   "的匯出也會受限——這正是第二次按下匯出時可能完全存不到"
                   "檔案的原因。十七個之中有十三個接著印出的是「伺服器」回傳"
                   "的數量（例如「2 file(s) ready」），從未詢問瀏覽器實際接受"
                   "了幾個。",
        evidence="Counted in the shipped templates: 17 such handlers across "
                 "7 pages (association_pairs 4, associations 2, entry 2, "
                 "group_data 3, kinship 2, networks 2, places 2), of which "
                 "13 report a server-side count as though it were the "
                 "outcome (association_pairs 4, associations 2, entry 1, "
                 "group_data 2, kinship 2, places 2).  The server side is "
                 "faultless: the same endpoints return every file, "
                 "identically, on repeated requests.  Under automation "
                 "downloads are auto-accepted and both files arrive, so the "
                 "blocking half is established by reading the delivery code "
                 "and was reported from real use; the misreported count is "
                 "measured in the browser.",
        evidence_zh="在釋出的模板中逐一計數：七個頁面共 17 處這樣的處理函式"
                    "（association_pairs 4、associations 2、entry 2、"
                    "group_data 3、kinship 2、networks 2、places 2），其中 13 "
                    "處會把伺服器端的數量當成實際結果回報（association_pairs "
                    "4、associations 2、entry 1、group_data 2、kinship 2、"
                    "places 2）。伺服器端本身沒有問題：同樣的端點在重複請求下"
                    "都會完整、一致地回傳每個檔案。在自動化環境中下載會被自動"
                    "接受、兩個檔案都會到齊，因此「被封鎖」這一半是透過閱讀"
                    "頁面的下載程式碼確認的，並且來自實際使用時的回報；"
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
                "Templates/places/index.html:691"),
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
               "for_a_column_it_lacks"),
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
                 "declares the column `CHAR(255)`, and a read-only count "
                 "over the shipped database finds all 30,100 values are of "
                 "type text, the commonest being \"Xian\" (13,687 rows).  So "
                 "a rebuild of the data would not change it: the declared "
                 "type in the Go struct is wrong.",
        evidence_zh="端點回應 `500 Neo4j export error: scan addrRow: sql: "
                    "Scan error on column index 3, name \"admin_type\": "
                    "converting driver.Value type string (\"Xian\") to a "
                    "int: invalid syntax`。釋出的結構描述把該欄位宣告為 "
                    "`CHAR(255)`；以唯讀方式統計釋出的資料庫，30,100 個值"
                    "全部都是文字型別，最常見的是 \"Xian\"（13,687 列）。"
                    "因此重建資料不會改變結果：問題在於 Go 結構中宣告的型別"
                    "有誤。",
        impact="The Associations form cannot export to Neo4j for any query "
               "whose people have addresses, which is almost all of them.  "
               "The user sees a server error.",
        impact_zh="只要查詢結果中的人物帶有地址（幾乎都會帶有），關聯表單就"
                  "無法匯出到 Neo4j，使用者只會看到伺服器錯誤。",
        fix="Declare the field `string` and read it as text -- the "
            "`COALESCE(c_admin_type, 0)` in the same SELECT should become "
            "`COALESCE(c_admin_type, '')` to match.  The other forms' Neo4j "
            "exports read the same table and are worth checking in the same "
            "commit.",
        fix_zh="把該欄位宣告為 `string` 並以文字讀取；同一段 SELECT 中的 "
               "`COALESCE(c_admin_type, 0)` 也應一併改為 "
               "`COALESCE(c_admin_type, '')` 以相符。其他表單的 Neo4j 匯出"
               "同樣讀取這個表，建議在同一次修改中一併檢查。",
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
                "Data/cbdb.db.schema.sql:42"),
        tests=("test_an_export_produces_a_well_formed_file",
               "test_an_export_describes_the_people_the_"
               "grid_did",
               "test_an_export_is_repeatable",
               "test_a_spreadsheet_export_can_be_opened_"
               "by_a_spreadsheet"),
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
)

#: What the report iterates.  Keyed by ``Defect.key`` (CBDB-D-0NN),
#: which is assigned while writing one report and means nothing outside
#: it -- that is why the waiver table is keyed by test names instead.
DEFECTS: dict[str, Defect] = {defect.key: defect for defect in _DEFECTS}

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
           "results, with no error shown to the user.",
           "靜默的錯誤結果——程式回傳錯誤或空白的結果，而且沒有任何錯誤提示。"),
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


@dataclass(frozen=True)
class Defect:
    """One confirmed defect in the shipped build, in both languages."""

    key: str
    priority: str            # "P0" … "P4"
    severity: str            # "high" | "medium" | "low"
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
        key="CBDB-D-001",
        priority="P0",
        severity="high",
        title="Person search finds nothing for terms of three or more characters",
        title_zh="人物搜尋：輸入三個字元以上就完全找不到人",
        area="People browser (/CBDB_Browser)",
        area_zh="人物瀏覽（/CBDB_Browser）",
        summary=(
            "Data/CBDB.db ships ZZZ_NAMES_FTS -- the external-content FTS5 "
            "trigram index over ZZZ_NAMES -- created together with its sync "
            "triggers but never populated.  SQLite uses that index for LIKE "
            "patterns of three or more characters and scans the content table "
            "below that, so short searches work and every realistic one "
            "silently returns nothing."),
        summary_zh=(
            "Data/CBDB.db 裡的 ZZZ_NAMES_FTS 是建立在 ZZZ_NAMES 之上的 FTS5 "
            "trigram 外部內容索引。索引表和同步觸發器都建好了，卻從未灌入內容。"
            "SQLite 在 LIKE 樣式達到三個字元時會改走這個索引，未達三個字元則"
            "回頭掃描內容表；因此短字串搜尋正常，而任何實際會用到的搜尋都"
            "靜默地回傳空結果。"),
        evidence=(
            "ZZZ_NAMES holds 866,011 names; ZZZ_NAMES_FTS_idx and "
            "ZZZ_NAMES_FTS_docsize are empty and ZZZ_NAMES_FTS_data holds 2 "
            "rows.  Through the shipped binary: 'wa' returns 56,504 (correct), "
            "'Wang' returns 0 of 50,493, 'Wang Anshi' returns 0 of 5, "
            "'王安石' returns 0 of 2, while '王安' correctly returns 146.  "
            "Rebuilding the index on a copy takes about 4 seconds and makes "
            "every one of those searches return exactly the counts the data "
            "supports."),
        evidence_zh=(
            "ZZZ_NAMES 共 866,011 筆姓名；ZZZ_NAMES_FTS_idx 與 "
            "ZZZ_NAMES_FTS_docsize 皆為空，ZZZ_NAMES_FTS_data 只有 2 列。"
            "透過釋出的執行檔實測：搜尋「wa」回傳 56,504 筆（正確）；"
            "「Wang」回傳 0 筆，實際應有 50,493 筆；「Wang Anshi」回傳 0 筆，"
            "應有 5 筆；「王安石」回傳 0 筆，應有 2 筆；而兩個字的「王安」"
            "則正確回傳 146 筆。在複本上重建索引約需 4 秒，之後上述每一項"
            "搜尋都回傳與資料相符的筆數。"),
        impact=(
            "The primary way of finding a person is broken for essentially "
            "every realistic query.  A full surname, a full name, or a "
            "three-character Chinese name returns an empty list that is "
            "indistinguishable from 'this person is not in CBDB'.  All 658,941 "
            "people are affected; the underlying data is intact."),
        impact_zh=(
            "使用者尋找人物最主要的途徑，在幾乎所有實際查詢下都失效。輸入完整"
            "姓氏、完整姓名，或三個漢字的中文名，都只會得到一份空清單——這在"
            "畫面上與「CBDB 裡沒有這個人」完全無法區分。全部 658,941 位人物"
            "都受影響；底層資料本身並未損壞。"),
        fix=(
            "Run INSERT INTO ZZZ_NAMES_FTS(ZZZ_NAMES_FTS) VALUES('rebuild') "
            "against the release database -- CBDBSetUpCode/zzznames_backend.go "
            "already does this as part of RunZZZNames -- and assert at build "
            "time that ZZZ_NAMES_FTS_docsize and ZZZ_NAMES have equal counts."),
        fix_zh=(
            "對釋出用的資料庫執行 "
            "INSERT INTO ZZZ_NAMES_FTS(ZZZ_NAMES_FTS) VALUES('rebuild')。"
            "CBDBSetUpCode/zzznames_backend.go 的 RunZZZNames 其實已經包含"
            "這一步，只是沒有對釋出檔執行過。建議同時在建置流程加一道檢查："
            "ZZZ_NAMES_FTS_docsize 與 ZZZ_NAMES 的筆數必須相等。"),
        steps=(
            "Start CBDB-Desktop and open the People browser (/CBDB_Browser).",
            "Type `Wang` into the search box. The list comes back empty.",
            "Now type `wa` instead. 56,504 people are found — the data is "
            "there, and the only difference is the number of characters.",
            "The same happens in Chinese: `王安` finds 146 people, `王安石` "
            "finds none.",
            "At the database level: `SELECT COUNT(*) FROM "
            "ZZZ_NAMES_FTS_docsize` returns 0, while `SELECT COUNT(*) FROM "
            "ZZZ_NAMES` returns 866,011.",
        ),
        steps_zh=(
            "啟動 CBDB-Desktop，開啟人物瀏覽頁面（/CBDB_Browser）。",
            "在搜尋框輸入 `Wang`，結果清單為空。",
            "改輸入 `wa`，卻找到 56,504 人——資料其實都在，差別只在字元數。",
            "中文也一樣：`王安` 找到 146 人，`王安石` 一人也找不到。",
            "在資料庫層確認：`SELECT COUNT(*) FROM ZZZ_NAMES_FTS_docsize` "
            "回傳 0，而 `SELECT COUNT(*) FROM ZZZ_NAMES` 回傳 866,011。",
        ),
        source=("Code/browser_form_backend.go:812",
                "CBDBSetUpCode/zzznames_backend.go:114",
                "Data/CBDB.db.schema.sql:1035"),
        tests=("test_searching_people_by_name_finds_them",
               "test_the_name_search_index_is_populated"),
    ),
    Defect(
        key="CBDB-D-004",
        priority="P0",
        severity="high",
        title="Another form's query silently empties the Associations export",
        title_zh="其他表單的查詢會靜默清空「社會關係」的匯出結果",
        area="Associations form (/LookAtAssociations)",
        area_zh="社會關係表單（/LookAtAssociations）",
        summary=(
            "The Associations export takes no request body and no lock: it "
            "re-reads ZZ_SOCIAL_NETWORK and ZZ_SCRATCH_PEOPLE, the scratch "
            "tables its own query filled.  Association Pairs and Networks "
            "clear ZZ_SOCIAL_NETWORK at the start of their own queries, so "
            "visiting either between pressing Query and pressing Export "
            "replaces the result with an empty file.  Kinship clears only "
            "ZZ_SCRATCH_PEOPLE, which empties the second exported file "
            "rather than the first."),
        summary_zh=(
            "「社會關係」的匯出不接受任何請求內容，也不加鎖：它直接重讀 "
            "ZZ_SOCIAL_NETWORK 與 ZZ_SCRATCH_PEOPLE 這兩張由自己的查詢填入的"
            "暫存表。而「關係配對」與「社會網路」在各自查詢一開始就會清空 "
            "ZZ_SOCIAL_NETWORK；因此只要在按下「查詢」與按下「匯出」之間"
            "去過其中任一表單，匯出得到的就是一個空檔案。「親屬關係」只清空 "
            "ZZ_SCRATCH_PEOPLE，因此影響的是第二個匯出檔而非第一個。"),
        evidence=(
            "Through the shipped binary: an Associations query returns 55 "
            "rows and exports 55 rows.  A single POST /api/assocpairs/query "
            "then leaves the same export returning 0 rows -- HTTP 200, status "
            "'ok', a file with nothing in it but a header.  No error is "
            "reported at any point."),
        evidence_zh=(
            "透過釋出的執行檔實測：一次「社會關係」查詢得到 55 列，匯出也是 "
            "55 列。接著只要送出一次 POST /api/assocpairs/query，同一個匯出"
            "就只剩 0 列——HTTP 狀態 200、status 為 'ok'、檔案裡除了標題列"
            "什麼都沒有。整個過程沒有任何錯誤訊息。"),
        impact=(
            "A user loses their result with no indication that anything "
            "happened.  The export button still works, the file still "
            "downloads, and it is empty.  Reaching the state takes nothing "
            "unusual: run a query, look at a related form, come back and "
            "export."),
        impact_zh=(
            "使用者的查詢結果就這樣不見了，而且完全沒有任何提示。匯出按鈕照常"
            "可按、檔案照常下載，只是裡面是空的。要走到這一步也不需要什麼特別"
            "操作：跑一次查詢、去看一下相關的表單、回來按匯出，就會發生。"),
        fix=(
            "Have the export render the result it is given, as the office, "
            "status, texts and places exports already do; or key the scratch "
            "tables per session and hold associationsMu across the "
            "query-and-export pair."),
        fix_zh=(
            "讓匯出改為輸出呼叫端傳入的結果——「官職」「社會地位」「著述」"
            "「地點」四個表單的匯出本來就是這樣做的；或者把暫存表改為以工作"
            "階段（session）區分，並讓 associationsMu 涵蓋「查詢＋匯出」"
            "這一對操作。"),
        steps=(
            "Open the Associations form, pick an association type and press "
            "Query. The grid fills (55 rows in our run).",
            "Without closing anything, open the Association Pairs form and "
            "run any query there.",
            "Go back to the Associations form and press Export Results.",
            "The downloaded file contains only its header row. No error is "
            "shown at any point.",
        ),
        steps_zh=(
            "開啟「社會關係」表單，選一個關係類別，按下「查詢」。表格出現"
            "結果（我們的實測是 55 列）。",
            "不要關閉任何視窗，開啟「關係配對」表單，在那裡執行任何一次查詢。",
            "回到「社會關係」表單，按下「匯出結果」。",
            "下載到的檔案只有標題列。整個過程沒有出現任何錯誤訊息。",
        ),
        source=("Code/associations_form_backend.go:932 (the export reads "
                "ZZ_SOCIAL_NETWORK, taking no lock)",
                "Code/assocpairs_form_backend.go:417 (clears it)",
                "Code/networks_form_backend.go:1190 (clears it)",
                "Code/kinship_form_backend.go:750 (clears ZZ_SCRATCH_PEOPLE, "
                "so the people file empties instead)"),
        tests=("test_another_form_does_not_empty_the_associations_export",),
    ),
    Defect(
        key="CBDB-D-006",
        priority="P1",
        severity="high",
        title="A malformed ranking is accepted and applied to every person",
        title_zh="格式不正確的排序設定會被接受，並套用到每一位人物身上",
        area="Index address rankings (/IndexAddr)",
        area_zh="索引地址排序（/IndexAddr）",
        summary=(
            "POST /api/indexaddr/update declares its body as a nine-slot "
            "array and validates nothing about its length.  Go's JSON decoder "
            "zero-pads a shorter array and truncates a longer one without "
            "error, so a request with the wrong number of slots is accepted "
            "and applied -- and this is the one endpoint in the application "
            "that rewrites CBDB data rather than scratch."),
        summary_zh=(
            "POST /api/indexaddr/update 把請求內容宣告為九個欄位的陣列，卻"
            "完全沒有檢查長度。Go 的 JSON 解碼器會把過短的陣列補零、把過長的"
            "陣列截斷，兩者都不報錯；因此欄位數不對的請求會被照單全收並實際"
            "套用——而這正是整個程式裡唯一會改寫 CBDB 正式資料（而非暫存表）"
            "的端點。"),
        evidence=(
            "Against the shipped binary, on a private copy: a ranks array of "
            "eight elements answers 200 'Rankings updated and BIOG_MAIN "
            "rebuilt successfully' and installs address type 0 ('unknown') at "
            "rank 9, changing the number of people with an index address from "
            "383,322 to 379,051.  An eleven-element array is accepted too, "
            "with the last two types silently discarded.  The bodies that are "
            "refused are refused for unrelated reasons: a string fails in the "
            "JSON decoder, while a two-element array and an absent field are "
            "zero-padded and then caught by the duplicate-type check, because "
            "padding leaves several slots holding address type 0.  Eight slots "
            "leave only one, so nothing catches them."),
        evidence_zh=(
            "在獨立複本上對釋出的執行檔實測：送出只有八個元素的 ranks 陣列，"
            "回應為 200「Rankings updated and BIOG_MAIN rebuilt "
            "successfully」，並把地址類型 0（unknown）放進第 9 順位；擁有"
            "索引地址的人數也從 383,322 變成 379,051。送出十一個元素同樣被"
            "接受，最後兩個類型被靜默丟棄。至於那些會被拒絕的請求，其實都不是"
            "因為長度：字串在 JSON 解碼階段就失敗；兩個元素的陣列與完全沒有"
            "該欄位的請求，是補零之後多出好幾個地址類型 0，才被「重複類型」"
            "檢查攔下來。八個元素只會補出一個 0，因此沒有任何檢查攔得住。"),
        impact=(
            "A client that sends the wrong number of slots -- an older or "
            "newer page, a script, a partially-filled form -- silently "
            "reconfigures the index address of every person in the database "
            "and ranks 'unknown' as a real address type.  Nothing reports it, "
            "and the previous ranking is gone; /reset restores only the "
            "shipped default, so a ranking the user had configured is lost "
            "for good."),
        impact_zh=(
            "只要送出的欄位數不對——版本較舊或較新的頁面、自行撰寫的腳本、"
            "填了一半的表單——就會靜默地重設資料庫中每一位人物的索引地址，"
            "並把「unknown」當成一個正式的地址類型排進順位。過程中沒有任何"
            "提示，而原本的排序也就此消失：/reset 只能還原成出廠預設值，"
            "使用者自行設定過的排序無法救回。"),
        fix=(
            "Decode the ranks into a slice and reject a body that does not "
            "carry exactly nine slots, and reject address types that are not "
            "in BIOG_ADDR_CODES (0 is a real row, 'unknown', which is why the "
            "padding goes unnoticed)."),
        fix_zh=(
            "改用 slice 解碼 ranks，並拒絕欄位數不等於九的請求；同時拒絕"
            "不存在於 BIOG_ADDR_CODES 的地址類型。（0 在 BIOG_ADDR_CODES 中"
            "是一筆真實資料，名稱為 unknown，這正是補零之所以無人察覺的原因。）"),
        steps=(
            "Send POST /api/indexaddr/update with a `ranks` array of eight "
            "entries instead of nine — for example from a page belonging to a "
            "different build.",
            "The response is 200: 'Rankings updated and BIOG_MAIN rebuilt "
            "successfully'.",
            "Open the Index Address form. Rank 9 now holds address type 0 "
            "('unknown'), which was never selected.",
            "Count people with an index address: 383,322 before the request, "
            "379,051 after.",
            "Press Reset. The shipped default order returns — but any ranking "
            "the user had configured is gone.",
        ),
        steps_zh=(
            "送出 POST /api/indexaddr/update，其中 `ranks` 陣列只有八個元素"
            "而非九個——例如來自另一個版本的頁面。",
            "回應為 200：「Rankings updated and BIOG_MAIN rebuilt "
            "successfully」。",
            "開啟「索引地址」表單，第 9 順位出現地址類型 0（unknown），"
            "而這是使用者從未選過的。",
            "統計擁有索引地址的人數：請求之前為 383,322，之後為 379,051。",
            "按下「重設」，出廠預設順序會回來——但使用者原先設定過的排序"
            "已經永久遺失。",
        ),
        source=("Code/indexaddr_form_backend.go:69 (Ranks is a fixed [9]int)",
                "Code/indexaddr_form_backend.go:182 (decode, then no length "
                "check)",
                "Code/indexaddr_form_backend.go:199 (the duplicate check that "
                "accidentally catches the other bad bodies)"),
        tests=("test_a_ranking_of_the_wrong_length_is_refused",),
    ),
    Defect(
        key="CBDB-D-002",
        priority="P2",
        severity="medium",
        title="The Query Builder offers 30 columns that do not exist",
        title_zh="查詢建構器提供了 30 個並不存在的欄位",
        area="Query Builder (/QBE)",
        area_zh="查詢建構器（/QBE）",
        summary=(
            "Data/qbe_schema.json lists 30 columns across 8 views that "
            "Data/CBDB.db does not have.  HasColumn validates a request "
            "against that JSON whitelist alone and never against the "
            "database, so each one passes validation and then fails in "
            "SQLite."),
        summary_zh=(
            "Data/qbe_schema.json 中列出了 8 個檢視表下的 30 個欄位，而 "
            "Data/CBDB.db 裡並沒有這些欄位。HasColumn 只拿這份 JSON 白名單"
            "驗證請求，從不對照真正的資料庫，因此這些欄位都能通過驗證，"
            "最後在 SQLite 執行時才失敗。"),
        evidence=(
            "Comparing the whitelist against PRAGMA table_info for all 99 "
            "offered tables finds 30 absent columns, in View_BiogInstAddrData, "
            "View_BiogInstData, View_BiogSourceData, View_BiogTextData, "
            "View_Entry, View_EventData, View_KinAddr and "
            "View_PostingOfficeData.  Selecting any of them through "
            "/api/qbe/run answers HTTP 500 'Query failed: no such column'.  "
            "Four of them are the first column their table offers, so the "
            "failure is one click away."),
        evidence_zh=(
            "以 PRAGMA table_info 比對白名單中全部 99 張表，找出 30 個不存在"
            "的欄位，分布於 View_BiogInstAddrData、View_BiogInstData、"
            "View_BiogSourceData、View_BiogTextData、View_Entry、"
            "View_EventData、View_KinAddr 與 View_PostingOfficeData。"
            "透過 /api/qbe/run 選用其中任一個，都會得到 HTTP 500"
            "「Query failed: no such column」。其中四個還正好是該表清單中的"
            "第一個欄位，使用者點一下就會踩到。"),
        impact=(
            "A user building a query picks a column from the grid's own "
            "dropdown and gets a server error with no indication that the "
            "column was never available.  The eight affected views are "
            "otherwise usable."),
        impact_zh=(
            "使用者從查詢建構器自己提供的下拉選單中挑了一個欄位，換來的卻是"
            "伺服器錯誤，而且完全看不出這個欄位其實從一開始就不可用。"
            "這 8 個檢視表的其他欄位仍可正常使用。"),
        fix=(
            "Regenerate Data/qbe_schema.json from the live schema with "
            "Code/gen_qbe_schema.py, and have LoadSchemaFromJSON verify each "
            "whitelisted column against the database at startup so a stale "
            "whitelist fails loudly instead of per-query."),
        fix_zh=(
            "用 Code/gen_qbe_schema.py 依實際結構重新產生 "
            "Data/qbe_schema.json；並讓 LoadSchemaFromJSON 在啟動時就逐一"
            "比對白名單欄位是否真的存在，讓過期的白名單在啟動階段就明確報錯，"
            "而不是等到使用者查詢時才失敗。"),
        steps=(
            "Open the Query Builder (/QBE).",
            "Add the table `View_Entry` to the grid.",
            "From its column list — the one the page itself supplies — pick "
            "`c_personid`.",
            "Press Run. The result is HTTP 500: 'Query failed: no such column: "
            "v.c_personid'.",
            "The same happens for 30 columns across 8 views; the full list is "
            "pinned in tests/test_qbe.py.",
        ),
        steps_zh=(
            "開啟查詢建構器（/QBE）。",
            "把 `View_Entry` 這張表加入查詢格線。",
            "從欄位清單——也就是頁面自己提供的那一份——選擇 `c_personid`。",
            "按下執行，得到 HTTP 500：「Query failed: no such column: "
            "v.c_personid」。",
            "8 個檢視表下共 30 個欄位都是如此；完整清單釘在 "
            "tests/test_qbe.py 中。",
        ),
        source=("Code/qbe_schema.go:89", "Code/gen_qbe_schema.py",
                "Data/qbe_schema.json"),
        tests=("test_every_offered_column_exists_in_the_database",
               "test_a_phantom_column_gives_the_user_a_server_error",
               "test_every_offered_table_can_actually_be_queried"),
    ),
    Defect(
        key="CBDB-D-005",
        priority="P3",
        severity="medium",
        title="The release ships a previous session's working state",
        title_zh="釋出檔中殘留了前一次使用的工作狀態",
        area="Shipped database (Data/CBDB.db)",
        area_zh="釋出的資料庫（Data/CBDB.db）",
        summary=(
            "Fourteen ZZ_* scratch tables in the released database still hold "
            "the results of somebody's working session.  The forms read those "
            "tables on startup, so a fresh install opens with a person "
            "already in its working list and exports that return a stranger's "
            "data before the user has run anything."),
        summary_zh=(
            "釋出的資料庫中有 14 張 ZZ_* 暫存表，仍留著某一次工作階段的結果。"
            "各表單啟動時會讀取這些表，因此全新安裝一打開，工作清單裡就已經"
            "有一個人物；而使用者什麼都還沒查詢，匯出就會給出別人的資料。"),
        evidence=(
            "On a fresh copy of the shipped database, before any request that "
            "changes state: /api/kinship/person-count and "
            "/api/networks/person-count both answer 1 (Ouyang Xiu, person "
            "1384, sits in ZZ_SCRATCH_IMPORT_PEOPLE); store-count answers 2; "
            "/api/assocpairs/recall-ids returns Lv Daqi and Lv Zuqian; the "
            "Entry export returns 123 rows and the Associations export 16, "
            "both from queries the user never ran.  ZZ_KIN_LIST (112 rows), "
            "ZZ_SCRATCH_KINNET (111), ZZ_SCRATCH_PEOPLE (88), "
            "ZZ_SCRATCH_ENTRY (123) and nine more are likewise populated."),
        evidence_zh=(
            "在釋出資料庫的全新複本上，於任何會改變狀態的請求之前："
            "/api/kinship/person-count 與 /api/networks/person-count 都回傳 1"
            "（ZZ_SCRATCH_IMPORT_PEOPLE 中是歐陽修，人物編號 1384）；"
            "store-count 回傳 2；/api/assocpairs/recall-ids 回傳呂大器與呂祖謙；"
            "「入仕」匯出得到 123 列、「社會關係」匯出得到 16 列，"
            "而這些查詢使用者從未執行過。ZZ_KIN_LIST（112 列）、"
            "ZZ_SCRATCH_KINNET（111 列）、ZZ_SCRATCH_PEOPLE（88 列）、"
            "ZZ_SCRATCH_ENTRY（123 列）等另外九張表同樣有殘留內容。"),
        impact=(
            "A new user's first Export gives them somebody else's result with "
            "no indication that it is not theirs, and the Kinship and "
            "Networks forms start with a person nobody selected.  It also "
            "means the release was built from a database that had been used, "
            "rather than from a clean one.  Self-limiting: every form "
            "truncates its own scratch tables before writing, so the state "
            "survives only until the user's first query -- which is why this "
            "is medium rather than high."),
        impact_zh=(
            "新使用者第一次按下匯出，拿到的是別人的查詢結果，而且完全看不出"
            "那不是自己的；「親屬關係」與「社會網路」表單一開始就已經帶著一個"
            "沒人選過的人物。這也表示這份釋出檔是從一個「用過的」資料庫打包"
            "出來的，而非乾淨的資料庫。影響是有限的：每個表單在寫入前都會先"
            "清空自己的暫存表，所以這些殘留只會存活到使用者第一次查詢為止——"
            "這也是本項評為中等而非高的原因。"),
        fix=(
            "Empty the ZZ_* scratch tables before packaging, and add a "
            "build-time assertion that they are empty.  Clearing them costs "
            "nothing: every form truncates its own scratch tables before "
            "writing to them anyway."),
        fix_zh=(
            "打包前清空所有 ZZ_* 暫存表，並在建置流程加一道檢查確認它們為空。"
            "清空幾乎沒有代價：每個表單本來就會在寫入前先清空自己的暫存表。"),
        steps=(
            "Install the release and start the application. Do nothing else.",
            "Open the Kinship form: the working list already contains Ouyang "
            "Xiu (person 1384).",
            "Open the Entry form and press Export Results without running a "
            "query. The file contains 123 rows.",
            "On the shipped Data/CBDB.db: `SELECT COUNT(*) FROM "
            "ZZ_SCRATCH_ENTRY` returns 123, and thirteen other ZZ_* tables "
            "are likewise non-empty.",
        ),
        steps_zh=(
            "安裝釋出版本並啟動程式，什麼都先別做。",
            "開啟「親屬關係」表單：工作清單裡已經有歐陽修（人物編號 1384）。",
            "開啟「入仕」表單，不執行任何查詢，直接按「匯出結果」，"
            "得到的檔案有 123 列。",
            "對釋出的 Data/CBDB.db 執行 `SELECT COUNT(*) FROM "
            "ZZ_SCRATCH_ENTRY` 會得到 123；另外還有十三張 ZZ_* 表同樣非空。",
        ),
        source=("Data/CBDB.db",
                "Code/kinship_form_backend.go:handlePersonCount",
                "Code/entry_form_backend.go:handleExportResults"),
        tests=("test_a_fresh_install_starts_with_no_working_state",),
    ),
    Defect(
        key="CBDB-D-003",
        priority="P4",
        severity="low",
        title="A name is indexed for a person the database does not contain",
        title_zh="姓名索引中有一位資料庫裡並不存在的人物",
        area="Name index (ZZZ_NAMES)",
        area_zh="姓名索引（ZZZ_NAMES）",
        summary=(
            "Person 100382 has rows in ZZZ_NAMES but no row in BIOG_MAIN.  "
            "ZZZ_NAMES is derived from BIOG_MAIN and ALTNAME_DATA at build "
            "time, so this is a row the derivation kept after its source "
            "dropped it."),
        summary_zh=(
            "人物編號 100382 在 ZZZ_NAMES 中有資料，但 BIOG_MAIN 裡沒有對應的"
            "那一筆。ZZZ_NAMES 是建置時由 BIOG_MAIN 與 ALTNAME_DATA 推導出來"
            "的，因此這是一筆在來源資料已經刪除後、推導結果卻仍保留下來的紀錄。"),
        evidence=(
            "One person id -- 100382, 元世祖 / 'Pouyuandaizhudi' -- appears in "
            "ZZZ_NAMES with no matching BIOG_MAIN row.  It is reachable by "
            "name search, and /api/browser/person/100382 then answers 404."),
        evidence_zh=(
            "只有一個人物編號有此問題：100382，元世祖 / 'Pouyuandaizhudi'。"
            "它出現在 ZZZ_NAMES 中，卻沒有對應的 BIOG_MAIN 資料。這個名字可以"
            "被搜尋到，但 /api/browser/person/100382 會回傳 404。"),
        impact=(
            "Minor: a single name that can be found and not opened.  Worth "
            "fixing mainly because it means the derivation can outlive its "
            "source, which would matter more at a larger scale."),
        impact_zh=(
            "影響輕微：只是一個找得到、卻打不開的名字。之所以仍建議處理，"
            "主要是因為它顯示推導結果可能比來源資料活得更久——若日後規模擴大，"
            "同類問題會更麻煩。"),
        fix=(
            "Rebuild ZZZ_NAMES from the current BIOG_MAIN, and add a "
            "referential check to the build."),
        fix_zh=(
            "以目前的 BIOG_MAIN 重新產生 ZZZ_NAMES，並在建置流程加入一道"
            "參照完整性檢查。"),
        steps=(
            "On the shipped database, list names whose person is missing: "
            "`SELECT DISTINCT n.c_personid FROM ZZZ_NAMES n LEFT JOIN "
            "BIOG_MAIN b ON b.c_personid = n.c_personid WHERE b.c_personid IS "
            "NULL` — one row comes back, 100382.",
            "Request that person from the running application: "
            "`GET /api/browser/person/100382` answers 404.",
        ),
        steps_zh=(
            "在釋出的資料庫上列出「有名字卻查無此人」的紀錄："
            "`SELECT DISTINCT n.c_personid FROM ZZZ_NAMES n LEFT JOIN "
            "BIOG_MAIN b ON b.c_personid = n.c_personid WHERE b.c_personid IS "
            "NULL`——回傳一列，100382。",
            "向執行中的程式請求這位人物："
            "`GET /api/browser/person/100382` 回傳 404。",
        ),
        source=("CBDBSetUpCode/zzznames_backend.go",),
        tests=("test_every_name_belongs_to_a_person_who_exists",),
    ),
)

DEFECTS: dict[str, Defect] = {defect.key: defect for defect in _DEFECTS}

#: Convenient aliases, so a test can name the defect it demonstrates
#: without repeating an identifier.
BY_NAME: dict[str, Defect] = {
    "name-search": DEFECTS["CBDB-D-001"],
    "qbe-phantom-columns": DEFECTS["CBDB-D-002"],
    "orphan-name": DEFECTS["CBDB-D-003"],
    "associations-export-clobbered": DEFECTS["CBDB-D-004"],
    "shipped-scratch-state": DEFECTS["CBDB-D-005"],
    "unvalidated-ranking": DEFECTS["CBDB-D-006"],
}

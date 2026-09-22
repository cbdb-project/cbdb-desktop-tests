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
        title="The Group Data form is completely inert: three unclosed "
              "quotes leave its whole script unparsed",
        title_zh="分群資料表單完全失效：三處未closing的引號使整段程式碼無法解析",
        area="Group Data page (/LookAtGroupData)",
        area_zh="分群資料頁面（/LookAtGroupData）",
        summary="Three lines on this page open a JavaScript string that the "
                "line never closes.  All three are the same shape -- a "
                "sentence about downloads where the opening quote of the "
                "second fragment is missing and a stray `'\"` was left at "
                "the end.  A JavaScript string may not span a line, so each "
                "is a syntax error; and because this page keeps the whole "
                "of its behaviour in a single inline `<script>`, the "
                "browser discards the entire block.  Every function the "
                "page declares then does not exist.  The page still loads, "
                "still draws every control, and does nothing at all.\n\n"
                "The same three lines were among nine across three pages in "
                "the 2026-09-15_2 build.  The Association Pairs and Entry "
                "pages were repaired in 2026-09-16_2; Group Data was not.",
        summary_zh="這個頁面有三行程式碼開啟了字串卻沒有在同一行收尾。三處的"
                   "錯誤形狀相同：一句關於下載的訊息，後半段的起始引號不見"
                   "了，結尾還多留了一個 `'\"`。JavaScript 的字串不能跨行，"
                   "所以每一處都是語法錯誤；而這個頁面把全部行為都寫在單一"
                   "的內嵌 `<script>` 裡，因此瀏覽器會整塊放棄不執行。頁面"
                   "宣告的每一個函式都因此不存在。頁面照樣載入、照樣畫出所有"
                   "控制項，然後什麼也不做。\n\n"
                   "在 2026-09-15_2 版中，同樣形狀的錯誤共有九處、分布於三"
                   "個頁面。關聯配對與入仕兩頁已在 2026-09-16_2 版修好，分群"
                   "資料這一頁沒有。",
        evidence="Measured in a real Chromium: of the ten functions this "
                 "page's own buttons are wired to, none exists after the "
                 "page has loaded, while the other fifteen pages lose none.  "
                 "Every enabled button fires and raises `ReferenceError: "
                 "<name> is not defined`; the thirteen controls that ship "
                 "disabled can never be un-greyed, because the code that "
                 "would enable them is gone.  The page logs "
                 "`SyntaxError: missing ) after argument list` on load and "
                 "the server answers HTTP 200, serving the broken text "
                 "verbatim.  The same sentence is written correctly "
                 "eighteen times elsewhere in the build, which is what "
                 "identifies this as an unfinished repair rather than a "
                 "change anyone chose.",
        evidence_zh="以真實的 Chromium 實測：這個頁面的按鈕所連結的十個函式，"
                    "在頁面載入後一個都不存在，其餘十五個頁面則一個都沒少。"
                    "每一個可按的按鈕按下去都會拋出 "
                    "`ReferenceError: <名稱> is not defined`；那十三個一開始"
                    "就設為停用的控制項永遠無法啟用，因為負責啟用它們的程式"
                    "碼已經不存在。頁面載入時會記錄 "
                    "`SyntaxError: missing ) after argument list`，伺服器則"
                    "回 HTTP 200，原封不動送出這段壞掉的文字。同一句話在這"
                    "個版本的其他地方總共寫對了十八次——這說明它是一次沒有做"
                    "完的修補，而不是有人刻意改成這樣。",
        impact="A historian who opens this form can do nothing on it.  Run "
               "Query does not run, Import does not import, the language "
               "buttons do not switch, the tabs do not change, and every "
               "export button is dead -- with no error message anywhere, "
               "because the function that would show one was discarded with "
               "the rest.  Seven endpoints are reachable from no page at all "
               "as a result.  It is filed P0 under the band's own words -- "
               "the application returns empty results with no error shown "
               "to the user -- and the reason for saying so plainly is that "
               "nothing is computed wrongly here: nothing is computed at "
               "all.",
        impact_zh="研究者打開這個表單後什麼事也做不了。執行查詢按了沒反應、"
                  "匯入沒有作用、語言切換無效、分頁切不動，所有匯出按鈕也"
                  "全部失效——而且完全看不到任何錯誤訊息，因為負責顯示錯誤的"
                  "函式也一起被丟掉了。連帶使得七個 API 端點再也沒有任何頁面"
                  "到得了。本項列為 P0，依據的是該級別本身的定義——程式回傳"
                  "空白結果且沒有任何錯誤提示；要特別說明的是，這裡並不是算"
                  "錯了什麼，而是根本沒有進行任何運算。",
        fix="One character per line, three lines.  Each reads\n\n"
            "    showSuccess('X: ' + (j.files || []).length +  file(s) "
            "offered for download — check each Save dialog.'\");\n\n"
            "and should read\n\n"
            "    showSuccess('X: ' + (j.files || []).length + ' file(s) "
            "offered for download — check each Save dialog.');\n\n"
            "-- the opening quote restored before ` file(s)`, and the "
            "trailing `'\");` reduced to `');`.  The Entry and Association "
            "Pairs pages already carry the repaired form and can be copied "
            "from.  Worth running the page through `node --check` "
            "afterwards, or opening it and watching the browser console: a "
            "page whose script parsed logs nothing.",
        fix_zh="三行、每行一個字元。每一行目前是\n\n"
               "    showSuccess('X: ' + (j.files || []).length +  file(s) "
               "offered for download — check each Save dialog.'\");\n\n"
               "應該改為\n\n"
               "    showSuccess('X: ' + (j.files || []).length + ' file(s) "
               "offered for download — check each Save dialog.');\n\n"
               "——在 ` file(s)` 前補回起始引號，並把結尾的 `'\");` 改成 "
               "`');`。入仕與關聯配對兩個頁面已經是改好的樣子，可以直接照"
               "抄。改完後建議用 `node --check` 檢查這個頁面，或直接打開它"
               "看瀏覽器主控台：只要程式能解析，就不會有任何輸出。",
        steps=(
            "Open the Group Data form (/LookAtGroupData).",
            "Press any button -- Import, Run Query, or one of the language "
            "buttons.",
            "Nothing happens, and no message appears.",
            "Open the browser's developer console: it shows "
            "'SyntaxError: missing ) after argument list' from the page "
            "itself, and a ReferenceError for each button pressed.",
        ),
        steps_zh=(
            "打開分群資料表單（/LookAtGroupData）。",
            "按下任何一個按鈕——匯入、執行查詢，或任一個語言切換按鈕。",
            "什麼都不會發生，也不會出現任何訊息。",
            "打開瀏覽器的開發者主控台：可以看到頁面本身拋出 "
            "'SyntaxError: missing ) after argument list'，以及每按一次"
            "按鈕就多一則 ReferenceError。",
        ),
        source=("Templates/group_data/index.html:923",
                "Templates/group_data/index.html:956",
                "Templates/group_data/index.html:982"),
        tests=("test_every_page_script_closes_every_string_it_opens",
               "test_every_page_the_build_serves_loads_without_throwing",
               "test_every_button_is_wired_to_a_function_that_exists"),
    ),
    Defect(
        key="CBDB-D-002",
        priority="P0", severity="high", origin="software",
        title="Looking a person up in the Browser silently replaces the "
              "Kinship form's result, and the export then describes two "
              "people at once",
        title_zh="在瀏覽器中查閱某個人物，會無聲地取代親屬表單的查詢結果，"
                 "接著匯出的檔案會同時描述兩個不同的人",
        area="Kinship form and the Browser's kinship tab",
        area_zh="親屬表單，以及瀏覽器的親屬分頁",
        summary="`handleGetKinship` begins by deleting `ZZ_KIN_LIST`, "
                "`ZZ_KIN_LIST_TMP`, `ZZ_SCRATCH_KIN` and "
                "`ZZ_SCRATCH_KINNET` -- which is where the Kinship form's "
                "query put its answer.  So looking somebody up in the "
                "Browser, or pressing Export Profile there, overwrites a "
                "result the Kinship form is still displaying.  The form's "
                "Export Query Results then reads those tables and gets the "
                "new person's traversal, while `KinshipPeople.tsv` comes "
                "from `ZZ_SP_KINSHIP`, which that handler does not touch, "
                "and still describes the old one.",
        summary_zh="`handleGetKinship` 一開始就會清空 `ZZ_KIN_LIST`、"
                   "`ZZ_KIN_LIST_TMP`、`ZZ_SCRATCH_KIN` 與 "
                   "`ZZ_SCRATCH_KINNET`——而這幾張表正是親屬表單查詢結果的"
                   "存放處。因此只要在瀏覽器中查閱另一個人，或在那裡按下"
                   "Export Profile，就會覆蓋親屬表單畫面上仍然顯示著的結果。"
                   "此時該表單的 Export Query Results 讀到的是新那個人的"
                   "結果，而 `KinshipPeople.tsv` 來自該處理程序不會清空的 "
                   "`ZZ_SP_KINSHIP`，描述的仍是原來那個人。",
        evidence="Driven: with a Kinship result for person 1 on screen, a "
                 "GET of person 10's kinship changes what Export Query "
                 "Results returns -- `EgoRelativeKinship.tsv` and "
                 "`KinshipNetwork.tsv` both come back with different "
                 "content -- while `KinshipPeople.tsv` comes back byte for "
                 "byte the same.  Neither page says anything.  Re-running "
                 "the Kinship query returns its rows, so the result was "
                 "replaced rather than damaged: the user is exporting "
                 "somebody else's traversal.  The form's five other exports "
                 "build their rows from what the page posts to them and are "
                 "unaffected; this is Export Query Results alone.",
        evidence_zh="實測結果：畫面上是人物 1 的親屬查詢結果時，對人物 10 "
                    "發出一次親屬查詢，Export Query Results 的輸出就變了——"
                    "`EgoRelativeKinship.tsv` 與 `KinshipNetwork.tsv` 的"
                    "內容都不同了——而 `KinshipPeople.tsv` 則一個位元組都"
                    "沒變。兩個頁面都沒有任何提示。重新執行親屬查詢仍會回傳"
                    "資料，可見結果是被取代而非毀損：使用者匯出的是別人的"
                    "親屬網絡。該表單另外五個匯出功能都是依頁面送過去的資料"
                    "組成，不受影響；出問題的只有 Export Query Results。",
        impact="The three files in one download describe two different "
               "people, and nothing in them says so.  A researcher who runs "
               "a kinship query, glances somebody up in the Browser and "
               "then exports -- an ordinary sequence -- gets a bundle whose "
               "parts disagree.  Because the file names and the row shapes "
               "are unchanged, the mistake survives into whatever is built "
               "from them.",
        impact_zh="同一次下載的三個檔案描述的是兩個不同的人物，而檔案本身"
                  "沒有任何說明。研究者先執行一次親屬查詢，順手在瀏覽器裡"
                  "查了另一個人，再回來匯出——這是很自然的操作順序——拿到的"
                  "就是一份自相矛盾的檔案組。由於檔名與欄位結構都沒有變化，"
                  "這個錯誤會一路帶進後續用它們做出來的任何成果。",
        fix="Either give the Browser its own scratch tables for the kinship "
            "tab, as the 2026-09-07 build did for the forms that used to "
            "share theirs, or have it build the tab's answer without "
            "truncating anything.  If the sharing has to stay, the Kinship "
            "page at least needs to know its displayed result is no longer "
            "the one in the tables -- and Export Query Results should "
            "refuse rather than export a mixture.",
        fix_zh="兩種做法：一是像 2026-09-07 版為原本共用暫存表的那些表單所"
               "做的那樣，讓瀏覽器的親屬分頁擁有自己的暫存表；二是讓它在不"
               "清空任何東西的前提下組出該分頁的答案。若共用的設計必須保留，"
               "至少要讓親屬頁面知道「畫面上的結果已經不是表裡的那一份」，"
               "並且讓 Export Query Results 直接拒絕匯出，而不是送出一份"
               "混合的檔案。",
        steps=(
            "On the Kinship form, choose a person and run a query.",
            "Press Export Query Results and keep the three files.",
            "Open the Browser, look up a different person, and open their "
            "Kinship tab -- or simply press Export Profile.",
            "Return to the Kinship form, which still shows the first "
            "result, and export again: EgoRelativeKinship and "
            "KinshipNetwork now describe the person who was looked up, "
            "while KinshipPeople still describes the first one.",
        ),
        steps_zh=(
            "在親屬表單上選定一個人物並執行查詢。",
            "按下 Export Query Results，保留產生的三個檔案。",
            "開啟瀏覽器，查閱另一個人物，點開他的 Kinship 分頁"
            "——或者直接按下 Export Profile。",
            "回到親屬表單（畫面上仍是第一次的結果），再匯出一次："
            "EgoRelativeKinship 與 KinshipNetwork 描述的已是剛才查閱的"
            "那個人，KinshipPeople 描述的卻仍是最初那一位。",
        ),
        source=("Code/browser_form_backend.go:2104",
                "Code/browser_form_backend.go:2117",
                "Templates/browser/index.html:182"),
        tests=("test_looking_a_person_up_does_not_discard_a_kinship_result",
               "test_export_profile_loads_the_kinship_tab_it_lists"),
    ),
    Defect(
        key="CBDB-D-003",
        priority="P0", severity="medium", origin="software",
        title="Every multi-file export reports the server's file count as "
              "though the browser had saved them all",
        title_zh="所有會產生多個檔案的匯出功能，都把伺服器回報的檔案數當成"
                 "瀏覽器已經全部存檔",
        area="Ten pages, 22 export handlers",
        area_zh="十個頁面、22 個匯出處理程序",
        summary="Every export that produces more than one file delivers "
                "them by calling a download helper once per element of a "
                "list, from a single click.  The page then reports the "
                "count the *server* returned -- '3 file(s) offered for "
                "download' -- without asking the browser what it accepted. "
                " Chrome treats several downloads from one gesture as a "
                "permission to be granted, and a user who does not grant it "
                "gets fewer files than the page says they got.",
        summary_zh="所有會產生多個檔案的匯出，都是在一次點擊之後，對清單中的"
                   "每個元素各呼叫一次下載函式來送出檔案。頁面接著回報的是"
                   "*伺服器*送回的數量——「3 file(s) offered for download」"
                   "——卻從未詢問瀏覽器實際接受了幾個。Chrome 會把同一個動作"
                   "觸發的多個下載視為需要另行允許的權限，使用者若沒有允許，"
                   "拿到的檔案就會比頁面宣稱的少。",
        evidence="Read from the pages: 22 handlers across ten pages loop a "
                 "list and trigger one download per element, and 21 of them "
                 "then print the server's count as a success message.  The "
                 "counting half is confirmed under automation; the blocking "
                 "half is not reproducible there and is not claimed to be "
                 "-- a headless browser with `accept_downloads` accepts "
                 "every file, so Chrome's multiple-download permission "
                 "never engages.  What the browser test does establish is "
                 "that the page never consults the browser at all: the "
                 "number it prints comes only from the response.",
        evidence_zh="自頁面讀出：十個頁面共 22 個處理程序會走訪清單、每個"
                    "元素觸發一次下載，其中 21 個接著把伺服器回報的數量當成"
                    "成功訊息印出來。計數這一半已由自動化測試確認；被阻擋的"
                    "那一半在自動化環境中無法重現，本報告也不主張已經重現"
                    "——無頭瀏覽器開了 `accept_downloads` 會照單全收，Chrome "
                    "的多檔下載權限根本不會被觸發。瀏覽器測試真正證實的是："
                    "頁面從頭到尾沒有問過瀏覽器，它印出的數字只來自回應內容。",
        impact="A user can be told an export succeeded with three files "
               "when one arrived.  The missing files are not named and no "
               "error is shown, so the gap is discovered later, in the tool "
               "that needed them -- if at all.",
        impact_zh="使用者可能被告知匯出成功、共三個檔案，實際上只收到一個。"
                  "缺少的檔案不會被指出，也不會顯示任何錯誤，因此這個落差"
                  "往往要到後續使用那些檔案的工具裡才會被發現——如果還發現"
                  "得了的話。",
        fix="Report what was delivered rather than what was built.  The "
            "download helper can resolve per file, and the message can then "
            "name the count the browser accepted, or say plainly that "
            "several files are on their way and a prompt may appear.  "
            "Offering one archive per export instead of N files would "
            "remove the permission question altogether.",
        fix_zh="回報實際送達的數量，而不是產生的數量。下載函式可以逐檔回報"
               "結果，訊息再據此顯示瀏覽器實際接受的數量，或者明白告知使用者"
               "「接下來會有多個檔案，可能會跳出授權提示」。若改成每次匯出"
               "只提供一個壓縮檔而非 N 個檔案，這個權限問題就完全不存在了。",
        steps=(
            "Open any form with a Neo4j export and run a query.",
            "Press Export Neo4j CSVs.",
            "The page reports the number of files the server built.",
            "In a browser that has not been given the multiple-download "
            "permission for this site, fewer files are saved, and the "
            "message does not change.",
        ),
        steps_zh=(
            "打開任一個有 Neo4j 匯出的表單並執行查詢。",
            "按下 Export Neo4j CSVs。",
            "頁面回報的是伺服器產生的檔案數量。",
            "若瀏覽器尚未對本網站授予多檔下載權限，實際存下的檔案會比較少，"
            "而該訊息不會有任何不同。",
        ),
        source=("Templates/office/index.html:854",
                "Templates/status/index.html:797",
                "Templates/texts/index.html:833"),
        tests=("test_no_page_asks_the_browser_for_more_than_one_download",
               "test_an_export_does_not_claim_more_files_than_it_delivered"),
    ),
    Defect(
        key="CBDB-D-004",
        priority="P0", severity="medium", origin="software",
        title="The ASCII Pajek export begins with a UTF-8 byte order mark",
        title_zh="ASCII 版的 Pajek 匯出檔開頭仍然帶著 UTF-8 的位元組順序記號",
        area="Networks form, Pajek export",
        area_zh="網絡表單的 Pajek 匯出",
        summary="`handleExportPajek` writes `utf8BOM` before anything else, "
                "whatever encoding was asked for.  The body honours the "
                "request -- the ASCII file's labels really are pinyin -- "
                "but the first three bytes of a file a user asked to be "
                "ASCII are a UTF-8 marker.",
        summary_zh="`handleExportPajek` 不論要求的是哪種編碼，都會先寫入 "
                   "`utf8BOM`。檔案內容本身有遵守要求——ASCII 版的標籤確實"
                   "是拼音——但使用者指定要 ASCII 的檔案，開頭三個位元組卻"
                   "是 UTF-8 的記號。",
        evidence="`network_ascii.net` and `network_UTF8.net`, built from the "
                 "same records in the same run, both open with the same "
                 "three bytes.  Past the mark the ASCII file holds no byte "
                 "values above 0x7F while the Unicode one holds eighteen, "
                 "so the encoding flag reached the body and was ignored "
                 "only for the mark.",
        evidence_zh="同一次執行、由相同記錄產生的 `network_ascii.net` 與 "
                    "`network_UTF8.net`，開頭三個位元組完全相同。跳過該記號"
                    "之後，ASCII 檔中沒有任何大於 0x7F 的位元組，Unicode 檔"
                    "則有十八個——可見編碼選項有傳到內容產生的部分，只有這個"
                    "記號沒有跟著處理。",
        impact="A Pajek reader that takes the file as plain ASCII meets "
               "three unexpected bytes before `*Vertices`, which is either "
               "a parse error or a first line that reads as rubbish, "
               "depending on the tool.  The user asked for ASCII precisely "
               "to avoid that class of problem.",
        impact_zh="若某個 Pajek 讀取工具把這個檔案當成純 ASCII 處理，就會在 "
                  "`*Vertices` 之前先遇到三個意料之外的位元組；依工具不同，"
                  "結果可能是解析錯誤，也可能是第一行變成亂碼。使用者選擇 "
                  "ASCII，本來正是為了避開這一類問題。",
        fix="Write the mark only on the Unicode path, as the same file's "
            "Neo4j writers already do -- they omit it deliberately, because "
            "`LOAD CSV` reads it as part of the first column's name.  The "
            "condition is already available at that point in "
            "`handleExportPajek`.",
        fix_zh="只在 Unicode 的路徑上寫入該記號，就像同一個檔案裡的 Neo4j "
               "匯出已經在做的那樣——它們是刻意略過的，因為 `LOAD CSV` 會把"
               "這個記號當成第一個欄位名稱的一部分。`handleExportPajek` 在"
               "那個位置本來就拿得到判斷所需的條件。",
        steps=(
            "Run a Networks query.",
            "Export to Pajek with the ASCII (pinyin) option.",
            "Open the resulting .net file in a hex viewer: it begins EF BB "
            "BF, then `*Vertices`.",
        ),
        steps_zh=(
            "執行一次網絡查詢。",
            "選擇 ASCII（拼音）選項匯出 Pajek 檔。",
            "用十六進位檢視器打開產生的 .net 檔：開頭是 EF BB BF，"
            "接著才是 `*Vertices`。",
        ),
        source=("Code/networks_form_backend.go:2413",),
        tests=("test_an_export_named_ascii_contains_ascii",),
    ),
    Defect(
        key="CBDB-D-005",
        priority="P5", severity="medium", origin="software",
        title="Three forms accept an unfiltered query and give no way to "
              "ask for one -- and two of them offer the button for it",
        title_zh="三個表單接受不設條件的查詢，卻沒有任何途徑可以送出——"
                 "其中兩個還特地提供了那顆按鈕",
        area="Office, Associations and Status pages",
        area_zh="官職、人際關係、身份三個頁面",
        summary="Each of these three handlers adds its primary code filter "
                "only when the list is non-empty -- `if "
                "len(p.OfficeCodes) > 0` -- so an empty list means *every "
                "code*, and the Office page's own variable says so: "
                "`let _officeCodes = [];   // [] = all offices`.  Each page "
                "then greys out Run Query whenever that list is empty, "
                "which is exactly the state the handler reads as 'no "
                "filter'.  On Office and Associations the button that puts "
                "the form into that state -- *All Offices*, and *All* -- "
                "calls a clear function that empties the list and re-greys "
                "Run Query.  Pressing the control for 'everything' disables "
                "the control for 'go'.",
        summary_zh="這三個後端都只有在代碼清單非空時才加上主要篩選條件——"
                   "例如 `if len(p.OfficeCodes) > 0`——因此空清單的意思就是"
                   "「全部代碼」，官職頁面自己的變數也這樣註明："
                   "`let _officeCodes = [];   // [] = all offices`。然而"
                   "每一頁只要那份清單是空的，就會把執行查詢按鈕變成停用，"
                   "而那正是後端理解為「不設篩選」的狀態。官職與人際關係兩頁"
                   "更進一步：讓表單進入該狀態的按鈕（*All Offices* 與 "
                   "*All*）會呼叫清空函式，把清單清空後再次停用執行查詢。"
                   "按下「全部」那顆鈕，等於關掉「執行」那顆鈕。",
        evidence="Swept over the build rather than observed on one form, "
                 "and the chain is followed all three steps: the quantity "
                 "each page's Run Query gate tests, the request field the "
                 "page builds from it, and the Go field that field decodes "
                 "into.  Three forms meet on all three -- associations "
                 "(`assocCodes`), office (`_officeCodes` sent as "
                 "`officeCodes`), status (`selectedStatusCodes` sent as "
                 "`statusCodes`).  The Office case is confirmed end to end "
                 "in a browser: pick an office and Run Query is enabled; "
                 "press *All Offices* and it is disabled again, while the "
                 "same request sent over HTTP with `officeCodes: []` "
                 "answers 200.",
        evidence_zh="這是對整個版本的普查，而非單一表單的觀察，而且完整追"
                    "了三個環節：每個頁面執行查詢按鈕所檢查的那份清單、頁面"
                    "用它組出的請求欄位，以及該欄位對應的 Go 欄位。三個表單"
                    "在三個環節上都吻合——人際關係（`assocCodes`）、官職"
                    "（`_officeCodes`，送出時為 `officeCodes`）、身份"
                    "（`selectedStatusCodes`，送出時為 `statusCodes`）。"
                    "官職這一例已在瀏覽器中完整重現：選定一個官職後執行查詢"
                    "可用；按下 *All Offices* 後又變成停用，而同樣內容的請求"
                    "（`officeCodes: []`）直接以 HTTP 送出則回 200。",
        impact="Three of the six main forms cannot be asked for their "
               "unfiltered result.  A researcher who wants every office "
               "posting in a place, or every association of a person, or "
               "every status in a dynasty, has no way to say so through the "
               "page -- and on two of them the button that appears to offer "
               "it makes the form less usable rather than more.  The work "
               "behind that query is written, tested and reachable over "
               "HTTP; only the interface refuses.",
        impact_zh="六個主要表單中有三個無法被要求給出不設條件的結果。研究者"
                  "若想查某地的全部官職任命、某人的全部人際關係，或某朝代的"
                  "全部身份，透過頁面都無從表達；而在其中兩頁，那顆看起來正"
                  "是為此而設的按鈕，反而讓表單更不可用。支撐這項查詢的程式"
                  "碼都已寫好、可運作，直接以 HTTP 也叫得到，卡住的只有介面。",
        fix="Decide per form what an empty selection means and make the "
            "page agree with the handler.  If the unfiltered query is "
            "intended -- and the Office page's own comment says it is -- "
            "then Run Query should not be gated on the list being "
            "non-empty, and the *All* buttons should leave it enabled.  If "
            "it is not intended, the handlers should refuse an empty list "
            "with a message, the way the Places form refuses an empty "
            "category selection, rather than accepting a request no user "
            "can send.",
        fix_zh="請就每個表單決定「空選擇」的意義，並讓頁面與後端一致。若原本"
               "就允許不設條件的查詢——官職頁面自己的註解正是這樣寫的——那麼"
               "執行查詢就不該以清單非空作為啟用條件，「全部」類按鈕按下後"
               "也應維持可用。若原本不允許，則後端應該像地點表單拒絕空類別"
               "選擇那樣，明確回一個錯誤訊息，而不是接受一個沒有使用者送得"
               "出來的請求。",
        steps=(
            "Open the Office form (/LookAtOffice).",
            "Press Select Office and choose any office; Run Query becomes "
            "available.",
            "Press All Offices.",
            "Run Query is greyed out again, and there is no way to run the "
            "query the button just asked for.",
            "On the Associations form the same sequence with Select "
            "Associations and the All button does the same thing.",
        ),
        steps_zh=(
            "打開官職表單（/LookAtOffice）。",
            "按下選擇官職並任選一個官職，此時執行查詢變為可用。",
            "按下 All Offices。",
            "執行查詢又變回停用，而剛才那顆按鈕所要求的查詢已無從執行。",
            "在人際關係表單上，用選擇關係與 All 按鈕重複同樣步驟，結果相同。",
        ),
        source=("Templates/office/index.html:343",
                "Templates/office/index.html:357",
                "Code/office_form_backend.go:659",
                "Templates/associations/index.html:304",
                "Templates/status/index.html:473",
                "Code/associations_form_backend.go:534",
                "Code/status_form_backend.go:496"),
        tests=("test_a_form_that_accepts_an_unfiltered_query_has_a_way_to_ask_for_one",
               "test_all_offices_leaves_the_office_form_able_to_query"),
    ),
    Defect(
        key="CBDB-D-006",
        priority="P5", severity="low", origin="software",
        title="Two lookup endpoints were orphaned by the picker rework: "
              "implemented, routed, and called by no page",
        title_zh="選擇視窗改版後，有兩個查詢端點成了孤兒：程式還在、路由還在，"
                 "卻沒有任何頁面會呼叫",
        area="/api/entry-code-type-rel and /api/status-code-type-rel",
        area_zh="入仕代碼類型對照與身份代碼類型對照兩個查詢端點",
        summary="The entry and status pickers each had their search "
                "reworked in this build -- it now filters the codes already "
                "loaded rather than stepping through matches, and the "
                "*Next* button is gone.  Both pickers stopped fetching the "
                "code-to-type relation they had been loading alongside the "
                "type tree.  The two endpoints, their handlers and their "
                "SQL are all still in the build; nothing calls them.",
        summary_zh="這一版把入仕與身份兩個選擇視窗的搜尋功能都改寫了——現在"
                   "是對已載入的代碼做篩選，而不是逐筆跳到下一個符合項，"
                   "*Next* 按鈕也一併移除。兩個選擇視窗都不再抓取原本會連同"
                   "類型樹一起載入的「代碼—類型對照」資料。這兩個端點、它們"
                   "的處理程序與 SQL 都還在版本裡，只是沒有任何東西會呼叫。",
        evidence="Surveyed rather than noticed: every `/api/` route the "
                 "build registers, against every shipped page including the "
                 "pickers.  116 routes, two of them called by nothing.  "
                 "Both still answer when requested directly, so this is "
                 "work that runs and cannot be reached rather than work "
                 "that is broken.  The same survey found and reported two "
                 "Networks autocomplete helpers in the same state two builds "
                 "earlier; those were removed, which is one of the two "
                 "reasonable answers here.",
        evidence_zh="這是普查出來的，不是碰巧看到的：把版本註冊的每一條 "
                    "`/api/` 路由，對照每一個釋出的頁面（含各選擇視窗）。"
                    "共 116 條路由，其中兩條沒有任何東西呼叫。兩者若直接請求"
                    "都仍會正常回應，所以這是「能跑但到不了」的程式，而不是"
                    "壞掉的程式。同一項普查在兩版之前找出並回報過兩個處於相同"
                    "狀態的網絡自動完成端點；那兩個後來被刪除了，而刪除正是"
                    "這裡兩種合理處理方式之一。",
        impact="No user-visible consequence today: the pickers work, and "
               "what they stopped fetching they no longer need.  It is "
               "reported because dead-but-live code is a maintenance cost "
               "that grows quietly -- the handler, its SQL and its route "
               "will be read, updated and tested by somebody who does not "
               "know nothing calls them.",
        impact_zh="目前沒有使用者看得到的影響：選擇視窗運作正常，而不再抓取"
                  "的那份資料它們也確實不再需要。之所以回報，是因為「還活著"
                  "的死程式」會悄悄累積維護成本——日後總會有人去讀、去改、去"
                  "測這些處理程序、SQL 與路由，卻不知道根本沒有東西會呼叫"
                  "它們。",
        fix="Either delete the two handlers and their routes, as was done "
            "with the Networks search helpers, or wire them back to "
            "whatever still needs the relation.  Worth checking first "
            "whether the reworked search lost a capability along with the "
            "fetch: the old picker used the relation to search across "
            "types, and the new one filters within the loaded node.",
        fix_zh="兩種做法：一是像處理網絡搜尋端點那樣，把這兩個處理程序與其"
               "路由一併刪除；二是把它們重新接回仍然需要這份對照資料的地方。"
               "動手之前建議先確認：改寫後的搜尋是否連同那次抓取一起失去了"
               "某項能力——舊的選擇視窗是用這份對照跨類型搜尋的，新的則只在"
               "已載入的節點內篩選。",
        steps=(
            "Search the shipped Templates directory for "
            "'entry-code-type-rel' or 'status-code-type-rel': no page "
            "mentions either.",
            "Request either endpoint directly: it answers 200 with its "
            "rows.",
        ),
        steps_zh=(
            "在釋出的 Templates 目錄中搜尋 'entry-code-type-rel' 或 "
            "'status-code-type-rel'：沒有任何頁面提到它們。",
            "直接請求其中任一端點：仍會回 200 並送出資料。",
        ),
        source=("Code/entry_form_backend.go:182",
                "Code/status_form_backend.go:170",
                "Templates/pickers/entry_picker.html",
                "Templates/pickers/status_picker.html"),
        tests=("test_every_api_endpoint_the_build_routes_has_a_page_that_calls_it",),
    ),
    Defect(
        key="CBDB-D-007",
        priority="P3", severity="low", origin="software",
        title="A uniqueness the Kinship code declares is missing from the "
              "shipped table",
        title_zh="親屬功能的程式碼宣告了唯一性條件，釋出的資料表卻沒有它",
        area="The Kinship result scratch table ZZ_SP_KINSHIP, built by the "
             "database setup script",
        area_zh="親屬功能的結果暫存表 ZZ_SP_KINSHIP，由資料庫建置指令檔建立",
        summary="The Kinship backend declares `ZZ_SP_KINSHIP` with "
                "`UNIQUE(c_person_id)` and inserts into it with `INSERT OR "
                "IGNORE`.  The table that actually ships is created by the "
                "database builder without that constraint, and `CREATE "
                "TABLE IF NOT EXISTS` makes the Go declaration a no-op, so "
                "the `OR IGNORE` ignores nothing.",
        summary_zh="親屬後端宣告 `ZZ_SP_KINSHIP` 時帶有 "
                   "`UNIQUE(c_person_id)`，並以 `INSERT OR IGNORE` 寫入。"
                   "實際釋出的資料表是由資料庫建置程式建立的，沒有這個條件；"
                   "而 `CREATE TABLE IF NOT EXISTS` 讓 Go 那段宣告形同虛設，"
                   "於是 `OR IGNORE` 實際上什麼也沒有忽略。",
        evidence="Compared the `UNIQUE(...)` declarations in the shipped Go "
                 "against `sqlite_master` and `PRAGMA index_list` for each "
                 "table.  Five constraints are declared; four are enforced "
                 "by the shipped database and this one is not.  "
                 "`ZZ_SIP_NETWORK` was in the same state two builds ago and "
                 "has since been repaired in the same file, which is what "
                 "shows the omission is an oversight rather than a policy.\n\n"
                 "Origin is `software`, not `release`, and the deciding "
                 "experiment is what settles it: the constraint is missing "
                 "from the *builder's source*, so a clean rebuild from the "
                 "current CBDB data using this same code reproduces it "
                 "exactly.  Nothing about how the archive was assembled "
                 "would have prevented it, and the fix below is a source "
                 "edit.  The band still reads P3 because that describes the "
                 "symptom -- a released file lacking something it should "
                 "have -- while the origin says who fixes it.",
        evidence_zh="把釋出 Go 程式碼中的 `UNIQUE(...)` 宣告，逐表與 "
                    "`sqlite_master` 及 `PRAGMA index_list` 比對。共宣告了"
                    "五個條件，其中四個在釋出的資料庫裡確實存在，只有這一個"
                    "沒有。`ZZ_SIP_NETWORK` 在兩版之前也是同樣狀況，後來已"
                    "在同一個檔案中修好——由此可見這是疏漏而非刻意的設計。\n\n"
                    "來源歸類為 `software` 而非 `release`，判定的依據是那個"
                    "決定性的實驗：缺少的條件就在*建置程式的原始碼*裡，因此"
                    "用同一套程式碼、以現有的 CBDB 資料重新建置一次，這個"
                    "問題會原封不動再出現。發行檔怎麼打包都阻止不了它，而"
                    "底下的修法也是改原始碼。級別仍維持 P3，因為級別描述的"
                    "是症狀——釋出的檔案缺少了應該有的東西——而來源說的是"
                    "該由誰來修。",
        impact="No user-visible consequence was found: importing a "
               "duplicate inflates the Kinship person-count, which reads a "
               "different table, but the query deduplicates downstream and "
               "the exported people are correct.  It is recorded because "
               "the declaration is untrue, and the next query written "
               "against this table will inherit the assumption that it is "
               "true.",
        impact_zh="目前沒有發現使用者看得到的影響：匯入重複的人物會讓親屬"
                  "表單的人數統計偏高（該數字讀的是另一張表），但查詢在後續"
                  "步驟會去除重複，匯出的人物資料是正確的。之所以記錄下來，"
                  "是因為這個宣告與事實不符，而下一個針對這張表所寫的查詢，"
                  "會理所當然地以為它是真的。",
        fix="Add `UNIQUE(c_person_id)` to the `ZZ_SP_KINSHIP` definition in "
            "CBDB_AdditionalTablesViewsIndices.sql, exactly as "
            "`ZZ_SIP_NETWORK` received it.",
        fix_zh="在 CBDB_AdditionalTablesViewsIndices.sql 的 ZZ_SP_KINSHIP "
               "定義中加上 `UNIQUE(c_person_id)`，做法與 `ZZ_SIP_NETWORK` "
               "當時的修法完全相同。",
        steps=(
            "Open Data/cbdb.db and run: SELECT sql FROM sqlite_master WHERE "
            "name = 'ZZ_SP_KINSHIP';",
            "The definition has no UNIQUE clause.",
            "Compare with the CREATE TABLE in the Kinship backend, which "
            "declares one.",
        ),
        steps_zh=(
            "打開 Data/cbdb.db 執行：SELECT sql FROM sqlite_master "
            "WHERE name = 'ZZ_SP_KINSHIP';",
            "可以看到定義中沒有 UNIQUE 子句。",
            "再對照親屬後端的 CREATE TABLE，那裡是有宣告的。",
        ),
        source=("Code/kinship_form_backend.go:479",
                "CBDBSetUpCode/CBDB_AdditionalTablesViewsIndices.sql:895"),
        tests=("test_a_uniqueness_a_form_declares_is_one_the_table_enforces",),
    ),
)

#: What the report iterates.  Keyed by ``Defect.key`` (CBDB-D-0NN),
#: which is assigned while writing one report and means nothing outside
#: it -- that is why the waiver table is keyed by test names instead.
DEFECTS: dict[str, Defect] = {defect.key: defect for defect in _DEFECTS}

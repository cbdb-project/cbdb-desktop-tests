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
        priority="P0", severity="medium", origin="software",
        title="Opening someone's Kinship tab in the Browser replaces the "
              "Kinship form's result: its Export Query Results then "
              "exports the other person's network, and its Store Person "
              "IDs adds the other person to the stored list",
        title_zh="在人物瀏覽中開啟某人的「親屬關係」分頁，會取代親屬表單的"
                 "查詢結果：之後「匯出查詢結果」匯出的是另一個人的親屬網絡，"
                 "「儲存人物ID」也會把另一個人加進儲存清單",
        area="Person Browser (/CBDB_Browser) and Kinship form "
             "(/LookAtKinship)",
        area_zh="人物瀏覽（/CBDB_Browser）與親屬表單（/LookAtKinship）",
        summary="The Browser's Kinship tab calls "
                "`GET /api/browser/person/{id}/kinship`, and "
                "`handleGetKinship` begins by deleting `ZZ_KIN_LIST`, "
                "`ZZ_KIN_LIST_TMP`, `ZZ_SCRATCH_KIN` and "
                "`ZZ_SCRATCH_KINNET` before filling them with its own "
                "traversal.  Those are the tables the Kinship form's query "
                "left its answer in, and two of the Kinship form's buttons "
                "read them back rather than what the page is showing:\n\n"
                "- **Export Query Results** (`handleExportResults`) reads "
                "`ZZ_SCRATCH_KINNET` and `ZZ_SCRATCH_KIN`, so it exports "
                "the Browser person's network.  Only half of it changes: "
                "its third file, `KinshipPeople.tsv`, is read from "
                "`ZZ_SP_KINSHIP`, which the Browser does not touch, so the "
                "bundle describes two different people at once.\n"
                "- **Store Person IDs** (`doStorePersonIDsConfirmed`) "
                "stores the kin from `ZZ_SP_KINSHIP` and the ego from "
                "`ZZ_SCRATCH_KIN`, so the stored list -- the channel by "
                "which a result travels to every other form -- gains the "
                "Browser's person.\n\n"
                "Reached two ways from the Browser page: pressing its "
                "Kinship tab, and Export Profile, which loads every tab it "
                "has not cached -- Kinship included -- for a user who never "
                "opened it.  The Kinship page keeps showing its own result "
                "throughout, and nothing on either page says anything has "
                "changed.  The page's own comment on Export Query Results "
                "says the export \"always reflects exactly what the last "
                "query wrote to those tables\"; the Browser is a second "
                "writer that comment does not allow for.",
        summary_zh="人物瀏覽的「親屬關係」分頁會呼叫 "
                   "`GET /api/browser/person/{id}/kinship`，而 "
                   "`handleGetKinship` 一開始就刪除 `ZZ_KIN_LIST`、"
                   "`ZZ_KIN_LIST_TMP`、`ZZ_SCRATCH_KIN` 與 "
                   "`ZZ_SCRATCH_KINNET`，再寫入它自己的親屬走訪結果。"
                   "這四張暫存表正是親屬表單查詢留下答案的地方，而親屬表單"
                   "有兩個按鈕是從這些表讀回資料，而不是使用頁面上顯示的"
                   "內容：\n\n"
                   "- **匯出查詢結果**（`handleExportResults`）讀取 "
                   "`ZZ_SCRATCH_KINNET` 與 `ZZ_SCRATCH_KIN`，因此匯出的是"
                   "人物瀏覽中那個人的網絡。而且只換掉了一半：第三個檔案 "
                   "`KinshipPeople.tsv` 讀自 `ZZ_SP_KINSHIP`，人物瀏覽不會"
                   "動到這張表，所以壓縮檔同時描述了兩個不同的人。\n"
                   "- **儲存人物 ID**（`doStorePersonIDsConfirmed`）從 "
                   "`ZZ_SP_KINSHIP` 取親屬、從 `ZZ_SCRATCH_KIN` 取中心人物，"
                   "因此儲存清單——也就是查詢結果傳往其他所有表單的管道——"
                   "會多出人物瀏覽中的那個人。\n\n"
                   "從人物瀏覽頁面有兩條路會觸發：按下「親屬關係」分頁，以及"
                   "「匯出人物檔案」（Export Profile）——後者會載入所有尚未快取的分頁，包括"
                   "親屬關係，即使使用者從未打開過它。整個過程中親屬頁面仍"
                   "顯示原本的結果，兩個頁面都沒有任何訊息說明內容已改變。"
                   "頁面自己在「匯出查詢結果」旁的註解寫著，匯出「永遠正好"
                   "反映上一次查詢寫入這些表的內容」；人物瀏覽是這段註解沒有"
                   "考慮到的第二個寫入者。",
        evidence="Both halves driven through the running binary.  "
                 "`test_looking_a_person_up_does_not_discard_a_kinship_"
                 "result`: a Kinship query for person 1, then "
                 "`GET /api/browser/person/10/kinship`, then Export Query "
                 "Results -- HTTP 200, a `KinshipResults.zip` whose "
                 "`EgoRelativeKinship.tsv` went from 920 to 9,795 "
                 "characters and whose `KinshipNetwork.tsv` went from 1,067 "
                 "to 295, while `KinshipPeople.tsv` came back identical.  "
                 "Re-running the query for person 1 returns its 6 "
                 "kinRecords again, so the result was replaced, not "
                 "damaged.  `test_looking_a_person_up_does_not_change_what_"
                 "kinship_stores`: from the same result, Store Person IDs "
                 "stored 6 people before the lookup and 7 after -- person "
                 "10 added, nobody removed.\n\n"
                 "Read from the source: the four `DELETE`s at the top of "
                 "`handleGetKinship`; the two tables "
                 "`doStorePersonIDsConfirmed` reads; `loadTabKinship` on "
                 "the Browser page, which `EXPORT_TABS` lists as Export "
                 "Profile's Kinship loader "
                 "(`test_export_profile_loads_the_kinship_tab_it_lists`).  "
                 "The Kinship query's own clear step is commented \"add "
                 "ZZ_SP_KINSHIP vs browser\" -- the Kinship query clears "
                 "the tables the Browser also uses, plus the one it does "
                 "not, so the sharing of the other four was known.  The "
                 "five other "
                 "Kinship exports build their rows from the records the "
                 "page posts and are unaffected.",
        evidence_zh="兩個部分都透過實際執行的程式驗證。"
                    "`test_looking_a_person_up_does_not_discard_a_kinship_"
                    "result`：先對人物 1 執行親屬查詢，再呼叫 "
                    "`GET /api/browser/person/10/kinship`，然後按「匯出查詢"
                    "結果」——回應 HTTP 200，得到的 `KinshipResults.zip` 中 "
                    "`EgoRelativeKinship.tsv` 由 920 字元變為 9,795 字元，"
                    "`KinshipNetwork.tsv` 由 1,067 變為 295，而 "
                    "`KinshipPeople.tsv` 與原本相同。對人物 1 重新查詢仍回傳 "
                    "6 筆 kinRecords，可見結果是被取代，而不是損壞。"
                    "`test_looking_a_person_up_does_not_change_what_kinship_"
                    "stores`：同一份結果，查看前「儲存人物ID」存了 6 人，"
                    "查看後存了 7 人——多了人物 10，沒有人被移除。\n\n"
                    "從原始碼讀出的部分：`handleGetKinship` 開頭的四個 "
                    "`DELETE`；`doStorePersonIDsConfirmed` 讀取的兩張表；人物"
                    "瀏覽頁面上的 `loadTabKinship`，`EXPORT_TABS` 把它列為"
                    "「匯出人物檔案」（Export Profile）的親屬載入函式"
                    "（`test_export_profile_loads_the_kinship_tab_it_lists`）。"
                    "親屬查詢自己的清除步驟註解寫著「add ZZ_SP_KINSHIP vs "
                    "browser」——親屬查詢清除人物瀏覽也在用的那幾張表，再加上"
                    "它不用的這一張，可見開發者知道另外四張是與人物瀏覽共用的。親屬"
                    "表單的其他五種匯出是用頁面傳來的資料列產生，不受影響。",
        impact="A historian who looks somebody up in the Browser between "
               "running a Kinship query and acting on it gets, without any "
               "error or sign on either page, either an export about a "
               "different person's kin stitched to the first person's "
               "people list, or a stored list that carries one extra "
               "person into whatever form it is recalled into next.  "
               "Nothing about the sequence is unusual -- checking a "
               "relative in the Browser is what the Browser is for -- and "
               "both results look plausible, so they are likely to be "
               "used.  Medium rather than high because it takes that "
               "particular sequence, and the grid on screen stays correct.",
        impact_zh="研究者若在執行親屬查詢之後、使用結果之前，到人物瀏覽查看了"
                  "某個人，就會在沒有任何錯誤、兩個頁面也看不出跡象的情況下，"
                  "得到一份描述另一個人親屬、卻拼上第一個人人物清單的匯出檔，"
                  "或是一份多了一個人的儲存清單，並被帶進下一個調用它的表單。"
                  "這個操作順序一點也不特別——在人物瀏覽中查看某位親屬正是這個"
                  "頁面的用途——而兩種結果看起來都合理，因此很可能被直接拿去"
                  "使用。嚴重度列為中而非高，是因為必須恰好走過這個順序，而且"
                  "畫面上的表格本身仍是正確的。",
        fix="Give the Browser its own kinship scratch tables, as each form "
            "already has its own, or have `handleGetKinship` compute its "
            "traversal without writing to the Kinship form's.  That cures "
            "both buttons.  Changing Export Query Results to export the "
            "records its page holds, as the other five exports do, would "
            "cure the export and leave Store Person IDs as it is.",
        fix_zh="讓人物瀏覽擁有自己的親屬暫存表（每個表單本來就各有一套），"
               "或讓 `handleGetKinship` 在計算親屬走訪時不寫入親屬表單的"
               "暫存表。這樣兩個按鈕都會一併修好。若只把「匯出查詢結果」改為"
               "匯出頁面手上的資料列（另外五種匯出就是這樣做），能修好匯出，"
               "但「儲存人物ID」的問題仍然存在。",
        steps=(
            "Open Kinship, choose a person, and press Run Query.  Note "
            "the result.",
            "In another tab, open the Person Browser, look up a different "
            "person, and press the Kinship tab (or Export Profile).",
            "Return to the Kinship tab -- it still shows the first "
            "person's result -- and press Export Query Results.  Unzip "
            "KinshipResults.zip: KinshipNetwork.tsv and "
            "EgoRelativeKinship.tsv describe the second person; "
            "KinshipPeople.tsv still describes the first.",
            "Press Store Person IDs, then Recall on any other form: the "
            "second person is among the people recalled.",
        ),
        steps_zh=(
            "開啟親屬表單，選擇一位人物並按「執行查詢」，記下結果。",
            "在另一個分頁開啟人物瀏覽，查詢另一位人物，並按「親屬關係」"
            "分頁（或「匯出人物檔案」（Export Profile））。",
            "回到親屬表單——畫面仍顯示第一個人的結果——按「匯出查詢結果」。"
            "解壓縮 KinshipResults.zip：KinshipNetwork.tsv 與 "
            "EgoRelativeKinship.tsv 描述的是第二個人；KinshipPeople.tsv "
            "描述的仍是第一個人。",
            "按「儲存人物ID」，再到任何其他表單按「調取ID」：第二個人也在"
            "調用進來的人物之中。",
        ),
        source=(
            "Code/browser_form_backend.go:handleGetKinship (the four "
            "DELETEs at its top)",
            "Code/kinship_form_backend.go:handleExportResults (reads "
            "ZZ_SCRATCH_KINNET and ZZ_SCRATCH_KIN back, and ZZ_SP_KINSHIP)",
            "Code/kinship_form_backend.go:doStorePersonIDsConfirmed (kin "
            "from ZZ_SP_KINSHIP, ego from ZZ_SCRATCH_KIN)",
            "Templates/browser/index.html:1724 (loadTabKinship)",
            "Templates/browser/index.html:182 (EXPORT_TABS, which Export "
            "Profile walks)",
        ),
        tests=("test_looking_a_person_up_does_not_discard_a_kinship_result",
               "test_looking_a_person_up_does_not_change_what_kinship_stores"),
    ),
    Defect(
        key="CBDB-D-002",
        priority="P0", severity="medium", origin="software",
        title="The Places form's \"Export as ASCII (pinyin)\" checkbox is "
              "ignored by Save to GIS and Save to KML",
        title_zh="地點表單的「以ASCII（拼音）而非Unicode匯出」核取方塊，對「保存到GIS」"
                 "與「保存到KML」完全沒有作用",
        area="Places form (/LookAtPlace): /api/places/export-gis",
        area_zh="地點表單（/LookAtPlace）的「保存到GIS」與「保存到KML」兩種匯出",
        summary="The Places page sends the checkbox as `encoding: "
                "\"ascii\"` with each export beside it "
                "(`getExportEncoding`).  Of those three buttons, Export "
                "Neo4j CSVs honours it and the other two do not: "
                "`handleExportGIS` decodes `Encoding` and never reads it, "
                "and both of its writers put the Chinese fields in the "
                "file whatever was asked -- `writePlaceTab` writes every "
                "`*Chn` column beside its pinyin twin, and `writePlaceKML` "
                "writes `NameChn` into each placemark's description.  A "
                "user who ticks the "
                "box and presses Save to GIS or Save to KML gets the "
                "Unicode file, byte for byte, with nothing to say so.\n\n"
                "The same form's Gephi writer honours the choice in part: "
                "its edge labels switch to pinyin and its node labels stay "
                "`NameChn`.  No button reaches that export on this build "
                "(CBDB-D-003); it is recorded here too so that wiring one "
                "up does not ship the same fault.",
        summary_zh="地點表單在這個核取方塊旁的每一種匯出中，都會把它以 "
                   "`encoding: \"ascii\"` 傳給後端（`getExportEncoding`）。"
                   "這三個按鈕中，「導出Neo4j CSV」有遵照，另外兩個"
                   "沒有：`handleExportGIS` 解析了 `Encoding` 卻從未讀取，"
                   "兩個寫檔函式不論要求為何都會寫入中文欄位——"
                   "`writePlaceTab` 把每個 `*Chn` 欄位與其拼音欄位並列寫出，"
                   "`writePlaceKML` 則把 `NameChn` 寫進每個地標的說明。使用者"
                   "勾選後按「保存到GIS」或「保存到KML」，拿到的是與 "
                   "Unicode 版本逐位元組相同的檔案，而且沒有任何提示。\n\n"
                   "同一表單的 Gephi 匯出只遵照了一部分：邊的標籤改為拼音，"
                   "節點標籤仍是 `NameChn`。這個版本沒有任何按鈕能觸發該匯出"
                   "（見 CBDB-D-003）；一併記錄在這裡，免得日後接上按鈕時帶著"
                   "同樣的問題上線。",
        evidence="`test_an_export_asked_for_ascii_contains_only_ascii` "
                 "posts two records in which every Chinese field has an "
                 "ASCII pinyin twin, once with `encoding=unicode` and once "
                 "with `encoding=ascii`, and reads each file past any "
                 "leading byte-order mark.  With ascii: `places:gis` "
                 "delivered `places_export.tsv` with 72 bytes above 0x7F "
                 "and `places:kml` delivered `places_export.kml` with 18 "
                 "-- both byte-for-byte the unicode export.  "
                 "`places:gephi` delivered `network_ascii.gdf` with 42, "
                 "different from its unicode file.  `places:neo4j` and "
                 "`places:pajek` passed (pure ASCII past the mark); "
                 "`places:ucinet` writes no Chinese in either mode and "
                 "has nothing to judge.",
        evidence_zh="`test_an_export_asked_for_ascii_contains_only_ascii` 送出"
                    "兩筆每個中文欄位都有 ASCII 拼音對應的資料，分別以 "
                    "`encoding=unicode` 與 `encoding=ascii` 各送一次，並略過"
                    "檔首的位元組順序標記後讀取檔案。以 ascii 送出時："
                    "`places:gis` 得到的 `places_export.tsv` 有 72 個大於 "
                    "0x7F 的位元組，`places:kml` 得到的 `places_export.kml` "
                    "有 18 個——兩者都與 unicode 版本逐位元組相同。"
                    "`places:gephi` 得到的 `network_ascii.gdf` 有 42 個，"
                    "與它的 unicode 檔案不同。`places:neo4j` 與 "
                    "`places:pajek` 通過（標記之後全為 ASCII）；"
                    "`places:ucinet` 兩種模式都不寫入中文，無從判斷。",
        impact="The checkbox is there for a user whose GIS or mapping tool "
               "cannot read Chinese, and those are exactly the files it "
               "does nothing to.  They get Unicode names they asked not "
               "to get, in a file that looks like the one they asked for, "
               "and the only sign is the tool that then shows them "
               "garbage.  Medium: the files are not wrong for anyone who "
               "did not tick the box, and Neo4j does honour it.",
        impact_zh="這個核取方塊是為了 GIS 或地圖工具無法讀取中文的使用者而設，"
                  "而它恰恰對這兩種檔案不起作用。使用者明明要求不要中文，拿到"
                  "的卻是 Unicode 名稱，檔案看起來又像是他們要的那一份，唯一的"
                  "跡象是之後工具顯示出一堆亂碼。嚴重度列為中：對沒有勾選的人"
                  "而言檔案並沒有錯，而且 Neo4j 匯出確實有遵照。",
        fix="In `handleExportGIS`, read `Encoding` and pass it to both "
            "writers, which in ascii mode should leave the Chinese out, as "
            "`buildPlaceNeo4jFiles` already does: `writePlaceTab` by "
            "omitting or blanking its `*Chn` columns, `writePlaceKML` by "
            "leaving `NameChn` out of the description.  In "
            "`handleExportGephi`, use `n.NamePY` as the node label in "
            "ascii mode, as its edge labels already do.",
        fix_zh="在 `handleExportGIS` 中讀取 `Encoding` 並傳給兩個寫檔函式，"
               "ascii 模式下不寫入中文，就像 `buildPlaceNeo4jFiles` 已經做的"
               "那樣：`writePlaceTab` 省略或清空各個 `*Chn` 欄位，"
               "`writePlaceKML` 不把 `NameChn` 寫進說明。在 "
               "`handleExportGephi` 中，ascii 模式下以 `n.NamePY` 作為節點"
               "標籤，與它的邊標籤一致。",
        steps=(
            "Open Places and run any query that returns rows with "
            "Chinese names.",
            "Tick \"Export as ASCII (pinyin) instead of Unicode\".",
            "Press Save to KML, and separately Save to GIS.",
            "Open either file: it carries the Chinese -- the KML in each "
            "placemark's description, the GIS file in its *Chn columns -- "
            "and is identical to the one saved with the box unticked.",
        ),
        steps_zh=(
            "開啟地點表單，執行任何會回傳中文名稱的查詢。",
            "勾選「以ASCII（拼音）而非Unicode匯出」。",
            "按「保存到KML」，再另外按「保存到GIS」。",
            "打開任一檔案：中文仍在其中——KML 在每個地標的說明裡，GIS "
            "檔在各個 *Chn 欄位——而且與沒有勾選時存下的檔案完全相同。",
        ),
        source=(
            "Code/places_form_backend.go:handleExportGIS (decodes Encoding, "
            "never reads it)",
            "Code/places_form_backend.go:writePlaceTab (every *Chn column "
            "beside its pinyin twin)",
            "Code/places_form_backend.go:writePlaceKML (NameChn in the "
            "placemark description)",
            "Code/places_form_backend.go:handleExportGephi (NameChn as the "
            "node label in both modes)",
            "Templates/places/index.html:727 (getExportEncoding)",
        ),
        tests=("test_an_export_asked_for_ascii_contains_only_ascii",),
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
                "`exportUCINet`, each posting the query result and the "
                "ASCII choice to its endpoint and downloading the answer, "
                "and the three handlers are routed and answer.  Nothing "
                "on the page invokes any of the three functions: its "
                "buttons are Run Query, Store Person IDs, Export Query "
                "Results, Save to KML, Save to GIS and Export Neo4j CSVs, "
                "and no listener or load-time code calls them either.  "
                "So three network exports -- the formats the other network "
                "forms offer -- exist on both sides and no user can reach "
                "them.  Whether their output is right is a separate "
                "question: the Gephi one keeps Chinese node labels in "
                "ASCII mode (CBDB-D-002).",
        summary_zh="地點表單頁面定義了 `exportPajek`、`exportGephi` 與 "
                   "`exportUCINet`，各自把查詢結果與 ASCII 選項送到對應的"
                   "端點並下載回應，三個後端處理函式也都有路由、能夠回應。"
                   "但頁面上沒有任何東西會呼叫這三個函式：它的按鈕只有執行"
                   "查詢、儲存人物ID、導出查詢結果、保存到KML、保存到GIS "
                   "與導出Neo4j CSV，也沒有任何事件監聽或載入時執行的程式碼"
                   "呼叫它們。因此這三種網絡匯出——其他網絡類表單都有提供的"
                   "格式——前後端都已存在，卻沒有使用者到得了。至於輸出是否"
                   "正確是另一個問題：Gephi 匯出在 ASCII 模式下仍保留中文節點"
                   "標籤（見 CBDB-D-002）。",
        evidence="`test_every_endpoint_a_page_calls_is_reachable_from_"
                 "something_a_user_does` walks each page's call graph from "
                 "everything that can run -- buttons, every inline "
                 "`on...=` handler, load-time code, listeners registered "
                 "by name, and the `window.X` callbacks popups call back "
                 "into.  Across every page the build ships, these three "
                 "are the only endpoints a page mentions that the walk "
                 "never reaches.  The textual survey "
                 "(`test_every_api_endpoint_the_build_routes_has_a_page_"
                 "that_calls_it`) counts them as called, because the "
                 "fetches are there, inside functions nothing runs.",
        evidence_zh="`test_every_endpoint_a_page_calls_is_reachable_from_"
                    "something_a_user_does` 從每個頁面上所有可能執行的地方"
                    "出發——按鈕、每個行內 `on...=` 處理函式、載入時執行的"
                    "程式碼、以名稱註冊的事件監聽，以及彈出視窗回呼的 "
                    "`window.X`——沿著頁面的呼叫關係走訪。在這個版本的所有"
                    "頁面中，只有這三個端點是頁面提到、卻走訪不到的。純文字"
                    "的普查（`test_every_api_endpoint_the_build_routes_has_a_"
                    "page_that_calls_it`）把它們算作「有呼叫」，因為 fetch "
                    "確實寫在頁面裡，只是位於沒有任何東西會執行的函式中。",
        impact="A historian working in Places cannot produce the Pajek, "
               "Gephi or UCINet files the other network forms offer, and "
               "there is nothing on the page to say the feature exists.  "
               "No wrong answer is given; the feature is simply "
               "unreachable.",
        impact_zh="在地點表單中工作的研究者，無法產生其他網絡類表單都能產生的 "
                  "Pajek、Gephi 或 UCINet 檔案，頁面上也沒有任何跡象顯示這項"
                  "功能存在。這不會給出錯誤的結果，只是功能到不了。",
        fix="Add the three buttons the functions were written for, as the "
            "Kinship and Networks pages have, or delete the functions and "
            "handlers if the Places form is not meant to offer these "
            "formats.  Fix the Gephi ASCII labels (CBDB-D-002) before "
            "wiring it up.",
        fix_zh="補上這三個函式原本要搭配的按鈕（親屬與網絡頁面都有），或者若"
               "地點表單本來就不打算提供這些格式，就刪除這些函式與後端處理"
               "函式。接上 Gephi 之前，請先修正它的 ASCII 標籤問題"
               "（CBDB-D-002）。",
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
            "Templates/places/index.html:825 (exportUCINet, called by "
            "nothing)",
            "Templates/places/index.html:842 (exportPajek, called by "
            "nothing)",
            "Templates/places/index.html:859 (exportGephi, called by "
            "nothing)",
            "Templates/places/index.html:92 (the page's action buttons)",
        ),
        tests=("test_every_endpoint_a_page_calls_is_reachable_from_"
               "something_a_user_does",),
    ),
)

#: What the report iterates.  Keyed by ``Defect.key`` (CBDB-D-0NN),
#: which is assigned while writing one report and means nothing outside
#: it -- that is why the waiver table is keyed by test names instead.
DEFECTS: dict[str, Defect] = {defect.key: defect for defect in _DEFECTS}

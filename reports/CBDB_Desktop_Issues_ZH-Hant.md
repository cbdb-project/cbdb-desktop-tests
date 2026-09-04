# CBDB-Desktop —— 問題彙報

_自動化迴歸測試過程中發現的問題彙總，謹呈維護團隊斧正。_

_受測版本：cbdb-desktop_20260901.zip_

_本報告產生於 2026-09-04 11:57 UTC，依據一次 234 項測試的執行結果（耗時 65 秒）。_

尊敬的維護者：

以下是我們在為 CBDB-Desktop 編寫自動化迴歸測試套件的過程中，陸續整理出來的問題清單。我們希望這份報告能在您繼續主持這份寶貴資料集時有所助益；同時，對您多年來在這套資料與程式上的辛勤付出，我們由衷表示感謝與敬意。

以下每一項問題，都是實際啟動釋出的 `Bin/cbdb.exe`、以它自己的 HTTP 介面搭配釋出的資料庫實測出來的——我們沒有用 Python 重寫任何應用邏輯，因此這裡描述的就是釋出程式的真實行為。問題按嚴重程度排序（P0 最高），每一條都包含：簡要說明、據以認定的實測數據、逐步復現方式，以及一份建議的修復方案。這些問題都不緊急，整理於此只是方便您在合適的時候逐一處理。

## 本次執行結果

| 結果 | 數量 |
| --- | --- |
| 通過 | 193 |
| 預期失敗（已知缺陷，仍然存在） | 41 |

## 測試套件的涵蓋範圍

| 範圍 | 測試數 | 檢查內容 |
| --- | --- | --- |
| 發行檔本身 | 49 | 受測的檔案樹確實逐一符合釋出的壓縮檔 |
| 應用程式行程 | 13 | 釋出的執行檔能啟動、能服務、並能釋放資料庫 |
| 所有已註冊的路由 | 17 | 從釋出的 Go 原始碼讀出的全部 141 條路由，逐一實測 |
| 代碼與地址清單 | 34 | 各表單在查詢前提供的下拉選單 |
| 查詢建構器 | 50 | 白名單、顯示給使用者的 SQL，以及各項防護 |
| 六個唯讀表單 | 49 | 入仕、官職、社會地位、著述、社會關係、地點——查詢與匯出 |
| 具狀態的表單 | 13 | 親屬關係、社會網路、關係配對、群組資料——工作清單 |
| 索引地址排序 | 9 | 唯一會改寫 CBDB 正式資料（而非暫存表）的端點 |

## 問題總覽

| 編號 | 等級 | 本次執行狀態 | 問題 |
| --- | --- | --- | --- |
| CBDB-D-001 | P0 | 已確認 | 人物搜尋：輸入三個字元以上就完全找不到人 |
| CBDB-D-004 | P0 | 已確認 | 其他表單的查詢會靜默清空「社會關係」的匯出結果 |
| CBDB-D-006 | P1 | 已確認 | 格式不正確的排序設定會被接受，並套用到每一位人物身上 |
| CBDB-D-002 | P2 | 已確認 | 查詢建構器提供了 30 個並不存在的欄位 |
| CBDB-D-005 | P3 | 已確認 | 釋出檔中殘留了前一次使用的工作狀態 |
| CBDB-D-003 | P4 | 已確認 | 姓名索引中有一位資料庫裡並不存在的人物 |

## 目錄

- [CBDB-D-001 — 人物搜尋：輸入三個字元以上就完全找不到人](#cbdb-d-001--人物搜尋：輸入三個字元以上就完全找不到人)
- [CBDB-D-004 — 其他表單的查詢會靜默清空「社會關係」的匯出結果](#cbdb-d-004--其他表單的查詢會靜默清空「社會關係」的匯出結果)
- [CBDB-D-006 — 格式不正確的排序設定會被接受，並套用到每一位人物身上](#cbdb-d-006--格式不正確的排序設定會被接受，並套用到每一位人物身上)
- [CBDB-D-002 — 查詢建構器提供了 30 個並不存在的欄位](#cbdb-d-002--查詢建構器提供了-30-個並不存在的欄位)
- [CBDB-D-005 — 釋出檔中殘留了前一次使用的工作狀態](#cbdb-d-005--釋出檔中殘留了前一次使用的工作狀態)
- [CBDB-D-003 — 姓名索引中有一位資料庫裡並不存在的人物](#cbdb-d-003--姓名索引中有一位資料庫裡並不存在的人物)
- [嚴重等級說明](#嚴重等級說明)
- [如何重現這份報告](#如何重現這份報告)

## CBDB-D-001 — 人物搜尋：輸入三個字元以上就完全找不到人

**涉及範圍：** 人物瀏覽（/CBDB_Browser）

**嚴重等級：** P0 — 靜默的錯誤結果——程式回傳錯誤或空白的結果，而且沒有任何錯誤提示。

**本次執行狀態：** 已確認

#### 問題描述

Data/CBDB.db 裡的 ZZZ_NAMES_FTS 是建立在 ZZZ_NAMES 之上的 FTS5 trigram 外部內容索引。索引表和同步觸發器都建好了，卻從未灌入內容。SQLite 在 LIKE 樣式達到三個字元時會改走這個索引，未達三個字元則回頭掃描內容表；因此短字串搜尋正常，而任何實際會用到的搜尋都靜默地回傳空結果。

#### 實測依據

ZZZ_NAMES 共 866,011 筆姓名；ZZZ_NAMES_FTS_idx 與 ZZZ_NAMES_FTS_docsize 皆為空，ZZZ_NAMES_FTS_data 只有 2 列。透過釋出的執行檔實測：搜尋「wa」回傳 56,504 筆（正確）；「Wang」回傳 0 筆，實際應有 50,493 筆；「Wang Anshi」回傳 0 筆，應有 5 筆；「王安石」回傳 0 筆，應有 2 筆；而兩個字的「王安」則正確回傳 146 筆。在複本上重建索引約需 4 秒，之後上述每一項搜尋都回傳與資料相符的筆數。

#### 影響

使用者尋找人物最主要的途徑，在幾乎所有實際查詢下都失效。輸入完整姓氏、完整姓名，或三個漢字的中文名，都只會得到一份空清單——這在畫面上與「CBDB 裡沒有這個人」完全無法區分。全部 658,941 位人物都受影響；底層資料本身並未損壞。

#### 復現步驟

1. 啟動 CBDB-Desktop，開啟人物瀏覽頁面（/CBDB_Browser）。
2. 在搜尋框輸入 `Wang`，結果清單為空。
3. 改輸入 `wa`，卻找到 56,504 人——資料其實都在，差別只在字元數。
4. 中文也一樣：`王安` 找到 146 人，`王安石` 一人也找不到。
5. 在資料庫層確認：`SELECT COUNT(*) FROM ZZZ_NAMES_FTS_docsize` 回傳 0，而 `SELECT COUNT(*) FROM ZZZ_NAMES` 回傳 866,011。

#### 建議修復方式

對釋出用的資料庫執行 INSERT INTO ZZZ_NAMES_FTS(ZZZ_NAMES_FTS) VALUES('rebuild')。CBDBSetUpCode/zzznames_backend.go 的 RunZZZNames 其實已經包含這一步，只是沒有對釋出檔執行過。建議同時在建置流程加一道檢查：ZZZ_NAMES_FTS_docsize 與 ZZZ_NAMES 的筆數必須相等。

#### 對應的程式位置

- `Code/browser_form_backend.go:812`
- `CBDBSetUpCode/zzznames_backend.go:114`
- `Data/CBDB.db.schema.sql:1035`

#### 對應的測試

- 5 × 預期失敗（已知缺陷，仍然存在）: `test_searching_people_by_name_finds_them[Wang-50000]`, `test_searching_people_by_name_finds_them[Wang Anshi-1]`, `test_searching_people_by_name_finds_them[Su Shi-1]`, `test_searching_people_by_name_finds_them[\u738b\u5b89\u77f3-1]` (+1)

## CBDB-D-004 — 其他表單的查詢會靜默清空「社會關係」的匯出結果

**涉及範圍：** 社會關係表單（/LookAtAssociations）

**嚴重等級：** P0 — 靜默的錯誤結果——程式回傳錯誤或空白的結果，而且沒有任何錯誤提示。

**本次執行狀態：** 已確認

#### 問題描述

「社會關係」的匯出不接受任何請求內容，也不加鎖：它直接重讀 ZZ_SOCIAL_NETWORK 與 ZZ_SCRATCH_PEOPLE 這兩張由自己的查詢填入的暫存表。而「關係配對」與「社會網路」在各自查詢一開始就會清空 ZZ_SOCIAL_NETWORK；因此只要在按下「查詢」與按下「匯出」之間去過其中任一表單，匯出得到的就是一個空檔案。「親屬關係」只清空 ZZ_SCRATCH_PEOPLE，因此影響的是第二個匯出檔而非第一個。

#### 實測依據

透過釋出的執行檔實測：一次「社會關係」查詢得到 55 列，匯出也是 55 列。接著只要送出一次 POST /api/assocpairs/query，同一個匯出就只剩 0 列——HTTP 狀態 200、status 為 'ok'、檔案裡除了標題列什麼都沒有。整個過程沒有任何錯誤訊息。

#### 影響

使用者的查詢結果就這樣不見了，而且完全沒有任何提示。匯出按鈕照常可按、檔案照常下載，只是裡面是空的。要走到這一步也不需要什麼特別操作：跑一次查詢、去看一下相關的表單、回來按匯出，就會發生。

#### 復現步驟

1. 開啟「社會關係」表單，選一個關係類別，按下「查詢」。表格出現結果（我們的實測是 55 列）。
2. 不要關閉任何視窗，開啟「關係配對」表單，在那裡執行任何一次查詢。
3. 回到「社會關係」表單，按下「匯出結果」。
4. 下載到的檔案只有標題列。整個過程沒有出現任何錯誤訊息。

#### 建議修復方式

讓匯出改為輸出呼叫端傳入的結果——「官職」「社會地位」「著述」「地點」四個表單的匯出本來就是這樣做的；或者把暫存表改為以工作階段（session）區分，並讓 associationsMu 涵蓋「查詢＋匯出」這一對操作。

#### 對應的程式位置

- `Code/associations_form_backend.go:932 (the export reads ZZ_SOCIAL_NETWORK, taking no lock)`
- `Code/assocpairs_form_backend.go:417 (clears it)`
- `Code/networks_form_backend.go:1190 (clears it)`
- `Code/kinship_form_backend.go:750 (clears ZZ_SCRATCH_PEOPLE, so the people file empties instead)`

#### 對應的測試

- 1 × 預期失敗（已知缺陷，仍然存在）: `test_another_form_does_not_empty_the_associations_export`

## CBDB-D-006 — 格式不正確的排序設定會被接受，並套用到每一位人物身上

**涉及範圍：** 索引地址排序（/IndexAddr）

**嚴重等級：** P1 — 破壞性寫入——一次請求改寫了本不該改寫的既存資料，原本的狀態無法復原。

**本次執行狀態：** 已確認

#### 問題描述

POST /api/indexaddr/update 把請求內容宣告為九個欄位的陣列，卻完全沒有檢查長度。Go 的 JSON 解碼器會把過短的陣列補零、把過長的陣列截斷，兩者都不報錯；因此欄位數不對的請求會被照單全收並實際套用——而這正是整個程式裡唯一會改寫 CBDB 正式資料（而非暫存表）的端點。

#### 實測依據

在獨立複本上對釋出的執行檔實測：送出只有八個元素的 ranks 陣列，回應為 200「Rankings updated and BIOG_MAIN rebuilt successfully」，並把地址類型 0（unknown）放進第 9 順位；擁有索引地址的人數也從 383,322 變成 379,051。送出十一個元素同樣被接受，最後兩個類型被靜默丟棄。至於那些會被拒絕的請求，其實都不是因為長度：字串在 JSON 解碼階段就失敗；兩個元素的陣列與完全沒有該欄位的請求，是補零之後多出好幾個地址類型 0，才被「重複類型」檢查攔下來。八個元素只會補出一個 0，因此沒有任何檢查攔得住。

#### 影響

只要送出的欄位數不對——版本較舊或較新的頁面、自行撰寫的腳本、填了一半的表單——就會靜默地重設資料庫中每一位人物的索引地址，並把「unknown」當成一個正式的地址類型排進順位。過程中沒有任何提示，而原本的排序也就此消失：/reset 只能還原成出廠預設值，使用者自行設定過的排序無法救回。

#### 復現步驟

1. 送出 POST /api/indexaddr/update，其中 `ranks` 陣列只有八個元素而非九個——例如來自另一個版本的頁面。
2. 回應為 200：「Rankings updated and BIOG_MAIN rebuilt successfully」。
3. 開啟「索引地址」表單，第 9 順位出現地址類型 0（unknown），而這是使用者從未選過的。
4. 統計擁有索引地址的人數：請求之前為 383,322，之後為 379,051。
5. 按下「重設」，出廠預設順序會回來——但使用者原先設定過的排序已經永久遺失。

#### 建議修復方式

改用 slice 解碼 ranks，並拒絕欄位數不等於九的請求；同時拒絕不存在於 BIOG_ADDR_CODES 的地址類型。（0 在 BIOG_ADDR_CODES 中是一筆真實資料，名稱為 unknown，這正是補零之所以無人察覺的原因。）

#### 對應的程式位置

- `Code/indexaddr_form_backend.go:69 (Ranks is a fixed [9]int)`
- `Code/indexaddr_form_backend.go:182 (decode, then no length check)`
- `Code/indexaddr_form_backend.go:199 (the duplicate check that accidentally catches the other bad bodies)`

#### 對應的測試

- 1 × 預期失敗（已知缺陷，仍然存在）: `test_a_ranking_of_the_wrong_length_is_refused`

## CBDB-D-002 — 查詢建構器提供了 30 個並不存在的欄位

**涉及範圍：** 查詢建構器（/QBE）

**嚴重等級：** P2 — 可見的執行時錯誤——使用者的操作以伺服器錯誤收場。

**本次執行狀態：** 已確認

#### 問題描述

Data/qbe_schema.json 中列出了 8 個檢視表下的 30 個欄位，而 Data/CBDB.db 裡並沒有這些欄位。HasColumn 只拿這份 JSON 白名單驗證請求，從不對照真正的資料庫，因此這些欄位都能通過驗證，最後在 SQLite 執行時才失敗。

#### 實測依據

以 PRAGMA table_info 比對白名單中全部 99 張表，找出 30 個不存在的欄位，分布於 View_BiogInstAddrData、View_BiogInstData、View_BiogSourceData、View_BiogTextData、View_Entry、View_EventData、View_KinAddr 與 View_PostingOfficeData。透過 /api/qbe/run 選用其中任一個，都會得到 HTTP 500「Query failed: no such column」。其中四個還正好是該表清單中的第一個欄位，使用者點一下就會踩到。

#### 影響

使用者從查詢建構器自己提供的下拉選單中挑了一個欄位，換來的卻是伺服器錯誤，而且完全看不出這個欄位其實從一開始就不可用。這 8 個檢視表的其他欄位仍可正常使用。

#### 復現步驟

1. 開啟查詢建構器（/QBE）。
2. 把 `View_Entry` 這張表加入查詢格線。
3. 從欄位清單——也就是頁面自己提供的那一份——選擇 `c_personid`。
4. 按下執行，得到 HTTP 500：「Query failed: no such column: v.c_personid」。
5. 8 個檢視表下共 30 個欄位都是如此；完整清單釘在 tests/test_qbe.py 中。

#### 建議修復方式

用 Code/gen_qbe_schema.py 依實際結構重新產生 Data/qbe_schema.json；並讓 LoadSchemaFromJSON 在啟動時就逐一比對白名單欄位是否真的存在，讓過期的白名單在啟動階段就明確報錯，而不是等到使用者查詢時才失敗。

#### 對應的程式位置

- `Code/qbe_schema.go:89`
- `Code/gen_qbe_schema.py`
- `Data/qbe_schema.json`

#### 對應的測試

- 32 × 預期失敗（已知缺陷，仍然存在）: `test_every_offered_column_exists_in_the_database`, `test_every_offered_table_can_actually_be_queried`, `test_a_phantom_column_gives_the_user_a_server_error[View_BiogInstAddrData-c_personid]`, `test_a_phantom_column_gives_the_user_a_server_error[View_BiogInstAddrData-c_notes]` (+28)

## CBDB-D-005 — 釋出檔中殘留了前一次使用的工作狀態

**涉及範圍：** 釋出的資料庫（Data/CBDB.db）

**嚴重等級：** P3 — 封裝問題——釋出的檔案裡含有不該出現的內容。

**本次執行狀態：** 已確認

#### 問題描述

釋出的資料庫中有 14 張 ZZ_* 暫存表，仍留著某一次工作階段的結果。各表單啟動時會讀取這些表，因此全新安裝一打開，工作清單裡就已經有一個人物；而使用者什麼都還沒查詢，匯出就會給出別人的資料。

#### 實測依據

在釋出資料庫的全新複本上，於任何會改變狀態的請求之前：/api/kinship/person-count 與 /api/networks/person-count 都回傳 1（ZZ_SCRATCH_IMPORT_PEOPLE 中是歐陽修，人物編號 1384）；store-count 回傳 2；/api/assocpairs/recall-ids 回傳呂大器與呂祖謙；「入仕」匯出得到 123 列、「社會關係」匯出得到 16 列，而這些查詢使用者從未執行過。ZZ_KIN_LIST（112 列）、ZZ_SCRATCH_KINNET（111 列）、ZZ_SCRATCH_PEOPLE（88 列）、ZZ_SCRATCH_ENTRY（123 列）等另外九張表同樣有殘留內容。

#### 影響

新使用者第一次按下匯出，拿到的是別人的查詢結果，而且完全看不出那不是自己的；「親屬關係」與「社會網路」表單一開始就已經帶著一個沒人選過的人物。這也表示這份釋出檔是從一個「用過的」資料庫打包出來的，而非乾淨的資料庫。影響是有限的：每個表單在寫入前都會先清空自己的暫存表，所以這些殘留只會存活到使用者第一次查詢為止——這也是本項評為中等而非高的原因。

#### 復現步驟

1. 安裝釋出版本並啟動程式，什麼都先別做。
2. 開啟「親屬關係」表單：工作清單裡已經有歐陽修（人物編號 1384）。
3. 開啟「入仕」表單，不執行任何查詢，直接按「匯出結果」，得到的檔案有 123 列。
4. 對釋出的 Data/CBDB.db 執行 `SELECT COUNT(*) FROM ZZ_SCRATCH_ENTRY` 會得到 123；另外還有十三張 ZZ_* 表同樣非空。

#### 建議修復方式

打包前清空所有 ZZ_* 暫存表，並在建置流程加一道檢查確認它們為空。清空幾乎沒有代價：每個表單本來就會在寫入前先清空自己的暫存表。

#### 對應的程式位置

- `Data/CBDB.db`
- `Code/kinship_form_backend.go:handlePersonCount`
- `Code/entry_form_backend.go:handleExportResults`

#### 對應的測試

- 1 × 預期失敗（已知缺陷，仍然存在）: `test_a_fresh_install_starts_with_no_working_state`

## CBDB-D-003 — 姓名索引中有一位資料庫裡並不存在的人物

**涉及範圍：** 姓名索引（ZZZ_NAMES）

**嚴重等級：** P4 — 資料完整性——釋出資料中存在無法解析的參照。

**本次執行狀態：** 已確認

#### 問題描述

人物編號 100382 在 ZZZ_NAMES 中有資料，但 BIOG_MAIN 裡沒有對應的那一筆。ZZZ_NAMES 是建置時由 BIOG_MAIN 與 ALTNAME_DATA 推導出來的，因此這是一筆在來源資料已經刪除後、推導結果卻仍保留下來的紀錄。

#### 實測依據

只有一個人物編號有此問題：100382，元世祖 / 'Pouyuandaizhudi'。它出現在 ZZZ_NAMES 中，卻沒有對應的 BIOG_MAIN 資料。這個名字可以被搜尋到，但 /api/browser/person/100382 會回傳 404。

#### 影響

影響輕微：只是一個找得到、卻打不開的名字。之所以仍建議處理，主要是因為它顯示推導結果可能比來源資料活得更久——若日後規模擴大，同類問題會更麻煩。

#### 復現步驟

1. 在釋出的資料庫上列出「有名字卻查無此人」的紀錄：`SELECT DISTINCT n.c_personid FROM ZZZ_NAMES n LEFT JOIN BIOG_MAIN b ON b.c_personid = n.c_personid WHERE b.c_personid IS NULL`——回傳一列，100382。
2. 向執行中的程式請求這位人物：`GET /api/browser/person/100382` 回傳 404。

#### 建議修復方式

以目前的 BIOG_MAIN 重新產生 ZZZ_NAMES，並在建置流程加入一道參照完整性檢查。

#### 對應的程式位置

- `CBDBSetUpCode/zzznames_backend.go`

#### 對應的測試

- 1 × 預期失敗（已知缺陷，仍然存在）: `test_every_name_belongs_to_a_person_who_exists`

## 嚴重等級說明

- **P0** — 靜默的錯誤結果——程式回傳錯誤或空白的結果，而且沒有任何錯誤提示。
- **P1** — 破壞性寫入——一次請求改寫了本不該改寫的既存資料，原本的狀態無法復原。
- **P2** — 可見的執行時錯誤——使用者的操作以伺服器錯誤收場。
- **P3** — 封裝問題——釋出的檔案裡含有不該出現的內容。
- **P4** — 資料完整性——釋出資料中存在無法解析的參照。

## 如何重現這份報告

整份報告由一道指令產生。只要在 `.env` 中以 `CBDB_DESKTOP_ZIP` 指定發行壓縮檔：

```powershell
.\run_tests.ps1
```

這道指令會解開壓縮檔、以釋出資料庫的私有複本啟動釋出的執行檔、執行 234 項測試，並重新產生這幾份檔案。測試套件不會寫入作為對照基準的 `Data/CBDB.db`——每次執行都使用各自的複本，因此跑完之後，發行檔與執行前完全相同。

每一項問題底下都列出了對應的測試名稱。若只想執行其中一項：

```powershell
python -m pytest tests -k test_searching_people_by_name_finds_them -v
```


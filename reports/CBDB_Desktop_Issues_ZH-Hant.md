# CBDB-Desktop —— 問題彙報

_自動化迴歸測試過程中發現的問題彙總，謹呈維護團隊斧正。_

_受測版本：CBDB-Desktop_20260907.7z_

_本報告產生於 2026-09-08 08:59 UTC，依據一次 789 項測試的執行結果（耗時 174 秒）。_

尊敬的維護者：

以下是我們在為 CBDB-Desktop 編寫自動化迴歸測試套件的過程中，陸續整理出來的問題清單。我們希望這份報告能在您繼續主持這份寶貴資料集時有所助益；同時，對您多年來在這套資料與程式上的辛勤付出，我們由衷表示感謝與敬意。

以下每一項問題，都是實際啟動釋出的 `Bin/cbdb.exe`、以它自己的 HTTP 介面搭配釋出的資料庫實測出來的——我們沒有用 Python 重寫任何應用邏輯，因此這裡描述的就是釋出程式的真實行為。問題按嚴重程度排序（P0 最高），每一條都包含：簡要說明、據以認定的實測數據、逐步復現方式，以及一份建議的修復方案。這些問題都不緊急，整理於此只是方便您在合適的時候逐一處理。

## 本次執行結果

| 結果 | 數量 |
| --- | --- |
| 通過 | 670 |
| 預期失敗（已知缺陷，仍然存在） | 84 |
| 略過 | 35 |

## 測試套件的涵蓋範圍

| 範圍 | 測試數 | 檢查內容 |
| --- | --- | --- |
| 發行檔本身 | 54 | 受測的檔案樹確實逐一符合釋出的壓縮檔 |
| 應用程式行程 | 13 | 釋出的執行檔能啟動、能服務、並能釋放資料庫 |
| 所有已註冊的路由 | 17 | 從釋出的 Go 原始碼讀出的全部 141 條路由，逐一實測 |
| 代碼與地址清單 | 35 | 各表單在查詢前提供的下拉選單 |
| 查詢建構器 | 51 | 白名單、顯示給使用者的 SQL，以及各項防護 |
| 六個單次查詢的表單 | 51 | 入仕、官職、社會地位、著述、社會關係、地點——查詢與匯出 |
| 具狀態的表單 | 16 | 親屬關係、社會網路、關係配對、群組資料——工作清單 |
| 索引地址排序 | 12 | 唯一會改寫 CBDB 正式資料（而非暫存表）的端點 |
| 本報告自身的依據 | 22 | 以下每一項問題所引用的程式位置仍然存在，且中英文皆已填寫 |

## 問題總覽

| 編號 | 等級 | 本次執行狀態 | 問題 |
| --- | --- | --- | --- |
| CBDB-D-007 | P0 | 已確認 | 兩個 KML 匯出產生的檔案，任何地圖軟體都打不開 |
| CBDB-D-010 | P0 | 已確認 | 兩個瀏覽器分頁、或同時開兩份程式，會共用同一份查詢結果 |
| CBDB-D-011 | P0 | 已確認 | 所有匯出的 CSV 都是不帶 BOM 的 UTF-8，在 Excel 開啟時中文名字全變亂碼 |
| CBDB-D-012 | P0 | 已確認 | 多檔匯出只存下第一個檔案，卻回報「全部完成」 |
| CBDB-D-002 | P2 | 已確認 | 查詢建構器提供了 30 個並不存在的欄位 |
| CBDB-D-008 | P2 | 已確認 | 社會網絡表單有三個匯出按鈕永遠失敗 |
| CBDB-D-009 | P2 | 已確認 | 社會關係表單的 Neo4j 匯出永遠失敗 |

## 目錄

- [CBDB-D-007 — 兩個 KML 匯出產生的檔案，任何地圖軟體都打不開](#cbdb-d-007--兩個-kml-匯出產生的檔案，任何地圖軟體都打不開)
- [CBDB-D-010 — 兩個瀏覽器分頁、或同時開兩份程式，會共用同一份查詢結果](#cbdb-d-010--兩個瀏覽器分頁、或同時開兩份程式，會共用同一份查詢結果)
- [CBDB-D-011 — 所有匯出的 CSV 都是不帶 BOM 的 UTF-8，在 Excel 開啟時中文名字全變亂碼](#cbdb-d-011--所有匯出的-csv-都是不帶-bom-的-utf-8，在-excel-開啟時中文名字全變亂碼)
- [CBDB-D-012 — 多檔匯出只存下第一個檔案，卻回報「全部完成」](#cbdb-d-012--多檔匯出只存下第一個檔案，卻回報「全部完成」)
- [CBDB-D-002 — 查詢建構器提供了 30 個並不存在的欄位](#cbdb-d-002--查詢建構器提供了-30-個並不存在的欄位)
- [CBDB-D-008 — 社會網絡表單有三個匯出按鈕永遠失敗](#cbdb-d-008--社會網絡表單有三個匯出按鈕永遠失敗)
- [CBDB-D-009 — 社會關係表單的 Neo4j 匯出永遠失敗](#cbdb-d-009--社會關係表單的-neo4j-匯出永遠失敗)
- [嚴重等級說明](#嚴重等級說明)
- [如何重現這份報告](#如何重現這份報告)

## CBDB-D-007 — 兩個 KML 匯出產生的檔案，任何地圖軟體都打不開

**涉及範圍：** 入仕表單與地點表單——KML

**嚴重等級：** P0 — 靜默的錯誤結果——程式回傳錯誤或空白的結果，或產生任何軟體都讀不了的檔案，而且沒有任何錯誤提示。

**問題來源：** `software` — 程式本身的問題：cbdb.exe、其 Go 原始碼、頁面模板，或資料庫建置程式的邏輯。由 CBDB-Desktop 的開發者修正。

**本次執行狀態：** 已確認

#### 問題描述

入仕表單與地點表單的 KML 寫出程式，檔案開頭寫成 `<?xml version="1.0" encoding="UTF-8">`——XML 宣告的結尾用 `>` 而不是 `?>`。這不是合法的 XML，任何讀取程式都會在第一行就整檔拒絕。而程式端顯示成功，下載也完全正常。

#### 實測依據

在任一表單查詢後按下 KML，檔案開頭是 `<?xml version="1.0" encoding="UTF-8">`。Python 的 XML 解析器報「unclosed token: line 1, column 0」；Google Earth 與 QGIS 直接拒絕此檔。同一版程式裡另外五處 KML 寫出（社會關係、親屬關係、社會網絡、群體資料、官職）都正確地收尾，可見這是筆誤而非設計——也因此不必執行程式就能在原始碼裡找到：entry_form_backend.go:1002 與 places_form_backend.go:763。

#### 影響

研究者匯出某條入仕途徑或一組地點的地理資料，在 Google Earth 裡打開，卻被告知檔案損壞。程式端沒有任何跡象顯示出錯，於是最自然的結論會是地圖軟體有問題或資料有問題。同兩個表單的 GIS（.tab）匯出不受影響，可作為替代做法。

#### 復現步驟

1. 開啟入仕表單（/LookAtEntry），選一個入仕代碼並按下查詢。
2. 按下 KML 並儲存檔案。
3. 用 Google Earth、QGIS 或任何 XML 解析器開啟：檔案在第 1 行就被拒絕。
4. 地點表單（/LookAtPlaces）的情況完全相同。

#### 建議修復方式

把這兩處補上 `?>`。並建議抽出一個共用的函式來輸出 KML 檔頭：目前這段序言已經有七份副本，其中兩份是錯的。

#### 對應的程式位置

- `Code/entry_form_backend.go:1002`
- `Code/places_form_backend.go:763`

#### 對應的測試

- 49 × 通過: `test_an_export_produces_a_well_formed_file[entry:results]`, `test_an_export_produces_a_well_formed_file[entry:gis]`, `test_an_export_produces_a_well_formed_file[entry:neo4j]`, `test_an_export_produces_a_well_formed_file[entry:save]` (+45)
- 6 × 預期失敗（已知缺陷，仍然存在）: `test_an_export_produces_a_well_formed_file[entry:kml]`, `test_an_export_produces_a_well_formed_file[places:kml]`, `test_an_export_produces_a_well_formed_file[associations:neo4j]`, `test_an_export_produces_a_well_formed_file[networks:pajek]` (+2)

## CBDB-D-010 — 兩個瀏覽器分頁、或同時開兩份程式，會共用同一份查詢結果

**涉及範圍：** 所有具備工作清單或暫存結果的表單

**嚴重等級：** P0 — 靜默的錯誤結果——程式回傳錯誤或空白的結果，或產生任何軟體都讀不了的檔案，而且沒有任何錯誤提示。

**問題來源：** `software` — 程式本身的問題：cbdb.exe、其 Go 原始碼、頁面模板，或資料庫建置程式的邏輯。由 CBDB-Desktop 的開發者修正。

**本次執行狀態：** 已確認

#### 問題描述

請求裡沒有任何東西能辨識它來自哪個分頁或哪個工作階段。查詢寫入、匯出讀取的暫存表，每個資料庫只有一組，因此在一個分頁執行查詢，就會覆蓋另一個分頁即將匯出的內容。更嚴重的是，main.go 沒有取得單一實例鎖，而且預設使用 port 0，因此 cbdb.exe 可以對同一個 Data/cbdb.db 啟動兩次；此時程式內的 mutex 完全失去作用，因為兩個行程各有自己的一份。

#### 實測依據

這是 CBDB-Desktop 開發者在 2026-09-07 修復工作中自己找到的問題，當時記錄為未解決，這裡再從釋出的原始碼確認：為 CBDB-D-004 增加的「每個表單自有暫存表」消除了*跨表單*共用，但*跨請求*共用完全沒有改變。對處理程式而言，兩個打到同一端點的請求無從區分；而在 main.go 中搜尋，找不到任何 mutex、鎖檔、PID 檔或固定通訊埠的處理。

#### 影響

使用者在兩個分頁裡開著社會關係表單——這是比較兩個查詢再自然不過的做法——就可能匯出錯的那一份，而且沒有任何錯誤提示。兩個行程的情況比覆蓋更糟：SQLite 的 WAL 模式允許兩者同時寫入，於是兩邊的寫入可能交錯進同一組暫存表，產生的結果不屬於任何一次查詢。

#### 復現步驟

1. 在兩個瀏覽器分頁中開啟社會關係表單。
2. 在分頁 A 執行一次查詢，格線填入結果。
3. 在分頁 B 執行另一次不同的查詢。
4. 回到分頁 A 按下匯出結果：檔案的內容是分頁 B 的查詢結果。
5. 另外：把 Bin/cbdb.exe 啟動兩次。兩者都會啟動、都會開啟同一個 Data/cbdb.db，而且都不會提到對方的存在。

#### 建議修復方式

把暫存狀態改成依工作階段（session）而非依表單命名空間：在 cookie 中放一個 session id，並採用依 session 命名的表、或在每張暫存表中加一個 session 欄位。另外一個便宜得多的做法是：拒絕對同一個資料庫啟動第二個實例（在 Data/cbdb.db 旁放一個鎖檔，啟動時檢查）——僅此一項就能消除交錯寫入的那一半問題。

#### 對應的程式位置

- `Code/main.go`
- `Code/associations_form_backend.go:233`
- `Code/networks_form_backend.go:411`

#### 對應的測試

- 2 × 預期失敗（已知缺陷，仍然存在）: `test_a_second_query_replaces_what_the_first_would_export`, `test_nothing_stops_a_second_instance_opening_the_database`

## CBDB-D-011 — 所有匯出的 CSV 都是不帶 BOM 的 UTF-8，在 Excel 開啟時中文名字全變亂碼

**涉及範圍：** 所有表單的所有匯出功能

**嚴重等級：** P0 — 靜默的錯誤結果——程式回傳錯誤或空白的結果，或產生任何軟體都讀不了的檔案，而且沒有任何錯誤提示。

**問題來源：** `software` — 程式本身的問題：cbdb.exe、其 Go 原始碼、頁面模板，或資料庫建置程式的邏輯。由 CBDB-Desktop 的開發者修正。

**本次執行狀態：** 已確認

#### 問題描述

匯出的檔案名為 EntryData_UTF8.csv、AssociationsPeople_UTF8.csv 之類，內容的位元組也確實是 UTF-8——但沒有任何一個檔案帶上 UTF-8 的位元組順序記號（BOM）。Windows 版 Excel 判斷 .csv 編碼的方式就是找這個記號，找不到就改用系統的 ANSI 代碼頁來讀。於是檔案裡所有中文人名、地名與書名，開起來全都是亂碼。

#### 實測依據

測試會把每一個匯出檔解碼並檢查開頭的位元組：42 個會產生檔案的端點裡，沒有一個輸出 EF BB BF；在釋出的 Go 原始碼中以各種寫法搜尋 BOM（\xEF、\uFEFF、"BOM"）也完全找不到。而檔案內容在所有真正會用到的情況下都含有非 ASCII 字元——例如一個親屬網絡的 Neo4j People 檔，第二欄就是中文姓名。

#### 影響

對多數使用者而言，這正是這個程式存在的目的：匯出結果，然後打開來看。程式顯示成功、檔案順利下載，畫面上卻是一片無法閱讀的內容——看起來像資料壞了，而不是編碼預設值的問題，於是最自然的反應會是懷疑 CBDB 的資料。變通做法（資料 > 從文字/CSV，選 UTF-8）並不容易被發現，而只要在每個檔案開頭加上三個位元組就不再需要它。

#### 復現步驟

1. 開啟入仕表單（/LookAtEntry），選一個入仕代碼並按下查詢。
2. 按下匯出結果，儲存 EntryPeopleData_UTF8.csv。
3. 直接雙擊該檔讓 Excel 開啟：中文欄位是亂碼。
4. 檢視檔案開頭的位元組——執行 `certutil -dump EntryPeopleData_UTF8.csv | more`，或用十六進位編輯器開啟——會發現沒有 EF BB BF。
5. 改用「資料 > 從文字/CSV」重新開啟同一個檔案並選擇 65001 / UTF-8：文字就正確了。這正說明缺少那個記號就是問題的全部。

#### 建議修復方式

在每一個以試算表為使用對象的文字匯出檔開頭寫入 EF BB BF——也就是 .csv、.tab 與 .txt 這幾類。由於這些緩衝區的建立方式相同，可以集中在一個共用函式處理（CSV 類最自然的位置是 cbdb_shared_utils.go 的 toDataURL）。KML 與社會網絡格式請保持原狀：XML 會自行宣告編碼，而 Pajek、GDF、VNA 的讀取程式並不預期有這個記號。

#### 對應的程式位置

- `Code/cbdb_shared_utils.go:60`
- `Code/entry_form_backend.go`
- `Code/kinship_form_backend.go`

#### 對應的測試

- 1 × 通過: `test_no_export_writes_a_byte_order_mark`
- 9 × 略過: `test_a_spreadsheet_export_can_be_opened_by_a_spreadsheet[places:pajek]`, `test_a_spreadsheet_export_can_be_opened_by_a_spreadsheet[places:gephi]`, `test_a_spreadsheet_export_can_be_opened_by_a_spreadsheet[places:ucinet]`, `test_a_spreadsheet_export_can_be_opened_by_a_spreadsheet[kinship:pajek]` (+5)
- 31 × 預期失敗（已知缺陷，仍然存在）: `test_a_spreadsheet_export_can_be_opened_by_a_spreadsheet[entry:results]`, `test_a_spreadsheet_export_can_be_opened_by_a_spreadsheet[entry:gis]`, `test_a_spreadsheet_export_can_be_opened_by_a_spreadsheet[entry:neo4j]`, `test_a_spreadsheet_export_can_be_opened_by_a_spreadsheet[entry:save]` (+27)

## CBDB-D-012 — 多檔匯出只存下第一個檔案，卻回報「全部完成」

**涉及範圍：** 所有會回傳多個檔案的表單匯出功能（匯出結果、Neo4j）

**嚴重等級：** P0 — 靜默的錯誤結果——程式回傳錯誤或空白的結果，或產生任何軟體都讀不了的檔案，而且沒有任何錯誤提示。

**問題來源：** `software` — 程式本身的問題：cbdb.exe、其 Go 原始碼、頁面模板，或資料庫建置程式的邏輯。由 CBDB-Desktop 的開發者修正。

**本次執行狀態：** 已確認

#### 問題描述

會產生多個檔案的匯出，做法是為每個檔案建立一個隱藏的 <a download> 並依序點擊，而且全部發生在同一次使用者操作中。瀏覽器每次操作只允許一個自動下載，其餘會被封鎖，因此只有第一個檔案被存下來，其他都沒有。接著頁面回報的是*伺服器*送回的檔案數量——「2 file(s) ready」——因為它數的是回應內容，而不是實際完成的下載。一旦觸發封鎖，瀏覽器連後續的匯出也會一併拒絕，這就是為什麼第二次按下匯出看起來毫無反應。

#### 實測依據

維護者在執行中的版本上重現：於 http://localhost:8042/LookAtEntry 按下匯出結果，畫面顯示「Query results export complete — 2 file(s) ready」，實際只收到一個檔案；再按一次匯出則完全沒有存下任何東西。機制就在釋出的頁面模板裡：入仕表單的兩個多檔處理函式在同一個事件迴圈裡連續點擊——`(j.files || []).forEach(f => triggerDownload(f.url, f.name))`——然後回報 `(j.files || []).length`。共有四個頁面採用同樣寫法；社會關係與社會網絡頁面會以每個檔案 150 毫秒的間隔錯開點擊，那是針對同一問題的嘗試，但仍屬於同一次使用者操作。群體資料的 Neo4j 匯出就是這樣一次回傳十個檔案。

#### 影響

遺失的是第二個檔案，而在每個表單裡那都是人物檔——姓名、指標年與座標。相信畫面訊息的使用者會以為自己拿到了完整的匯出結果，若真的發現不對，往往也已經過了很久。此外，它也讓匯出按鈕在第二次按下時看起來壞掉了——這個問題就是這樣被發現的。

#### 復現步驟

1. 開啟入仕表單（/LookAtEntry），選一個入仕代碼並按下查詢。
2. 按下匯出結果，狀態列顯示「Query results export complete — 2 file(s) ready」。
3. 查看下載資料夾：只有一個檔案，不是兩個。
4. 再按一次匯出結果，什麼都沒有存下來，狀態列仍顯示同樣的訊息。
5. 入仕、人物配對與群體資料表單的 Neo4j 匯出也一樣，它們的檔案組分別是六個、四個與十個檔案。

#### 建議修復方式

分成兩個彼此獨立的部分。(1) 讓多檔匯出變成**一次**下載：最常見的做法是在伺服器端打包成 zip，完全不需要瀏覽器配合。(2) 不要回報頁面無從得知的數量：可以說明「正在準備 2 個檔案」或什麼都不說，但絕不要說「已下載 2 個檔案」。後者每個處理函式只需改一行，就能去掉這個問題中會誤導使用者的部分。

#### 對應的程式位置

- `Templates/entry/index.html`
- `Templates/group_data/index.html`
- `Templates/association_pairs/index.html`
- `Templates/associations/index.html`

#### 對應的測試

- 1 × 預期失敗（已知缺陷，仍然存在）: `test_no_page_asks_the_browser_for_more_than_one_download`

## CBDB-D-002 — 查詢建構器提供了 30 個並不存在的欄位

**涉及範圍：** 查詢建構器（/QBE）

**嚴重等級：** P2 — 可見的執行時錯誤——使用者的操作以伺服器錯誤收場。

**問題來源：** `software` — 程式本身的問題：cbdb.exe、其 Go 原始碼、頁面模板，或資料庫建置程式的邏輯。由 CBDB-Desktop 的開發者修正。

**本次執行狀態：** 已確認

#### 問題描述

Data/qbe_schema.json 列出 8 個檢視表下的 30 個欄位，而 Data/cbdb.db 並沒有以這些名稱存在的欄位。這 8 個檢視表都各自把同一個欄位名選了兩次——例如 KIN_DATA.c_personid 與 View_PeopleData.c_personid——SQLite 解決撞名的方式是把後者改名為 `c_personid:1`。白名單產生程式是讀 CREATE VIEW 的文字，並未模擬這個改名，於是提供了資料庫並不認得的名稱。ValidateGridState 只拿 JSON 驗證請求，所以這些欄位都能通過驗證，最後在 SQLite 執行時才失敗。

#### 實測依據

以 PRAGMA table_info 比對白名單中全部 102 張表，找出 30 個不存在的欄位，分布於 View_BiogInstAddrData、View_BiogInstData、View_BiogSourceData、View_BiogTextData、View_Entry、View_EventData、View_KinAddr 與 View_PostingOfficeData。這 30 個欄位每一個都在同一個檢視表裡有一個加了「:1」的兄弟欄位——一對一完全對應，這正說明機制是撞名改名，而不是檔案過期。透過 /api/qbe/run 選用其中任一個，都會得到 HTTP 500「Query failed: no such column」。其中四個還正好是該檢視表清單中的第一個欄位，使用者點一下就會踩到。

#### 影響

使用者從查詢建構器自己提供的下拉選單中挑了一個欄位，換來的卻是伺服器錯誤，而且完全看不出這個欄位其實從一開始就不可用。這 8 個檢視表的其他欄位仍可正常使用。由於根本原因是輸出欄位撞名、而不是檔案過期，因此再從同一份 CREATE VIEW 文字重新產生 qbe_schema.json（2026-09-07 版就是這麼做的）並不會有任何改變：JSON 與 SQL 彼此一致，卻都與 SQLite 不一致。

#### 復現步驟

1. 開啟查詢建構器（/QBE）。
2. 把檢視表 `View_Entry` 加入查詢格線。
3. 從欄位清單——也就是頁面自己提供的那一份——選擇 `c_personid`。
4. 按下執行，得到 HTTP 500：「Query failed: no such column: v.c_personid」。
5. 在釋出的資料庫上執行 `PRAGMA table_info(View_Entry)`，看到的是 `c_personid:1`，沒有 `c_personid`。
6. 8 個檢視表下共 30 個欄位都是如此；完整清單釘在 tests/test_qbe.py 中。

#### 建議修復方式

有兩個彼此獨立的部分，而第一個才是真正的修法。(1) 讓這 8 個檢視表的輸出欄位名稱不再撞名——在 CBDBSetUpCode/CBDB_AdditionalTablesViewsIndices.sql 的 CREATE VIEW 中為重複出現的那一個加上別名——這樣 SQLite 就沒有東西需要改名。名為 `c_personid:1` 的欄位任何客戶端都無法選取，所以無論查詢建構器怎麼做，這件事都值得做。(2) 改由對已建好的資料庫執行 PRAGMA table_info 來產生 qbe_schema.json，而不是解析 CREATE VIEW 的文字，白名單就不可能描述出資料庫沒有的欄位。這一版其實已經附了一個能抓到這個問題的 Go 測試——Code/qbe_schema_test.go，正是為這個缺陷而寫，而且確實使用 PRAGMA table_info——但它在非專案根目錄執行時會自行跳過，而且並未對這個資料庫執行過。

#### 對應的程式位置

- `Code/qbe_schema.go:89`
- `Code/qbe_schema_test.go`
- `Data/gen_qbe_schema.py`
- `Data/qbe_schema.json`
- `CBDBSetUpCode/CBDB_AdditionalTablesViewsIndices.sql`

#### 對應的測試

- 1 × 通過: `test_no_view_resolves_two_columns_to_the_same_name`
- 32 × 預期失敗（已知缺陷，仍然存在）: `test_every_offered_column_exists_in_the_database`, `test_every_offered_table_can_actually_be_queried`, `test_a_phantom_column_gives_the_user_a_server_error[View_BiogInstAddrData-c_personid]`, `test_a_phantom_column_gives_the_user_a_server_error[View_BiogInstAddrData-c_notes]` (+28)

## CBDB-D-008 — 社會網絡表單有三個匯出按鈕永遠失敗

**涉及範圍：** 社會網絡表單（/LookAtNetworks）——Pajek、Gephi 與 UCINet

**嚴重等級：** P2 — 可見的執行時錯誤——使用者的操作以伺服器錯誤收場。

**問題來源：** `software` — 程式本身的問題：cbdb.exe、其 Go 原始碼、頁面模板，或資料庫建置程式的邏輯。由 CBDB-Desktop 的開發者修正。

**本次執行狀態：** 已確認

#### 問題描述

Pajek、Gephi 與 UCINet 三個匯出功能都從 ZZ_SN_NETWORK 讀取網絡的邊，並向這張表要一個叫 c_node_dist 的欄位。ZZ_SN_NETWORK 沒有這個欄位——它每一條邊帶的距離叫 c_edge_dist——所以 SQLite 直接拒絕這個查詢，處理程式回傳 HTTP 500。無論輸入什麼，這三個按鈕都不可能成功。

#### 實測依據

先為一位在距離 1 以內有親屬的人物執行社會網絡查詢，再按下 Pajek、Gephi 或 UCINet：三者都回傳 HTTP 500「Database error: no such column: c_node_dist」。同一批處理程式裡的節點查詢是向 ZZ_SP_NETWORK 要 c_node_dist，那張表確實有；出錯的只有對 ZZ_SN_NETWORK 的邊查詢。以 PRAGMA table_info 在釋出的資料庫上確認：ZZ_SN_NETWORK 的 89 個欄位裡有 c_edge_dist，沒有 c_node_dist。

#### 影響

在一個以社會網絡分析為全部目的的表單上，七種匯出格式裡有三種完全不能用。想把 CBDB 的網絡帶進 Pajek、Gephi 或 UCINet 的人，只能改走親屬關係或人物配對表單——同樣的三種格式在那裡是正常的。這個問題比 2026-09-07 的「每個表單自有暫存表」更早：被取代的共用表 ZZ_SOCIAL_NETWORK 同樣沒有 c_node_dist，也就是說這三個按鈕從來沒有正常運作過，只是先前沒有任何測試按下它們。

#### 復現步驟

1. 開啟社會網絡表單（/LookAtNetworks），設定一位有親屬的人物。
2. 以最小的距離參數（maxLoop 1、maxNodeDist 1）按下執行，讓查詢回傳一個圖。
3. 按下 Pajek，回應是 HTTP 500「Database error: no such column: c_node_dist」。
4. Gephi 與 UCINet 也一樣。同一表單上的匯出結果、GIS、KML 與 Neo4j 都正常。

#### 建議修復方式

在 networks_form_backend.go 裡，把這三個邊查詢改成選取 c_edge_dist（ZZ_SN_NETWORK 真正擁有的欄位），或者若配色其實要表達的是節點距離，就從 ZZ_SP_NETWORK 併入。兩種解讀都說得通，程式本身無法判斷原意，因此這裡只報告而不逕行修改。

#### 對應的程式位置

- `Code/networks_form_backend.go:2089`
- `Code/networks_form_backend.go:2212`
- `Code/networks_form_backend.go:2337`
- `Code/networks_form_backend.go:419`

#### 對應的測試

- 98 × 通過: `test_an_export_produces_a_well_formed_file[entry:results]`, `test_an_export_produces_a_well_formed_file[entry:gis]`, `test_an_export_produces_a_well_formed_file[entry:neo4j]`, `test_an_export_produces_a_well_formed_file[entry:save]` (+94)
- 10 × 預期失敗（已知缺陷，仍然存在）: `test_an_export_produces_a_well_formed_file[entry:kml]`, `test_an_export_produces_a_well_formed_file[places:kml]`, `test_an_export_produces_a_well_formed_file[associations:neo4j]`, `test_an_export_produces_a_well_formed_file[networks:pajek]` (+6)

## CBDB-D-009 — 社會關係表單的 Neo4j 匯出永遠失敗

**涉及範圍：** 社會關係表單（/LookAtAssociations）——Neo4j

**嚴重等級：** P2 — 可見的執行時錯誤——使用者的操作以伺服器錯誤收場。

**問題來源：** `software` — 程式本身的問題：cbdb.exe、其 Go 原始碼、頁面模板，或資料庫建置程式的邏輯。由 CBDB-Desktop 的開發者修正。

**本次執行狀態：** 已確認

#### 問題描述

產生 Neo4j 檔案時會讀取 ADDR_CODES，並把 c_admin_type 掃描成 Go 的 int。但在釋出的資料庫裡這個欄位是文字：全部 30,100 列的內容都是行政層級的名稱，例如「State」、「Shengshi」、「[Unknown]」。第一筆地址就掃描失敗，處理程式放棄，回傳 HTTP 500。

#### 實測依據

執行任何社會關係查詢後按下 Neo4j：HTTP 500「Neo4j export error: scan addrRow: sql: Scan error on column index 3」。索引 3 就是 c_admin_type。在釋出的資料庫上執行 `SELECT DISTINCT typeof(c_admin_type) FROM ADDR_CODES` 只會得到 'text'，結構定義也是 varchar(255)——換言之，再怎麼更新資料，這個掃描都不會成功。其他五個表單的同一種匯出並沒有要這個欄位，因此正常運作。

#### 影響

社會關係網絡完全無法匯入 Neo4j。這個表單的其他三種匯出正常，資料仍有別的取得方式，但使用者為此按下的那個按鈕每次都以伺服器錯誤收場。

#### 復現步驟

1. 開啟社會關係表單（/LookAtAssociations），選一個記錄不多的關係代碼。
2. 按下查詢，格線填入結果。
3. 按下 Neo4j，回應是 HTTP 500「Neo4j export error: scan addrRow」。

#### 建議修復方式

把 c_admin_type 掃描成字串；若下游確實需要數字，應透過 ADDR_CODES 自己的類型表換算，而不是假設這個欄位是數值。建議同時檢查其他所有對 ADDR_CODES 的 Scan：這個欄位的名字看起來像代碼，內容卻不是。

#### 對應的程式位置

- `Code/associations_form_backend.go:1384`
- `Code/associations_form_backend.go:1395`

#### 對應的測試

- 98 × 通過: `test_an_export_produces_a_well_formed_file[entry:results]`, `test_an_export_produces_a_well_formed_file[entry:gis]`, `test_an_export_produces_a_well_formed_file[entry:neo4j]`, `test_an_export_produces_a_well_formed_file[entry:save]` (+94)
- 10 × 預期失敗（已知缺陷，仍然存在）: `test_an_export_produces_a_well_formed_file[entry:kml]`, `test_an_export_produces_a_well_formed_file[places:kml]`, `test_an_export_produces_a_well_formed_file[associations:neo4j]`, `test_an_export_produces_a_well_formed_file[networks:pajek]` (+6)

## 嚴重等級說明

- **P0** — 靜默的錯誤結果——程式回傳錯誤或空白的結果，或產生任何軟體都讀不了的檔案，而且沒有任何錯誤提示。
- **P1** — 破壞性寫入——一次請求改寫了本不該改寫的既存資料，原本的狀態無法復原。
- **P2** — 可見的執行時錯誤——使用者的操作以伺服器錯誤收場。
- **P3** — 封裝問題——釋出的檔案裡含有不該出現的內容。
- **P4** — 資料完整性——釋出資料中存在無法解析的參照。

## 如何重現這份報告

整份報告由一道指令產生。只要在 `.env` 中以 `CBDB_DESKTOP_ZIP` 指定發行壓縮檔：

```powershell
.\run_tests.ps1
```

這道指令會解開壓縮檔、以釋出資料庫的私有複本啟動釋出的執行檔、執行 789 項測試，並重新產生這幾份檔案。測試套件不會寫入作為對照基準的 `Data/CBDB.db`——每次執行都使用各自的複本，因此跑完之後，發行檔與執行前完全相同。

每一項問題底下都列出了對應的測試名稱。若只想執行其中一項：

```powershell
python -m pytest tests -k test_searching_people_by_name_finds_them -v
```


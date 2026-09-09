# CBDB-Desktop —— 問題彙報

_自動化迴歸測試過程中發現的問題彙總，謹呈維護團隊斧正。_

_受測版本：CBDB-Desktop_20260908.7z_

_本報告產生於 2026-09-09 11:58 UTC，依據一次 1099 項測試的執行結果（耗時 366 秒）。_

尊敬的維護者：

以下是我們在為 CBDB-Desktop 編寫自動化迴歸測試套件的過程中，陸續整理出來的問題清單。我們希望這份報告能在您繼續主持這份寶貴資料集時有所助益；同時，對您多年來在這套資料與程式上的辛勤付出，我們由衷表示感謝與敬意。

以下的問題，多數是實際啟動釋出的 `cbdb.exe`、以它自己的 HTTP 介面搭配釋出的資料庫實測出來的；其餘則是直接閱讀釋出的頁面模板、Go 原始碼與發行壓縮檔而確認的——對於根本不需要查詢就能證明的問題，這才是誠實的說法。無論是哪一種，我們都沒有用 Python 重寫任何應用邏輯，因此這裡描述的就是釋出程式的真實行為。問題按嚴重程度排序（P0 最高），每一條都包含：簡要說明、據以認定的實測數據、逐步復現方式，以及一份建議的修復方案。這些問題都不緊急，整理於此只是方便您在合適的時候逐一處理。

## 本次執行結果

| 結果 | 數量 |
| --- | --- |
| 通過 | 894 |
| 失敗 | 78 |
| 預期失敗（已知缺陷，仍然存在） | 3 |
| 略過 | 124 |

在 78 項失敗中，有 **77** 項是用來證明下列問題的測試——這些問題正是由它們認定的，問題修好之後它們就會恢復通過。其餘 **1** 項在下方逐一交代，以免讀者拿這些數字去對照問題清單，卻發現兩邊對不起來。

其中 **1** 項指向的是本測試套件自身的覆蓋缺口，而不是釋出版本的缺陷：介面上有、但我們尚未驅動過的東西。那部分該由我們補上，與您無關。

| 對應檢查 | 指出我們尚未驅動的部分 |
| --- | --- |
| `test_every_endpoint_the_ui_can_reach_is_exercised_by_this_run` | 介面上可以到達、但本次執行從未實際請求過的端點；完整清單見 artifacts/endpoint_coverage.json（14 endpoint(s) a user can reach from the interface were never requested by this run） |

## 測試套件的涵蓋範圍

| 範圍 | 測試數 | 檢查內容 |
| --- | --- | --- |
| 發行檔本身 | 59 | 受測的檔案樹確實逐一符合釋出的壓縮檔 |
| 應用程式行程 | 13 | 釋出的執行檔能啟動、能服務、並能釋放資料庫 |
| 所有已註冊的路由 | 17 | 從釋出的 Go 原始碼讀出的全部 141 條路由，逐一實測 |
| 代碼與地址清單 | 35 | 各表單在查詢前提供的下拉選單 |
| 查詢建構器 | 51 | 白名單、顯示給使用者的 SQL，以及各項防護 |
| 六個單次查詢的表單 | 51 | 入仕、官職、社會地位、著述、社會關係、地點——查詢與匯出 |
| 具狀態的表單 | 16 | 親屬關係、社會網路、關係配對、群組資料——工作清單 |
| 索引地址排序 | 12 | 唯一會改寫 CBDB 正式資料（而非暫存表）的端點 |
| 每一個篩選條件，輸入取自資料本身 | 254 | 依釋出資料庫中實際有資料的組合各跑一次查詢，並將每個開關的兩種狀態都測過 |
| 所有匯出按鈕 | 497 | 45 個會產生檔案的端點全部按過，並回讀所得檔案 |
| 在真實瀏覽器中的頁面 | 7 | 每個頁面載入時不拋錯；等待使用者操作的控制項在條件滿足後確實解除停用 |
| 同時開兩個分頁 | 3 | 一次查詢是否會取代另一個分頁即將匯出的內容 |
| 暫存工作表 | 6 | 各表單各自擁有哪些暫存表——從釋出的 Go 原始碼讀出並釘住 |
| 本次執行自身的覆蓋率 | 5 | 釋出頁面能觸及的每一個端點，本次執行是否真的都請求過 |
| 已協商擱置的項目 | 28 | 每一條擱置項目是否仍對應到本次執行中存在的檢查，以及套件中沒有其他地方私自容忍失敗 |
| 本報告自身的依據 | 22 | 以下每一項問題所引用的程式位置仍然存在，且中英文皆已填寫 |
| 本報告本身 | 23 | 本報告可由上述執行結果完整重現，不會憑空產生問題、不會遺漏問題，也不會隱藏任何擱置項目 |
| 本次執行的全部測試 | 1099 |  |

## 已協商暫時擱置的項目

以下項目均為已知情形，並已協商暫時維持現狀。列於此處是為了避免任何問題被無聲地忽略：每一項都指明了對應的檢查名稱，隨時可以重新處理。

| 對應檢查 | 適用範圍 | 處理方式 | 協商紀錄 | 有效期至 | 原因 |
| --- | --- | --- | --- | --- | --- |
| test_a_second_query_replaces_what_the_first_would_export | 全部情況 | 仍然檢查，失敗予以容忍 | 2026-09-09 (maintainer) | 未設期限 | 已協商暫時維持現狀：暫存表每個資料庫只有一組，因此在第二個分頁執行查詢，會取代第一個分頁即將匯出的內容。若要改成依工作階段（session）劃分命名空間，等於重新設計所有表單儲存工作狀態的方式；而這一版的使用者一次只會開一個視窗作業。 |
| test_a_second_working_list_replaces_the_first | 全部情況 | 仍然檢查，失敗予以容忍 | 2026-09-09 (maintainer) | 未設期限 | 同一項協商，發生在更早的一步：同一個表單的兩個分頁共用一份工作清單，因此第二次匯入會取代第一次，接下來的查詢對象也就換成了另一批人。基於同樣的理由暫時維持現狀。 |
| test_nothing_stops_a_second_instance_opening_the_database | 全部情況 | 仍然檢查，失敗予以容忍 | 2026-09-09 (maintainer) | 未設期限 | 同一項協商，發生在行程層級：main.go 沒有取得單一實例鎖，通訊埠也是隨機選取，因此 cbdb.exe 可以對同一個資料庫啟動兩次。加一個鎖檔是這個問題最便宜的一半修法，經協商同樣留待日後的版本處理。 |

## 問題總覽

| 編號 | 等級 | 本次執行狀態 | 問題 |
| --- | --- | --- | --- |
| CBDB-D-001 | P0 | 已確認 | 兩個 KML 匯出功能寫出的 XML 宣告沒有結尾，任何軟體都無法讀取這個檔案 |
| CBDB-D-002 | P0 | 已確認 | 地點頁面允許使用者取消勾選全部類別，然後回傳他們已排除的「傳記」資料 |
| CBDB-D-003 | P0 | 已確認 | 二十二個匯出按鈕會一次要求瀏覽器儲存多個檔案，其中二十一個更在只有第一個檔案下載成功時，回報所有檔案都已儲存 |
| CBDB-D-004 | P2 | 已確認 | 網絡表單四個網絡匯出中有三個對任何輸入都回傳 HTTP 500：它們查詢了自己的暫存表所沒有的欄位 |
| CBDB-D-005 | P2 | 已確認 | 只要查詢結果帶有地址，關聯表單的 Neo4j 匯出就回傳 HTTP 500：程式把一個文字欄位讀進整數變數 |
| CBDB-D-006 | P2 | 已確認 | 查詢建構器提供了 30 個欄位，而釋出的檢視表其實是以另一個名稱呈現它們；每一個都會讓使用者得到伺服器錯誤 |
| CBDB-D-007 | P3 | 已確認 | 發行檔中一併附上了十份帶日期的模板工作副本 |

## 目錄

- [CBDB-D-001 — 兩個 KML 匯出功能寫出的 XML 宣告沒有結尾，任何軟體都無法讀取這個檔案](#cbdb-d-001--兩個-kml-匯出功能寫出的-xml-宣告沒有結尾，任何軟體都無法讀取這個檔案)
- [CBDB-D-002 — 地點頁面允許使用者取消勾選全部類別，然後回傳他們已排除的「傳記」資料](#cbdb-d-002--地點頁面允許使用者取消勾選全部類別，然後回傳他們已排除的「傳記」資料)
- [CBDB-D-003 — 二十二個匯出按鈕會一次要求瀏覽器儲存多個檔案，其中二十一個更在只有第一個檔案下載成功時，回報所有檔案都已儲存](#cbdb-d-003--二十二個匯出按鈕會一次要求瀏覽器儲存多個檔案，其中二十一個更在只有第一個檔案下載成功時，回報所有檔案都已儲存)
- [CBDB-D-004 — 網絡表單四個網絡匯出中有三個對任何輸入都回傳 HTTP 500：它們查詢了自己的暫存表所沒有的欄位](#cbdb-d-004--網絡表單四個網絡匯出中有三個對任何輸入都回傳-http-500：它們查詢了自己的暫存表所沒有的欄位)
- [CBDB-D-005 — 只要查詢結果帶有地址，關聯表單的 Neo4j 匯出就回傳 HTTP 500：程式把一個文字欄位讀進整數變數](#cbdb-d-005--只要查詢結果帶有地址，關聯表單的-neo4j-匯出就回傳-http-500：程式把一個文字欄位讀進整數變數)
- [CBDB-D-006 — 查詢建構器提供了 30 個欄位，而釋出的檢視表其實是以另一個名稱呈現它們；每一個都會讓使用者得到伺服器錯誤](#cbdb-d-006--查詢建構器提供了-30-個欄位，而釋出的檢視表其實是以另一個名稱呈現它們；每一個都會讓使用者得到伺服器錯誤)
- [CBDB-D-007 — 發行檔中一併附上了十份帶日期的模板工作副本](#cbdb-d-007--發行檔中一併附上了十份帶日期的模板工作副本)
- [嚴重等級說明](#嚴重等級說明)
- [如何重現這份報告](#如何重現這份報告)

## CBDB-D-001 — 兩個 KML 匯出功能寫出的 XML 宣告沒有結尾，任何軟體都無法讀取這個檔案

**涉及範圍：** 入仕表單與地點表單的 KML 匯出

**嚴重等級：** P0 — 靜默的錯誤結果——程式回傳錯誤或空白的結果，或產生任何軟體都讀不了的檔案，而且沒有任何錯誤提示。

**問題來源：** `software` — 程式本身的問題：cbdb.exe、其 Go 原始碼、頁面模板，或資料庫建置程式的邏輯。由 CBDB-Desktop 的開發者修正。

**本次執行狀態：** 已確認

#### 問題描述

入仕與地點兩個表單寫出的 KML，開頭一行是 `<?xml version="1.0" encoding="UTF-8">`。XML 宣告必須以 `?>` 結尾，這裡卻只有 `>`。因此任何 XML 解析器都會在第一行就拒絕整份文件，Google Earth、QGIS、ArcGIS 都打不開——而程式卻回報匯出成功。

#### 實測依據

以兩種互相獨立的方式各測一次。透過釋出的執行檔實際呼叫這兩個端點，取回的檔案開頭就是上述字串（`entry:kml/entry_gis_UTF8.kml` 與 `places:kml/places_export.kml`）；直接讀釋出的 Go 原始碼，也只找到這兩處寫法。因此與資料內容無關：任何輸入都是錯的。

#### 影響

程式的兩項地理匯出完全不可用，而且不會有任何提示。想把入仕或地點的地址繪成地圖的使用者，只會拿到一個 GIS 軟體打不開的檔案。

#### 復現步驟

1. 開啟入仕表單（/LookAtEntry），任選一個入仕代碼並執行查詢。
2. 按下 KML 並儲存檔案。
3. 用 Google Earth 開啟，或用任何 XML 解析器讀取：第一行即失敗。
4. 在地點表單（/LookAtPlace）重複一次，結果相同。

#### 建議修復方式

在兩處各補上缺少的 `?`，寫成 `<?xml version="1.0" encoding="UTF-8"?>`。建議同時檢查其餘的 KML 輸出處——它們目前是正確的，所以這裡只列出這兩處。

#### 對應的程式位置

- `Code/entry_form_backend.go:1006`
- `Code/places_form_backend.go:764`

#### 對應的測試

- 7 × 失敗: `test_an_export_produces_a_well_formed_file[entry:kml]`, `test_an_export_produces_a_well_formed_file[places:kml]`, `test_an_export_produces_a_well_formed_file[associations:neo4j]`, `test_an_export_produces_a_well_formed_file[networks:pajek]` (+3)
- 48 × 通過: `test_an_export_produces_a_well_formed_file[entry:results]`, `test_an_export_produces_a_well_formed_file[entry:gis]`, `test_an_export_produces_a_well_formed_file[entry:neo4j]`, `test_an_export_produces_a_well_formed_file[entry:save]` (+44)

## CBDB-D-002 — 地點頁面允許使用者取消勾選全部類別，然後回傳他們已排除的「傳記」資料

**涉及範圍：** 地點表單的類別勾選項

**嚴重等級：** P0 — 靜默的錯誤結果——程式回傳錯誤或空白的結果，或產生任何軟體都讀不了的檔案，而且沒有任何錯誤提示。

**問題來源：** `software` — 程式本身的問題：cbdb.exe、其 Go 原始碼、頁面模板，或資料庫建置程式的邏輯。由 CBDB-Desktop 的開發者修正。

**本次執行狀態：** 已確認

#### 問題描述

地點查詢的處理程式發現七個類別全部未勾選時，會自動改成 `IncludeBiog = true`。若只是為了避免空請求，這樣的保護尚屬合理；問題在於頁面允許使用者真的走到這個狀態。七個勾選框沒有「至少選一項」的限制，因此全部取消後按下查詢，回傳的是使用者明確排除掉的傳記地址，而且沒有任何提示。

#### 實測依據

本次量測使用的地址代碼是 20056——由測試套件從釋出資料中自行挑選，而非人工指定。七個類別全部取消勾選時，查詢回傳 396 列；把同一個請求改成只勾選「傳記」，回傳的也是同樣的 396 列——空選擇不只是「並非真的空」，而是恰好等於傳記那一支的結果。此結果是透過執行中的程式實測，之後在原始碼中看到對應的替換邏輯。

#### 影響

研究者以取消類別的方式縮小查詢範圍，卻拿到自己排除掉的類別的資料，並且被當成所提問題的答案。介面上沒有任何地方顯示選擇已被覆寫。

#### 復現步驟

1. 開啟地點表單（/LookAtPlace），選擇一個地址——上文量測使用的是地址代碼 20056。
2. 取消七個類別勾選框的全部勾選，包含「傳記」。
3. 按下執行查詢：仍有資料回傳。
4. 改為只勾選「傳記」再查一次：得到相同的資料、相同的列數。

#### 建議修復方式

兩種做法皆可：一是在頁面端拒絕空選擇（在至少勾選一項之前，讓「執行查詢」保持停用——正如這一版的關聯表單對其選取器所做的），二是對空選擇回傳零列並明確告知使用者。只要頁面不會再送出這種請求，伺服器端的預設值可以留著當作保護。

#### 對應的程式位置

- `Code/places_form_backend.go:205`
- `Templates/places/index.html:90`
- `Templates/places/index.html:540`

#### 對應的測試

- 1 × 失敗: `test_turning_every_category_off_returns_nothing`

## CBDB-D-003 — 二十二個匯出按鈕會一次要求瀏覽器儲存多個檔案，其中二十一個更在只有第一個檔案下載成功時，回報所有檔案都已儲存

**涉及範圍：** 十個表單頁面上的匯出按鈕

**嚴重等級：** P0 — 靜默的錯誤結果——程式回傳錯誤或空白的結果，或產生任何軟體都讀不了的檔案，而且沒有任何錯誤提示。

**問題來源：** `software` — 程式本身的問題：cbdb.exe、其 Go 原始碼、頁面模板，或資料庫建置程式的邏輯。由 CBDB-Desktop 的開發者修正。

**本次執行狀態：** 已確認

#### 問題描述

這些處理函式會走訪伺服器回傳的檔案清單，在單一次點擊中為每個項目各觸發一次下載。瀏覽器對每個使用者手勢只允許一次自動下載，其餘一律封鎖；而且一旦被封鎖，同一頁面之後的匯出也會受限——這正是第二次按下匯出時可能完全存不到檔案的原因。二十二個之中有二十一個接著印出的是「伺服器」回傳的數量（例如「2 file(s) ready」），從未詢問瀏覽器實際接受了幾個。

#### 實測依據

在釋出的模板中逐一計數：所有 10 個會匯出多個檔案的頁面共 22 處這樣的處理函式（association_pairs 4、associations 2、entry 2、group_data 3、kinship 2、networks 2、office 2、places 2、status 2、texts 1），其中 21 處會把伺服器端的數量當成實際結果回報（與上面相同，只少了 networks 的一處）。同一種迴圈在這些頁面裡有三種寫法，三種都已計入；若出現第四種，檢查會直接失敗，而不是讓這些數字悄悄變小。

伺服器端本身沒有問題：同樣的端點在重複請求下都會完整、一致地回傳每個檔案。在自動化環境中下載會被自動接受、每個檔案都會到齊，因此「被封鎖」這一半是透過閱讀頁面的下載程式碼確認的，並且來自實際使用時的回報；「數量回報錯誤」這一半則是在瀏覽器中實測的。

#### 影響

使用者按下匯出，被告知已備妥兩個或五個檔案，實際磁碟上只有一個。沒有到齊的檔案不會被列出，也沒有任何錯誤訊息可供追查。

#### 復現步驟

1. 開啟親屬表單，執行查詢，按下匯出結果。
2. 留意訊息：顯示已備妥三個檔案。
3. 檢查下載資料夾：只有一個檔案。
4. 再按一次匯出結果——在預設的瀏覽器設定下，這一次什麼也不會存下。

#### 建議修復方式

把多檔匯出改成單一次下載——通常做成 zip 壓縮檔即可，且不需要瀏覽器授權——或是每個使用者手勢只儲存一個檔案。無論採用哪種方式，回報的都應該是實際送達的內容，而不是回應中包含的數量。

#### 對應的程式位置

- `Templates/kinship/index.html:630`
- `Templates/association_pairs/index.html:936`
- `Templates/group_data/index.html:914`
- `Templates/entry/index.html:1093`
- `Templates/associations/index.html:680`
- `Templates/networks/index.html:1551`
- `Templates/places/index.html:691`
- `Templates/office/index.html:850`
- `Templates/status/index.html:795`
- `Templates/texts/index.html:823`

#### 對應的測試

- 1 × 失敗: `test_no_page_asks_the_browser_for_more_than_one_download`

## CBDB-D-004 — 網絡表單四個網絡匯出中有三個對任何輸入都回傳 HTTP 500：它們查詢了自己的暫存表所沒有的欄位

**涉及範圍：** 網絡表單的 Pajek、Gephi/GUESS 與 UCINet 匯出

**嚴重等級：** P2 — 可見的執行時錯誤——使用者的操作以伺服器錯誤收場。

**問題來源：** `software` — 程式本身的問題：cbdb.exe、其 Go 原始碼、頁面模板，或資料庫建置程式的邏輯。由 CBDB-Desktop 的開發者修正。

**本次執行狀態：** 已確認

#### 問題描述

三者都從 `ZZ_SN_NETWORK` 讀取 `c_node_dist`。這個表由同一個檔案建立，欄位清單中並沒有 `c_node_dist`，只有 `c_edge_dist` 與 `c_distance`。SQLite 因此拒絕該查詢，使得這三個按鈕對任何可能的查詢結果都失敗。相鄰的表單（關聯、關聯配對）確實有宣告 `c_node_dist`，這很可能就是欄位名稱的來源。

#### 實測依據

每個端點都回應 `500 Database error: no such column: c_node_dist`，即使在沒有任何資料可匯出的情況下也一樣——可見問題出在 SQL 敘述本身，而不是資料。另外獨立閱讀釋出的 Go 原始碼，也找到同樣的三段 SELECT 以及與之矛盾的 CREATE TABLE。

#### 影響

網絡表單是本程式的社會網絡分析工具，而它四種網絡格式中有三種完全無法產出檔案，只有 Neo4j 可用。

#### 復現步驟

1. 開啟網絡表單（/LookAtNetworks），選定一個人物並執行一次會回傳邊的查詢。
2. 按下 Pajek：請求回傳 HTTP 500。
3. 以 Gephi/GUESS 與 UCINet 重複，得到相同錯誤。
4. 按下 Neo4j：這一個可以正常產生檔案。

#### 建議修復方式

請先確定這三個匯出所指的「距離」究竟是什麼，然後改用對應的欄位——`ZZ_SN_NETWORK` 為每條邊所填入的是 `c_edge_dist`——或者在 CREATE TABLE 中加入 `c_node_dist` 並確實填值。若在建置階段對每個暫存表的宣告欄位做一次 `PRAGMA table_info` 檢查，就能提前發現這個問題，正如 `Code/qbe_schema_test.go` 對查詢建構器所做的那樣。

#### 對應的程式位置

- `Code/networks_form_backend.go:2093`
- `Code/networks_form_backend.go:2216`
- `Code/networks_form_backend.go:2341`
- `Code/networks_form_backend.go:419`

#### 對應的測試

- 34 × 失敗: `test_an_export_produces_a_well_formed_file[entry:kml]`, `test_an_export_produces_a_well_formed_file[places:kml]`, `test_an_export_produces_a_well_formed_file[associations:neo4j]`, `test_an_export_produces_a_well_formed_file[networks:pajek]` (+30)
- 308 × 通過: `test_an_export_produces_a_well_formed_file[entry:results]`, `test_an_export_produces_a_well_formed_file[entry:gis]`, `test_an_export_produces_a_well_formed_file[entry:neo4j]`, `test_an_export_produces_a_well_formed_file[entry:save]` (+304)
- 91 × 略過: `test_an_export_describes_the_people_the_grid_did[entry:kml]`, `test_an_export_describes_the_people_the_grid_did[entry:save]`, `test_an_export_describes_the_people_the_grid_did[office:gis]`, `test_an_export_describes_the_people_the_grid_did[office:gis-people]` (+87)

## CBDB-D-005 — 只要查詢結果帶有地址，關聯表單的 Neo4j 匯出就回傳 HTTP 500：程式把一個文字欄位讀進整數變數

**涉及範圍：** 關聯表單的 Neo4j 匯出

**嚴重等級：** P2 — 可見的執行時錯誤——使用者的操作以伺服器錯誤收場。

**問題來源：** `software` — 程式本身的問題：cbdb.exe、其 Go 原始碼、頁面模板，或資料庫建置程式的邏輯。由 CBDB-Desktop 的開發者修正。

**本次執行狀態：** 已確認

#### 問題描述

這個匯出把 `ADDR_CODES.c_admin_type` 讀進宣告為 `AdminType int` 的 Go 結構欄位。該欄位其實是文字：全部 30,100 列都存放像 "Xian"、"Zhou" 這樣的字串。因此第一列地址就讀取失敗，整個匯出回傳 HTTP 500。

#### 實測依據

端點回應 `500 Neo4j export error: scan addrRow: sql: Scan error on column index 3, name "admin_type": converting driver.Value type string ("Xian") to a int: invalid syntax`。釋出的結構描述把該欄位宣告為 `varchar(255)`；以唯讀方式統計釋出的資料庫，30,100 個值全部都是文字型別，最常見的是 "Xian"（13,687 列）。因此重建資料不會改變結果：問題在於 Go 結構中宣告的型別有誤。

#### 影響

只要查詢結果中的人物帶有地址（幾乎都會帶有），關聯表單就無法匯出到 Neo4j，使用者只會看到伺服器錯誤。

#### 復現步驟

1. 開啟關聯表單（/LookAtAssociations），選一個關聯代碼並執行查詢。
2. 按下 Neo4j。
3. 請求回傳 HTTP 500，錯誤訊息即為上述的讀取錯誤。

#### 建議修復方式

把該欄位宣告為 `string` 並以文字讀取；同一段 SELECT 中的 `COALESCE(c_admin_type, 0)` 也應一併改為 `COALESCE(c_admin_type, '')` 以相符。

同樣的錯誤在這一版中還有第二處，但不在別的 Neo4j 匯出裡——沒有其他匯出會讀這個欄位。那一處是 `networks_form_backend.go` 的 `handlePlaceSearch`：它同樣把 `COALESCE(c_admin_type, 0)` 讀進 `AdminType int`，而且在讀取失敗時直接 `continue`，因此任何搜尋都會回傳空清單，而不是回報錯誤。目前釋出的模板沒有任何地方會呼叫這個路由，這也是至今沒有使用者回報的原因；建議在同一次修改中一併處理，而不要留到某天真的有人用到它才被發現。

#### 對應的程式位置

- `Code/associations_form_backend.go:1377`
- `Code/associations_form_backend.go:1388`
- `Code/networks_form_backend.go:2987`
- `Data/cbdb.db.schema.sql:42`

#### 對應的測試

- 34 × 失敗: `test_an_export_produces_a_well_formed_file[entry:kml]`, `test_an_export_produces_a_well_formed_file[places:kml]`, `test_an_export_produces_a_well_formed_file[associations:neo4j]`, `test_an_export_produces_a_well_formed_file[networks:pajek]` (+30)
- 279 × 通過: `test_an_export_produces_a_well_formed_file[entry:results]`, `test_an_export_produces_a_well_formed_file[entry:gis]`, `test_an_export_produces_a_well_formed_file[entry:neo4j]`, `test_an_export_produces_a_well_formed_file[entry:save]` (+275)
- 109 × 略過: `test_an_export_describes_the_people_the_grid_did[entry:kml]`, `test_an_export_describes_the_people_the_grid_did[entry:save]`, `test_an_export_describes_the_people_the_grid_did[office:gis]`, `test_an_export_describes_the_people_the_grid_did[office:gis-people]` (+105)

## CBDB-D-006 — 查詢建構器提供了 30 個欄位，而釋出的檢視表其實是以另一個名稱呈現它們；每一個都會讓使用者得到伺服器錯誤

**涉及範圍：** 產生出來的查詢建構器結構檔，以及 CBDBSetUpCode 中的檢視表定義

**嚴重等級：** P2 — 可見的執行時錯誤——使用者的操作以伺服器錯誤收場。

**問題來源：** `software` — 程式本身的問題：cbdb.exe、其 Go 原始碼、頁面模板，或資料庫建置程式的邏輯。由 CBDB-Desktop 的開發者修正。

**本次執行狀態：** 已確認

#### 問題描述

釋出的檢視表中有八個，其 30 個欄位的名稱帶有 `:1` 後綴——例如 `c_personid:1`、`c_notes:1`、`c_dy:1` 等。這些名稱是 SQLite 自己產生的：這幾個檢視表都是層層嵌套的 Access 風格連接（join）結構，而所選欄位又沒有明確取別名。

介面提供的欄位清單來自 `Data/qbe_schema.json`，由 `gen_qbe_schema.py` 產生。這支腳本其實**知道這個問題**：它會偵測到重複名稱，只保留第一個並去掉後綴，同時印出警告，而且它自己的檔頭就寫著「真正的修法是在檢視表定義中加上明確的 AS 別名」。但它保留不帶後綴的名稱，是基於「SQLite 自己就是這樣解析對多個同名欄位的未限定參照」這個假設——而對這幾個檢視表來說，這個假設是錯的。真正可用的是帶後綴的名稱：`SELECT t."c_personid:1" FROM View_Entry t` 可以取回資料，而不帶後綴的 `SELECT t.c_personid FROM View_Entry t` 則被拒絕。也就是說，產生腳本把一個查得到的名稱換成了一個查不到的名稱；其中四個檢視表受影響的還是清單中的第一個欄位，整個表看起來就像完全不能用。

#### 實測依據

透過執行中的程式操作查詢建構器，全部 30 種組合都回應 `500 Query failed: no such column`；而對 View_BiogInstAddrData、View_BiogInstData、View_Entry 與 View_KinAddr 而言，那正是介面提供的第一個欄位。以唯讀方式讀取釋出的資料庫，`PRAGMA table_info` 回報的正是這 8 個檢視表中的這 30 個帶 `:1` 後綴的欄位。此命名僅由檢視表自己的 SELECT 即可重現；在該 SELECT 中加上明確的 `AS c_personid` 後，後綴消失，`SELECT t.c_personid` 也隨即成功——這同時指出了原因與修法。

#### 影響

使用者從程式自己提供的清單中挑選欄位，卻得到伺服器錯誤。其中四個檢視表因為第一個可選欄位就是這類欄位，看起來像是整個壞掉了。

#### 復現步驟

1. 開啟查詢建構器（/QBE）。
2. 選擇檢視表 View_Entry。
3. 選取它提供的第一個欄位 c_personid，然後執行。
4. 請求回傳 500 `no such column: t.c_personid`。
5. 在釋出的資料庫中執行 PRAGMA table_info(View_Entry)，可見該欄位的名稱其實是 `c_personid:1`。

#### 建議修復方式

`gen_qbe_schema.py` 自己的檔頭已經指出修法：在這八個檢視表定義中為衝突的欄位明確取別名（例如 `ENTRY_DATA.c_personid AS c_personid`）。這正是上文已驗證有效的修法——後綴會消失，`SELECT t.c_personid` 也隨即成功——而且能讓已產生的欄位清單維持正確。

在那之前，產生腳本不應輸出自己無法驗證的名稱。它的警告只在產生時印出一次，之後就再也沒人看到；若某個欄位名稱通不過 `SELECT t.<欄位> FROM <檢視表> t LIMIT 0`，那麼把它從 JSON 中略去，會比提供給使用者更好——而這項檢查在產生階段只需要每個欄位一次查詢的成本。另一種可行做法是輸出真正的、帶後綴的名稱，並在產生的 SQL 中加上引號——因為那才是能解析的名稱；但取別名仍是更好的修法，畢竟研究者看到的欄位標題不該帶著 `:1`。

#### 對應的程式位置

- `Data/gen_qbe_schema.py:52`
- `Data/qbe_schema.json:5456`
- `CBDBSetUpCode/CBDB_AdditionalTablesViewsIndices.sql:1254`
- `Code/qbe_schema.go:53`

#### 對應的測試

- 32 × 失敗: `test_every_offered_column_exists_in_the_database`, `test_every_offered_table_can_actually_be_queried`, `test_a_phantom_column_gives_the_user_a_server_error[View_BiogInstAddrData-c_personid]`, `test_a_phantom_column_gives_the_user_a_server_error[View_BiogInstAddrData-c_notes]` (+28)

## CBDB-D-007 — 發行檔中一併附上了十份帶日期的模板工作副本

**涉及範圍：** 封裝內容：Templates/

**嚴重等級：** P3 — 封裝問題——釋出的檔案裡含有不該出現的內容。

**問題來源：** `release` — 這一次釋出的組裝流程問題——例如把開發用的工作副本當成正式建置成果送出、某個檔案沒有重新產生。由負責建置發行檔的人在流程上修正。

**本次執行狀態：** 已確認

#### 問題描述

壓縮檔 85 個成員中有 10 個，是與正式檔案並存的帶日期模板備份——例如 `entry/entry.index.20260906.html` 與 `entry/index.html` 並列、`qbe/qbe.20260827.html` 與 `qbe/qbe.html` 並列等。沒有任何路由會提供這些檔案，且只有 `Static/` 是以檔案伺服方式對外，因此它們並不是可被存取的頁面；這是把工作目錄照原樣打包的結果。

#### 實測依據

以下清單讀自壓縮檔自身的目錄，而非解開後的目錄樹：`Templates/associations/associations.index.20260906.html`、`associations.index.20260908.html`、`entry/entry.index.20260906.html`、`networks/networks.index.20260813.html`、`office/office.index.20260815.html`、`pickers/address_picker.20260729.html`、`places/places.index.20260906.html`、`qbe/qbe.20260827.html`、`status/status.index.20260816.html`、`texts/texts.index.20260815.html`。把其中一份與其正式版本相比，可確認確實較舊：20260906 版的入仕頁面沒有 `chkUseXY` 這個控制項，而釋出的頁面有。

#### 影響

影響不大，但並非沒有影響。它使釋出的目錄樹難以判斷哪一份模板才是最新版本，也把未正式發行的工作狀態交到使用者手上；而且正是這類疏漏，最終可能讓過時的檔案「以正式檔案的身分」被釋出。在本次測試中，它同時造成三項測試失敗，因為本套件是依據建置內容自行列舉頁面與按鈕，而不是比對一份自備清單。

#### 復現步驟

1. 列出壓縮檔內容：7z l CBDB-Desktop_20260908.7z
2. 留意 Templates/ 之下十個名稱帶日期的成員。
3. 任選其中一個，與同目錄下的 index.html 進行比對。

#### 建議修復方式

請以乾淨的匯出結果來製作發行檔，而不要直接打包工作目錄；或在封裝時排除 `*.<日期>.html`。這些備份本身有其用處，只是它們該放在版本控制中，而不是發行檔裡。

#### 對應的程式位置

- `Templates/pickers/address_picker.20260729.html`
- `Templates/qbe/qbe.20260827.html`
- `Templates/entry/entry.index.20260906.html`

#### 對應的測試

- 4 × 失敗: `test_distribution_ships_the_expected_pieces`, `test_the_distribution_ships_no_dated_working_copies`, `test_every_disabled_control_has_a_declared_precondition`, `test_every_page_has_the_buttons_it_shipped_with`

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

這道指令會解開壓縮檔、以釋出資料庫的私有複本啟動釋出的執行檔、執行 1099 項測試，並重新產生這幾份檔案。測試套件不會寫入作為對照基準的 `Data/CBDB.db`——每次執行都使用各自的複本，因此跑完之後，發行檔與執行前完全相同。

每一項問題底下都列出了對應的測試名稱。若只想執行其中一項：

```powershell
python -m pytest tests -k test_searching_people_by_name_finds_them -v
```


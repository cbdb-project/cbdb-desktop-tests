# CBDB-Desktop —— 問題彙報

_自動化迴歸測試過程中發現的問題彙總，謹呈維護團隊斧正。_

_受測版本：CBDB-Desktop_20260925.7z_

_本報告產生於 2026-09-30 11:02 UTC，依據一次 1381 項測試的執行結果（耗時 507 秒）。_

尊敬的維護者：

以下是我們在為 CBDB-Desktop 編寫自動化迴歸測試套件的過程中，陸續整理出來的問題清單。我們希望這份報告能在您繼續主持這份寶貴資料集時有所助益；同時，對您多年來在這套資料與程式上的辛勤付出，我們由衷表示感謝與敬意。

以下的問題，多數是實際啟動釋出的 `cbdb.exe`、以它自己的 HTTP 介面搭配釋出的資料庫實測出來的；其餘則是直接閱讀釋出的頁面模板、Go 原始碼與發行壓縮檔而確認的——對於根本不需要查詢就能證明的問題，這才是誠實的說法。無論是哪一種，我們都沒有用 Python 重寫任何應用邏輯，因此這裡描述的就是釋出程式的真實行為。

各條目所標示的級別，既是輕重也是類別：P0 至 P2 確實由重到輕，但 P3 以後標示的是類別——封裝、資料完整性、沒有任何入口的功能——因此 P5 並不比 P3 輕微；各級別的意義均隨附說明。每一條都包含：簡要說明、據以認定的實測數據、逐步復現方式，以及一份建議的修復方案。

我們無意代為排定優先順序：這些級別描述的是我們量測到的情況，而不是您的使用者正在反映的需求，孰輕孰重，您遠比我們更有判斷的立場。其中有幾項是「靜默」的——程式給出錯誤或不完整的結果，卻沒有顯示任何錯誤——凡屬此類我們都已明白標示，因為這種問題最容易被忽略，事後也最難察覺。這裡沒有任何一項需要今天就回覆。

## 本次執行結果

| 結果 | 數量 |
| --- | --- |
| 通過 | 1190 |
| 失敗 | 6 |
| 預期失敗（已豁免的結果，仍然存在） | 2 |
| 略過 | 183 |

6 項失敗全部都是用來證明下列問題的測試。

## 測試套件的涵蓋範圍

| 範圍 | 測試數 | 檢查內容 |
| --- | --- | --- |
| 發行檔本身 | 63 | 受測的檔案樹確實逐一符合釋出的壓縮檔 |
| 應用程式行程 | 13 | 釋出的執行檔能啟動、能服務、並能釋放資料庫 |
| 所有已註冊的路由 | 17 | 從釋出的 Go 原始碼讀出的每一條路由，逐一實測 |
| 在表單之間傳遞查詢結果 | 22 | 已儲存人物清單：一個表單存入的，另一個表單取回的 |
| 各頁面與其後端的對照 | 18 | 表單的前後兩半對於請求與回應是否一致——後端從不讀取的控制項、頁面讀不懂的回應、沒有任何入口的功能 |
| 各頁面的 JavaScript 是否還能解析 | 30 | 表單把全部行為都放在單一的內嵌 script 裡，因此只要其中有一處語法錯誤，整頁的控制項就全部失效，而頁面本身照樣載入——這項檢查直接讀釋出的模板，不需要瀏覽器 |
| 代碼與地址清單 | 38 | 各表單在查詢前提供的下拉選單 |
| 分群資料表單 | 7 | 五個區段開關逐一單獨驅動，以及全部關閉時它回傳什麼 |
| 入仕途徑與社會地位的選擇視窗 | 4 | 它們的類型樹：所提供的每個類型底下是否都有代碼，以及所指的每個上層類型是否真的存在 |
| 網絡表單的各項篩選 | 11 | 親屬與非親屬開關、性別篩選，以及每一個「確實有選取作用」的關聯類別，逐一單獨驅動 |
| 查詢建構器的格線，逐格檢查 | 34 | 十一種運算子、四種彙總函數、排序列、連接方式，以及遇到無法剖析的儲存格時的行為 |
| 查詢建構器 | 21 | 白名單、顯示給使用者的 SQL，以及各項防護 |
| 六個單次查詢的表單 | 57 | 入仕、官職、社會地位、著述、社會關係、地點——查詢與匯出 |
| 具狀態的表單 | 19 | 親屬關係、社會網路、關係配對、群組資料——工作清單 |
| 索引地址排序 | 12 | 唯一會改寫 CBDB 正式資料（而非暫存表）的端點 |
| 每一個篩選條件，輸入取自資料本身 | 420 | 依釋出資料庫中實際有資料的組合各跑一次查詢，並將每個開關的兩種狀態都測過 |
| 所有匯出按鈕 | 503 | 每個會產生檔案的端點都按過，並回讀所得檔案 |
| 在真實瀏覽器中的頁面 | 12 | 每個頁面載入時不拋錯；等待使用者操作的控制項在條件滿足後確實解除停用 |
| 同時開兩個分頁 | 3 | 一次查詢是否會取代另一個分頁即將匯出的內容 |
| 暫存工作表 | 7 | 各表單各自擁有哪些暫存表——從釋出的 Go 原始碼讀出並釘住 |
| 本次執行自身的覆蓋率 | 5 | 釋出頁面能觸及的每一個端點，本次執行是否真的都請求過 |
| 已協商擱置的項目 | 28 | 每一條擱置項目是否仍對應到本次執行中存在的檢查，以及套件中沒有其他地方私自容忍失敗 |
| 本報告自身的依據 | 10 | 以下每一項問題所引用的程式位置仍然存在，且中英文皆已填寫 |
| 本報告本身 | 27 | 本報告可由上述執行結果完整重現，不會憑空產生問題、不會遺漏問題，也不會隱藏任何擱置項目 |
| 本次執行的全部測試 | 1381 |  |

### 本次執行尚未涵蓋的部分

上表統計的是「已檢查的項目」，並不是應用程式功能的清單。某項功能可能只因為其中一個狹窄的面向受到檢查而列於表中——例如某個按鈕是否在該解除停用時解除停用——而該按鈕實際產生的內容卻從未被讀取。若這一版新增的功能有這種情形，下方對應的問題條目會自行說明。請把表中的每一列讀作「檢查到這個程度」，而未列出的項目則代表完全未檢查。

## 已協商暫時擱置的項目

以下項目均為已知情形，並已協商暫時維持現狀。列於此處是為了避免任何問題被無聲地忽略：每一項都指明了對應的檢查名稱，隨時可以重新處理。

| 對應檢查 | 適用範圍 | 處理方式 | 協商紀錄 | 有效期至 | 原因 |
| --- | --- | --- | --- | --- | --- |
| test_a_second_query_replaces_what_the_first_would_export | 全部情況 | 仍然檢查，失敗予以容忍 | 2026-09-09 (maintainer) | 未設期限 | 已協商暫時維持現狀：暫存表每個資料庫只有一組，因此在第二個分頁執行查詢，會取代第一個分頁即將匯出的內容。若要改成依工作階段（session）劃分命名空間，等於重新設計所有表單儲存工作狀態的方式；而這一版的使用者一次只會開一個視窗作業。 |
| test_a_second_working_list_replaces_the_first | 全部情況 | 仍然檢查，失敗予以容忍 | 2026-09-09 (maintainer) | 未設期限 | 同一項協商，發生在更早的一步：同一個表單的兩個分頁共用一份工作清單，因此第二次匯入會取代第一次，接下來的查詢對象也就換成了另一批人。基於同樣的理由暫時維持現狀。 |

## 問題總覽

| 編號 | 等級 | 本次執行狀態 | 問題 |
| --- | --- | --- | --- |
| CBDB-D-001 | P0 | 已確認 | 在人物瀏覽中開啟某人的「親屬關係」分頁，會取代親屬表單的查詢結果：之後「匯出查詢結果」匯出的是另一個人的親屬網絡，「儲存人物ID」也會把另一個人加進儲存清單 |
| CBDB-D-002 | P0 | 已確認 | 地點表單的「以ASCII（拼音）而非Unicode匯出」核取方塊，對「保存到GIS」與「保存到KML」完全沒有作用 |
| CBDB-D-003 | P5 | 已確認 | 地點表單的 Pajek、Gephi/GUESS 與 UCINet 匯出已經實作，但頁面上沒有任何控制項會呼叫它們 |

## 目錄

- [CBDB-D-001 — 在人物瀏覽中開啟某人的「親屬關係」分頁，會取代親屬表單的查詢結果：之後「匯出查詢結果」匯出的是另一個人的親屬網絡，「儲存人物ID」也會把另一個人加進儲存清單](#cbdb-d-001--在人物瀏覽中開啟某人的「親屬關係」分頁，會取代親屬表單的查詢結果：之後「匯出查詢結果」匯出的是另一個人的親屬網絡，「儲存人物id」也會把另一個人加進儲存清單)
- [CBDB-D-002 — 地點表單的「以ASCII（拼音）而非Unicode匯出」核取方塊，對「保存到GIS」與「保存到KML」完全沒有作用](#cbdb-d-002--地點表單的「以ascii（拼音）而非unicode匯出」核取方塊，對「保存到gis」與「保存到kml」完全沒有作用)
- [CBDB-D-003 — 地點表單的 Pajek、Gephi/GUESS 與 UCINet 匯出已經實作，但頁面上沒有任何控制項會呼叫它們](#cbdb-d-003--地點表單的-pajek、gephiguess-與-ucinet-匯出已經實作，但頁面上沒有任何控制項會呼叫它們)
- [嚴重等級說明](#嚴重等級說明)
- [如何重現這份報告](#如何重現這份報告)

## CBDB-D-001 — 在人物瀏覽中開啟某人的「親屬關係」分頁，會取代親屬表單的查詢結果：之後「匯出查詢結果」匯出的是另一個人的親屬網絡，「儲存人物ID」也會把另一個人加進儲存清單

**涉及範圍：** 人物瀏覽（/CBDB_Browser）與親屬表單（/LookAtKinship）

**嚴重等級：** P0 — 靜默的錯誤結果——程式回傳錯誤或空白的結果，或產生任何軟體都讀不了的檔案，而且沒有任何錯誤提示。

**問題來源：** `software` — 程式本身的問題：cbdb.exe、其 Go 原始碼、頁面模板，或資料庫建置程式的邏輯。由 CBDB-Desktop 的開發者修正。

**本次執行狀態：** 已確認

#### 問題描述

人物瀏覽的「親屬關係」分頁會呼叫 `GET /api/browser/person/{id}/kinship`，而 `handleGetKinship` 一開始就刪除 `ZZ_KIN_LIST`、`ZZ_KIN_LIST_TMP`、`ZZ_SCRATCH_KIN` 與 `ZZ_SCRATCH_KINNET`，再寫入它自己的親屬走訪結果。這四張暫存表正是親屬表單查詢留下答案的地方，而親屬表單有兩個按鈕是從這些表讀回資料，而不是使用頁面上顯示的內容：

- **匯出查詢結果**（`handleExportResults`）讀取 `ZZ_SCRATCH_KINNET` 與 `ZZ_SCRATCH_KIN`，因此匯出的是人物瀏覽中那個人的網絡。而且只換掉了一半：第三個檔案 `KinshipPeople.tsv` 讀自 `ZZ_SP_KINSHIP`，人物瀏覽不會動到這張表，所以壓縮檔同時描述了兩個不同的人。
- **儲存人物 ID**（`doStorePersonIDsConfirmed`）從 `ZZ_SP_KINSHIP` 取親屬、從 `ZZ_SCRATCH_KIN` 取中心人物，因此儲存清單——也就是查詢結果傳往其他所有表單的管道——會多出人物瀏覽中的那個人。

從人物瀏覽頁面有兩條路會觸發：按下「親屬關係」分頁，以及「匯出人物檔案」（Export Profile）——後者會載入所有尚未快取的分頁，包括親屬關係，即使使用者從未打開過它。整個過程中親屬頁面仍顯示原本的結果，兩個頁面都沒有任何訊息說明內容已改變。頁面自己在「匯出查詢結果」旁的註解寫著，匯出「永遠正好反映上一次查詢寫入這些表的內容」；人物瀏覽是這段註解沒有考慮到的第二個寫入者。

#### 實測依據

兩個部分都透過實際執行的程式驗證。`test_looking_a_person_up_does_not_discard_a_kinship_result`：先對人物 1 執行親屬查詢，再呼叫 `GET /api/browser/person/10/kinship`，然後按「匯出查詢結果」——回應 HTTP 200，得到的 `KinshipResults.zip` 中 `EgoRelativeKinship.tsv` 由 920 字元變為 9,795 字元，`KinshipNetwork.tsv` 由 1,067 變為 295，而 `KinshipPeople.tsv` 與原本相同。對人物 1 重新查詢仍回傳 6 筆 kinRecords，可見結果是被取代，而不是損壞。`test_looking_a_person_up_does_not_change_what_kinship_stores`：同一份結果，查看前「儲存人物ID」存了 6 人，查看後存了 7 人——多了人物 10，沒有人被移除。

從原始碼讀出的部分：`handleGetKinship` 開頭的四個 `DELETE`；`doStorePersonIDsConfirmed` 讀取的兩張表；人物瀏覽頁面上的 `loadTabKinship`，`EXPORT_TABS` 把它列為「匯出人物檔案」（Export Profile）的親屬載入函式（`test_export_profile_loads_the_kinship_tab_it_lists`）。親屬查詢自己的清除步驟註解寫著「add ZZ_SP_KINSHIP vs browser」——親屬查詢清除人物瀏覽也在用的那幾張表，再加上它不用的這一張，可見開發者知道另外四張是與人物瀏覽共用的。親屬表單的其他五種匯出是用頁面傳來的資料列產生，不受影響。

#### 影響

研究者若在執行親屬查詢之後、使用結果之前，到人物瀏覽查看了某個人，就會在沒有任何錯誤、兩個頁面也看不出跡象的情況下，得到一份描述另一個人親屬、卻拼上第一個人人物清單的匯出檔，或是一份多了一個人的儲存清單，並被帶進下一個調用它的表單。這個操作順序一點也不特別——在人物瀏覽中查看某位親屬正是這個頁面的用途——而兩種結果看起來都合理，因此很可能被直接拿去使用。嚴重度列為中而非高，是因為必須恰好走過這個順序，而且畫面上的表格本身仍是正確的。

#### 復現步驟

1. 開啟親屬表單，選擇一位人物並按「執行查詢」，記下結果。
2. 在另一個分頁開啟人物瀏覽，查詢另一位人物，並按「親屬關係」分頁（或「匯出人物檔案」（Export Profile））。
3. 回到親屬表單——畫面仍顯示第一個人的結果——按「匯出查詢結果」。解壓縮 KinshipResults.zip：KinshipNetwork.tsv 與 EgoRelativeKinship.tsv 描述的是第二個人；KinshipPeople.tsv 描述的仍是第一個人。
4. 按「儲存人物ID」，再到任何其他表單按「調取ID」：第二個人也在調用進來的人物之中。

#### 建議修復方式

讓人物瀏覽擁有自己的親屬暫存表（每個表單本來就各有一套），或讓 `handleGetKinship` 在計算親屬走訪時不寫入親屬表單的暫存表。這樣兩個按鈕都會一併修好。若只把「匯出查詢結果」改為匯出頁面手上的資料列（另外五種匯出就是這樣做），能修好匯出，但「儲存人物ID」的問題仍然存在。

#### 對應的程式位置

- `Code/browser_form_backend.go:handleGetKinship (the four DELETEs at its top)`
- `Code/kinship_form_backend.go:handleExportResults (reads ZZ_SCRATCH_KINNET and ZZ_SCRATCH_KIN back, and ZZ_SP_KINSHIP)`
- `Code/kinship_form_backend.go:doStorePersonIDsConfirmed (kin from ZZ_SP_KINSHIP, ego from ZZ_SCRATCH_KIN)`
- `Templates/browser/index.html:1724 (loadTabKinship)`
- `Templates/browser/index.html:182 (EXPORT_TABS, which Export Profile walks)`

#### 對應的測試

- 2 × 失敗: `test_looking_a_person_up_does_not_discard_a_kinship_result`, `test_looking_a_person_up_does_not_change_what_kinship_stores`

## CBDB-D-002 — 地點表單的「以ASCII（拼音）而非Unicode匯出」核取方塊，對「保存到GIS」與「保存到KML」完全沒有作用

**涉及範圍：** 地點表單（/LookAtPlace）的「保存到GIS」與「保存到KML」兩種匯出

**嚴重等級：** P0 — 靜默的錯誤結果——程式回傳錯誤或空白的結果，或產生任何軟體都讀不了的檔案，而且沒有任何錯誤提示。

**問題來源：** `software` — 程式本身的問題：cbdb.exe、其 Go 原始碼、頁面模板，或資料庫建置程式的邏輯。由 CBDB-Desktop 的開發者修正。

**本次執行狀態：** 已確認

#### 問題描述

地點表單在這個核取方塊旁的每一種匯出中，都會把它以 `encoding: "ascii"` 傳給後端（`getExportEncoding`）。這三個按鈕中，「導出Neo4j CSV」有遵照，另外兩個沒有：`handleExportGIS` 解析了 `Encoding` 卻從未讀取，兩個寫檔函式不論要求為何都會寫入中文欄位——`writePlaceTab` 把每個 `*Chn` 欄位與其拼音欄位並列寫出，`writePlaceKML` 則把 `NameChn` 寫進每個地標的說明。使用者勾選後按「保存到GIS」或「保存到KML」，拿到的是與 Unicode 版本逐位元組相同的檔案，而且沒有任何提示。

同一表單的 Gephi 匯出只遵照了一部分：邊的標籤改為拼音，節點標籤仍是 `NameChn`。這個版本沒有任何按鈕能觸發該匯出（見 CBDB-D-003）；一併記錄在這裡，免得日後接上按鈕時帶著同樣的問題上線。

#### 實測依據

`test_an_export_asked_for_ascii_contains_only_ascii` 送出兩筆每個中文欄位都有 ASCII 拼音對應的資料，分別以 `encoding=unicode` 與 `encoding=ascii` 各送一次，並略過檔首的位元組順序標記後讀取檔案。以 ascii 送出時：`places:gis` 得到的 `places_export.tsv` 有 72 個大於 0x7F 的位元組，`places:kml` 得到的 `places_export.kml` 有 18 個——兩者都與 unicode 版本逐位元組相同。`places:gephi` 得到的 `network_ascii.gdf` 有 42 個，與它的 unicode 檔案不同。`places:neo4j` 與 `places:pajek` 通過（標記之後全為 ASCII）；`places:ucinet` 兩種模式都不寫入中文，無從判斷。

#### 影響

這個核取方塊是為了 GIS 或地圖工具無法讀取中文的使用者而設，而它恰恰對這兩種檔案不起作用。使用者明明要求不要中文，拿到的卻是 Unicode 名稱，檔案看起來又像是他們要的那一份，唯一的跡象是之後工具顯示出一堆亂碼。嚴重度列為中：對沒有勾選的人而言檔案並沒有錯，而且 Neo4j 匯出確實有遵照。

#### 復現步驟

1. 開啟地點表單，執行任何會回傳中文名稱的查詢。
2. 勾選「以ASCII（拼音）而非Unicode匯出」。
3. 按「保存到KML」，再另外按「保存到GIS」。
4. 打開任一檔案：中文仍在其中——KML 在每個地標的說明裡，GIS 檔在各個 *Chn 欄位——而且與沒有勾選時存下的檔案完全相同。

#### 建議修復方式

在 `handleExportGIS` 中讀取 `Encoding` 並傳給兩個寫檔函式，ascii 模式下不寫入中文，就像 `buildPlaceNeo4jFiles` 已經做的那樣：`writePlaceTab` 省略或清空各個 `*Chn` 欄位，`writePlaceKML` 不把 `NameChn` 寫進說明。在 `handleExportGephi` 中，ascii 模式下以 `n.NamePY` 作為節點標籤，與它的邊標籤一致。

#### 對應的程式位置

- `Code/places_form_backend.go:handleExportGIS (decodes Encoding, never reads it)`
- `Code/places_form_backend.go:writePlaceTab (every *Chn column beside its pinyin twin)`
- `Code/places_form_backend.go:writePlaceKML (NameChn in the placemark description)`
- `Code/places_form_backend.go:handleExportGephi (NameChn as the node label in both modes)`
- `Templates/places/index.html:727 (getExportEncoding)`

#### 對應的測試

- 3 × 失敗: `test_an_export_asked_for_ascii_contains_only_ascii[places:gis]`, `test_an_export_asked_for_ascii_contains_only_ascii[places:kml]`, `test_an_export_asked_for_ascii_contains_only_ascii[places:gephi]`
- 2 × 通過: `test_an_export_asked_for_ascii_contains_only_ascii[places:neo4j]`, `test_an_export_asked_for_ascii_contains_only_ascii[places:pajek]`
- 1 × 略過: `test_an_export_asked_for_ascii_contains_only_ascii[places:ucinet]`

## CBDB-D-003 — 地點表單的 Pajek、Gephi/GUESS 與 UCINet 匯出已經實作，但頁面上沒有任何控制項會呼叫它們

**涉及範圍：** 地點表單（/LookAtPlace）的 Pajek、Gephi/GUESS 與 UCINet 三種網絡匯出

**嚴重等級：** P5 — 無法觸及的功能——程式實作了某項功能，卻沒有任何頁面可以呼叫它。這個級別只說明「沒有任何使用者到得了」。至於背後的程式碼是否正確，是另一個問題、也有另一個答案；因此一項既到不了、本身又有錯的功能會在兩處分別記錄，而不是在同一處爭論該算哪一種。

**問題來源：** `software` — 程式本身的問題：cbdb.exe、其 Go 原始碼、頁面模板，或資料庫建置程式的邏輯。由 CBDB-Desktop 的開發者修正。

**本次執行狀態：** 已確認

#### 問題描述

地點表單頁面定義了 `exportPajek`、`exportGephi` 與 `exportUCINet`，各自把查詢結果與 ASCII 選項送到對應的端點並下載回應，三個後端處理函式也都有路由、能夠回應。但頁面上沒有任何東西會呼叫這三個函式：它的按鈕只有執行查詢、儲存人物ID、導出查詢結果、保存到KML、保存到GIS 與導出Neo4j CSV，也沒有任何事件監聽或載入時執行的程式碼呼叫它們。因此這三種網絡匯出——其他網絡類表單都有提供的格式——前後端都已存在，卻沒有使用者到得了。至於輸出是否正確是另一個問題：Gephi 匯出在 ASCII 模式下仍保留中文節點標籤（見 CBDB-D-002）。

#### 實測依據

`test_every_endpoint_a_page_calls_is_reachable_from_something_a_user_does` 從每個頁面上所有可能執行的地方出發——按鈕、每個行內 `on...=` 處理函式、載入時執行的程式碼、以名稱註冊的事件監聽，以及彈出視窗回呼的 `window.X`——沿著頁面的呼叫關係走訪。在這個版本的所有頁面中，只有這三個端點是頁面提到、卻走訪不到的。純文字的普查（`test_every_api_endpoint_the_build_routes_has_a_page_that_calls_it`）把它們算作「有呼叫」，因為 fetch 確實寫在頁面裡，只是位於沒有任何東西會執行的函式中。

#### 影響

在地點表單中工作的研究者，無法產生其他網絡類表單都能產生的 Pajek、Gephi 或 UCINet 檔案，頁面上也沒有任何跡象顯示這項功能存在。這不會給出錯誤的結果，只是功能到不了。

#### 復現步驟

1. 開啟地點表單，執行一個有結果的查詢。
2. 尋找 Pajek、Gephi/GUESS 或 UCINet 匯出：一個都沒有，儘管頁面程式碼中定義了 exportPajek、exportGephi 與 exportUCINet。

#### 建議修復方式

補上這三個函式原本要搭配的按鈕（親屬與網絡頁面都有），或者若地點表單本來就不打算提供這些格式，就刪除這些函式與後端處理函式。接上 Gephi 之前，請先修正它的 ASCII 標籤問題（CBDB-D-002）。

#### 對應的程式位置

- `Templates/places/index.html:825 (exportUCINet, called by nothing)`
- `Templates/places/index.html:842 (exportPajek, called by nothing)`
- `Templates/places/index.html:859 (exportGephi, called by nothing)`
- `Templates/places/index.html:92 (the page's action buttons)`

#### 對應的測試

- 1 × 失敗: `test_every_endpoint_a_page_calls_is_reachable_from_something_a_user_does`

## 嚴重等級說明

- **P0** — 靜默的錯誤結果——程式回傳錯誤或空白的結果，或產生任何軟體都讀不了的檔案，而且沒有任何錯誤提示。
- **P1** — 破壞性寫入——一次請求改寫了本不該改寫的既存資料，原本的狀態無法復原。
- **P2** — 可見的失敗——使用者的操作以他看得到的錯誤收場。多半是伺服器錯誤，有時則是頁面把一次其實已經成功的請求回報為失敗。這個級別看的是使用者看到什麼，而不是程式的哪一半出了問題。
- **P3** — 封裝問題——釋出的檔案裡含有不該出現的內容，或缺少了應該有的內容。
- **P4** — 資料完整性——釋出資料中存在無法解析的參照。
- **P5** — 無法觸及的功能——程式實作了某項功能，卻沒有任何頁面可以呼叫它。這個級別只說明「沒有任何使用者到得了」。至於背後的程式碼是否正確，是另一個問題、也有另一個答案；因此一項既到不了、本身又有錯的功能會在兩處分別記錄，而不是在同一處爭論該算哪一種。

## 如何重現這份報告

整份報告由一道指令產生。只要在 `.env` 中以 `CBDB_DESKTOP_ZIP` 指定發行壓縮檔：

```powershell
.\run_tests.ps1
```

這道指令會解開壓縮檔、以釋出資料庫的私有複本啟動釋出的執行檔、執行 1381 項測試，並重新產生這幾份檔案。測試套件不會寫入作為對照基準的 `Data/CBDB.db`——每次執行都使用各自的複本，因此跑完之後，發行檔與執行前完全相同。

每一項問題底下都列出了對應的測試名稱。若只想執行其中一項：

```powershell
python -m pytest tests -k test_searching_people_by_name_finds_them -v
```


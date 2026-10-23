# CBDB-Desktop —— 問題彙報

_自動化迴歸測試過程中發現的問題彙總，謹呈維護團隊斧正。_

_受測版本：CBDB-Desktop_20261021.7z_

_本報告產生於 2026-10-22 10:55 UTC，依據一次 1535 項測試的執行結果（耗時 509 秒）。_

尊敬的維護者：

以下是我們在為 CBDB-Desktop 編寫自動化迴歸測試套件的過程中，陸續整理出來的問題清單。我們希望這份報告能在您繼續主持這份寶貴資料集時有所助益；同時，對您多年來在這套資料與程式上的辛勤付出，我們由衷表示感謝與敬意。

以下的問題，多數是實際啟動釋出的 `cbdb.exe`、以它自己的 HTTP 介面搭配釋出的資料庫實測出來的；其餘則是直接閱讀釋出的頁面模板、Go 原始碼與發行壓縮檔而確認的——對於根本不需要查詢就能證明的問題，這才是誠實的說法。無論是哪一種，我們都沒有用 Python 重寫任何應用邏輯，因此這裡描述的就是釋出程式的真實行為。

各條目所標示的級別，既是輕重也是類別：P0 至 P2 確實由重到輕，但 P3 以後標示的是類別——封裝、資料完整性、沒有任何入口的功能——因此 P5 並不比 P3 輕微；各級別的意義均隨附說明。每一條都包含：簡要說明、據以認定的實測數據、逐步復現方式，以及一份建議的修復方案。

我們無意代為排定優先順序：這些級別描述的是我們量測到的情況，而不是您的使用者正在反映的需求，孰輕孰重，您遠比我們更有判斷的立場。其中有幾項是「靜默」的——程式給出錯誤或不完整的結果，卻沒有顯示任何錯誤——凡屬此類我們都已明白標示，因為這種問題最容易被忽略，事後也最難察覺。這裡沒有任何一項需要今天就回覆。

## 本次執行結果

| 結果 | 數量 |
| --- | --- |
| 通過 | 1317 |
| 失敗 | 35 |
| 預期失敗（已協商暫時擱置） | 2 |
| 略過 | 181 |

在 35 項失敗中，有 **31** 項是用來證明下列問題的測試——這些問題正是由它們認定的，問題修好之後它們就會恢復通過。其餘 **4** 項在下方逐一交代，以免讀者拿這些數字去對照問題清單，卻發現兩邊對不起來。

其中 **3** 項屬於本測試套件自身的問題，而不是釋出版本的缺陷：可能是介面上有、但我們尚未驅動過的東西，也可能是我們自己的作業流程出了紕漏。那部分該由我們補上，與您無關。

| 對應檢查 | 它指出我們這邊的什麼問題 |
| --- | --- |
| `test_every_finding_this_run_raises_is_accounted_for` | 上一次執行中有一項發現既未登錄也未列入豁免；同樣是我們自己的作業問題，列於此處是為了讓下方的數字仍然對得起來（6 test(s) raised a finding that no registry entry names and no waiver covers） |
| `test_the_committed_report_still_says_what_the_registry_says` | 已提交的報告比登錄表舊——條目變更後沒有重新產生報告，這是我們自己的作業疏漏，與版本無關（reports/CBDB_Desktop_Issues_EN.md no longer says what the registry says -- the registry was edited after the report was generated, or the report was edited by hand. Missing: ['CBDB-D-001.title', 'CBD） |
| `test_the_committed_report_still_says_what_the_registry_says` | 已提交的報告比登錄表舊——條目變更後沒有重新產生報告，這是我們自己的作業疏漏，與版本無關（reports/CBDB_Desktop_Issues_ZH-Hant.md no longer says what the registry says -- the registry was edited after the report was generated, or the report was edited by hand. Missing: ['CBDB-D-001.title',） |

**本次執行有 1 項失敗尚未歸類。**它們既不屬於下列問題，也不屬於我們已知的覆蓋缺口——換句話說，這次執行發現了還沒有人看過的東西。它們可能是值得立案的缺陷，也可能是檢查本身的問題；請務必逐一閱讀，不要把下面的清單當成已經完整。

| 對應檢查 | 回報的內容 |
| --- | --- |
| `test_the_coverage_table_describes_every_test_file_in_the_suite` | the coverage table and the suite disagree. Missing: ['test_build_provenance.py', 'test_release_notes.py', 'test_translations.py']; describing files that no longer exist: [] |

## 測試套件的涵蓋範圍

| 範圍 | 測試數 | 檢查內容 |
| --- | --- | --- |
| 發行檔本身 | 63 | 受測的檔案樹確實逐一符合釋出的壓縮檔 |
| 應用程式行程 | 13 | 釋出的執行檔能啟動、能服務、並能釋放資料庫 |
| 所有已註冊的路由 | 17 | 從釋出的 Go 原始碼讀出的每一條路由，逐一實測 |
| 在表單之間傳遞查詢結果 | 21 | 已儲存人物清單：一個表單存入的，另一個表單取回的 |
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
| 所有匯出按鈕 | 498 | 每個會產生檔案的端點都按過，並回讀所得檔案 |
| 在真實瀏覽器中的頁面 | 20 | 每個頁面載入時不拋錯；等待使用者操作的控制項在條件滿足後確實解除停用 |
| 英文、繁體與簡體標籤 | 102 | 從模板與畫面兩處檢查每個翻譯標籤：三種語言齊全、中文各用其字體，並與 CBDB 標籤對照表及其他表單一致 |
| 隨附的原始碼 | 19 | Code/ 中隨附的 Go 原始碼確實是隨附 cbdb.exe 的原始碼 |
| 開發者的修訂說明 | 8 | 隨附於檔案樹旁的說明文件忠實地轉成 Markdown，而且每次結果相同 |
| 同時開兩個分頁 | 3 | 一次查詢是否會取代另一個分頁即將匯出的內容 |
| 暫存工作表 | 7 | 各表單各自擁有哪些暫存表——從釋出的 Go 原始碼讀出並釘住 |
| 本次執行自身的覆蓋率 | 5 | 釋出頁面能觸及的每一個端點，本次執行是否真的都請求過 |
| 已協商擱置的項目 | 28 | 每一條擱置項目是否仍對應到本次執行中存在的檢查，以及套件中沒有其他地方私自容忍失敗 |
| 本報告自身的依據 | 25 | 以下每一項問題所引用的程式位置仍然存在，且中英文皆已填寫 |
| 本報告本身 | 35 | 本報告可由上述執行結果完整重現，不會憑空產生問題、也不會遺漏任何未經協商擱置的問題 |
| 本次執行的全部測試 | 1535 |  |

### 本次執行尚未涵蓋的部分

上表統計的是「已檢查的項目」，並不是應用程式功能的清單。某項功能可能只因為其中一個狹窄的面向受到檢查而列於表中——例如某個按鈕是否在該解除停用時解除停用——而該按鈕實際產生的內容卻從未被讀取。若這一版新增的功能有這種情形，下方對應的問題條目會自行說明。請把表中的每一列讀作「檢查到這個程度」，而未列出的項目則代表完全未檢查。

## 問題總覽

| 編號 | 等級 | 本次執行狀態 | 問題 |
| --- | --- | --- | --- |
| CBDB-D-008 | P0 | 已確認 | 地點表單的 UCINet 匯出把部分人物的屬性寫成空白——指數年 0、性別空白、座標 0.0 0.0——使 network.vna 中這些列少了一個欄位 |
| CBDB-D-002 | P2 | 已確認 | 群體資料表單在尚未執行查詢時會拋出錯誤：匯入名單明明成功卻顯示「Import error」，召回 ID 也顯示錯誤，而「清除」無法清除 |
| CBDB-D-001 | P3 | 已確認 | Code/ 中隨附的 Go 原始碼並不是隨附 cbdb.exe 的原始碼：自 20260925 以來只有 office_form_backend.go 有變動，而執行檔卻已包含修訂說明所描述的修改 |
| CBDB-D-003 | P5 | 已確認 | 地點表單的 Pajek、Gephi/GUESS 與 UCINet 匯出已經實作，但頁面上沒有任何控制項會呼叫它們 |
| CBDB-D-004 | P6 | 已確認 | 十一個有翻譯的表單中有十個，中文標籤與 CBDB 標籤對照表的用語不同——其中有些改變了意思：官職表單的「指數年」篩選被標為「生卒年」，另有五個表單把指數年寫成「索引年」 |
| CBDB-D-005 | P6 | 已確認 | 四個表單上有十二個標籤，其英文與中文的配對與對照表不符——其中包括人物瀏覽中英文標為 Basic Information、中文卻寫「生卒年」的分頁 |
| CBDB-D-006 | P6 | 已確認 | 七個表單顯示的文字與所選語言的字體不符：寫死在頁面上、語言切換不會改寫的雙語標籤，以及簡體文字中殘留的「指數」 |
| CBDB-D-007 | P6 | 已確認 | 同一個英文標籤、好幾種中文：23 個標籤在不同表單上譯法不同（Save to GIS 有三種、Index Year 有四種） |

## 目錄

- [CBDB-D-008 — 地點表單的 UCINet 匯出把部分人物的屬性寫成空白——指數年 0、性別空白、座標 0.0 0.0——使 network.vna 中這些列少了一個欄位](#cbdb-d-008--地點表單的-ucinet-匯出把部分人物的屬性寫成空白指數年-0、性別空白、座標-00-00使-networkvna-中這些列少了一個欄位)
- [CBDB-D-002 — 群體資料表單在尚未執行查詢時會拋出錯誤：匯入名單明明成功卻顯示「Import error」，召回 ID 也顯示錯誤，而「清除」無法清除](#cbdb-d-002--群體資料表單在尚未執行查詢時會拋出錯誤：匯入名單明明成功卻顯示「import-error」，召回-id-也顯示錯誤，而「清除」無法清除)
- [CBDB-D-001 — Code/ 中隨附的 Go 原始碼並不是隨附 cbdb.exe 的原始碼：自 20260925 以來只有 office_form_backend.go 有變動，而執行檔卻已包含修訂說明所描述的修改](#cbdb-d-001--code-中隨附的-go-原始碼並不是隨附-cbdbexe-的原始碼：自-20260925-以來只有-office-form-backendgo-有變動，而執行檔卻已包含修訂說明所描述的修改)
- [CBDB-D-003 — 地點表單的 Pajek、Gephi/GUESS 與 UCINet 匯出已經實作，但頁面上沒有任何控制項會呼叫它們](#cbdb-d-003--地點表單的-pajek、gephiguess-與-ucinet-匯出已經實作，但頁面上沒有任何控制項會呼叫它們)
- [CBDB-D-004 — 十一個有翻譯的表單中有十個，中文標籤與 CBDB 標籤對照表的用語不同——其中有些改變了意思：官職表單的「指數年」篩選被標為「生卒年」，另有五個表單把指數年寫成「索引年」](#cbdb-d-004--十一個有翻譯的表單中有十個，中文標籤與-cbdb-標籤對照表的用語不同其中有些改變了意思：官職表單的「指數年」篩選被標為「生卒年」，另有五個表單把指數年寫成「索引年」)
- [CBDB-D-005 — 四個表單上有十二個標籤，其英文與中文的配對與對照表不符——其中包括人物瀏覽中英文標為 Basic Information、中文卻寫「生卒年」的分頁](#cbdb-d-005--四個表單上有十二個標籤，其英文與中文的配對與對照表不符其中包括人物瀏覽中英文標為-basic-information、中文卻寫「生卒年」的分頁)
- [CBDB-D-006 — 七個表單顯示的文字與所選語言的字體不符：寫死在頁面上、語言切換不會改寫的雙語標籤，以及簡體文字中殘留的「指數」](#cbdb-d-006--七個表單顯示的文字與所選語言的字體不符：寫死在頁面上、語言切換不會改寫的雙語標籤，以及簡體文字中殘留的「指數」)
- [CBDB-D-007 — 同一個英文標籤、好幾種中文：23 個標籤在不同表單上譯法不同（Save to GIS 有三種、Index Year 有四種）](#cbdb-d-007--同一個英文標籤、好幾種中文：23-個標籤在不同表單上譯法不同（save-to-gis-有三種、index-year-有四種）)
- [嚴重等級說明](#嚴重等級說明)
- [如何重現這份報告](#如何重現這份報告)

## CBDB-D-008 — 地點表單的 UCINet 匯出把部分人物的屬性寫成空白——指數年 0、性別空白、座標 0.0 0.0——使 network.vna 中這些列少了一個欄位

**涉及範圍：** 地點表單的 UCINet 網絡匯出（輸出檔 network.vna）

**嚴重等級：** P0 — 靜默的錯誤結果——程式回傳錯誤或空白的結果，或產生任何軟體都讀不了的檔案，而且沒有任何錯誤提示。

**問題來源：** `software` — 程式本身的問題：cbdb.exe、其 Go 原始碼、頁面模板，或資料庫建置程式的邏輯。由 CBDB-Desktop 的開發者修正。

**本次執行狀態：** 已確認

#### 問題描述

在 `*node data` 區段中，部分人物被寫成 `<id> 0  0.0 0.0`：指數年 0、性別欄空白且未加引號、座標為零。這些人其實在查詢結果中有真實的性別與指數年——寫出程式似乎是從他們只以「關係人」身分出現的那筆記錄取屬性。由於 VNA 以空白分隔，空白的性別欄會消失，後面每一欄都往左移，因此這些列不只是錯誤，格式也壞了。PLC-3（親屬改讀 KIN_DATA）增加了大量只以關係人身分出現的情形，所以現在才顯現。頁面上沒有任何控制項到得了這個匯出（CBDB-D-003），目前沒有使用者能產生這個檔案；列入是因為開發者保留了這個匯出，打算日後接上。

#### 實測依據

`test_an_export_produces_a_well_formed_file[places:ucinet]`，以套件自己找出的地點查詢執行：有 11 個節點列是這種形式，所有欄位不足的列都完全符合。在較密集的輸入上（地址 14504、七個類別全選、932 筆記錄，於私有資料庫副本上）465 個節點列中有 155 列，例如人物 145689，在結果中為性別 F、指數年 747。執行檔的地點程式碼不在隨附原始碼中（CBDB-D-001），因此無法閱讀寫出程式；機制是由輸出推斷的。

#### 影響

目前沒有影響，因為頁面上沒有任何東西呼叫這個匯出。若照現狀接上，UCINet 會在沒有任何錯誤提示的情況下，把這些人的屬性欄位錯位讀入。

#### 復現步驟

1. 把一次地點查詢的結果 POST 到 /api/places/export-ucinet（沒有任何按鈕會這樣做），打開 network.vna：部分 *node data 列為 '<id> 0  0.0 0.0'。

#### 建議修復方式

每個人的節點屬性應取自他自己的記錄（或 BIOG_MAIN），而不是他以關係人身分出現的記錄；並在接上按鈕之前為空值加上引號。

#### 對應的程式位置

- `Code/places_form_backend.go:1348 (handleExportUCINet, as shipped -- the source the binary was built from was not)`
- `Templates/places/index.html:853 (exportUCINet, called by nothing)`

#### 對應的測試

- 1 × 失敗: `test_an_export_produces_a_well_formed_file[places:ucinet]`
- 53 × 通過: `test_an_export_produces_a_well_formed_file[entry:results]`, `test_an_export_produces_a_well_formed_file[entry:gis]`, `test_an_export_produces_a_well_formed_file[entry:kml]`, `test_an_export_produces_a_well_formed_file[entry:neo4j]` (+49)

## CBDB-D-002 — 群體資料表單在尚未執行查詢時會拋出錯誤：匯入名單明明成功卻顯示「Import error」，召回 ID 也顯示錯誤，而「清除」無法清除

**涉及範圍：** 群體資料表單（/LookAtGroupData）的頁面程式碼

**嚴重等級：** P2 — 可見的失敗——使用者的操作以他看得到的錯誤收場。多半是伺服器錯誤，有時則是頁面把一次其實已經成功的請求回報為失敗。這個級別看的是使用者看到什麼，而不是程式的哪一半出了問題。

**問題來源：** `software` — 程式本身的問題：cbdb.exe、其 Go 原始碼、頁面模板，或資料庫建置程式的邏輯。由 CBDB-Desktop 的開發者修正。

**本次執行狀態：** 已確認

#### 問題描述

`updateRunButton()` 負責決定哪些按鈕可用。它的前半段有防範尚無結果的情況（`queryData !== null && ...`）；但這個版本新增、用來啟用各資料集 GIS 勾選框的六行程式，讀取 `queryData.statusRecords`、`.officeRecords` 等時沒有這個防範。頁面載入時以及按「清除」之後，`queryData` 都是 `null`，因此在第一次查詢之前的每一次呼叫——載入時、匯入後、召回 ID 後、勾選類別時，以及在「清除」之中——都會拋出 `TypeError: Cannot read properties of null (reading 'statusRecords')`，並讓呼叫它的函式中途停止。

#### 實測依據

以 Chromium 實際操作。`test_every_page_the_build_serves_loads_without_throwing`：頁面載入時就記錄了這個錯誤。`test_group_data_can_be_used_before_its_first_query` 透過頁面自己的檔案輸入匯入一個只含一人的檔案：伺服器回應 200 並載入了該人物，頁面卻顯示「Import error: Cannot read properties of null (reading 'statusRecords')」，「清除」仍不可用，「匯入」仍可用。這六行在 20260925 的模板中並不存在，也沒有任何修訂說明提到它們。

#### 影響

使用者在群體資料表單上做的第一件事——匯入或召回一份人物名單——會回報一個並未發生的失敗，並讓按鈕停在錯誤的狀態；之後「清除」也會無聲地失敗，表單無法在不重新載入的情況下重設。查詢仍然可以執行，所以忽略錯誤訊息的人還是能用這個表單——但這不是可以要求使用者做的事。

#### 復現步驟

1. 開啟群體資料表單（Look At Group Data）。
2. 以「從檔案匯入」匯入一個只含一個人物 ID 的文字檔。
3. 頁面顯示「Import error: Cannot read properties of null (reading 'statusRecords')」；「清除」仍不可用。

#### 建議修復方式

像上面那幾行一樣防範這六行（`queryData && ...`），或改用作用域內已有的 `hasData` 來計算。

#### 對應的程式位置

- `Templates/group_data/index.html:365 (chkGisStatus, first of the six unguarded lines)`
- `Templates/group_data/index.html:161 (queryData = null)`
- `Templates/group_data/index.html:479 (clearPeople resets it to null and calls updateRunButton)`

#### 對應的測試

- 2 × 失敗: `test_every_page_the_build_serves_loads_without_throwing`, `test_group_data_can_be_used_before_its_first_query`

## CBDB-D-001 — Code/ 中隨附的 Go 原始碼並不是隨附 cbdb.exe 的原始碼：自 20260925 以來只有 office_form_backend.go 有變動，而執行檔卻已包含修訂說明所描述的修改

**涉及範圍：** 發行壓縮檔：Code/*.go 與 cbdb.exe 的對應

**嚴重等級：** P3 — 封裝問題——釋出的檔案裡含有不該出現的內容，或缺少了應該有的內容。

**問題來源：** `release` — 這一次釋出的組裝流程問題——例如把開發用的工作副本當成正式建置成果送出、某個檔案沒有重新產生。由負責建置發行檔的人在流程上修正。

**本次執行狀態：** 已確認

#### 問題描述

`cbdb.exe` 於 2026-10-20 重新建置，但 `Code/` 中除了 `office_form_backend.go` 之外，每個檔案都與 20260925 的壓縮檔逐位元組相同（`CBDBSetUpCode/` 也未變動，儘管 `CBDBsetup.exe` 同樣重新建置過）。執行檔中含有隨附原始碼裡沒有宣告的函式——`InlineArgsForDisplay` 與 `sqlLiteral`（QBE-3）、`PlaceHandler.fillIndexAddresses`（PLC-4）、`fmtOptFloat`（ASP-6）——而原始碼仍宣告 `NetworkHandler.handleRerun` 並註冊 `/api/networks/rerun`，執行檔中卻已沒有這些（NET-4 已將其移除）。因此公開的原始碼建置不出公開的程式，九份說明中的 Go 修訂沒有一項以原始碼形式隨附。

#### 實測依據

`test_the_shipped_source_is_the_source_of_the_shipped_binary` 比對 cbdb.exe 函式名稱表中的 `main.` 函式與 `Code/*.go` 中的 `func` 宣告（排除編譯器產生的包裝函式與連結器捨棄的函式，規則以寫定答案的案例測試；20260925 的壓縮檔比對結果一致）。只在執行檔中：InlineArgsForDisplay、PlaceHandler.fillIndexAddresses、fmtOptFloat、sqlLiteral。只在原始碼中：NetworkHandler.handleRerun。從行為上看，`test_every_registered_api_route_still_exists` 發現 `/api/networks/rerun` 在原始碼中有註冊、執行檔卻回應 404；`test_every_api_endpoint_the_build_routes_has_a_page_that_calls_it` 發現它在原始碼中有路由、卻沒有任何頁面呼叫。

#### 影響

任何閱讀、稽核或以隨附原始碼重新建置的人，得到的都是上個月的程式。對本測試套件而言，凡是把 Go 原始碼當作資料讀取的檢查——路由清單、暫存表歸屬、本報告中引用的 Go 程式行——在兩者有差異之處描述的都是前一個版本；因此本報告中重要的發現都是透過實際操作執行檔確立的。

#### 復現步驟

1. 打開壓縮檔中的 Code/networks_form_backend.go：它註冊了 /api/networks/rerun（第 326 行）。
2. 執行 cbdb.exe，對 /api/networks/rerun 發出任何請求：回應 404。

#### 建議修復方式

隨附建置執行檔時實際使用的 `Code/`（與 `CBDBSetUpCode/`），並把複製原始碼列為建置執行檔的發行步驟之一。

#### 對應的程式位置

- `Code/networks_form_backend.go:326 (registers /api/networks/rerun, absent from the binary)`
- `Code/networks_form_backend.go:823 (handleRerun)`

#### 對應的測試

- 3 × 失敗: `test_the_shipped_source_is_the_source_of_the_shipped_binary`, `test_every_api_endpoint_the_build_routes_has_a_page_that_calls_it`, `test_every_registered_api_route_still_exists`

## CBDB-D-003 — 地點表單的 Pajek、Gephi/GUESS 與 UCINet 匯出已經實作，但頁面上沒有任何控制項會呼叫它們

**涉及範圍：** 地點表單（/LookAtPlace）的 Pajek、Gephi/GUESS 與 UCINet 三種網絡匯出

**嚴重等級：** P5 — 無法觸及的功能——程式實作了某項功能，卻沒有任何頁面可以呼叫它。這個級別只說明「沒有任何使用者到得了」。至於背後的程式碼是否正確，是另一個問題、也有另一個答案；因此一項既到不了、本身又有錯的功能會在兩處分別記錄，而不是在同一處爭論該算哪一種。

**問題來源：** `software` — 程式本身的問題：cbdb.exe、其 Go 原始碼、頁面模板，或資料庫建置程式的邏輯。由 CBDB-Desktop 的開發者修正。

**本次執行狀態：** 已確認

#### 問題描述

地點表單頁面定義了 `exportPajek`、`exportGephi` 與 `exportUCINet`，各自把查詢結果送到對應的端點並下載回應，三個後端處理函式也都有路由、能夠回應。但頁面上沒有任何東西會呼叫這三個函式：它的按鈕只有執行查詢、儲存人物ID、導出查詢結果、保存到KML、保存到GIS 與導出Neo4j CSV，也沒有任何事件監聽或載入時執行的程式碼呼叫它們。開發者 2026-10-15 的修訂說明（PLC-6）表示這是刻意的：雖然表單上沒有按鈕，這些函式與路由仍「保留」，因為地點查詢不建立社會或親屬網絡，這些匯出只會產生片段的網絡；保留是為了日後指導委員會若要加上按鈕時備用。列入報告是為了讓這個決定可見；是否接受由維護者決定。

#### 實測依據

`test_every_endpoint_a_page_calls_is_reachable_from_something_a_user_does` 從每個頁面上所有可能執行的地方出發——按鈕、每個行內 `on...=` 處理函式、載入時執行的程式碼、以名稱註冊的事件監聽，以及彈出視窗回呼的 `window.X`——沿著頁面的呼叫關係走訪。在這個版本的所有頁面中，只有這三個端點是頁面提到、卻走訪不到的。PLC-6 說明證實這是刻意的，並把「在 `exportUCINet()` 上方加註解說明刻意保留」列為待辦事項。

#### 影響

在地點表單中工作的研究者，無法產生其他網絡類表單都能產生的 Pajek、Gephi 或 UCINet 檔案，頁面上也沒有任何跡象顯示這項功能存在。這不會給出錯誤的結果，只是功能到不了——而這是開發者的選擇。

#### 復現步驟

1. 開啟地點表單，執行一個有結果的查詢。
2. 尋找 Pajek、Gephi/GUESS 或 UCINet 匯出：一個都沒有，儘管頁面程式碼中定義了 exportPajek、exportGephi 與 exportUCINet。

#### 建議修復方式

可以接受為既定設計（以上述測試為鍵登錄一筆豁免即可記錄這個決定），或補上三個按鈕，或刪除這些函式與後端處理函式。PLC-6 提議的註解可讓閱讀頁面程式碼的人知道它們為何存在。

#### 對應的程式位置

- `Templates/places/index.html:853 (exportUCINet, called by nothing)`
- `Templates/places/index.html:870 (exportPajek, called by nothing)`
- `Templates/places/index.html:887 (exportGephi, called by nothing)`
- `Templates/places/index.html:93 (the page's action buttons)`

#### 對應的測試

- 1 × 失敗: `test_every_endpoint_a_page_calls_is_reachable_from_something_a_user_does`

## CBDB-D-004 — 十一個有翻譯的表單中有十個，中文標籤與 CBDB 標籤對照表的用語不同——其中有些改變了意思：官職表單的「指數年」篩選被標為「生卒年」，另有五個表單把指數年寫成「索引年」

**涉及範圍：** 所有具語言切換的表單的翻譯表（Templates/*/index.html）

**嚴重等級：** P6 — 用語問題——頁面上的標籤在三種顯示語言（英文、繁體、簡體中文）之一說錯了意思，或用錯了字體。依固定規則對照 CBDB 標籤對照表判定；不影響程式的計算結果，但可能讓讀者誤解控制項的作用。

**問題來源：** `software` — 程式本身的問題：cbdb.exe、其 Go 原始碼、頁面模板，或資料庫建置程式的邏輯。由 CBDB-Desktop 的開發者修正。

**本次執行狀態：** 已確認

#### 問題描述

當一個標籤的英文是 CBDB 標籤對照表（Access 前端的 FormLabels 表，即測試儲存庫中的 docs/labels/FormLabels.xlsx）為該表單定義的用語時，它的中文應當是對照表為該用語給出的譯名之一。十一個有翻譯的表單中有十個（人物瀏覽除外），共 116 個標籤不是如此。多數是措辭與對照表不同（*Run Query* 寫作 `執行查詢`，對照表為 `查詢`；*Store Person IDs* 寫作 `儲存人物ID`，對照表為 `存儲人物代碼`；*From*/*To* 寫作 `起`/`終`，對照表為 `始年`/`終年`）。但也有一些改變了告訴讀者的意思：

- 官職表單：日期篩選 *Index Years* 在兩種中文中都寫作 `生卒年`；實際篩選的是指數年。
- 兩兩關係、社會關係、入仕、社會網絡、著述表單：*Index Year* 寫作 `索引年`／`索引年份`；對照表的用語是 `指數年`，而開發者自己 2026-10-16 的說明也指出 `指數` 才正確、`索引` 應改回。
- 社會區分與群體資料表單：*Status* 寫作 `身份`；對照表的用語是 `社會區分`。
- 親屬表單：*Mourning Circle* 寫作 `服制圈`；對照表的用語是 `五服`。
- 社會網絡表單：社會關係類別的勾選框自行翻譯（`友誼`、`對立`、`支持`、`學術隸屬`、`推薦／贊助`），對照表則為 `朋友`、`軍事對抗`、`軍事支持`、`學術交往`、`薦舉保任`。

完整清單及每項判定所依據的對照表列，見 `reports/CBDB_Desktop_Translations.md`／`.xlsx`。

#### 實測依據

`test_chinese_labels_use_the_glossary_term` 每個表單一個測試，十一個中有十個失敗。標籤是從每個模板的翻譯物件中以資料方式讀出，只判定頁面實際使用的標籤；每個標籤只和它自己的 Access 表單的對照表列比較（官職對 LAO、社會區分對 LAS、人物瀏覽對 BIO 與 BROWSE——其子表單的簡短欄位標題不用來決定英文詞的譯法），比較措辭時先把兩邊轉成同一種字體，並容許兩岸用語差異（匯出／导出、儲存／保存），因此字體錯誤或地區用語都不會在這裡造成判定。各表單筆數：社會網絡 32、群體資料 15、社會區分 14、兩兩關係 11、入仕 9、官職 9、親屬 8、著述 8、社會關係 7、地點 3（此版本的量測結果；以報告為準）。

#### 影響

中文介面的讀者所得到的訊息，與英文讀者不同，也與 CBDB 其他地方使用的用語不同。在意思被改變之處會造成誤導：在官職表單上讀到「生卒年」的研究者，會以為該篩選是依生卒年選取。程式的計算結果不受影響。

#### 復現步驟

1. 開啟官職表單（Look At Office），按「繁」（或「简」）。
2. 閱讀英文頁面稱為 Index Years 的日期篩選選項：它寫著「生卒年」。
3. 開啟入仕表單（Look At Entry），按「繁」：指數年選項寫著「索引年」，而 CBDB 的用語是「指數年」。

#### 建議修復方式

把清單中的每個中文標籤換成對照表的用語（報告中已列出），先處理改變意思的那些。若開發者偏好自己的措辭，應改的是對照表——在試算表中修改，讓兩者維持同一套用語。

#### 對應的程式位置

- `Templates/office/index.html:245 (indexYearsFilter: '生卒年')`
- `Templates/entry/index.html:299 (indexYear: '索引年')`
- `Templates/status/index.html:218 (status: '身份')`
- `Templates/kinship/index.html:170 (Mourning Circle: '服制圈')`

#### 對應的測試

- 10 × 失敗: `test_chinese_labels_use_the_glossary_term[association_pairs]`, `test_chinese_labels_use_the_glossary_term[associations]`, `test_chinese_labels_use_the_glossary_term[entry]`, `test_chinese_labels_use_the_glossary_term[group_data]` (+6)
- 1 × 通過: `test_chinese_labels_use_the_glossary_term[browser]`

## CBDB-D-005 — 四個表單上有十二個標籤，其英文與中文的配對與對照表不符——其中包括人物瀏覽中英文標為 Basic Information、中文卻寫「生卒年」的分頁

**涉及範圍：** 人物瀏覽、親屬、社會網絡與官職表單的翻譯表

**嚴重等級：** P6 — 用語問題——頁面上的標籤在三種顯示語言（英文、繁體、簡體中文）之一說錯了意思，或用錯了字體。依固定規則對照 CBDB 標籤對照表判定；不影響程式的計算結果，但可能讓讀者誤解控制項的作用。

**問題來源：** `software` — 程式本身的問題：cbdb.exe、其 Go 原始碼、頁面模板，或資料庫建置程式的邏輯。由 CBDB-Desktop 的開發者修正。

**本次執行狀態：** 已確認

#### 問題描述

當一個標籤的中文是其表單的對照表用語、而英文完全不是對照表用語時，英文應是對照表為該中文所給的英文——否則就是中文那一半有誤。有十二個不是：人物瀏覽的 *Basic Information* 對應 `生卒年`（對照表為 *Birth/Death Years*）、*Social Institutions* 對應 `社交機構`（*Institutions*）、*ID:* 與 *CBDB ID* 對應 `人物代碼`（*Person ID*）、*Birth:*／*Death:* 對應 `生年`／`卒年`（*Born*／*Died*）、*Age* 對應 `享年`（*Age at Death*）、*Offices* 對應 `職官`（*Postings*）；親屬的 *Kin Network*（*Kinship Network*）；社會網絡的 *Biography* 與 *Ritual*（*Biographical Texts*、*Ritual Texts*）；官職的 *Query*（*Run Query*）。第一項不只與對照表不符，也是兩種語言之間互不相符：頁面自己的註解寫著英文標題已改名，「尚未提供新的中文標題」。

#### 實測依據

`test_english_labels_use_the_glossary_term` 在人物瀏覽（8）、社會網絡（2）、親屬（1）與官職（1）上失敗。只有英文「不是」對照表用語的標籤才以這種方式判定，因此一組錯誤的對應只會被報告一次（在 D-004 或這裡），不會兩邊各報一次。

#### 影響

多半是措辭問題。人物瀏覽的第一個分頁是例外：英文讀者與中文讀者被告知這個分頁的內容不同。

#### 復現步驟

1. 開啟人物瀏覽，選擇一個人物，以英文閱讀第一個分頁（Basic Information），再按「繁」：顯示為「生卒年」。

#### 建議修復方式

這十二個標籤改用對照表的英文；或為人物瀏覽補上註解中所等待的中文標題，並將兩者一併加入對照表。

#### 對應的程式位置

- `Templates/browser/index.html:406 (tabBasicInfo: '生卒年', with the comment about the renamed caption)`
- `Templates/kinship/index.html:163 (Kin Network)`

#### 對應的測試

- 4 × 失敗: `test_english_labels_use_the_glossary_term[browser]`, `test_english_labels_use_the_glossary_term[kinship]`, `test_english_labels_use_the_glossary_term[networks]`, `test_english_labels_use_the_glossary_term[office]`
- 7 × 通過: `test_english_labels_use_the_glossary_term[association_pairs]`, `test_english_labels_use_the_glossary_term[associations]`, `test_english_labels_use_the_glossary_term[entry]`, `test_english_labels_use_the_glossary_term[group_data]` (+3)

## CBDB-D-006 — 七個表單顯示的文字與所選語言的字體不符：寫死在頁面上、語言切換不會改寫的雙語標籤，以及簡體文字中殘留的「指數」

**涉及範圍：** 兩兩關係、社會關係、社會網絡、官職、地點、社會區分與著述表單

**嚴重等級：** P6 — 用語問題——頁面上的標籤在三種顯示語言（英文、繁體、簡體中文）之一說錯了意思，或用錯了字體。依固定規則對照 CBDB 標籤對照表判定；不影響程式的計算結果，但可能讓讀者誤解控制項的作用。

**問題來源：** `software` — 程式本身的問題：cbdb.exe、其 Go 原始碼、頁面模板，或資料庫建置程式的邏輯。由 CBDB-Desktop 的開發者修正。

**本次執行狀態：** 已確認

#### 問題描述

選擇「繁」時，官職表單仍顯示 `Office 官职`、`Type 类型`、`Place 地点` 以及標題 `官职查询`；著述表單顯示 `查询模式`、`(全部地点)` 與 `日期筛选`；社會關係表單顯示 `(关系)`。選擇「简」時，地點、社會關係與社會網絡表單保留繁體標題（`查看地點`、`查看關係`、`查看人際網絡`），社會區分保留 `Place / 地點`，著述保留 `書名`，兩兩關係保留提示文字 `[漢字]`。這些都是直接寫在 HTML 中、`setLanguage` 不會改寫的標籤。另外有四個簡體翻譯含有繁體的「數」：地點的 `指數年份范围`、`相关人物指數地点`、`亲属指數地点`，以及社會區分的 `使用指數年份`（兩個中文表中皆同）。

#### 實測依據

兩處各有一項檢查。`test_each_chinese_language_shows_only_its_own_script` 在 Chromium 中按下每個頁面自己的「繁」與「简」按鈕，判讀畫面上的文字（只判讀出現在模板中、且不屬於翻譯表的字串——翻譯表中的字串已由另一項檢查判讀，不重複計算；頁面上顯示的 CBDB 資料不在判讀之列）：7 個頁面共 14 個字串。`test_every_chinese_label_is_written_in_its_own_script` 讀取翻譯表：即上述四個「數」。只有當 OpenCC 轉換為所選字體的每一種標準——大陸、台灣與香港——不論在上下文中或單獨看都會改動某個字時，該字才會被標出。

#### 影響

選擇了某一種字體的讀者，在標籤與標題中看到另一種字體。屬於外觀問題，但正是選擇「繁」或「简」的讀者最先注意到的地方。

#### 復現步驟

1. 開啟官職表單（Look At Office），按「繁」。
2. 閱讀左側面板：'Office 官职'、'Type 类型'、'Place 地点' 仍是簡體字。

#### 建議修復方式

為每個寫死的雙語標籤加上 id，並在頁面的翻譯表中加入對應的鍵（已翻譯的標籤本來就是這樣做）；把四個簡體字串中的「數」改為「数」。

#### 對應的程式位置

- `Templates/office/index.html:34 (<label>Office 官职</label>)`
- `Templates/status/index.html:49 (<h3>Place / 地點</h3>)`
- `Templates/places/index.html:202 (indexYearRange: '指數年份范围')`
- `Templates/status/index.html:239 (useIndexYears: '使用指數年份')`

#### 對應的測試

- 9 × 失敗: `test_every_chinese_label_is_written_in_its_own_script[places]`, `test_every_chinese_label_is_written_in_its_own_script[status]`, `test_each_chinese_language_shows_only_its_own_script[association_pairs]`, `test_each_chinese_language_shows_only_its_own_script[associations]` (+5)
- 13 × 通過: `test_every_chinese_label_is_written_in_its_own_script[association_pairs]`, `test_every_chinese_label_is_written_in_its_own_script[associations]`, `test_every_chinese_label_is_written_in_its_own_script[browser]`, `test_every_chinese_label_is_written_in_its_own_script[entry]` (+9)

## CBDB-D-007 — 同一個英文標籤、好幾種中文：23 個標籤在不同表單上譯法不同（Save to GIS 有三種、Index Year 有四種）

**涉及範圍：** 所有表單的翻譯表

**嚴重等級：** P6 — 用語問題——頁面上的標籤在三種顯示語言（英文、繁體、簡體中文）之一說錯了意思，或用錯了字體。依固定規則對照 CBDB 標籤對照表判定；不影響程式的計算結果，但可能讓讀者誤解控制項的作用。

**問題來源：** `software` — 程式本身的問題：cbdb.exe、其 Go 原始碼、頁面模板，或資料庫建置程式的邏輯。由 CBDB-Desktop 的開發者修正。

**本次執行狀態：** 已確認

#### 問題描述

把所有翻譯標籤依英文分組，有 23 個在不同表單上有多於一種譯法，例如：*Save to GIS* 有 `儲存至GIS`（兩兩關係、入仕、群體資料）、`保存到GIS`（社會關係、社會網絡、地點、社會區分、著述）、`存至GIS`（親屬）；*Index Year* 有 `索引年`、`索引年份`、`指數年`、`生卒年`；*Recall IDs* 有 `召回ID`、`調出ID`、`調取ID`；*Status* 有 `社會區分`（人物瀏覽）與 `身份`（群體資料、社會區分）；*Offices* 有 `職官` 與 `官職`；*From:*／*To:* 有 `從:`／`至:` 與 `起`／`終`。兩岸用語差異不算作不同（維護者 2026-10-22 的裁定）。

#### 實測依據

`test_one_english_label_is_translated_one_way_across_pages`（不需對照表）。措辭依 OpenCC 的字體與兩岸用語對應，加上 docs/labels/regional_terms.tsv 中的詞對歸類，因此 儲存／保存、匯出／导出 或 連結／连接 視為同一個詞；同一表單內一個簡短英文詞對應數個中文標籤（人物瀏覽的 Range → 生年時限／卒年時限）是依上下文命名的欄位，不計入。

#### 影響

讀者在表單間移動時，對同一個動作或概念要認識好幾個詞，也無法分辨各表單指的是否是同一件事。

#### 復現步驟

1. 在入仕、社會網絡與親屬表單上按「繁」，比較 Save to GIS 按鈕：儲存至GIS、保存到GIS、存至GIS。

#### 建議修復方式

每個標籤選定一種措辭——對照表有的就用對照表的（見 D-004）——並在所有表單上一致使用。

#### 對應的程式位置

- `Templates/entry/index.html:308 (saveGIS: '儲存至GIS')`
- `Templates/networks/index.html:482 (saveToGIS: '保存到GIS')`
- `Templates/kinship/index.html:150 (Save to GIS: '存至GIS')`

#### 對應的測試

- 1 × 失敗: `test_one_english_label_is_translated_one_way_across_pages`

## 嚴重等級說明

- **P0** — 靜默的錯誤結果——程式回傳錯誤或空白的結果，或產生任何軟體都讀不了的檔案，而且沒有任何錯誤提示。
- **P1** — 破壞性寫入——一次請求改寫了本不該改寫的既存資料，原本的狀態無法復原。
- **P2** — 可見的失敗——使用者的操作以他看得到的錯誤收場。多半是伺服器錯誤，有時則是頁面把一次其實已經成功的請求回報為失敗。這個級別看的是使用者看到什麼，而不是程式的哪一半出了問題。
- **P3** — 封裝問題——釋出的檔案裡含有不該出現的內容，或缺少了應該有的內容。
- **P4** — 資料完整性——釋出資料中存在無法解析的參照。
- **P5** — 無法觸及的功能——程式實作了某項功能，卻沒有任何頁面可以呼叫它。這個級別只說明「沒有任何使用者到得了」。至於背後的程式碼是否正確，是另一個問題、也有另一個答案；因此一項既到不了、本身又有錯的功能會在兩處分別記錄，而不是在同一處爭論該算哪一種。
- **P6** — 用語問題——頁面上的標籤在三種顯示語言（英文、繁體、簡體中文）之一說錯了意思，或用錯了字體。依固定規則對照 CBDB 標籤對照表判定；不影響程式的計算結果，但可能讓讀者誤解控制項的作用。

## 如何重現這份報告

整份報告由一道指令產生。只要在 `.env` 中以 `CBDB_DESKTOP_ZIP` 指定發行壓縮檔：

```powershell
.\run_tests.ps1
```

這道指令會解開壓縮檔、以釋出資料庫的私有複本啟動釋出的執行檔、執行 1535 項測試，並重新產生這幾份檔案。測試套件不會寫入作為對照基準的 `Data/CBDB.db`——每次執行都使用各自的複本，因此跑完之後，發行檔與執行前完全相同。

每一項問題底下都列出了對應的測試名稱。若只想執行其中一項：

```powershell
python -m pytest tests -k test_searching_people_by_name_finds_them -v
```


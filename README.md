# Pokémon GO 田野調查任務地圖

只顯示任務碼為 `16^1^8^0^^^^^Excellent`、且獎勵碼為 `4^890^^25^N^^^N` 的補給站。標記顯示「投出1次Excellent」與「獲得糖果25顆(無極汰那)」。可匯入多份 JSON、搜尋站名、查看台灣時間、定位和開啟 Google Maps 導航。地圖使用 Leaflet 與臺灣通用電子地圖，無廣告或分析追蹤程式。

## Windows

開啟 `dist/local.html` 會直接載入本機打包的任務快照。允許瀏覽器定位後，地圖只顯示直線距離 5 公里內符合任務及獎勵的補給站。按「全覽」顯示快照中所有符合項目，按「定位」可重新取得位置。若瀏覽器限制本機檔案定位，可執行下方的本機 HTTP 預覽並開啟 `http://localhost:8000/dist/local.html`。

有新的 `quests.json` 時執行 `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build.ps1 -LocalSnapshot` 重建本機版。快照反映檔案中的資料及更新時間，專案不會向來源網站抓取即時任務。包含快照的 `dist/local.html` 已列入 Git 忽略清單，請留在本機。

1. 用 Chrome 或 Edge 雙擊開啟 [dist/index.html](dist/index.html)。單檔已內嵌專案的 CSS 和 JavaScript，可直接用 `file://` 開啟。
2. 按「匯入 JSON」選取一個或多個 `quests.json` 檔案。也可先使用 [範例資料](data/quests.sample.json)。
3. 點選標記查看任務。縮小地圖時各站仍各自顯示。同一位置的標記可能重疊。「全覽」會縮放到目前符合篩選條件的資料範圍。

單檔內嵌 Leaflet 和樣式，底圖圖磚仍需連網。手動匯入的資料只在目前頁面記憶體中，重新開啟頁面後需重新匯入。

## iPhone Safari

- 按「跟隨定位」並允許 Safari 使用位置。地圖開著時會隨位置更新附近 5 公里的任務。「停止跟隨」會停在上次位置，「全覽」會顯示整份快照。
- 在站點彈窗勾選「加入路線」，查看地圖上的編號，再按下方「路線導航」開啟單一 Google Maps 機車路線。第一次勾選時固定起點，有定位時用當下的位置，否則用第一站。地圖最多計算 16 站的最短直線往返順序。Google Maps 單一路線的中途站限制在手機瀏覽器為 3 站，桌面瀏覽器為 9 站。[Google Maps URL 說明](https://developers.google.com/maps/documentation/urls/get-started#directions-action)
- 按「標記完成」後，站點會變灰並移出路線。再打開該站點可取消完成。完成紀錄保存在目前瀏覽器，按台灣日期重新計算。

1. 將 JSON 存到 iCloud Drive 或「我的 iPhone」的「檔案」App。
2. 用 Safari 開啟 GitHub Pages 的 HTTPS 網址。
3. 按「匯入 JSON」並從檔案選擇器選取資料。按「定位」時，請允許 Safari 使用位置。
4. 要從主畫面開啟，從 Safari 的分享選單選「加入主畫面」，若有「打開為網頁 App」選項則開啟後再按「加入」。[Apple 的操作說明](https://support.apple.com/zh-tw/guide/iphone/iphea86e5236/27/ios/27)

## GitHub Pages 部署

1. 在 GitHub 建立公開儲存庫。使用 GitHub Free 時，公開儲存庫可使用 Pages。
2. 將 `dist/index.html` 的內容以 `index.html` 檔名上傳到儲存庫根目錄，提交到 `main`。如需一起上傳開發原始碼，可將上面的單檔放在儲存庫的 `docs/index.html`，再選擇 `/docs` 發布。
3. 在 **Settings → Pages → Build and deployment** 下選擇 **Deploy from a branch**，選 `main` 與 `/ (root)` 或對應的 `/docs`，儲存並等待 Pages 顯示網址。以 HTTPS 網址開啟。部署後家中的電腦可以關機。[GitHub Pages 發布來源說明](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages?s=09)
4. 預設由訪客手動選檔。若有允許公開再散布的資料，可把 `quests.json` 放在發布版的 `index.html` 同一層，頁面會自動讀取並要求定位。Pages 上的檔案可由訪客下載。現有的原始擷取檔、請求標頭和憑證請留在本機。

單檔版及 GitHub Pages 版均使用國土測繪中心免申請的「臺灣通用電子地圖」WMTS，底圖主要涵蓋台灣，無須 API Key。原版的 OpenStreetMap 公益圖磚端點可能對缺少網站 Referer 的本機檔案回傳 403。[國土測繪中心 WMTS 說明](https://maps.nlsc.gov.tw/S09SOA/pro/Wmts_ajax_main.jsp) · [OpenStreetMap 圖磚政策](https://operations.osmfoundation.org/policies/tiles/)

## 原始碼與開發

- `index.html` 與 `css/style.css` 提供網頁與行動版樣式。
- `js/parser.js` 解析 `fp`、驗證座標、保留並拆分原始碼，以及格式化台灣時間。
- `js/filters.js` 實作同一組的複選聯集，以及站名、任務、獎勵之間的交集。
- `js/map.js` 負責底圖、獨立站點標記、定位與導航。批次繪製標記可讓瀏覽器在批次之間處理互動。
- `js/app.js` 負責檔案選擇、合併和介面更新。

以完整 `a` 值辨識重複資料。缺少 `a` 時以經緯度和站名辨識。保留時間較新的記錄，同時間或兩筆皆無時間時以後匯入者為準。無效座標會略過，缺少站名、時間或編碼時顯示對應提示。已確認的完整編碼可加入 `js/parser.js` 的 `mappings`。未知碼在標記中原樣顯示，篩選器以首段原始代碼分組，代碼分組不代表已解碼的種類。

在 PowerShell 執行以下命令來重建單檔。若要以 HTTP 測試，可執行第二行並開啟 `http://localhost:8000/dist/`。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build.ps1
python -m http.server 8000 --bind 127.0.0.1
```

Python 3.8 以上可用標準函式庫合併 JSON 或依檔頭辨識的 GZIP，輸出新檔後再匯入。以下以目前工作目錄中的兩份同源資料為例。

```powershell
python scripts/convert_data.py quests.json response.bin -o quests.merged.json
```

## 測試結果

2026-11-20，Windows Chrome 的本機單檔測試通過 20 項。涵蓋底圖圖磚實際載入與署名、中文、數字座標、編碼拆分、台灣時區、無效資料、合併、多選篩選、15,000 筆合成資料匯入與叢集、匯入後搜尋、標記導航、320px 展開版面及現有 `quests.json` 匯入。可透過上述 HTTP 預覽開啟 `http://localhost:8000/tests/browser.html` 重跑，工作目錄沒有 `quests.json` 時只執行 19 項。Python 3.13 已驗證範例與現有 JSON／GZIP，合併後保留 834 筆並移除 834 筆重複記錄。iPhone 實機、真實定位授權與 GitHub Pages 上線仍待驗證。

## 每日更新可行性

截至 2026-11-20，公開資料查核包含來源首頁、任務頁、隱私權政策與索引搜尋。沒有查到該端點的公開 API 規格、允許定時擷取的條款、公開配額或機器授權流程。來源隱私權政策描述個人資料處理，沒有提供任務資料的再散布授權。這次公開查核無法讀取裸端點及 robots.txt，因此兩者不構成判定依據。[來源首頁](https://twpkinfo.com/) · [任務頁](https://twpkinfo.com/iquest.aspx) · [隱私權政策](https://twpkinfo.com/policy.aspx/)

| 問題 | 結果 |
| --- | --- |
| 匿名或程式化存取 | 依使用者的測試，簡化匿名請求失敗，完整瀏覽器請求成功，尚未確認有受支援的公開存取方式。 |
| Cookie 是否必要 | 成功樣本含 Cookie 和多種標頭，失敗樣本同時省略了其他條件，無法獨立判定 Cookie 是否必要。 |
| `f`、`g` 是否有時效 | 目前沒有公開規格或站方確認。 |
| 正常授權 | 可向站方詢問官方匯出、API 金鑰或其他機器對機器方式，並確認快取、地理範圍及再發布權。 |
| 頻率 | 取得授權後，先依站方配額與更新時刻，以每日一次和最小地理範圍為起點。支援時使用條件式請求，遇到限流依 `Retry-After` 降速，授權失敗時停止排程。 |

### 探測與本機測試

在全新的匿名請求中，裸端點回了含一筆資料的 `fp`，但該筆沒有有效座標，也沒有完整任務和獎勵碼。探測器回報 `invalid_row`，原本 `quests.json` 的雜湊不變。仍需站方提供允許程式呼叫的介面，現階段可繼續使用手動匯入。

有站方允許的 HTTPS GET 端點時，在 PowerShell 設定 `QUEST_API_URL`，先以唯讀模式驗證。腳本只發出一次 GET，接受明文或 GZIP，會拒絕重新導向、空快照、無效列與超出大小限制的回應。成功才原子替換目標檔，錯誤記錄只有類型及 HTTP 狀態碼。

```powershell
$env:QUEST_API_URL = 'https://你的授權端點'
python scripts/probe_api.py --check
# 確認唯讀驗證成功後，才執行下列更新
python scripts/probe_api.py
# 不連來源站的本機端到端測試
python -m unittest discover -s tests -p test_probe_api.py -v
```

### 啟用 Playwright 更新及 GitHub Pages

Playwright 更新器每次啟動全新 Chromium 工作階段，正常開啟任務頁，等候頁面自己發出的任務回應。它不操作地圖或重試。完整驗證站名、座標及任務和獎勵碼後，依站點 ID 合併重複列，保留時間較新的記錄；沒有 ID 時以座標及站名辨識。更新和時間戳以同一個檔案原子寫入 `data/quests.json`。任務內容相同時保留原檔及上次快照變更時間。

```powershell
python -m pip install playwright==1.65.2
python -m playwright install chromium
python -m unittest discover -s tests -p "test_*.py" -v
python scripts/update_quests.py
```

1. 確認站方允許每天執行及公開再散布，然後把原始碼、`dist/index.html` 和工作流程提交到預設分支。原始擷取檔及含本機快照的 `dist/local.html` 留在本機。
2. 在 **Settings → Pages → Build and deployment** 選 **GitHub Actions**。確認儲存庫政策允許工作流程的 token 寫入內容，並檢查預設分支規則是否允許 bot 直接提交資料。
3. 在 **Actions → Update quest snapshot → Run workflow** 選含變更的分支，保留 publish 未勾選，無需變數即可唯讀試跑。日誌會列出查詢矩形、圈內筆數及覆蓋判定。
4. 要先手動跑一次完整掃描，在預設分支勾選 `publish`，並設定 `QUEST_AUTO_UPDATE_ENABLED=true`。掃描保持定位後的縮放，以一般地圖拖曳切換視窗。每次主動拖曳前，距上一筆任務請求至少等候 8 秒，整趟最多 48 筆任務請求，包含網站自行發出的台北及定位初始化請求。
5. 手動掃描確認成功後，可再設定 `QUEST_AREA_SCAN_ENABLED=true`，使台灣時間 00:30 的排程執行同一完整流程。只開啟 `QUEST_AUTO_UPDATE_ENABLED` 時，排程仍會做唯讀探測並輸出視窗規劃。

唯讀探測不提交或發布。完整掃描以實際查詢矩形聯集驗證整個設定圓，再依站點 ID 及時間去重，只保留圈內任務。資料有變才提交，並部署單檔地圖和快照。遇到存取限制、無效視窗、請求逾時、超過請求上限或覆蓋不足時，工作失敗，現有快照和 Pages 網站保留。覆蓋驗證只確認幾何範圍，站方若未公開資料截斷規則，仍無法證明回應包含所有任務。地圖優先讀取 `./data/quests.json`，遇到 404 時支援舊版同層 `quests.json`，快照請求使用 `no-store`。最後更新時間以台灣時間顯示，快照超過 48 小時時會提醒，仍繼續使用資料。

掃描遇到 HTTP 200、`fp` 只有一筆且該筆為 `invalid_row` 的回應時，依目前設定將該視窗視為空資料。該矩形仍計入幾何覆蓋，日誌標記為 `assumed_empty`。整趟沒有有效資料時保留舊快照。

來源頁初始化、資料範圍、欄位格式、速率限制和授權都可能變動。若來源的預設地圖範圍改變，通過欄位驗證也可能得到不同覆蓋範圍。分支規則禁止 bot push 時，部署工作會停在提交步驟。


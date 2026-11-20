# 爬報寶貝 Playwright 初始化診斷

測試日期為 2026-11-20（台灣時間）。環境為 Windows、Python 3.13、Playwright 1.65.2 和 Playwright 隨附的 Chromium 159.0.8154.6。兩次均使用 `chromium` channel，各建立全新的 Browser Context，未讀入任何瀏覽器狀態。

## 實際結果

| 模式 | 任務頁 | 觀察到的 `getquest.ashx` | `fp` 筆數 | 通過欄位驗證 | 互動 |
| --- | --- | --- | ---: | ---: | --- |
| Headless | HTTP 200，已到 DOMContentLoaded | HTTP 200，JSON | 1,643 | 1,643 | 無 |
| Headed | HTTP 200，已到 DOMContentLoaded | HTTP 200，JSON | 1,643 | 1,643 | 無 |

兩種模式均達成成功條件。初始化期間，任務頁自身的 JavaScript 發出請求，探測器被動接收已完成的回應。雖然執行時允許在觀察窗結束後最多按一次可見的地圖放大按鈕，兩次都在此之前得到有效回應，所以沒有按下任何按鈕。

兩次觀察皆未遇到可見 CAPTCHA、登入提示或 HTTP 401、403、407、429；沒有失敗階段。這證明在此次 Windows 環境中，全新瀏覽器工作階段可透過原頁面初始化取得有效資料，沒有手動傳入 Cookie 或 Token。網站可能自行建立 Session，診斷未讀取其值，也未判定哪個欄位必要、資料範圍是否完整，或參數的有效期限。

## Ubuntu Runner 與整合建議

GitHub Actions 的 Ubuntu Runner 具備執行 Playwright Chromium 的技術條件，可透過 `python -m playwright install --with-deps chromium` 安裝瀏覽器與系統相依套件。本站在 Ubuntu Runner 上的可達性、回應筆數與是否允許無人值守擷取及再散布均未驗證。[Playwright CI 文件](https://playwright.dev/python/docs/ci)

若站方確認允許，先在 Ubuntu Runner 手動做一次唯讀 headless 驗證，確認回傳範圍符合用途。通過後，可在現有更新器加入獨立的瀏覽器取資料模式，只接收網站正常生成的第一筆通過全檔驗證的任務回應，再交由既有原子寫入處理。無回應、空資料、驗證失敗或存取受限時保留舊快照，使用站方允許的頻率，避免重試或反覆操作地圖。現階段每日排程未啟用。

## 固定多區域可行性

2026-11-20 以全新 headless Chromium 開頁，等候初始任務回應，再向左拖曳一次可見地圖。兩筆任務回應均為 HTTP 200，所有資料列均通過既有欄位驗證。

| 視窗 | 北緯 | 東經 | 南緯 | 西經 | 有效筆數 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 開頁 | 25.063598 | 121.577497 | 25.037938 | 121.522565 | 1,643 |
| 拖曳一次後 | 25.063598 | 121.598997 | 25.037938 | 121.544065 | 1,556 |

這證實一般拖曳會觸發不同的查詢視窗。兩個視窗都在台北市附近，南北跨度約 2.85 公里，單一視窗不可能覆蓋半徑 5 公里的圓。欄位驗證及查詢邊界都無法證明來源沒有截斷資料。未確認能用公開介面跳到任意座標，也沒有找到站方公布的結果上限或自動多區域存取及再散布規範。[來源任務頁](https://twpkinfo.com/iquest.aspx) · [站方政策與聯絡方式](https://twpkinfo.com/policy.aspx/)

現階段保留正式更新器和排程。後續驗證需要目標公開地標或區域中心與半徑，以及站方允許的查詢方式、頻率與資料範圍。若允許切割視窗，需要以實際送出的矩形聯集檢查圓形覆蓋，並確認回應完整性，才可替換該區的舊資料。使用者定位仍由前端本機篩選。

### 高雄設定唯讀試跑

`config/area.json` 可正常讀取，包含高雄鳳山及高雄楠梓，各半徑 5 公里。全新 Chromium 開頁後，原站在台北的初始視窗回傳 1,643 筆有效資料。兩個目標中心都在視窗外，回應內沒有落在任一目標圓內的記錄。載入時沒有可見的搜尋輸入框或下拉選單可直接跳轉。這次沒有驗證高雄的即時結果，也沒有寫入快照。

本機既有 `quests.json` 依直線距離計算，鳳山圓內有 834 筆、楠梓圓內 0 筆。這是既有檔案的點位統計，無法證明任何一區的完整覆蓋。

## 重跑診斷

```powershell
python -m pip install playwright==1.65.2
python -m playwright install chromium
python scripts/probe_playwright.py
python scripts/probe_playwright.py --headed
```

若需要觀察一次普通的地圖放大操作，可加 `--zoom-once`。診斷只輸出階段、HTTP 狀態、筆數與分類，不保存回應本體或瀏覽器狀態。地圖、更新器、GitHub Actions 和任務資料均未改動。

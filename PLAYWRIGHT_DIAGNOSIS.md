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

## 重跑診斷

```powershell
python -m pip install playwright==1.65.2
python -m playwright install chromium
python scripts/probe_playwright.py
python scripts/probe_playwright.py --headed
```

若需要觀察一次普通的地圖放大操作，可加 `--zoom-once`。診斷只輸出階段、HTTP 狀態、筆數與分類，不保存回應本體或瀏覽器狀態。地圖、更新器、GitHub Actions 和任務資料均未改動。

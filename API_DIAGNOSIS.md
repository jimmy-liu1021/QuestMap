# 爬報寶貝任務 API 診斷

2026-11-20（台灣時間）

## 現有請求方式與七項問題

| 問題 | 結果 |
| --- | --- |
| 1. 使用的客戶端 | `scripts/probe_api.py` 使用 Python 標準函式庫 `urllib.request`，每次新建 opener 並發出一次 GET。GitHub Actions 呼叫同一腳本。 |
| 2. 是否先造訪任務頁 | 沒有。也沒有設定 Cookie jar 或初始化網站 Session。 |
| 3. Playwright 是否真的開頁 | 專案沒有使用 Playwright，亦沒有使用 `APIRequestContext`。 |
| 4. Playwright 頁面是否能顯示任務 | 未執行。 |
| 5. Playwright Network 是否取得有效 `fp` | 未執行。使用者回報的一般 Chrome 成功紀錄是另一個測試。 |
| 6. Codex 的確切失敗 | HTTP 200，成功解析 JSON，`fp` 有一筆，未通過任務欄位驗證，分類為 `invalid_row`。本次匿名回應未命中已知 `error2` 標記。 |
| 7. Session、參數、環境、IP 的證據 | 完整 Chrome 請求與裸 GET 同時有多個差異，沒有獨立變因測試，也沒有不同環境下的等價請求對照。 |

## 實際測試

| 測試 | HTTP 狀態與標頭 | 大小與結果 |
| --- | --- | --- |
| Python 全新匿名裸 GET | 200，`application/json`，無 `Content-Encoding` | 65 bytes，JSON，`fp` 1 筆，`invalid_row`。早先的唯讀檢查亦得到同類結果，座標合法且任務與獎勵碼完整的列為 0。 |
| 歷史 `response.bin` 唯讀檢查 | 本次只使用 body，HTTP 狀態與標頭無法由檔頭復原 | 42,415 bytes，檔頭辨識為 GZIP，解壓後 157,774 bytes，834 筆通過驗證。 |
| 使用者回報的簡化 cURL | 未獨立重跑 | 使用者提供的 JSON 中有 `error2`。該請求與本次裸 GET 設定不同，兩個結果分別記錄。 |
| 最新完整 cURL 對照 | 未執行 | 最新成功對照來自正常 Chrome 操作。 |
| 最新正常 Chrome 操作 | 使用者從 DevTools 回報 200，`application/json; charset=utf-8`，`gzip` | 已解壓的 `response.latest.json` 為 67,323 bytes，`fp` 有 204 筆，全數通過驗證。僅驗證回應本體，未重播瀏覽器請求。 |
| 診斷器本機分類 | 9 個合成案例通過 | 涵蓋純文字與 JSON 內的 `error2`、空陣列、無效列、HTML、損壞 JSON／GZIP、一般與 GZIP 任務資料。 |
| 既有更新器本機端到端 | 3 組測試通過 | 明文／GZIP 成功寫入，唯讀檢查保留原檔，各種失敗保留原檔並遮蔽輸入。 |
| Requests 與 Playwright 實測 | 未執行 | Requests 可用 Cookie jar 保留伺服器設定的 Cookie，但不執行頁面 JavaScript。完整 Playwright 頁面可執行 JavaScript；其 APIRequestContext 僅發送 HTTP。現有證據未確認需要哪種方式。 |

## error2 的證據與限制

| 變因 | 目前證據 |
| --- | --- |
| `ASP.NET_SessionId`、`_uid` | 使用者觀察到成功請求含這兩個 Cookie，而簡化請求缺少 Cookie。同時還有其他請求差異。站方隱私權政策只說明 Cookie 可能影響部分功能，沒有說明此端點的要求。 |
| `Referer`、`X-Requested-With` | 存在於使用者的成功樣本。各欄位是否必要未驗證。 |
| `f`、`g` | 使用者觀察到原站請求包含這兩個參數。正常初始化何時產生它們、它們是否有時效或與 Session 綁定，均未確認。 |
| 地圖範圍與其他參數 | 裸 GET 沒有範圍和其他查詢條件，也可能影響結果。沒有站方規格可判定。 |
| IP、執行環境與反自動化 | 沒有等價對照。這次收到 HTTP 200，因此只能確認回應沒有有效任務。 |

公開任務頁與隱私權政策未說明供本專案無人值守擷取的介面。自動重播完整 cURL、移除可能涉及存取控制的欄位逐項試探，以及 Playwright 初始化均未執行。[來源任務頁](https://twpkinfo.com/iquest.aspx) · [隱私權政策與站方聯絡方式](https://twpkinfo.com/policy.aspx/)

## GitHub Actions 可行性與下一步

本機測試證明更新程式能處理正常及異常回應。目前沒有全新 Session 能取得有效資料的證據，必要參數的正常取得方式、是否需要瀏覽器或人工操作、Cookie 期限及 Ubuntu Runner 的來源端到端可用性都未驗證。每日排程繼續停用，地圖可使用現有快照與手動匯入。

向站方索取正式 API 或匯出方式，確認無人值守使用、頻率及再發布權限。取得站方允許的機器端點後，先本機執行 `probe_api.py --check`，再從 Runner 手動驗證。若站方允許自動化瀏覽並指定正常流程，再評估以完整瀏覽器觀察該流程的回應。

若只需補一筆最新的成功對照，可提供從正常 Chrome 操作取得的純回應 body，以及另外記下的 HTTP 狀態、Content-Type 和 Content-Encoding。保留 Cookie、完整 cURL、含動態參數的 URL 及 HAR 在你的瀏覽器或本機。工具可用以下命令驗證對照資料。

```powershell
python scripts/diagnose_api.py --body response.bin
python scripts/diagnose_api.py --anonymous
```

診斷器只輸出回應摘要，不寫任務檔。現有更新器、GitHub Actions 及地圖程式未修改。

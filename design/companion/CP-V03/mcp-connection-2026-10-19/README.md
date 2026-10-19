# MCP 安裝與真 stdio 測試

已將使用者提供的 CubismExternalEditMCP 固定在 commit `863ebc87d0feafd841cf3877b16f0311047b9448`，安裝至獨立 Python 3.12 環境 `/home/jasonliao/.local/share/siro-cubism-mcp/venv`；沒有修改 Siro production code 或全域 Codex 設定。

真 MCP client → server 已完成 initialize、tools/list（42 個）與 cubism_status 呼叫。`stdio-probe.json` 是實際回應：connected／registered／approved／edit_approved 均 false。服務能執行，不等於已連接 Editor，更不等於可完成 5.4 專用建模或匯出。

`requirements-resolved.txt` 固定本輪實際解析的套件版本。serverInfo.version 回報的是 FastMCP／MCP 框架版本 1.30.0；Cubism MCP 套件版本為 1.0.3，見 receipt，兩者不能混用。

使用者需在現有 Editor 開啟 File → External Application Integration Settings → Use（預設 22033），連線時於 Editor 授權 Allow；只有支援編輯 API 且提供 Edit 的版本，才可再授權 Edit。目前尚未發生成功註冊，不記錄 token，也未繞過 Editor 的授權。

本輪另啟動最長 10 分鐘的 stdio 連線觀測，若接通且獲准，只查 documents 並保存本機結果，不自動修改模型。live 結果在 `/home/jasonliao/.local/share/siro-cubism-mcp/connection-monitor-latest.json`；過期後需重新查程序狀態，不能以此文件假定監測仍執行。

官方主下載 JS 現為 5.3.04（另有 5.3.05 beta1）；先前 S3 備援仍為舊 5.2.03。這項新證據修正版本盤點，但不證明 5.3 支援 5.4 Alpha 編輯 API。本輪未為此盲目升級現有已啟動 Editor。

CP-V03 的 PSD 匯入、cmo3/can3 保存重開、moc3 與 motion 匯出、兩次真 renderer 播放仍待實測。

## 已連線後的直接 API 核對

使用者開啟 Use／Allow 後，真實連線與註冊成功。`editor-api-readback.json` 保留獨立核對的原始 API 回應：

- `GetIsApproval` → `Result: true`。
- `GetDocuments` → 三類文件皆空，目前無模型或動畫工程。
- `GetCurrentEditMode` → 空字串。
- **`GetIsEditApproval` → `ErrorType: MethodNotFound`**。

這修正前面的歸因：本機 5.2.03 沒有該編輯授權方法，不能要求使用者尋找或勾選不存在的 Edit 欄位。上游 cubism_status 對該錯誤使用 `.get("Result", False)`，導致 unsupported 被呈現為 edit_approved=false；原始 MethodNotFound 比此布林值更能說明限制。未更動第三方程式。

MCP 服務已完成接通；PSD 匯入、建模與工程保存／匯出仍未完成。需要原生視窗操作方式或有效且支援所需編輯 API 的 Editor。已再次提供「使用者明確指定 xdotool」或「使用者操作、代理驗證」選項，沒有把 API 接通計為 V03 DONE。

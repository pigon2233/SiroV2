# 使用者提供的三個 MCP 專案：CP-V03 適用性

核對日期：2026-10-19 Asia/Taipei。僅閱讀來源並測本機 loopback 連線，未安裝或執行第三方 MCP，未更動 Editor 授權／設定。

| 專案／核對 commit | 實際範圍 | 對 V03 的判定 |
| --- | --- | --- |
| J621111/live2d-automation `4ad77c555165e1ba02bd68e0db7299d5f4fe0327` | 影像／素材 pipeline；預設 mock intermediate moc3；另有需校準的 Windows GUI controller | 不能把預設 export 當作真 Cubism 匯出。Windows PowerShell 控制器未經 Wine 驗證。 |
| nana7chi/CubismExternalEditMCP `863ebc87d0feafd841cf3877b16f0311047b9448` | 真 Editor WebSocket API：既有參數讀寫；5.4 Alpha 的參數／部件／變形器／ArtMesh 等編輯 | 三者中最接近所需。現有 5.2.03 不提供該專案要求的完整 5.4 編輯介面；工具列表未提供 PSD 開啟、工程保存或 moc3 匯出的 action。 |
| Mitscherlich/live2d-mcp `69726142a897d498c47139e2e15e41fa805e6916` | Electron 角色播放器、表情／動作／視線／參數與視窗控制 | 控制已匯出的角色，不能取代建模與工程匯出。 |

## 本機與官方條件

- 原 Wine Editor 視窗為 `Live2D Cubism Editor 5.2.03 FREE version`。
- `127.0.0.1:22033` TCP connect_ex=111（connection refused）。這只證明此刻沒有可連線的預設 API 端口，不能推論 Wine 永遠無法使用 API。
- nana7chi README 的 Alpha1 到期日為 2026-09-14；官方更新公告說明 Alpha2 延至 2026-10-18 23:59 JST，現在亦已過期。沒有測試以變更系統日期等方式延長使用。
- 本輪未確認可用的繼任 Beta／正式版，因此沒有下載過期 Alpha 或宣稱 MCP 已接通。
- 官方既有 API 的 `NotifyMocFileExported` 是匯出事件通知，不是觸發匯出的命令。不能以訂閱通知代替完成匯出。

後續若取得有效且支援編輯 API 的版本，優先測試 nana7chi 路徑；仍須另驗 PSD 匯入、cmo3/can3 保存重開、atlas/runtime 匯出與兩次真 renderer 播放。現有測試 PSD 保留，不改用 mock 完成 gate。

## 來源

- [live2d-automation README](https://github.com/J621111/live2d-automation/blob/4ad77c555165e1ba02bd68e0db7299d5f4fe0327/README.md)
- [CubismExternalEditMCP 工具源碼](https://github.com/nana7chi/CubismExternalEditMCP/blob/863ebc87d0feafd841cf3877b16f0311047b9448/cubism_mcp.py)
- [live2d-mcp README](https://github.com/Mitscherlich/live2d-mcp/blob/69726142a897d498c47139e2e15e41fa805e6916/README.md)
- [官方 Alpha 公告與期限](https://www.live2d.com/en/information/cubism-5_4-alpha/)
- [官方外部 API 指令／事件](https://docs.live2d.com/en/cubism-editor-manual/external-application-integration-api-list/)

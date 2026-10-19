# Cubism 工具鏈：目前驗收狀態

2026-10-19。**LOCAL_VERIFIED；遠端交付待重新登入 GitHub。** 原先僅 Wine 啟動、MCP 連線或工程存在的間接證據，已補上真 Editor 修改／再匯出／真 SDK 畫面比較，見 [完整驗收](roundtrip-verification-2026-10-19/README.md)。

## 實際路徑

使用者確認只有 Linux，要求用 Wine，並明確授權 xdotool。依這個指示，以官方 Windows 版 Editor 5.2.03 FREE＋Wine 10＋Xvfb :93／twm 操作；未使用付費 PRO／試用、未要求另找 Windows 主機，未宣稱官方支援 Linux。原生 Windows／macOS 與實體 GPU 尚未驗。

工程輸入：自有兩層 RGB8／sRGB PSD。輸出：可編輯 cmo3／can3、1024 atlas PNG、moc3（moc version5）／model3／cdi3／motion3。第一版 Angle X 動作 0→30→0，第二版在 Editor 改中間 key 為 15 後另存及匯出，0→15→0。第二版只有動畫修改，moc3 與 atlas hash 應保持相同。

隔離驗證使用本機已存在 Cubism SDK Web 5-r.5／Core6.0.1，Framework renderer 與 SDK motion manager 真播放。Node／browser Core 頂點相同、alpha／draw order 正負例、底圖靜止與標記移動、循環邊界及停止後穩定均驗。各版19項、比較8項，原始 JSON／畫面／未編譯驗證 source 均歸檔，沒有提交 SDK 或編譯產物。

## 可自動與人工操作

| 步驟 | 已驗能力與責任 |
| --- | --- |
| 自有 PSD／素材檔驗證、檔名／hash／manifest | 可離線自動驗證；素材／來源由 Codex 負責 |
| Editor 匯入、mesh／參數編輯、保存重開 | 真 GUI 已操作；隔離 X11 可由已授權 xdotool 驅動，需逐步看畫面，不能當穩定 batch API |
| atlas、moc3／motion3 匯出 | 真 Editor menu／dialog 已操作；兩版原始輸出可核對 |
| Core consistency、SDK WebGL／motion manager 播放 | 可用 Claude 編寫的隔離工具自動重跑；未接 production |
| alpha／draw order／位移與兩版差異 | 真畫面 pixel 與 Core 頂點交叉檢驗，含錯誤上傳／順序負例 |
| 造型、補圖、全身 rig／自然度 | 仍需美術／Editor 製作與人工視覺驗收；CP-V04 未完成 |
| MCP 自動編輯 | 5.2.03 已測 GetIsEditApproval=MethodNotFound；不能把連上 port 當已支援編輯 |
| production loader／宿主／動畫接線 | Claude 負責，未在本輪修改 |

SDK 不自動採用 motion Meta.Loop，工具明確呼叫 SDK `setLoop`；SDK 更新下 2.5 秒的參數較理想對稱曲線有約1.5／0.75差值，已保留。證據只支持基本播放與循環邊界連續，不支持全身動作自然度／精確相位／正式效能。

## 來源與歷史證據

- [官方系統需求](https://www.live2d.com/cubism/download/spec/)；Windows／macOS 為官方平台。本機是使用者選定的 Wine 實測替代路線。
- [官方檔案類型](https://docs.live2d.com/en/cubism-editor-manual/file-type-and-extension/)／[runtime 匯出](https://docs.live2d.com/en/cubism-editor-manual/export-moc3-motion3-files/)／[PSD 注意事項](https://docs.live2d.com/en/cubism-editor-manual/precautions-for-psd-data/)。
- [Wine 啟動證據](wine-2026-10-19/README.md)、[兩層 PSD](roundtrip-fixture/0.1.0/README.md)、[MCP 連線與 API 限制](mcp-connection-2026-10-19/README.md)、[當時暫停點](editor-checkpoint-2026-10-19/README.md)。這些文件的未完成狀態屬歷史；目前結果以本頁與完整驗收為準。

跨機請取得 source 與 runtime 全部檔案並核 hash；can3 若仍指向本機 `C:\siro-v03\roundtrip.cmo3`，以 Editor 重連所附 cmo3，不能從 moc3 反推可編輯原稿。舊可用角色完全不替換。

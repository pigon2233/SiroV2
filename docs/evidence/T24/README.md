# T24 驗收證據

日期：2026-09-25｜結果：PASS（Linux Chrome L2 + visible L3；任意 Wayland desktop UI unsupported）

- `ScopedBrowserDriver` 使用系統 Google Chrome，支援受限 origin 的 navigate/read/fill/click/key/
  pointer/screenshot。每次動作綁定 SHA-256 screen version；DOM 或輸入值變更後舊 target
  立即失效，必須重新 observe/select。
- Playwright request routing 對每個請求禁止自動 redirect，先檢查 `Location`；跨 scope 的直接
  URL、redirect 與 subresource 在送出前阻擋。語意 target 必須唯一且可見。
- 合成網站 integration test 以真 Chrome 完成表單、key、semantic click、coordinate pointer、
  state readback、stale target、scope/redirect 拒絕與 screenshot。
- `VisionModel` port 輸出 description、source、confidence、width、height。本機
  `PixelScreenAnalyzer` 實際分析 PNG，但只宣稱尺寸、亮度與粗略主色；無效影像明確失敗，
  不產生可盲點擊的座標。Groq 帳戶當前列出的模型沒有 vision model，cloud vision 明示
  unavailable。
- `uv run python scripts/t24_visible_browser_demo.py` 在 GNOME Wayland 上開啟可視 Google
  Chrome，完成 `Saved T24 verified` 讀回；1280×720 screenshot 回報
  `dark screen; blue is the largest coarse colour bucket`，confidence 0.9957。
- 任意 GNOME/Wayland 視窗、全桌面 key/pointer 沒有安全可用 driver，能力表標為 unsupported；
  browser DOM 成功不外推為所有桌面程式可控。Windows/macOS 未驗證。

證據：`tests/integration/test_browser_driver.py`、`scripts/t24_visible_browser_demo.py`、
`docs/PLATFORM_CAPABILITIES.md`。

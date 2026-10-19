# V03 保留點：使用者改做 Blender／VRM 小樣

**歷史保留點；後續 active V03 續作已補第二輪匯出與真 SDK 播放，見 [新驗收](../roundtrip-verification-2026-10-19/README.md)。以下為當時狀態。**

2026-10-19，使用者明確選擇「先保留 V03，改做 Blender／VRM 風格小樣」。原目標已暫停，整卡未完成。

已由真正的 Editor 操作完成：兩層 PSD 匯入、透明背景、標記 draw order 501／底圖 500、標記自動 mesh、Angle X 三鍵、cmo3 保存、1024 atlas、SDK 5.0 moc3／model3／texture 匯出；can3 保存、關閉全部後重開，2 秒／30 fps／61 frames，motion3 曲線為 0→30→0。第一次匯出的首尾錯位已在 Editor 修正後重匯出。

第二輪已重開 can3 並將第 30 幀的值從 30 改為 15，另存 roundtrip-v2.can3；尚未完成第二輪 runtime 匯出與兩版比較。renderer 委派 Claude CLI 仍未交完整驗收結果；保留其暫存成果，不計為播放成功。

來源與真匯出檔保存於 `assets/companion/siro-original/toolchain-roundtrip/0.1.0/`；manifest 提供 hashes。source 內兩份工程應放同一資料夾；若 Editor 要求找模型，可指定旁邊的 roundtrip.cmo3。原本可用路徑為 C:\siro-v03\roundtrip.cmo3。未對角色原稿做完整 rig，此測試件不能當角色模型。

xdotool 在原 Wayland 桌面未成功輸入；改用隔離的 Xvfb :93＋twm＋Wine prefix 後成功。不依賴假模型，沒有修改 Siro production code。使用者現在要求先做 3D 風格比較，故保留現況，後續重啟 V03 時仍需重驗工程載入、真 renderer、第二次匯出與差異。

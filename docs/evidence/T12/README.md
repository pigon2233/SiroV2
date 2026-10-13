# T12 驗收證據

日期：2026-09-25｜結果：PASS（L1 + local L2）

Owner 從官方下載並接受 Live2D Proprietary Software、Open Software 與 sample material 適用條款。使用 `CubismSdkForWeb-5-r.5.zip`，SHA-256 `67064a7fb1812cf502f5c4a03bfe12cc638c75a621bb4acf06bb28763df06ba0`；ZIP 完整性無錯誤。專有 SDK/Core/Haru 留在 Git ignored `models/`。

本機 manifest `live2d.cubism-web-5-r.5-haru` 驗證 Core 與 Haru 共 56 個檔案的來源、授權接受時間和 SHA-256。`BodyAssetManifest` 拒絕 path escape、缺檔及竄改。

真實 TypeScript SDK sample 通過 `tsc --noEmit` 與 Vite build。FastAPI 只在設定 `SIRO_LIVE2D_DIST` 時掛載 `/live2d`；瀏覽器實際載入 Cubism Core、WebGL shaders、Haru moc3、textures、expressions、motions、physics、pose 與 user data。SIRO bridge 將 emotion、gesture、look、speech mouth 與 generation-bound cancel 映射到真模型，並經認證 `/ws/body` 連線。

A07：將真 renderer 導離後，故障隔離測試確認文字 turn 完成、SQLite source-backed memory 可回憶；回到 `/live2d/` 後模型與 WebSocket 重新載入。單 owner/writer、有界 queue、舊 generation 丟棄與慢 renderer 不阻塞 Core 的 deterministic tests 同時通過。

發布限制：本證據只涵蓋本機開發與驗收。若公開或散布 SIRO，必須依當時用途與組織規模另行確認 Publication License；專有 SDK、Core、模型和私人 acceptance manifest 不提交 Git。

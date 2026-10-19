# CP-V03：全身設計與工具鏈

2026-10-19 Asia/Taipei。**LOCAL_VERIFIED／DELIVERY_PENDING_AUTH**：工作卡的外觀規格、分層計畫及最小 Editor 工程往返驗收已通過；尚未推送，完整交付仍待 GitHub 重新登入。CP-V04 全角色 rig 未完成，沒有替換目前角色。

## 外觀與分層

Owner 已接受設定圖 0.2.0 作製作基準。圖含正面、左右側面、背面、坐姿與三個表情，見 [目前設定圖](references/0.2.0/siro-concept-sheet.png)。Owner 曾指出縮胯修訂看起來差異不明顯，本卡不宣稱該問題已有明顯改善。

- [DESIGN.md](DESIGN.md)：成年女性、比例目標、角色自身左右、服裝／色票、站坐參考與一致性限制。
- [LAYERING.md](LAYERING.md)／[layer-plan.csv](layer-plan.csv)：80 個唯一分件 ID 的切件／補圖／遮擋計畫，並非 80 張已畫好的素材。
- [concept-artifact.json](concept-artifact.json)／[PROMPT-0.2.0.md](PROMPT-0.2.0.md)：設定圖生成來源、尺寸與 hash。原始參考為 Git tracked PNG，可隨分支取得。
- [material-study/README.md](material-study/README.md)：額外分層材料試作。舊髮組錯誤挖出耳朵輪廓已作廢；較新版本補全後髮。試作沒有當成正式 rig。

## 真工程往返驗收

[完整證據與重現命令](roundtrip-verification-2026-10-19/README.md)／[要求逐項稽核](roundtrip-verification-2026-10-19/completion-audit.json)。

Windows 版 Cubism Editor 5.2.03 FREE 經使用者指定的 Wine 路徑，在 Linux／隔離 X11 中完成自有雙層 PSD 匯入、mesh／Angle X 編輯、cmo3／can3 保存、關閉重開、atlas 與 moc3／motion3 匯出。重新開工程把動畫峰值 30 改為 15，再匯出並重新開啟確認保存值。

兩版均由真正 Cubism Core／SDK Framework WebGL renderer 與 CubismMotionManager 播放：各 19 項檢查 PASS，版本比較 8 項 PASS。1 秒時 ParamAngleX 為 30／15，畫面標記位移為 64／32 px，底圖不動。可編輯工程、原始匯出及 hashes 在 `assets/companion/siro-original/toolchain-roundtrip/0.1.0/` 與 `0.2.0/`。

[首版 SDK 播放](roundtrip-verification-2026-10-19/v1-final-sdk-playback.gif)／[修改後 SDK 播放](roundtrip-verification-2026-10-19/v2-final-sdk-playback.gif)。測試件是兩個自有矩形，不是 SIRO 的全身模型。不能把工具鏈通過擴大為 V04 rig／步行／坐下完成。

## 自動化、限制與交接

[TOOLCHAIN.md](TOOLCHAIN.md) 列出可自動與必須操作 Editor 的步驟。軟體 WebGL 通過，未驗實體 GPU／原生 Win 或 macOS；SDK 循環的取樣相位差保留為 finding，沒有宣稱自然度或完全精確循環。測試程式由 Claude CLI 撰寫，僅保存隔離驗證 source；沒有改 production renderer、宿主或共享 STATUS／TASKS。

[先前暫停點](editor-checkpoint-2026-10-19/README.md) 是歷史狀態；本輪 active V03 續作完成其第二輪匯出／播放缺口。另行探索的 [Blender 風格粗模](../blender-style-study/0.1.0/README.md) 保留，沒有用它代替本卡的 Live2D 驗收，也未決定替換正式工作流。

下一步是完成遠端分支交付；造型／完整活動 rig 屬 CP-V04，不自動啟動。回退只撤本卡 owned design／fixture 資產；現有 Haru、身份／記憶／聲線與 production 接線均未更動。Owner 指定直接推既有 branch、自行合併；不再建立 PR，不合併 main、不部署。

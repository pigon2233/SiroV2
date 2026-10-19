# CP-V03 Editor 往返與真 SDK 播放驗收

2026-10-19 Asia/Taipei。**LOCAL_VERIFIED；分支遠端交付待 GitHub 重新登入。** 這是 CP-V03 的小工程工具鏈驗收，不是 CP-V04 的全角色 rig。

## 已執行的工程操作

使用者只有 Linux，並明確要求用 Wine、xdotool 完成 V03；依此以 Windows 版 Cubism Editor 5.2.03 FREE＋Wine 10＋Xvfb :93／twm 實測，取代另找 Windows／macOS 實體主機的前置條件。未宣稱官方支援 Linux，也未驗原生 Windows／macOS。

1. 原始自有 RGB8／sRGB 雙層 PSD 匯入，保留透明與重疊；標記 draw order 501、底圖 500，標記自動 mesh；模型 Angle X 的 -30／0／30 三鍵已有可見變形。
2. 保存 `roundtrip.cmo3`，建立 2 秒、30 fps、61 frames 的 can3；保存、關閉所有文件、重新開啟，修正原先首尾錯位後匯出 0→30→0 的 motion。首輪保存點見 [先前紀錄](../editor-checkpoint-2026-10-19/README.md)。
3. 以 Editor 的 1024 atlas／SDK5 匯出 moc3、model3、cdi3、texture、motion3。沒有偽造二進位模型，沒有以手寫曲線代替 Editor 匯出。
4. 重新開 can3，把第 30 幀從 30 改為 15，另存 `roundtrip-v2.can3`；再由 Editor Export For Runtime → motion3 匯出。第二版只改動畫，因此模型、貼圖及其他模型引用刻意沿用首版；motion3 的 digest 不同。
5. 第二版匯出後再次 Close all → Open `roundtrip-v2.can3` → 第 30 幀，UI 值仍為 15，見 `siro-v03-reopened-v2-key15.png`。另重開 cmo3，Angle X 0／30 時標記位置不同，見 `siro-v03-model-reopened*.png`。原始工程檔沒有因驗證姿勢被覆寫。

可編輯工程與 Editor 原始輸出：`assets/companion/siro-original/toolchain-roundtrip/0.1.0/` 及 `0.2.0/`。各版 manifest 列出每檔大小與 SHA-256。動畫工程在本機引用 `C:\siro-v03\roundtrip.cmo3`；跨機載入時將 cmo3／can3 放同資料夾，Editor 如要求找模型，指定所附 `roundtrip.cmo3`。不要假定 can3 在任意新路徑會自動重連。

## 真 renderer 結果

Claude CLI 實作隔離測試工具；Codex 核對原始輸入、程式路徑、報告與實際渲染畫面。使用本機已存在且合法取得的 Cubism SDK for Web 5-r.5／Core 6.0.1，moc version 5。Core 載入檢查、SDK Framework renderer 與 CubismMotionManager 均真實執行；不是 SVG 動畫，也不是手動設參數冒充 motion 播放。

Headless Chrome 154.0.8037.92、ANGLE／SwiftShader、WebGL1、512×512。兩版各 **19 個報告檢查** PASS，兩版比較 **8 個** PASS。Claude 摘要曾寫 21 checks；以實際 JSON 的 19 個為準（每版另有 21 張主要截圖）。

| 證據 | 首版 | 第二版 |
| --- | --- | --- |
| SDK 1 秒時 ParamAngleX | 30 | 15 |
| 0 秒→1 秒標記中心 x | 268→332 px | 268→300 px |
| 實際水平位移 | 64 px | 32 px |
| 主要動作取樣的底圖差異 | 0 pixels | 0 pixels |
| 首尾 0／2 秒 ParamAngleX | 0／0 | 0／0 |
| moc3／texture hash | 兩版相同 | 兩版相同 |
| motion3 hash | 與第二版不同 | 與首版不同 |

`v1-final/report.json`／`v2-final/report.json`：Core 與 Framework consistency、mesh 索引、Node／browser 相同頂點、底圖靜止、標記移動、alpha、draw order、SDK motion parse／播放／loop 邊界／停止穩定，以及 browser errors。透明區隨背景色改變而實色區不變；錯誤 straight-alpha 上傳與逆向 draw order 的負例均可被檢出。

`comparison.json`：重新計算輸入 hash，核對相同模型／貼圖、不同 motion 峰值、SDK 實測值、底圖與畫面位移。`v*-final-sdk-playback.gif` 各由同次 SDK 播放的 23 張原始截圖組成，涵蓋 0–2.2 秒；每 6 個 1/60 秒更新取樣一次。GIF 自身重播不是 SDK 循環驗收依據，報告另有跨 2 秒邊界的逐幀取樣。

## 限制與操作邊界

- SDK loader 不自動套用 Meta.Loop；測試以 SDK `setLoop(meta.loop)` 明確設定，`setLoopFadeIn(false)`。首輪有 SDK 預設 1 秒 fade-in。更新皆由 motion manager 執行。
- loop 邊界無突跳，但第二循環 2.5 秒讀回 13.503／6.7515，與對稱曲線理想 15／7.5 有相位差。此 finding 保留，僅驗「可播放與邊界連續」，不宣稱精確相位／自然動作品質；不能把本證據擴大成 V04 活動驗收。
- 軟體 WebGL 通過，實體 GPU 驅動、效能／記憶體預算、production 宿主接線、真人活動自然度均未驗。
- PSD 匯入、mesh／參數編輯、保存重開、atlas 與匯出，仍由真 Editor 操作。此環境可用已授權的 xdotool 操作隔離 X11；不是穩定的 headless 建模 API。MCP 5.2.03 缺少編輯 API，詳見既有 connection 紀錄。
- 可自動重跑部分：hash、檔案引用、Core 檢查、WebGL 播放取樣、pixel／差異驗證。造型審核、分層補圖與 rig 品質仍需美術檢視。

## 重現命令

只保存自有未編譯驗證程式於 `harness/`；**不提交 SDK Core、Framework 或編譯 build**。工具會在執行前清空指定 `--out`，請使用專屬暫存目錄。`CUBISM_SDK` 可指定合法 SDK 根目錄；本機 Node modules 路徑及 Chrome 路徑見 source，跨機需按自己的環境配置。此工具不是 SIRO production renderer。

在 repo 根目錄（以下 `node` 指本機 bundled Node）執行：

```bash
node design/companion/CP-V03/roundtrip-verification-2026-10-19/harness/run.cjs --model assets/companion/siro-original/toolchain-roundtrip/0.1.0/runtime/roundtrip.model3.json --motion assets/companion/siro-original/toolchain-roundtrip/0.1.0/runtime/roundtrip.motion3.json --expected-peak 30 --preview --out /tmp/siro-v03-v1-verify
node design/companion/CP-V03/roundtrip-verification-2026-10-19/harness/run.cjs --model assets/companion/siro-original/toolchain-roundtrip/0.2.0/runtime/roundtrip.model3.json --motion assets/companion/siro-original/toolchain-roundtrip/0.2.0/runtime/roundtrip.motion3.json --expected-peak 15 --preview --out /tmp/siro-v03-v2-verify
node design/companion/CP-V03/roundtrip-verification-2026-10-19/harness/compare.cjs --v1 /tmp/siro-v03-v1-verify --v2 /tmp/siro-v03-v2-verify --v1dir "$PWD/assets/companion/siro-original/toolchain-roundtrip/0.1.0/runtime" --v2dir "$PWD/assets/companion/siro-original/toolchain-roundtrip/0.2.0/runtime" --out /tmp/siro-v03-comparison.json
```

實測執行使用相同未編譯 source 於 `/tmp/siro-v03-renderer`，輸出至 `out/v1-final`／`out/v2-final`，隨後歸檔；報告保留原始絕對路徑與 timestamp，不冒充歸檔後另一次執行。測試自建 browser/server 於 finally 關閉。GitHub HTTPS 缺憑證，Connector 明確回覆 requires reauthentication，尚未推送；不重試 PR，不合併或部署。

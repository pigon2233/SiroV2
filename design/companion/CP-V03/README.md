# CP-V03：原創全身設定草案與工具鏈前置

2026-10-18 Asia/Taipei。**外觀 0.2.0 ACCEPTED；CP-V03 整卡 PARTIAL，Editor 往返 BLOCKED_EXTERNAL。**
本卡最初 source parent：f58c4d4；延續 design/companion-cp00-20261018。
Owned paths 僅 design/companion/CP-V03/；保留既有 TASKS.md dirty 修改，不改 production 或使用中 Haru。

## 已交付

- 一張新生成的原創 SIRO 設定候選：正面 A pose、左右側身、背面、坐姿與三種表情。
- [DESIGN.md](DESIGN.md)：角色、比例、朝向、服裝與色票；逐項檢視與待修處。
- [LAYERING.md](LAYERING.md)／[layer-plan.csv](layer-plan.csv)：80 個唯一命名分件的計畫、遮擋與補圖規則；不是 80 張已畫素材。
- [TOOLCHAIN.md](TOOLCHAIN.md)：Editor 環境證據、官方規格、最小工程往返實驗及未完成項。
- [PROMPT.md](PROMPT.md)：built-in image_gen.imagegen 的完整原始生成 prompt，無輸入圖。
- [concept-artifact.json](concept-artifact.json)：原圖版本、尺寸、hash、來源與存放／取得方式。

### 0.1.0 歷史原圖（當前修訂請見文末 0.2.0）

初稿為 1536×1024 PNG、1,780,151 bytes。當時的專案本機檔：
`design/companion/CP-V03/artifacts/0.1.0/siro-concept-sheet.png`。
原圖以版本化本機 artifact 保存，artifacts/ 被本目錄 .gitignore 排除，尚未上傳共享儲存。
另一台電腦須轉移原圖並驗 hash，不能只靠 pushed 文件宣稱已取得視覺資產。

## Gate 與限制

Owner 已接受 0.2.0 為外觀製作基準；先前初稿待確認的紀錄保留於歷史。
V01 真音訊／實機與 V02 P01 接線仍未完整驗收，本卡不解除它們。
本卡「外觀草案先給使用者看，再大量製作」的外觀確認已取得；Editor 與 rig gate 仍保持。
這個確認來自本專案 CP-V03 工作卡，不是 ImageGen 工具額外要求。

未確認 Windows／macOS Editor 主機，未產 cmo3／can3／PSD，也沒有新的 moc3。
官方支援平台與來源在 TOOLCHAIN。概念圖不是可播放 Live2D 模型；CP-V03 不標 DONE、CP-V04 未開始。

本輪文檔／CSV／圖檔 hash 和尺寸檢查可重現；沒有跑 production unit／integration／硬體或 Editor 往返測試。
本卡僅生成一張候選與製作規格，未換模型、改身份／記憶、安裝軟體、重啟服務或部署。

回退：撤本卡文件 commit；本機生成圖依 receipt 保留或移除，舊模型與原圖 source 不受影響。
下一步：依已接受外觀細化分層精稿，確認可用 Editor 主機／版本，完成最小工程往返。

## 同步紀錄

草案／規格 commit `001be614690c5a33a0902615647ba928c606137e` 已推送。
本輪建立 Issue 與 Draft PR 均回 403 `Resource not accessible by integration`；沒有遠端認領或 PR URL。
狀態 PUSHED／BLOCKED_PR，原圖仍僅為本機 artifact；未合併 main、未發訊息到另一 AI 聊天。


## 最新修訂 0.2.0

Owner 指出正面臀胯外擴過大；已用內建 ImageGen 編修原圖，收窄下身輪廓並改較直筒的短褲，
各視圖保持同一角色與服裝。當前圖稿：
[SIRO 0.2.0](references/0.2.0/siro-concept-sheet.png)，完整 prompt 見
[PROMPT-0.2.0.md](PROMPT-0.2.0.md)，digest 見 concept-artifact.json。
先前尺寸／本機 artifact 段落描述的是 0.1.0；歷史 receipt 保留於 concept-artifact-0.1.0.json。
最新修訂 PNG 隨 Git 推送，可以跨機 fetch 取得，不再只放本機 ignored artifact。

Owner 已指定後續直接推 branch，由 owner 自行合併；不再嘗試建立 PR。
此分支的新交付依該指示辦理，既有 PR 403 記錄僅保留為歷史。
Owner 後續已接受這版作外觀基準，並指出修訂差異不明顯；Editor 往返限制保持。

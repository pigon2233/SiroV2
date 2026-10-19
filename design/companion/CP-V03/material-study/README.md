# CP-V03 材料分件試作：站立母稿與頭髮補底

2026-10-18 Asia/Taipei。**頭髮遮擋補底已修正；素材仍為 PROTOTYPE，未完成 rig。**
延續 owner 已接受的外觀方向；本輪 base 235ee6e，owned paths 為本目錄與
assets/companion/siro-original/material-study/。原 TASKS.md dirty 修改保持。

## 本輪具體產出

- 0.1.0：站立正面母稿、頭部母稿、皮膚／耳朵補底、五官分組、舊髮組。
- 0.2.0：完整後髮補底、前髮、角色左／右側髮、獨立左側髮夾；共 5 張新 RGBA PNG。
- 0.2.0 的 head-layered.svg 與 layer-layout.json：7 個可編輯素材群組，保留原 PNG，以非破壞性變換／遮罩對齊。
- 各版本 manifest 逐檔記錄 hash／大小；完整生成 prompt 保存於 PROMPTS.md 與 PROMPTS-0.2.0.md。

最新素材：[0.2.0 manifest](../../../../assets/companion/siro-original/material-study/0.2.0/material-manifest.json)
／[可編輯 SVG](../../../../assets/companion/siro-original/material-study/0.2.0/head-layered.svg)。
SVG 依賴同資料夾 PNG，須整個資料夾取得；它不是內嵌所有圖像的單檔，也不是 PSD／cmo3。

## Owner 指出的耳洞與修正

舊 hair-group.png 抽取了原畫可見髮區，留下耳朵形狀的空洞，不能當作完整可綁定頭髮。
owner 要求暫停後已停止製作；owner 指示繼續後改為先補全後髮，再分前髮／側髮／髮夾。
0.1.0 manifest 明確標 SUPERSEDED／REJECTED，舊檔只作失敗對照與素材來源，不可當完整髮片使用。

新順序：後髮 → 角色左側髮 → 角色右側髮 → 皮膚與耳朵 → 五官 → 前髮 → 髮夾。
後髮在頭皮、臉、耳朵、上頸遮住的區域補成連續髮量；耳朵由皮膚層蓋上，不靠挖洞避開。
側髮也補耳後重疊，未以左右翻轉偷代不對稱髮流。自然外圍捲髮間隙與解剖形耳洞分開看待。

## 已執行 QA

[透明度紀錄](alpha-qa-0.2.0.json)／[疊合預覽](hair-occlusion-qa-0.2.0.png)。

- 8 張 0.2.0 PNG 均為 1254×1254 RGBA，有透明背景與實際圖像 alpha。
- 原角色左耳遮擋取樣框 x920–970／y665–785：舊髮組 alpha≥200 覆蓋約 6.28%，新後髮 100%。
- 臉中央隱藏取樣框 x550–700／y650–870：舊髮組 0%，新後髮 100%。這是兩個局部檢查，不宣稱所有關節都經驗收。
- 用真瀏覽器載入保存的 SVG，棋盤背景顯示後髮與七層疊合；確認不再靠耳形洞避開皮膚。
- 初次疊合發現前髮根部突出邊角；編輯來源將前髮限制在後髮外輪廓 alpha envelope 內。這個遮罩是工程資料，沒有改寫來源 PNG。
- 早期五官圖被生成工具放大；採兩個虹膜像素群重心作相似變換，原圖不重採樣。它只是對齊試作，不能取代所有五官精稿驗收。
- 最初站立母稿直接預覽看似有暗色暈，但取樣顯示外側 alpha=0；RGB 隱藏值不可當作不透明背景證據。額外清理候選未採用。

## 限制與下一步

皮膚／耳朵、五官仍為群組；虹膜、眼皮、口內、上下唇尚未獨立，不能眨眼或做音訊嘴型。
前髮／側髮的局部髮流、露耳量及接縫與母稿仍有差異，須後續精修與 pivot／mesh 驗證，
不把派生素材當作 owner 再次批准的新髮型。剪影遮罩在製作 Editor import PSD 時需明確合層／補畫，不能默認支援。
完整 80 葉件尚未交齊；沒有把 CSV 的 PLANNED 計畫改成 DONE。
沒有 PSD／cmo3／can3／moc3、轉頭變形、物理或 Editor 往返成果，CP-V03 仍 PARTIAL。
使用中的 Haru、production、宿主、音訊與私人資料未改；沒有安裝、啟動或重啟服務。

下一步為五官細拆與衣物／四肢關節補圖；正式 rig 仍需已確認的 Editor 主機／版本。
資料與 PNG 隨分支推送，不再建立 PR，由 owner 自行合併。回退撤本次素材 commit，不影響使用中角色。


## 最新：眼部／嘴部細拆 0.3.0

Owner 已回覆 0.2.0 頭髮批次可接受。續作見 [face-0.3.0/README.md](face-0.3.0/README.md)：
6 張來源圖、15 個獨立片段、24 個 SVG 圖層與 5 個靜態遮擋情境。下眼皮仍只有部分外緣，
未完成獨立 PNG／PSD 葉件、Cubism rig 或音訊嘴型，不沿用先前「不能眨眼」作當前遮擋資料結論，
也不把新的靜態閉眼資料說成已接入實際動畫控制器。

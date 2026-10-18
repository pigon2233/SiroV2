# SIRO 眼部／嘴部細拆試作 0.3.0

狀態：**15 個可獨立定位的圖像片段／24 個頭部圖層群組；靜態遮擋驗證通過，尚非 Cubism rig。**
本輪延續 426436e，保留已通過的 0.2.0 頭髮分件，沒有重新修改頭髮原圖。
owned paths：assets/companion/siro-original/material-study/0.3.0/ 與本目錄；
另更新材料入口文件，原 TASKS.md dirty 修改保留。

## 素材與可編輯來源

- 6 張 1254×1254 RGBA：眼白、完整虹膜、開眼輪廓、閉眼線、口內 atlas、上下唇緣 atlas。
- paired／atlas 原圖不改寫，以 SVG source clip 切成左右眼白／虹膜單元、上下眼皮、閉眼線、口內、牙齒、舌面及上下唇緣；共 15 個獨立定位片段。
- 眉毛與中性閉嘴線沿用原五官素材中的獨立範圍，沒有以整張五官圖重播取代新控制。
- 包含 [head-layered.svg](../../../../../assets/companion/siro-original/material-study/0.3.0/head-layered.svg)、part-layout.json、五個靜態姿態 SVG 與逐檔 SHA-256 manifest。
- [PROMPTS.md](PROMPTS.md) 保存內建 ImageGen 的完整 prompts；中斷前已產出的眼白 PNG 保留續用。

這是保留來源像素的可編輯 SVG 圖層專案，**尚未輸出每個葉件的獨立 PNG／PSD**。
需連同 0.2.0 基礎素材一起取得，因 SVG 以相對路徑引用頭髮、皮膚及原眉毛／閉嘴線。
只有虹膜連同瞳孔／高光作一個可移動單元，沒有將三者各自拆完。

## 遮擋規則

眼白補滿原虹膜遮住的部分；虹膜補成完整圓片。虹膜移動只用位置偏移，
眨眼改開口遮罩與眼皮位置，不改虹膜的垂直縮放。全閉時隱去眼白／虹膜並顯示閉眼線。
左右眼各有自己的遮罩／圖層，能單眼閉合。

口內有完整深色底，不挖牙齒或舌頭形狀的洞；牙齒／舌面獨立定位並受嘴部開口裁切。
開口為 0 時口內全部隱去，只保留原中性閉嘴線。唇緣開合是幾何姿態，不表示已有音訊同步。

## 實際驗證

[四姿態總覽](pose-contact-sheet.png)；另有 neutral／half-blink／closed／left-wink／mouth-open-gaze-right 五張 640×640 真瀏覽器讀回。
每個 SVG 以獨立 image document 渲染，避免跨姿態相同 mask ID 干擾。

- PNG／隱藏補底：[asset-validation.json](asset-validation.json)。眼白原虹膜位置與口內中央取樣框 alpha≥200 覆蓋皆 100%。
- 真實畫面像素：[pixel-readback.json](pixel-readback.json)。中性兩眼虹膜色像素 1357／1369；半閉 738／762；全閉 0／0；角色左眼單閉時左 0、右 1357。
- 張嘴時固定 mouth ROI 深色口內像素由 43 增至 721；不是由模型文字或檔名推定有張嘴。
- 各姿態 iris source matrix 完全相同；視線右移只額外平移 8 個模型畫布單位，沒有隨閉眼壓扁虹膜。
- 六張 PNG 的模式／尺寸／hash、24 個圖層群組、相對圖檔引用、瀏覽器 pageerror=0 已查核。

## 保留缺口與服務失敗

額外請求單獨下眼皮線時，圖片服務回 moderation_blocked，沒有產出新圖；
未繞過拒絕或改走 CLI。下眼皮保留既有素材中的部分外緣，已在布局資料標明，
沒有宣稱完整下眼皮皮膚／閉合 mesh 已完成。

PNG 片段邊緣、原表情一致性、上下眼皮曲率與開口遮罩的逐幀接合仍需精修；
現有五個 SVG 只是靜態幾何情境，不能取代自然眨眼、說話、真音訊嘴型或 Cubism deformer 驗收。
沒有 PSD／cmo3／can3／moc3／Editor 往返、production 接線、TTS／麥克風或真服務測試；
V01 mouth pin 問題也沒有由本輪修復。完整 80 葉件與全身 rig 仍未完成，CP-V03 保留 PARTIAL。

下一步：完整下眼皮與五官葉件輸出、衣物／四肢關節補圖；Editor 主機仍待確認。
依 owner 指示直接推分支，不建立 PR、不合併 main、不改使用中角色。回退撤本輪素材 commit。

# SIRO Blender／VRM 風格粗模小樣 0.1.0

2026-10-19。使用者選擇保留並暫停 CP-V03，先試 Blender／VRM 風格小樣。本項為獨立探索，不完成或取代 CP-V03／V04，不改現有 Live2D 接線。

## 產物與範圍

資產位於 `assets/companion/siro-original/3d-style-study/0.1.0/`：可編輯 `siro-style.blend`、普通 glTF 2.0 的 `siro-style.glb`、正面／35 度／90 度 PNG，以及從同一工程渲染的轉頭 GIF。

這是實際三維頭肩粗模，保留銀灰短髮、青綠眼睛、角色左側髮夾、米色外套與霧藍內搭。參考為既有核准設定 `design/companion/CP-V03/references/0.2.0/siro-concept-sheet.png`。未載入第三方角色模型、貼圖、商用外掛或動作庫。Claude Code CLI 編寫建模腳本，Codex 指定造型、檢視渲染，並調整幾何及燈光參數。腳本是製作來源，不是供 runtime 執行的資產。

## 驗收判斷

技術交付和美術通過分開：**能建立、儲存、匯出與轉頭；美術仍是粗模，未通過原設定的精緻度與相似度驗收。**

三角度人工檢視已發現：瀏海與髮帽交界仍過於幾何化、髮束層次不足；眼睛僅靜態曲面色片、缺少精細眼瞼與虹膜；鼻口輪廓與臉型尚需雕塑；外套只是肩部形體。不能據此宣稱「看不出是 3D」或已達原畫品質。轉頭是整頭物件旋轉，不是表情／臉部 rig，也不是物理模擬。

這份 GLB **不是 VRM**：沒有 VRMC_vrm／humanoid、MToon、spring bone、眨眼／嘴型 shape keys、手指／全身骨架、布料碰撞或跟蹤接線。使用基本 Principled 材質；Blender 燈光／色彩管理不隨 GLB 轉移。未量測桌寵效能，不能套用為正式 SIRO 資產包。

## 重現

Linux 原生 Blender 4.5.14 LTS（build `62c1db4208e8`）。官方 portable archive SHA-256：`9ba871ff2ecd36526b77432745980b7e6664ecd0c7ca11c48849073dcfe06da3`。工具置於使用者 local share，不含在資產或 Git。

```bash
blender --background --threads 8 --python design/companion/blender-style-study/0.1.0/build_siro.py -- --output /tmp/siro-style-rebuild
```

建模檔內 `HeadPivot` 有 1／18／36／54／72 幀關鍵幀，左右轉約 30 度及輕微俯仰，24 fps。三張 PNG 為同模型在不同相機角度的實際 Cycles CPU 渲染，768×768、16 samples、denoise；GIF 為重開工程後每 6 幀取樣，384×384、8 samples。實際檢查見 `inspection.json`、`glb-import.json` 與渲染紀錄；不把尚未做的 VRM／物理／整合列為 PASS。

## 自動化工具評估

- [Auto-Rig Pro 作者說明](https://superhivemarket.com/products/auto-rig-pro)：Smart 可自動定位骨骼，結果可編輯；作者仍建議學習權重繪製並調整影響範圍。沒有「保證完美權重」的依據。本輪未購買或使用。
- [AccuRIG 官方系統需求](https://manual.reallusion.com/AccuRig-2/1.0/03-introducing-the-user-interface/system_requirements.htm)：列出 Windows。本輪不以其作為 Linux 前置依賴，未進行 Wine 綁骨測試。
- [VRM 1.0 規格入口](https://vrm.dev/en/vrm1/)：VRM 另有 humanoid／expression／meta 等結構及 MToon／springBone 擴充。普通 GLB 匯出不等於 VRM 已完成。

下一步先修髮帽與瀏海的拓撲、雕塑臉型及眼瞼，再與設定圖比對。造型獲確認後才值得擴展全身、測試 Blender 自動權重及 VRM spring bone，並檢查肩肘／手指變形、髮絲碰撞。現階段沒有足夠證據建議全面替換 Live2D。

## 資產驗證命令

```bash
blender --background --threads 8 /tmp/siro-style-rebuild/siro-style.blend --python-exit-code 1 --python design/companion/blender-style-study/0.1.0/inspect_preview.py -- /tmp/siro-style-preview
blender --background --threads 2 --python-exit-code 1 --python design/companion/blender-style-study/0.1.0/inspect_glb.py -- /tmp/siro-style-rebuild/siro-style.glb
```

實測：工程重開、5 個關鍵幀的旋轉讀回、12 幀渲染、GLB 匯入後第 1／18 幀矩陣差異、GLB 不含 `_cut` 隱藏切割物件、6 份核心資產 SHA-256 核對均完成。GLB 有 52 nodes／51 meshes／1 animation／0 skins；工程可見評估後 112,764 triangles，尚未為桌寵減面。

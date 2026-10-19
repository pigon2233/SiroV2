# 兩層 Editor 往返測試件 0.1.0

自有幾何測試圖，256×256、RGB 8 bit、sRGB、兩個獨立透明圖層；無圖層遮罩、效果或智慧物件。這不是角色模型，也不是已完成的 Cubism 工程。

`two-layer.psd` 是匯入輸入；`fixture_base.png`、`fixture_marker.png` 是獨立圖層參照；`expected-composite.png` 是合成結果。深藍底部長方形與上方青綠標記重疊，標記在前。

檔案 QA：Pillow 合成 RGBA 逐像素相同、ICC 逐 byte 相同、圖層名稱解析通過；另外按 PSD 格式讀回各 raw channel，與兩張來源 PNG 的 RGBA 通道逐 byte 相同。詳見 `file-validation.json`。Editor 實際匯入仍 **NOT TESTED**；檔案 QA 不能取代它。

## 在 Editor 執行（尚未執行）

1. 使用已開啟的 FREE Editor，關閉 Home；File → Open 選本目錄的 `two-layer.psd`。如需 Windows 路徑，可用 `Z:\home\jasonliao\文件\Siro\SiroV2-companion-plan\design\companion\CP-V03\roundtrip-fixture\0.1.0\two-layer.psd`。
2. 記錄匯入訊息，確認兩個 ArtMesh／圖層、名稱、透明背景、前後順序與參照 PNG 一致。失敗則保留錯誤，不將 PSD 標為成功。
3. 為 `fixture_marker` 生成可編輯 mesh；用參數 `ParamAngleX` 的 -30／0／30 三鍵，讓標記在 +30 時向右移約 40 canvas pixels，底部固定。保存 `roundtrip.cmo3`。
4. 新建短動畫，參照該模型；30 fps、2 秒，參數在第 0／30／60 frame 為 0／30／0。保存 `roundtrip.can3`。關閉後重開模型與動畫，修改一個 key，再保存，確認可編輯。
5. 建立 texture atlas，將 moc3／model3.json／textures／motion3.json 匯出至自有版本目錄 `exports/0.1.0/`。保留精確 export version 與 Editor 設定；不要假定其一定可被既有 Core 讀取。
6. 將新匯出包交由隔離 renderer 載入、播放，核對移動、alpha、draw order、loop 與中斷；保存畫面及 hashes。這一步只能在真匯出檔產生後執行。
7. 回 Editor 將 +30 key 的標記移動改為約 20 pixels；另存 `roundtrip-v2.cmo3`、`roundtrip-v2.can3`，輸出 `exports/0.2.0/`，真 renderer 核對振幅變小。兩版都保留，不覆寫證據。

工程與匯出包可先保存在本目錄的 `artifacts/`（Git 忽略）；實際產生後核對來源、大小與 hash，再決定版本化交付方式。此處沒有建立空的假 cmo3／moc3 或預填 PASS。

[Adobe PSD 格式](https://www.adobe.com/devnet-apps/photoshop/fileformatashtml/)／[Cubism PSD 注意事項](https://docs.live2d.com/en/cubism-editor-manual/precautions-for-psd-data/)／[Cubism 匯出說明](https://docs.live2d.com/en/cubism-editor-manual/export-moc3-motion3-files/)。

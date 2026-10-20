# VRoid 原生角色重做 — 本機檔案／蒙皮已驗；美術與物理 PARTIAL

日期：2026-10-19。依使用者「從來一次」從 VRoid Studio 2.14.0 新女性底模重做；不沿用 Hunyuan 表面。前版外觀被使用者否定的結論不變。

## 實際產出

全部大型檔案在 Git ignored 的 `.siro-data/vroid/`：

- `siro-restart-v1.vroid`：6,946,826 bytes，實際透過 VRoid GUI 儲存。原生 ZIP 完整性檢查通過。
- `siro-restart-v1.vrm`：VRoid GUI 原生匯出的 VRM 1.0，15,658,820 bytes。39,665 三角面，保留原始匯出。
- `siro-restart-separated.vrm`、`.glb`：39,789 三角面；拆分外套／短褲／靴／頭皮與身體，頭髮原已獨立，另補 124 面的深藍髮夾並 parent 到原生 head。沒有改原骨架、權重與表情綁定。
- `siro-restart-separated.blend`：Blender 4.5.3 真匯入，8 個角色 mesh、1 個 128 骨 armature，貼圖已打包。另有 importer 的骨骼顯示用 Icosphere，不算角色 mesh，設為不渲染。
- 7 張真 Cycles 預覽：正面 T-pose／手臂放低、四分之三、背面、臉、左手中立／張開。
- `siro-vroid-restart-v1.zip`：45,213,012 bytes，19 entries，所有封裝檔案逐項 SHA256 與 CRC 檢查通過。含來源、分件模型、Blend、預覽、README、驗證 JSON 與腳本。

## 已執行與結果

依當前官方 Computer Use skill 的 Node REPL `@oai/sky` 操作。重新列舉時 VRoid 未執行，依 list_apps 回傳的安裝 ID 啟動，使用新女性底模。這輪首次條款頁已不再顯示，沒有重複替使用者接受條款或更動全域安全／隱私設定。

原生五指與骨架保留。選擇柔和臉型、銀灰鮑伯頭及側分瀏海、青藍眼睛；以原生 cardigan 模板建立米白寬袖外套，另做淺藍內搭、深藍短褲、灰黑褲襪與深藍短靴。參考圖沿用既有四向素材，未上傳第三方服務或 VRoid Hub。

按照 [VRoid 官方疊穿文件](https://vroid.pixiv.help/hc/en-us/articles/4405497325721-How-do-I-overlay-outfits) 檢視模板與參數。初次 T-shirt 疊穿出現穿插；該試驗及重複外套圖層保留但隱藏，改採原生貼身內搭後的正面／四分之三預覽無該穿插。內搭是身體貼圖，不能將這項處理說成完成獨立內搭網格。

重現命令（Python 使用本機 bundled runtime；Blender 使用既有 WSL 安裝，沒有新增產品依賴）：

```text
python .siro-data/vroid/prepare_candidate.py
wsl.exe -d Ubuntu --exec /home/pepepig/.local/share/siro/hunyuan3d/tools/blender-4.5.3-linux-x64/blender -b --python /mnt/e/coding/股票策略機器學習/SiroV2/.siro-data/vroid/render_candidate.py
python .siro-data/vroid/bundle_candidate.py
```

`prepare_candidate.py`：exit0。檢查 GLB header／長度／indices 範圍、所有實際引用蒙皮頂點的非負有限權重與權重總和；雙手 30 個指關節均具有非零影響。分件前後的 VRM expression／spring 資料完全相等：57 個 morph targets、14 個預設表情、30 組 spring、28 個 collider。新增髮夾使用頭骨子節點，沒有重編既有節點索引。

`render_candidate.py`：最終 exit0，重新匯入 8 個角色 mesh，7 個原生角色部件有 Armature modifier，髮夾隨頭骨。左手 Index／Middle／Ring／Little proximal joints 做張開試驗，561 個 evaluated vertices 位移超過 0.0001m，最大 0.0161089556m。真渲染手部近景清楚顯示五指分離，測後還原手指 pose。這是左手合成姿勢的真蒙皮測試，右手僅做權重與骨架檢查，非全動畫驗收。

`bundle_candidate.py`：exit0；ZIP 19 entries 的 CRC、檔名集合與 manifest SHA256 全部通過；原生 `.vroid` 內部 ZIP testzip 無錯誤。

## 失敗及修正保留

- Save dialog 的 set_value 回「element not settable」；重新觀察後用實際檔名欄位輸入路徑並保存，沒有將失敗寫成成功。
- 一次內搭填色誤填透明區域，立即 undo，之後檢查沒有全身變藍的錯誤。褲襪主色填色成功。
- 兩次以筆觸延長短褲沒有可確認變化，不宣稱褲管長度修改成功；目前仍偏短。
- 首輪 Blender 腳本將 importer 骨骼顯示用 Icosphere 算入 mesh 數而 assert 失敗。改以 Armature modifier／獨立髮夾辨識角色 mesh 後最終通過。
- 髮夾初始位置藏在髮內；依 head world matrix 與實際髮頂點範圍校正，最終臉部及四分之三真渲染確認可見。

## 限制與下一步

外觀仍是候選，尚無使用者美術驗收。瀏海帶預設編髮、短褲偏短、靴底偏厚，身形、髮尾及衣褶尚未逐項貼合參考。不能把幾何／檔案檢查通過說成美術完成。

內搭與褲襪仍為身體貼圖，不是獨立厚度衣物，也沒有完整隱藏人體。其餘指定主要分件及髮夾可獨立選取，但沒有啟用衣物 cloth／剛體引擎。30 組髮束 spring 只確認資料保留，未在 VRM 播放器或 SIRO renderer 中驗證；Cycles 使用 glTF fallback 材質，不代表各引擎 MToon 的最終效果。

後製髮夾只在分件 VRM／GLB／Blend；原生 `.vroid` 不含它。下一步先讓使用者檢查目前臉型／比例／服裝，再精修外觀、獨立內搭與完整身體，最後才做目標引擎的物理／動作驗收。

這輪執行時 repo 已在 main，先前舊報告不在目前 checkout；沒有還原或覆蓋其他工作。僅新增本報告及 STATUS 接續點；正式 Core／renderer／桌寵未改，未跑產品測試／CI，未 commit／push。模型留在本機 ignored 目錄。

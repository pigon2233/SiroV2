# 資產交接規格 v0

CP-00 提案，DRAFT／待 Claude 接收；不是已可呼叫的 loader schema。

## 路徑與相容

design/companion/ 保存分鏡、曲線、參數表、mask 與視覺驗收。
後續 assets/companion/<pack-id>/<version>/ 只放自製且允許提交的 runtime 資料，
不夾 SDK 或可執行程式。大型／受限工程以版本化 artifact 提供 owner、取得方式、授權與逐檔 SHA-256。
尚未建立 runtime 資產；未啟用 LFS。

現有 config/body-assets 的 asset-manifest.json 仍遵循 adapters/body/assets.py 的
BodyAssetManifest v1（extra=forbid）。新 metadata 另表交付，不塞入現有 manifest。
Claude 寫 loader／validator，Codex 交資料，不雙寫 production。

## 每包必填

| 表 | 必填內容 |
| --- | --- |
| pack | pack_id、version、identity、來源／授權、工具版本、每檔 hash、取得方式 |
| compatibility | SDK／renderer／model digest、可編輯工程索引；未實測填 unverified |
| parameters | 真 ID、型別、模型 min／max／default、channel、owner、混合規則；從實檔讀，不猜 ID |
| motions | motion_id、activity、entry／loop／exit、duration、fade、interrupt／resume、mask |
| root／contact | 步態與桌面位移分開、接地時段、速度、朝向；半身不支援則填 unsupported |
| capability | supported／unsupported、缺項 fallback；不依檔名推定 |
| cost | texture 尺寸／數量、檔案大小、主機、frame／記憶體實測；沒量填 unmeasured |
| evidence | source／asset digest、固定情境、錄製、缺陷；mock／真 renderer／真人分列 |

## 曲線及驗收

身體主活動一次一個；root 由宿主控制；expression 保持 Core affect；gaze 經仲裁；
mouth 只用有效音訊 owner；呼吸／眨眼／物理接受 mask。
曲線列參數白名單，未列參數不可隱含清零；從當前姿態插值，不從 default 重設。
0.2–0.6 秒 fade 是待驗初值。entry→loop→interrupt→foreground→resume→exit
須有固定情境；resume 不重播工具／語音。站姿平移不能當步行，缺模型不產假 motion3。

## 待 Claude 接收

請在交接紀錄填 branch／head、實際模型 manifest／renderer、metadata 檔名、
activity adapter、generation／停止語意、安全切包點與失敗 fallback。
未接收前維持 Body v1；不授權部署或 protocol migration。

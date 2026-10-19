# CP-00：Codex 視覺基線交付

2026-10-18 Asia/Taipei。PARTIAL，待 Claude 接收與 runtime 核對。

## 認領

Owner：本次 Codex session。Branch：design/companion-cp00-20261018。
Base：64f21d973ab60724ef5e5a10c807dcff048eda7e。
功能 source 基線：3c7ee58de4f53129ed35be5d9877979d7efc586c。
工作區 SiroV2-companion-plan 開始時 clean，已 fetch origin。
本卡 owned paths：design/companion/CP-00-BASELINE.md、design/companion/ASSET-HANDOFF.md。
production、scripts、desktop、tests 及共用 STATUS／TASKS／DECISIONS 仍由 Claude 負責。
本檔不是跨機共享鎖，沒有 Claude 接收回覆。

已讀 AGENTS、STATUS、SOL_RUNBOOK、companion-workflow 四文件與遠端 AI_COLLABORATION。
已讀 owner acceptance 分支 62064cfe80bc82a8339e5081577587f525729606 的 SUMMARY；
取消／刷新、200% 及記憶回答的真人失敗保持，不用歷史 PASS 覆蓋。

## Source caller／consumer 對映

以下除 scripts 外以 src/siro/ 為根；是 source 調查，不是執行中服務驗證。

| 邊界 | 現有程式 | 新契約界線 |
| --- | --- | --- |
| Body intent | ports/body.py；adapters/body/web.py 的 MinimalWebBodyAdapter | 維持 body v1，新 activity intent／回執仍是提案 |
| 單 writer | adapters/body/web.py 的 WebSocketBodyTransport.attach／_write_loop | 有界佇列容量 64，換 owner 先 detach；重連只記住 emotion |
| renderer owner | services/presentation/gateway.py 的 renderer transport／desktop_renderer 接線 | desktop lease；Claude 核對當版 consumer |
| affect | core/affect.py；services/affect/coordinator.py；persistence/affect.py | 視覺消費情緒，不新增 writer |
| audio owner | services/presentation/gateway.py 的 PlaybackOwnership acquire／release | 動畫不能取得播音權；真能量接線待核對 |
| journal | services/presentation/integrated.py 的 _journal_event／finish_journal；persistence/migrations/013_run_journal.sql | activity／network 投影 API 尚未實作 |
| browser | services/tools/browser_session.py 的 BrowserSessions；gateway.py 組裝 | 不代表全程序網路監測 |
| proactivity | core/rooms.py 的 choose caller → core/proactivity.py 的 ProactivityRules | caller 存在不等於 companion 自主研究已接入，composition／配置待 Claude 核對 |
| production UI | services/presentation/static/index.html | Claude 唯一修改者 |
| renderer 製作 | scripts/prepare_live2d_renderer.py；scripts/repair_companion_renderer.py | Codex 僅讀，生成腳本不等於目前運行產物 |

## 視覺待重現情境

- prepare 腳本 stopSiroMotion 同時停 motion／expression 並關嘴。請 Claude 核對 repair 後產物，再錄「說話中取消主活動」；目前是 source 風險，非已重現現場缺陷。
- playSiroGesture 使用 TapBody 隨機動作與 force priority；不能稱為精確點頭／閱讀。V01 須讀 model3 真索引。
- body.look 接 onDrag；以視線→情緒→停止→恢復檢查參數搶寫，尚未實測。
- prepare 含每 120ms 交替開合嘴；不是音訊同步證據，須核對 repair 與實際 audio owner，不能推斷當前版本。

## 資產／環境 gate

此工作樹沒有 models/；config/body-assets/ 只有 README。未取得模型實體／manifest，
不能盤點 moc3 合法參數範圍或錄製自然度。腳本目標是 Cubism Web 5-r.5／Haru，
不代表已載入版本。ParamMouthOpenY 的 0–1 是腳本限制，並非模型量測；
F01／F03／F05／F06／F08 是腳本映射，尚未證明對應 expression 檔齊備。
Editor 主機／版本、可編輯工程、授權接受及匯出往返尚未確認。
不複製其他 checkout 的 ignored／私人資產，不啟動或重啟使用中服務。

## 交付與下一步

配套：[ASSET-HANDOFF.md](ASSET-HANDOFF.md)。未改現有 manifest schema 或 protocol。
只做文件與 source 對映，沒有 runtime、模型、硬體或錄影 PASS。
Claude 接收與配置核對未完成，CP-00 不標 DONE，也不跳過依賴宣稱 V01 完成。
下一步：Claude 接收對映並提供可用模型／manifest 路徑與最終 renderer 版本，
Codex 做 V01 實檔盤點及固定情境錄影，再製作 V02 曲線。
全身外觀在大量素材／rig 前先交具體草案供使用者確認。
回退：撤回本卡文件 commit；無服務／資料／設定變更。

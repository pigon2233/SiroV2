# T／RT 未完成範圍盤點

2026-10-18；核對 TASKS、STATUS、Runtime roadmap、Interface plan 及目前實作。DONE僅表示各列當時聲明的驗證層級，不能擴大成全產品完成。

| 範圍 | 目前缺口／狀態 | 可立即實作？ |
|---|---|---|
| RT-001–015 | 原卡皆scoped DONE；RT-011摘要、013 workspace read/list、015 read-only整理在10-06已解除舊DEFER並完成 | 不重做原能力；有新缺陷另依證據局部修復 |
| T10-UI-01 | 整體PARTIAL：任務詳情、設定用語、完整可及性／真人流程；記憶搜尋本輪完成限定切片 | 是；一次一切片 |
| T12 Companion後續 | 獨立宿主已有，但全身可編輯rig、完整左右步態／轉向／坐起／道具、自由活動及多螢幕／DPI整合仍未全交付；舊Live2D L2 DONE不等於這些追加需求完成 | 軟體／素材可按既有plan分切片；資產授權與真平台各自驗 |
| T15 新B聲線／FIX-005 | B reference與clone路由已接；新台詞人耳品質、首音速度SLO未全驗 | 量測／優化可做；另一台硬體、人耳不能由本機mock代證 |
| T20 | 既有quiet/busy/day-limit L1完成；主動互動L3仍待驗 | 需實際體驗，不應再造排程 |
| T27 | MQTT模擬完成；HTTP /event使用者回報正常但接收器來源／保存payload未定位，WorldState／真actuator閉環未證 | 取得receiver資訊或既有MQTT實板條件後接入；不猜測URL服務 |
| T28／T29 | 真HA與真sensor→actuator→readback未驗，模擬路徑已完成 | 需要真設備／HA條件 |
| T35 | BLOCKED-EXTERNAL：v1.0 24h soak、真人UX、真設備、正式provider profile | 條件齊備後執行，不以新增元件代替驗收 |
| T39 | BLOCKED-EXTERNAL：真雙節點運行／斷線／epoch等；使用者已有另一台運行，但目前未建立測試連線與角色配置 | 先取得真節點角色與可用連線，不能宣稱已驗 |
| T40 | BLOCKED-EXTERNAL：依賴T35／T39與發布稽核 | 尚不能標DONE |
| RT附錄RI-003 | PARTIAL：一般multiprocess／threads／pytest／deps的隔離認證未完成 | 需獨立profile驗收，不可沿single-process聲稱支援 |
| RT附錄RI-004 | PARTIAL：真正enabled skill worker／安全審查／明確批准與撤銷整合未完 | 有安全依賴，不自動下載／啟用 |
| RT附錄RI-005 | PARTIAL：first-adoption舊writer排除、immutable package驗簽→import、maintenance→runtime handoff及正式部署未完 | RED區需有界設計／相容驗收，不能順手擴張 |
| RT附錄RI-006 | PARTIAL：真根因定位→真最小patch尚未完成，現有為有來源唯讀調查view | 可分安全提案切片，執行／部署仍受RI-003／005門檻 |
| FIX-002／FIX-006 | 有用搜尋與已知／未知理解的產品品質gate仍保留 | 按原缺陷卡與實際症狀續作，測試數量不能取代品質 |

T00–T34、T36–T38其他原卡保留既有scoped DONE；上述不是重設任務順序或新增RT卡。STATUS舊「本機缺口已全清」與歷史DEFER段落不能覆蓋更新後的PARTIAL與上述實際缺口。

本輪選 **T10-UI-01記憶搜尋**：依賴滿足、後端已有caller、前端確實缺入口，修改可限單一HTML與必要測試；不動另一台電腦的運行配置。下一候選是同卡任務詳情，不在本輪預先實作。

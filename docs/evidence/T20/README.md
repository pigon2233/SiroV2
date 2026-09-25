# T20 驗收證據

日期：2026-09-25｜結果：PASS（L1），L3 feedback pending

主動功能預設關閉且需 owner 啟用。決策順序固定檢查 timezone quiet hours、busy、already speaking、cooldown、daily limit，再評估 home-arrival、overdue-task、environment-change；每次包含 `do_nothing` 與明確 reason。A13 的四種抑制與正常回家，以及 7-day replay 已通過。

使用者主觀干擾度屬 L3，需在 T16 真人音訊驗收後收集，未以自評替代。

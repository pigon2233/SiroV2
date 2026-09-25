# T19 驗收證據

日期：2026-09-24

已完成固定 Attention 公式、0.6 門檻、明確 user input 旁路、stop/cancel 優先；Action Selector 在評分前套 permission/quiet/busy/cooldown/resources hard gates，並永遠保留 `do_nothing`。Drive 有具名、可關閉、0–1 pressure 與原因。Workspace 限制一個 foreground、三個 goals、20 個 events；Goal 有明確狀態、deadline、step/cost budget、SQLite revision/CAS 與合法狀態轉移。

固定 1,000 個 noise signals/actions 的正反順序 replay 得到相同 user/do_nothing 結果；噪音不觸發未授權背景 action。完成時 Python gate：76 passed、3 個 real-provider opt-in skips；新增 Drive 後專項 7 passed、ruff/mypy 通過。

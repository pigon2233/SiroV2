# ROUTINE-01 作息學習（階段 1）

2026-10-29，Claude，DONE／LOCAL_VERIFIED／LOCAL_ONLY／NOT PUSHED，在使用者 main checkout 做 local commit。
Owned：services/agent/routine.py、core/sensor_reactions.py（兩個 trigger 文案）、gateway.py（watcher 啟動，
env SIRO_ROUTINE_ENABLED 預設 1）、tests/unit/test_routine.py、tests/integration/test_routine_watcher.py、本檔。
不碰 firmware/、顯示相關；STATUS.md 留整合者。
驗證：WSL pytest 單元＋整合僅合成資料；無真實感測資料驗證。
限制：需 ≥5 個有效日才生效；睡眠時段不判定無人。下一階段：節點健康、場景、在家判斷融合、OTA。

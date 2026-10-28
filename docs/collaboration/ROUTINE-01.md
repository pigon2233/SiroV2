# ROUTINE-01 作息學習（階段 1）

2026-10-29，Claude，DONE／LOCAL_VERIFIED／LOCAL_ONLY／NOT PUSHED，在使用者 main checkout 做 local commit。
Owned：services/agent/routine.py、core/sensor_reactions.py（兩個 trigger 文案）、gateway.py（watcher 啟動，
env SIRO_ROUTINE_ENABLED 預設 1）、tests/unit/test_routine.py、tests/integration/test_routine_watcher.py、本檔。
不碰 firmware/、顯示相關；STATUS.md 留整合者。
驗證：WSL pytest 單元＋整合僅合成資料；無真實感測資料驗證。
限制：需 ≥5 個有效日才生效；睡眠時段不判定無人。下一階段：節點健康、場景、在家判斷融合、OTA。

## 階段 2–5（同日，LOCAL_ONLY／NOT PUSHED）
- 節點健康 services/agent/node_health.py（離線 10 分鐘後提醒、恢復通知；gateway 每 2 分鐘檢查）。
- 場景 services/agent/scene.py（僅資訊、無執行器）；在家判斷 services/agent/home.py（動靜＋光＋最近對話）；
  兩者附加在作息異常 facts 的 scene／home。
- OTA 僅服務端 services/devices/ota.py（manifest：version/size/sha256；只提供更新版本）。
- 韌體待辦（未動 firmware/）：節點需取得 manifest、下載、驗 sha256、雙分區切換與回滾；
  gateway 尚未掛 OTA 端點（gateway.py 目前有他人未提交修改，待其提交後再接）。

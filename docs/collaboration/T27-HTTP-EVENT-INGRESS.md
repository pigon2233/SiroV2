# T27 ESP32 HTTP 事件轉 SIRO 狀態：本機交接

- Owner：Codex；2026-10-23 Asia/Taipei；**LOCAL_ONLY／BLOCKED_SYNC**。修改前查詢 GitHub 未結 Issue／PR 為空，`origin/main` 為 `89b80fbf17dee5e311c5f1c3123cb92833b6cc68`；先前 GitHub 寫入憑證不可用，故尚未線上認領。恢復認證後須重查競爭認領。
- Base：本機 `codex/t27-esp32-sensor-telemetry`@`a5f79e5`（該分支尚未推送）；本分支 `codex/t27-http-event-ingress`、獨立 worktree `E:/coding/Worktrees/t27-http-event-ingress/SiroV2`。與先前 T27 感測韌體變更有前置依賴。
- 範圍：只在 `src/siro/services/devices/http_sensor.py` 建立使用者現有 HTTP `light_update`、`motion_detected`、`motion_cleared`、`button_pressed` 的嚴格 parser 與 World State 投影元件，測試在 `tests/integration/test_esp32_http_sensor.py`；保留 `C:/Users/pepepig/siro_receiver.py` 原檔與原服務。
- 契約界線：不新增正式 HTTP route、不讓外部程序寫 SIRO 主資料庫、不賦予事件設備控制權。正式接入 `/event` 涉及入口認證與路由契約，待 `docs/DECISIONS.md` 與受影響測試由共享文件 owner 審核後實作；這份文件不是決策紀錄或共享鎖。
- 驗收：合成 payload 經 parser、Registry、SQLite World 觀測；拒絕格式錯誤、偽造 device、異常 lux；驗證時間與失效、PIR 低電平不推斷房間無人。實板 POST 仍由使用者舊接收器單獨接收，不宣稱 SIRO 已線上感知。
- 結果：20 項相關測試 PASS／4.81s；Ruff check／format、mypy、diff PASS。詳見 [本輪證據](../evidence/T27-http-event-projector-2026-10-23/REPORT.md)。沒有 live ingress 或實板驗收。
- 本地實作 commit：`acf3f66`。無互動 `git push --dry-run` 回覆 `could not read Username for 'https://github.com'`；未推送、未建立 Issue／Draft PR。正式接續前先恢復 GitHub 認證並重查共享狀態。

## 2026-10-23 接續：HTTP 入口決策草案

使用者要求繼續接入現有 8765 接收器。GitHub 仍未完成登入，線上認領及共享 `docs/DECISIONS.md` 寫入權尚未取得；本節是**待整合者審核的契約草案**，不是已合併決策。因主程式對 `siro.db` 有獨占 owner，Windows 接收器不能直接寫庫。實作限定獨立分支，新增 `src/siro/services/presentation/gateway.py` 中預設關閉的 loopback HTTP ingress、主程序持有的 Registry/World 投影、`scripts/esp32_http_receiver.py` 純標準函式庫 LAN relay 與新整合測試。這與其他 AI 的 gateway 工作可能在檔案層衝突；不得自行合併，恢復線上認領後先檢查並取得交接。

擬定契約：Windows relay 仍監聽 `POST /event` 於 8765，只接受設定的 ESP32 來源 IP，傳原始 JSON 到 SIRO `127.0.0.1:8000/v1/devices/esp32/events`；該入口只接受 loopback、明確設定的隨機 relay token、≤4096 bytes JSON 與單一已配置 device ID。SIRO 主程序驗證後，以伺服器接收時間寫 World State；成功持久化才回 200。另提供 owner session token 保護的 `GET /v1/devices/esp32/state`，只讀同一主程序的三個感測屬性，過期值只標 unknown，不把舊值當現況。下游 timeout 或未知結果不重送，ESP32 仍可收到失敗，不能把其 HTTP 200 當成 T27 MQTT／A18 L3。沒有 LED、沒有設備 action、沒有新的模型授權；`motion=false` 不推斷無人。預設不設 token 時入口 503，且不建立接收器／descriptor。使用者原獨立接收器與目前運行的 gateway 不會在此分支自動替換或重啟。

實作與驗證：新增 `scripts/esp32_http_receiver.py`、`tests/integration/test_esp32_http_gateway.py`、`docs/ESP32_HTTP_INGRESS.md`、[接續證據](../evidence/T27-http-relay-2026-10-23/REPORT.md)，並修改 `src/siro/services/devices/http_sensor.py` 與 `src/siro/services/presentation/gateway.py`。Python 3.14 WSL 相關 45 tests PASS／11.18s；Ruff check／format 與新檔 targeted mypy PASS；完整 gateway mypy 仍有兩項先存錯誤。Windows→WSL loopback 與 Windows relay 缺設定拒絕啟動已驗。當前 8000 是舊版本、8765 未運行新版；無實板 World State 驗收。未取得 ESP32 區網 IP、未設定 token、未更新共享 `docs/DECISIONS.md`／`docs/STATUS.md`，不能宣稱正式部署或安全配對。整合者需先核對與其他 gateway owner 的檔案衝突，再納入共享決策與狀態。

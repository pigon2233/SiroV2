# T27 ESP32 relay：桌寵重新啟動後保留私有認證

狀態：**LOCAL_CODE_VERIFIED / LIVE_SWITCH_PENDING / NOT PUSHED**。2026-10-24 Asia/Taipei。

2026-10-24 05:07 左右，另一個 AI 使用 VRM 啟動器重新啟動主專案的 SIRO。該啟動器先清除所有 `SIRO_` 環境變數，之後呼叫 `scripts/start-companion`；新 Gateway 健康，但 `POST /v1/devices/esp32/events` 回 503，因為先前只在另一個手動 Gateway 啟動環境中的 ESP32 relay token 丟失。Windows relay 仍監聽 8765，故實板 POST 暫時不能進入 World。先前正式服務已確實留下實板光度從 0 到 0.8 lux 的觀測，見 [現場紀錄](../T27-esp32-live-2026-10-24/REPORT.md)。

本分支以 `85c5fc3` 為本機基線，在 `scripts/start-companion` 啟動 Gateway 的子程序中，若環境沒有 token，才從啟動者的 `$XDG_CONFIG_HOME/siro/esp32-relay-token`（預設 `~/.config/siro/esp32-relay-token`）讀取。檔案必須是非 symlink 的一般檔案、由啟動者擁有、group/other 無任何權限，token 長度 32–256 且不含空白；不合格即拒絕啟動並只輸出不含 token 的錯誤。桌面 host 不繼承從檔案載入的 token；無檔案時維持原本預設關閉行為，明確環境變數仍優先。

驗證：WSL `bash -n scripts/start-companion scripts/load-esp32-relay-token` PASS；Ruff check／format PASS；`PYTHONPATH=src python -m pytest -q tests/integration/test_esp32_companion_token.py tests/integration/test_desktop_entry_scripts.py` **49 passed／11.33s**，涵蓋正常啟動子程序、桌面 host 不持有 token、過寬權限／symlink 拒絕、無檔案預設與明確環境變數優先。未用真 Gateway 重新啟動測此修正；另一路 AI 正在執行其桌寵啟動流程，避免在其使用中改動主 checkout。使用者要求不得 git push，因此本分支僅本機提交。

下一步：與桌寵工作協調後，把本分支小範圍啟動修正整合到主專案，使用既有私有 token 檔案短暫重啟並驗證 `/health/live=200`、有效 token 下的拒絕型測試為 400、實板新光度進 World；不要以 200 健康狀態代替 sensor ingress 驗收。若需回退，移除本啟動修正或暫時移開 token 檔案（環境變數仍可覆蓋），再按原流程啟動；不用還原資料庫。

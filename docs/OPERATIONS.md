# SIRO 本機操作手冊

## 安裝與服務

在 repository 根目錄執行：

```bash
scripts/install
scripts/doctor
```

第一個命令使用 locked production dependencies，建立保守的 `config.json`、`siro-gateway.service` 與每日
log-retention timer，但預設不啟動服務。檢視 unit 後明確啟用：

```bash
scripts/install --enable
systemctl --user status siro-gateway.service
curl --fail http://127.0.0.1:8000/health/ready
```

停止或重新啟動使用 `systemctl --user stop/restart siro-gateway.service`。服務只綁 loopback；設定、資料與
log 預設分別位於 `~/.config/siro`、`~/.local/share/siro`、`~/.local/state/siro/log`。每日 timer 刪除超過
14 天的 rotated `siro.log.*`，目前 `siro.log` 不會被 retention job 刪除。

不使用 systemd 時，可在兩個終端執行：

```bash
scripts/start .siro-run/gateway.pid
scripts/stop .siro-run/gateway.pid
```

start 會建立 PID file、轉送 SIGTERM 並在程序退出時清除 PID file。stop 僅終止明確 PID，不依程序名稱
廣泛終止。

## 備份與還原

只備份資料庫的相容入口：

```bash
scripts/backup ~/.local/share/siro backup.sqlite3
scripts/restore restored-data backup.sqlite3
```

正式操作應同時帶設定，產生含 hash manifest 的 ZIP bundle：

```bash
scripts/backup ~/.local/share/siro backup.zip ~/.config/siro/config.json
scripts/restore restored-data backup.zip restored-config.json
```

restore 會先驗證 bundle 檔案集合、SHA-256、設定 schema 和 SQLite integrity，再替換目標。備份不包含
環境變數或 API key；provider secret 必須由部署環境重新提供。

## 故障定位

依序檢查 `scripts/doctor --json`、`systemctl --user status siro-gateway.service`、health endpoint 和
`~/.local/state/siro/log/siro.log`。缺少可選 GPU、音訊或設備能力會顯示 unavailable，不應造成 minimal
profile crash loop。

## 2026-10-16 正式服務入口修正

新產生的 siro-gateway.service 經專案 .venv/bin/python 執行 scripts/launch_companion.py，與 scripts/start-runtime-product 相同，會讀取 allowlisted 本機模型設定並載入已準備角色；缺少設定明確失敗。既有已安裝 unit 不會因原始碼更新自動改寫，需重新執行 scripts/install、檢視 unit 後 daemon-reload，再由 owner 決定重啟。不要以直接執行 siro-gateway 的離線測試結果當成正式模型／Live2D已驗。scripts/start PID_FILE 預設正式入口，只有明確 --demo 才走舊的離線 gateway。

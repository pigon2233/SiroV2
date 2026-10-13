# RI-005 first-adoption：舊 writer 停止證據

2026-10-13（Asia/Taipei）。唯讀 code review＋自有臨時 SQLite／自有 child probe；未修改 production source/tests，未搜尋、訊號或停止使用者程序，未讀私人 DB／chat／key／config，未接觸 live 8026 或正式部署。

## 結論與分類

D50 新 lease **不能證明舊版或外部 writer 已停**；這是既有 `BLOCKED_BY_RELEASE_INTEGRATION` 的 **MISSING_INTEGRATION／TEST_GAP 前置條件**，不是新的 D50 flock implementation bug，也沒有證據要求改原 single-owner 設計。維持 RI-005 `PARTIAL`，不新增 registry、PID/TTL authority、lock manager 或全庫 connection scanner。

本輪 scoped evidence **PASS**：實際舊 SQLite WAL connection 在新 lease 成功後仍能 commit；同協議受管 contender 被 kernel flock 拒絕；已知舊 child 明確 close 且 wait joined 後，在同一連續新 lease 下接入保留所有晚寫。這個正向情境只證已知、自有且完整掌握的 writer，不聲稱本機所有未知 writer 已不存在。

## 實際 call path

| 路徑 | 現有行為 | 不能推論的事實 |
|---|---|---|
| `src/siro/adapters/data_ownership.py:101`，`exclusive_data_owner` | canonical DB path→固定帳戶 namespace→SHA key→nonblocking `flock`；持到 owned pools shutdown/join，再 close FD | 未受管 SQLite connection 不取得這個 advisory key；它不會因此停止或失去 write 能力 |
| `src/siro/cli.py:405`，`main` | demo/backup/restore/指定 DB 的 release 操作前取得相同 owner；包住實際 handler 与 loop join | 新 lease 成功不是 first-adoption stopped proof |
| `src/siro/services/presentation/gateway.py:1333`，`main` | acquire owner 後才 `_run_gateway`／初始化；owner 持到 serve/drain／owned IO 完成 | 不能從服務能啟動或 HTTP healthy 推論其他舊 binary 已停 |
| `src/siro/core/releases.py:63`，`stage_and_activate`／`:118`，`rollback` | 驗簽、schema gate、staging、pointer；D48 rollback 不倒回 DB | active pointer 或 readonly schema snapshot 不是實際 binary handoff，也不是 stopped reservation |
| `scripts/start:21`／`:28` | 自己啟動 child 並 `wait`；PID file 只記 PID | PID file 與 `kill -0` 不能識別所有舊 DB-writing jobs，不能當成 release authority |
| `scripts/stop:16`（本輪 baseline） | 發送 `TERM` 後返回 | signal delivery 成功不等於 child／threads／helper 已 drain 與 joined；本輪沒有執行這支腳本對現用服務做 stop |

精確審查版本 SHA-256 在 `adoption-result.json.source_hashes`；run 結束的 `source_hashes_after` 保留相同 scope 再綁定。root 的 launcher slice 若修改 `scripts/start`／`scripts/stop`，本表屬其修改前 baseline，須以 final source 與新 caller 驗收補上結果，不能改寫歷史 probe。

## 可重現驗收

```bash
.venv/bin/python docs/evidence/RI-005-launcher-2026-10-13/adoption-probe.py > docs/evidence/RI-005-launcher-2026-10-13/adoption-result.json
.venv/bin/ruff check docs/evidence/RI-005-launcher-2026-10-13/adoption-probe.py
.venv/bin/ruff format --check docs/evidence/RI-005-launcher-2026-10-13/adoption-probe.py
```

全部實際執行 PASS。probe 的唯一 controlled 邊界是將 `_owner_directory` locator 指向該 probe 自有 temporary directory；production canonical key、FD validation、kernel flock、SQLite WAL/commit/integrity、child wait 全是實際操作。沒有 mock return value、並未修改 owner source。temp coordination locks 在所有自有 child 結束後與整個 fixture 一起清除；這不是授權 production 刪除 stable lock。

`adoption-result.json` 有九項 checks、三個自有 child 與單調時鐘 event sequence：

1. 舊 child 建立 WAL DB、commit `legacy-before-lease`，保持原 connection 開啟。
2. parent 使用現有 adapter 取得新 lease；舊 child 仍 alive。
3. parent 實際 `BEGIN IMMEDIATE`／commit `sqlite-preflight` 成功；這仍不能證舊 connection 已停。
4. parent 明確要求舊 child 再 write；舊 child commit `legacy-after-lease` 成功，新 lease 一直持有。
5. 另一遵循 D50 的 child 試同 key，實際得到 `managed-busy`，exit 0／joined／stderr 空。
6. 已知舊 child 收到明確 stop，先 close connection，再回報 stopped，parent `wait` exit 0／joined／stderr 空。
7. parent 在同一連續 lease 下讀回全部三個既有 markers，再 write `managed-after-stop`；四項均保留，`integrity_check=ok`。沒有 restore 舊備份。
8. lease 正常釋放後，第三個受管 child 得到 `managed-acquired`，exit 0／joined／stderr 空。
9. 所有自有 child 均 joined，temporary root 已移除。raw synthetic markers 不是私人對話資料。

實際時間控制為 pipe command handshake，讓 idle legacy connection 在新 lease 後 commit；這是反例的排程控制，不是假裝在現用 SIRO 觀察到同樣狀態。沒有在 fixture 之外發 signal，沒有 force kill 成功路徑。此反例證 concurrency 邊界，不聲稱本輪已造成資料毀損。

## 最小可信 handoff 前置條件

1. **明確界定 writer authority 與 data path。** launcher 必須握有自己原先建立的 child handle／受信 supervisor 的實際 lifecycle，而非靠模型提供的 PID、PID file 數值或一次 `kill -0` 猜 owner。第一次採用 D50 時，原 binary 可能完全不持新鎖；需要 operator 對這個資料目錄原先的啟動／写入入口作具體停止證據。
2. **先阻止新舊入口重新起寫入。** 停止期間，既有自啟動或其他已知入口不可重新開舊 writer。不得把「尚未取得新 lease」的空檔解讀成可以同時 migration。
3. **停止 admission，完成可確認的 graceful stop/drain/join。** 等待已知 old owner、所有其 DB-writing jobs／threads／helpers 結束，不能只發 TERM 後立即下一步；timeout、未知 close/join、未受掌控 descendant 均 fail closed，不能以自動 retry 或 force kill 冒充成功。強制結束／崩潰恢復需另外驗收。
4. **只有真正停止後才接新 writer，讀最新 DB。** 在同 process 的接入操作可連續持 existing D50 lease 到 startup/drain。跨 process exec 的 D50 FD 是 `CLOEXEC`，不能假裝 parent lease 自動轉交 child；child 仍應在自己的真寫入前取得既有 D50 lease。父程序不要一邊持有同 advisory key 一邊啟動也要取該 key 的 Gateway，否則新 Gateway 正常 fail busy。已停的舊 writer與被封住的入口是這段實際 handoff 的外部前置條件。
5. **實際版本與 readiness/readback 綁定。** 新 child 須從已驗簽的精確版本啟動；readiness 應對該 child/版本，而非任一碰巧同 port 的服務。持用既有最新 DB，code rollback 不能 restore 舊 DB。此項由 root 的獨立 signed launcher slice 驗收，不能引用本 probe 當成 PASS。
6. **未知 unmanaged writer 保持 block。** 沒有本輪可用的 production API 能證明所有未知 SQLite writer 已停；取 lease、schema/integrity/readiness check、等待固定時間都不是替代證據。若原啟動 authority 與所有寫入口無法確認，first-adoption 對該真 DB 仍不得放行。

這是既有 single-owner invariant 的接入前提，不要求擴一套永久程序 registry、跨 UID 掃描或強行接管其他程式。

## 現在已驗與仍未驗

**已驗：** advisory lease 不能停 unmanaged old writer；SQLite write lock 成功也不能證 idle old writer 停；managed mutual exclusion；明確 known-child close/join；連續 lease 下 latest-data preserving adoption；下一受管 owner 正常接續與 fixture 完整清理。

**未驗：** 現用 live 8026 的 old writer stop／其所有 helper；未知外部 SQLite clients absence；正式 operator approval；root 尚未完成的 signed version/readiness/跨 process handoff；network FS、其他 OS、power loss。請把真 first-adoption gate 與這份 synthetic verification 分開記錄。

## 回退與風險

本 agent 沒有 production diff；回退只移除本輪 `adoption-*` evidence，不能倒回 DB 或改 stable locks。probe 只保有三個自己 Popen 建立的 handle，失敗 cleanup 的 TERM 也只針對這些 handle。實際來源與最新資料保留在 temporary fixture 中被驗，不需要存 DB 二進位到 Git。主要剩餘風險是 launcher 把 signal／PID／pointer／綠燈誤當為 complete stopped proof；它需要 caller 的真 lifecycle gate，不需要抽象擴張。

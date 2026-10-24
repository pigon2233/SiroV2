# CP-I02 發布與回退準備（DRAFT，未演練）

狀態：PREPARED，**不是** DONE。I02 依賴 CP-I01，而 I01 依賴 P05／P06；目前 STATUS 沒有
I01／P06 完成紀錄，故完整驗收不成立。本文件只固定「已核對的現況」與「待授權演練步驟」。

## 授權（owner 於 2026-10-23 在 thread 同意）

- 授權對象：本卡的 Claude 擔任授權整合者。
- 範圍：僅本機隔離環境的回退→重新套用演練，以及共享 STATUS／roadmap 更新。
- 不含：push、merge、部署到正式環境、動另一台電腦、重啟 owner 正在用的服務。
  任何超出者需 owner 另行明說，原授權不自動擴及。

## 基線（2026-10-23 核對）

| 項目 | 值 |
| --- | --- |
| 分支 / HEAD | `claude/cp-p02-p03-test-gaps` / `0da2178e5e95257842f5826724b3d9535007e7e8`（本機，未 push） |
| 相對 main | 8 個 commit、21 檔、+1313/−19 |
| DB migration | `001`～`015`，共 15 個；相對 main **無新增 migration**（persistence 目錄 diff 為 0） |
| 素材 hash | `assets`＋`models`＋`renderers` 追蹤檔（assets/models 共 107 檔）逐檔 sha256 再 sha256：`bb9339c760b31488e0d156e7db43306adc6f82269e0fbaa6002fecb720d2d4dc`。注意：此值含 renderers 追蹤檔，正式 receipt 前以乾淨 checkout 重算 |
| 相容開關 | 新增程式無新 env 開關；既有 `SIRO_SELF_ACTIVITY_ENABLED` 可關掉自主活動（P04 回退入口） |
| 既有 release 機制 | `src/siro/core/releases.py`：簽章 manifest（`min_schema`／`max_schema`）、staged 啟用、`rollback()` 回 last-known-good，schema 超出範圍會拒絕（`incompatible_schema`／`schema_unknown`） |
| 備份／還原 | `scripts/backup`、`scripts/restore`（`siro backup`／`siro restore`） |

## 本次實際執行的驗證（WSL，`UV_PROJECT_ENVIRONMENT=$HOME/.venvs/sirov2`）

```
pytest -q tests/integration/test_release_manager.py test_release_launch_selection.py \
  test_release_manifest_signing.py test_release_data_retention.py \
  test_sqlite_backup_lifecycle.py test_sqlite_restore_lifecycle.py \
  test_sqlite_restore_validation.py test_backup_cli_cancellation.py
→ 223 passed in 17.99s
```

這只證明 release／backup 既有邏輯在 source 層可用，不等於 I02 演練。未跑全套 check、
Ruff／mypy／JS，也未在 Windows／WSLg／跨機驗。

## 待演練步驟（owner 已授權，本機隔離，尚未執行）

1. 在暫存資料目錄建一份合成資料 DB（schema 15），不用 owner 的真實資料。
2. `scripts/backup` 備份；記 manifest／hash。
3. 以簽章 manifest stage 新版（本 HEAD）→ 啟用；確認 `active.json` 與 schema 範圍。
4. 先 drain／停止：關 `SIRO_SELF_ACTIVITY_ENABLED=0`，確認背景活動取消、無進行中 run。
5. `ReleaseManager.rollback()` 回舊版；驗資料未丟（筆數／hash 相同）、舊版可讀 schema 15。
6. 重新套用新版；再比對資料與 hash；`scripts/restore` 從步驟 2 備份還原到另一空目錄並比對。
7. 把以上每步的命令、輸出與 hash 存到 `docs/evidence/CP-I02-<日期>/`。

## Release receipt 草稿（待演練後填）

| 欄位 | 內容 |
| --- | --- |
| source commit | 待乾淨 checkout 確認 |
| 測試結果 | 上節 223 passed 為準備期結果；演練與全套 check 待補 |
| 素材 hash | 見基線，待重算 |
| schema／migration | 15，無新增；待演練確認 min／max_schema |
| 停止與回退 | `SIRO_SELF_ACTIVITY_ENABLED=0` → drain → `ReleaseManager.rollback()`；禁止 SQL 降版或還原舊 DB 取代 |
| 演練層級 | 全部「未演練」。source revert 不等於正式部署回退，不得互相代稱 |
| 未驗限制 | Windows／WSLg／跨機、正式部署、另一台電腦、O01 以外的程序流量、qwen3:4b 真環境行為 |

## 阻擋項

- P05（`0da2178` 已有 work_context 實作，尚無 STATUS 驗收紀錄）、P06、I01 owner 試用未完成。
- 本機無 `gh`，GitHub 認領／PR 狀態未核對；本分支未 push，其他 AI 無法讀到。

## 隔離演練結果（2026-10-23，WSL，合成資料，臨時目錄，未部署）

腳本與輸出：`docs/evidence/CP-I02-2026-10-23/drill.py`、`drill-result.json`。
舊版 = `974cdd7` 的 `src/siro`，新版 = 當時 HEAD `a541756` 的 `src/siro`。

| 步驟 | 結果 |
| --- | --- |
| 初始化 DB | 18 個 migration（基線表中的 15 已過時，main 已新增 016～018） |
| 啟用舊版／新版 | activated；資料 hash 不變 |
| `rollback()` | rolled_back 回 1.0.0；資料 hash 不變 |
| 重新套用新版 | activated（1.1.1）；資料 hash 不變 |
| healthcheck 失敗 | healthcheck_failed，active 維持不變 |
| `backup_to`→`restore_from` | 還原後資料 hash 相同 |

**限制（不可誇大）**
- 通過的是 `ReleaseManager`＋SQLite 備份還原的 **source／套件層**，不是正式部署回退。
- 舊版 `974cdd7` 只認得 15 個 migration，但演練 DB 是 18；manifest 的 `max_schema` 是演練腳本填的，
  所以**沒有證明舊程式真的能讀 schema 18**（真實回退需確認 016～018 對舊版向下相容或限制回退點）。
- healthcheck 是 `python -c pass`，沒有啟動真服務；沒驗 drain、服務停止、Windows／WSLg／跨機。
- 資料是合成的 50 筆；未碰 owner 真實資料或服務。

## 隔離演練 v2（2026-10-24，WSL，合成資料，臨時目錄，備用埠，未部署）

腳本與輸出：`docs/evidence/CP-I02-2026-10-23/drill2.py`、`hc.py`、`drill2-result.json`。
舊版 = `974cdd7`（臨時 git worktree，演練後已移除）；新版 = `811c62f`（當時 main HEAD 的 `src/siro`）。
舊版 DB 由舊程式建立（15 個 migration，53 表＋50 筆合成資料），不碰 owner 的服務、資料庫或部署目錄。

| 項目 | 結果 | 內容 |
| --- | --- | --- |
| 1. 舊版能否讀 schema 18 | **程式能讀，release 閘門不放行** | 舊程式開 schema 18 的 DB 複本：`initialize()` 成功、integrity ok、資料讀得到；舊 gateway 在該 DB 上 `/health/ready` healthy。原因：016～018 都是加欄位／加表，舊程式的 migration 檢查只看自己認得的版本。但舊版誠實的 manifest（`max_schema` 15）使 `ReleaseManager.rollback()` 回 `incompatible_schema`，active 維持新版。舊程式看不到 016～018 的新表（記憶審核、向量等），這部分功能在舊版不存在，不代表資料遺失。 |
| 回退路徑 | **必須還原部署前備份** | `stage_and_activate` 在啟用前自動備份到 `backups/before-<ver>.sqlite3`（schema 15）。**新版程式的 `restore_from` 會重新套用 migration，還原後又是 schema 18**，rollback 仍 `incompatible_schema`。必須用**舊版程式**的 `restore_from` 還原，DB 回到 schema 15、資料 hash 與部署前相同，`rollback()` 才回 `rolled_back`（1.0.0），舊 gateway 健康檢查通過。代價：部署後新寫的資料（演練中 5 筆）會消失。 |
| 2. 真實 healthcheck | verified | `hc.py` 取代 `python -c pass`：在 staging 目錄以該版本原始碼啟動 gateway（備用埠、DB 複本在臨時目錄、`PYTHONDONTWRITEBYTECODE` 避免改動被簽章的目錄），輪詢 `/health/ready` 到 `healthy` 且 `/health/live` 為 `alive` 才通過。失敗的 healthcheck（`exit 1`）仍回 `healthcheck_failed` 並保留 active。 |
| 3. 停止與 drain | **部分 verified** | 已驗：SIGTERM 後 websocket 收到 close code **1012**（service restart）、uvicorn 記錄 `Application shutdown complete`、停止約 0.1～0.2 秒、埠關閉、同一資料目錄第二個 gateway 被拒絕（exit 1，資料擁有者鎖）、停止後同目錄可再啟動。行程結束碼是 **-15**（uvicorn 完成關閉後再向自己送出收到的信號），不是 0，屬正常。**未驗**：有進行中的 turn／工具／語音時的 drain（原始碼會把 turn 標 `interrupted_shutdown` 並呼叫 `on_cancel`，但演練用 offline 模型、沒有進行中的 run）；也未驗 Windows 行程管理與 WSLg。 |
| 4. 回退→重新套用 | verified | 資料 hash（舊 schema 就存在的表與欄位的全部列）在每一步都相同：舊版 DB →（新版啟用並 migrate 至 18）→ 以舊版程式還原部署前備份 → `rollback()` → 重新套用新版 1.1.1 並 migrate → 與最初相同；`data_hashes_match: true`。 |

**限制**：仍是 source／套件層與 gateway 行程層的隔離演練，不是正式部署回退；healthcheck 用 legacy profile 與 offline 模型；沒有碰 owner 資料，沒有驗 Windows 行程停止、跨機或 candidate profile 下的進行中工作。

### 需加到 docs/STATUS.md 的文字（由其他對話合併）

> Companion CP-I02 隔離演練 v2（2026-10-24，PARTIAL）：以 `974cdd7` 舊版與 `811c62f` 新版在臨時目錄／備用埠演練。舊程式能開 schema 18 資料庫且 gateway 健康，但舊版 manifest（max_schema 15）使 `ReleaseManager.rollback()` 回 `incompatible_schema`；回退必須用**舊版程式**的 restore 還原部署前備份（新版程式的 restore 會再 migrate 回 18），部署後新寫的資料會消失。真實 gateway healthcheck（`/health/ready`）取代 `python -c pass`；SIGTERM 後 websocket 收到 1012、記錄 `Application shutdown complete`、同資料目錄的第二個 gateway 被拒、結束碼 -15（uvicorn 正常行為）。回退→重新套用資料 hash 全程相同。未驗：進行中 run 的 drain、Windows 行程停止、跨機、正式部署。見 [CP-I02-RELEASE-PREP](companion-workflow/CP-I02-RELEASE-PREP.md)、`docs/evidence/CP-I02-2026-10-23/`。

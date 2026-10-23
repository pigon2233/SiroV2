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

# MEM-RUNTIME-INTEGRATION：隔離整合與本機記憶試用

2026-10-22 Asia/Taipei。**PARTIAL / FAILED_VERIFICATION / LOCAL_ONLY / NOT PUSHED**。
實作與試用入口已完成；整合 gate 尚有一項未過，不能正式啟用或宣稱整套完成。

工作區：`E:/coding/Worktrees/memory-runtime-integration/SiroV2`。
分支：`codex/memory-runtime-integration-20261022`。
main 基線：`89b80fbf17dee5e311c5f1c3123cb92833b6cc68`；記憶前置：
`af89a1c8595631440c0b22b81ccc6e7ba1b29ae3`。
整合 checkpoint：`2d6970b63d045e653f80ec44e9140bb720631345`，當時標 verification pending。
收尾 commit 完整 SHA 由 git log／交接訊息提供；本文件不自引用。

## 已實作

- 在獨立分支整合既有 MEM01–04B／RT-Hermes 計畫與 main 基線。程式碼自動合併；
  CONTRACTS／DECISIONS 的 append 衝突只移除衝突標記，保留觸碰與記憶兩方內容。
- 新增 `services/agent/local_memory.py` 組裝既有 SQLiteMemoryRepository、SQLiteMemoryVectors、
  OllamaEmbedder、HybridMemoryRetriever 與可選 OllamaMemoryRelevance。沒有第二個 MemoryStore。
- `siro demo --memory-profile <JSON>` 明確啟用 hybrid 或 relevance 檢索；無 profile 保持
  lexical-only，沒有本機模型 HTTP 呼叫。profile 不得夾帶寫入權限或未知設定。
- 設定檔限 8192 bytes 的 regular JSON、拒絕重複鍵、嚴格型別、固定 digest、literal loopback、
  cloud model tag、無效端點／維度／預算均拒絕。設定錯誤在 SQLite initialize 前停止，錯誤不回顯值。
- 整筆來源 context byte budget 沿用 CompanionCore；查詢失敗不偷偷 fallback、取消不假成功；
  終止失敗回傳非零，不將 provider body 顯示給使用者。
- 必要測試適配：activity test 固定 schema15／舊14 reader，不再假設15永遠是最後 migration；
  runtime status test 解碼 data_only observation JSON 後檢查派送紀錄，保留原權限／隱私斷言。
- 根 `.venv`、`target` symlink 加入 ignore，避免把 task 專用環境指標提交。

**回答仍使用 OfflineDemoModel**，入口會明示；這是檢索到對話的接線試用，不是新聊天模型，
也不是中文回答品質認證。原 demo 對話紀錄與可重建向量快取仍會保存到指定 data 目錄；
不新增自動長期記憶、候選批准、人格更新、工具執行或主動提醒。

## 驗證與未通過項目

| 批次 | 實際結果 | 界線 |
| --- | --- | --- |
| 新增 profile／composition／CLI 專項 | 32 PASS | 真 SQLite／Core、mock HTTP，非模型語意測試 |
| 加兩份必要測試適配 | 87 PASS | 包含前述32，不加總 |
| 初輪全 `tests` | 2949 PASS／48 FAIL／19 SKIP，694.97s | `full-v1-receipt.json`，完整整合未過 |
| 專用環境 selected v2 | 1241 PASS／14 FAIL／0 SKIP，268.62s | 剩14個 trusted worker 路徑失敗 |
| 從 workspace/.venv 入口驗 worker | 72 PASS，12.82s | 不擴 sandbox mount，與後續批次重疊 |
| **最終 selected v3** | **1254 PASS／1 FAIL／0 SKIP／7 warnings，314.59s** | **不是 PASS receipt**；含 unit／contract／記憶與實際啟動、發布、Rust、技能／取消等所列 targets |

最終失敗：`tests/integration/test_data_owner_callers.py::test_actual_gateway_process_blocks_competitors_until_shutdown`。
資料已有 Gateway owner 時，第二個程序應拒絕；本輪在 `subprocess.run(..., timeout=5)`
發生 TimeoutExpired，沒有在定義的五秒內返回。**沒有延長門檻或將單次重跑成功當解決**。
較早環境重驗五項通過（含相同案例）保留為局部結果，不能取代最終混合負載失敗。
此入口以外的正式 Gateway 接線仍待原 owner 交接；未修改 Gateway 產品碼來迴避 gate。

三份 receipt 的 source before/after 均一致。最終 source content SHA256：
`cf8a3d0af90d8d3ad1c27eff1b6791a9055027974fef02e7779190f09e073a64`，
harness 320.020s；宣告 L1，不等於自動認證 L2/L3。
最終 runtime 程式／測試之後只加入交接與本報告／摘要，沒有更改已驗執行碼。

Ruff check／format：六個新增或修改 Python 檔 PASS；strict scoped mypy：CLI、組裝器、
兩份新測試共四檔 PASS。schema export --check PASS。四檔 scoped detect-secrets 零 finding，
見 scoped-secrets.json；不能推導全庫 gate 通過。

初輪全域 Ruff 有155個診斷，涉及六個與 main 基線相同的檔案；未修改它們或放寬規則。
初輪 mypy 13 errors／7 files（含環境缺 faster_whisper）；專用環境最終全域 mypy
**11 errors／6 files，332 files checked**，仍未通過。activity test 的既有 return 型別錯誤
所在區塊未改。全 scripts/check／Rust test+clippy／遠端 CI 未在本輪完整執行，不能宣稱全綠。
初輪桌寵／前端／secret baseline 等失敗也未因 selected v3 改寫成完成；詳失敗摘要。

## 環境修正與可重現方法

開始先盤點缺項，沒有新增依賴或下載模型。使用既有 cache：

```text
UV_PROJECT_ENVIRONMENT=/home/pepepig/.local/share/siro/memory-runtime-integration-20261022 uv sync --locked --offline --all-groups
rustup run 1.97.1-x86_64-unknown-linux-gnu cargo build --locked --offline --workspace --target-dir /home/pepepig/.local/share/siro/memory-runtime-integration-20261022-target
```

實際103項 resolved、102項從 cache 安裝，Rust build 26.22s；venv／target 在 WSL ext4，
工作區 symlink 指向它們。初輪測試產生的 Windows-mounted `.venv` 沒有刪除，
保留在 task 父目錄 `first-run-venv`；移動前已確認兩個絕對路徑均在 task root。
沒有重指共用 venv。只對 task 專用環境預編譯已安裝套件 bytecode，未抑制 warnings 或放寬 sandbox。

trusted worker 只看得到 workspace/.venv；即使實體放 ext4，也須用下列入口重現，
不能改用 `/home/.../bin/python` 後聲稱該路徑已掛入沙箱：

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python scripts/run_acceptance.py <selected-v3-receipt.json 的 targets> --output <工作區外新目錄> --level L1 --git-executable git.exe
```

targets／命令／Python版本／結果在 receipts。完整 raw logs、環境 probe、Rust build、
Ruff／mypy 診斷保存在 `E:/coding/Worktrees/memory-runtime-integration/` 的
`MEM-RUNTIME-*-20261022*` 檔案；本目錄僅提交 receipts、失敗名稱與數量摘要、scoped scan，
不盲目將 subprocess traceback／SDK／對話原文輸出收進 Git。

## 試用入口

在 WSL 本工作區，用獨立合成資料或已完成相容性檢查的隔離備份。初始化會套用到 schema18；
不要把此範例指到正在使用的私人 DB。舊 max_schema15 的 release 不會因此取得讀新版 DB 的能力。
profile.json 可使用已確認安裝的本機 model pins：

```json
{
  "mode": "relevance",
  "base_url": "http://127.0.0.1:11434",
  "embedding_model": "qwen3-embedding:0.6b",
  "embedding_digest": "ac6da0dfba84a81fdbfbaf330198c33cd77c4cdfc53e8bc50eb581914a15621d",
  "dimensions": 1024,
  "relevance_model": "qwen3:4b-instruct",
  "relevance_digest": "0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0",
  "context_bytes": 8192
}
```

```text
.venv/bin/python -m siro.cli demo --data /tmp/siro-memory-isolated-demo --memory-profile /path/to/profile.json --once "先前記錄的充電器在哪裡？"
```

新 data 沒有來源就回答沒找到；本輪沒有新增造假記憶的 seed 指令。
hybrid 模式移除 relevance_model／relevance_digest，不用篩選模型；不傳 memory-profile
回原離線字詞檢索。context_bytes 只限制記憶來源片段，不能冒稱整個模型視窗或 token 成本。
當 context_bytes=0 仍可能先檢索再剔除來源，不代表零推論費用。
Windows loopback 的 tags 已核對上列兩個 digest；WSL CLI 仍要求同一執行環境的 loopback 可達，
沒有更改網路轉發或服務設定。本輪 HTTP 模型呼叫由測試 transport 模擬，未重跑真模型語意組。

## 交接與限制

本輪沒有改 main checkout、正在運行的服務、私人 DB／keys／設定或 Gateway／UI 產品碼。
工作期間 main 已另前進到觀察值 `3e242fb5e75300f18518da8c7bd3caf08a556689`；
本分支只驗前述89b基線，較新 main 尚待序列整合，不對其宣稱本輪驗收有效。

下一步：由 Gateway owner 解決並重驗五秒拒絕 gate；再按
[RT/Hermes 接續](../../memory-evolution/RT-HERMES-INTEGRATION.md) 做正式裝配與審閱入口。
MEM02最新25/30低於27/30、MEM03真Auth／Policy／UI與清除、背景保存／提醒、T30 trace feed
仍未完成；不可因 profile opt-in 越過原產品品質／權限 gate。真語音／真人／硬體／長時間驗收未跑。
共享 STATUS／roadmap 由整合 owner 接收本報告，不覆寫其他工作。

回退：移除 demo 的 memory-profile 即恢復字詞路徑；停用該試用程序，保留資料與 revisions。
本卡無 schema19；對已到18的資料不能用舊程式或舊備份覆蓋回退。文件／CLI變更可在本分支
按 commit 回退，正式部署回退仍待獨立驗收。NOT PUSHED／未 PR／未合併 main／未部署。

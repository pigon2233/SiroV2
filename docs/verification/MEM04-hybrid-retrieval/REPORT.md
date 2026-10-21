# MEM04 混合記憶檢索 — 2026-10-20

**LOCAL_ONLY / NOT PUSHED；檢索基礎已實作，產品驗收仍 PARTIAL。**

分支 `codex/memory-hybrid-retrieval-20261020`，基線
`012dce8cb0c844b6ebbc4395c3b38591694b07ce`；獨立工作區
`E:/coding/Worktrees/memory-hybrid-retrieval/SiroV2`。
認領與先行契約見 [任務紀錄](../../collaboration/MEM04-hybrid-retrieval.md)。
本機提交由該分支 `git rev-parse HEAD` 與本輪交付訊息確認；未推送、合併或部署。
STATUS、PLAN、DECISIONS 等共享狀態留待整合者更新，避免覆寫其他工作。

## 交付內容

- 以注入方式啟用 `HybridMemoryRetriever`，原 `MemoryService` 預設仍使用關鍵字。
  同一查詢合併 lexical 與 cosine 排序，採 RRF `1/(60+rank)`、最多回傳五筆。
  lexical 也必須符合向量相關度門檻，避免泛用字詞繞過篩選。
- 使用既有本機 Ollama 的 `qwen3-embedding:0.6b`，1024 維。只允許 literal
  loopback HTTP，拒絕 redirect／環境 proxy，請求 `truncate:false`；查詢加英文
  retrieval instruction，文件不加。前後驗證模型 digest；向量數量、維度、有限值及
  非零長度均驗證。這依賴可信任的本機 daemon，不是對惡意 tag ABA 替換的原子證明。
- SQLite schema 18 新增向量快取，無新向量 DB／Python 套件；快取不複製原文。
  key 綁定模型名稱、digest、維度、格式版本；每筆再綁 revision 與完整來源 hash。
  corrupt cache 重新計算。記憶更正、刪除、撤銷及衍生失效與 cache 清除同 transaction；
  review transition 透過相同 invalidation helper 清除 root。保留既有版本與來源。
- 嵌入前先檢查 identity/person、committed、有效時間、privacy、來源撤銷與完整 lineage；
  每批送出前再查，cache 寫入與推論後再次核對。最終沿用 Core context snapshot 與
  dispatch 前來源檢查；相似度不授權、不確認事實、不把相衝突文字自動合併。
- 每 instance 一個 refresh owner，文件每批最多 32、corpus 最多 1000，總 timeout
  預設 120 秒。容量計算以 scope 內 committed rows 為上限，含尚未做 TTL/privacy
  排除的 rows；超量直接報錯，不默默只搜一部分。沒有隱藏的 lexical 成功降級。
  Task 取消會傳到 HTTP；SQLite 工作取消仍 shield/join 至 transaction 結束。
  關閉 HTTP 不能保證 Ollama GPU 當下停止計算。
- 指代續問只補入同 session 最近兩則使用者文字、每則最多 512 字作查詢提示。
  原始當前訊息與 native dialogue 不被改寫或截短；不拿助理猜測當個人記憶。
- `CompanionCore(memory_context_bytes=...)` 可限制 memory packet 的 UTF-8 bytes
  增量，包含 provenance。超限依排名移除整筆，再重建 snapshot；保留既有來源
  excerpt 規則。這不是 tokenizer token 數，也不取代全 request／output reserve guard。

## 真實 embedding 量測（合成資料）

固定 corpus：20 筆目標記憶＋10 筆近似干擾；另有 4 題無答案、20 題小型保留測試。
原始結果見本目錄 JSON；沒有使用 fake vectors 計算語意分數，沒有私人對話／DB。

| 指標 | 實測 |
|---|---:|
| 開發集 lexical 正確來源 top-5 | 2/20 |
| 開發集 hybrid 正確來源 top-5 | 19/20 |
| 開發集 hybrid 正確來源 top-1 | 17/20 |
| 開發集無答案時不附記憶 | 4/4 |
| 保留集正例 top-5 | 9/10 |
| 保留集無答案時不附記憶 | 9/10 |
| 第一題冷索引時間（30 筆文件） | 2.006 秒 |
| 後續 19 題檢索中位時間 | 0.083 秒 |
| 重建 service/cache instance 後檢索 | 0.078 秒 |
| 首輪文件 embedding inputs／全部查詢後 | 30／30 |

前一版門檻 0.3 是 20/20 top-5，但 4 題無答案全誤召回；診斷後改為 0.5，並要求
lexical 同樣通過門檻。**20 題開發集被用來調整門檻，不能聲稱是盲測。** 保留集在
調整門檻後、執行之前固定，未用它再調參；其規模仍不足以代表日常使用。
0.5 是這個 pinned 1024 維模型的經驗門檻，不是「事實正確率 50%」。

剩餘錯誤：開發集「買飲料要避開何種成分」漏查咖啡因；保留集「喜歡的語文和長度」
漏查繁體中文／簡短偏好；「最喜歡什麼顏色」錯召回「偏好深色介面」。來源仍有效
不代表回答屬性相符。A10 的 top-5 數值達 18/20，但衝突推論、完整 A10／產品驗收
尚未完成，不能單憑此表宣稱通過。

### Token 比較的精確邊界

使用現有 `qwen3:4b-instruct` `/api/chat` 真實 `prompt_eval_count`，`think:false`、
`num_predict:1`、`num_ctx:32768`，不評分生成答案。只測合成案例 2（過敏原）：

| 同一問題的輸入策略 | 記憶數 | 實測整體輸入 tokens |
|---|---:|---:|
| 將全部 corpus 與來源送入 | 30 | 15,382 |
| hybrid 只附召回記憶 | 2，包含正確來源 | 2,109 |
| lexical | 0，未找到正確來源 | 1,124 |

hybrid 相對「全部送入」少約 86.3%；這是單一成功召回案例，不是所有對話的節省率。
它比漏查來源的 lexical 多用 tokens。向量不直接傳給聊天模型；仍需傳回必要原文／來源。
早期 token 請求返回 HTTP 400，沒有冒稱成功；後來在測量請求明確設定 context window
才成功。未保存第一次 provider 詳細錯誤，不能斷言 400 的唯一原因。一次中間測量用到
未召回的案例 1，保留為
`threshold-case1-preliminary.json`，不能用它的低 token 數證明有效節省。
正式樣本為 `real-retrieval-case2.json`，不是全 20 題的平均或答案品質驗收。

## 測試與證據

- 新測試 40 項，包括 HTTP 協定／錯誤／取消、profile 隔離、跨重啟 cache、privacy、
  candidate/TTL/future/scope 排除、來源更正／撤銷／envelope 競態、衍生 invalidation、
  corrupt cache、容量／timeout、重複取消等待 writer、續問 hint、實際 Core packet
  預算與 native 原文保留、17→18 升級與 rollback、舊 max-schema 17 拒絕 18。
- 26 個完整測試檔：**631 PASS、0 FAIL、0 SKIP，7 warnings**；pytest 96.75 秒。
  `regression-pass/receipt.json` 包含完整命令、targets、版本與測試前後一致的 source
  fingerprint。這是 selected L1 宣告，不是自動產品認證。log 另存供重現。
  測試後只新增／更新交付文件與匯入證據，沒有再改 production code。
  版控中的 pytest.log 僅移除行尾空白；未修改測試結果，原始 log 留在 `/tmp/siro-mem04-*`。
- 首輪 **617 PASS／14 FAIL**，原因是隔離工作區缺少原生 token guard 的固定 tokenizer
  資產；沒有跳過失敗測試。以既有 `scripts/setup_context_tokenizer.py` 補齊五個公開
  pinned 檔案（合計 27,902,275 bytes，含 Apache-2.0 LICENSE），全部雜湊驗證後重跑。
  它們在本 E: worktree 的 ignored cache；不是 GPT-OSS 模型權重。失敗 receipt/log 保留。
- Ruff check／12 個檔案 format check、scoped strict mypy 9 檔、`git diff --check` 通過。
  Full scripts/check、全 repo mypy／secret scan 未重跑，先前專案全域 gate 不因此解除。
- scoped detect-secrets 14 個實作／測試／腳本／認領文件：1 個 finding，人工核對是
  `evaluate_memory_retrieval.py` 的公開 Ollama model digest。沒有新增 ignore 規則或聲稱
  「零 finding」；原始掃描保留在 `scoped-secrets.json`。

主要重現命令（在此 worktree、既有 WSL venv，設定 `PYTHONPATH=src`）：

```bash
python scripts/evaluate_memory_retrieval.py --output /tmp/new-mem04-eval.json --measure-tokens
python scripts/setup_context_tokenizer.py
```

完整回歸使用 `scripts/run_acceptance.py --git-executable git.exe --level L1`；26 個 targets
與新的 output directory 寫法以 receipt 的 `command` 為準，不覆蓋既有證據。
評測 script exit 0 表示完成量測，並不表示所有品質條件通過。

## 使用與剩餘整合

可在取得部署／整合範圍後，用同一 SQLiteStore 建立 `SQLiteMemoryVectors`、
`OllamaEmbedder(EmbeddingProfile(model, digest))`、`HybridMemoryRetriever`，注入
`MemoryService(repo, retriever=...)`，並明確設定 Core 的 `memory_context_bytes`。
未注入時行為不變；新分支初始化 DB 則仍會套用 schema 18。

本輪未修改 Gateway、UI、現用服務設定或私人 DB；沒有讓使用中的聊天自動啟用。
只新增必要的 embedding 權重（639,150,858 bytes，E:-hosted WSL）及上述公開 tokenizer；
現有聊天模型 tag、daemon 與服務設定沒有更改，測量的 context window 僅作用於請求。

下一步應先補屬性／主體對應及保留集反例，避免把近似記憶當答案；再接 scheduler 的
L3 背景預熱、跨 instance 的 batch owner、使用者停止、可理解的失敗狀態與明確開關。
目前 task cancellation 已驗，但產品 stop→retrieval 的完整接線與 GPU 資源讓步未驗。
原 MEM02 理解門檻、MEM03 正式 owner/Policy/Gateway/UI 及 retention/purge 仍各自待驗，
不因向量召回改善而完成。向量的 logical deletion 也不是 WAL／備份的物理抹除證明。

回退：尚未部署，不需動現用服務；整合時先關閉注入回到 lexical。已升級至 18 的 DB
要搭配相容 release；舊版回退須使用先前備份，不能只改 schema 數字或刪歷史記錄。

官方介面：[Ollama embed](https://docs.ollama.com/api/embed)、
[Qwen3-Embedding-0.6B model card](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B)。

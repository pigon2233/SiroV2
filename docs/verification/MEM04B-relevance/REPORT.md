# MEM04B：記憶來源相關性驗證

日期：2026-10-21 Asia/Taipei。狀態：LOCAL_VERIFIED_FOUNDATION / PARTIAL_PRODUCT。
本機交付，NOT PUSHED；未建立 PR、未合併、未部署。

工作區：`E:/coding/Worktrees/memory-hybrid-retrieval/SiroV2`。
分支：`codex/memory-relevance-20261020`。
基線：`64c2c24b52b8c0dcbed18e271765db1c0571f505`。
認領及實作前契約：[MEM04B-relevance](../../collaboration/MEM04B-relevance.md)。
本提交以 `MEM04B:` 開頭；完整交付 SHA 由本機提交紀錄及交接訊息提供。

## 實作與邊界

在原有向量／字詞檢索後加入可選的本機來源篩選器，判斷人物、屬性、限定條件、
確定性與來源事件類型。未注入篩選器時維持既有行為。有篩選器時候選相似度
預設可放寬至 0.3，最多八筆，獨立逐筆分類，最後最多回傳五筆原始記憶。

模型只能選來源索引及提供原文引句，不能改寫記憶、授權或產生實際回答。
來源事件類型取自同一次 SQLite 讀取的 authoritative envelope；事件類型不等於
已驗證說話者身分。Core 在等待分類後重新核對來源版本、雜湊、存取範圍、
期限與撤回狀態；變更或錯誤會拒絕操作，不假稱檢索成功。

使用已安裝 `qwen3:4b-instruct`，digest
`0edcdef34593eac1aa2be9c7d06c432dcf81945adca5eca2f27662c18f168ba0`。
向量仍用既有 `qwen3-embedding:0.6b`、1024 維。無新增模型、套件或 migration；
資料庫仍為既有 schema 18。僅允許 literal loopback HTTP，禁用環境代理與重新導向，
模型 digest 在推論前後及快取命中時均核對。取消可向下傳遞，沒有隱藏重試。

分類快取上限 128 組，鍵包含問題、來源綁定、來源文字、事件類型、模型及提示版本的
雜湊；值只有選取索引。快取不替代授權，也不保存原文 log。
所有模型呼叫（含失敗回應）計入成本；取消或未取得用量時保留 unmeasured 計數。

輸入另有欄位與整包上限。所有獨立配對在任何 HTTP 前完成視窗預檢：
policy UTF-8 bytes + 配對 JSON UTF-8 bytes + 1024 framing reserve + 768 output
reserve 不得超過 16384。這是保守輸入門檻，不是精確 tokenizer 計數；
超限整筆拒絕，不截短來源。模型輸出須完整結束、符合嚴格 schema、每筆有判定、
引句必須在原文中；重複鍵、偽造引句、工具呼叫、錯誤模型與截斷輸出均拒絕。

API 依據：[Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs)、
[Chat API](https://docs.ollama.com/api/chat)。未更新 daemon，未採用需新版服務的功能。

## 真實模型測試：合成資料

以下是本機實際 Ollama 推論，使用合成資料與暫存 SQLite，並非正式 Gateway、UI
或私人記憶資料庫。對照題在第一次推論前固定，但之後用於調整提示，因此全數視為
已知開發回歸；former holdout 也不再是獨立盲測。

| 版本 | 對照題 | 原開發題召回 | former holdout 正例 | 舊缺來源題 | 決策 |
| --- | --- | --- | --- | --- | --- |
| v1 批次索引 | 29/32 | 未留完整結果 | 未留完整結果 | 未留完整結果 | 保留失敗證據 |
| v2 陣列判定 | 27/32 | 10/20 | 8/10 | 13/14 | 拒絕，漏判定列 |
| v3 keyed schema | 30/32 | 19/20 | 10/10 | 13/14 | 持續修正 |
| v4 來源事件類型 | 31/32 | 未跑全組 | 未跑全組 | 未跑全組 | 持續修正 |
| **v5 獨立 JSON 配對** | **31/32** | **19/20** | **10/10** | **14/14** | **採用** |
| v6 單 token 判定 | 26/32 | 17/20 | 6/10 | 14/14 | 拒絕，低於 18/20 召回門檻 |

v5 對照題為正例組 17/18、負例組 14/14。固定的缺來源、他人及注入負例通過，
不表示所有未見輸入都能正確判斷。召回分數只要求目標來源出現在回傳集合，
不能據此宣稱所有額外回傳來源皆正確。最終回答內容並未評分。

已知漏記：R32「我希望你的回答長一點還是短一點？」未選出
「我希望你用繁體中文，簡短回答就好。」；開發題「電腦沒電了，電源供應器放哪裡？」
也未選出目標來源。因此不標記整體記憶或產品 DONE。

原始量測為 `v*-evaluation.json`、`v*-contrast.json`、`v*-progress.jsonl`，各版本
adapter 快照為 `v*-adapter.txt`。v5 真實語意量測完成後，最終程式另加上錯誤回應形狀
處理與長輸入預檢，沒有重跑整組模型語意題。最終 POLICY 與 v5 快照逐字相同，
SHA256 為 `e41274a15042ce03083c687a98c24111afcbfbd730e6931ec5fbd453b0697b9c`；
其短案例輸入協定不變。新增邊界由下列回歸驗證。

先前中斷後消失的 `/tmp` 首輪結果不列作完整驗收；本目錄保留後續持久化結果。
已失敗實驗未刪除。匯入 `.log` 僅移除行尾空白以符合 diff 檢查，沒有更改結果數值。

## token 與時間

`v5-token-probe.json` 的同一筆成功合成問題：

| 項目 | 實測 |
| --- | ---: |
| 全部 30 筆記憶的聊天 prompt | 15460 tokens |
| 篩選後聊天 prompt | 1631 tokens |
| 分類輸入／輸出 | 4393 / 132 tokens |
| 分類加篩選後聊天 prompt | 6156 tokens |
| 首次／立即重複檢索 | 12.022 / 2.117 秒 |
| 立即重複分類輸入／輸出 | 0 / 0 tokens |

單筆冷查詢的生成模型 token 合計約減少 60.18%，不包含 embedding tokens 或最終回答
輸出。聊天探測僅生成一個未評分 token。冷查詢包含索引與模型載入成本；立即重複
發生在聊天 token 探測之後，不能直接解讀為常態延遲。
完整舊 44 題回歸中位數約 4.200 秒；完成多題後再問最早問題，LRU 已淘汰，
再耗分類輸入 4393／輸出 130 tokens，約 4.299 秒。不能宣稱一般查詢都零分類成本、
最省 token、達成 p95 或產品 SLO。較便宜但失準的 v6 未提供為正式選項。

## 最終程式回歸與可重現方式

`regression-v2-receipt.json` / `regression-v2.log`：28 個完整測試檔，
**698 passed / 0 failed / 0 skipped / 7 warnings**，pytest 91.24 秒，harness 93.270 秒。
來源 before/after content SHA256 相同：
`3ec6b3b8e07830b0bf25da6dd80ec9d5ff365b6170bcdb893b901a2ab974a964`。
這是 selected pytest 驗收，不是全產品驗收；receipt 的 L1 是宣告，非自動認證。
v1 receipt 保存預檢補強前的 697 項通過紀錄。

67 個新 unit/integration 案例使用 mock HTTP／假向量／真 SQLite，涵蓋嚴格協定、
來源變更／撤回／私密／到期／事件類型改動、取消釋鎖、失敗成本、快取與範圍。
長配對測試先觀察到失敗（原程式已送 HTTP），補強後在任何 HTTP 前拒絕。
這些測試不作為模型語意準確率證據。

在 WSL 設定 `PYTHONPATH=src`、`PYTHONDONTWRITEBYTECODE=1`，使用既有 ext4 venv
`/home/pepepig/.local/share/siro/venv/bin/python`。完整測試檔列表、pytest 命令、
環境與統計皆在 receipt；可將同一 targets 傳入：

```text
python scripts/run_acceptance.py --output <工作區外的新目錄> --level L1 --git-executable git.exe <receipt.targets>
```

重跑實際模型量測（會消耗本機推論資源，output 必須尚不存在）：

```text
python scripts/evaluate_memory_relevance.py --output <新的完整結果.json>
python scripts/evaluate_memory_relevance.py --token-probe-only --output <新的token結果.json>
```

本輪另對七個變更 Python 檔執行 Ruff check、format check 與
`mypy --strict --follow-imports=silent`，均通過。七檔為 adapter、port、Core retriever、
SQLite vectors、evaluation script、兩個新測試檔。未重跑全專案 check／全域 mypy。
`scoped-secrets.json` 為前次九路徑掃描：一筆 high-entropy finding 是 evaluation script
第 50 行的公開固定模型 digest，人工核對非 secret，未新增忽略規則；不宣稱零 finding
或全域 secret gate 通過。最終長輸入補強未新增憑證／外送設定。

## 交接、限制與下一步

目前只是可選元件，未接入正式 Gateway、主畫面、背景排程或既有私人資料。
MEM02 上下文角色／矛盾／澄清仍有缺口，MEM03 正式 Auth／owner 綁定、
記憶審核入口、保存／清除流程與 T18/T30 全流程仍需各自驗收。正式主動記憶與
自動寫入沒有因此完成；本元件完全不寫入記憶。

下一個同範圍步驟：另凍結未見正／負例，驗證漏記與多餘來源率、回答正確性、
多題快取成本與延遲，再由 Gateway/UI 原 owner 接線。不得將目前來源選取測試
當成背景記憶可自行生效的授權。

共享 `STATUS.md`、`DECISIONS.md`、roadmap 未取得 owner，更新事項由整合者依本報告
補入。舊 `MEM04-hybrid-retrieval/REPORT.md` 的使用者未提交文字改動保留，
不包含在本次 commit；提交後工作區預期仍有該一筆 dirty。原 checkout 未改動。

回退：組裝時省略可選 relevance filter 即恢復既有檢索路徑；未新增 migration。
若整體回退 MEM04，須另遵循 schema 18 相容性，不能直接用舊版開啟新版資料庫。
成果留在本機分支與 commit，NOT PUSHED。

# FIX-003 — provider completion repair

2026-10-07；baseline c1d2d41＋既有規劃文件 dirty；Python 3.14 venv、Linux、本機 Node／SQLite／HTTPX。使用者已授權依三份規劃實作。**本卡 DONE / VERIFIED（限定如下），尚未部署至正在運行的私人服務；其餘卡未因此完成。**

## 修復與實證

OpenAI-compatible 邊界以 ProviderOutputTruncated／Filtered／Incomplete 保留固定原因；length／filter／unknown／非正常 SSE EOF 不再當完成。保留 partial，正常 stop／tool_calls、reason-less DONE 與完整 legacy JSON 仍可用。工具在終止確認前不 yield，未完成不 dispatch／retry；取消優先，owned transport 明確關閉，cleanup failure 不能蓋掉原原因或移除 buffered-intent fence。UI 半句後也顯示未完成，不朗讀為成功。

不改 Core／ports／其他 provider／512 output budget／native guard／資料 schema。近期私人樣本實際截斷原因仍未知，本卡不假稱已解所有語言品質問題。

| 證據 | 結果與界限 |
|---|---|
| `before.log`；adapter／UI 新反例 | 修前 15 FAIL，非預期通過；涵蓋 stream／non-stream length/filter/unknown、裸 EOF、partial UI |
| `regression.log` | 修後相鄰回歸 149 PASS／3 warnings，39.81 秒；conversation、batch、terminal、restore、native budget 等；較後 cleanup 分支另以下列 final suite 驗 |
| `completion-first.log`、`candidate-continuation.log` | 初次新整合 76 PASS／2 FAIL；兩處 fixture 誤把 candidate 私有 call ID 當 native ID，改為精確 proposal／journal 綁定，2 FAIL cases 重跑 PASS。未修改 production identity 契約或放鬆 effects 驗收 |
| `cleanup-before.log` | 獨立 review 發現 cleanup exception 可能蓋原因／重試，修前 3 FAIL；局部修復後納入 final suite |
| `final-completion.log` | 最終 81 PASS／3 existing warnings，7.05 秒；含真 loopback HTTP SSE → 真 adapter → controller → SQLite 的 8-case legacy/candidate、initial/continuation、length/EOF，與 restart/readback/no-replay |
| `configured-provider-first.log` | 真配置模型首輪兩個合成 case 通過，但暴露 async-generator cleanup warning；不以退出0掩蓋此缺口。已補 explicit close 與固定反例 |
| `configured-provider.json` | 修後真配置模型兩個合成 case PASS：正常短答0.621秒；8-token 故意限額0.574秒→ProviderOutputTruncated、無finished。共兩輪4個有界新請求，未重播私人對話／工具。此為功能樣本，不是延遲 p95 |
| `mypy.log`、changed-file Ruff check／format | mypy196files PASS；Ruff PASS。沒有執行本輪全套 pytest 或遠端CI |
| `source.patch`、`rollback.json` | 隔離目錄從 HEAD source apply→reverse check→reverse，4個原檔完全恢復、新測試移除 PASS；含 patch/source SHA256。這是 source 回退，不等於私人部署回滾驗收 |

主要命令：`.venv/bin/pytest -q tests/contract/test_model_adapters.py tests/contract/test_failover_policy.py tests/integration/test_frontend_companion.py tests/integration/test_provider_completion.py`；`.venv/bin/mypy`；changed-file `.venv/bin/ruff check`／`format`；`.venv/bin/python docs/evidence/FIX-003-2026-10-07/probe_configured.py --run-configured`。

## 驗收邊界

L1：原因／取消／相容／無 fallback／UI 真函式測試。L2：真 HTTP framing 與真 SQLite／controller 合成整合、真已設定模型正常與故意限額；HTTP fixture 的工具效果只是合成 counter，沒有真 OS 操作。failed partial 可回讀、不進 completed hydration；已成 observation 與 exact proposal 綁定保留；重啟不呼叫 provider／executor。

獨立 review 找出的兩個取消／收尾邊界已補反例並修復，最後唯讀 review 無剩餘本卡 blocker。沒有私人 DB 寫入、服務重啟、原聊天匯出、TTS／桌寵／理解品質驗收。FIX-004／005／006 與搜尋 FIX-002 的 gates 保留。

回退只在 drain 後撤本卡精確 patch，保留最新 DB／journal，不重送失敗工具。回退會恢復未完成誤判風險，相關產品 gate 不得自動解除。下一張為 FIX-004：session lifecycle，使用本卡完成的 UI 為相容基線。

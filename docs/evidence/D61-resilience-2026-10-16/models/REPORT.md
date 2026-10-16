# FIX-023 — Model protocol boundary verification

日期：2026-10-16（Asia/Taipei）。範圍為 D61 的既有模型 adapter 局部修復，LOCAL_VERIFIED；未呼叫真模型、未外送資料、未操作正式服務或資料庫。

## 已確認問題與誤報

| 指控／觀測 | 判定 | 實際 evidence |
|---|---|---|
| JSON／Unicode 解析錯誤缺少安全、可識別的 adapter error | REQUIRED_FIX / IMPLEMENTATION_BUG + TEST_GAP | 原 Urllib 與 Ollama 回傳 JSONDecodeError／UnicodeDecodeError；新真 loopback HTTP 測試與 source-only-before.log 重現。 |
| Ollama 合法 `{"error":"..."}` 串流可變成 finished | REQUIRED_FIX / IMPLEMENTATION_BUG | 原 `_stream_response` 沒檢查 error envelope，把它當空 message；真 HTTP 新回歸原版「DID NOT RAISE」。 |
| 解析錯誤使整個 conversation event loop 崩潰 | FALSE_POSITIVE | `core/conversation.py` 原 provider boundary 已捕捉 Exception 並寫 FAILED、發 terminal；新真 HTTP＋SQLite 案例驗失敗後下一輪正常 COMPLETED。 |
| 單模型重試一次一定是缺陷 | FALSE_POSITIVE | RT-009／CONTRACTS 明定本地單 backend 可以在輸出前重試一次，最多兩次；原 bounded retry 測試保持 PASS。 |
| `_cloud_budget` 應改成跨 request 共享扣計數 | FALSE_POSITIVE | 原契約是每個 generation 的額外 cloud request 上限，不是帳單／每日預算。新跨兩輪測試原版即 PASS。 |

## 最小修改

- `src/siro/adapters/models/http.py`：新增 `ProviderResponseInvalid(ValueError)` 與私有 JSON decoder，固定安全文案，從 exception handler 外拋出，避免掛上含原回應的 JSON／Unicode decoder exception chain。既有 urllib response context／offloop I/O 與非 object JSON 拒絕保留。
- `src/siro/adapters/models/ollama.py`：套用同一 decoder，拒絕已知 error envelope，沿既有 `aclose` 模式等待本 iterator 清理；保留原錯誤、取消優先、已輸出的 text／tool，無成功 finished。nonstream transport 已轉成標準錯誤時亦尊重取消。
- `src/siro/adapters/models/openai_compatible.py`：僅替換 SSE event 的一個 JSON 解析點；既有 partial tool-intent note、completion 判定與 cleanup 機制保持。
- 新 `tests/integration/test_model_protocol_recovery.py` 25 案例。既有測試未修改；`failover.py` 與 before snapshot hash 一致。

這些錯誤延續 ValueError 的非 retryable 規則，不擴大 automatic retry／cloud egress。沒有新 Core／port／router、依賴、資料 schema、權限或模型選擇策略。

## 實際驗收

| 執行範圍 | 結果 | 紀錄 |
|---|---|---|
| 原模型／failover／conversation baseline | 72 PASS／6.70s | baseline-adjacent.log |
| 最初新增 13 例、未修 source | 12 FAIL／1 PASS | initial-red.log |
| nonstream decode 完成後取消的中間相容缺口 | 1 FAIL，局部修正後納入最終 PASS | cancel-readback-red.log |
| 最終 25 新例＋原 72 相鄰 | **97 PASS／6.79s**，無 failed／skip／xfail | green-adjacent.log |
| 原 FIX-001 failed-generation dispatch matrix | **32 PASS／2.96s**；13 不相干案例 deselected | accepted-generation-gate.log |
| Ruff／format／mypy（3 source＋1 test）／diff whitespace | PASS | static.log／實際 diff check exit0 |
| 隔離、精確三檔 source-only 反例 | **24 FAIL／1 PASS → 25 PASS** | source-only-before.log、source-only-after.log、source-only-result.json |

新驗收包含真 loopback HTTP 的純文字錯誤、截斷 JSON、無效 UTF-8、Ollama error envelope；合成 iterator 的 partial text／tool intent、decoder error、owned cleanup failure 與輸出／清理時取消；真 ConversationEngine＋臨時 SQLite 的 FAILED → 下一輪 COMPLETED、各一 terminal、兩次 provider request 及實際 turns 持久狀態。OpenAI SSE、cloud policy 由明示合成 transport／model 驗證，不是假稱真雲端推論。

隔離反例在自有 temporary source copy 中只替換上述三個 source 為 before／candidate；25 個測試完全相同。實際 import 路徑、候選 source／test hash、workspace 不變、failover 不變與 temp 清理都有 JSON 紀錄。前後各一個 Python 3.14 SyntaxWarning 來自原 OpenAI `finally` return，該區未改；其他相鄰 gate 的兩個 pypinyin deprecation warnings 亦為既有依賴。source-only-before 的 async-generator cleanup error 記錄保留；candidate 無此 unhandled 記錄。

## 相容、風險與回退

標準錯誤仍是 ValueError；既有 Conversation FAILED／單 terminal／partial text、privacy、輸出預算及輸出後不重試不變。durable error 名稱由 JSONDecodeError／UnicodeDecodeError 改成 ProviderResponseInvalid，屬 D61 已明示的可識別分類。原證據資料不回寫。

回退僅在已停止的隔離候選 checkout 還原 `../before/src/siro/adapters/models/{http.py,ollama.py,openai_compatible.py}`，不動 DB、Core 或 failover；上述 source-only 反例已證明回退會恢復缺陷，不能把舊版當已驗證發布。正式服務未被切換。沒有新 monetized budget、Ollama bare EOF 終止契約或自動降級功能的完成宣稱。

真 Ollama／OpenAI 可用性、模型品質、實體 ESP32、正式部署及完整 CI 不由本局部 PASS 代證；交由根任務記錄合併驗收。

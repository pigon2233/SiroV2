# TOOL-DECISION-20261117

執行者：Claude（遠端控制工作階段）。分支 `claude/tool-decision`，base `144978b`，worktree `E:/coding/Worktrees/tool-decision`。
狀態：PARTIAL（mock 與離線實測通過；尚未在執行中的 SIRO 上開啟驗證）／LOCAL_ONLY／NOT PUSHED。

## 為什麼

實測（2026-11-17，`.scratch/tool-eval/`，未進 Git）：gemma4:e4b 帶完整人設 prompt 時，該用工具的 30 次漏用 22 次。
常見情況是嘴上說要做，卻沒有發出 tool_call。用一個不帶人設的短 prompt 讓同一模型只選類別，未見過的題目可以全對。

## 改了什麼

- 新增 `src/siro/services/agent/tool_decision.py`（flag `SIRO_TOOL_DECISION`，預設 `0`）。
  - 決策：本機模型（`SIRO_TOOL_DECISION_MODEL`，預設 `SIRO_OLLAMA_MODEL`），Ollama `format` 用 JSON schema enum，`think=false`、`temperature=0`、`num_ctx` 至少 8192（透過 `ollama_options` 沿用聊天模型的設定）。選單只列本回合實際提供的工具。輸入帶最近 2 句使用者訊息和 SIRO 上一句回覆前 80 字（疑似金鑰會遮蔽）。
  - 填參數：用該工具的 input_schema 當 `format`，prompt 帶當地日期時間，並要求 task 用繁體中文、指令必須是非互動的。驗證走 `_valid_arguments`，另加頂層字串長度檢查；`computer.execute` 另有互動程式擋單（top 只允許 `-b`，python/node 不帶參數也擋）。不合格就視為沒有決定。
  - Groq 複核：只有本機回 none、看起來是追問（上一回合用過工具，或 SIRO 上一句是拒絕），而且這回合允許上雲時才會呼叫。重用 `OpenAICompatibleAdapter`、`SIRO_OPENAI_API_KEY`、`SIRO_COMPUTER_GROQ_MODEL`（預設 qwen/qwen3.8-27b）；任何失敗都保留本機結果。
  - 每次決策寫一行到 `$SIRO_DATA_DIR/tool_decisions.jsonl`：時間、句子前 120 字、選擇、來源、參數是否合格、延遲。
- `integrated.py`：在 `route_tools` 之後呼叫 `_decide_tool`。決定出的 ToolCall 在 `decided_tool_call(...)` 區塊內，交給包在 ConversationEngine 外層的 `DecidedToolModel`：第一個提供該工具的模型請求，會直接回這個 tool_call，不會呼叫主模型。
  - 理由：這樣 CompanionCore 會照常把 `assistant(tool_calls)` 寫進 history，之後走既有的 `_propose_tool_calls`、批准、orchestrator 驗證、觀測回填和續寫。工具結果回來後，由原本的人設模型回話。歷史紀錄的格式和模型自己呼叫工具時完全一樣，不需要另外補訊息，也沒有繞過任何安全檢查。
  - flag 關閉、legacy profile、決策為 none 或失敗時，流程完全不變（不包裝模型，也不送請求）。

## 驗證

- 新測試：`tests/unit/test_tool_decision.py`（假 LLM：決策、參數、互動擋單、Groq 只在追問且允許上雲時呼叫、flag 關閉、包裝器只送一次）；`tests/integration/test_tool_decision_turn.py`（candidate 回合：決定的呼叫走提案路徑、history 為 system/user/assistant(tool_calls)/tool 且 id 配對；flag 關閉和 none 都不影響）。新測試與相關回歸一起跑 82 passed。
- ruff check／format 與 mypy（新模組）通過。
- WSL 全套：3648 passed、16 failed、20 skipped。
  - 13 個 skill sandbox 測試：用未修改的 base 原始碼、同樣在 main checkout 以外的路徑跑，也會失敗（base 是 14 failed），屬於路徑／沙盒環境問題。
  - 3 個（`test_provider_completion` 的兩個 candidate case、`test_qwen_lifecycle` metadata-cap）：單獨重跑 3/3 通過，屬全套負載下的不穩定。
- 未見題實測（真 gemma4:e4b，不執行工具；題目與標答先存檔才跑，在 `.scratch/tool-eval/round3/`）：
  - 本機：單句 20/20，多輪 38/40（漏「你可以用 Claude 查啊」2 次），平均 0.51 s。
  - 本機＋Groq 複核：單句 20/20，多輪 39/40，平均 0.98 s，Groq 呼叫 10 次。
  - 第一次跑時模型是冷啟動，有 4 次超過 20 s 逾時，安全退回原流程。這份紀錄保留為 `results3_run1_coldstart.json`。

## 限制與下一步

- 尚未在執行中的 SIRO 上開啟。開啟方式：在 `~/.local/bin/siro-companion-vrm` 加 `export SIRO_TOOL_DECISION=1`，再由擁有者重啟。
- 正式 gateway 環境沒有 `SIRO_OPENAI_API_KEY`（launcher 會 unset，start-win-backend 只匯出 `SIRO_COMPUTER_*`），所以目前 Groq 複核不會啟用，只用本機結果。
- `OpenAICompatibleAdapter` 不能送 `reasoning_effort`，qwen3 有時會思考過長導致解析失敗，這時退回本機結果（實測 10 次裡有 1 次）。
- 冷啟動時，決策會在 20 s 後逾時才退回，那一回合會慢 20 s。
- 決策會在 `assistant_started` 之後多花約 0.2–0.6 s。
- `docs/STATUS.md` 是共享檔，沒有修改，交給整合者更新。

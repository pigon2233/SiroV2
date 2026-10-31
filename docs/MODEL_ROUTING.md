# 依任務選擇對話模型

預設行為不變：設了 `SIRO_OLLAMA_MODEL` 就只用本機 Ollama；沒有 Ollama 才用
`SIRO_OPENAI_API_KEY`／`SIRO_OPENAI_MODEL`（Groq 或其他 OpenAI 相容端點）。
`SIRO_MODEL_ROUTER=0` 時不會因為同時寫了雲端金鑰就把閒聊或推理送出去。

## 開啟

在 `.env.local` 加上（`scripts/launch_companion.py` 會讀這些名稱）：

```bash
SIRO_MODEL_ROUTER=1
SIRO_OLLAMA_MODEL=qwen3:4b
SIRO_OPENAI_BASE_URL=https://api.groq.com/openai
SIRO_OPENAI_MODEL=openai/gpt-oss-20b
SIRO_OPENAI_API_KEY=你的金鑰
SIRO_CLAUDE_BUDGET_CALLS=10
```

Claude 用這台電腦已經登入的 `claude` 指令，不另存 API 金鑰。模型名稱沿用
`SIRO_CLAUDE_MODEL`（預設與 `claude.ask` 相同）。找不到指令、或
`SIRO_CLAUDE_ENABLED=0`，就不會把 Claude 排進對話。

至少要有兩個提供者（本機、Groq、Claude 裡的兩個）才會分流。只設一個時，
仍走原來的單模型。只有 Claude 時，額度用完就沒有下一家，畫面上會說明何時可以再用。

本機 Ollama 仍須維持 `SIRO_CONTEXT_TOKEN_BUDGET_ENABLED=0`。啟動器本來就不允許
在沒有已驗證 tokenizer 的模型上打開 token 預算；這次沒有改那條規則。

## 怎麼選

分類是規則，不是再叫一次本機模型。8GB 顯示卡已經同時跑 4B 與語音，
分類若再佔一次 GPU，閒聊會更慢，也比較難寫測試。

- 請求是 `local_only`、輸出上限不超過 512 token（觸摸、記憶提名這類內部短呼叫）、
  或內容像密碼／私鑰：只用本機。沒有本機模型時，密碼類內容不會改送雲端，回覆會直接說明沒有送出。
- 短句、陪伴、沒有寫程式／規劃／除錯等字樣：本機。
- 寫程式、規劃、除錯、很長的題目，或這輪已經在呼叫工具：Claude，還有額度就用；
  否則 Groq；再不行才本機。
- 雲端開關關掉之後，有本機就全部留在本機。

閒聊那一輪的提示會維持 `local_only`，所以本機記憶與工作情境還在。
推理那一輪改成 `cloud_allowed`，本機限定的記憶不會放進提示。
同一段對話因此分成兩條隱私紀錄：雲端推理看不到只留在本機的上一句閒聊。
這是原本的隱私分軌，不是把本機對話外送。

## 額度

`SIRO_CLAUDE_BUDGET_CALLS` 預設 10，計算滾動 5 小時內真正打到 Claude CLI 的次數，
寫在資料目錄的 `claude-budget.json`（權限 0600）。重開機不會歸零。
用完、額度檔讀不到，或 CLI 回報限流，會自動改走 Groq，再不行改本機。

畫面上會出現一句話，例如 Claude 次數用完、改用哪一家、以及大約什麼時候可以再用。
監控頁的「對話模型」會顯示 `model_actual`，並在還要等的時候顯示 `claude_available_at`。
限流訊息若沒有寫回復時間，先暫停 `SIRO_CLAUDE_RATE_LIMIT_COOLDOWN_SECONDS`（預設 900 秒）。

## 關掉

`SIRO_MODEL_ROUTER=0`，或拿掉該行。已寫入的 `claude-budget.json` 可以留著，不會被讀。

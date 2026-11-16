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
SIRO_CHAT_ROUTE=groq
```

`SIRO_CHAT_ROUTE` 決定一般閒聊走哪裡：`local`（預設，維持原本只用本機）或 `groq`
（先 Groq，失敗再本機）。其他值會在啟動時報錯。Groq 模型沿用
`openai/gpt-oss-20b`，因為啟動器的 token 預算只驗證過這個模型；換更大的模型要另外處理
`SIRO_CONTEXT_TOKEN_BUDGET_ENABLED` 與 tokenizer。

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
- 空白或含密碼／私鑰等敏感字樣：本機，提示一律 `local_only`。
- 一般閒聊（短句、陪伴、沒有寫程式／規劃／除錯等字樣）：`SIRO_CHAT_ROUTE=local` 時本機；
  `groq` 時先 Groq、再本機，提示改成 `cloud_allowed`。閒聊從不排 Claude，也不扣 Claude 額度。
  Groq 回 429 時這句改用本機並顯示一句提示；每日額度用完（或限流沒寫恢復時間）後，
  冷卻期間閒聊直接走本機，不會每句先打一次 Groq。其他錯誤（逾時、5xx）只退回本機。
- 寫程式、規劃、除錯、很長的題目，或這輪已經在呼叫工具：Claude，還有額度就用；
  否則 Groq；再不行才本機。
- 雲端開關關掉之後，有本機就全部留在本機。

閒聊走本機時，那一輪的提示維持 `local_only`，所以本機記憶與工作情境還在。
閒聊改走 Groq 前，會先用同一套記憶檢索看這句話會叫出哪些記憶：只要其中有一筆不是
`cloud_allowed`（來源事件不是全部 `cloud_allowed`），這一輪就整輪改成 `local_only`、交給本機回答，
本機記憶照常可用，Groq 完全收不到這一輪。叫不出記憶，或叫出的全部是 `cloud_allowed`，才送 Groq，
提示也只放 `cloud_allowed` 的記憶。檢查本身出錯時同樣留在本機。含密碼／私鑰等字樣的句子
不論記憶如何都是 `local_only`。`SIRO_CHAT_ROUTE=local`（預設）時這項檢查不會執行，行為與以前相同。
只看記憶表；`affect` 的偏好紀錄仍沿用原本的隱私篩選，不會讓一輪改成本機。
推理那一輪改成 `cloud_allowed`，本機限定的記憶不會放進提示。
同一段對話因此分成兩條隱私紀錄：雲端推理看不到只留在本機的上一句閒聊。
這是原本的隱私分軌，不是把本機對話外送。對話還原（`recent_session_messages`）只取同一隱私等級
已完成的回合（`run_journal.privacy` 完全相同），所以走 Groq 的那輪不會帶到 `local_only` 回合的內容；
反過來，本機那輪也只看本機回合。代價是兩條紀錄之間的接續話題，對方模型看不到。

## 閒聊走 Groq 時的記憶

先看目前記憶的隱私分布（唯讀，不會改資料庫）：

```bash
python scripts/report_memory_privacy.py --database ~/.local/share/siro/data/siro.db
```

要讓稱呼、喜好、作息這類記憶在閒聊走 Groq 時也能用，先停止 SIRO，再在 WSL 執行：

```bash
~/.venvs/sirov2/bin/python scripts/promote_memory_privacy.py --database ~/.local/share/siro/data/siro.db
```

想先看會改哪些、不改任何東西，加 `--dry-run`：只讀資料庫，不拿獨占鎖（SIRO 可以繼續開著），
不寫事件、記憶、revision 或 jsonl：

```bash
~/.venvs/sirov2/bin/python scripts/promote_memory_privacy.py --database ~/.local/share/siro/data/siro.db --everyday --dry-run
```

腳本會逐類列出記憶，每一類都要你回答 y（全部）、s（逐筆）或跳過，最後還要再確認一次才會寫入。
加 `--everyday` 時稱呼、喜好、作息三類一次全部列入，不再逐類詢問，但最後的 y/N 仍然要回答 y 才會寫入。
真正寫入時必須停止 SIRO：寫入會產生 revision 與 jsonl 紀錄，SIRO 開著時拿不到獨占鎖，腳本會直接結束。
密碼、身分、財務等敏感內容不會出現在清單裡，永遠是 `local_only`。有衍生記憶（`memory_derivations`）、
語意事實（`semantic_facts`）或來源已撤銷的記憶不處理；報告會逐筆列出這些記憶和原因。
來源事件不會被修改：每筆同意的記憶會新增一個 `cloud_allowed` 的同意事件和一份新記憶，
舊記憶以軟刪除留下版本紀錄，變更逐筆寫進資料庫旁的 `memory-privacy-promotions.jsonl`。
新寫入記憶的預設等級沒有改變。

## 額度

`SIRO_CLAUDE_BUDGET_CALLS` 預設 10，計算滾動 5 小時內真正打到 Claude CLI 的次數，
寫在資料目錄的 `claude-budget.json`（權限 0600）。重開機不會歸零。
用完、額度檔讀不到，或 CLI 回報限流，會自動改走 Groq，再不行改本機。

畫面上會出現一句話，例如 Claude 次數用完、改用哪一家、以及大約什麼時候可以再用。
監控頁的「對話模型」會顯示 `model_actual`，並在還要等的時候顯示 `claude_available_at`。
限流訊息若沒有寫回復時間，先暫停 `SIRO_CLAUDE_RATE_LIMIT_COOLDOWN_SECONDS`（預設 900 秒）。

## 關掉

`SIRO_MODEL_ROUTER=0`，或拿掉該行。已寫入的 `claude-budget.json` 可以留著，不會被讀。

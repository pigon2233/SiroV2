# SIRO 決策層驗證（第二輪，2026-11-17）

只量測：沒有改 repo、沒有 commit 或 push，也沒有重啟 SIRO，**沒有真的執行任何工具**。Ollama 用 gemma4:e4b，所有呼叫都是 `num_ctx=8192`、`think=false`、`temperature=0`。Groq 用 `qwen/qwen3.8-27b`，參數是 `reasoning_effort=none`、json_object。

**做法**：決策器的 system prompt 用 v1 = 第一輪原文（一字未改）。使用者訊息改成帶上下文：最近 2 句使用者訊息、SIRO 上一句回覆的前 80 字，加上現在這句。v2 是**看過 v1 的錯題之後才改的** prompt（`router_prompt_v2.txt`），主要多了幾條：追問原因或要求重查算 research、「卡在哪」算 status、「那 X 呢」沿用上一句的類別、打開遊戲來玩算 play 不是 execute、助理說做不到但使用者再要求時照選。所以 v2 的成績對這批題目是**偏樂觀**的。

## 1. 歷史 32 句標註

標註是在跑決策器**之前**存的（`history_labeled.json`）。分布：none 6, research 4, ambiguous 8, files_list 4, play 10。ambiguous 有 8 句，已排除，剩 24 句、各跑 1 次。h10 和 h11 是「先列檔再讀檔」的多步要求，files_list 和 files_read 都算對。

| id | 使用者 | 標註 | 備註 |
|---|---|---|---|
| h0 | 今天天氣不錯 | none | 評論天氣，非查詢 |
| h1 | 你不能查嗎 | research | 前句要查台中氣象，追問「你不能查嗎」= 再查 |
| h2 | 你剛剛查了什麼呀 | none | 問剛剛查了什麼，答案在對話裡 |
| h3 | 我以為你剛剛有自己在查什麼耶 | none | 閒聊追問 |
| h4 | 那台中地區的歷史建築不是你查的羅 | none | 閒聊追問 |
| h5 | 你連調用系統時間都是錯的嗎 你不是可以調用codex來查資料嗎 | ambiguous | 抱怨資訊錯誤，可能要求重查也可能只是抱怨 |
| h6 | 今天台北天氣怎麼樣？請幫我查一下。 | research |  |
| h7 | 今天台北天氣怎麼樣？請幫我查一下。 | research |  |
| h8 | /plan 列出工作目錄有哪些檔案，再讀其中一個文字檔並告訴我內容重點 | files_list | 多步：先列檔 |
| h9 | /plan 列出工作目錄有哪些檔案，再讀其中一個文字檔並告訴我內容重點 | files_list | 多步：先列檔 |
| h10 | /plan 列出工作目錄的檔案，再讀 note.txt 和 contact.txt，告訴我密語和備用 | files_list | 多步：先列檔（files_read 也接受） |
| h11 | /plan 列出工作目錄的檔案，再讀 note.txt 和 contact.txt，告訴我密語和備用 | files_list | 多步：先列檔（files_read 也接受） |
| h12 | 我在玩瓦羅蘭 | none | 談論自己在玩 |
| h13 | 今天天氣怎麼樣 | research | 沒給地點仍屬查天氣 |
| h14 | 剛剛做了可以讓你玩遊戲的東西但我不知道怎麼讓你操作 | none | 討論怎麼讓她操作，非命令 |
| h15 | 幫我玩UNDERTALE | play |  |
| h16 | 就打開undertale 然後開始遊玩 | play |  |
| h17 | 幫我玩UNDERTALE | play |  |
| h18 | 幫我玩UNDERTALE | play |  |
| h19 | 幫我玩UNDERTALE | play |  |
| h20 | 幫我玩UNDERTALE | play |  |
| h21 | 有阿 你有工具 幫我玩UNDERTALE | play |  |
| h22 | 幫我玩UNDERTALE | play |  |
| h23 | 幫我玩UNDERTALE | play |  |
| h24 | 來玩一局遊戲。 | ambiguous | 「來玩一局」可能是邀一起玩 |
| h25 | 說到底當然一打一的時候他遇到一些暫時的玩家。 | ambiguous | STT 亂碼 |
| h26 | 現在找到殘血就要趕快換身已經六等了,現在殘血站的線上都是非常危險的。然後可以等中路突然間這邊也再進到 | ambiguous | STT 亂碼／聊遊戲 |
| h27 | 他們打到管道可以打邊線的組合甚至玩的部門,今天可以夜裙的場合。他們前面的節奏,他在救我。而且知道什麼 | ambiguous | STT 亂碼／聊遊戲 |
| h28 | 居然是定跳跳通知,說小黃瓜在玩啊。 | ambiguous | STT 亂碼 |
| h29 | 原來是有人遊戲玩不好嗎? | ambiguous | STT 片段／聊遊戲 |
| h30 | 對對對 因為我們想玩三根的嘛所以我們是不是去玩三根的 | ambiguous | STT 亂碼 |
| h31 | 可以幫我玩殺戮艦塔嗎? | play |  |

## 2. 決策準確率

| 集合 | 本機 v1 | 本機 v2 | Groq v1 | Groq v2 |
|---|---|---|---|---|
| 歷史（24 句 × 1） | 19/24 (79%) | 22/24 (92%) | 未跑 | 未跑 |
| 新題（29 句 × 2） | 58/58 (100%) | 58/58 (100%) | 58/58 (100%) | 58/58 (100%) |
| 多輪（10 句 × 2） | 14/20 (70%) | 20/20 (100%) | 18/20 (90%) | 20/20 (100%) |

錯誤類型（漏用 = 該用沒用，多用 = 不該用卻用，錯用 = 選錯工具）：

- **本機 v1**：錯 11 次 {'missed': 8, 'wrong': 3}
  - h1「你不能查嗎」（前句：幫我查一下明天晚上台中的氣象） 預期 research → 選了 none（1 次）
  - h16「就打開undertale 然後開始遊玩」（前句：操控電腦） 預期 play → 選了 execute（1 次）
  - h20「幫我玩UNDERTALE」（前句：幫我玩UNDERTALE） 預期 play → 選了 none（1 次）
  - h21「有阿 你有工具 幫我玩UNDERTALE」（前句：幫我玩UNDERTALE） 預期 play → 選了 none（1 次）
  - h31「可以幫我玩殺戮艦塔嗎?」（前句：你好啊 好久沒有關你打開了） 預期 play → 選了 none（1 次）
  - m1「那 todo.md 呢」（前句：幫我讀 notes.txt） 預期 files_read → 選了 files_list（2 次）
  - m4「為什麼跌這麼多」（前句：台積電股價多少） 預期 research → 選了 none（2 次）
  - m6「那你覺得卡在哪」（前句：遊戲玩完了嗎） 預期 status → 選了 none（2 次）
- **Groq v1**：錯 2 次 {'missed': 2}
  - m6「那你覺得卡在哪」（前句：遊戲玩完了嗎） 預期 status → 選了 none（2 次）
- **本機 v2**：錯 2 次 {'extra': 2}
  - h2「你剛剛查了什麼呀」（前句：你幫我看一下明天台中的預估風雨） 預期 none → 選了 status（1 次）
  - h4「那台中地區的歷史建築不是你查的羅」（前句：我以為你剛剛有自己在查什麼耶） 預期 none → 選了 research（1 次）
- **Groq v2**：錯 0 次 

**解讀**：
- 新題（沒看過的 29 句）在 v1 就是本機和 Groq 都 58/58，所以單句判斷不是問題。
- v1 的錯集中在**上下文**：追問原因（「為什麼跌這麼多」）、追問遊戲狀況（「那你覺得卡在哪」）、「那 todo.md 呢」被當成列檔；歷史句裡 SIRO 上一句說「我沒有工具」之後，使用者再要求玩，本機決策器也跟著選 none；「就打開undertale 然後開始遊玩」被選成 execute。
- v2 修好了這些，但多了 2 次「多用」：h2「你剛剛查了什麼呀」選了 status（無害，只是讀狀態）、h4「那台中地區的歷史建築不是你查的羅」選了 research（這句其實是質疑，不是要求）。這兩句是 v2 的規則「追問 → 沿用」被過度套用。
- Groq qwen 在 v1 就比本機更會用上下文（多輪 18/20，本機 14/20），只錯在「卡在哪」。v2 兩者都是 20/20。

## 3. 第二步：填參數（本機 gemma4:e4b，`format` = 工具的 input_schema）

- v1：決策器選了工具的有 54 次，**通過 `_valid_arguments` 54/54**。實際呼叫 LLM 的 50 次平均 0.35 s、205 prompt tokens、16 輸出 tokens（computer.status 沒有參數，不用呼叫）。同一句兩次產生的參數完全一樣。
- v2：決策器選了工具的有 64 次，**通過 `_valid_arguments` 64/64**。實際呼叫 LLM 的 57 次平均 0.38 s、213 prompt tokens、17 輸出 tokens（computer.status 沒有參數，不用呼叫）。同一句兩次產生的參數完全一樣。

人工判斷（每種去重後的參數都看過，完整清單在 `results_v*.json` 的 `args`）：

| 句子 | 工具 | 參數 | 判斷 |
|---|---|---|---|
| 高雄現在幾度？ | claude.ask | {"task": "What is the current temperature in Kaohsiung?"} | 合理（但改用英文） |
| 幫我看看這禮拜有沒有颱風 | claude.ask | {"task": "請幫我查詢本週（2026年11月17日開始）台灣是否有颱風的預報。"} | 合理，有帶時間 |
| NBA 昨天誰贏 | claude.ask | {"task": "NBA 昨天（2026年11月16日）的比賽結果是誰贏了？"} | 合理，有換算日期 |
| 鼎泰豐週日有開嗎 | claude.ask | {"task": "鼎泰豐在週日是否營業？"} | 可接受（沒指定分店，原句也沒有） |
| 今天天氣怎麼樣（沒給地點） | claude.ask | {"task": "請告訴我今天（2026年11月17日）台灣的天氣狀況。"} | 可接受，地點只寫台灣，最好先問或用預設城市 |
| 多輪：今天台北天氣怎樣 → 那高雄呢 | claude.ask | {"task": "請幫我查詢高雄今天的天氣狀況。"} | 合理，有帶入主題 |
| 多輪：台積電股價多少 → 為什麼跌這麼多（v2） | claude.ask | {"task": "請幫我查一下台積電股價最近幾天的走勢和相關新聞，以了解為什麼股價會下跌這麼多。"} | 合理，有帶入主題 |
| 多輪：最近有什麼新聞 → 科技的就好 | claude.ask | {"task": "請提供最近科技相關的新聞。"} | 合理 |
| 多輪：工作資料夾有什麼 → 第二個檔案打開看看 | filesystem.read | {"path": "todo.md"} | 合理，從 SIRO 上一句的列表取出第二個 |
| 這篇幫我看一下講什麼 https://zh.wikipedia.org/wiki/黑洞 | browser.navigate+read | {"url": "https://zh.wikipedia.org/wiki/黑洞"} | 合理 |
| 看一下電腦開機多久了 | computer.execute | {"argv": ["uptime"]} | 合理 |
| **幫我看 CPU 用量多少** | computer.execute | {"argv": ["top"]} | **不合理**：top 是互動式程式，會一直跑到逾時；應該用 `top -bn1` 或 `cat /proc/loadavg` |
| **v1：就打開undertale 然後開始遊玩** | computer.execute | {"argv": ["./undertale"]} | **不合理**：這是決策錯誤造成的（v2 改成 computer.play，goal「打開 Undertale 並開始遊玩」） |
| **v1：那 todo.md 呢** | filesystem.list | {"path": "todo.md"} | **不合理**：決策選錯，把檔名當成目錄 |
| 幫我玩 Undertale／繼續 | computer.play | {"goal": "玩 Undertale"} / {"goal": "繼續玩 Undertale"} | 合理；「繼續」有從上一句帶入遊戲名 |

- 參數的 schema 合格率是 100%，因為 `format` 用 JSON schema 強制了結構。真正的問題在**內容**：本機一共只有 1 個參數內容有問題（`top`），另外 2 個是決策選錯造成的。claude.ask 的 task 有 5 種會變成英文（中文發問、英文 task），對 Claude 沒有影響，但如果要給使用者看就不一致。
- 參數 prompt 有給今天日期（2026-11-17），所以「昨天」「本週」都換算正確。正式實作也要把時鐘帶進去。

## 4. 延遲與 token

| 做法 | 平均延遲 s（決策） | prompt tok | 輸出 tok |
|---|---|---|---|
| 本機 gemma4:e4b v1 | 0.21 | 258 | 7 |
| Groq qwen3.8-27b v1 | 0.29 | 235 | 7 |
| 本機 gemma4:e4b v2 | 0.26 | 407 | 7 |
| Groq qwen3.8-27b v2 | 0.28 | 372 | 7 |

帶上下文後，本機決策器的 prompt 是 v1 約 260、v2 約 400 tokens（第一輪不帶上下文時是 219），延遲 0.2–0.3 s；加上填參數約 0.35 s，所以「決策 + 參數」一共約 0.6 s 之後才會開始執行工具。Groq 每次決策約 0.3 s（含網路）、約 250–350 tokens；以 1K RPD 算，大約是一天 1000 句。

## 5. 結論

- 單句意圖用很短的 prompt 就能判斷準確，本機 gemma 就做得到，不一定要靠雲端。
- 難的是多輪和「上一句說做不到」的情境，要把規則寫進決策 prompt（v2）。但 v2 是看過題目後才改的，還需要另一批沒看過的多輪題目來確認，而且 v2 已經出現 2 次因為過度套用規則而多用工具。
- 參數內容大致合理，但 computer.execute 需要一份防護清單（不能用互動式指令）。

檔案（`.scratch/tool-eval/round2/`）：`history_items.json`、`history_labeled.json`、`router_prompt_v2.txt`、`results_v1.json`、`results_v2.json`、`eval2.py`、`summarize2.py`、`run_v1.log`、`run_v2.log`。

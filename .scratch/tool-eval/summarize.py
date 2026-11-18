import json, collections, statistics as st, re, pathlib
D = pathlib.Path(__file__).resolve().parent
r = json.load(open(D / 'results.json', encoding='utf-8')); h = json.load(open(D / 'history.json', encoding='utf-8'))


def stats(rows):
    ok = [x for x in rows if 'error' not in x]
    oc = collections.Counter(x['outcome'] for x in ok)
    lat = [x['latency_s'] for x in ok]
    return dict(n=len(rows), errors=len(rows) - len(ok), ok=oc['ok'], missed=oc['missed'], wrong=oc['wrong'], extra=oc['extra'],
                bad_args=oc['bad_args'], na=oc['n/a'],
                lat_mean=round(st.mean(lat), 2) if lat else '-', lat_p50=round(st.median(lat), 2) if lat else '-', lat_max=max(lat) if lat else '-',
                pt=round(st.mean([x.get('prompt_tokens') or 0 for x in ok])) if ok else '-', ot=round(st.mean([x.get('output_tokens') or 0 for x in ok])) if ok else '-')


cur = r['current']
S = {'現行（gemma4:e4b 自帶工具）': stats(cur), 'A 本機決策層 gemma4:e4b': stats(r['router_local'])}
for m, v in r['router_groq'].items():
    S[f'B Groq {m}'] = stats(v['rows'])
cat = collections.defaultdict(collections.Counter)
for x in cur:
    cat[x['expected']][x['outcome']] += 1
announce = [x for x in cur if x['outcome'] == 'missed' and re.search(r'我會|我現在會|馬上|正在|我使用|請稍等', x['reply60'])]
need = sum(1 for x in cur if x['expected'] != 'none' and x['outcome'] != 'n/a')
missed = sum(c['missed'] for c in cat.values())
f = lambda s: s.replace('\n', ' ').replace('|', '｜')
L = []
L.append("# SIRO 工具使用實測（2026-11-17）\n")
L.append("只量測；沒有改 repo、沒有 commit，也沒有重啟 SIRO。測試時 gateway 沒有在跑，Ollama 在跑。參數跟 `ollama.py` 和 `router._ollama` 一樣：模型 gemma4:e4b、`num_ctx=8192`、`think=false`、`num_predict=512`，溫度沿用模型預設。29 句、每句跑 2 次，共 58 次。\n")
L.append("## 1. 真實狀況\n")
L.append("**設定來源**：這台機器上沒有 `.env.local`。實際設定在 WSL 的 `~/.local/bin/siro-companion-vrm`，用的是 `SIRO_OLLAMA_MODEL=gemma4:e4b`、`SIRO_OLLAMA_CONTEXT_LENGTH=8192`，runtime profile 是 candidate。Groq 金鑰在 Windows 的 `%USERPROFILE%/siro-computer/computer.env`（`SIRO_OPENAI_API_KEY`），但 start-win-backend 只從那裡匯出 `SIRO_COMPUTER_*`，所以聊天**沒有**設定 Groq 模型（`SIRO_OPENAI_MODEL` 未設）。唯一有設定的 Groq 模型是電腦操控用的 `SIRO_COMPUTER_GROQ_MODEL=qwen/qwen3.8-27b`。\n")
L.append(f"**工具清單**：取自 2026-11-16 最新聊天 run 的 system prompt 能力區塊，模型實際收到的有 {len(r['meta']['available_tools'])} 個：`" + "`, `".join(r['meta']['available_tools']) + "`。")
L.append("- `computer.play` 有註冊，但目前 `available=false`（`not_ready`，`SIRO_COMPUTER_CONTROL_ENABLED=0`），所以不會送給模型，「幫我玩」類句子標 n/a。")
L.append("- 研究工具現在叫 `claude.ask`（`codex.ask` 是舊紀錄裡的名稱）。`web.search` 預設關閉，沒有註冊。")
L.append("- 工具定義是從原始碼重建的（`DEFAULT_MODEL_TOOLS`、`BROWSER_SESSION_TOOLS`、`WORKSPACE_TOOLS`、`CLAUDE_DEFINITION`、`computer_tool.DEFINITIONS`），再依上面的清單篩選，JSON 約 4.7k 字元。")
L.append(f"- 用的 system prompt 是 `system_prompt.txt`，取自 live DB 最新聊天 run `21298c48…` 的 history[0]，共 {r['meta']['system_prompt_chars']} 字元，實際約 5.4k prompt tokens（含工具）。測試只送 system 加這一句，不帶之前的對話。\n")
L.append("**真實對話統計**（live DB `~/.local/share/siro/data/siro.db`，唯讀；資料期間 2026-10-17 到 2026-11-16）：")
L.append(f"- 聊天 run（用 persona system prompt 的）共 {h['chat_runs']} 個；`messages` 表裡使用者回合 {h['messages_table_user_turns']} 個。")
L.append(f"- 聊天 run 中有呼叫工具的：**{h['runs_with_tool']} 個（{h['runs_with_tool']/h['chat_runs']:.1%}）**，分別是：" + ", ".join(f"{k} {v}" for k, v in h['tool_counts'].items()))
L.append("- 所有 run（含自主閱讀）的工具提案：" + ", ".join(f"{k} {v}" for k, v in h['tool_proposals_by_capability'].items()) + f"；狀態：{h['tool_proposals_by_state']}")
L.append(f"- 「看起來需要工具但沒呼叫」的句子（關鍵字篩選）共 {h['missed_candidates_total']} 句，最近 30 句如下。其中有些只是在談論遊戲或追問，未必真的需要工具；舊紀錄也可能是不同模型（例如 10 月時用的 qwen3:4b）。\n")
L.append("| 日期 | 使用者 | 模型回覆前 80 字 |\n|---|---|---|")
for m in h['missed_candidates']:
    L.append(f"| {m['ts'][:10]} | {f(m['user'][:60])} | {f(m['reply'][:80])} |")
L.append("\n## 2. 結果總表\n")
L.append("| 做法 | 次數 | 對 | 漏用 | 錯用 | 多用 | 參數錯 | n/a | API 錯 | 平均延遲 s | p50 | 最大 | prompt tok | 輸出 tok |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
for k, s in S.items():
    L.append(f"| {k} | {s['n']} | {s['ok']} | {s['missed']} | {s['wrong']} | {s['extra']} | {s['bad_args']} | {s['na']} | {s['errors']} | {s['lat_mean']} | {s['lat_p50']} | {s['lat_max']} | {s['pt']} | {s['ot']} |")
L.append("\n「延遲」是單一次 HTTP 請求的時間。Ollama 是熱模型（暖機那次不計），而且非串流，所以現行做法的延遲指的是整句回覆或工具呼叫完成的時間。決策層只算決策本身，之後還要再跑一次主模型。\n")
L.append("### 現行做法：按類別\n")
L.append("| 預期 | 對 | 漏用 | 錯用 | 多用 | 參數錯 | n/a |\n|---|---|---|---|---|---|---|")
for k, c in cat.items():
    L.append(f"| {k} | {c['ok']} | {c['missed']} | {c['wrong']} | {c['extra']} | {c['bad_args']} | {c['n/a']} |")
L.append(f"\n- 在該用工具、而且工具可用的 {need} 次裡，**漏用 {missed} 次（{missed/need:.0%}）**。沒有錯用，也沒有參數錯：只要有呼叫，參數都通過 `_valid_arguments`。不該用的 24 次全部沒用（0 多用）。")
L.append(f"- 漏用時，有 {len(announce)} 次模型**嘴上說要用工具，卻沒有發出 tool_call**，例如「好的，我馬上為您讀取 `notes.txt`」「我會幫您打開 https://www.cwa.gov.tw」。另一類是**否認自己有能力**：問「剛剛玩得怎樣」時說無法得知（可用的 `computer.status` 沒用），問磁碟空間時說沒有權限（`computer.execute` 沒用）。")
L.append("- 研究類 18 次對 7 次；browser、status、files_read、execute 全部 0 次對；files_list 2 次對 1 次。同一句跑兩次結果經常不同。")
L.append("- 「幫我玩」：因為 `computer.play` 不可用，模型回答自己不能玩，這是正確的行為。歷史上 11 次 `computer.play` 都是在控制開關打開的時候。\n")
L.append("### 決策層\n")
L.append("Prompt 很短（不帶 persona），全文在 `results.json` 的 `meta.router_prompt`，要求只輸出 `{\"tool\": none|research|browser|play|status|files_list|files_read|execute}`。")
L.append("- **A 本機 gemma4:e4b**：用 Ollama `format`（JSON schema enum）、`think=false`、`temperature=0`、`num_ctx=8192`，結果 **58/58 全對**，平均 0.17 s，約 219 prompt tokens、7 輸出 tokens。")
L.append("- **B Groq**：`llama-3.1-8b-instant` 已經**不存在**（404 model_not_found）。目前帳號能用的聊天模型只有 openai/gpt-oss-120b、openai/gpt-oss-20b、qwen/qwen3.8-27b、allam-2-7b，所以改試以下兩個：")
L.append("  - `qwen/qwen3.8-27b`（SIRO 電腦操控用的 Groq 模型，`reasoning_effort=none`，json_object）：**58/58 全對**。")
L.append("  - `openai/gpt-oss-20b`（`reasoning_effort=low`）：答出來的 55 次全對，但有 3 次 Groq 回 400 json_validate_failed（磁碟空間 2 次、講個笑話 1 次），實際使用時這幾次就得退回。")
L.append("- **Groq 額度**：從 response headers 看，qwen/qwen3.8-27b 是 `x-ratelimit-limit-requests=1000`（RPD）、`limit-tokens=8000`（TPM）。官方 rate-limits 頁上 qwen/qwen3.8-27b 是 30 RPM / 1K RPD / 8K TPM / 200K TPD，但那頁沒有清楚標明是 Free 還是 Developer 方案。官方表上已經沒有 llama-3.1-8b-instant。gpt-oss-20b 的額度沒查到。每次決策約 200–350 tokens，所以 1K RPD 大約是一天 1000 句。\n")
L.append("## 3. 解讀與限制\n")
L.append("- 主要問題是**漏用**，不是錯用，也不是參數錯：gemma4:e4b 在約 5.4k token 的 persona prompt 下，常常只「說」要做而不發 tool_call，或說自己做不到。")
L.append("- 決策層在這 29 句上，本機和 Groq qwen 都是 100%，本機還更快、不出網、不用額度。")
L.append("- 限制：測試句少，而且決策 prompt 是看過這批題目才寫的，可能過度擬合。測試也沒帶對話上下文（例如「繼續」「那個呢」這種追問），沒測決策之後主模型會不會真的照著呼叫（例如只送那一個工具，或強制 tool_call）。下一步應該用歷史上的 32 句加新的、沒看過的句子再驗證一次。")
L.append("- 現行做法的延遲很低（約 0.8 s），是因為 Ollama 對同一段 system prompt 有前綴快取。決策層每回合多一次約 0.2 s 的本機呼叫。")
L.append("\n檔案：`results.json`（每次呼叫的原始紀錄）、`history.json`、`history_runs.json`、`system_prompt.txt`、`eval.py`、`summarize.py`、`run.log`、`run_groq2.log`。")
(D / 'SUMMARY.md').write_text('\n'.join(L) + '\n', encoding='utf-8')
print(json.dumps(S, ensure_ascii=False))

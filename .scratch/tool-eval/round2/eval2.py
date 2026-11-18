# Round 2: decision layer with context + argument fill. Usage: eval2.py <version> (v1|v2). Scratch only.
import json, os, re, sys, time, pathlib
import httpx

sys.path.insert(0, "/mnt/e/coding/股票策略機器學習/SiroV2/src")
from siro.services.tools.orchestrator import DEFAULT_MODEL_TOOLS, BROWSER_SESSION_TOOLS, _valid_arguments
from siro.services.tools.workspace import WORKSPACE_TOOLS
from siro.services.tools.claude import CLAUDE_DEFINITION
from siro.services.computer_use import tool as computer_tool

D = pathlib.Path(__file__).resolve().parent
VERSION = sys.argv[1]
OLLAMA = "http://127.0.0.1:11434/api/chat"
MODEL = "gemma4:e4b"
DEFS = {d.name: d for d in (*DEFAULT_MODEL_TOOLS, *BROWSER_SESSION_TOOLS, *WORKSPACE_TOOLS, CLAUDE_DEFINITION, *computer_tool.DEFINITIONS.values())}
TOOL_FOR = {"research": "claude.ask", "browser": "browser.navigate+read", "play": "computer.play", "status": "computer.status",
            "files_list": "filesystem.list", "files_read": "filesystem.read", "execute": "computer.execute"}
LABELS = ["none", "research", "browser", "play", "status", "files_list", "files_read", "execute"]
r1 = json.loads((D.parent / "results.json").read_text(encoding="utf-8"))
PROMPTS = {"v1": r1["meta"]["router_prompt"], "v2": (D / "router_prompt_v2.txt").read_text(encoding="utf-8") if (D / "router_prompt_v2.txt").exists() else None}
ROUTER_PROMPT = PROMPTS[VERSION]
SCHEMA = {"type": "object", "properties": {"tool": {"type": "string", "enum": LABELS}}, "required": ["tool"]}

# ---- cases ----
hist = json.loads((D / "history_labeled.json").read_text(encoding="utf-8"))
CASES = [{"set": "history", "id": f"h{x['id']}", "text": x["text"], "recent_user": x["recent_user"], "prev_reply": x["prev_reply"],
          "expected": x["expected"], "accept": x["accept"]} for x in hist if x["expected"] != "ambiguous"]
NEW = {"research": ["高雄現在幾度？", "幫我看看這禮拜有沒有颱風", "NBA 昨天誰贏", "比特幣現在多少錢", "查一下台北到台中的高鐵末班車", "最新的 Claude 模型是哪個", "鼎泰豐週日有開嗎"],
       "browser": ["這篇幫我看一下講什麼 https://zh.wikipedia.org/wiki/黑洞", "讀一下 https://example.com"],
       "files_list": ["資料夾裡有沒有 txt 檔"], "files_read": ["把 todo.md 內容念給我聽"],
       "status": ["你剛剛那局打到哪了", "遊戲那邊結束了嗎"], "execute": ["看一下電腦開機多久了", "幫我看 CPU 用量多少"],
       "none": ["你覺得我今天穿什麼好", "我今天被老闆罵了", "你會不會無聊", "唱首歌給我聽", "二加三等於多少", "天氣預報說明天會冷耶", "我剛查了天氣好像會下雨",
                "你昨天幫我查的那個很有用", "不用查了", "謝謝你", "我在玩瓦羅蘭", "我要去洗澡了", "你知道光速多快嗎", "不要幫我查，我只是隨便說說天氣"]}
i = 0
for exp, texts in NEW.items():
    for t in texts:
        CASES.append({"set": "new", "id": f"n{i}", "text": t, "recent_user": [], "prev_reply": "", "expected": exp, "accept": [exp]}); i += 1
MULTI = [("今天台北天氣怎樣", "我幫你問問看台北今天的天氣喔！", "那高雄呢", "research"),
         ("幫我讀 notes.txt", "notes.txt 裡寫著：明天早上十點開會、記得買牛奶。", "那 todo.md 呢", "files_read"),
         ("幫我玩 Undertale", "好，我開始玩 Undertale 囉！", "繼續", "play"),
         ("我好累", "辛苦了，要不要休息一下？", "嗯", "none"),
         ("台積電股價多少", "台積電今天收盤大約 1,050 元，跌了 3%。", "為什麼跌這麼多", "research"),
         ("講個笑話", "為什麼電腦很冷？因為它開了視窗！", "再一個", "none"),
         ("遊戲玩完了嗎", "剛剛那局玩到一半就停下來了。", "那你覺得卡在哪", "status"),
         ("工作資料夾有什麼", "資料夾裡有 notes.txt、todo.md、photo.png 三個檔案。", "第二個檔案打開看看", "files_read"),
         ("幫我查明天天氣", "好，要查哪個地區的呢？", "不用了 謝謝", "none"),
         ("最近有什麼新聞", "最近有選舉、颱風跟科技相關的新聞，你想聽哪一類？", "科技的就好", "research")]
for j, (pu, pa, t, exp) in enumerate(MULTI):
    CASES.append({"set": "multi", "id": f"m{j}", "text": t, "recent_user": [pu], "prev_reply": pa, "expected": exp, "accept": [exp]})


def context_message(c):
    recent = " | ".join(u[:80] for u in c["recent_user"][-2:]) or "(無)"
    return f"最近的使用者訊息（舊到新）：{recent}\nSIRO 上一句回覆：{(c['prev_reply'] or '(無)')[:80]}\n使用者現在說：{c['text']}"


client = httpx.Client(timeout=300)


def ollama(payload):
    t = time.perf_counter(); r = client.post(OLLAMA, json=payload); r.raise_for_status(); return r.json(), time.perf_counter() - t


def parse_label(content):
    m = re.search(r"\{.*\}", content or "", re.S)
    try:
        v = json.loads(m.group(0))["tool"] if m else None
    except Exception:  # noqa: BLE001
        v = None
    return v if v in LABELS else "invalid"


def outcome(c, got):
    if got in c["accept"]:
        return "ok"
    if got == "invalid":
        return "invalid"
    if c["expected"] == "none":
        return "extra"
    if got == "none":
        return "missed"
    return "wrong"


def route_local(c):
    data, dt = ollama({"model": MODEL, "stream": False, "think": False, "format": SCHEMA, "options": {"num_ctx": 8192, "num_predict": 30, "temperature": 0},
                       "messages": [{"role": "system", "content": ROUTER_PROMPT}, {"role": "user", "content": context_message(c)}]})
    content = data.get("message", {}).get("content")
    return parse_label(content), content, dt, data.get("prompt_eval_count"), data.get("eval_count")


def groq_key():
    for line in pathlib.Path("/mnt/c/Users/pepepig/siro-computer/computer.env").read_text().splitlines():
        m = re.match(r"\s*(?:export\s+)?SIRO_OPENAI_API_KEY=(.*)", line)
        if m:
            return m.group(1).strip().strip("'\"")


KEY = groq_key()


def route_groq(c, model="qwen/qwen3.8-27b"):
    payload = {"model": model, "temperature": 0, "max_completion_tokens": 60, "reasoning_effort": "none", "response_format": {"type": "json_object"},
               "messages": [{"role": "system", "content": ROUTER_PROMPT}, {"role": "user", "content": context_message(c)}]}
    for attempt in range(3):
        t = time.perf_counter()
        r = client.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers={"Authorization": f"Bearer {KEY}"})
        dt = time.perf_counter() - t
        if r.status_code == 429:
            time.sleep(15); continue
        break
    time.sleep(2.1)
    if r.status_code != 200:
        return "invalid", f"HTTP {r.status_code}", dt, None, None
    data = r.json(); content = data["choices"][0]["message"].get("content"); u = data.get("usage", {})
    return parse_label(content), content, dt, u.get("prompt_tokens"), u.get("completion_tokens")


ARG_PROMPT = ("你是 SIRO 的工具參數產生器。根據對話，為工具 {name} 產生呼叫參數，只輸出 JSON。\n工具說明：{desc}\n"
              "現在是 2026-11-17（台灣）。SIRO 在 WSL Linux 上執行。參數要具體、帶入對話中的主題、地點和時間。")


def fill_args(label, c):
    name = TOOL_FOR[label]; d = DEFS[name]
    if not d.input_schema.get("properties"):
        return name, {}, True, 0.0, 0, 0
    data, dt = ollama({"model": MODEL, "stream": False, "think": False, "format": d.input_schema, "options": {"num_ctx": 8192, "num_predict": 200, "temperature": 0},
                       "messages": [{"role": "system", "content": ARG_PROMPT.format(name=name, desc=d.description)}, {"role": "user", "content": context_message(c)}]})
    raw = data.get("message", {}).get("content") or ""
    try:
        args = json.loads(raw)
    except Exception:  # noqa: BLE001
        args = raw
    ok = isinstance(args, dict) and _valid_arguments(args, d.input_schema)
    return name, args, ok, round(dt, 2), data.get("prompt_eval_count"), data.get("eval_count")


out = {"version": VERSION, "router_prompt": ROUTER_PROMPT, "arg_prompt": ARG_PROMPT, "local": [], "groq": []}
route_local({"text": "嗨", "recent_user": [], "prev_reply": ""})  # warm-up
for c in CASES:
    reps = 1 if c["set"] == "history" else 2
    for rep in range(reps):
        got, raw, dt, pt, ot = route_local(c)
        row = {**c, "rep": rep, "got": got, "outcome": outcome(c, got), "raw": (raw or "")[:60], "latency_s": round(dt, 2), "prompt_tokens": pt, "output_tokens": ot}
        if got in TOOL_FOR:
            name, args, ok, adt, apt, aot = fill_args(got, c)
            row["args"] = {"tool": name, "arguments": args, "schema_ok": ok, "latency_s": adt, "prompt_tokens": apt, "output_tokens": aot}
        out["local"].append(row); print(json.dumps(row, ensure_ascii=False), flush=True)
    (D / f"results_{VERSION}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
for c in CASES:
    if c["set"] == "history":
        continue
    for rep in range(2):
        got, raw, dt, pt, ot = route_groq(c)
        row = {**c, "rep": rep, "got": got, "outcome": outcome(c, got), "raw": (raw or "")[:60], "latency_s": round(dt, 2), "prompt_tokens": pt, "output_tokens": ot}
        out["groq"].append(row); print("GROQ", json.dumps(row, ensure_ascii=False), flush=True)
(D / f"results_{VERSION}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("DONE", VERSION)

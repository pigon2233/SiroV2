# Tool-use eval for SIRO (scratch, not part of the repo). Run inside WSL with the sirov2 venv.
import json, os, re, sys, time, pathlib
import httpx

sys.path.insert(0, "/mnt/e/coding/股票策略機器學習/SiroV2/src")
from siro.services.tools.orchestrator import DEFAULT_MODEL_TOOLS, BROWSER_SESSION_TOOLS, _valid_arguments
from siro.services.tools.workspace import WORKSPACE_TOOLS
from siro.services.tools.claude import CLAUDE_DEFINITION
from siro.services.computer_use import tool as computer_tool

OUT = pathlib.Path(__file__).resolve().parent
OLLAMA = "http://127.0.0.1:11434/api/chat"
MODEL = os.environ.get("SIRO_OLLAMA_MODEL", "gemma4:e4b")
REPEATS = 2
STAGES = sys.argv[1:] or ["current", "local", "groq"]

system_prompt = (OUT / "system_prompt.txt").read_text(encoding="utf-8")
cap = json.loads(system_prompt.split("[SIRO_TOOL_CAPABILITIES_V1]\n")[1].split("\n[/SIRO_TOOL_CAPABILITIES_V1]")[0])
available = [c["name"] for c in cap["capabilities"] if c["available"] and c["model_visible"]]
all_defs = {d.name: d for d in (*DEFAULT_MODEL_TOOLS, *BROWSER_SESSION_TOOLS, *WORKSPACE_TOOLS, CLAUDE_DEFINITION, *computer_tool.DEFINITIONS.values())}
# Order as in the real catalog capture.
tools = [all_defs[n] for n in available if n in all_defs]
missing_defs = [n for n in available if n not in all_defs]
ollama_tools = [{"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.input_schema}} for t in tools]

RESEARCH = {"claude.ask", "codex.ask", "web.search"}
CASES = [
    *[(s, "research") for s in ["今天台北天氣怎樣？", "明天會下雨嗎", "最近有什麼科技新聞", "台積電今天股價多少",
       "幫我查一下 iPhone 18 什麼時候發售", "這週末高雄有什麼活動", "美元兌台幣現在多少",
       "幫我找 Python 3.14 有什麼新功能", "Undertale 最近有出續作嗎"]],
    ("打開這個網址看看 https://www.cwa.gov.tw", "browser"),
    ("幫我玩 Undertale", "play"), ("你自己去玩一下遊戲吧", "play"),
    ("剛剛玩得怎樣？", "status"), ("遊戲進度如何", "status"),
    ("看一下工作資料夾裡有什麼檔案", "files_list"), ("幫我讀 notes.txt", "files_read"),
    ("幫我看一下電腦磁碟剩多少空間", "execute"),
    *[(s, "none") for s in ["早安", "你好可愛", "我今天好累", "你喜歡什麼顏色", "講個笑話", "什麼是黑洞",
       "我剛剛玩 Undertale 好難喔", "我不想玩遊戲", "天氣好熱喔", "晚安", "你在幹嘛", "幫我想一下晚餐吃什麼"]],
]
LABEL_TOOLS = {"research": RESEARCH, "browser": {"browser.navigate+read"}, "play": {"computer.play"},
               "status": {"computer.status"}, "files_list": {"filesystem.list"}, "files_read": {"filesystem.read"},
               "execute": {"computer.execute"}, "none": set()}
LABELS = list(LABEL_TOOLS)


def label_of(tool_name):
    for k, v in LABEL_TOOLS.items():
        if tool_name in v:
            return k
    return "other:" + tool_name


def classify(expected, got_label, args_ok=True):
    """expected/got are labels. Returns outcome."""
    if expected != "none" and not (LABEL_TOOLS[expected] & set(available)) and expected != "research_na":
        pass
    if got_label == expected:
        return "ok" if args_ok else "bad_args"
    if expected == "none":
        return "extra"
    if got_label == "none":
        return "missed"
    return "wrong"


client = httpx.Client(timeout=300)
results = json.loads((OUT / "results.json").read_text(encoding="utf-8")) if (OUT / "results.json").exists() else {}


def ollama_chat(payload):
    t = time.perf_counter()
    r = client.post(OLLAMA, json=payload)
    r.raise_for_status()
    return r.json(), time.perf_counter() - t


def current_path():
    rows = []
    # warm-up (excluded)
    ollama_chat({"model": MODEL, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": "嗨"}],
                 "stream": False, "think": False, "tools": ollama_tools, "options": {"num_predict": 512, "num_ctx": 8192}})
    for text, expected in CASES:
        na = expected != "none" and not (LABEL_TOOLS[expected] & set(available))
        for rep in range(REPEATS):
            payload = {"model": MODEL, "stream": False, "think": False,
                       "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": text}],
                       "tools": ollama_tools, "options": {"num_predict": 512, "num_ctx": 8192}}
            try:
                data, dt = ollama_chat(payload)
            except Exception as e:  # noqa: BLE001
                rows.append({"text": text, "expected": expected, "rep": rep, "error": repr(e)[:200]})
                continue
            msg = data.get("message", {})
            calls = [{"name": c["function"]["name"], "arguments": c["function"].get("arguments")} for c in msg.get("tool_calls") or []]
            for c in calls:
                d = all_defs.get(c["name"])
                c["schema_ok"] = bool(d) and c["name"] in available and isinstance(c["arguments"], dict) and _valid_arguments(c["arguments"], d.input_schema)
            got = label_of(calls[0]["name"]) if calls else "none"
            outcome = "n/a" if na else classify(expected, got, all(c["schema_ok"] for c in calls))
            row = {"text": text, "expected": expected, "rep": rep, "tool_calls": calls, "got": got, "outcome": outcome,
                   "reply60": (msg.get("content") or "")[:60], "latency_s": round(dt, 2),
                   "prompt_tokens": data.get("prompt_eval_count"), "output_tokens": data.get("eval_count"),
                   "done_reason": data.get("done_reason")}
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
    return rows


ROUTER_PROMPT = (
    "你是聊天助理的工具路由器。讀使用者這一句話，選出助理這回合該用的工具，只輸出 JSON {\"tool\": \"...\"}。\n"
    "none：閒聊、情緒、打招呼、常識或知識問答、建議，不需要即時資料或動作。\n"
    "research：需要上網查即時或最新資訊（天氣、新聞、股價、匯率、活動、新產品、版本更新）。\n"
    "browser：使用者給了網址，要打開閱讀。\n"
    "play：要求助理自己去玩或操作電腦上的遊戲。\n"
    "status：問助理目前或剛才玩遊戲／電腦任務的進度或結果。\n"
    "files_list：查看工作資料夾裡有哪些檔案。\n"
    "files_read：讀取某個指定檔案的內容。\n"
    "execute：在電腦上執行指令查系統資訊（磁碟、記憶體、程序等）。\n"
    "只是談論遊戲、否定句、抱怨天氣，都是 none。"
)
SCHEMA = {"type": "object", "properties": {"tool": {"type": "string", "enum": LABELS}}, "required": ["tool"]}


def parse_label(content):
    m = re.search(r"\{.*\}", content or "", re.S)
    try:
        v = json.loads(m.group(0))["tool"] if m else None
    except Exception:  # noqa: BLE001
        v = None
    return v if v in LABELS else "invalid"


def local_router():
    rows = []
    base = {"model": MODEL, "stream": False, "think": False, "format": SCHEMA, "options": {"num_ctx": 8192, "num_predict": 30, "temperature": 0}}
    ollama_chat({**base, "messages": [{"role": "system", "content": ROUTER_PROMPT}, {"role": "user", "content": "嗨"}]})
    for text, expected in CASES:
        for rep in range(REPEATS):
            data, dt = ollama_chat({**base, "messages": [{"role": "system", "content": ROUTER_PROMPT}, {"role": "user", "content": text}]})
            got = parse_label(data.get("message", {}).get("content"))
            row = {"text": text, "expected": expected, "rep": rep, "got": got, "outcome": classify(expected, got),
                   "raw": (data.get("message", {}).get("content") or "")[:80], "latency_s": round(dt, 2),
                   "prompt_tokens": data.get("prompt_eval_count"), "output_tokens": data.get("eval_count")}
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
    return rows


def groq_key():
    for line in pathlib.Path("/mnt/c/Users/pepepig/siro-computer/computer.env").read_text().splitlines():
        m = re.match(r"\s*(?:export\s+)?SIRO_OPENAI_API_KEY=(.*)", line)
        if m:
            return m.group(1).strip().strip("'\"")
    return None


def groq_router(model, reasoning=None):
    key = groq_key()
    rows, headers_seen = [], {}
    for text, expected in CASES:
        for rep in range(REPEATS):
            payload = {"model": model, "temperature": 0, "max_completion_tokens": 60 if not reasoning else 400,
                       "response_format": {"type": "json_object"},
                       "messages": [{"role": "system", "content": ROUTER_PROMPT}, {"role": "user", "content": text}]}
            if reasoning:
                payload["reasoning_effort"] = reasoning
            t = time.perf_counter()
            r = client.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers={"Authorization": f"Bearer {key}"})
            dt = time.perf_counter() - t
            headers_seen = {k: v for k, v in r.headers.items() if k.startswith("x-ratelimit")}
            if r.status_code != 200:
                row = {"text": text, "expected": expected, "rep": rep, "error": f"{r.status_code} {r.text[:200]}", "latency_s": round(dt, 2)}
                rows.append(row); print(json.dumps(row, ensure_ascii=False), flush=True)
                if r.status_code == 429:
                    time.sleep(10)
                continue
            data = r.json()
            content = data["choices"][0]["message"].get("content")
            got = parse_label(content)
            u = data.get("usage", {})
            row = {"text": text, "expected": expected, "rep": rep, "got": got, "outcome": classify(expected, got),
                   "raw": (content or "")[:80], "latency_s": round(dt, 2), "prompt_tokens": u.get("prompt_tokens"),
                   "output_tokens": u.get("completion_tokens"), "groq_total_time": u.get("total_time")}
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
            time.sleep(2.1)  # stay under 30 RPM
    return rows, headers_seen


results["meta"] = {"model": MODEL, "repeats": REPEATS, "available_tools": available, "tool_defs_sent": [t.name for t in tools],
                   "missing_defs": missing_defs, "system_prompt_chars": len(system_prompt), "router_prompt": ROUTER_PROMPT}
if "current" in STAGES:
    results["current"] = current_path()
    (OUT / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
if "local" in STAGES:
    results["router_local"] = local_router()
    (OUT / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
if "groq" in STAGES:
    pairs = [tuple(p.split("|")) for p in os.environ["GROQ_MODELS"].split(",")] if os.environ.get("GROQ_MODELS") else [("llama-3.1-8b-instant", None), ("qwen/qwen3.8-27b", "none")]
    for model, reasoning in [(m, r or None) for m, r in pairs]:
        rows, hdr = groq_router(model, reasoning)
        results.setdefault("router_groq", {})[model] = {"rows": rows, "ratelimit_headers": hdr}
        (OUT / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
print("DONE", STAGES)

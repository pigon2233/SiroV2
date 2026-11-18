# Round 3: run the committed module (worktree src) on unseen labeled cases. No tool is executed.
import asyncio, json, os, pathlib, re, sys, time

sys.path.insert(0, "/mnt/e/coding/Worktrees/tool-decision/src")
from siro.services.agent import tool_decision as td
from siro.services.tools.orchestrator import DEFAULT_MODEL_TOOLS, BROWSER_SESSION_TOOLS
from siro.services.tools.workspace import WORKSPACE_TOOLS
from siro.services.tools.claude import CLAUDE_DEFINITION
from siro.services.computer_use import tool as computer_tool

D = pathlib.Path(__file__).resolve().parent
defs = {d.name: d for d in (*DEFAULT_MODEL_TOOLS, *BROWSER_SESSION_TOOLS, *WORKSPACE_TOOLS, CLAUDE_DEFINITION, *computer_tool.DEFINITIONS.values())}
NAMES = ["browser.navigate+read", "computer.execute", "browser.read", "browser.fill", "browser.click", "browser.close",
         "claude.ask", "computer.play", "computer.status", "filesystem.read", "filesystem.list"]
TOOLS = tuple(defs[n] for n in NAMES)
env = {"SIRO_OLLAMA_MODEL": "gemma4:e4b", "SIRO_OLLAMA_CONTEXT_LENGTH": "8192", "SIRO_TOOL_DECISION": "1"}
for line in pathlib.Path("/mnt/c/Users/pepepig/siro-computer/computer.env").read_text().splitlines():
    m = re.match(r"\s*(?:export\s+)?(SIRO_OPENAI_API_KEY|SIRO_OPENAI_BASE_URL|SIRO_COMPUTER_GROQ_MODEL)=(.*)", line)
    if m:
        env[m.group(1)] = m.group(2).strip().strip("'\"")
cases = json.loads((D / "cases_labeled.json").read_text(encoding="utf-8"))


async def run(mode):
    groq = td.groq_chat(env) if mode == "local+groq" else None
    calls = {"n": 0}
    if groq:
        inner = groq
        async def counted(s, u):
            calls["n"] += 1
            await asyncio.sleep(2.1)
            return await inner(s, u)
        groq = counted
    decider = td.ToolDecider(chat=td.ollama_json_chat("gemma4:e4b", env), groq=groq, log_path=D / f"decisions_{mode}.jsonl")
    await decider.decide("嗨", TOOLS)  # warm-up
    rows = []
    for c in cases:
        for rep in range(2):
            before = calls["n"]
            t = time.perf_counter()
            d = await decider.decide(c["text"], TOOLS, recent_user=c["recent_user"], prev_reply=c["prev_reply"],
                                     last_turn_used_tool=c["last_turn_used_tool"], cloud_allowed=(mode == "local+groq"))
            got = d.category
            exp = c["expected"]
            if got == exp and (got == "none" or d.call is not None):
                outcome = "ok"
            elif got == exp:
                outcome = "bad_args"
            elif exp == "none":
                outcome = "extra"
            elif got in ("none", "error", "invalid"):
                outcome = "missed"
            else:
                outcome = "wrong"
            row = {**c, "rep": rep, "got": got, "source": d.source, "groq_called": calls["n"] > before,
                   "call": {"name": d.call.name, "arguments": d.call.arguments} if d.call else None,
                   "args_ok": d.args_ok, "outcome": outcome, "latency_s": round(time.perf_counter() - t, 2)}
            rows.append(row)
            print(mode, json.dumps(row, ensure_ascii=False), flush=True)
    return rows


async def main():
    out = {}
    for mode in ("local", "local+groq"):
        out[mode] = await run(mode)
        (D / "results3.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("DONE")


asyncio.run(main())

import asyncio, json, sys, httpx
sys.path.insert(0, "/mnt/e/coding/Worktrees/tool-decision/src")
from siro.services.agent import tool_decision as td
exec(open("/mnt/e/coding/股票策略機器學習/SiroV2/.scratch/tool-eval/round3/eval3.py").read().split("cases = ")[0].split("D = pathlib")[0])
import pathlib
D=pathlib.Path("/mnt/e/coding/股票策略機器學習/SiroV2/.scratch/tool-eval/round3")
exec(open(D/"eval3.py").read().split("cases = ")[0].split("import asyncio, json, os, pathlib, re, sys, time")[1].replace('pathlib.Path(__file__).resolve().parent','D'))
c=[x for x in json.load(open(D/"cases_labeled.json",encoding="utf-8")) if x["id"]=="m0"][0]
menu=td.categories(TOOLS)
system=td.router_prompt(menu); user=td.context_message(c["text"],c["recent_user"],c["prev_reply"])
schema={"type":"object","properties":{"tool":{"type":"string","enum":list(menu)}},"required":["tool"]}
r=httpx.post("http://127.0.0.1:11434/api/chat",json={"model":"gemma4:e4b","stream":False,"think":False,"format":schema,"options":{"temperature":0,"num_predict":30,"num_ctx":8192},"messages":[{"role":"system","content":system},{"role":"user","content":user}]},timeout=60).json()
print(json.dumps({k:r.get(k) for k in ("done","done_reason","eval_count")},ensure_ascii=False), repr(r["message"]["content"]))

"""Configured-provider synthetic evaluation of actual repaired composition; no effects."""
from __future__ import annotations
import asyncio
import hashlib
import json
import probe_dialogue_ablation as probe

async def main():
    files=("src/siro/services/presentation/integrated.py","src/siro/services/agent/runs.py","src/siro/core/memory.py","src/siro/adapters/models/openai_compatible.py")
    hashes={f:hashlib.sha256((probe.ROOT/f).read_bytes()).hexdigest() for f in files}
    provider=probe.model()
    results=[]
    for label,question,failure,dispatched in probe.CASES:
        request,_=await probe.fixture(label,question,failure,dispatched)
        result=await probe.evaluate(provider,request,label,None,"A")
        result["arm"]="actual_repaired_composition"
        result["own_status_in_prompt"]="Own runtime status:" in request.prompt
        results.append(result)
        print(json.dumps({"case":label,"error_class":result.get("error_class"),"http_status":result.get("http_status"),"terminal_chunk_kinds":result.get("terminal_chunk_kinds")}),flush=True)
    report={"synthetic_only":True,"actual_configured_provider":True,"tools_executed":0,"max_output_tokens":512,"samples_per_case":1,"source_sha256":hashes,"sources_unchanged":all(hashlib.sha256((probe.ROOT/f).read_bytes()).hexdigest()==h for f,h in hashes.items()),"limitations":["not statistical quality certification","captcha uses synthetic native observation; not browser acceptance","no private conversations/live service changes"],"results":results}
    (probe.OUT/"dialogue-after.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")

if __name__=="__main__":
    asyncio.run(main())

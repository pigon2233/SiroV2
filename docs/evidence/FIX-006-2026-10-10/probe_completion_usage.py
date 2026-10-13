"""Evidence-only bounded SSE metrics; never saves hidden reasoning or executes tools."""
from __future__ import annotations
import asyncio
import hashlib
import json
import os
import time
from dataclasses import replace
from uuid import uuid4
import probe_dialogue_ablation as probe
from siro.adapters.models.http import HttpxStreamingTransport
from siro.ports.models import CancellationToken

async def sample(provider, request, label, arm, iteration):
    request=replace(request,generation_id=str(uuid4()))
    payload=provider.request_payload(request)
    assert payload["model"]=="openai/gpt-oss-20b" and payload["max_tokens"]==512
    if arm=="low": payload["reasoning_effort"]="low"
    token=CancellationToken(); transport=HttpxStreamingTransport(); started=time.monotonic()
    result={"case":label,"arm":arm,"iteration":iteration,"max_tokens":512,"tools_executed":0,"finish_reason":None,"usage":{},"visible_characters":0,"tool_proposal_fragments":False,"done_marker":False}
    visible=[]; events=0; iterator=None
    try:
        iterator=transport.stream_lines(os.environ["SIRO_OPENAI_BASE_URL"].rstrip("/")+"/v1/chat/completions",payload,{"Authorization":"Bearer "+os.environ["SIRO_OPENAI_API_KEY"]},30,token)
        async with asyncio.timeout(35):
            async for line in iterator:
                events+=1
                if events>2048 or len(line.encode())>524288: raise ValueError("diagnostic_stream_bound")
                if not line.startswith("data:"): continue
                data=line.removeprefix("data:").strip()
                if data=="[DONE]": result["done_marker"]=True; break
                event=json.loads(data)
                if not isinstance(event,dict): raise ValueError("diagnostic_event_shape")
                x=event.get("x_groq")
                candidates=[event.get("usage"),x.get("usage") if isinstance(x,dict) else None]
                for usage in candidates:
                    if not isinstance(usage,dict): continue
                    for key in ("prompt_tokens","completion_tokens","total_tokens"):
                        value=usage.get(key)
                        if type(value) is int and value>=0: result["usage"][key]=value
                    details=usage.get("completion_tokens_details")
                    count=details.get("reasoning_tokens") if isinstance(details,dict) else None
                    if type(count) is int and count>=0: result["usage"]["reasoning_tokens"]=count
                for choice in event.get("choices",[]):
                    if not isinstance(choice,dict): continue
                    reason=choice.get("finish_reason")
                    if reason in ("stop","length","tool_calls","content_filter"): result["finish_reason"]=reason
                    delta=choice.get("delta")
                    if not isinstance(delta,dict): continue
                    # Do not inspect, retain, print or derive content from the reasoning field.
                    content=delta.get("content")
                    if isinstance(content,str):
                        result["visible_characters"]+=len(content)
                        if result["visible_characters"]>32768: raise ValueError("visible_output_bound")
                        visible.append(content)
                    if delta.get("tool_calls"): result["tool_proposal_fragments"]=True
        if result["done_marker"] and result["finish_reason"]=="stop": result["completed_visible_text"]="".join(visible)
        if "reasoning_tokens" not in result["usage"]: result["reasoning_tokens_status"]="UNKNOWN"
    except Exception as error:
        response=getattr(error,"response",None); status=getattr(response,"status_code",None)
        result["error_class"]=type(error).__name__; result["http_status"]=status if type(status) is int else None
    finally:
        token.cancel()
        if iterator is not None: await iterator.aclose()
    result["elapsed_seconds"]=round(time.monotonic()-started,3)
    result["prompt_sha256"]=hashlib.sha256(request.messages[0].content.encode()).hexdigest()
    return result

async def main():
    provider=probe.model(); results=[]
    names=("src/siro/services/presentation/integrated.py","src/siro/services/agent/runs.py","src/siro/core/memory.py","src/siro/adapters/models/openai_compatible.py")
    hashes={n:hashlib.sha256((probe.ROOT/n).read_bytes()).hexdigest() for n in names}
    for label,question,failure,dispatched in probe.CASES:
        if label not in {"voice_correction","own_failure","unknown_effect"}: continue
        request,_=await probe.fixture(label,question,failure,dispatched)
        for iteration in range(2 if label=="voice_correction" else 1):
            for arm in ("omitted_default","low"):
                result=await sample(provider,request,label,arm,iteration)
                results.append(result)
                print(json.dumps({k:result.get(k) for k in ("case","arm","iteration","finish_reason","usage","visible_characters","error_class","http_status","elapsed_seconds")}),flush=True)
    report={"synthetic_only":True,"actual_configured_provider":True,"production_changes":False,"budget_or_model_change":False,"only_wire_difference":"reasoning_effort=low vs omitted default","tools_executed":0,"hidden_reasoning_retained":False,"max_requests":8,"max_parallel":1,"max_events_per_request":2048,"max_wall_seconds_per_request":35,"no_auto_retry":True,"source_sha256":hashes,"sources_unchanged":all(hashlib.sha256((probe.ROOT/n).read_bytes()).hexdigest()==h for n,h in hashes.items()),"usage_note":"latest cumulative numeric totals, not sum; missing reasoning count UNKNOWN","sources":["https://console.groq.com/docs/api-reference","https://console.groq.com/docs/reasoning","https://github.com/groq/groq-python/blob/main/src/groq/types/completion_usage.py","https://github.com/groq/groq-python/blob/main/src/groq/types/chat/chat_completion_chunk.py"],"limitations":["small synthetic samples, no statistical or overall quality claim","raw metrics consumer is evidence-only; production completion fence unchanged","no private chat/live service/restart/deployment"],"results":results}
    (probe.OUT/"completion-usage-ablation.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")

if __name__=="__main__": asyncio.run(main())

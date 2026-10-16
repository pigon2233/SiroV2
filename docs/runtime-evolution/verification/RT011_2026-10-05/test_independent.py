"""Independent composition check: native rejection precedes every retry backend."""
from copy import deepcopy
from pathlib import Path
import pytest
from siro.adapters.models.failover import FailoverModel
from siro.adapters.models.openai_compatible import OpenAICompatibleAdapter
from siro.ports.models import CancellationToken, ModelChunk, ModelMessage, ModelRequest, Privacy, ToolCall
from siro.services.agent.context import ContextBudgetExceeded, ContextBudgetModel
from siro.services.agent.native_context import GPTOSSBudget

@pytest.mark.asyncio
async def test_native_rejection_fences_both_attempts_preserves_pending_pair():
    calls = []
    class Model:
        name = "independent"
        async def stream(self, request, cancellation):
            calls.append(request)
            raise ConnectionError("must never enter provider")
            yield ModelChunk("finished")
    serializer = OpenAICompatibleAdapter(base_url="https://api.groq.com/openai",
        api_key="synthetic", model="openai/gpt-oss-20b")
    request = ModelRequest("immutable goal", "g", Privacy.CLOUD_ALLOWED, messages=(
        ModelMessage("system", "authorization [source:policy]"),
        ModelMessage("user", "immutable goal"),
        ModelMessage("assistant", "", (ToolCall("pending", "inspect", {"path":"中文"}),)),
        ModelMessage("tool", "retained observation", tool_call_id="pending")))
    before = deepcopy(request)
    assets = Path(__file__).resolve().parents[4] / ".siro-data/tokenizers/gpt-oss-20b"
    guard = GPTOSSBudget(assets, serializer.request_payload, context_window=1)
    wrapper = ContextBudgetModel(FailoverModel((Model(), Model()), backoff_seconds=0),
        max_bytes=None, token_budget=guard)
    with pytest.raises(ContextBudgetExceeded):
        _ = [chunk async for chunk in wrapper.stream(request, CancellationToken())]
    assert calls == [] and request == before
    assert request.messages[-1].tool_call_id == "pending"

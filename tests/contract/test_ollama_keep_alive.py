"""Optional model residency: unset keeps Ollama's default unload behaviour."""

from __future__ import annotations

import pytest

from siro.adapters.models.ollama import OllamaAdapter
from siro.ports.models import CancellationToken, ModelRequest
from tests.contract.test_ollama_reasoning_options import Transport


async def _payload(adapter: OllamaAdapter) -> dict[str, object]:
    transport = adapter._transport
    assert isinstance(transport, Transport)
    _ = [c async for c in adapter.stream(ModelRequest("synthetic", "g"), CancellationToken())]
    return transport.payload


@pytest.mark.asyncio
async def test_keep_alive_is_absent_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SIRO_OLLAMA_KEEP_ALIVE", raising=False)
    adapter = OllamaAdapter(model="synthetic", transport=Transport())
    assert "keep_alive" not in await _payload(adapter)


@pytest.mark.asyncio
async def test_keep_alive_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIRO_OLLAMA_KEEP_ALIVE", "30m")
    adapter = OllamaAdapter(model="synthetic", transport=Transport())
    assert (await _payload(adapter))["keep_alive"] == "30m"


@pytest.mark.parametrize("value", ["forever", "5 minutes", "m30", "1.5h"])
def test_keep_alive_rejects_malformed_duration(value: str) -> None:
    with pytest.raises(ValueError):
        OllamaAdapter(model="synthetic", keep_alive=value)

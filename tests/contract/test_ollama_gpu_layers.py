"""Optional GPU layer count: unset leaves placement to Ollama."""

from __future__ import annotations

from typing import cast

import pytest

from siro.adapters.models.ollama import OllamaAdapter
from tests.contract.test_ollama_keep_alive import _payload
from tests.contract.test_ollama_reasoning_options import Transport


async def _options(adapter: OllamaAdapter) -> dict[str, object]:
    return cast(dict[str, object], (await _payload(adapter))["options"])


@pytest.mark.asyncio
async def test_gpu_layers_absent_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SIRO_OLLAMA_GPU_LAYERS", raising=False)
    adapter = OllamaAdapter(model="synthetic", transport=Transport())
    assert "num_gpu" not in await _options(adapter)


@pytest.mark.asyncio
@pytest.mark.parametrize("context_length", [None, 8192])
async def test_gpu_layers_from_environment(
    monkeypatch: pytest.MonkeyPatch, context_length: int | None
) -> None:
    monkeypatch.setenv("SIRO_OLLAMA_GPU_LAYERS", "42")
    adapter = OllamaAdapter(model="synthetic", transport=Transport(), context_length=context_length)
    assert (await _options(adapter))["num_gpu"] == 42


@pytest.mark.parametrize("value", ["all", "-1", "4.5", "999"])
def test_gpu_layers_rejects_malformed_value(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("SIRO_OLLAMA_GPU_LAYERS", value)
    with pytest.raises(ValueError):
        OllamaAdapter(model="synthetic")

"""Load options shared by every direct Ollama caller.

Ollama reloads a model whenever `num_ctx` or `num_gpu` differs from the loaded
instance, and the latest `keep_alive` wins. Callers that target the chat model
(`SIRO_OLLAMA_MODEL`) therefore reuse the chat settings instead of their own.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

DEFAULT_KEEP_ALIVE = "30m"


def keep_alive(env: Mapping[str, str] | None = None, *, default: str = DEFAULT_KEEP_ALIVE) -> str:
    values = os.environ if env is None else env
    return values.get("SIRO_OLLAMA_KEEP_ALIVE") or default


def _is_chat_model(values: Mapping[str, str], model: str) -> bool:
    return bool(model) and model == values.get("SIRO_OLLAMA_MODEL")


def gpu_layers(
    env: Mapping[str, str] | None, model: str, *, override: str | None = None
) -> int | None:
    """Caller override first, else the chat model's `SIRO_OLLAMA_GPU_LAYERS`.

    Raises ValueError on a malformed value. None lets Ollama decide.
    """
    values = os.environ if env is None else env
    raw = values.get(override) if override else None
    if raw is None and _is_chat_model(values, model):
        raw = values.get("SIRO_OLLAMA_GPU_LAYERS", "").strip() or None
    if raw is None:
        return None
    if not raw.isdigit() or int(raw) > 256:
        raise ValueError("Ollama GPU layers must be an integer between 0 and 256")
    return int(raw)


def context_length(env: Mapping[str, str] | None, model: str, needed: int) -> int:
    """The chat model's context when it covers `needed`, so the load is reused."""
    values = os.environ if env is None else env
    raw = values.get("SIRO_OLLAMA_CONTEXT_LENGTH", "").strip()
    if _is_chat_model(values, model) and raw.isdigit() and int(raw) >= needed:
        return int(raw)
    return needed

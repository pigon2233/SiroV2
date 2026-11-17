"""The system prompt keeps per-turn content after a stable, cacheable prefix."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from siro.adapters.models import ollama_options
from siro.core.identity import IdentityState, ImmutableCore
from siro.core.memory import LIVE_CONTEXT_MARKER, assemble_prompt


def _state() -> IdentityState:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return IdentityState(
        identity_id="siro",
        core=ImmutableCore(
            name="SIRO",
            baseline_identity="persistent companion",
            core_values=("honesty",),
            creator_relationship="owner",
        ),
        created_at=now,
        updated_at=now,
    )


def test_prefix_is_identical_across_turns(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SIRO_PROMPT_LAYOUT", raising=False)
    first = assemble_prompt(
        _state(), "", (), native_dialogue=True, now=datetime(2026, 1, 1, 8, 0, tzinfo=UTC)
    )
    later = assemble_prompt(
        _state(),
        "",
        (),
        verified_context=("owner likes tea",),
        native_dialogue=True,
        now=datetime(2026, 1, 2, 9, 30, tzinfo=UTC),
    )
    stable, marker, live = first.partition(LIVE_CONTEXT_MARKER)
    assert marker and later.startswith(stable + marker)
    assert "Current local date" not in stable and "Verified memories" not in stable
    assert "Current local date" in live and "Verified memories" in live
    assert "Affect policy" in stable and "Conversation policy" in stable


def test_legacy_layout_is_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIRO_PROMPT_LAYOUT", "legacy")
    prompt = assemble_prompt(_state(), "hi", ())
    assert LIVE_CONTEXT_MARKER not in prompt
    assert prompt.index("Current local date") < prompt.index("Conversation policy")
    assert prompt.index("Verified memories") < prompt.index("Affect policy")


def test_shared_ollama_options_follow_the_chat_model() -> None:
    env = {
        "SIRO_OLLAMA_MODEL": "chat",
        "SIRO_OLLAMA_CONTEXT_LENGTH": "8192",
        "SIRO_OLLAMA_GPU_LAYERS": "42",
        "SIRO_OLLAMA_KEEP_ALIVE": "45m",
    }
    assert ollama_options.keep_alive(env) == "45m"
    assert ollama_options.keep_alive({}) == ollama_options.DEFAULT_KEEP_ALIVE
    assert ollama_options.context_length(env, "chat", 2048) == 8192
    assert ollama_options.context_length(env, "chat", 16384) == 16384
    assert ollama_options.context_length(env, "other", 2048) == 2048
    assert ollama_options.gpu_layers(env, "chat") == 42
    assert ollama_options.gpu_layers(env, "other") is None
    assert ollama_options.gpu_layers({**env, "X": "24"}, "other", override="X") == 24
    with pytest.raises(ValueError):
        ollama_options.gpu_layers({**env, "X": "many"}, "chat", override="X")

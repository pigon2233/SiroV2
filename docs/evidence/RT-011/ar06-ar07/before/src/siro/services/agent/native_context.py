"""Pinned official GPT-OSS reference token budget for the selected Groq model."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path
from typing import Never

from jinja2.sandbox import ImmutableSandboxedEnvironment
from tokenizers import Tokenizer

from siro.ports.models import ModelRequest
from siro.services.agent.context import ContextBudgetExceeded, ContextBudgetUnavailable


def _raise_template(message: str) -> Never:
    raise ContextBudgetUnavailable(message)


def _tojson(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


class GPTOSSBudget:
    def __init__(
        self,
        directory: Path,
        payload_builder: Callable[[ModelRequest], dict[str, object]],
        *,
        context_window: int = 131072,
        safety_tokens: int = 256,
    ) -> None:
        profile = json.loads(
            files("siro.services.agent").joinpath("gpt_oss_profile.json").read_text()
        )
        if not 1 <= context_window <= profile["context_window"] or safety_tokens < 0:
            raise ValueError("invalid provider context limit")
        for filename, digest in profile["files"].items():
            if hashlib.sha256((directory / filename).read_bytes()).hexdigest() != digest:
                raise ContextBudgetUnavailable("tokenizer asset digest mismatch")
        self._tokenizer = Tokenizer.from_file(str(directory / "tokenizer.json"))
        self._tokenizer.no_truncation()
        self._tokenizer.no_padding()
        environment = ImmutableSandboxedEnvironment(trim_blocks=True, lstrip_blocks=True)
        environment.filters["tojson"] = _tojson
        self._template = environment.from_string((directory / "chat_template.jinja").read_text())
        self._payload_builder = payload_builder
        self._context_window = context_window
        self._max_output = int(profile["max_output_tokens"])
        self._safety_tokens = safety_tokens

    def count_input(self, request: ModelRequest) -> int:
        # Copy only for HF template normalization; the SDK wire payload is never changed.
        payload = json.loads(json.dumps(self._payload_builder(request), ensure_ascii=False))
        if payload["model"] != "openai/gpt-oss-20b":
            raise ContextBudgetUnavailable("tokenizer does not match selected provider model")
        if "<|" in json.dumps(payload, ensure_ascii=False):
            raise ContextBudgetUnavailable("reserved Harmony markers require explicit encoding")
        for index, message in enumerate(payload["messages"]):
            if message["role"] not in {"system", "user", "assistant", "tool"} or (
                message["role"] == "system" and index != 0
            ):
                raise ContextBudgetUnavailable("reference template cannot count this message role")
            calls = message.get("tool_calls", [])
            if len(calls) > 1:
                raise ContextBudgetUnavailable("reference template supports one call per message")
            for call in calls:
                call["function"]["arguments"] = json.loads(call["function"]["arguments"])
        rendered = self._template.render(
            messages=payload["messages"],
            tools=payload.get("tools", []),
            add_generation_prompt=True,
            raise_exception=_raise_template,
            strftime_now=lambda fmt: datetime.now(UTC).strftime(fmt),
        )
        return len(self._tokenizer.encode(rendered, add_special_tokens=False).ids)

    def validate(self, request: ModelRequest) -> int:
        if request.max_output_tokens > self._max_output:
            raise ContextBudgetExceeded("requested output exceeds provider maximum")
        count = self.count_input(request)
        total = count + request.max_output_tokens + self._safety_tokens
        if total > self._context_window:
            raise ContextBudgetExceeded(
                f"reference input {count} + output {request.max_output_tokens} "
                f"+ safety {self._safety_tokens} exceeds context {self._context_window}"
            )
        return count

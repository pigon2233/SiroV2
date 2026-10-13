"""Disposable extractive context summaries. Sources stay in the canonical journal."""

from __future__ import annotations

import hashlib
from dataclasses import replace

from siro.ports.models import ModelMessage


def summarize_completed(
    messages: tuple[ModelMessage, ...], *, keep_tail: int = 2
) -> tuple[ModelMessage, ...]:
    """Preserve user/system text and pairing; only excerpt old completed responses.

    This is deliberately an extract, not a claim that omitted details were understood.
    Latest context and pending tool results are never shortened.
    """
    output = list(messages)
    completed_tools: set[int] = set()
    for index, message in enumerate(messages):
        if message.role != "assistant" or not message.tool_calls:
            continue
        ids = {call.call_id for call in message.tool_calls}
        results = messages[index + 1 : index + 1 + len(ids)]
        after = index + 1 + len(ids)
        if (
            len(ids) == len(message.tool_calls)
            and len(results) == len(ids)
            and all(m.role == "tool" for m in results)
            and {m.tool_call_id for m in results} == ids
            and any(m.role == "assistant" for m in messages[after:])
        ):
            completed_tools.update(range(index + 1, after))
    for index, message in enumerate(messages[: max(0, len(messages) - keep_tail)]):
        eligible = (
            message.role == "assistant" and not message.tool_calls
        ) or index in completed_tools
        if not eligible or len(message.content) <= 1024:
            continue
        digest = hashlib.sha256(message.content.encode()).hexdigest()
        content = (
            f"[Extractive summary v1; source message {index}; sha256:{digest}; "
            f"original characters:{len(message.content)}. Middle content omitted; "
            "do not infer omitted details.]\n"
            + message.content[:384]
            + "\n[… omitted …]\n"
            + message.content[-384:]
        )
        output[index] = replace(message, content=content)
    return tuple(output)

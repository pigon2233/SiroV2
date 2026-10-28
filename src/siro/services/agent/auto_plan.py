"""Conservative judgment of when a chat message is a multi-step task worth planning."""

from __future__ import annotations

import os
import re

AUTO_PLAN_FLAG = "SIRO_AUTO_PLAN_ENABLED"
_MIN_CHARS = 24
_STEP_MARKERS = re.compile(
    r"先|然後|接著|再來|之後|最後|首先|其次|並且|同時|步驟|\b1[.、)]|①|第一"
    r"|\bfirst\b|\bthen\b|\bnext\b|\bfinally\b|\band then\b",
    re.I,
)
_TASK_VERBS = re.compile(
    r"查|找|搜尋|整理|比較|分析|研究|蒐集|收集|調查|彙整|寫一份|做一份|規劃"
    r"|\bsearch\b|\bfind\b|\bresearch\b|\bcompare\b|\banaly[sz]e\b|\bsummari[sz]e\b|\bplan\b",
    re.I,
)


def auto_plan_enabled(env: dict[str, str] | None = None, *, default: str = "0") -> bool:
    return (os.environ if env is None else env).get(AUTO_PLAN_FLAG, default).strip() == "1"


def looks_multistep(text: str) -> bool:
    """True only for a long request with a task verb and at least two sequencing markers."""

    stripped = text.strip()
    if len(stripped) < _MIN_CHARS or stripped.startswith("/"):
        return False
    if not _TASK_VERBS.search(stripped):
        return False
    return len({m.group(0).lower() for m in _STEP_MARKERS.finditer(stripped)}) >= 2

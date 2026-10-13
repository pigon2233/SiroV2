"""Conservative extraction of explicit owner preference statements."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PreferenceStatement:
    subject: str
    polarity: float
    strength: float


_PATTERNS = (
    (re.compile(r"^我(?:很|非常|最)?(?:喜歡|愛)(.+)$"), 1.0),
    (re.compile(r"^我(?:很|非常)?(?:討厭|不喜歡)(.+)$"), -1.0),
)


def extract_explicit_preference(text: str) -> PreferenceStatement | None:
    normalized = text.strip().rstrip("。.! ")
    if any(marker in text for marker in ("?", "\uff1f")) or any(
        word in normalized for word in ("什麼", "哪個", "哪些", "是否")
    ):
        return None
    for pattern, polarity in _PATTERNS:
        match = pattern.fullmatch(normalized)
        if match is None:
            continue
        subject = match.group(1).strip(" ,。.!")
        if not subject or len(subject) > 200:
            return None
        strength = 1.0 if any(word in normalized for word in ("非常", "最", "愛")) else 0.8
        return PreferenceStatement(subject, polarity, strength)
    return None

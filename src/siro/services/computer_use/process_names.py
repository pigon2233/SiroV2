"""Opt-in exact process-name normalization. Never substring/prefix/title authorization."""

from __future__ import annotations

import os
import re
import string
import unicodedata
from collections.abc import Iterable, Mapping

NORMALIZE_ENV = "SIRO_COMPUTER_NORMALIZE_PROCESS_NAMES"


def normalization_enabled(env: Mapping[str, str] | None = None) -> bool:
    return (os.environ if env is None else env).get(NORMALIZE_ENV, "0") == "1"


def process_key(name: str) -> str:
    if not name or len(name) > 80 or any(c in name for c in ("/", "\\", ":", "\0")):
        return ""
    name = name.strip().lower().removesuffix(".exe")
    result = []
    for char in name:
        if char.isalnum():
            result.append(char)
        elif (
            char.isspace()
            or char in string.punctuation
            or unicodedata.category(char).startswith("P")
        ):
            continue
        else:
            return ""  # symbols/combining forms are not silently removed
    return "".join(result)


def process_in(name: str, allowed: Iterable[str], env: Mapping[str, str] | None = None) -> bool:
    if not normalization_enabled(env):
        return name in allowed  # byte-for-byte legacy behavior when OFF
    key = process_key(name)
    return bool(key) and any(process_key(candidate) == key for candidate in allowed)


def mentions_process(stem: str, text: str) -> bool:
    key = process_key(stem + ".exe")  # callers supply an already stripped ProcessName stem
    if len(key) < 3:
        return False
    # Only separators BETWEEN exact letters/digits; longer words never match.
    pattern = r"(?<![a-z0-9])" + r"(?:[^\w]|_)*".join(re.escape(c) for c in key) + r"(?![a-z0-9])"
    return re.search(pattern, text.lower()) is not None

"""Small, deterministic redaction boundary for diagnostic output."""

from __future__ import annotations

import re
from collections.abc import Mapping

_SENSITIVE_NAME = re.compile(r"(?:api[_-]?key|token|secret|password|credential)", re.I)


def redact_mapping(values: Mapping[str, object]) -> dict[str, object]:
    """Redact values whose keys indicate credentials.

    This protects SIRO-owned structured diagnostics. It is not a replacement for
    a full log classification and secret scanning policy.
    """

    return {
        key: "[REDACTED]" if _SENSITIVE_NAME.search(key) else value for key, value in values.items()
    }

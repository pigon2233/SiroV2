"""Fail CI on findings except the exact independently reviewed public tokenizer pins."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

PROFILE = "src/siro/services/agent/gpt_oss_profile.json"
# Public blob and detector fingerprints: FIX-016/scan-public-fingerprint-binding.json.
PROFILE_SHA256 = (
    "3fbccde17033b8443aee5a26e1824c88955b8418c955b03ef003c712939a645e"  # pragma: allowlist secret
)
PUBLIC_PINS = {
    (3, "1d403576bfa0919fac728d081b7d3730ab5274e1"),  # pragma: allowlist secret
    (7, "000cca28ecda60515feca539cdf16adac987fa1a"),  # pragma: allowlist secret
    (8, "a074e33a8b7597cf69d7a35d59a8e238cef430cf"),  # pragma: allowlist secret
    (9, "8ebd7373145de425bee23fbd71343dd1db3e7627"),  # pragma: allowlist secret
    (10, "3657a04a520af8371b7f923474b3b91e1040d516"),  # pragma: allowlist secret
    (11, "9833b8adf7737438ef1bc5a313ca0f97e3b1992f"),  # pragma: allowlist secret
}


def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate report key")
        result[key] = value
    return result


def unresolved(report: object) -> list[tuple[str, int, str]]:
    if not isinstance(report, dict) or not isinstance(report.get("results"), dict):
        raise ValueError("invalid report")
    try:
        profile_matches = hashlib.sha256(Path(PROFILE).read_bytes()).hexdigest() == PROFILE_SHA256
    except OSError:
        profile_matches = False
    failures: list[tuple[str, int, str]] = []
    for path, findings in report["results"].items():
        if not isinstance(path, str) or not isinstance(findings, list) or not findings:
            raise ValueError("invalid findings")
        for finding in findings:
            if not isinstance(finding, dict):
                raise ValueError("invalid finding")
            line = finding.get("line_number")
            kind = finding.get("type")
            fingerprint = finding.get("hashed_secret")
            if (
                type(line) is not int
                or line < 1
                or not isinstance(kind, str)
                or not isinstance(fingerprint, str)
                or finding.get("filename") != path
                or type(finding.get("is_verified")) is not bool
            ):
                raise ValueError("invalid finding binding")
            if (
                path == PROFILE
                and profile_matches
                and kind == "Hex High Entropy String"
                and finding["is_verified"] is False
                and (line, fingerprint) in PUBLIC_PINS
            ):
                continue
            failures.append((path, line, kind))
    return failures


def main() -> int:
    try:
        failures = unresolved(json.load(sys.stdin, object_pairs_hook=unique_object))
    except (ValueError, TypeError):
        print("Invalid secret scanner report; CI refused.", file=sys.stderr)
        return 1
    for path, line, kind in failures:
        print(f"{path}:{line}: {kind}", file=sys.stderr)
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())

"""Fail CI except exact reviewed public pins and immutable verification snapshots."""

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


# FIX-026: immutable audited bytes AND their complete scanner findings batch.
# See docs/evidence/FIX-026-2026-10-16/semantic-audit.json.
REVIEWED_SNAPSHOTS = {
    "docs/runtime-evolution/SOURCE_INVENTORY.json": (
        104,
        (
            "defc0c12c09e7695cfad67f7cf8e25de"  # pragma: allowlist secret
            "2f860f496856a857a6a553033723e6ef"  # pragma: allowlist secret
        ),
        (
            "470b5429bbd2b89ef7de0669c13ff9a3"  # pragma: allowlist secret
            "9e97488c34aa9022dcd4fb09b49f3d32"  # pragma: allowlist secret
        ),
    ),
    "docs/runtime-evolution/verification/RT005_reverification_2026-10-01/source-snapshot.json": (
        120,
        (
            "eba8b23d59ffd494a798d316044dc760"  # pragma: allowlist secret
            "4ea5cb5cc293920ffd1622096a219730"  # pragma: allowlist secret
        ),
        (
            "6ffe496087286a8c527f2b7c8d57cc7c"  # pragma: allowlist secret
            "78dbbfbf2906be1a079725a9671733ac"  # pragma: allowlist secret
        ),
    ),
    "docs/runtime-evolution/verification/RT006_2026-10-01/gpu.log": (
        2,
        (
            "803a62637ad3fcaa34e510a48faf8cde"  # pragma: allowlist secret
            "5d00c130fd20224dccceadc4f1da008c"  # pragma: allowlist secret
        ),
        (
            "6fe57011542290ed649726f2203d6c6c"  # pragma: allowlist secret
            "229bd71083c1dc8da1af3bc6961c4a0b"  # pragma: allowlist secret
        ),
    ),
    "docs/runtime-evolution/verification/RT006_2026-10-01/source-snapshot.json": (
        136,
        (
            "504303671219d35045464a3bc57fb055"  # pragma: allowlist secret
            "c4d8148815a843610ace16aabbefa96d"  # pragma: allowlist secret
        ),
        (
            "7e434a8c348821c0706d6e0fbafbb924"  # pragma: allowlist secret
            "a40e3347f862b6aaf464dd0612f504d2"  # pragma: allowlist secret
        ),
    ),
    "docs/runtime-evolution/verification/RT007_2026-10-02/source-snapshot.json": (
        120,
        (
            "a4de80378dd9abc8822173740c21895d"  # pragma: allowlist secret
            "2ae45e5ac51f30e30330206c19bccf1d"  # pragma: allowlist secret
        ),
        (
            "f7977e39a3a62caf7118e9bcdc5ba8a9"  # pragma: allowlist secret
            "aff6f76513c391f5f4350f348d4dd994"  # pragma: allowlist secret
        ),
    ),
    "docs/runtime-evolution/verification/RT009_reverification_2026-10-05/source-snapshot.json": (
        121,
        (
            "4dea35e35e17ef7521bcb5c59ba6584c"  # pragma: allowlist secret
            "340260cf7df4e0c0ae0cc2698aa9931b"  # pragma: allowlist secret
        ),
        (
            "4ecee6b635a010e20da8d9bba9a2ccda"  # pragma: allowlist secret
            "501161459b4c18de0b08c5632237d023"  # pragma: allowlist secret
        ),
    ),
    "docs/runtime-evolution/verification/RT010_2026-10-05/source-snapshot.json": (
        121,
        (
            "66528a685475fedce0364a320b9eafb9"  # pragma: allowlist secret
            "0da14b917b2ffa69322ca5080af458c0"  # pragma: allowlist secret
        ),
        (
            "4c8034cd620e9081ca4b204edef5ac56"  # pragma: allowlist secret
            "fe3f8dde4ff66b101223fe0f948070dd"  # pragma: allowlist secret
        ),
    ),
    "docs/runtime-evolution/verification/RT011_2026-10-05/source-snapshot.json": (
        124,
        (
            "bf8c12210d7d067fe299dd117aa40a0b"  # pragma: allowlist secret
            "3d8f5ddcfbed020e7133bd9913a8c361"  # pragma: allowlist secret
        ),
        (
            "8ddfda579863adc3f803b4e3a2d25d04"  # pragma: allowlist secret
            "2acc664d44180de7d4483a6aa88b168e"  # pragma: allowlist secret
        ),
    ),
    "docs/runtime-evolution/verification/RT011_2026-10-05/test_independent.py": (
        1,
        (
            "2649955abeddc20e070b57f66f224095"  # pragma: allowlist secret
            "725d06ebd4777a477a4d0c6cd1ca0638"  # pragma: allowlist secret
        ),
        (
            "c8b785831a67f748b2e4dfe794ee64e6"  # pragma: allowlist secret
            "b0f3e5d26c1468bac50de0e59e7fecd5"  # pragma: allowlist secret
        ),
    ),
    "docs/runtime-evolution/verification/RT012_2026-10-05/source-snapshot.json": (
        125,
        (
            "de6f376d19a96b54cb570370dbe00082"  # pragma: allowlist secret
            "d6fb3ef753be9b8f163bab036ed23277"  # pragma: allowlist secret
        ),
        (
            "e8de167422788479b5071b35a546c083"  # pragma: allowlist secret
            "cb8cfafdc36ced2424bbea39e7624616"  # pragma: allowlist secret
        ),
    ),
    "docs/runtime-evolution/verification/RT014_2026-10-05/source-snapshot.json": (
        125,
        (
            "4fdebac0ae3295e5fa212d8fff88fc34"  # pragma: allowlist secret
            "e7dcce1804af847871a4446bf2f07ee7"  # pragma: allowlist secret
        ),
        (
            "c146cca21276e16ed0dca8ab66e04867"  # pragma: allowlist secret
            "aba24f523fe37219f95b4b9d45edc6d8"  # pragma: allowlist secret
        ),
    ),
    "docs/runtime-evolution/verification/architecture_review_2026-10-03/source-digests.json": (
        110,
        (
            "22232a316ab8f7b7f110b0a148f70781"  # pragma: allowlist secret
            "da08a197c1b7819548e6f55fbdad0cdc"  # pragma: allowlist secret
        ),
        (
            "928ecf5995a14e323edcd7450f2c6cd4"  # pragma: allowlist secret
            "992dcd7def511d632544ad1425ae29a4"  # pragma: allowlist secret
        ),
    ),
    "docs/runtime-evolution/verification/architecture_review_2026-10-05/source-digests.json": (
        123,
        (
            "74ab1f34f07b561d3ec0c57889061994"  # pragma: allowlist secret
            "50f06843a4a90b6d7d91794db59abb4b"  # pragma: allowlist secret
        ),
        (
            "fafa3cbe276ca8c481fa5dbb2f437eca"  # pragma: allowlist secret
            "edfae74bc08ee262dc6c338fc26515c4"  # pragma: allowlist secret
        ),
    ),
    # CP-P01: versioned visual pack; the 11 hex values are SHA-256 digests of real files.
    # See docs/evidence/CP-P01-2026-10-18/secret-audit.json. A new pack version needs review.
    "assets/companion/haru-upperbody/0.1.0/pack.json": (
        11,
        (
            "d9b65f71da57f3699996049a6df51386"  # pragma: allowlist secret
            "1bae884d0c9ddb82da62c2e5f8858137"  # pragma: allowlist secret
        ),
        (
            "aed0f7dcc863a7889bff89c8004c253a"  # pragma: allowlist secret
            "88c12becf46cef0202199b0461d05456"  # pragma: allowlist secret
        ),
    ),
}


def reviewed_snapshot(path: str, batch: list[tuple[str, int, str, str, bool]]) -> bool:
    expected = REVIEWED_SNAPSHOTS.get(path)
    if expected is None or len(batch) != expected[0]:
        return False
    target = Path(path)
    try:
        if any(part.is_symlink() for part in (target, *target.parents)):
            return False
        if hashlib.sha256(target.read_bytes()).hexdigest() != expected[1]:
            return False
    except OSError:
        return False
    encoded = json.dumps(sorted(batch), ensure_ascii=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest() == expected[2]


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
        batch: list[tuple[str, int, str, str, bool]] = []
        for finding in findings:
            if not isinstance(finding, dict):
                raise ValueError("invalid finding")
            line = finding.get("line_number")
            kind = finding.get("type")
            fingerprint = finding.get("hashed_secret")
            verified = finding.get("is_verified")
            if (
                type(line) is not int
                or line < 1
                or not isinstance(kind, str)
                or not isinstance(fingerprint, str)
                or finding.get("filename") != path
                or type(verified) is not bool
            ):
                raise ValueError("invalid finding binding")
            batch.append((path, line, kind, fingerprint, verified))
        if reviewed_snapshot(path, batch):
            continue
        for _, line, kind, fingerprint, verified in batch:
            if (
                path == PROFILE
                and profile_matches
                and kind == "Hex High Entropy String"
                and verified is False
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

"""Audit only the explicitly selected public FIX-016 candidates; never scan private roots.

Run with the repository's Python: this_script [--publication-only].
Raw detector results and audit outputs are excluded from their own input scope.
Every accepted entropy finding is bound to calculated public bytes or an independently
reviewed public pin. Unknown values remain UNRESOLVED; values are never printed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
REL_EVIDENCE = EVIDENCE.relative_to(ROOT).as_posix()
PUBLIC_COMMIT = "d1f5d07c6c9ab8e8f17b091fcf9ea387685803d5"
PROFILE = "src/siro/services/agent/gpt_oss_profile.json"
EXTRA_EVIDENCE = ROOT / "docs/evidence/FIX-017-2026-10-13"
EXTRA_PUBLIC_PARENT = "2324b359310e9ae62edb357969d75a3c96e8887c"
PUBLICATION = (
    "rust-toolchain.toml",
    "scripts/check",
    "scripts/check_secrets.py",
    "tests/integration/test_ci_secret_gate.py",
    "runtime/siro-runtime/src/linux.rs",
    ".github/workflows/check.yml",
    "tests/integration/test_unknown_effect_approval.py",
    "src/siro/services/audio/tts.py",
    "tests/integration/test_tts_import_boundary.py",
    "docs/CONTRACTS.md",
    "docs/DECISIONS.md",
    "docs/STATUS.md",
    "docs/runtime-evolution/FIX_REGISTER.md",
    "docs/runtime-evolution/RUNTIME_EVOLUTION_ROADMAP.md",
    "docs/runtime-evolution/ARCHITECTURE_REVIEW.md",
    f"{REL_EVIDENCE}/REPORT.md",
    "docs/evidence/FIX-017-2026-10-13/REPORT.md",
)
RAW_REPORTS = {
    "scan-original-public.json",
    "scan-with-public-tokenizer.json",
    "scan-with-public-tokenizer-diagnostic-no-verify.json",
    "repair-source-secrets.json",
    "publish-code-docs-secret-scan.json",
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fingerprint(value: str) -> str:
    return hashlib.sha1(value.encode()).hexdigest()


def git_bytes(path: str) -> bytes:
    if path.startswith((".siro-data/", ".codex/")) or ".." in Path(path).parts:
        raise ValueError("private or unsafe public-blob request refused")
    return subprocess.run(
        ["git", "show", f"{PUBLIC_COMMIT}:{path}"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout


def input_paths(publication_only: bool) -> list[str]:
    result = set(PUBLICATION)
    if not publication_only:
        for path in EVIDENCE.rglob("*"):
            if not path.is_file():
                continue
            if path.name in RAW_REPORTS or path.name.startswith("scan-artifact-"):
                continue
            relative = path.relative_to(ROOT).as_posix()
            if "before" in path.relative_to(EVIDENCE).parts:
                original = path.relative_to(EVIDENCE / "before").as_posix()
                if path.read_bytes() != git_bytes(original):
                    raise ValueError("before-snapshot differs from public Git bytes")
                result.add(relative)
            elif path.suffix in {".json", ".log", ".md", ".patch", ".py"}:
                result.add(relative)
        for path in EXTRA_EVIDENCE.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(ROOT).as_posix()
            if "before" in path.relative_to(EXTRA_EVIDENCE).parts:
                original = path.relative_to(EXTRA_EVIDENCE / "before").as_posix()
                if path.read_bytes() != git_bytes(original):
                    raise ValueError("extra before-snapshot differs from public Git bytes")
            if path.suffix in {".json", ".log", ".md", ".patch", ".py"}:
                result.add(relative)
    return sorted(result)


def proofs(captured: dict[str, bytes]) -> dict[str, list[dict[str, str]]]:
    known: dict[str, list[dict[str, str]]] = {}

    def add(value: str, reason: str, binding: str) -> None:
        known.setdefault(fingerprint(value), []).append({"reason": reason, "binding": binding})

    for path, data in captured.items():
        add(digest(data), "actual captured public file SHA256", path)
    baseline_path = f"{REL_EVIDENCE}/baseline.json"
    if baseline_path in captured:
        baseline = json.loads(captured[baseline_path])
        for path, expected in baseline.items():
            if not path.startswith(
                ("src/", "tests/", "scripts/", "runtime/", ".github/")
            ) and path not in {
                "Cargo.lock",
                "rust-toolchain.toml",
                "uv.lock",
                ".python-version",
            }:
                raise ValueError("baseline contains an unselected public path")
            actual = digest(git_bytes(path))
            if actual != expected:
                raise ValueError("baseline digest differs from exact public Git blob")
            add(actual, "verified exact public Git baseline file SHA256", path)
    add(PUBLIC_COMMIT, "published Git commit", PUBLIC_COMMIT)
    references = ["HEAD", "origin/main"]
    lineage = (
        subprocess.run(
            ["git", "rev-list", "--max-count=16", f"{PUBLIC_COMMIT}..HEAD"],
            cwd=ROOT,
            capture_output=True,
            check=True,
        )
        .stdout.decode()
        .splitlines()
    )
    references.extend(lineage)
    for reference in dict.fromkeys(references):
        descendant = subprocess.run(
            ["git", "merge-base", "--is-ancestor", PUBLIC_COMMIT, reference],
            cwd=ROOT,
            capture_output=True,
        )
        if descendant.returncode == 0:
            commit = (
                subprocess.run(
                    ["git", "rev-parse", reference], cwd=ROOT, capture_output=True, check=True
                )
                .stdout.decode()
                .strip()
            )
            add(commit, "current public-line candidate Git identity", reference)
            for path in PUBLICATION:
                blob = subprocess.run(
                    ["git", "show", f"{commit}:{path}"], cwd=ROOT, capture_output=True
                )
                if blob.returncode == 0:
                    add(
                        digest(blob.stdout),
                        "selected public-line Git snapshot SHA256",
                        f"{commit}:{path}",
                    )
    extra_baseline_path = "docs/evidence/FIX-017-2026-10-13/baseline.json"
    if extra_baseline_path in captured:
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", PUBLIC_COMMIT, EXTRA_PUBLIC_PARENT],
            cwd=ROOT,
            check=True,
        )
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", EXTRA_PUBLIC_PARENT, "HEAD"],
            cwd=ROOT,
            check=True,
        )
        for path, expected in json.loads(captured[extra_baseline_path]).items():
            if path not in json.loads(captured[baseline_path]) and path not in PUBLICATION:
                raise ValueError("extra baseline path outside existing audited public scope")
            original = subprocess.run(
                ["git", "show", f"{EXTRA_PUBLIC_PARENT}:{path}"],
                cwd=ROOT,
                capture_output=True,
                check=True,
            ).stdout
            if digest(original) != expected:
                raise ValueError("extra baseline does not match its actual public parent")
            add(expected, "verified FIX-017 public parent baseline SHA256", path)
    sqlite_path = f"{REL_EVIDENCE}/scan-sqlite-public-state.json"
    if sqlite_path in captured:
        state = json.loads(captured[sqlite_path])
        official_digest = "9145255e83da6529e70121ee4d7a4c88fe83ca4511da0c9ed13d10842df36782"
        if (
            state["official_release_url"] != "https://www.sqlite.org/releaselog/3_50_4.html"
            or state["official_amalgamation_url"]
            != "https://www.sqlite.org/2025/sqlite-amalgamation-3500400.zip"
            or state["sqlite3_c_sha3_256"] != official_digest
            or state["official_source_digest_match"] is not True
        ):
            raise ValueError("official SQLite source proof changed")
        add(official_digest, "official release sqlite3.c SHA3 and actual source match", sqlite_path)
    archive = subprocess.run(
        ["git", "archive", PUBLIC_COMMIT], cwd=ROOT, capture_output=True, check=True
    ).stdout
    add(digest(archive), "recomputed public Git archive SHA256", PUBLIC_COMMIT)
    profile_bytes = git_bytes(PROFILE)
    profile = json.loads(profile_bytes)
    add(digest(profile_bytes), "exact public Git profile blob SHA256", PROFILE)
    values = [("revision", profile["revision"]), *profile["files"].items()]
    for field, value in values:
        add(value, "independently audited public tokenizer pin", f"{PROFILE}:{field}")
        add(fingerprint(value), "detector fingerprint of audited public pin", f"{PROFILE}:{field}")
    primary_path = f"{REL_EVIDENCE}/scan-public-primary-pins.json"
    if primary_path in captured:
        primary = json.loads(captured[primary_path])
        checks = primary["checks"]
        if primary["profile_sha256"] != digest(profile_bytes) or len(checks) != 5:
            raise ValueError("public primary-pin evidence binding changed")
        for row in checks:
            filename = row["file"]
            value = profile["files"][filename]
            url = (
                f"https://huggingface.co/{profile['repository']}/resolve/"
                f"{profile['revision']}/{filename}"
            )
            if not (
                row["expected_sha256"] == row["actual_sha256"] == value
                and row["matches"] is True
                and row["primary_url"] == url
            ):
                raise ValueError("public primary-pin evidence differs from reviewed public pins")
    fixture_source = captured.get("tests/integration/test_ci_secret_gate.py", b"")
    if b"ci-boundary-test-credential-never-valid" in fixture_source:
        synthetic = hashlib.sha256(b"ci-boundary-test-credential-never-valid").hexdigest()
        add(
            fingerprint(synthetic),
            "actual synthetic application fixture detector fingerprint",
            "test_ci_secret_gate.py",
        )
    return known


def classify(
    finding: dict[str, object],
    path: str,
    captured: dict[str, bytes],
    known: dict[str, list[dict[str, str]]],
) -> list[dict[str, str]]:
    kind = finding["type"]
    hashed = finding["hashed_secret"]
    if finding["is_verified"] is not False or not isinstance(hashed, str):
        return []
    if kind == "Hex High Entropy String" and hashed in known:
        return known[hashed]
    if path == f"{REL_EVIDENCE}/scan-public-fingerprint-binding.json" and kind == "Secret Keyword":
        line_number = finding["line_number"]
        if type(line_number) is int and line_number > 0 and hashed in known:
            line = captured[path].decode().splitlines()[line_number - 1].strip().removesuffix(",")
            try:
                field = json.loads("{" + line + "}")
            except ValueError:
                field = {}
            if (
                list(field) == ["hashed_secret"]
                and isinstance(field["hashed_secret"], str)
                and fingerprint(field["hashed_secret"]) == hashed
                and any(
                    p["reason"] == "detector fingerprint of audited public pin"
                    for p in known[hashed]
                )
            ):
                return [
                    {
                        "reason": "exact public pin detector-fingerprint metadata field",
                        "binding": path,
                    }
                ]
    if path == f"{REL_EVIDENCE}/git-metadata-boundary-before.log" and kind == "Secret Keyword":
        source = captured.get("tests/integration/test_ci_secret_gate.py", b"")
        line_number = finding["line_number"]
        if b"synthetic-public-commit" in source and type(line_number) is int and line_number == 42:
            detector_fp = fingerprint(hashlib.sha1(b"synthetic-public-commit").hexdigest())
            truncated_repr = detector_fp[:12] + "...ame"
            line = captured[path].decode().splitlines()[line_number - 1]
            if (
                hashed == fingerprint(truncated_repr)
                and "'.git/FETCH_HEAD':" in line
                and f"'hashed_secret': '{truncated_repr}'" in line
                and "'new_provider.py'" in line
            ):
                return [
                    {
                        "reason": "exact synthetic detector metadata in truncated pytest repr",
                        "binding": path,
                    }
                ]
    if path != f"{REL_EVIDENCE}/secret-gate-before.log":
        return []
    line_number = finding["line_number"]
    if type(line_number) is not int or line_number < 1:
        return []
    lines = captured[path].decode().splitlines()
    line = lines[line_number - 1]
    if (
        kind == "Secret Keyword"
        and hashed in known
        and any(p["reason"] == "detector fingerprint of audited public pin" for p in known[hashed])
        and line.startswith("public_report = {")
        and "'hashed_secret':" in line
        and "'is_verified': False" in line
    ):
        return [{"reason": "captured pytest public scanner-report fixture field", "binding": path}]
    unreviewed = hashlib.sha1(b"unreviewed").hexdigest()
    source = captured.get("tests/integration/test_ci_secret_gate.py", b"")
    if (
        kind == "Hex High Entropy String"
        and hashed == fingerprint(unreviewed)
        and b'hashlib.sha1(b"unreviewed").hexdigest()' in source
        and unreviewed in line
        and "value =" in line
    ):
        return [{"reason": "fixed never-credential malformed-finding test value", "binding": path}]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publication-only", action="store_true")
    args = parser.parse_args()
    paths = input_paths(args.publication_only)
    captured: dict[str, bytes] = {}
    for path in paths:
        absolute = ROOT / path
        if absolute.is_symlink() or not absolute.is_file():
            raise ValueError("selected public candidate is missing or a symlink")
        captured[path] = absolute.read_bytes()
    known = proofs(captured)
    suffix = "publication" if args.publication_only else "final"
    scope = {
        "cutoff_utc": datetime.now(UTC).isoformat(),
        "publication_only": args.publication_only,
        "base_public_commit": PUBLIC_COMMIT,
        "main_private_tree_scanned": False,
        "explicit_selected_files_only": True,
        "files": {
            path: {"sha256": digest(data), "bytes": len(data)} for path, data in captured.items()
        },
        "excluded_raw_scanner_results": sorted(RAW_REPORTS),
        "excluded_own_outputs_prefix": "scan-artifact-",
    }
    with tempfile.TemporaryDirectory(prefix="siro-fix016-artifact-audit-") as temporary:
        temporary_root = Path(temporary)
        for path, data in captured.items():
            target = temporary_root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        run = subprocess.run(
            [str(ROOT / ".venv/bin/detect-secrets"), "scan", "--all-files", "--no-verify", *paths],
            cwd=temporary_root,
            capture_output=True,
            check=True,
            timeout=120,
        )
        report = json.loads(run.stdout)
    findings = []
    unresolved = []
    for path, items in report["results"].items():
        if path not in captured:
            raise ValueError("detector returned a file outside explicit captured scope")
        for finding in items:
            if finding["filename"] != path:
                raise ValueError("detector filename binding changed")
            proof = classify(finding, path, captured, known)
            row = {
                **finding,
                "classification": "REVIEWED_FALSE_POSITIVE" if proof else "UNRESOLVED",
                "proof": proof,
            }
            findings.append(row)
            if not proof:
                unresolved.append(row)
    changed = [path for path, data in captured.items() if (ROOT / path).read_bytes() != data]
    result = {
        "status": "PASS" if not unresolved and not changed else "FAIL",
        "cutoff_utc": scope["cutoff_utc"],
        "captured_files": len(captured),
        "raw_findings": len(findings),
        "reviewed_false_positives": len(findings) - len(unresolved),
        "unresolved": len(unresolved),
        "source_changed_during_audit": changed,
        "scanner_no_verify": True,
        "scanner_executable_from_shared_venv_only": True,
        "temporary_captured_public_copy_removed": True,
        "findings": findings,
    }
    (EVIDENCE / f"scan-artifact-{suffix}-scope.json").write_text(json.dumps(scope, indent=2) + "\n")
    (EVIDENCE / f"scan-artifact-{suffix}-raw.json").write_bytes(run.stdout)
    (EVIDENCE / f"scan-artifact-{suffix}-result.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "status",
                    "captured_files",
                    "raw_findings",
                    "reviewed_false_positives",
                    "unresolved",
                    "source_changed_during_audit",
                )
            }
        )
    )
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

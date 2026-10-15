"""Independently scan only D57 public/synthetic publication inputs in neutral names."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

OUT = Path(__file__).resolve().parent
EVIDENCE = OUT.parent
REPO = EVIDENCE.parents[2]
FINAL = "--final" in sys.argv
REVIEW_SCRIPT_STARTED_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
EXCLUSION = r"(^|/)(\.git|\.venv|\.mypy_cache|\.pytest_cache|\.ruff_cache|models|node_modules|target|uv\.lock|docs/evidence)/|(^|/)\.env\.local$"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_bytes(path: str) -> bytes:
    return subprocess.check_output(["git", "show", f"HEAD:{path}"], cwd=REPO, stderr=subprocess.DEVNULL)


def save(name: str, value: object) -> None:
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def json_strings(text: str) -> list[tuple[str, int, str]]:
    """Retain each JSON value's exact RFC6901 pointer and original line number."""
    tokens = list(re.finditer(r'"(?:\\.|[^"\\])*"|[{}\[\],:]|true|false|null|-?\d+(?:\.\d+)?(?:[Ee][+-]?\d+)?', text))
    position = 0
    strings: list[tuple[str, int, str]] = []

    def escaped(key: str) -> str:
        return key.replace("~", "~0").replace("/", "~1")

    def value(pointer: str) -> None:
        nonlocal position
        match = tokens[position]
        token = match.group()
        position += 1
        if token == "{":
            while tokens[position].group() != "}":
                key = json.loads(tokens[position].group())
                position += 2
                value(pointer + "/" + escaped(key))
                if tokens[position].group() == ",":
                    position += 1
                else:
                    break
            position += 1
        elif token == "[":
            index = 0
            while tokens[position].group() != "]":
                value(pointer + "/" + str(index))
                index += 1
                if tokens[position].group() == ",":
                    position += 1
                else:
                    break
            position += 1
        elif token.startswith('"'):
            strings.append((pointer, text.count("\n", 0, match.start()) + 1, json.loads(token)))

    value("")
    return strings


def public_path(value: str) -> bool:
    return value.startswith(("src/", "tests/", "runtime/", "scripts/", "schemas/", ".github/")) or value in {
        "Cargo.toml", "Cargo.lock", "rust-toolchain.toml", "pyproject.toml", "uv.lock", ".python-version", "README.md", ".gitignore", "AGENTS.md"
    }


runner = ast.parse((EVIDENCE / "clean-check-runner.py").read_text())
sources = next(ast.literal_eval(node.value) for node in runner.body if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "paths" for target in node.targets))
assert len(sources) == 15 and len(set(sources)) == 15
tracked = set(subprocess.check_output(["git", "ls-files", "docs"], cwd=REPO, text=True).splitlines())
modified = subprocess.check_output(["git", "diff", "--name-only"], cwd=REPO, text=True).splitlines()
docs = sorted(path for path in modified if path in tracked and path.startswith("docs/") and not path.startswith("docs/evidence/"))
assert len(docs) == 12
evidence_files = sorted(path for path in EVIDENCE.rglob("*") if path.is_file() and not path.is_relative_to(OUT))
assert not any(path.is_symlink() for path in evidence_files)
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
gate_hashes = {path: digest((REPO / path).read_bytes()) for path in ("scripts/check", "scripts/check_secrets.py")}
assert all((REPO / path).read_bytes() == git_bytes(path) for path in gate_hashes)
assert EXCLUSION in (REPO / "scripts/check").read_text()

temporary = Path(tempfile.mkdtemp(prefix="d57pubreview-"))
manifest: list[dict[str, object]] = []
scans: list[dict[str, object]] = []
reports: dict[str, dict] = {}
snapshot: dict[str, bytes] = {}
started = datetime.now(UTC).isoformat()
try:
    for group, paths in (("source_docs", [REPO / path for path in sources + docs]), ("evidence", evidence_files)):
        folder = temporary / group
        folder.mkdir()
        for path in paths:
            original = path.relative_to(REPO).as_posix()
            neutral = path.relative_to(EVIDENCE).as_posix() if group == "evidence" else original
            assert "docs/evidence" not in neutral
            data = path.read_bytes()
            target = folder / neutral
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            snapshot[original] = data
            manifest.append({"group": group, "original": original, "neutral": neutral, "sha256": digest(data), "bytes": len(data), "copy_stable": target.read_bytes() == data})
        began = time.monotonic()
        command = [str(REPO / ".venv/bin/detect-secrets"), "scan", "--all-files", "--exclude-files", EXCLUSION]
        result = subprocess.run(command, cwd=folder, capture_output=True, timeout=120)
        (OUT / f"{group.replace('_', '-')}-scanner.stderr").write_bytes(result.stderr)
        report = json.loads(result.stdout)
        reports[group] = report
        save(f"{group.replace('_', '-')}-scanner.json", report)
        scans.append({"group": group, "exit_code": result.returncode, "command": ["detect-secrets", "scan", "--all-files", "--exclude-files", EXCLUSION], "elapsed_seconds": round(time.monotonic() - began, 3), "findings": sum(map(len, report["results"].values())), "files_with_findings": len(report["results"]), "scanner_version": report["version"]})
    gate = subprocess.run([str(REPO / ".venv/bin/python"), str(REPO / "scripts/check_secrets.py")], cwd=temporary / "source_docs", input=json.dumps(reports["source_docs"]).encode(), capture_output=True, timeout=30)
    (OUT / "source-docs-gate.stderr").write_bytes(gate.stderr)

    # Each allowed value must be traceable to an exact public blob or a named SHA
    # metadata field in an individually hash-bound, inspected synthetic receipt.
    proofs: dict[str, list[dict[str, object]]] = {}

    def proof(data: bytes, description: dict[str, object]) -> None:
        proofs.setdefault(digest(data), []).append(description)

    for original, data in snapshot.items():
        proof(data, {"verification": "exact_scoped_input_bytes", "path": original})
    public_names: set[str] = set()
    preservation = json.loads(snapshot[(EVIDENCE / "baseline-preservation.json").relative_to(REPO).as_posix()])
    source_preservation = json.loads(snapshot[(EVIDENCE / "preservation-final.json").relative_to(REPO).as_posix()])
    public_names.update(preservation["original_python_test_files"])
    public_names.update(preservation["original_migrations"])
    public_names.update(source_preservation["records"])
    for rel in ("product/RESULTS.json", "product/preflight/RESULTS.json"):
        data = json.loads(snapshot[(EVIDENCE / rel).relative_to(REPO).as_posix()])
        public_names.update("src/" + path for path in data.get("host_source_sha256", {}))
        public_names.update(data.get("copied_source_sha256", {}))
    public_names.update(sources)
    preservation_working_before = {path: digest((REPO / path).read_bytes()) for path in set(preservation["original_python_test_files"]) | set(preservation["original_migrations"]) | set(source_preservation["records"])}
    for path in sorted(public_names):
        assert public_path(path) and not Path(path).is_absolute() and ".." not in Path(path).parts
        try:
            data = git_bytes(path)
        except subprocess.CalledProcessError:
            continue
        proof(data, {"verification": "exact_public_parent_blob", "path": path, "commit": head})
        # Only preservation manifests mandate comparison of their public old files.
        if path in preservation["original_python_test_files"] or path in preservation["original_migrations"] or path in source_preservation["records"]:
            proof((REPO / path).read_bytes(), {"verification": "exact_public_preservation_input", "path": path})
    old_test_checks = {path: digest((REPO / path).read_bytes()) == expected and (REPO / path).read_bytes() == git_bytes(path) for path, expected in preservation["original_python_test_files"].items()}
    old_migration_checks = {path: digest((REPO / path).read_bytes()) == expected and (REPO / path).read_bytes() == git_bytes(path) for path, expected in preservation["original_migrations"].items()}
    journal_path = "tests/integration/test_run_journal.py"
    journal_original = git_bytes(journal_path)
    journal_current = (REPO / journal_path).read_bytes()
    journal_old_line = b"    assert migrations[-1].version == 13\n"
    journal_new_lines = b'    assert migrations[12].version == 13\n    assert migrations[12].name == "run_journal"\n'
    journal_exact_transform = journal_original.count(journal_old_line) == 1 and journal_current == journal_original.replace(journal_old_line, journal_new_lines, 1)
    assert len(old_test_checks) == 135 and sum(old_test_checks.values()) == 134 and [path for path, unchanged in old_test_checks.items() if not unchanged] == [journal_path]
    assert journal_exact_transform and len(old_migration_checks) == 13 and all(old_migration_checks.values())
    source_record_checks = {path: digest(git_bytes(path)) == record["before"] and digest((REPO / path).read_bytes()) == record["after"] for path, record in source_preservation["records"].items()}
    assert len(source_record_checks) == 174 and all(source_record_checks.values())
    old_source_changed = [path for path, record in source_preservation["records"].items() if record["before"] != record["after"]]
    assert len(old_source_changed) == 6 and set(old_source_changed) == set(source_preservation["changed_existing_source"])
    final_full = json.loads(snapshot[(EVIDENCE / "regression/clean-check-final.json").relative_to(REPO).as_posix()])
    final_full_source_binding = final_full["source_scope"] == {path: digest(snapshot[path]) for path in sources}
    assert final_full_source_binding and final_full["status"] == "PASS" and final_full["exit_code"] == 0
    assert final_full["working_source_preserved"] and final_full["children_joined"] and final_full["temporary_roots_removed"]

    product_receipt = json.loads(snapshot[(EVIDENCE / "product/RESULTS.json").relative_to(REPO).as_posix()])
    d57_sources = sources[:8]
    product_source_binding = {path: product_receipt["host_source_sha256"][path.removeprefix("src/")] == digest(snapshot[path]) for path in d57_sources if path.startswith("src/")}
    rust_receipt = json.loads(snapshot[(EVIDENCE / "rust-read/green-result.json").relative_to(REPO).as_posix()])
    product_source_binding["runtime/siro-runtime/src/linux.rs"] = rust_receipt["source_sha256"] == digest(snapshot["runtime/siro-runtime/src/linux.rs"])
    assert len(product_source_binding) == 8 and all(product_source_binding.values())
    product_package_differences = ["src/" + path for path, expected in product_receipt["host_source_sha256"].items() if digest((REPO / "src" / path).read_bytes()) != expected]
    assert product_package_differences == ["src/siro/services/tools/orchestrator.py"]
    assert product_receipt["host_source_sha256"]["siro/services/tools/orchestrator.py"] == digest(git_bytes("src/siro/services/tools/orchestrator.py"))

    product_script = ast.parse(snapshot[(EVIDENCE / "product/product-probe.py").relative_to(REPO).as_posix()].decode())
    for node in product_script.body:
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id in {"NOTES", "LATER", "CORRECTED"} for target in node.targets):
            name = next(target.id for target in node.targets if isinstance(target, ast.Name))
            proof(ast.literal_eval(node.value).encode(), {"verification": "exact_synthetic_fixture_content", "path": "product/product-probe.py", "constant": name})
    page = snapshot["src/siro/services/presentation/static/index.html"].decode()
    proof(page.split("<script>", 1)[1].split("</script>", 1)[0].encode(), {"verification": "exact_public_page_script", "path": "src/siro/services/presentation/static/index.html"})
    proof(page.replace("__SIRO_RENDERER_PATH__", "/live2d/").replace("__SIRO_RENDERER_STATUS__", "Live2D 載入中…").encode(), {"verification": "public_page_with_synthetic_renderer_route", "path": "src/siro/services/presentation/static/index.html"})

    fixture_identifiers: dict[str, list[dict[str, object]]] = {}
    for original, raw in snapshot.items():
        if "/rollback/" not in original:
            continue
        try:
            receipt = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            continue
        if not isinstance(receipt, dict) or not isinstance(receipt.get("database"), dict):
            continue
        facts = receipt["database"]
        task = facts.get("task_json")
        if not isinstance(task, dict):
            continue
        workspace = task.get("workspace")
        if isinstance(workspace, str) and re.fullmatch(r"/tmp/g57r-[a-z0-9_]+/synthetic-fixture/workspace", workspace):
            fixture_root = Path(workspace).parents[1]
            origins = receipt.get("loaded_origins", {})
            assert len(origins) == 3 and all(Path(value).is_relative_to(fixture_root / "public-source/src") for value in origins.values())
            assert task["owner_session_id"] == "synthetic-owner" and task["paths"] == ["checklist.md"]
            fixture_identifiers.setdefault(workspace, []).append({"verification": "exact_owned_synthetic_fixture_workspace", "receipt_path": original, "receipt_sha256": digest(raw), "json_pointer": "/database/task_json/workspace", "origin_paths_share_owned_fixture_root": True, "reproduction_script": "rollback/rollback-probe.py", "private_runtime_data_read": False})
        proof(json.dumps(task, separators=(",", ":"), ensure_ascii=False).encode(), {"verification": "exact_synthetic_task_metadata_content", "receipt_path": original, "json_pointer": "/database/task_json"})
    rollback_ast = ast.parse(snapshot[(EVIDENCE / "rollback/rollback-probe.py").relative_to(REPO).as_posix()].decode()) if (EVIDENCE / "rollback/rollback-probe.py").relative_to(REPO).as_posix() in snapshot else None
    if rollback_ast is not None:
        for node in ast.walk(rollback_ast):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "write_text" and node.args:
                try:
                    fixture_text = ast.literal_eval(node.args[0])
                except ValueError:
                    continue
                if isinstance(fixture_text, str) and fixture_text.startswith("# Synthetic rollback checklist\n"):
                    proof(fixture_text.encode(), {"verification": "exact_synthetic_fixture_content", "path": "rollback/rollback-probe.py", "fixture": "checklist.md"})

    # Reconstruct exactly the publicly retained synthetic account wrapper, never
    # execute it or start any process, and compare its digest to the child receipt.
    helper = ast.parse(git_bytes("tests/integration/test_release_source_process.py").decode())
    helper_function = next(node for node in helper.body if isinstance(node, ast.FunctionDef) and node.name == "source_bundle")
    write_expression = next(node.args[0] for node in ast.walk(helper_function) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "write_text")

    class PublicGatewayText:
        def read_text(self) -> str:
            return snapshot["src/siro/services/presentation/gateway.py"].decode()

    for version in ("D57-product-fixture",):
        wrapped = eval(compile(ast.Expression(write_expression), "<public-fixture-expression>", "eval"), {"__builtins__": {}}, {"gateway": PublicGatewayText(), "version": version})
        proof(wrapped.encode(), {"verification": "exact_public_source_plus_synthetic_account_wrapper", "path": "tests/integration/test_release_source_process.py", "fixture_version": version})

    # Binary identity is read only at the explicit D57 receipt's named public build.
    binary = REPO / "target/debug/siro-runtime"
    if binary.is_file():
        proof(binary.read_bytes(), {"verification": "exact_named_public_rust_build", "path": "target/debug/siro-runtime"})
    copied_linux = temporary / "source_docs/runtime/siro-runtime/src/linux.rs"
    reverse = subprocess.run(["git", "apply", "--reverse", str(EVIDENCE / "rust-read/production-repair.patch")], cwd=temporary / "source_docs", capture_output=True, timeout=30)
    if reverse.returncode == 0:
        proof(copied_linux.read_bytes(), {"verification": "exact_current_public_rust_with_retained_production_patch_reversed", "path": "rust-read/production-repair.patch"})
    # This mutation was only in the review-owned neutral copy, after scanning.

    classifications: list[dict[str, object]] = []
    for group, report in reports.items():
        for neutral, findings in report["results"].items():
            original = (EVIDENCE / neutral).relative_to(REPO).as_posix() if group == "evidence" else neutral
            raw = snapshot[original]
            try:
                json.loads(raw)
                parsed_strings = json_strings(raw.decode())
            except (ValueError, UnicodeDecodeError):
                parsed_strings = []
            for finding in findings:
                matches = [(pointer, value) for pointer, line, value in parsed_strings if line == finding["line_number"] and hashlib.sha1(value.encode()).hexdigest() == finding["hashed_secret"]]
                record = {"group": group, "path": original, "line_number": finding["line_number"], "type": finding["type"], "hashed_secret": finding["hashed_secret"], "input_sha256": digest(raw), "exact_json_value_matches": len(matches)}
                if len(matches) == 1 and finding["type"] == "Base64 High Entropy String" and matches[0][1] in fixture_identifiers:
                    record.update(json_pointer=matches[0][0], classification="SYNTHETIC_NONPRODUCTION_FIXTURE_IDENTIFIER", provenance=fixture_identifiers[matches[0][1]])
                elif len(matches) == 1 and finding["type"] == "Hex High Entropy String" and re.fullmatch(r"[a-f0-9]{40}|[a-f0-9]{64}", matches[0][1]):
                    pointer, value = matches[0]
                    record["json_pointer"] = pointer
                    if value == head and pointer in {"/baseline_commit", "/baseline_public_commit", "/public_parent", "/head"}:
                        record.update(classification="PUBLIC_SOURCE_CONTENT_SHA", provenance={"verification": "exact_public_parent_commit", "commit": head})
                    elif value in proofs:
                        record.update(classification="PUBLIC_SOURCE_CONTENT_SHA", provenance=proofs[value])
                    elif any(name in pointer for name in ("sha256", "source_before", "source_after", "source_scope", "source_hashes", "/records/")):
                        record.update(classification="PUBLIC_SOURCE_CONTENT_SHA", provenance={"verification": "individually_bound_historical_public_source_digest_receipt", "receipt_path": original, "receipt_sha256": digest(raw), "json_pointer": pointer, "underlying_historical_bytes_reconstructed": False, "basis": "Named SHA metadata of the inspected D57 public-source/synthetic process receipt; older candidate bytes are not independently recoverable here."})
                    else:
                        record.update(classification="UNRESOLVED_PUBLICATION_BLOCKER", provenance={"verification": "unproven_digest_field"})
                else:
                    line = raw.decode(errors="replace").splitlines()[finding["line_number"] - 1]
                    candidates = [value for value in re.findall(r"(?<![a-f0-9])(?:[a-f0-9]{64}|[a-f0-9]{40})(?![a-f0-9])", line) if hashlib.sha1(value.encode()).hexdigest() == finding["hashed_secret"]]
                    if len(candidates) == 1 and finding["type"] == "Hex High Entropy String" and (candidates[0] in proofs or candidates[0] == head):
                        record.update(classification="PUBLIC_SOURCE_CONTENT_SHA", provenance=proofs.get(candidates[0], [{"verification": "exact_public_parent_commit", "commit": head}]), textual_binding="exact_digest_token_on_scanner_line")
                    else:
                        record.update(classification="UNRESOLVED_PUBLICATION_BLOCKER", provenance={"verification": "finding_not_proven_to_be_public_sha_or_synthetic_fixture"})
                classifications.append(record)
    counts = dict(Counter(row["classification"] for row in classifications))
    historical = sum(isinstance(row.get("provenance"), dict) and row["provenance"].get("verification") == "individually_bound_historical_public_source_digest_receipt" for row in classifications)
    stable = {row["original"]: digest((REPO / str(row["original"])).read_bytes()) == row["sha256"] for row in manifest}
    preservation_working_after = {path: digest((REPO / path).read_bytes()) for path in preservation_working_before}
    preservation_source_guard = preservation_working_before == preservation_working_after
    assert preservation_source_guard
    save("finding-classifications.json", {"classification_policy": "Each actual scanner finding is bound to its original file/line, input SHA256, exact JSON value and detector fingerprint. Unknown fields or credentials block. This evidence audit does not alter the original CI gate or any scanner plugin/filter.", "counts": counts, "historical_digest_receipt_only_count": historical, "findings": classifications})
finally:
    shutil.rmtree(temporary)

state = {
    "snapshot_is_final": FINAL,
    "docs_acceptance": "FINAL_HASH_BOUND" if FINAL else "PENDING_FINAL_REBIND",
    "started_utc": started,
    "finished_utc": datetime.now(UTC).isoformat(),
    "public_parent": head,
    "source_count": len(sources),
    "tracked_docs_count": len(docs),
    "evidence_count": len(evidence_files),
    "private_main_tree_scanned": False,
    "old_untracked_scanned": False,
    "own_review_outputs_excluded": True,
    "own_review_output_exclusion_reason": "publication outputs describe this input snapshot; including their own manifest/receipt creates a recursive self-hash. Root final selection must bind these output files separately.",
    "actual_scanner_unchanged": True,
    "original_gate_unchanged": gate_hashes,
    "source_docs_original_gate_exit_code": gate.returncode,
    "neutral_root": str(temporary),
    "temporary_root_removed": not temporary.exists(),
    "all_scanner_children_joined": True,
    "input_manifest": manifest,
    "scans": scans,
    "all_inputs_still_match_snapshot": all(stable.values()),
    "inputs_changed_during_review": [path for path, matches in stable.items() if not matches],
    "old_python_test_helper_count": len(old_test_checks),
    "old_python_tests_all_byte_identical": all(old_test_checks.values()),
    "old_python_byte_identical_count": sum(old_test_checks.values()),
    "single_journal_exact_approved_transform": {"path": journal_path, "exact_transform": journal_exact_transform, "all_other_original_assertions_preserved": journal_exact_transform, "before_sha256": digest(journal_original), "after_sha256": digest(journal_current)},
    "old_migrations_count": len(old_migration_checks),
    "old_migrations_all_byte_identical": all(old_migration_checks.values()),
    "original_public_source_build_schema_count": len(source_record_checks),
    "original_public_source_preservation_manifest_rechecked": all(source_record_checks.values()),
    "old_public_source_changed_paths": old_source_changed,
    "old_public_source_unchanged": len(source_record_checks) - len(old_source_changed),
    "preservation_working_tree_source_before_after_guard": preservation_source_guard,
    "final_full_check_exact_15_source_binding": final_full_source_binding,
    "d57_eight_source_evidence_still_current": product_source_binding,
    "product_complete_package_predates_d58_differences": product_package_differences,
    "classification_counts": counts,
    "historical_digest_receipt_only_count": historical,
    "review_script_started_sha256": REVIEW_SCRIPT_STARTED_SHA256,
    "review_script_stable_during_execution": digest(Path(__file__).read_bytes()) == REVIEW_SCRIPT_STARTED_SHA256,
    "confirmed_true_secrets": 0,
    "unresolved_findings": counts.get("UNRESOLVED_PUBLICATION_BLOCKER", 0),
    "status": "PASS_PUBLIC_SYNTHETIC_SCOPE" if not counts.get("UNRESOLVED_PUBLICATION_BLOCKER") and gate.returncode == 0 and digest(Path(__file__).read_bytes()) == REVIEW_SCRIPT_STARTED_SHA256 and (not FINAL or all(stable.values())) else "BLOCKED_OR_UNSTABLE",
}
save("snapshot-manifest.json", state)
save("review-receipt.json", {
    "status": state["status"],
    "final_hash_rebound": FINAL,
    "source_hashes": {str(row["original"]): row["sha256"] for row in manifest if row["original"] in sources},
    "tracked_modified_document_hashes": {str(row["original"]): row["sha256"] for row in manifest if row["original"] in docs},
    "evidence_input_count": len(evidence_files),
    "scope_manifest_sha256": digest((OUT / "snapshot-manifest.json").read_bytes()),
    "raw_scanner_output_sha256": {name: digest((OUT / name).read_bytes()) for name in ("source-docs-scanner.json", "evidence-scanner.json")},
    "per_finding_classifications_sha256": digest((OUT / "finding-classifications.json").read_bytes()),
    "review_report_sha256": digest((OUT / "REPORT.md").read_bytes()),
    "review_script_sha256": REVIEW_SCRIPT_STARTED_SHA256,
    "review_script_stable_during_execution": digest(Path(__file__).read_bytes()) == REVIEW_SCRIPT_STARTED_SHA256,
    "source_docs_scanner_findings": scans[0]["findings"],
    "source_docs_original_gate_exit_code": gate.returncode,
    "classification_counts": counts,
    "historical_source_sha_receipt_only_count": historical,
    "true_secret_or_unresolved_publication_blocker_count": counts.get("UNRESOLVED_PUBLICATION_BLOCKER", 0),
    "architecture_read_review": {
        "status": "NO_CONFIRMED_SCOPED_BLOCKER",
        "core_ui_provider_os_cycle_introduced": False,
        "duplicate_planner_goal_database_memory_store_introduced": False,
        "model_or_document_autoapproval_path_found": False,
        "only_new_dispatch_capability": "filesystem.read",
        "approval_and_resume": "explicit existing-owner bearer + mutation Origin + closed payload + immutable scope + revision",
        "broader_argv_parent_alias_host_sandbox": "NOT_CERTIFIED",
        "general_autonomy_model_provider_quality_formal_release": "NOT_CERTIFIED",
        "details": "publication/REPORT.md",
    },
    "visually_reviewed_product_screenshots": {str(row["original"]): row["sha256"] for row in manifest if str(row["original"]).endswith(".jpg")},
    "product_reproduction_and_child_receipt_binding": {str(row["original"]): row["sha256"] for row in manifest if row["original"] in {str((EVIDENCE / path).relative_to(REPO)) for path in ("product/product-probe.py", "product/RESULTS.json", "product/preflight/RESULTS.json", "product/SUMMARY.md", "rollback/rollback-probe.py", "rollback/database-probe.py", "rollback/rollback-result.json")}},
    "product_renderer_account_content": "explicit public/synthetic fixture; no provider/TTS request or real-model/Live2D quality claim",
    "d57_eight_source_evidence_still_current": product_source_binding,
    "product_complete_package_predates_d58_differences": product_package_differences,
    "product_package_scope_limit": "The three-cycle product package predates only the separately tested D58 Orchestrator leaf. Eight D57 source identities remain current; this is not a final complete-package attestation.",
    "old_test_helper_and_migration_bytes": {"python_count": len(old_test_checks), "python_all_byte_identical": all(old_test_checks.values()), "python_byte_identical_count": sum(old_test_checks.values()), "only_changed_old_test": journal_path, "journal_exact_approved_transform": journal_exact_transform, "all_other_original_assertions_preserved": journal_exact_transform, "old_migration_count": len(old_migration_checks), "old_migrations_all_byte_identical": all(old_migration_checks.values())},
    "original_public_source_preservation": {"count": len(source_record_checks), "rechecked": all(source_record_checks.values()), "unchanged": len(source_record_checks) - len(old_source_changed), "changed": old_source_changed},
    "original_scanner_checker_allowances_broadened": False,
    "original_gate_hashes": gate_hashes,
    "private_live_or_other_untracked_data_scanned": False,
    "reviewer_production_test_tracked_public_document_or_commit_mutation": False,
    "reviewer_mutation_scope": "D57/publication evidence folder only",
    "scanner_gate_children_joined": True,
    "owned_neutral_root_removed": not temporary.exists(),
    "previous_interrupted_review_owned_neutral_root_removed": not Path("/tmp/siro-d57-pub-review-hzsplhry").exists(),
    "input_stability": {"all_inputs_match": all(stable.values()), "changed": [path for path, matches in stable.items() if not matches]},
    "preservation_source_guard": {"before": preservation_working_before, "after": preservation_working_after, "identical": preservation_source_guard},
    "final_full_check_binding": {"exact_15_source_binding": final_full_source_binding, "receipt_path": "regression/clean-check-final.json", "receipt_sha256": digest(snapshot[(EVIDENCE / "regression/clean-check-final.json").relative_to(REPO).as_posix()]), "status": final_full["status"], "exit_code": final_full["exit_code"], "elapsed_seconds": final_full["elapsed_seconds"]},
    "full_regression_rollback_and_remote_actions": "Root owns their actual final disposition; publication scan does not certify those gates.",
    "publication_output_hash_binding": "Root must bind these generated review outputs separately in the selected commit/package; recursive self-hashes are deliberately excluded.",
})
print(json.dumps({key: state[key] for key in ("status", "snapshot_is_final", "source_count", "tracked_docs_count", "evidence_count", "classification_counts", "historical_digest_receipt_only_count", "all_inputs_still_match_snapshot", "inputs_changed_during_review", "temporary_root_removed")}))

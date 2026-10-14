"""Reproduce the published pre-FIX-020 digest encoding with public tiny files."""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

BASELINE = "f3f94c12e690e80ccc945a0bea16b4e91054875e"


def main() -> None:
    repository = Path(__file__).resolve().parents[3]
    public_source = subprocess.check_output(
        ["git", "show", f"{BASELINE}:src/siro/core/releases.py"],
        cwd=repository,
        text=True,
    )
    module = ast.parse(public_source)
    release = next(
        item
        for item in module.body
        if isinstance(item, ast.ClassDef) and item.name == "ReleaseManager"
    )
    method = next(
        item
        for item in release.body
        if isinstance(item, ast.FunctionDef) and item.name == "_digest"
    )
    # Compile just the exact reviewed public pure method; no application module imports.
    historical = ast.ClassDef(
        name="HistoricalReleaseManager",
        bases=[],
        keywords=[],
        body=[method],
        decorator_list=[],
        type_params=[],
    )
    selected = ast.fix_missing_locations(ast.Module(body=[historical], type_ignores=[]))
    scope: dict[str, object] = {"hashlib": hashlib, "Path": Path}
    exec(compile(selected, "<public-baseline-digest-method>", "exec"), scope)
    manager = scope["HistoricalReleaseManager"]
    function = manager._digest
    with tempfile.TemporaryDirectory(prefix="siro-release-digest-review-") as folder:
        root = Path(folder)
        first, second = root / "first", root / "second"
        first.mkdir()
        second.mkdir()
        (first / "a").write_bytes(b"ALPHAb")
        (first / "b").write_bytes(b"BRAVO")
        (second / "a").write_bytes(b"ALPHA")
        (second / "b").write_bytes(b"bBRAVO")
        first_digest = function(first)
        second_digest = function(second)
        result = {
            "prototype_only": True,
            "baseline": BASELINE,
            "exact_public_baseline_method_replayed": True,
            "current_production_imports_or_modifications": False,
            "fixtures": {
                "first": {"a": "ALPHAb", "b": "BRAVO"},
                "second": {"a": "ALPHA", "b": "bBRAVO"},
            },
            "filenames_equal": sorted(path.name for path in first.iterdir())
            == sorted(path.name for path in second.iterdir()),
            "content_bytes_different": (first / "a").read_bytes() != (second / "a").read_bytes(),
            "digest_equal": first_digest == second_digest,
            "digest": first_digest,
            "explanation": "identical ambiguous serialized input, not a SHA-256 collision",
        }
    result["temporary_root_removed"] = not root.exists()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

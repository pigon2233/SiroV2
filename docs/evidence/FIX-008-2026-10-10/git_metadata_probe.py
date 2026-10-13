"""Read-only Git metadata evidence; no apply/check, production path or private inputs."""

import json
import subprocess
import tempfile
from pathlib import Path

CASES = {
    "rename_only_protected_source": "diff --git a/src/siro/core/authorization.py b/calc.py\n"
    "similarity index 100%\nrename from src/siro/core/authorization.py\nrename to calc.py\n",
    "timestamp_header": "--- a/src/siro/core/authorization.py\t2026-01-01 00:00:00 +0000\n"
    "+++ b/src/siro/core/authorization.py\t2026-01-01 00:00:00 +0000\n"
    "@@ -1 +1 @@\n-POLICY = 1\n+POLICY = 2\n",
    "dot_alias": "--- a/src/siro/core/./authorization.py\n"
    "+++ b/src/siro/core/./authorization.py\n@@ -1 +1 @@\n-POLICY = 1\n+POLICY = 2\n",
    "literal_headers_in_hunk": "--- a/docs/example.txt\n+++ b/docs/example.txt\n"
    "@@ -1 +1 @@\n--- a/src/siro/core/authorization.py\n+++ b/docs/other.txt\n",
    "conflicting_git_header": "diff --git a/src/siro/core/authorization.py "
    "b/src/siro/core/authorization.py\n--- a/calc.py\n+++ b/calc.py\n"
    "@@ -1 +1 @@\n-VALUE = 1\n+VALUE = 2\n",
}

if __name__ == "__main__":
    output = Path(__file__).resolve().parent
    rows = []
    with tempfile.TemporaryDirectory(prefix="siro-fix008-git-metadata-") as directory:
        for name, diff in CASES.items():
            result = subprocess.run(
                ["git", "apply", "--numstat", "-z", "-"],
                input=diff,
                cwd=directory,
                text=True,
                capture_output=True,
                check=False,
                timeout=3,
            )
            rows.append(
                {"case": name, "exit_code": result.returncode, "numstat": result.stdout.split("\0")}
            )
        assert not list(Path(directory).iterdir()), "metadata must not create files"
    record = {
        "git_version": subprocess.check_output(["git", "--version"], text=True).strip(),
        "numstat_only": True,
        "apply_or_check_run": False,
        "private_inputs": False,
        "temporary_cwd_removed": not Path(directory).exists(),
        "cases": rows,
    }
    (output / "git-metadata.json").write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps(record, indent=2))

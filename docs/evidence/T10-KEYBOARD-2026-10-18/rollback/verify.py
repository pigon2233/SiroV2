"""Check this checkout without changing it; rehearse only in a disposable directory."""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from pathlib import Path


def verify() -> None:
    package = Path(__file__).resolve().parent
    root = package.parents[3]
    manifest = json.loads((package / "manifest.json").read_text())
    relative = Path(manifest["source_path"])
    before = (package / "index.before.snapshot").read_bytes()
    after = (package / "index.after.snapshot").read_bytes()
    for checksum in (package / manifest["checksums_file"]).read_text().splitlines():
        expected, name = checksum.split(maxsplit=1)
        if hashlib.sha256((package / name).read_bytes()).hexdigest() != expected:
            raise RuntimeError("Snapshot checksum mismatch; no checkout changes made")
    if (root / relative).read_bytes() != after:
        raise RuntimeError("Checkout source has drifted; no checkout changes made")
    # A normal forward --check now means rollback, not reapplication of the feature.
    subprocess.run(
        ["git", "apply", "--check", str(package / "rollback.patch")], cwd=root, check=True
    )
    with tempfile.TemporaryDirectory(prefix="siro-detail-repro-rollback-") as directory:
        sandbox = Path(directory)
        source = sandbox / relative
        source.parent.mkdir(parents=True)
        source.write_bytes(after)
        retained = sandbox / "latest-data.txt"
        retained.write_text("synthetic newest data")
        subprocess.run(["git", "apply", str(package / "rollback.patch")], cwd=sandbox, check=True)
        if source.read_bytes() != before or retained.read_text() != "synthetic newest data":
            raise RuntimeError("Rollback did not preserve the supplied baseline")
        subprocess.run(["git", "apply", str(package / "reapply.patch")], cwd=sandbox, check=True)
        if source.read_bytes() != after or retained.read_text() != "synthetic newest data":
            raise RuntimeError("Reapply verification failed")
    if (root / relative).read_bytes() != after:
        raise RuntimeError("Checkout changed during verification")
    print("PASS: checkout rollback check; isolated rollback/reapply; checkout unchanged")


if __name__ == "__main__":
    verify()

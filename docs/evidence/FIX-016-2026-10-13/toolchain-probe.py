"""Self-owned cold rustup bootstrap; never changes the user's toolchain home."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
RUSTUP = Path("/home/jasonliao/.cargo/bin/rustup")
CARGO = Path("/home/jasonliao/.cargo/bin/cargo")
PIN = "1.97.1"


def main() -> None:
    tracked = ["rust-toolchain.toml", ".python-version", "Cargo.lock", "uv.lock"]
    baseline = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in tracked}
    steps: list[dict[str, object]] = []
    result: dict[str, object] = {
        "mode": "actual official downloads / isolated homes / no production source mutation",
        "rust_version": PIN,
        "profile": "minimal",
        "steps": steps,
        "baseline": baseline,
    }
    probe_root: Path | None = None
    try:
        with tempfile.TemporaryDirectory(prefix="siro-fix016-rustup-") as raw:
            probe_root = Path(raw)
            project = probe_root / "project"
            project.mkdir()
            env = os.environ.copy()
            env["RUSTUP_HOME"] = str(probe_root / "rustup")
            env["CARGO_HOME"] = str(probe_root / "cargo")
            env["RUSTUP_DIST_SERVER"] = "https://static.rust-lang.org"
            env["RUSTUP_UPDATE_ROOT"] = "https://static.rust-lang.org/rustup"
            env.pop("RUSTUP_TOOLCHAIN", None)
            manifest = project / "rust-toolchain.toml"
            manifest.write_text(
                f'[toolchain]\nchannel = "{PIN}"\nprofile = "minimal"\n',
                encoding="utf-8",
            )

            def run(name: str, arguments: list[str], expected: int | None = None) -> str:
                completed = subprocess.run(
                    arguments,
                    cwd=project,
                    env=env,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    timeout=600,
                    check=False,
                )
                steps.append(
                    {
                        "name": name,
                        "arguments": arguments,
                        "returncode": completed.returncode,
                        "output": completed.stdout,
                    }
                )
                print(name, "exit", completed.returncode, flush=True)
                if expected is not None and completed.returncode != expected:
                    raise AssertionError(f"{name}: exit {completed.returncode}, expected {expected}")
                return completed.stdout

            run(
                "cold-minimal-install",
                [str(RUSTUP), "toolchain", "install", PIN, "--profile", "minimal", "--no-self-update"],
                0,
            )
            before = run(
                "before-installed-components",
                [str(RUSTUP), "component", "list", "--installed", "--toolchain", PIN],
                0,
            )
            assert "rustfmt" not in before and "clippy" not in before
            fmt_before = run("before-cargo-fmt", [str(CARGO), "fmt", "--version"], 1)
            clippy_before = run("before-cargo-clippy", [str(CARGO), "clippy", "--version"], 1)
            assert "cargo-fmt" in fmt_before and "not installed" in fmt_before
            assert "cargo-clippy" in clippy_before and "not installed" in clippy_before

            manifest.write_text(
                f'[toolchain]\nchannel = "{PIN}"\nprofile = "minimal"\n'
                'components = ["rustfmt", "clippy"]\n',
                encoding="utf-8",
            )
            run("after-manifest-auto-provision", [str(CARGO), "fmt", "--version"], 0)
            run("after-cargo-clippy", [str(CARGO), "clippy", "--version"], 0)
            after = run(
                "after-installed-components",
                [str(RUSTUP), "component", "list", "--installed", "--toolchain", PIN],
                0,
            )
            assert "rustfmt" in after and "clippy" in after
            result["status"] = "PASS"
    except BaseException as error:
        result["status"] = "FAIL"
        result["error_type"] = type(error).__name__
        raise
    finally:
        result["temporary_root_removed"] = probe_root is not None and not probe_root.exists()
        result["ending"] = {
            p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in tracked
        }
        result["note"] = (
            "Parent may concurrently repair repo manifest; this probe writes only its temporary manifest."
        )
        (EVIDENCE / "toolchain-probe.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()

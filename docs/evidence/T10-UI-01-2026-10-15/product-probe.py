"""Owned actual-main/Rust/HTTP UI acceptance fixture; no live profile is read.

This entry point starts no process when imported or invoked with --check-only.
Browser actions remain real interactions against the served root application.
The reused D57 helper only substitutes the synthetic account locator and records
the copied source origins; it does not mock the API, persistence or Rust reads.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
ORIGINAL = ROOT / "docs/evidence/T19-goal-loop-2026-10-14/product/product-probe.py"


def load_fixture():
    spec = importlib.util.spec_from_file_location("ui_acceptance_d57_probe", ORIGINAL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # The old fixture is reused read-only. All new logs and receipts stay here.
    module.OUT = OUT
    return module


def check_only() -> None:
    from playwright.sync_api import sync_playwright

    assert ORIGINAL.is_file()
    assert (ROOT / ".venv/bin/python").is_file()
    assert (ROOT / "target/debug/siro-runtime").is_file()
    with sync_playwright() as browser:
        bundled = Path(browser.chromium.executable_path)
        chromium = bundled if bundled.is_file() else Path("/opt/google/chrome/chrome")
        assert chromium.is_file()
    print(
        json.dumps(
            {
                "prepared": True,
                "started_server": False,
                "fixture": str(ORIGINAL.relative_to(ROOT)),
                "python_version": sys.version,
                "playwright_default_chromium_present": bundled.is_file(),
                "browser_executable": str(chromium),
                "browser_launch": "NOT_RUN",
                "renderer": "synthetic placeholder; actual Live2D NOT_TESTED",
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


def main() -> None:
    if sys.argv[1:] == ["--check-only"]:
        check_only()
        return
    assert not sys.argv[1:], "Only --check-only is accepted; live ports are never accepted."
    fixture = load_fixture()
    probe = fixture.Probe()
    # Preserve the existing helper's explicit SIRO isolation and strip all other
    # named credential-like variables before spawning a child. Values are neither
    # printed nor persisted. This fixture never sends chat/provider/TTS requests.
    probe.env = {
        key: value
        for key, value in probe.env.items()
        if key == "SIRO_CONTEXT_TOKEN_BUDGET_ENABLED"
        or not any(
            marker in key.upper()
            for marker in ("API_KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")
        )
    }
    probe.receipt.update(
        {
            "task": "T10-UI-01",
            "scope": "actual default candidate main; copied current UI; synthetic account/renderer",
            "reproduction_script_sha256": fixture.sha(Path(__file__).read_bytes()),
            "reused_fixture_sha256": fixture.sha(ORIGINAL.read_bytes()),
            "browser_acceptance": "NOT_RUN; root browser actions must be recorded separately",
            "actual_live2d": "NOT_TESTED; explicit prepared-renderer placeholder",
            "native_desktop": "NOT_TESTED",
            "navigation_checkpoints": [],
        }
    )
    closed = False
    try:
        probe.start()
        for line in sys.stdin:
            command = json.loads(line)
            action = command["command"]
            # Observations may occur after a long manual UI step; renew only this
            # fixture client's short-lived session before its explicit readback.
            probe.token = None
            if action == "restart":
                probe.stop()
                probe.start()
            elif action == "checkpoint":
                fixture.announce(probe.checkpoint(command["name"]))
            elif action == "snapshot":
                fixture.announce({"snapshot": probe.snapshot(), "runtime_reads": probe.reads()})
            elif action == "navigation":
                # No mutation is performed by this observation. The caller
                # compares before/after snapshots around real browser actions.
                snapshot = probe.snapshot()
                reads = probe.reads()
                if "expected_reads" in command:
                    assert reads == command["expected_reads"]
                value = {
                    "label": command["label"],
                    "cycle": probe.cycle,
                    "observed_utc": datetime.now(UTC).isoformat(),
                    "snapshot": snapshot,
                    "runtime_reads": reads,
                }
                probe.receipt["navigation_checkpoints"].append(value)
                probe.save()
                fixture.announce(value)
            elif action == "correction":
                fixture.announce(probe.correction())
            elif action == "finish":
                probe.close()
                closed = True
                fixture.announce(
                    {
                        "finished": True,
                        "temporary_removed": probe.receipt["temporary_removed"],
                        "cycles": probe.cycle,
                        "browser_acceptance": probe.receipt["browser_acceptance"],
                        "actual_live2d": probe.receipt["actual_live2d"],
                    }
                )
                return
            else:
                raise ValueError("unknown command")
    finally:
        if not closed:
            probe.close()


if __name__ == "__main__":
    main()

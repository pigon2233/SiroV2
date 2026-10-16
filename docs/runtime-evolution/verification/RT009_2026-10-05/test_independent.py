"""Independent verification; intentionally outside default test discovery."""
import importlib.util
import sqlite3
from pathlib import Path



def test_main_preserves_selected_backend_in_durable_journal(tmp_path, monkeypatch):
    fixture = Path(__file__).resolve().parents[4] / "tests/integration/test_provider_retry.py"
    spec = importlib.util.spec_from_file_location("rt009_fixture", fixture)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Actual main/Core/SQLite/ASGI, synthetic cloud failure with no effects.
    module.test_real_main_provider_policy_and_dispatch_gate(
        tmp_path, monkeypatch, "candidate", "cloud_fail", False, 1, False, "failed"
    )
    with sqlite3.connect(tmp_path / "siro.db") as connection:
        recorded = connection.execute("SELECT backend FROM run_journal").fetchall()
    assert recorded == [("synthetic-cloud",)], recorded

"""Fail visibly unless the actual eight-case final signal evidence is complete."""

from __future__ import annotations

import json
from pathlib import Path

result = json.loads(Path(__file__).with_name("signal-final.json").read_text())
cases = result["cases"]
assert len(cases) == 8
assert result["source_unchanged_during_probe"]
required_true = (
    "child_alive_while_io_pending",
    "owned_sync_backup_call_pending",
    "source_busy_while_io_pending",
    "destination_busy_while_io_pending",
    "child_joined",
    "original_sigint_handler_restored_after_command",
    "actual_snapshot_io_finished",
    "settings_retained",
    "fixed_temporary_retained",
    "source_value_retained",
    "all_keys_available_after_join",
    "next_owner_output_retained",
    "owned_child_joined_in_finally",
    "synthetic_root_removed",
)
for case in cases:
    assert all(case.get(key) is True for key in required_true), case
    assert case["child_exit"] == 130, case
    assert not case["child_stderr_present"], case
    assert not case["runner_close_started_while_backup_pending"], case
    assert case["consumed_async_wait_cancellations_while_backup_pending"] == case["signals"], case
    assert case["staging_entries_after_join"] == [], case
    assert "probe_error" not in case, case
    assert "forced_fixture_cleanup" not in case, case
    if case["bundle"]:
        assert case["fixed_temporary_busy_while_io_pending"], case
        assert case["previous_final_archive_retained"], case
        assert not case["snapshot_exists_after_join"], case
    else:
        assert case["raw_output_replaced"] is case["cancel_after_actual_raw_commit"], case
    if case["cancel_after_actual_raw_commit"]:
        assert case["raw_committed_value"] == "source-snapshot", case
        assert case["explicit_connection_close_calls"] == 2, case
    if case["cancel_during_actual_sqlite_progress"]:
        assert case["explicit_connection_close_calls"] == 2, case
        assert case["actual_non_done_progress"]["remaining"] > 0, case
        assert case["owned_scratch_present_before_cancellation"], case

print(
    "PASS: 8 actual mapped cases; stable public source; all sources/outputs/leases/staging/"
    "cancellation/SIGINT-handler/stdio/next-owner/child/root invariants"
)

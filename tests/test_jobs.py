from datetime import UTC, datetime, timedelta

import pytest

from siro.core.jobs import JobLeases


def test_t37_epoch_fences_late_results_and_bounds_input() -> None:
    now = datetime(2026, 9, 26, 16, tzinfo=UTC)
    jobs = JobLeases(max_input_bytes=4)
    with pytest.raises(ValueError, match="input"):
        jobs.submit(b"large", "node-a", now=now)
    first = jobs.submit(b"ok", "node-a", now=now, lease_seconds=1)
    with pytest.raises(ValueError, match="not expired"):
        jobs.retry(first.job_id, "node-b", now=now)
    second = jobs.retry(first.job_id, "node-b", now=now + timedelta(seconds=1), lease_seconds=30)
    assert second.epoch == 2
    assert not jobs.accept_result(first, now=now + timedelta(seconds=1))
    assert jobs.accept_result(second, now=now + timedelta(seconds=2))
    assert not jobs.accept_result(second, now=now + timedelta(seconds=2))
    cancelled = jobs.submit(b"ok", "node-a", now=now)
    assert jobs.cancel(cancelled.job_id)
    assert not jobs.accept_result(cancelled, now=now)

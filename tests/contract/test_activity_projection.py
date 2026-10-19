"""CP-P02: redaction and state rules of the activity projection (no browser needed)."""

from __future__ import annotations

import pytest

from siro.services.activity.monitor import describe_tool, redact_url, run_state, tool_state


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://example.test/a/b", {"url": "https://example.test/a/b"}),
        (
            "https://example.test:8443/p?token=S1#frag",
            {"url": "https://example.test:8443/p", "redacted": True},
        ),
        (
            "http://user:S2@example.test/",  # pragma: allowlist secret
            {"url": "http://example.test/", "redacted": True},
        ),
        ("file:///home/owner/S3.txt", {"url": "file:", "redacted": True}),
        ("javascript:alert('S4')", {"url": "javascript:", "redacted": True}),
        ("http://[::1", {"url": None, "invalid": True}),
        ("", None),
        (None, None),
    ],
)
def test_urls_lose_queries_credentials_and_non_web_detail(raw: object, expected: object) -> None:
    assert redact_url(raw) == expected


def test_typed_values_and_page_text_never_reach_the_view() -> None:
    view = describe_tool(
        "browser.fill",
        {"role": "textbox", "name": "Password", "value": "S5", "screen_version": "v"},
        {"url": "https://example.test/login?next=S6", "title": "t", "text": "S7"},
    )
    assert view["target"] == {"url": "https://example.test/login", "redacted": True}
    assert not {"S5", "S6", "S7"} & set(str(view).split("'"))
    assert view["network"]["coverage"] == "browser_adapter"  # type: ignore[index]


def test_shell_reports_program_only_and_unobserved_network() -> None:
    view = describe_tool("computer.execute", {"argv": ["./bin/tool", "--key", "S8"]}, None)
    assert view["target"] == {"program": "tool", "argument_count": 2}
    assert view["network"] == {
        "coverage": "unobserved",
        "requests": [],
        "gaps": ["subprocess_network_not_monitored"],
    }
    assert describe_tool("unknown.tool", {"x": "S9"}, None)["target"] is None


@pytest.mark.parametrize(
    ("raw", "error", "dispatched", "expected"),
    [
        ("pending", None, None, "proposed"),
        ("approved", None, None, "queued"),
        ("running", None, 1, "running"),
        ("completed", None, 1, "completed"),
        ("denied", None, None, "cancelled"),
        ("failed", "ExecutionCancelled", 0, "cancelled"),
        ("failed", "ExecutionCancelled", 1, "unknown"),
        ("failed", "ExecutionCancelled", None, "unknown"),
        ("failed", "interrupted_restart", 1, "unknown"),
        ("failed", "TimeoutError", 1, "failed"),
        ("mystery", None, None, "unknown"),
    ],
)
def test_cancellation_is_only_clean_without_a_dispatch(
    raw: str, error: object, dispatched: object, expected: str
) -> None:
    assert tool_state(raw, error, dispatched) == expected


def test_run_states() -> None:
    assert run_state("waiting_tool", None) == "running"
    assert run_state("failed", "outcome_unknown") == "unknown"
    assert run_state("failed", "interrupted_restart") == "failed"
    assert run_state("cancelled", None) == "cancelled"
    assert run_state("weird", None) == "unknown"

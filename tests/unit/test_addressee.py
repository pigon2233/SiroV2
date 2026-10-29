import asyncio

import pytest

from siro.services.agent.addressee import (
    Audience,
    Context,
    addressee_enabled,
    judge,
    looks_lasting,
    parse_audience,
)


def run(text, context=None, classifier=None):
    return asyncio.run(judge(text, context or Context(), classifier))


def test_name_mention_is_addressed():
    verdict = run("西羅今天天氣怎麼樣")
    assert verdict.addressed and verdict.reason == "name"


def test_follow_up_window_is_addressed():
    verdict = run("那明天呢", Context(seconds_since_spoke=5))
    assert verdict.addressed and verdict.reason == "window"


def test_filler_is_dropped_even_in_window():
    assert run("嗯", Context(seconds_since_spoke=1)).audience is Audience.DROP


def test_classifier_decides_ambiguous_text():
    async def friend(_text, _recent):
        return Audience.DROP

    verdict = run("你昨天那個報告交了嗎", Context(seconds_since_spoke=300), friend)
    assert verdict.audience is Audience.DROP and verdict.reason == "classifier"


def test_classifier_failure_stays_quiet_outside_window():
    async def broken(_text, _recent):
        raise RuntimeError("down")

    verdict = run("幫我開燈", Context(seconds_since_spoke=300), broken)
    assert not verdict.addressed and not verdict.confident


def test_fallback_keeps_lasting_statements_only():
    assert run("我每天晚上十一點睡覺").audience is Audience.KEEP
    assert run("今天午餐吃什麼好呢").audience is Audience.DROP
    assert looks_lasting("我通常早上喝咖啡")
    assert not looks_lasting("我通常")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("SIRO", Audience.SIRO), (" keep.", Audience.KEEP), ("「DROP」", Audience.DROP), ("好", None)],
)
def test_parse_audience(raw, expected):
    assert parse_audience(raw) is expected


def test_flag_defaults_on():
    assert addressee_enabled({})
    assert not addressee_enabled({"SIRO_ADDRESSEE_ENABLED": "0"})

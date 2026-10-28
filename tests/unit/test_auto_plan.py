import asyncio

import pytest

from siro.services.agent.auto_plan import auto_plan_enabled, looks_multistep, should_plan
from siro.services.agent.planning_adapters import planner_enabled
from siro.services.agent.resume import resume_enabled


def test_multistep_requests_are_planned() -> None:
    assert looks_multistep("先幫我搜尋三家雲端供應商的價格，然後比較差異，最後整理成表格")
    assert looks_multistep("First search the docs, then compare the two options and summarize")


def test_ordinary_chat_is_not_planned() -> None:
    assert not looks_multistep("你好，今天過得怎麼樣？")
    assert not looks_multistep("先吃飯然後睡覺好不好呢今天晚上真的很晚了耶")
    assert not looks_multistep("/plan 先查再整理然後寫成一份報告給我看看吧")
    assert not looks_multistep("")


def test_kill_switch_and_profile_defaults() -> None:
    assert auto_plan_enabled({}, default="1") is True
    assert auto_plan_enabled({}) is False
    assert auto_plan_enabled({"SIRO_AUTO_PLAN_ENABLED": "0"}, default="1") is False


def test_planner_and_resume_default_on_for_candidate_only() -> None:
    assert planner_enabled({}, default="1") is True
    assert resume_enabled({}, default="1") is True
    assert planner_enabled({}) is False
    assert resume_enabled({}) is False
    assert planner_enabled({"SIRO_AGENT_PLANNER_ENABLED": "0"}, default="1") is False
    assert resume_enabled({"SIRO_AGENT_RESUME_ENABLED": "0"}, default="1") is False


async def _yes(_t: str) -> bool:
    return True


async def _no(_t: str) -> bool:
    return False


async def _boom(_t: str) -> bool:
    raise RuntimeError("luna down")


async def _slow(_t: str) -> bool:
    await asyncio.sleep(5)
    return True


MULTI = "先幫我搜尋三家雲端供應商的價格，然後比較差異，最後整理成表格"
PLAIN = "今天天氣真的很好呢你覺得呢"


@pytest.mark.asyncio
async def test_luna_decides_when_available() -> None:
    assert await should_plan(PLAIN, _yes) is True
    assert await should_plan(MULTI, _no) is False


@pytest.mark.asyncio
async def test_error_and_timeout_fall_back_to_heuristic() -> None:
    assert await should_plan(MULTI, _boom) is True
    assert await should_plan(PLAIN, _boom) is False
    assert await should_plan(MULTI, _slow, timeout=0.05) is True
    assert await should_plan(PLAIN, _slow, timeout=0.05) is False
    assert await should_plan(MULTI, None) is True


@pytest.mark.asyncio
async def test_prefilter_skips_classifier() -> None:
    assert await should_plan("你好", _yes) is False
    assert await should_plan("/plan 查一下很多很多東西好嗎", _yes) is False

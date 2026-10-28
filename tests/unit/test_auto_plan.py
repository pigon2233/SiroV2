from siro.services.agent.auto_plan import auto_plan_enabled, looks_multistep
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

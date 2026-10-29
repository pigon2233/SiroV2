# ruff: noqa: RUF001
"""D80 D3: the skill phrase opens a chat card locally and never becomes a model turn."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

INDEX = Path(__file__).parents[2] / "src/siro/services/presentation/static/index.html"


def test_skill_phrase_is_recognised_and_ordinary_chat_is_not() -> None:
    html = INDEX.read_text(encoding="utf-8")
    pattern = re.search(r"const SKILL_REQUEST = (/.*/);", html)
    assert pattern
    script = f"""
const re = {pattern.group(1)};
const yes = ["學習待辦清單技能", "技能", "管理技能", "學習技能"];
const no = ["幫我整理待辦清單", "你有什麼技能嗎？", "學習待辦清單技能好嗎", "技能是什麼"];
console.log(JSON.stringify({{yes: yes.map(t => re.test(t)), no: no.map(t => re.test(t))}}));
"""
    result = json.loads(
        subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True).stdout
    )
    assert all(result["yes"]) and not any(result["no"])


def test_card_opens_before_any_submission_and_each_step_is_a_button() -> None:
    html = INDEX.read_text(encoding="utf-8")
    submit = html[html.index('document.querySelector("#chat").onsubmit') :]
    submit = submit[: submit.index("};")]
    assert submit.index("renderSkillCard(); return;") < submit.index("submitText(value)")
    start = html.index("function renderSkillCard()")
    card = html[start : html.index("function renderToolProposal(")]
    for label in ("準備並測試", "安裝（保持停用）", "啟用", "撤銷啟用", "撤銷安裝"):
        assert f'step("{label}"' in card
    # Install only ever sends the reviewed id and hash; nothing is installed or enabled implicitly.
    assert "review_id: review.review_id, package_hash: review.package_hash" in card

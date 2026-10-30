from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_path = Path(__file__).parents[2] / "scripts" / "verify_undertale_screen_cue.py"
_spec = importlib.util.spec_from_file_location("undertale_fast_cue", _path)
assert _spec and _spec.loader
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)


@pytest.mark.parametrize(
    ("heading", "instruction", "expected"),
    [
        ("UNDERTALE", "[PRESS Z OR ENTER]", True),
        ("Undertale", "Press Z or Enter", True),
        ("TORIEL", "PRESS Z OR ENTER", False),
        ("UNDERTALE", "PRESS Z OR ENTER TO RESET", False),
        ("UNDERTALE", "PRESS Z OR ENTER TO CONTINUE", False),
        ("UNDERTALE", "", False),
        ("", "PRESS Z OR ENTER", False),
    ],
)
def test_title_prompt_requires_both_exact_lines(
    heading: str, instruction: str, expected: bool
) -> None:
    assert _module.is_title_prompt(heading, instruction) is expected


def test_middle_overlay_blocks_title_trigger() -> None:
    assert not _module.is_title_prompt("UNDERTALE", "PRESS Z OR ENTER", "SAVE")

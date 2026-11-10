"""Motion cues stay out of chat and speech, and map onto the body channel."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from siro.adapters.body.web import MinimalWebBodyAdapter
from siro.adapters.models.mock import MockModel
from siro.core.companion import CompanionCore
from siro.core.conversation import ConversationEngine, TurnState
from siro.core.identity import IdentityService, IdentityState, ImmutableCore
from siro.core.memory import MemoryService, assemble_prompt
from siro.core.motion_cues import (
    MotionCue,
    MotionStream,
    body_message,
    fallback_cues,
    motion_cues_enabled,
    motion_prompt,
    research_capability,
)
from siro.persistence.conversation import SQLiteConversationRepository
from siro.persistence.memory import SQLiteMemoryRepository
from siro.persistence.sqlite import SQLiteStore
from siro.persistence.state import SQLiteIdentityRepository
from siro.ports.body import EmotionIntent, GestureIntent, LookIntent, SpeechIntent


def test_flag_off_leaves_tags_and_skips_the_prompt() -> None:
    assert motion_cues_enabled({"SIRO_MOTION_CUES": "0"}) is False
    assert motion_cues_enabled({}) is True
    assert motion_cues_enabled({"SIRO_MOTION_CUES": "1"}) is True
    assert motion_prompt(False) == ""
    assert "[[g:wave]]" in motion_prompt(True)
    now = datetime.now(UTC)
    state = IdentityState(
        identity_id="siro",
        core=ImmutableCore(
            name="SIRO",
            baseline_identity="persistent companion",
            core_values=("honesty",),
            creator_relationship="owner",
        ),
        created_at=now,
        updated_at=now,
    )
    plain = assemble_prompt(state, "你好", ())
    cued = assemble_prompt(state, "你好", (), motion_cues=True)
    assert "Motion cues, never spoken" not in plain
    assert "Motion cues, never spoken" in cued
    assert "[[g:wave]]" not in plain


def test_stream_strips_split_tags_and_maps_cues() -> None:
    stream = MotionStream()
    assert stream.push("早啊[[g:") == "早啊"
    assert stream.push("wave:0.9]]，看這裡[[l:left]]。") == "，看這裡。"  # noqa: RUF001
    assert stream.finish() == ""
    assert "[[" not in stream.spoken
    assert stream.spoken == "早啊，看這裡。"  # noqa: RUF001
    kinds = [(cue.kind, cue.name, cue.intensity) for cue in stream.cues]
    assert ("gesture", "wave", 0.9) in kinds
    assert any(cue.kind == "look" and cue.name == "left" and cue.x < 0 for cue in stream.cues)
    messages = [body_message(cue) for cue in stream.cues]
    assert messages[0] == {"v": 1, "type": "body.gesture", "name": "wave", "intensity": 0.9}
    look = next(item for item in messages if item["type"] == "body.look")
    assert look["x"] == -0.8


def test_unknown_tag_is_removed_and_does_not_become_a_command() -> None:
    stream = MotionStream()
    assert stream.push("好[[g:explode]][[note]]") == "好[[note]]"
    stream.finish()
    assert stream.cues == ()
    assert "explode" not in stream.spoken


def test_unclosed_tag_never_reaches_the_spoken_text() -> None:
    stream = MotionStream()
    assert stream.push("到這裡[[e:happy:0.4") == "到這裡"
    assert stream.finish() == ""
    assert stream.spoken == "到這裡"
    assert stream.cues == ()


def test_fallback_matches_the_renderer_patterns_when_there_is_no_tag() -> None:
    assert fallback_cues("你好，今天也好。")[0].name == "wave"  # noqa: RUF001
    assert fallback_cues("謝謝你。")[0].name == "bow"
    assert fallback_cues("不是這樣。")[0].name == "shake"
    point = fallback_cues("你看左邊。")
    assert [cue.name for cue in point] == ["point", "left"]
    assert research_capability("browser.navigate+read")
    assert research_capability("claude.ask")
    assert not research_capability("computer.execute")


def test_inline_tag_suppresses_the_word_fallback() -> None:
    stream = MotionStream()
    stream.push("你好[[e:sad:0.4]]")
    stream.finish()
    assert [cue.kind for cue in stream.cues] == ["emotion"]
    assert stream.cues[0].intensity == 0.4
    assert body_message(stream.cues[0])["type"] == "body.emotion"


class _Transport:
    def __init__(self, connected: bool = True) -> None:
        self.connected = connected
        self.messages: list[dict[str, object]] = []

    async def send(self, message: dict[str, object]) -> None:
        self.messages.append(message)


@pytest.mark.asyncio
async def test_body_adapter_sends_gesture_look_and_server_motion() -> None:
    transport = _Transport()
    body = MinimalWebBodyAdapter(transport)
    assert await body.gesture(GestureIntent("point", 0.4))
    assert await body.look(LookIntent(-0.8, 0.1))
    assert await body.speak(SpeechIntent("s", "你好", "g", motion="server"))
    assert await body.set_emotion(EmotionIntent("happy", 0.55))
    assert [item["type"] for item in transport.messages] == [
        "body.gesture",
        "body.look",
        "body.speech",
        "body.emotion",
    ]
    assert transport.messages[0]["intensity"] == 0.4
    assert transport.messages[2]["motion"] == "server"
    assert transport.messages[2]["text"] == "你好"
    offline = MinimalWebBodyAdapter(_Transport(False))
    assert not await offline.gesture(GestureIntent("nod"))
    assert not await offline.look(LookIntent(0, 0))


async def _core(tmp_path: Path, chunks: tuple[str, ...]) -> tuple[SQLiteStore, CompanionCore]:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    identities = SQLiteIdentityRepository(store)
    await IdentityService(identities).create(
        "siro",
        ImmutableCore(
            name="SIRO",
            baseline_identity="persistent companion",
            core_values=("honesty",),
            creator_relationship="owner",
        ),
        now=datetime.now(UTC),
    )
    core = CompanionCore(
        identities,
        MemoryService(SQLiteMemoryRepository(store)),
        ConversationEngine(MockModel(chunks), SQLiteConversationRepository(store)),
    )
    return store, core


@pytest.mark.asyncio
async def test_reply_tags_do_not_reach_chat_memory_or_stored_turns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SIRO_MOTION_CUES", "1")
    store, core = await _core(
        tmp_path,
        (
            "今天[[g:",
            "nod]]很好。",
        ),
    )
    shown: list[str] = []
    heard: list[str] = []

    async def on_delta(text: str) -> None:
        shown.append(text)

    async def on_motion(cue: MotionCue) -> None:
        heard.append(str(body_message(cue)["name"]))

    result = await core.respond("session", "siro", "你好", on_delta=on_delta, on_motion=on_motion)
    assert result.state is TurnState.COMPLETED
    assert result.text == "今天很好。"
    assert "[[" not in "".join(shown)
    assert "".join(shown) == "今天很好。"
    assert "nod" in heard
    remembered = core._working.recent("session")
    assert remembered[-1].text == "今天很好。"
    rows = await store.run_transaction(
        lambda connection: connection.execute(
            "SELECT text FROM messages WHERE role = 'assistant'"
        ).fetchall()
    )
    assert [row[0] for row in rows] == ["今天很好。"]


@pytest.mark.asyncio
async def test_flag_off_keeps_the_model_text_and_emits_no_cue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SIRO_MOTION_CUES", "0")
    _store, core = await _core(tmp_path, ("你好[[g:wave]]",))
    cues: list[MotionCue] = []

    async def on_motion(cue: MotionCue) -> None:
        cues.append(cue)

    result = await core.respond("session", "siro", "嗨", on_motion=on_motion)
    assert result.text == "你好[[g:wave]]"
    assert cues == []

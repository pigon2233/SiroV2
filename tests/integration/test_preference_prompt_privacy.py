"""Private historical preferences stay local when the companion uses a cloud route."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
from siro.contracts.events import Priority, UserTextEvent, UserTextPayload
from siro.contracts.events import Privacy as EventPrivacy
from siro.persistence.affect import Preference, SQLiteAffectRepository
from siro.persistence.sqlite import SQLiteStore
from siro.ports.models import CancellationToken, ModelChunk, ModelRequest, Privacy
from siro.services.presentation.gateway import GatewayHub
from siro.services.presentation.integrated import IntegratedCompanion


class RecordingModel:
    name = "synthetic-preference-privacy"

    def __init__(self) -> None:
        self.requests: list[ModelRequest] = []

    async def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        assert not cancellation.cancelled
        self.requests.append(request)
        yield ModelChunk("text", "合成驗收回覆。")
        yield ModelChunk("finished")


class RecordingHub(GatewayHub):
    def __init__(self) -> None:
        super().__init__()
        self.messages: list[dict[str, object]] = []

    async def broadcast(self, message: dict[str, object], *, urgent: bool = False) -> None:
        self.messages.append(message)
        await super().broadcast(message, urgent=urgent)


def companion(
    path: Path, model: RecordingModel, privacy: Privacy, hub: GatewayHub | None = None
) -> IntegratedCompanion:
    return IntegratedCompanion(
        path,
        model,
        hub or GatewayHub(),
        MinimalWebBodyAdapter(WebSocketBodyTransport()),
        privacy=privacy,
        runtime_profile="candidate",
        session_restore_enabled=False,
    )


def preference(person: str, subject: str, source_ids: tuple[str, ...]) -> Preference:
    return Preference(
        str(uuid4()),
        "siro",
        person,
        person,
        subject,
        1.0,
        0.8,
        1.0,
        "general",
        "committed",
        source_ids,
        1,
    )


@pytest.mark.asyncio
async def test_local_preferences_stay_out_of_cloud_prompt_and_native_messages(
    tmp_path: Path,
) -> None:
    local = companion(tmp_path, RecordingModel(), Privacy.LOCAL_ONLY)
    private_owner = "SYNTHETIC_PRIVATE_OWNER_PREFERENCE"
    await local.respond("local-source", f"我喜歡{private_owner}")

    store = SQLiteStore(tmp_path / "siro.db")
    repository = SQLiteAffectRepository(store)
    private_source = (await repository.preferences("siro", "owner"))[0].source_ids[0]
    now = datetime.now(UTC)
    public_source = UserTextEvent(
        event_id=uuid4(),
        type="conversation.user_text.v1",
        source="test.preference",
        occurred_at=now,
        received_at=now,
        trace_id="synthetic-public-preference",
        session_id="public-source",
        turn_id="public-turn",
        sequence=0,
        priority=Priority.INTERACTIVE,
        privacy=EventPrivacy.CLOUD_ALLOWED,
        payload=UserTextPayload(text="synthetic public preference source", language="zh-TW"),
    )
    await store.record_event(public_source)
    public_id = str(public_source.event_id)
    private_self = "SYNTHETIC_PRIVATE_SELF_PREFERENCE"
    mixed = "SYNTHETIC_MIXED_PREFERENCE"
    missing = "SYNTHETIC_MISSING_SOURCE_PREFERENCE"
    unknown = "SYNTHETIC_UNKNOWN_SOURCE_PREFERENCE"
    public_owner = "SYNTHETIC_PUBLIC_OWNER_PREFERENCE"
    public_self = "SYNTHETIC_PUBLIC_SELF_PREFERENCE"
    for item in (
        preference("siro", private_self, (private_source,)),
        preference("owner", mixed, (public_id, private_source)),
        preference("siro", missing, (str(uuid4()),)),
        preference("siro", unknown, ("identity-core:unknown",)),
        preference("owner", public_owner, (public_id,)),
        preference("siro", public_self, (public_id,)),
    ):
        await repository.put_preference(item)

    cloud_model = RecordingModel()
    await companion(tmp_path, cloud_model, Privacy.CLOUD_ALLOWED).respond("cloud-reader", "你好")
    assert len(cloud_model.requests) == 1
    cloud_request = cloud_model.requests[0]
    assert cloud_request.messages
    serialized = json.dumps(asdict(cloud_request), ensure_ascii=False)
    for subject in (private_owner, private_self, mixed, missing, unknown):
        assert subject not in serialized
    assert public_owner in serialized
    assert public_self in serialized
    public_preferences = await repository.preferences(
        "siro", "owner", route_privacy=EventPrivacy.CLOUD_ALLOWED
    )
    assert {item.subject for item in public_preferences} == {public_owner}

    local_model = RecordingModel()
    await companion(tmp_path, local_model, Privacy.LOCAL_ONLY).respond("local-reader", "你好")
    serialized_local = json.dumps(asdict(local_model.requests[0]), ensure_ascii=False)
    for subject in (
        private_owner,
        private_self,
        mixed,
        missing,
        unknown,
        public_owner,
        public_self,
    ):
        assert subject in serialized_local


@pytest.mark.asyncio
@pytest.mark.parametrize("privacy", [Privacy.LOCAL_ONLY, Privacy.CLOUD_ALLOWED])
async def test_cloud_affect_projection_omits_private_reason_but_ui_keeps_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, privacy: Privacy
) -> None:
    model, hub = RecordingModel(), RecordingHub()
    controller = companion(tmp_path, model, privacy, hub)
    original = controller._affect.appraise_user_event
    private_reason = "SYNTHETIC_PRIVATE_AFFECT_REASON"

    def appraise(*args: object, **kwargs: object) -> object:
        result = original(*args, **kwargs)  # type: ignore[arg-type]
        return replace(result, state=replace(result.state, reason=private_reason))

    monkeypatch.setattr(controller._affect, "appraise_user_event", appraise)
    await controller.respond("synthetic-affect", "你好")
    serialized = json.dumps(asdict(model.requests[0]), ensure_ascii=False)
    assert (private_reason in serialized) is (privacy is Privacy.LOCAL_ONLY)
    affect_messages = [message for message in hub.messages if message["type"] == "affect_state"]
    assert len(affect_messages) == 1
    assert affect_messages[0]["reason"] == private_reason

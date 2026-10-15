"""Optional D57 metadata failure must not take the existing companion offline."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
from siro.core.cognition import Goal, GoalState
from siro.core.goal_tasks import GoalTask
from siro.persistence.goals import SQLiteGoalRepository
from siro.persistence.sqlite import SQLiteStore
from siro.ports.models import CancellationToken, ModelChunk, ModelRequest, Privacy
from siro.services.agent.goal_tasks import ReadTaskOwner
from siro.services.presentation.gateway import GatewayHub, create_app
from siro.services.presentation.integrated import IntegratedCompanion
from siro.services.tools.execution import ExecutionContext


class NoProvider:
    name = "must-not-call-provider"

    def __init__(self) -> None:
        self.calls = 0

    async def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        self.calls += 1
        yield ModelChunk("text", "unexpected provider invocation")
        raise AssertionError("this owned startup/status fixture must not invoke a provider")


class RecordingHub(GatewayHub):
    def __init__(self) -> None:
        super().__init__()
        self.events: list[dict[str, object]] = []

    async def broadcast(self, payload: dict[str, object], *, urgent: bool = False) -> None:
        self.events.append(payload)


class NoReadWorkspace:
    available = True

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir()
        self.calls = 0

    async def execute(
        self, capability: str, arguments: dict[str, object], context: ExecutionContext
    ) -> object:
        self.calls += 1
        raise AssertionError("malformed metadata must never become a read")


@pytest.mark.asyncio
@pytest.mark.parametrize("malformation", ["completed-without-hash", "over-capacity"])
async def test_bad_optional_goal_metadata_leaves_main_chat_startup_available(
    tmp_path: Path, malformation: str
) -> None:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    workspace = NoReadWorkspace(tmp_path / "documents")
    task = GoalTask(owner_session_id="owner", workspace=str(workspace.root), paths=("notes.md",))
    identifier = str(uuid4())
    if malformation == "completed-without-hash":
        await SQLiteGoalRepository(store).add(
            Goal(identifier, GoalState.PROPOSED, "notes.md", None, task=task)
        )
        encoded = task.model_dump(mode="json")
        encoded["observations"] = [
            {
                "path": "notes.md",
                "status": "completed",
                "sha256": None,
                "read_at": "2026-10-14T00:00:00+00:00",
            }
        ]
        await store.run_transaction(
            lambda connection: connection.execute(
                "UPDATE goals SET task_json=? WHERE goal_id=?", (json.dumps(encoded), identifier)
            )
        )
    else:
        # Directly seed damaged persisted capacity; do not weaken normal add's cap.
        await store.run_transaction(
            lambda connection: connection.executemany(
                "INSERT INTO goals(goal_id,state,next_step,deadline,budget_json,revision,"
                "task_json) "
                "VALUES (?,'proposed','notes.md',NULL,?,1,?)",
                [
                    (
                        str(uuid4()),
                        '{"steps_used":0,"max_steps":8,"cost_used":0,"max_cost":0}',
                        task.model_dump_json(),
                    )
                    for _ in range(21)
                ],
            )
        )
    model, hub = NoProvider(), RecordingHub()
    transport = WebSocketBodyTransport()
    controller = IntegratedCompanion(
        tmp_path,
        model,
        hub,
        MinimalWebBodyAdapter(transport),
        privacy=Privacy.LOCAL_ONLY,
        runtime_profile="candidate",
        session_restore_enabled=False,
        memory_ingress_enabled=False,
    )
    owner = ReadTaskOwner(
        store, workspace, busy=lambda: controller.foreground_active, allowed=lambda: True
    )

    async def shutdown() -> None:
        await controller.cancel("owned-startup", "owned fixture shutdown")

    app = create_app(
        allowed_origins={"http://testserver"},
        runtime_profile="candidate",
        hub=hub,
        body_transport=transport,
        on_startup=controller.startup,
        on_shutdown=shutdown,
        on_turn=controller.respond,
        read_task_owner=owner,
    )
    try:
        async with app.router.lifespan_context(app):
            assert controller._core is not None
            await controller.respond("owner", "gateway 本機測試狀態")
            assert any(
                event.get("type") == "assistant_terminal" and event.get("state") == "completed"
                for event in hub.events
            )
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://testserver"
            ) as client:
                token = (
                    await client.post("/v1/session", headers={"origin": "http://testserver"})
                ).json()["token"]
                response = await client.get(
                    "/v1/goal-tasks/owner", headers={"authorization": f"Bearer {token}"}
                )
                assert response.status_code == 503
                assert response.json() == {"detail": {"code": "unavailable"}}
                assert str(workspace.root) not in response.text
            assert workspace.calls == 0 and model.calls == 0
    finally:
        await owner.close()
        assert workspace.calls == 0 and model.calls == 0

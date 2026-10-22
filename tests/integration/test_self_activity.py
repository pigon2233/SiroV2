"""CP-P04 stage 1: SIRO's own background run is read-only, visible and always yields."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from test_activity_monitor import ScriptedModel, activities_of, companion

from siro.ports.models import ToolCall
from siro.services.activity.monitor import ActivityMonitor
from siro.services.agent.runs import SQLiteAgentRunRepository
from siro.services.agent.self_activity import SELF_SESSION, SelfActivityOwner
from siro.services.presentation.gateway import create_app
from siro.services.tools.execution import ExecutionContext

pytestmark = pytest.mark.asyncio
READ = "browser.navigate+read"


def read_call(call_id: str, url: str = "https://example.test/nebula") -> ToolCall:
    return ToolCall(call_id, READ, {"url": url})


async def owner_for(
    tmp_path: Path, model: ScriptedModel, executors: dict[str, Any], allowed: list[bool]
) -> tuple[SelfActivityOwner, Any, list[str]]:
    controller, store = await companion(tmp_path, model, executors)
    orchestrator = controller._tool_orchestrator
    assert orchestrator is not None
    closed: list[str] = []

    async def close_browser(session_id: str) -> None:
        closed.append(session_id)

    owner = SelfActivityOwner(
        SQLiteAgentRunRepository(store),
        orchestrator,
        model,
        allowed=lambda: allowed[0],
        close_browser=close_browser,
    )
    return owner, store, closed


async def settle(owner: SelfActivityOwner) -> None:
    for _ in range(200):
        if not owner.busy:
            return
        await asyncio.sleep(0.01)
    raise AssertionError("self activity did not finish")


async def test_research_run_is_read_only_visible_and_kept_out_of_owner_sessions(
    tmp_path: Path,
) -> None:
    pages: list[object] = []
    ran: list[object] = []

    async def read(arguments: dict[str, object], context: ExecutionContext) -> object:
        assert context.session_id == SELF_SESSION
        pages.append(arguments["url"])
        return {"url": arguments["url"], "title": "synthetic nebula page", "text": "M42"}

    async def execute(arguments: dict[str, object], context: ExecutionContext) -> object:
        ran.append(arguments)
        return {}

    model = ScriptedModel(
        [
            [read_call("r1"), ToolCall("x1", "computer.execute", {"argv": ["rm", "-rf", "/"]})],
            "筆記：獵戶座星雲 M42 [https://example.test/nebula]",  # noqa: RUF001
        ]
    )
    owner, store, closed = await owner_for(
        tmp_path, model, {READ: read, "computer.execute": execute}, [True]
    )
    run_id = await owner.start("讀一篇關於獵戶座星雲的介紹")
    assert run_id is not None
    await settle(owner)
    [activity] = activities_of(await ActivityMonitor(store).snapshot())
    assert (activity["activity_id"], activity["origin"]) == (run_id, "self_interest")
    assert activity["session_id"] == SELF_SESSION and activity["state"] == "completed"
    # Only the page read became a tool; the shell request never reached a proposal.
    assert [tool["capability"] for tool in activity["tools"]] == [READ]
    assert activity["tools"][0]["state"] == "completed"
    assert pages == ["https://example.test/nebula"] and ran == []
    assert closed == [SELF_SESSION]


async def test_owner_turn_preempts_and_a_new_run_can_start_after(tmp_path: Path) -> None:
    entered = asyncio.Event()

    async def read(arguments: dict[str, object], context: ExecutionContext) -> object:
        entered.set()
        await context.cancellation.wait()
        context.check()
        return {}

    model = ScriptedModel([[read_call("r1")], "never"])
    owner, store, _ = await owner_for(tmp_path, model, {READ: read}, [True])
    first = await owner.start("慢慢讀一頁")
    await asyncio.wait_for(entered.wait(), 5)
    assert await owner.start("第二件事") is None  # one background run at a time
    await asyncio.wait_for(owner.foreground(), 5)
    assert not owner.busy
    [activity] = activities_of(await ActivityMonitor(store).snapshot())
    assert activity["activity_id"] == first and activity["state"] in {"cancelled", "unknown"}
    # A dispatched read is never shown as a clean cancellation.
    assert [tool["state"] for tool in activity["tools"]] == ["unknown"]
    model.rounds, model.requests = ["沒有要讀的了"], 0
    assert await owner.start("下一件事") is not None
    await settle(owner)


async def test_pause_lets_the_current_step_finish_then_ends_and_blocks_new_runs(
    tmp_path: Path,
) -> None:
    release = asyncio.Event()
    entered = asyncio.Event()

    async def read(arguments: dict[str, object], context: ExecutionContext) -> object:
        entered.set()
        await release.wait()
        return {"title": "page"}

    model = ScriptedModel([[read_call("r1")], [read_call("r2")], "done"])
    owner, store, _ = await owner_for(tmp_path, model, {READ: read}, [True])
    run_id = await owner.start("讀兩頁")
    await asyncio.wait_for(entered.wait(), 5)
    await owner.set_paused(True)
    release.set()
    await settle(owner)
    [activity] = activities_of(await ActivityMonitor(store).snapshot())
    assert activity["activity_id"] == run_id
    assert (activity["state"], activity["error"]) == ("cancelled", "autonomy_paused")
    assert [tool["state"] for tool in activity["tools"]] == ["completed"]
    assert await owner.start("暫停中") is None
    await owner.set_paused(False)
    assert await owner.start("恢復後") is not None
    await owner.close()


async def test_tools_switch_off_refuses_and_stops(tmp_path: Path) -> None:
    allowed = [False]

    async def read(arguments: dict[str, object], context: ExecutionContext) -> object:
        return {}

    owner, _, _ = await owner_for(tmp_path, ScriptedModel(["x"]), {READ: read}, allowed)
    assert await owner.start("不准用工具") is None
    allowed[0] = True
    assert await owner.start("可以了") is not None
    await settle(owner)


def test_gateway_controls_reach_only_the_background_owner() -> None:
    origin = "http://testserver"
    calls: list[tuple[str, object]] = []

    class FakeOwner:
        paused = False

        async def stop(self, reason: str, run_id: str | None = None) -> bool:
            calls.append(("stop", reason))
            return True

        async def foreground(self, reason: str = "foreground") -> None:
            calls.append(("foreground", reason))

        async def set_paused(self, paused: bool) -> None:
            self.paused = paused
            calls.append(("paused", paused))

    async def snapshot(limit: int) -> dict[str, object]:
        return {"status": "ok", "activities": []}

    async def cancel(turn_id: str, reason: str) -> None:
        calls.append(("cancel", turn_id))

    app = create_app(
        allowed_origins={origin},
        on_activity_snapshot=snapshot,
        on_cancel=cancel,
        self_activity=FakeOwner(),  # type: ignore[arg-type]
    )
    with TestClient(app) as client:
        assert client.post("/v1/activities/stop-background").status_code == 401
        token = client.post("/v1/session", headers={"origin": origin}).json()["token"]
        auth = {"authorization": f"Bearer {token}"}
        assert client.get("/v1/activities", headers=auth).json()["self_activity"] == {
            "paused": False
        }
        response = client.put("/v1/self-activity", json={"paused": True}, headers=auth)
        assert response.json() == {"type": "self_activity", "paused": True}
        assert client.post("/v1/activities/stop-background", headers=auth).json() == {
            "stopped": True
        }
        client.post("/v1/turns/t1/cancel", json={"reason": "user"}, headers=auth)
    assert calls == [
        ("paused", True),
        ("stop", "owner stopped background work"),
        ("cancel", "t1"),
        ("stop", "owner stop"),
    ]


def test_notes_are_shared_only_on_request_and_reach_the_change_feed() -> None:
    origin = "http://testserver"
    shared: list[tuple[str, str]] = []
    marked: list[str] = []
    note = {"run_id": "n1", "topic": "M42", "text": "筆記", "sources": [], "shared": False}

    class FakeOwner:
        paused = False

    class FakeNotes:
        async def unshared(self) -> list[str]:
            return [] if marked else ["n1"]

        async def notes(self) -> list[dict[str, object]]:
            return [note]

        async def note(self, run_id: str) -> dict[str, object] | None:
            return note if run_id == "n1" else None

        def mark_shared(self, run_id: str) -> None:
            marked.append(run_id)

    async def share(text: str, spoken: str) -> None:
        shared.append((text, spoken))

    async def changes(after: int, limit: int) -> dict[str, object]:
        return {"status": "ok", "events": []}

    app = create_app(
        allowed_origins={origin},
        on_activity_changes=changes,
        self_activity=FakeOwner(),  # type: ignore[arg-type]
        self_notes=FakeNotes(),  # type: ignore[arg-type]
        on_share_note=share,
    )
    with TestClient(app) as client:
        token = client.post("/v1/session", headers={"origin": origin}).json()["token"]
        auth = {"authorization": f"Bearer {token}"}
        feed = client.get("/v1/activities/changes?after=0", headers=auth).json()
        assert feed["self_activity"] == {"paused": False, "unshared": ["n1"]}
        assert client.get("/v1/self-notes", headers=auth).json() == {"notes": [note]}
        assert client.post("/v1/self-notes/zz/share", headers=auth).status_code == 404
        assert client.post("/v1/self-notes/n1/share", headers=auth).json()["shared"] is True
        assert client.post("/v1/self-notes/n1/dismiss", headers=auth).status_code == 200
        assert client.post("/v1/self-notes/n1/delete", headers=auth).status_code == 422
    assert len(shared) == 1 and shared[0][0].startswith("我剛剛自己查了「M42」")
    assert marked == ["n1", "n1"]


async def test_nothing_starts_when_dispatches_cannot_be_audited(tmp_path: Path) -> None:
    async def read(arguments: dict[str, object], context: ExecutionContext) -> object:
        raise AssertionError("an unaudited dispatch must never run")

    owner, store, _ = await owner_for(
        tmp_path, ScriptedModel([[read_call("r1")]]), {READ: read}, [True]
    )
    hook = owner._orchestrator.journal_hook
    owner._orchestrator.journal_hook = None
    assert await owner.start("沒有審計就不開始") is None
    assert not owner.busy and activities_of(await ActivityMonitor(store).snapshot()) == []
    owner._orchestrator.journal_hook = hook
    assert await owner.start("審計恢復後可以開始") is not None
    await settle(owner)


async def test_owner_pause_survives_a_restart_but_a_shutdown_does_not(tmp_path: Path) -> None:
    controller, store = await companion(tmp_path, ScriptedModel(["x"]), {})
    orchestrator = controller._tool_orchestrator
    assert orchestrator is not None
    state = tmp_path / "self-activity-state.json"

    def make() -> SelfActivityOwner:
        return SelfActivityOwner(
            SQLiteAgentRunRepository(store),
            orchestrator,
            ScriptedModel(["x"]),
            allowed=lambda: True,
            state_path=state,
        )

    first = make()
    assert not first.paused
    await first.set_paused(True)
    assert make().paused
    await first.set_paused(False)
    await first.close()
    assert not make().paused


async def test_what_she_shared_is_known_to_her_next_reply(tmp_path: Path) -> None:
    class Recording(ScriptedModel):
        seen: list[str] = []  # noqa: RUF012

        async def stream(self, request: Any, cancellation: Any) -> Any:
            self.seen.append(repr(request))
            async for chunk in super().stream(request, cancellation):
                yield chunk

    model = Recording(["好"])
    controller, _ = await companion(tmp_path, model, {})
    await controller.respond("s1", "你好")
    assert not any("self-note-share" in seen for seen in model.seen)
    await controller.share_self_note("我剛剛自己查了「星雲」。", "星雲")
    await controller.respond("s1", "剛剛那個是什麼")
    assert "星雲" in model.seen[-1] and "self-note-share" in model.seen[-1]

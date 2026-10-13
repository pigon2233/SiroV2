from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
from siro.persistence.sqlite import SQLiteStore
from siro.ports.models import CancellationToken, ModelChunk, ModelRequest, Privacy, ToolCall
from siro.services.presentation.gateway import GatewayHub
from siro.services.presentation.integrated import IntegratedCompanion
from siro.services.tools import execution
from siro.services.tools.execution import (
    ExecutionCancelled,
    ExecutionCleanupError,
    ExecutionContext,
    execute_bounded_argv,
)
from siro.services.tools.orchestrator import SQLiteToolProposalRepository, ToolOrchestrator


async def wait_file(path: Path) -> None:
    async with asyncio.timeout(3):
        while not path.exists() or not path.read_text().strip():
            await asyncio.sleep(0.005)


def running(pid: int) -> bool:
    path = Path(f"/proc/{pid}/stat")
    try:
        return path.read_text().split(") ", 1)[1][0] != "Z"
    except (FileNotFoundError, ProcessLookupError):
        return False


TREE = """
import os,signal,time
child = os.fork()
if child == 0:
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    open('child.pid','w').write(str(os.getpid()))
else:
    open('parent.pid','w').write(str(os.getpid()))
while True:
    time.sleep(.01)
"""


@pytest.mark.asyncio
@pytest.mark.parametrize("cause", ["cancel", "timeout", "task_cancel"])
async def test_owned_parent_child_stop_and_unrelated_process_survives(
    tmp_path: Path, cause: str
) -> None:
    context = ExecutionContext("run", "session", "epoch")
    unrelated = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(30)"], start_new_session=True
    )
    task = asyncio.create_task(
        execute_bounded_argv(
            (sys.executable, "-c", TREE),
            cwd=tmp_path,
            environment=os.environ.copy(),
            timeout=1 if cause == "timeout" else 30,
            context=context,
        )
    )
    try:
        await wait_file(tmp_path / "child.pid")
        await wait_file(tmp_path / "parent.pid")
        parent, child = (int((tmp_path / name).read_text()) for name in ("parent.pid", "child.pid"))
        started = asyncio.get_running_loop().time()
        if cause == "cancel":
            context.cancellation.cancel()
        elif cause == "task_cancel":
            task.cancel()
        error = (
            ExecutionCancelled
            if cause == "cancel"
            else asyncio.CancelledError
            if cause == "task_cancel"
            else TimeoutError
        )
        with pytest.raises(error):
            await task
        assert asyncio.get_running_loop().time() - started < 2
        assert not Path(f"/proc/{parent}").exists(), "direct child must be reaped"
        assert not running(child), "TERM-ignoring descendant must stop after group KILL"
        assert unrelated.poll() is None
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        unrelated.terminate()
        unrelated.wait(timeout=3)


@pytest.mark.asyncio
async def test_pre_cancel_and_deadline_do_not_dispatch(tmp_path: Path) -> None:
    marker = tmp_path / "dispatch"
    context = ExecutionContext("run", "session", "epoch")
    context.cancellation.cancel()
    for ctx, error in (
        (context, ExecutionCancelled),
        (ExecutionContext("run", "session", "epoch", deadline=0), TimeoutError),
    ):
        with pytest.raises(error):
            await execute_bounded_argv(
                (sys.executable, "-c", "open('dispatch','w').write('bad')"),
                cwd=tmp_path,
                environment=os.environ.copy(),
                timeout=30,
                context=ctx,
            )
    assert not marker.exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("acknowledged", [False, True])
async def test_detach_session_lifetime_and_pre_ack_cancel(
    tmp_path: Path, acknowledged: bool
) -> None:
    context = ExecutionContext("run", "session", "epoch")
    task = asyncio.create_task(
        execute_bounded_argv(
            (
                sys.executable,
                "-c",
                "import os,time; open('pid','w').write(str(os.getpid())); time.sleep(30)",
            ),
            cwd=tmp_path,
            environment=os.environ.copy(),
            timeout=30,
            detach=True,
            context=context,
        )
    )
    await wait_file(tmp_path / "pid")
    pid = int((tmp_path / "pid").read_text())
    try:
        if acknowledged:
            result = await task
            assert result == {
                "argv": [
                    sys.executable,
                    "-c",
                    "import os,time; open('pid','w').write(str(os.getpid())); time.sleep(30)",
                ],
                "pid": pid,
                "state": "started",
            }
            context.cancellation.cancel()
            await asyncio.sleep(0.01)
            assert running(pid)
        else:
            context.cancellation.cancel()
            with pytest.raises(ExecutionCancelled):
                await task
            assert not running(pid)
    finally:
        if running(pid):
            os.killpg(pid, signal.SIGKILL)
        async with asyncio.timeout(3):
            while running(pid):
                await asyncio.sleep(0.005)


@pytest.mark.asyncio
@pytest.mark.parametrize("refusal", ["permission", "no_effect"])
async def test_cleanup_failure_is_explicit_and_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, refusal: str
) -> None:
    context = ExecutionContext("run", "session", "epoch")

    def denied(process: asyncio.subprocess.Process, sig: signal.Signals) -> None:
        if refusal == "permission":
            raise PermissionError("synthetic cleanup refusal")

    monkeypatch.setattr(execution, "_signal_owned_group", denied)
    task = asyncio.create_task(
        execute_bounded_argv(
            (
                sys.executable,
                "-c",
                "import os,time; open('pid','w').write(str(os.getpid())); time.sleep(30)",
            ),
            cwd=tmp_path,
            environment=os.environ.copy(),
            timeout=30,
            context=context,
        )
    )
    await wait_file(tmp_path / "pid")
    pid = int((tmp_path / "pid").read_text())
    started = asyncio.get_running_loop().time()
    try:
        context.cancellation.cancel()
        with pytest.raises(ExecutionCleanupError):
            await task
        assert asyncio.get_running_loop().time() - started < 5
    finally:
        if running(pid):
            os.killpg(pid, signal.SIGKILL)
        async with asyncio.timeout(3):
            while running(pid):
                await asyncio.sleep(0.005)


class ToolModel:
    name = "lifecycle-synthetic"

    def __init__(self, commands: list[list[str]]) -> None:
        self.commands = commands
        self.requests: list[ModelRequest] = []

    async def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        self.requests.append(request)
        if len(self.requests) == 1:
            for i, argv in enumerate(self.commands):
                yield ModelChunk(
                    "tool_request",
                    tool_call=ToolCall(f"call-{i}", "computer.execute", {"argv": argv}),
                )
        else:
            yield ModelChunk("text", "done")
        yield ModelChunk("finished")


class Hub(GatewayHub):
    def __init__(self) -> None:
        super().__init__()
        self.events: list[dict[str, object]] = []

    async def broadcast(self, payload: dict[str, object], *, urgent: bool = False) -> None:
        self.events.append(payload)


@pytest.mark.asyncio
async def test_real_controller_orchestrator_process_cancel_fences_second_tool(
    tmp_path: Path,
) -> None:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    contexts: list[ExecutionContext] = []

    async def legacy(arguments: dict[str, object]) -> object:
        raise AssertionError("candidate must use context executor")

    async def contextual(arguments: dict[str, object], context: ExecutionContext) -> object:
        contexts.append(context)
        argv = arguments["argv"]
        assert isinstance(argv, list)
        return await execute_bounded_argv(
            tuple(str(a) for a in argv),
            cwd=tmp_path,
            environment=os.environ.copy(),
            timeout=30,
            context=context,
        )

    orchestrator = ToolOrchestrator(
        SQLiteToolProposalRepository(store),
        {"computer.execute": legacy},
        contextual_executors={"computer.execute": contextual},
    )
    hub = Hub()
    model = ToolModel(
        [[sys.executable, "-c", TREE], [sys.executable, "-c", "open('bad','w').write('bad')"]]
    )
    controller = IntegratedCompanion(
        tmp_path,
        model,
        hub,
        MinimalWebBodyAdapter(WebSocketBodyTransport()),
        privacy=Privacy.LOCAL_ONLY,
        tool_orchestrator=orchestrator,
        runtime_profile="candidate",
        auto_authorize=lambda: True,
    )
    task = asyncio.create_task(controller.respond("one", "do tasks"))
    await wait_file(tmp_path / "child.pid")
    started = asyncio.get_running_loop().time()
    await controller.cancel("active", "stop")
    await asyncio.wait_for(task, 2)
    assert asyncio.get_running_loop().time() - started < 2
    assert not running(int((tmp_path / "child.pid").read_text()))
    assert len(contexts) == 1 and contexts[0].authorized
    assert contexts[0].session_id == "one" and contexts[0].proposal_id and contexts[0].call_id
    assert not (tmp_path / "bad").exists()
    terminal = [i for i, e in enumerate(hub.events) if e["type"] == "assistant_terminal"]
    assert len(terminal) == 1
    assert not any(
        e["type"] in {"tool_result", "tool_started", "assistant_delta"}
        for e in hub.events[terminal[0] + 1 :]
    )
    row = await store.run_transaction(
        lambda c: c.execute("SELECT state FROM agent_runs").fetchone()
    )
    assert row[0] == "cancelled"


@pytest.mark.asyncio
async def test_main_http_cancel_targets_only_owned_session(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import httpx
    import uvicorn
    from fastapi import FastAPI

    from siro.adapters.models import ollama
    from siro.services.presentation import gateway

    class MainModel:
        name = "main-lifecycle-synthetic"

        async def stream(
            self, request: ModelRequest, cancellation: CancellationToken
        ) -> AsyncIterator[ModelChunk]:
            if len(request.messages) == 2:
                session = request.messages[-1].content
                code = (
                    f"import os,time; open('pid.{session}','w').write(str(os.getpid())); "
                    "time.sleep(30)"
                )
                yield ModelChunk(
                    "tool_request",
                    tool_call=ToolCall(
                        request.generation_id,
                        "computer.execute",
                        {"argv": [sys.executable, "-c", code], "cwd": str(tmp_path)},
                    ),
                )
            else:
                yield ModelChunk("text", "done")
            yield ModelChunk("finished")

    for name in tuple(os.environ):
        if name.startswith("SIRO_") or name == "GROQ_API_KEY":
            monkeypatch.delenv(name)
    monkeypatch.setenv("SIRO_DATA_DIR", str(tmp_path))
    # Synthetic provider has no native tokenizer; this fixture tests executor lifecycle.
    monkeypatch.setenv("SIRO_CONTEXT_TOKEN_BUDGET_ENABLED", "0")
    monkeypatch.setenv("SIRO_OLLAMA_MODEL", "synthetic")
    monkeypatch.setenv("SIRO_RUNTIME_PROFILE", "candidate")
    monkeypatch.setattr(ollama, "OllamaAdapter", lambda **kwargs: MainModel())
    hub = Hub()
    monkeypatch.setattr(gateway, "GatewayHub", lambda: hub)
    apps: list[FastAPI] = []
    monkeypatch.setattr(uvicorn, "run", lambda app, **kwargs: apps.append(app))
    # main initializes SQLite synchronously; run composition outside this event loop.
    await asyncio.to_thread(gateway.main)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=apps[0]), base_url="http://127.0.0.1:8000"
    ) as client:
        token = (
            await client.post("/v1/session", headers={"origin": "http://127.0.0.1:8000"})
        ).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        turns = [
            asyncio.create_task(
                client.post(f"/v1/conversations/{s}/turns", headers=headers, json={"text": s})
            )
            for s in ("one", "two")
        ]
        try:
            await wait_file(tmp_path / "pid.one")
            await wait_file(tmp_path / "pid.two")
            snapshot = (await client.get("/v1/snapshot", headers=headers)).json()
            started = asyncio.get_running_loop().time()
            response = await client.post(
                f"/v1/turns/{snapshot['active_turns']['one']['turn_id']}/cancel",
                headers=headers,
                json={"reason": "stop one"},
            )
            assert response.status_code == 200
            assert asyncio.get_running_loop().time() - started < 2
            assert not running(int((tmp_path / "pid.one").read_text()))
            assert running(int((tmp_path / "pid.two").read_text()))
            one_terminal = [
                e
                for e in hub.events
                if e["type"] == "assistant_terminal" and e["session_id"] == "one"
            ]
            assert len(one_terminal) == 1
            # An unknown turn ID must not become an all-session cancellation.
            await client.post(
                "/v1/turns/not-owned/cancel", headers=headers, json={"reason": "unknown"}
            )
            assert running(int((tmp_path / "pid.two").read_text()))
        finally:
            await client.post(
                "/v1/turns/active/cancel", headers=headers, json={"reason": "test cleanup"}
            )
            await asyncio.gather(*turns)


@pytest.mark.asyncio
async def test_context_completion_cancel_races_100_no_late_ui(tmp_path: Path) -> None:
    for iteration in range(100):
        entered, release = asyncio.Event(), asyncio.Event()
        store = SQLiteStore(tmp_path / str(iteration) / "siro.db")
        await store.initialize()
        executed: list[object] = []

        async def old(arguments: dict[str, object]) -> object:
            raise AssertionError("candidate dispatched old executor")

        async def contextual(
            arguments: dict[str, object],
            context: ExecutionContext,
            executed: list[object] = executed,
            entered: asyncio.Event = entered,
            release: asyncio.Event = release,
        ) -> object:
            executed.append(arguments)
            entered.set()
            ready = asyncio.create_task(release.wait())
            stopped = asyncio.create_task(context.cancellation.wait())
            try:
                await asyncio.wait({ready, stopped}, return_when=asyncio.FIRST_COMPLETED)
                context.check()
                return {}
            finally:
                ready.cancel()
                stopped.cancel()
                await asyncio.gather(ready, stopped, return_exceptions=True)

        orchestrator = ToolOrchestrator(
            SQLiteToolProposalRepository(store),
            {"computer.execute": old},
            contextual_executors={"computer.execute": contextual},
        )
        model, hub = ToolModel([["first"], ["second"]]), Hub()
        controller = IntegratedCompanion(
            tmp_path / str(iteration),
            model,
            hub,
            MinimalWebBodyAdapter(WebSocketBodyTransport()),
            privacy=Privacy.LOCAL_ONLY,
            tool_orchestrator=orchestrator,
            runtime_profile="candidate",
            auto_authorize=lambda: True,
        )
        task = asyncio.create_task(controller.respond("race", "goal"))
        await asyncio.wait_for(entered.wait(), 2)
        if iteration % 3:
            release.set()
        if iteration % 3 == 2:
            # Give a completed executor an actual scheduler opportunity before cancellation.
            await asyncio.sleep(0)
        await controller.cancel("active", "race cancel")
        release.set()
        await asyncio.wait_for(task, 2)
        terminals = [i for i, e in enumerate(hub.events) if e["type"] == "assistant_terminal"]
        assert len(terminals) == 1
        assert not any(
            e["type"] in {"tool_result", "tool_started", "assistant_delta"}
            for e in hub.events[terminals[0] + 1 :]
        )
        assert len(executed) == 1
        assert len(model.requests) == 1
        assert not any(orchestrator._active.values())


@pytest.mark.asyncio
@pytest.mark.parametrize("arguments_only", [False, True])
async def test_manual_http_executor_cancel_has_no_late_tool_result(
    tmp_path: Path, arguments_only: bool
) -> None:
    import httpx

    from siro.services.presentation.gateway import create_app

    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()

    async def old(arguments: dict[str, object]) -> object:
        assert arguments_only, "wrong backend"
        argv = arguments["argv"]
        assert isinstance(argv, list)
        return await execute_bounded_argv(
            tuple(str(a) for a in argv),
            cwd=tmp_path,
            environment=os.environ.copy(),
            timeout=30,
        )

    async def contextual(arguments: dict[str, object], context: ExecutionContext) -> object:
        argv = arguments["argv"]
        assert isinstance(argv, list)
        return await execute_bounded_argv(
            tuple(str(a) for a in argv),
            cwd=tmp_path,
            environment=os.environ.copy(),
            timeout=30,
            context=context,
        )

    orchestrator = ToolOrchestrator(
        SQLiteToolProposalRepository(store),
        {"computer.execute": old},
        contextual_executors=None if arguments_only else {"computer.execute": contextual},
    )
    hub, model = Hub(), ToolModel([[sys.executable, "-c", TREE]])
    controller = IntegratedCompanion(
        tmp_path,
        model,
        hub,
        MinimalWebBodyAdapter(WebSocketBodyTransport()),
        privacy=Privacy.LOCAL_ONLY,
        tool_orchestrator=orchestrator,
        runtime_profile="candidate",
        auto_authorize=lambda: False,
    )
    app = create_app(
        hub=hub,
        tool_orchestrator=orchestrator,
        on_turn=controller.respond,
        on_cancel=controller.cancel,
        on_tool_result=controller.continue_after_tool,
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8000"
    ) as client:
        token = (
            await client.post("/v1/session", headers={"origin": "http://127.0.0.1:8000"})
        ).json()["token"]
        headers = {"Authorization": f"Bearer {token}"}
        response = await client.post(
            "/v1/conversations/manual/turns", headers=headers, json={"text": "goal"}
        )
        assert response.status_code == 200
        proposal_id = str(
            next(e for e in hub.events if e["type"] == "tool_proposal")["proposal_id"]
        )
        approval = asyncio.create_task(
            client.post(
                f"/v1/tool-proposals/{proposal_id}/approve",
                headers=headers,
                json={"approved": True},
            )
        )
        await wait_file(tmp_path / "child.pid")
        try:
            cancelled = await client.post(
                "/v1/turns/active/cancel", headers=headers, json={"reason": "stop"}
            )
            assert cancelled.status_code == 200
            result = await asyncio.wait_for(approval, 2)
            assert result.json()["status"] == "failed"
            assert not running(int((tmp_path / "child.pid").read_text()))
            terminal = next(
                i for i, e in enumerate(hub.events) if e["type"] == "assistant_terminal"
            )
            assert not any(
                e["type"] in {"tool_result", "tool_started", "assistant_delta"}
                for e in hub.events[terminal + 1 :]
            )
            assert len(model.requests) == 1
        finally:
            if not approval.done():
                await controller.cancel("active", "test cleanup")
                await approval


@pytest.mark.asyncio
async def test_cleanup_failure_reaches_run_terminal(tmp_path: Path) -> None:
    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    entered = asyncio.Event()

    async def old(arguments: dict[str, object]) -> object:
        raise AssertionError("wrong backend")

    async def fail_cleanup(arguments: dict[str, object], context: ExecutionContext) -> object:
        entered.set()
        await context.cancellation.wait()
        raise ExecutionCleanupError("synthetic owned process still running")

    orchestrator = ToolOrchestrator(
        SQLiteToolProposalRepository(store),
        {"computer.execute": old},
        contextual_executors={"computer.execute": fail_cleanup},
    )
    hub = Hub()
    controller = IntegratedCompanion(
        tmp_path,
        ToolModel([["first"]]),
        hub,
        MinimalWebBodyAdapter(WebSocketBodyTransport()),
        privacy=Privacy.LOCAL_ONLY,
        tool_orchestrator=orchestrator,
        runtime_profile="candidate",
        auto_authorize=lambda: True,
    )
    task = asyncio.create_task(controller.respond("failure", "goal"))
    await asyncio.wait_for(entered.wait(), 2)
    await controller.cancel("active", "stop")
    await task
    terminals = [e for e in hub.events if e["type"] == "assistant_terminal"]
    assert len(terminals) == 1 and terminals[0]["state"] == "failed"
    assert terminals[0]["error"] == "ExecutionCleanupError"
    row = await store.run_transaction(
        lambda c: c.execute("SELECT state,error FROM agent_runs").fetchone()
    )
    assert tuple(row) == ("failed", "ExecutionCleanupError")


@pytest.mark.asyncio
async def test_repeated_task_cancel_during_spawn_does_not_abandon_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = asyncio.create_subprocess_exec
    entered, release = asyncio.Event(), asyncio.Event()
    owned: list[asyncio.subprocess.Process] = []

    async def delayed_spawn(*argv: str, **kwargs: object) -> asyncio.subprocess.Process:
        entered.set()
        await release.wait()
        process = await original(*argv, **kwargs)  # type: ignore[arg-type]
        owned.append(process)
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", delayed_spawn)
    task = asyncio.create_task(
        execute_bounded_argv(
            (sys.executable, "-c", "import time; time.sleep(30)"),
            cwd=tmp_path,
            environment=os.environ.copy(),
            timeout=30,
        )
    )
    await asyncio.wait_for(entered.wait(), 2)
    task.cancel()
    await asyncio.sleep(0)
    task.cancel()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 2)
    assert len(owned) == 1 and owned[0].returncode is not None
    assert not Path(f"/proc/{owned[0].pid}").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("manual", [False, True])
async def test_arguments_only_cancel_waits_for_finally_and_prevents_effect(
    tmp_path: Path, manual: bool
) -> None:
    entered, release, cleaned = asyncio.Event(), asyncio.Event(), asyncio.Event()
    effects: list[object] = []

    async def handler(arguments: dict[str, object]) -> object:
        entered.set()
        try:
            await release.wait()
            effects.append(arguments)
            return {"ok": True}
        finally:
            await asyncio.sleep(0.01)
            cleaned.set()

    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    orchestrator = ToolOrchestrator(
        SQLiteToolProposalRepository(store), {"computer.execute": handler}
    )
    hub = Hub()
    controller = IntegratedCompanion(
        tmp_path,
        ToolModel([["synthetic"]]),
        hub,
        MinimalWebBodyAdapter(WebSocketBodyTransport()),
        privacy=Privacy.LOCAL_ONLY,
        tool_orchestrator=orchestrator,
        runtime_profile="candidate",
        auto_authorize=lambda: not manual,
    )
    task: asyncio.Task[object]
    if manual:
        await controller.respond("args", "goal")
        row = await store.run_transaction(
            lambda c: c.execute("SELECT proposal_id FROM tool_proposals").fetchone()
        )
        proposal = await orchestrator.get(row[0])
        assert proposal is not None
        await orchestrator.resolve(
            proposal.proposal_id, approved=True, arguments=proposal.arguments
        )
        task = asyncio.create_task(orchestrator.execute(proposal.proposal_id))
    else:
        task = asyncio.create_task(controller.respond("args", "goal"))
    await asyncio.wait_for(entered.wait(), 10)
    try:
        await controller.cancel("active", "cancel arguments", session_id="args")
        assert cleaned.is_set(), "handler cleanup must finish before terminal"
        release.set()
        await asyncio.wait_for(task, 2)
        assert effects == []
        readback = await controller.recovery_readback("args")
        assert readback is not None and readback["state"] == "cancelled"
        assert len([e for e in hub.events if e["type"] == "assistant_terminal"]) == 1
    finally:
        release.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_browser_enter_cancel_closes_acquired_resources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from siro.adapters import browser as module

    entered = asyncio.Event()
    closed: list[str] = []

    class Browser:
        async def new_page(self) -> object:
            entered.set()
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

        async def close(self) -> None:
            closed.append("browser")

    class Playwright:
        chromium: object

        def __init__(self) -> None:
            self.chromium = self

        async def launch(self, **kwargs: object) -> Browser:
            return Browser()

        async def stop(self) -> None:
            closed.append("playwright")

    class Manager:
        async def start(self) -> Playwright:
            return Playwright()

    monkeypatch.setattr("shutil.which", lambda name: "/synthetic/chromium")
    monkeypatch.setattr(module, "async_playwright", lambda: Manager())
    driver = module.ScopedBrowserDriver(("http://127.0.0.1",))
    task = asyncio.create_task(driver.__aenter__())
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert closed == ["browser", "playwright"]


@pytest.mark.asyncio
@pytest.mark.parametrize("refuses", [False, True])
async def test_arguments_only_cleanup_failure_is_bounded_and_unknown(
    tmp_path: Path, refuses: bool
) -> None:
    entered, release = asyncio.Event(), asyncio.Event()

    async def handler(arguments: dict[str, object]) -> object:
        entered.set()
        try:
            await release.wait()
        except asyncio.CancelledError:
            if refuses:
                raise RuntimeError("synthetic cleanup refused") from None
            await release.wait()  # deliberate noncooperation until the fixture releases it
        return {"not_proven_stopped": True}

    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    orchestrator = ToolOrchestrator(
        SQLiteToolProposalRepository(store), {"computer.execute": handler}
    )
    hub = Hub()
    controller = IntegratedCompanion(
        tmp_path,
        ToolModel([["synthetic"]]),
        hub,
        MinimalWebBodyAdapter(WebSocketBodyTransport()),
        privacy=Privacy.LOCAL_ONLY,
        tool_orchestrator=orchestrator,
        runtime_profile="candidate",
        auto_authorize=lambda: True,
    )
    task = asyncio.create_task(controller.respond("noncooperative", "goal"))
    await asyncio.wait_for(entered.wait(), 10)
    started = asyncio.get_running_loop().time()
    try:
        await controller.cancel("active", "stop", session_id="noncooperative")
        assert asyncio.get_running_loop().time() - started < 5
        readback = await controller.recovery_readback("noncooperative")
        assert readback is not None and readback["state"] == "failed"
        assert readback["error"] == "ExecutionCleanupError"
        import json
        from typing import cast

        calls = cast(list[dict[str, object]], readback["calls"])
        assert json.loads(str(calls[0]["observation_json"]))["error"] == "outcome_unknown"
        if not refuses:
            assert any(orchestrator._active.values()), "late cleanup must retain task ownership"
        before = len(hub.events)
        release.set()
        await asyncio.wait_for(task, 2)
        assert await controller.recovery_readback("noncooperative") == readback
        assert len(hub.events) == before
        assert not any(orchestrator._active.values())
        assert len([e for e in hub.events if e["type"] == "assistant_terminal"]) == 1
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_arguments_only_queued_cancel_and_shutdown_cleanup(tmp_path: Path) -> None:
    from siro.services.presentation.gateway import GatewayState, create_app

    entered, cleaned = asyncio.Event(), asyncio.Event()

    async def handler(arguments: dict[str, object]) -> object:
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cleaned.set()
        raise AssertionError("cancelled handler reached effect")

    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    orchestrator = ToolOrchestrator(
        SQLiteToolProposalRepository(store), {"computer.execute": handler}
    )
    controller = IntegratedCompanion(
        tmp_path,
        ToolModel([["queued"]]),
        Hub(),
        MinimalWebBodyAdapter(WebSocketBodyTransport()),
        privacy=Privacy.LOCAL_ONLY,
        tool_orchestrator=orchestrator,
        runtime_profile="candidate",
        auto_authorize=lambda: False,
    )
    await controller.respond("queued", "goal")
    row = await store.run_transaction(
        lambda c: c.execute("SELECT proposal_id FROM tool_proposals").fetchone()
    )
    await controller.cancel("active", "queued stop", session_id="queued")
    with pytest.raises(ValueError):
        await orchestrator.execute(row[0])
    assert not entered.is_set()
    # Actual production lifespan invokes cancellation and waits before shutdown.
    controller._model = ToolModel([["shutdown"]])
    assert controller._conversation is not None
    controller._conversation._model = controller._model
    controller._auto_authorize = lambda: True
    state = GatewayState()
    state.active_turns["shutdown"] = {"turn_id": "active", "state": "responding"}
    app = create_app(state=state, on_startup=controller.startup, on_cancel=controller.cancel)
    async with app.router.lifespan_context(app):
        task = asyncio.create_task(controller.respond("shutdown", "goal"))
        await asyncio.wait_for(entered.wait(), 10)
    assert cleaned.is_set()
    await asyncio.wait_for(task, 2)
    readback = await controller.recovery_readback("shutdown")
    assert readback is not None and readback["state"] == "cancelled"


@pytest.mark.asyncio
async def test_arguments_only_cancel_isolates_other_session(tmp_path: Path) -> None:
    class SessionModel:
        name = "session-lifecycle"

        async def stream(
            self, request: ModelRequest, cancellation: CancellationToken
        ) -> AsyncIterator[ModelChunk]:
            if request.messages[-1].role == "tool":
                yield ModelChunk("text", "done")
            else:
                yield ModelChunk(
                    "tool_request",
                    tool_call=ToolCall(
                        "call-0",
                        "computer.execute",
                        {"argv": [request.messages[-1].content]},
                    ),
                )
            yield ModelChunk("finished")

    entered = {s: asyncio.Event() for s in ("A", "B")}
    release = {s: asyncio.Event() for s in ("A", "B")}
    cleaned: list[str] = []
    effects: list[str] = []

    async def handler(arguments: dict[str, object]) -> object:
        session = str(arguments["argv"][0])  # type: ignore[index]
        entered[session].set()
        try:
            await release[session].wait()
            effects.append(session)
            return {"ok": True}
        finally:
            cleaned.append(session)

    store = SQLiteStore(tmp_path / "siro.db")
    await store.initialize()
    orchestrator = ToolOrchestrator(
        SQLiteToolProposalRepository(store), {"computer.execute": handler}
    )
    hub = Hub()
    controller = IntegratedCompanion(
        tmp_path,
        SessionModel(),
        hub,
        MinimalWebBodyAdapter(WebSocketBodyTransport()),
        privacy=Privacy.LOCAL_ONLY,
        tool_orchestrator=orchestrator,
        runtime_profile="candidate",
        auto_authorize=lambda: True,
    )
    await controller.startup()
    tasks = {s: asyncio.create_task(controller.respond(s, s)) for s in ("A", "B")}
    await asyncio.wait_for(asyncio.gather(*(e.wait() for e in entered.values())), 10)
    try:
        await controller.cancel("active", "stop A", session_id="A")
        await tasks["A"]
        assert cleaned == ["A"] and not tasks["B"].done()
        release["B"].set()
        await tasks["B"]
        assert effects == ["B"]
        for session, state in (("A", "cancelled"), ("B", "completed")):
            readback = await controller.recovery_readback(session)
            assert readback is not None and readback["state"] == state
    finally:
        for event in release.values():
            event.set()
        await asyncio.gather(*tasks.values(), return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["start", "launch", "close_failure"])
async def test_browser_startup_cancel_and_close_failure_always_stops_playwright(
    monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    from siro.adapters import browser as module

    entered, release = asyncio.Event(), asyncio.Event()
    closed: list[str] = []

    class Page:
        async def route(self, *args: object) -> None:
            pass

    class Browser:
        async def new_page(self) -> Page:
            return Page()

        async def close(self) -> None:
            closed.append("browser")
            if stage == "close_failure":
                raise RuntimeError("synthetic browser close refused")

    class Playwright:
        def __init__(self) -> None:
            self.chromium = self

        async def launch(self, **kwargs: object) -> Browser:
            if stage == "launch":
                entered.set()
                await release.wait()
            return Browser()

        async def stop(self) -> None:
            closed.append("playwright")

    class Manager:
        async def start(self) -> Playwright:
            if stage == "start":
                entered.set()
                await release.wait()
            return Playwright()

    monkeypatch.setattr("shutil.which", lambda name: "/synthetic/chromium")
    monkeypatch.setattr(module, "async_playwright", lambda: Manager())
    driver = module.ScopedBrowserDriver(("http://127.0.0.1",))
    if stage == "close_failure":
        await driver.__aenter__()
        with pytest.raises(RuntimeError, match="close refused"):
            await driver.__aexit__()
        assert closed == ["browser", "playwright"]
    else:
        task = asyncio.create_task(driver.__aenter__())
        await entered.wait()
        task.cancel()
        await asyncio.sleep(0)
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert closed == (["playwright"] if stage == "start" else ["browser", "playwright"])

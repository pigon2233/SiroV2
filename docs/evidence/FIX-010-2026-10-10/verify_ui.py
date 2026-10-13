"""Real Chromium/HTTP/WebSocket unknown-effect approval check with synthetic data."""

from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
import socket
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

import httpx
import uvicorn
from playwright.async_api import async_playwright, expect

from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
from siro.persistence.sqlite import SQLiteStore
from siro.ports.models import Privacy, ToolCall
from siro.services.agent.runs import SQLiteAgentRunRepository
from siro.services.presentation.gateway import (
    ClientChannel,
    GatewayHub,
    GatewayState,
    JsonSocket,
    create_app,
)
from siro.services.presentation.integrated import IntegratedCompanion
from siro.services.tools.orchestrator import (
    ProposalState,
    SQLiteToolProposalRepository,
    ToolOrchestrator,
)

REPOSITORY = Path(__file__).resolve().parents[3]
OUTPUT = Path(__file__).resolve().parent
SOURCE_FILES = (
    "src/siro/services/tools/orchestrator.py",
    "src/siro/services/presentation/gateway.py",
    "src/siro/services/presentation/integrated.py",
    "src/siro/services/presentation/static/index.html",
    "tests/integration/test_unknown_effect_approval.py",
)

# These helpers create a temporary DB and a pure counter executor, never OS effects.
sys.path.insert(0, str(REPOSITORY / "tests" / "integration"))
from test_unknown_effect_approval import ARGS, CounterModel, Fixture, prior_call  # noqa: E402


def hashes() -> dict[str, str]:
    return {
        name: hashlib.sha256((REPOSITORY / name).read_bytes()).hexdigest() for name in SOURCE_FILES
    }


class RecordingLiveHub(GatewayHub):
    """Record safe synthetic events while retaining the actual gateway writer path."""

    def __init__(self) -> None:
        super().__init__()
        self.events: list[dict[str, object]] = []
        self.connections = 0

    async def broadcast(self, payload: dict[str, object], *, urgent: bool = False) -> None:
        self.events.append(payload.copy())
        await super().broadcast(payload, urgent=urgent)

    async def connect(self, channel: JsonSocket, snapshot: dict[str, object]) -> ClientChannel:
        self.connections += 1
        return await super().connect(channel, snapshot)


async def wait_until(predicate: Callable[[], bool], *, timeout: float = 8) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            raise TimeoutError("Synthetic acceptance condition was not reached")
        await asyncio.sleep(0.02)


async def counter_fixture(directory: Path) -> Fixture:
    store = SQLiteStore(directory / "siro.db")
    await store.initialize()
    effects: list[dict[str, object]] = []

    async def counter(arguments: dict[str, object]) -> object:
        effects.append(arguments.copy())
        # Match the existing computer.execute observation shape without spawning a process.
        return {
            "returncode": 0,
            "stdout": "合成計數器已確認一次\uff1b沒有執行電腦命令。",
            "stderr": "",
            "truncated": False,
        }

    proposals = SQLiteToolProposalRepository(store)
    return Fixture(
        store,
        SQLiteAgentRunRepository(store),
        proposals,
        ToolOrchestrator(proposals, {"computer.execute": counter}),
        effects,
    )


async def verify() -> dict[str, object]:
    checks: dict[str, bool] = {}
    result: dict[str, object] = {
        "started_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "scope": "Real Chromium, current index.html, actual gateway HTTP/WebSocket and "
        "IntegratedCompanion; synthetic prior unknown-effect journal and counter-only executor.",
        "limitations": [
            "No access to production port 8026, private DB, keys, reference audio or voice cache.",
            "No real provider, OS tool effect, microphone, speech completion or Live2D acceptance.",
            "Reconnect means the same loaded page reconnecting its WebSocket; page reload "
            "restoration of pending proposal cards is not verified.",
            "The gateway active-turn snapshot may mark the request completed while the "
            "agent run is waiting_tool; that existing lifecycle discrepancy is not repaired here.",
        ],
        "source_sha256_start": hashes(),
        "checks": checks,
    }
    page_errors: list[str] = []
    browser_closed = False
    server_stopped = False
    temporary_path: Path | None = None
    server: uvicorn.Server | None = None
    server_task: asyncio.Task[None] | None = None
    listener: socket.socket | None = None
    approval_http_requests = 0
    try:
        with tempfile.TemporaryDirectory(prefix="siro-fix010-browser-") as directory:
            temporary_path = Path(directory)
            fixture = await counter_fixture(temporary_path)
            hub, transport = RecordingLiveHub(), WebSocketBodyTransport()
            model = CounterModel((ToolCall("fresh-held", "computer.execute", ARGS.copy()),))
            state = GatewayState(
                routes={"model": "synthetic:counter", "audio": "disabled", "body": "synthetic"},
                authorization_mode="full",
            )
            controller = IntegratedCompanion(
                temporary_path,
                model,
                hub,
                MinimalWebBodyAdapter(transport),
                privacy=Privacy.LOCAL_ONLY,
                tool_orchestrator=fixture.orchestrator,
                runtime_profile="candidate",
                auto_authorize=lambda: (
                    state.authorization_mode == "full" and state.kill_switches["tools"]
                ),
            )
            # Reconcile the empty temporary DB before adding the diagnostic prior journal.
            await controller.startup()
            prior_run_id, prior_proposal = await prior_call(fixture, session="browser")
            assert prior_proposal is not None

            async def prior_receipt() -> tuple[tuple[object, ...], ...]:
                rows = await fixture.store.run_transaction(
                    lambda connection: connection.execute(
                        "SELECT j.status,c.dispatched,c.observation_json "
                        "FROM run_journal j JOIN run_journal_calls c ON c.run_id=j.run_id "
                        "WHERE j.run_id=?",
                        (prior_run_id,),
                    ).fetchall()
                )
                return tuple(tuple(row) for row in rows)

            original_prior_receipt = await prior_receipt()
            assert len(original_prior_receipt) == 1
            assert json.loads(str(original_prior_receipt[0][2]))["error"] == "outcome_unknown"

            async def cancel(turn_id: str, reason: str) -> None:
                await controller.cancel(turn_id, reason, session_id="browser")

            async def shutdown() -> None:
                await cancel("active", "synthetic acceptance cleanup")

            listener = socket.socket()
            listener.bind(("127.0.0.1", 0))
            listener.listen(128)
            port = int(listener.getsockname()[1])
            assert port != 8026
            origin = f"http://127.0.0.1:{port}"
            result["synthetic_server_origin"] = origin
            app = create_app(
                allowed_origins={origin},
                state=state,
                hub=hub,
                body_transport=transport,
                on_turn=controller.respond,
                on_cancel=cancel,
                on_tool_result=controller.continue_after_tool,
                on_recovery=controller.recovery_readback,
                on_shutdown=shutdown,
                tool_orchestrator=fixture.orchestrator,
                runtime_profile="candidate",
                configuration_source="synthetic-fix010-browser-verification",
            )
            server = uvicorn.Server(uvicorn.Config(app, log_level="warning", lifespan="on"))
            server_task = asyncio.create_task(server.serve(sockets=[listener]))
            await wait_until(lambda: server is not None and server.started)

            async with httpx.AsyncClient(base_url=origin, timeout=8) as client:
                unauthenticated = await client.get("/v1/runtime")
                checks["unauthenticated_runtime_401"] = unauthenticated.status_code == 401
                bootstrap = await client.post("/v1/session", headers={"Origin": origin})
                bootstrap.raise_for_status()
                # The token remains in memory and is never included in saved evidence or logs.
                auth = {"Authorization": "Bearer " + bootstrap.json()["token"]}
                executable = shutil.which("google-chrome") or shutil.which("chromium")
                if executable is None:
                    raise RuntimeError("Real Chromium unavailable")
                result["browser_executable"] = executable
                async with async_playwright() as playwright:
                    browser = await playwright.chromium.launch(
                        executable_path=executable,
                        headless=True,
                        args=["--disable-gpu", "--no-sandbox"],
                    )
                    result["browser_version"] = browser.version
                    try:
                        context = await browser.new_context(
                            viewport={"width": 1440, "height": 1080}
                        )
                        page = await context.new_page()
                        page.on("pageerror", lambda error: page_errors.append(type(error).__name__))

                        def observe_request(request: object) -> None:
                            nonlocal approval_http_requests
                            url = getattr(request, "url", "")
                            if (
                                getattr(request, "method", "") == "POST"
                                and "/v1/tool-proposals/" in url
                                and url.endswith("/approve")
                            ):
                                approval_http_requests += 1

                        page.on("request", observe_request)
                        await page.goto(origin, wait_until="domcontentloaded")
                        await expect(page.locator("#connection")).to_have_text("已連線")
                        await expect(page.locator("#authorization-status")).to_contain_text(
                            "完整權限模式"
                        )
                        await page.locator("#text").fill("請重做剛才的合成操作")
                        await page.locator("#chat button[type=submit]").click()
                        cards = page.locator("#tool-proposals .proposal")
                        await expect(cards).to_have_count(1)
                        card = cards.first
                        await expect(card).to_contain_text("先前操作的結果未確認")
                        manual = card.get_by_role(
                            "button", name="確認結果後\uff0c授權這一次", exact=True
                        )
                        await expect(manual).to_be_enabled()
                        checks["full_mode_displays_unknown_warning_and_manual_button"] = True
                        checks["held_card_does_not_claim_auto_approval"] = (
                            "已自動授權" not in await card.inner_text()
                        )
                        fresh_events = [
                            event
                            for event in hub.events
                            if event.get("type") == "tool_proposal"
                            and event.get("call_id") == "fresh-held"
                        ]
                        assert len(fresh_events) == 1
                        proposal_id = str(fresh_events[0]["proposal_id"])
                        pending = await fixture.orchestrator.get(proposal_id)
                        assert pending is not None
                        checks["fresh_uuid_same_arguments_is_pending"] = (
                            proposal_id != prior_proposal.proposal_id
                            and pending.arguments_hash == prior_proposal.arguments_hash
                            and pending.state is ProposalState.PENDING
                        )
                        checks["first_proposal_event_contains_hold_once"] = (
                            fresh_events[0].get("automatic_approval_blocked")
                            == "prior_outcome_unknown"
                        )
                        checks["no_effect_or_started_event_before_owner_action"] = (
                            not fixture.effects
                            and not any(event.get("type") == "tool_started" for event in hub.events)
                            and approval_http_requests == 0
                            and len(model.requests) == 1
                        )
                        readback = await client.get("/v1/agent-runs/browser", headers=auth)
                        readback.raise_for_status()
                        result["agent_run_state_before_approval"] = readback.json().get("state")
                        checks["agent_run_waits_for_tool"] = (
                            result["agent_run_state_before_approval"] == "waiting_tool"
                        )
                        await page.locator("#computer-panel").screenshot(
                            path=str(OUTPUT / "unknown-effect-held.png")
                        )

                        unauth = await client.post(
                            f"/v1/tool-proposals/{proposal_id}/approve", json={"approved": True}
                        )
                        checks["unauthenticated_manual_approval_401"] = unauth.status_code == 401
                        disabled = await client.put(
                            "/v1/kill-switches/tools", headers=auth, json={"enabled": False}
                        )
                        disabled.raise_for_status()
                        blocked = await client.post(
                            f"/v1/tool-proposals/{proposal_id}/approve",
                            headers=auth,
                            json={"approved": True},
                        )
                        checks["tools_disabled_manual_approval_403_without_effect"] = (
                            blocked.status_code == 403 and not fixture.effects
                        )
                        enabled = await client.put(
                            "/v1/kill-switches/tools", headers=auth, json={"enabled": True}
                        )
                        enabled.raise_for_status()

                        connections_before = hub.connections
                        await page.evaluate("socket.close()")
                        await wait_until(lambda: hub.connections > connections_before)
                        await expect(page.locator("#connection")).to_have_text("已連線")
                        await expect(cards).to_have_count(1)
                        await expect(manual).to_be_enabled()
                        checks["websocket_reconnect_preserves_pending_card"] = True
                        checks["reconnect_has_no_effect_model_retry_or_approval_post"] = (
                            not fixture.effects
                            and len(model.requests) == 1
                            and approval_http_requests == 0
                            and len(
                                [
                                    event
                                    for event in hub.events
                                    if event.get("type") == "tool_proposal"
                                ]
                            )
                            == 1
                        )
                        async with page.expect_response(
                            lambda response: (
                                response.url.endswith(f"/v1/tool-proposals/{proposal_id}/approve")
                                and response.request.method == "POST"
                            )
                        ) as response_info:
                            await manual.click()
                        response = await response_info.value
                        checks["explicit_manual_button_returns_completed"] = (
                            response.status == 200
                            and (await response.json()).get("status") == "completed"
                        )
                        await expect(manual).to_be_disabled()
                        await expect(card).to_contain_text("完成")
                        await wait_until(
                            lambda: any(
                                event.get("type") == "assistant_terminal" for event in hub.events
                            )
                        )
                        completed = await fixture.orchestrator.get(proposal_id)
                        checks["manual_action_executes_counter_exactly_once"] = (
                            fixture.effects == [ARGS]
                            and approval_http_requests == 1
                            and completed is not None
                            and completed.state is ProposalState.COMPLETED
                            and len(model.requests) == 2
                        )
                        terminals = [
                            event
                            for event in hub.events
                            if event.get("type") == "assistant_terminal"
                        ]
                        checks["single_completed_terminal_after_manual_action"] = (
                            len(terminals) == 1 and terminals[0].get("state") == "completed"
                        )
                        duplicate = await client.post(
                            f"/v1/tool-proposals/{proposal_id}/approve",
                            headers=auth,
                            json={"approved": True},
                        )
                        checks["duplicate_post_404_without_second_effect"] = (
                            duplicate.status_code == 404
                            and fixture.effects == [ARGS]
                            and len(model.requests) == 2
                        )
                        prior_rows = await prior_receipt()
                        checks["prior_unknown_journal_not_resolved_or_deleted"] = (
                            len(prior_rows) == 1
                            and prior_rows == original_prior_receipt
                            and prior_rows[0][0] in {"terminal", "interrupted"}
                            and prior_rows[0][1] == 1
                        )
                        await page.locator("#computer-panel").screenshot(
                            path=str(OUTPUT / "unknown-effect-approved.png")
                        )
                        result["event_counts"] = {
                            name: sum(event.get("type") == name for event in hub.events)
                            for name in (
                                "tool_proposal",
                                "tool_started",
                                "tool_result",
                                "assistant_terminal",
                            )
                        }
                        result["model_requests"] = len(model.requests)
                        result["counter_effects"] = len(fixture.effects)
                        result["browser_manual_approval_http_requests"] = approval_http_requests
                        result["websocket_connections"] = hub.connections
                        result["page_error_types"] = page_errors
                        checks["no_browser_script_errors"] = not page_errors
                    finally:
                        await browser.close()
                        browser_closed = True
                server.should_exit = True
                await asyncio.wait_for(server_task, timeout=10)
                server_stopped = True
            listener.close()
            listener = None
        checks["temporary_database_removed"] = (
            temporary_path is not None and not temporary_path.exists()
        )
    except Exception as error:
        # Messages/tracebacks may contain transport secrets; save only the exception class.
        result["error_type"] = type(error).__name__
    finally:
        if server is not None and not server_stopped:
            server.should_exit = True
        if server_task is not None and not server_task.done():
            try:
                await asyncio.wait_for(server_task, timeout=10)
                server_stopped = True
            except TimeoutError:
                server_task.cancel()
                await asyncio.gather(server_task, return_exceptions=True)
        if listener is not None:
            listener.close()
        checks["browser_closed"] = browser_closed
        checks["server_stopped"] = server_stopped
        result["source_sha256_finish"] = hashes()
        checks["same_production_source"] = (
            result["source_sha256_start"] == result["source_sha256_finish"]
        )
        result["status"] = "PASS" if all(checks.values()) and "error_type" not in result else "FAIL"
        result["completed_at_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return result


if __name__ == "__main__":
    evidence = asyncio.run(verify())
    (OUTPUT / "ui-verification.json").write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False) + "\n"
    )
    print(json.dumps(evidence, indent=2, ensure_ascii=False))
    raise SystemExit(0 if evidence["status"] == "PASS" else 1)

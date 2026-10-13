"""Real Chrome/HTTP capability-panel check using a temporary synthetic catalog and DB."""

from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
import socket
import tempfile
import time
from pathlib import Path

import httpx
import uvicorn
from playwright.async_api import async_playwright, expect

from siro.persistence.sqlite import SQLiteStore
from siro.ports.models import ToolDefinition
from siro.services.presentation.gateway import GatewayState, create_app
from siro.services.tools.orchestrator import (
    AvailabilityReason,
    AvailabilityState,
    SQLiteToolProposalRepository,
    ToolAvailability,
    ToolCatalog,
    ToolDescriptor,
    ToolMetadata,
    ToolOrchestrator,
)

REPOSITORY = Path(__file__).resolve().parents[3]
OUTPUT = Path(__file__).resolve().parent
SOURCE_FILES = (
    "src/siro/services/tools/orchestrator.py",
    "src/siro/services/presentation/gateway.py",
    "src/siro/services/presentation/integrated.py",
    "src/siro/services/presentation/static/index.html",
)


def hashes() -> dict[str, str]:
    return {
        name: hashlib.sha256((REPOSITORY / name).read_bytes()).hexdigest() for name in SOURCE_FILES
    }


async def verify() -> dict[str, object]:
    result: dict[str, object] = {
        "started_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "scope": "Real Chrome, real loopback HTTP/WebSocket and current index.html; "
        "temporary synthetic SQLite and capability readiness only",
        "limitations": [
            "No model provider, tool execution, GPU, microphone, audio or Live2D validation.",
            "No access to production port 8026, private DB, reference audio or voice cache.",
        ],
        "source_sha256_start": hashes(),
        "checks": {},
    }
    checks: dict[str, bool] = {}
    result["checks"] = checks
    page_errors: list[str] = []
    executor_calls: list[dict[str, object]] = []
    browser_ready = False
    server: uvicorn.Server | None = None
    server_task: asyncio.Task[None] | None = None
    listener: socket.socket | None = None
    browser_closed = False
    server_stopped = False
    temporary_path: Path | None = None

    async def forbidden_executor(arguments: dict[str, object]) -> object:
        executor_calls.append(arguments)
        raise AssertionError("Capability discovery invoked an executor")

    try:
        with tempfile.TemporaryDirectory(prefix="siro-ri002-chrome-") as directory:
            temporary_path = Path(directory)
            store = SQLiteStore(temporary_path / "synthetic.db")
            await store.initialize()
            state = GatewayState(routes={"model": "synthetic:no-inference", "body": "disabled"})

            def readiness(name: str) -> ToolAvailability:
                if not state.kill_switches["tools"]:
                    return ToolAvailability(
                        AvailabilityState.UNAVAILABLE, AvailabilityReason.TOOLS_DISABLED
                    )
                if name == "browser.read" and not browser_ready:
                    return ToolAvailability(
                        AvailabilityState.UNAVAILABLE,
                        AvailabilityReason.BROWSER_EXECUTABLE_MISSING,
                    )
                return ToolAvailability(AvailabilityState.AVAILABLE, AvailabilityReason.READY)

            labels = {
                "computer.execute": "查看與操作電腦",
                "browser.read": "查看目前網頁",
                "synthetic.metadata": '<img src=x onerror="window.__capabilityInjected=1">',
            }
            catalog = ToolCatalog(
                tuple(
                    ToolDescriptor(
                        name,
                        ToolDefinition(
                            name,
                            "Synthetic capability; discovery must not execute it.",
                            {"type": "object", "properties": {}, "additionalProperties": False},
                        ),
                        forbidden_executor,
                        available=lambda name=name: readiness(name),
                        backend="synthetic",
                        effect="computer" if name == "computer.execute" else "read",
                        metadata=ToolMetadata(
                            display_name=label,
                            required_permissions=("synthetic.only",),
                            risk_level="computer"
                            if name == "computer.execute"
                            else "observe/read-only",
                            version="synthetic-1",
                            provenance="RI-002 synthetic verification fixture",
                        ),
                    )
                    for name, label in labels.items()
                )
            )
            orchestrator = ToolOrchestrator(
                SQLiteToolProposalRepository(store), {}, catalog=catalog
            )
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
                tool_orchestrator=orchestrator,
                runtime_profile="candidate",
                configuration_source="synthetic-browser-verification",
            )
            server = uvicorn.Server(uvicorn.Config(app, log_level="warning", lifespan="on"))
            server_task = asyncio.create_task(server.serve(sockets=[listener]))
            deadline = time.monotonic() + 8
            while not server.started:
                if server_task.done():
                    await server_task
                    raise RuntimeError("Synthetic HTTP server stopped before readiness")
                if time.monotonic() >= deadline:
                    raise TimeoutError("Synthetic HTTP server startup")
                await asyncio.sleep(0.05)

            async with httpx.AsyncClient(base_url=origin, timeout=5) as client:
                unauthenticated = await client.get("/v1/runtime")
                checks["unauthenticated_runtime_401"] = unauthenticated.status_code == 401
                bootstrap = await client.post("/v1/session", headers={"Origin": origin})
                bootstrap.raise_for_status()
                # Tokens are used locally only, never written to evidence or logs.
                headers = {"Authorization": "Bearer " + bootstrap.json()["token"]}
                executable = shutil.which("google-chrome") or shutil.which("chromium")
                if executable is None:
                    raise RuntimeError("Real Chrome/Chromium unavailable")
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
                        page.on("pageerror", lambda error: page_errors.append(str(error)))
                        await page.add_init_script("window.__capabilityInjected = 0;")
                        await page.goto(origin, wait_until="domcontentloaded")
                        await page.get_by_text("電腦協助", exact=True).click()
                        await page.get_by_text("我現在能做什麼", exact=True).click()
                        cards = page.locator("#capability-items .proposal")
                        await expect(cards).to_have_count(3)
                        computer = cards.filter(has_text=labels["computer.execute"])
                        web = cards.filter(has_text=labels["browser.read"])
                        await expect(computer).to_contain_text("目前可用")
                        await expect(web).to_contain_text("尚未找到可用的瀏覽器")
                        checks["initial_available_and_safe_unavailable_reason"] = True
                        checks["html_metadata_is_literal_text"] = (
                            await page.locator("#capability-items img").count() == 0
                            and await page.evaluate("window.__capabilityInjected") == 0
                            and any(
                                labels["synthetic.metadata"] in text
                                for text in await cards.all_text_contents()
                            )
                        )
                        await page.locator("#computer-panel").screenshot(
                            path=str(OUTPUT / "capability-panel.png")
                        )
                        result["initial_panel_text"] = await cards.all_text_contents()

                        browser_ready = True
                        await page.get_by_role("button", name="更新能力狀態", exact=True).click()
                        await expect(web).to_contain_text("目前可用")
                        checks["manual_refresh_observes_readiness_change"] = True

                        disabled = await client.put(
                            "/v1/kill-switches/tools", headers=headers, json={"enabled": False}
                        )
                        disabled.raise_for_status()
                        await page.get_by_role("button", name="更新能力狀態", exact=True).click()
                        await expect(cards).to_have_count(3)
                        for card in await cards.all():
                            await expect(card).to_contain_text("你已暫停電腦操作")
                        checks["disabled_refresh_removes_old_available_status"] = (
                            "目前可用" not in await page.locator("#capability-items").inner_text()
                        )
                        result["disabled_panel_text"] = await cards.all_text_contents()

                        restored = await client.put(
                            "/v1/kill-switches/tools", headers=headers, json={"enabled": True}
                        )
                        restored.raise_for_status()
                        await page.get_by_role("button", name="更新能力狀態", exact=True).click()
                        for card in await cards.all():
                            await expect(card).to_contain_text("目前可用")
                        checks["reenabled_refresh_restores_current_state"] = True
                        result["restored_panel_text"] = await cards.all_text_contents()
                        checks["no_injected_script_after_all_refreshes"] = (
                            await page.evaluate("window.__capabilityInjected") == 0
                            and await page.locator("#capability-items img").count() == 0
                        )
                        checks["executors_never_called"] = not executor_calls
                        checks["no_page_errors"] = not page_errors
                        result["page_errors"] = page_errors
                        result["executor_calls"] = len(executor_calls)
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
        result["error"] = {"type": type(error).__name__, "message": str(error)}
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
        result["status"] = "PASS" if all(checks.values()) and "error" not in result else "FAIL"
        result["completed_at_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return result


if __name__ == "__main__":
    evidence = asyncio.run(verify())
    (OUTPUT / "ui-verification.json").write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False) + "\n"
    )
    print(json.dumps(evidence, indent=2, ensure_ascii=False))
    raise SystemExit(0 if evidence["status"] == "PASS" else 1)

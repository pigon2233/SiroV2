"""Bounded configured-provider -> real Bing -> native continuation acceptance.

This is an opt-in evidence probe, not production logic. Only synthetic public
input is sent. The only eligible approved target is the exact clean Bing URL.
Provider configuration is loaded internally and never written to evidence.
"""

# ruff: noqa: RUF001 — The synthetic owner prompt intentionally uses Chinese punctuation.

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
import tempfile
import time
from collections.abc import AsyncIterator
from dataclasses import replace
from pathlib import Path
from urllib.parse import urlsplit

from siro.adapters.body.web import MinimalWebBodyAdapter, WebSocketBodyTransport
from siro.adapters.browser import BrowserScopeViolation, ScopedBrowserDriver
from siro.adapters.models.openai_compatible import OpenAICompatibleAdapter
from siro.core.authorization import argument_hash
from siro.persistence.sqlite import SQLiteStore
from siro.ports.models import CancellationToken, ModelChunk, ModelRequest, Privacy
from siro.services.presentation.gateway import GatewayHub
from siro.services.presentation.integrated import IntegratedCompanion
from siro.services.tools.browser_session import BrowserSessions
from siro.services.tools.execution import ExecutionContext
from siro.services.tools.orchestrator import (
    DEFAULT_MODEL_TOOLS,
    ProposalState,
    SQLiteToolProposalRepository,
    ToolCatalog,
    ToolDescriptor,
    ToolMetadata,
    ToolOrchestrator,
)

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
IS_DUCKDUCKGO = "--duckduckgo" in sys.argv
PUBLIC_URL = (
    "https://html.duckduckgo.com/html/?q=Python+asyncio+documentation"
    if IS_DUCKDUCKGO
    else "https://www.bing.com/search?q=Python+asyncio+documentation"
)
MODEL_LIMIT = 2 if IS_DUCKDUCKGO else 4
REPORT_NAME = "public-search-duckduckgo" if IS_DUCKDUCKGO else "public-search-acceptance"
SOURCES = (
    "src/siro/adapters/browser.py",
    "src/siro/services/tools/browser_session.py",
    "src/siro/services/tools/orchestrator.py",
    "src/siro/services/presentation/integrated.py",
    "src/siro/adapters/models/openai_compatible.py",
)


def source_hashes() -> dict[str, str]:
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCES}


def safe_error(error: BaseException) -> dict[str, object]:
    return {
        "error": "ScopeViolation"
        if isinstance(error, BrowserScopeViolation)
        else type(error).__name__,
        **({"reason": error.reason.value} if isinstance(error, BrowserScopeViolation) else {}),
    }


def load_model() -> OpenAICompatibleAdapter:
    allowed = {"SIRO_OPENAI_BASE_URL", "SIRO_OPENAI_MODEL", "SIRO_OPENAI_API_KEY"}
    for line in (ROOT / ".env.local").read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.removeprefix("export ").split("=", 1)
            if key.strip() in allowed:
                os.environ.setdefault(key.strip(), value.strip().strip("\"'"))
    return OpenAICompatibleAdapter(
        base_url=os.environ["SIRO_OPENAI_BASE_URL"],
        api_key=os.environ["SIRO_OPENAI_API_KEY"],
        model=os.environ["SIRO_OPENAI_MODEL"],
        timeout=30,
    )


class RecordingModel:
    name = "openai-compatible"

    def __init__(self, model: OpenAICompatibleAdapter) -> None:
        self.model = model
        self.requests: list[ModelRequest] = []

    async def stream(
        self, request: ModelRequest, cancellation: CancellationToken
    ) -> AsyncIterator[ModelChunk]:
        if len(self.requests) >= MODEL_LIMIT:
            raise RuntimeError("synthetic model round limit")
        self.requests.append(request)
        async for chunk in self.model.stream(request, cancellation):
            yield chunk


class RecordingHub(GatewayHub):
    def __init__(self) -> None:
        super().__init__()
        self.events: list[dict[str, object]] = []

    async def broadcast(self, payload: dict[str, object], *, urgent: bool = False) -> None:
        self.events.append(payload)


async def direct_browser_probe() -> dict[str, object]:
    start = time.monotonic()
    result: dict[str, object] = {"target": PUBLIC_URL, "actual_browser": True}
    try:
        async with asyncio.timeout(30):
            parsed = urlsplit(PUBLIC_URL)
            async with ScopedBrowserDriver((f"{parsed.scheme}://{parsed.netloc}",)) as driver:
                observation = await driver.navigate(PUBLIC_URL)
                result.update(
                    url=observation.url,
                    title=observation.title,
                    public_text_excerpt=observation.text[:1600],
                    text_characters=len(observation.text),
                    partial=observation.blocked_resources,
                    reason="subresource_denied" if observation.blocked_resources else None,
                    captcha_suspected=any(
                        item in observation.text.lower()
                        for item in (
                            "captcha",
                            "verify you are human",
                            "one last step",
                            "confirm this search was made by a human",
                            "select all squares",
                        )
                    ),
                )
                # Read-only diagnostic: distinguish early DOM read from resources blocked.
                delayed = []
                for delay in () if IS_DUCKDUCKGO else (1, 2):
                    await asyncio.sleep(delay)
                    later = await driver.observe()
                    delayed.append(
                        {
                            "after_seconds": sum((1, 2)[: len(delayed) + 1]),
                            "text_characters": len(later.text),
                            "public_text_excerpt": later.text[:2000],
                            "partial": later.blocked_resources,
                            "search_result_visible": "asyncio" in later.text.lower(),
                        }
                    )
                result["read_only_delayed_observations"] = delayed
    except BaseException as error:
        result.update(safe_error(error))
    result["seconds"] = round(time.monotonic() - start, 3)
    return result


async def configured_product_probe() -> dict[str, object]:
    started = time.monotonic()
    result: dict[str, object] = {
        "actual_configured_provider": True,
        "actual_browser": True,
        "private_inputs": False,
        "max_model_rounds": MODEL_LIMIT,
        "max_seconds": 180,
        "tool": "browser.navigate+read",
        "target": PUBLIC_URL,
    }
    model = RecordingModel(load_model())
    hub = RecordingHub()
    sessions = BrowserSessions(ScopedBrowserDriver, timeout=30, capacity=1)
    exact_bindings: list[bool] = []
    dispatches = 0
    approved: set[str] = set()
    observations: list[dict[str, object]] = []
    controller: IntegratedCompanion | None = None
    session_id = "synthetic-public-search-fix002"

    async def no_legacy(arguments: dict[str, object]) -> object:
        raise RuntimeError("legacy executor not eligible in synthetic candidate probe")

    async def execute(arguments: dict[str, object], context: ExecutionContext) -> object:
        nonlocal dispatches
        if arguments != {"url": PUBLIC_URL}:
            raise PermissionError("synthetic probe requires exact public search URL")
        dispatches += 1
        return await sessions.execute(
            "navigate+read",
            arguments,
            replace(context, deadline=asyncio.get_running_loop().time() + 30),
        )

    with tempfile.TemporaryDirectory(prefix="siro-fix002-public-") as temporary:
        directory = Path(temporary)
        store = SQLiteStore(directory / "siro.db")
        await store.initialize()
        catalog = ToolCatalog(
            (
                ToolDescriptor(
                    "browser.navigate+read",
                    DEFAULT_MODEL_TOOLS[0],
                    no_legacy,
                    lambda: True,
                    "python.browser.session",
                    "observe",
                    contextual_executor=execute,
                    metadata=ToolMetadata(display_name="開啟並讀取頁面", timeout_seconds=30),
                ),
            )
        )
        orchestrator = ToolOrchestrator(
            SQLiteToolProposalRepository(store),
            {"browser.navigate+read": no_legacy},
            catalog=catalog,
        )
        controller = IntegratedCompanion(
            directory,
            model,
            hub,
            MinimalWebBodyAdapter(WebSocketBodyTransport()),
            privacy=Privacy.CLOUD_ALLOWED,
            tool_orchestrator=orchestrator,
            runtime_profile="candidate",
            auto_authorize=lambda: False,
            max_agent_steps=MODEL_LIMIT,
            session_restore_enabled=False,
            memory_ingress_enabled=False,
        )
        prompt = (
            "這是公開網路搜尋驗收，沒有私人資料。請先實際使用 browser.navigate+read "
            f"讀取這個完全相同的 URL：{PUBLIC_URL}。"
            "不要改網址，不要使用其他工具。收到結果後，僅根據可見頁面內容，"
            "用繁體中文說明是否找到了 Python asyncio 的官方文件，"
            "附上你實際讀取的搜尋頁 URL 作為來源。若讀取失敗或只看到驗證頁，"
            "清楚說明，不能假装已讀到文件；若部分資源遭擋，說明搜尋頁是部分載入。"
            "請簡短回答，這輪不需繼續開啟文件。"
        )
        try:
            async with asyncio.timeout(180):
                await controller.respond(session_id, prompt)
                while True:
                    pending = [
                        event
                        for event in hub.events
                        if event.get("type") == "tool_proposal"
                        and str(event["proposal_id"]) not in approved
                    ]
                    if not pending:
                        break
                    for event in pending:
                        proposal = await orchestrator.get(str(event["proposal_id"]))
                        assert proposal is not None
                        approved.add(proposal.proposal_id)
                        if proposal.capability != "browser.navigate+read" or proposal.arguments != {
                            "url": PUBLIC_URL
                        }:
                            denied = await orchestrator.resolve(
                                proposal.proposal_id,
                                approved=False,
                                arguments=proposal.arguments,
                            )
                            result["target_mismatch_denied"] = True
                            await controller.continue_after_tool(denied)
                            continue
                        bound = proposal.arguments_hash == argument_hash(proposal.arguments)
                        await orchestrator.resolve(
                            proposal.proposal_id,
                            approved=True,
                            arguments=proposal.arguments,
                        )
                        resolved = await orchestrator.execute(proposal.proposal_id)
                        exact_bindings.append(
                            bound and resolved.arguments_hash == argument_hash(proposal.arguments)
                        )
                        record: dict[str, object] = {
                            "state": resolved.state.value,
                            "error": resolved.error,
                            "capability": resolved.capability,
                        }
                        if isinstance(resolved.observation, dict):
                            record.update(
                                url=resolved.observation.get("url"),
                                title=resolved.observation.get("title"),
                                public_text_excerpt=str(resolved.observation.get("text", ""))[
                                    :2000
                                ],
                                load_status=resolved.observation.get("load_status"),
                                reason=resolved.observation.get("reason"),
                            )
                        observations.append(record)
                        await controller.continue_after_tool(resolved)
        except BaseException as error:
            result.update(safe_error(error))
        finally:
            if controller.foreground_active:
                try:
                    await controller.cancel(
                        "synthetic-public-search", "probe cleanup", session_id=session_id
                    )
                except BaseException as cleanup_error:
                    result["run_cleanup"] = safe_error(cleanup_error)
            try:
                await sessions.close()
                await hub.shutdown()
                result["owned_browser_pool_cleaned"] = True
            except BaseException as cleanup_error:
                result["browser_cleanup"] = safe_error(cleanup_error)
        terminals = [event for event in hub.events if event.get("type") == "assistant_terminal"]
        reply = "".join(
            str(event.get("text", ""))
            for event in hub.events
            if event.get("type") == "assistant_delta"
        )
        paired = []
        for request in model.requests[1:]:
            calls = {
                call.call_id
                for message in request.messages
                if message.role == "assistant"
                for call in message.tool_calls
            }
            results = [message for message in request.messages if message.role == "tool"]
            paired.append(
                bool(results) and all(message.tool_call_id in calls for message in results)
            )
        observed_ok = any(row.get("state") == ProposalState.COMPLETED.value for row in observations)
        search_result_visible = any(
            "asyncio" in str(row.get("public_text_excerpt", "")).lower()
            for row in observations
            if row.get("state") == ProposalState.COMPLETED.value
        )
        official_result_visible = any(
            "asyncio" in str(row.get("public_text_excerpt", "")).lower()
            and "docs.python.org" in str(row.get("public_text_excerpt", "")).lower()
            for row in observations
            if row.get("state") == ProposalState.COMPLETED.value
        )
        chain_ok = bool(
            observed_ok
            and dispatches > 0
            and len(model.requests) >= 2
            and paired
            and all(paired)
            and exact_bindings
            and all(exact_bindings)
            and len(terminals) == 1
            and terminals[0].get("state") == "completed"
            and PUBLIC_URL in reply
            and bool(reply)
            and result.get("owned_browser_pool_cleaned")
        )
        result.update(
            model_rounds=len(model.requests),
            model_message_roles=[
                [message.role for message in request.messages] for request in model.requests
            ],
            actual_tool_dispatches=dispatches,
            exact_approved_argument_bindings=exact_bindings,
            native_pairing_checks=paired,
            observations=observations,
            terminal_count=len(terminals),
            terminal_states=[event.get("state") for event in terminals],
            terminal_errors=[event.get("error") for event in terminals],
            natural_reply=reply[:6000],
            sourced_reply_has_search_url=PUBLIC_URL in reply,
            actual_page_read=observed_ok,
            native_chain_gate=chain_ok,
            search_result_visible=search_result_visible,
            official_result_text_visible=official_result_visible,
            official_link_href_verified=False,
            automatic_end_to_end_gate=chain_ok and official_result_visible,
            semantic_evaluation="Human inspection of the synthetic reply is recorded separately; "
            "a search-page source URL or navigation-only read does not establish useful results.",
        )
    result["temporary_data_removed"] = not directory.exists()
    result["seconds"] = round(time.monotonic() - started, 3)
    return result


async def main() -> bool:
    if "--run-configured-public" not in sys.argv:
        raise SystemExit("Explicit --run-configured-public required")
    hashes = source_hashes()
    report: dict[str, object] = {
        "synthetic_public_only": True,
        "never_touched_existing_service_or_private_data": True,
        "ui_voice_human_checks": "NOT_RUN",
        "source_sha256_before": hashes,
    }
    report["direct_browser"] = await direct_browser_probe()
    try:
        report["configured_product"] = await configured_product_probe()
    except BaseException as error:
        report["configured_product"] = safe_error(error)
    report["source_sha256_after"] = source_hashes()
    report["source_unchanged_during_probe"] = report["source_sha256_after"] == hashes
    text = json.dumps(report, ensure_ascii=False, indent=2)
    (EVIDENCE / (REPORT_NAME + ".json")).write_text(text + "\n")
    print(text)
    return bool(
        isinstance(report["configured_product"], dict)
        and report["configured_product"].get("automatic_end_to_end_gate")
        and report["source_unchanged_during_probe"]
    )


if __name__ == "__main__":
    raise SystemExit(not asyncio.run(main()))

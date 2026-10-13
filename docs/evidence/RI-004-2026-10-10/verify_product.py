"""Synthetic temporary HTTP → actual Chromium → fixed-template OS verification acceptance."""
from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
import socket
import tempfile
from pathlib import Path

import httpx
import uvicorn
from playwright.async_api import async_playwright, expect

from siro.services.presentation.gateway import create_app
from siro.services.tools import skill_candidates as backend
from siro.services.tools.orchestrator import ToolCatalog

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
SOURCES = (
    "src/siro/services/tools/skill_candidates.py",
    "src/siro/services/presentation/gateway.py",
    "src/siro/services/presentation/static/index.html",
)


def hashes():
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCES}


async def main():
    checks = {}
    errors = []
    before = hashes()
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    origin = f"http://127.0.0.1:{listener.getsockname()[1]}"
    owner = backend.SkillCandidatePreparer(ToolCatalog(()))
    original = backend.verify_isolated_patch
    gate = False
    entered = asyncio.Event()
    verified = 0

    async def controlled_verify(root, proposal, **kwargs):
        nonlocal verified
        if gate:
            entered.set()
            await asyncio.Event().wait()
        result = await original(root, proposal, **kwargs)
        verified += 1
        return result

    backend.verify_isolated_patch = controlled_verify
    app = create_app(
        allowed_origins={origin}, runtime_profile="candidate", skill_candidates=owner,
        configuration_source="synthetic-ri004-verification",
    )
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", lifespan="on"))
    serving = asyncio.create_task(server.serve(sockets=[listener]))
    browser = None
    temporary = None
    try:
        async with asyncio.timeout(5):
            while not server.started:
                await asyncio.sleep(0.01)
        async with httpx.AsyncClient(base_url=origin, timeout=10) as client:
            checks["no_token_401"] = (await client.post(
                "/v1/skills/candidates", headers={"Origin": origin},
                json={"capability": backend.CAPABILITY},
            )).status_code == 401
            session = await client.post("/v1/session", headers={"Origin": origin})
            auth = {"Origin": origin, "Authorization": "Bearer " + session.json()["token"]}
            checks["foreign_origin_403"] = (await client.post(
                "/v1/skills/candidates", headers={**auth, "Origin": "http://foreign.invalid"},
                json={"capability": backend.CAPABILITY},
            )).status_code == 403
            checks["unknown_template_no_candidate"] = (await client.post(
                "/v1/skills/candidates", headers=auth, json={"capability": "not.supported"},
            )).json()["status"] == "unsupported_capability"
            executable = shutil.which("google-chrome") or shutil.which("chromium")
            assert executable, "real Chromium required"
            with tempfile.TemporaryDirectory(prefix="siro-ri004-browser-") as directory:
                temporary = Path(directory)
                async with async_playwright() as playwright:
                    browser = await playwright.chromium.launch(
                        executable_path=executable, headless=True,
                        args=["--disable-gpu", "--no-sandbox"],
                    )
                    context = await browser.new_context(viewport={"width": 1440, "height": 1080})
                    page = await context.new_page()
                    page.on("pageerror", lambda error: errors.append(type(error).__name__))
                    requests = []
                    downloads = []
                    page.on("request", lambda request: requests.append(request.url)
                            if request.method == "POST" and request.url.endswith("/v1/skills/candidates") else None)
                    page.on("download", lambda download: downloads.append(download))
                    await page.goto(origin, wait_until="domcontentloaded")
                    await expect(page.locator("#connection")).to_have_text("已連線")
                    await page.locator("#computer-panel > summary").click()
                    prepare = page.locator("#skill-candidate-prepare")
                    await expect(prepare).to_be_enabled()
                    await prepare.evaluate("button => {button.click(); button.click();}")
                    await expect(page.locator("#skill-candidate-status")).to_have_text(
                        "待你審查；尚未安裝或啟用。", timeout=15000)
                    checks["double_click_one_http_request"] = len(requests) == 1
                    checks["actual_sandbox_pass"] = verified == 1
                    checks["no_auto_download"] = not downloads
                    async with page.expect_download() as download_info:
                        await page.locator("#skill-candidate-export").click()
                    download = await download_info.value
                    await download.save_as(temporary / "review.json")
                    report = json.loads((temporary / "review.json").read_text())
                    checks["export_actual_report"] = report["verification"]["status"] == "passed"
                    checks["export_four_files"] = set(report["files"]) == {
                        "manifest.json", "input.json", "output.json", "plugin.py"}
                    checks["no_authority_from_pass"] = (
                        report["enabled"] is False and report["installed"] is False
                        and report["authorizes_execution"] is False
                        and report["trust_level"] == "unreviewed" and report["approval_required"] is True)
                    checks["readonly_plain_source"] = "def run(arguments):" in await page.locator(
                        "#skill-candidate-files").text_content()
                    await page.screenshot(path=str(OUT / "review.png"), full_page=True)
                    gate = True
                    await prepare.click()
                    await asyncio.wait_for(entered.wait(), 2)
                    checks["runtime_busy"] = (await client.get("/v1/runtime", headers=auth)).json()[
                        "skill_candidates"]["busy"] is True
                    busy = await client.post("/v1/skills/candidates", headers=auth,
                                             json={"capability": backend.CAPABILITY})
                    checks["parallel_owner_busy_409"] = busy.status_code == 409
                    await page.locator("#skill-candidate-cancel").click()
                    await expect(page.locator("#skill-candidate-status")).to_have_text(
                        "已取消準備；尚未安裝或啟用。")
                    checks["cancel_joined_owner"] = not owner.busy
                    checks["cancel_no_stale_review"] = not await page.locator(
                        "#skill-candidate-review").text_content()
                    await expect(page.locator("#skill-candidate-export")).to_be_disabled()
                    entered.clear()
                    await prepare.click()
                    await asyncio.wait_for(entered.wait(), 2)
                    switched = await client.put("/v1/kill-switches/tools", headers=auth,
                                                json={"enabled": False})
                    checks["tools_off_cancel_joined"] = switched.status_code == 200 and not owner.busy
                    checks["tools_off_reject_403"] = (await client.post(
                        "/v1/skills/candidates", headers=auth,
                        json={"capability": backend.CAPABILITY},
                    )).status_code == 403
                    runtime = (await client.get("/v1/runtime", headers=auth)).json()
                    checks["tools_off_metadata"] = runtime["skill_candidates"]["available"] is False
                    await page.evaluate("async () => renderSkillCandidateAvailability(await productRequest('/v1/runtime'))")
                    await expect(prepare).to_be_disabled()
                    checks["tools_off_ui_disabled"] = True
                    checks["page_errors_zero"] = not errors
                    version = browser.version
                    await context.close()
                    await browser.close()
                    browser = None
    finally:
        backend.verify_isolated_patch = original
        if browser is not None:
            await browser.close()
        server.should_exit = True
        await asyncio.wait_for(serving, 8)
        listener.close()
    checks["owner_closed"] = owner._closed and not owner.busy
    checks["temporary_download_removed"] = temporary is not None and not temporary.exists()
    checks["source_unchanged_during_acceptance"] = before == hashes()
    checks["listener_closed"] = listener.fileno() == -1
    result = {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks,
              "browser_version": version, "source_sha256": before,
              "boundary": "real Chromium, temporary Gateway, actual fixed-template RI003 sandbox; cancellation timing gate synthetic",
              "private_data_read": False, "live_8026_restarted": False,
              "model_tts_registry_deployment_used": False}
    (OUT / "product.json").write_text(json.dumps(result, indent=2) + "\n")
    assert all(checks.values()), result
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

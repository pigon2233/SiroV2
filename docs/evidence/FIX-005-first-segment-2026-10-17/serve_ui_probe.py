"""Opt-in isolated current UI/Qwen probe; the owner operates the browser manually.

No LLM, private DB, original cache, microphone, cloud request or live service is used.
The main product script remains byte-identical; the added observer exposes only
native Audio lifecycle and TTS status in #voice-verification. Stop with SIGTERM.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import json
import os
import runpy
import signal
import socket
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import uvicorn

from siro.adapters.body.web import WebSocketBodyTransport
from siro.services.audio.tts import plan_speech
from siro.services.presentation.gateway import GatewayHub, GatewayState, SessionTokens, create_app

ROOT = Path(__file__).resolve().parents[3]


def qwen_pids() -> list[int]:
    result = []
    for path in Path("/proc").iterdir():
        if not path.name.isdecimal():
            continue
        try:
            arguments = (path / "cmdline").read_bytes().split(b"\0")
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
        if any(argument.endswith(b"/qwen_tts_worker.py") for argument in arguments):
            result.append(int(path.name))
    return sorted(result)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hashes() -> dict[str, str]:
    return {
        name: sha((ROOT / name).read_bytes())
        for name in (
            "scripts/qwen_tts_worker.py",
            "src/siro/services/audio/tts.py",
            "src/siro/services/presentation/gateway.py",
            "src/siro/services/presentation/static/index.html",
        )
    }


class OwnedServer(uvicorn.Server):
    @contextlib.contextmanager
    def capture_signals(self):
        # This harness owns SIGTERM so an active inference is cancelled before
        # Uvicorn waits for HTTP requests during graceful shutdown.
        yield


async def serve(output: Path) -> None:
    if qwen_pids():
        raise RuntimeError("existing Qwen owner; refusing another worker")
    query = subprocess.run(
        ["nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader"],
        capture_output=True,
        text=True,
        check=True,
    )
    if query.stdout.strip():
        raise RuntimeError("existing GPU compute owner; refusing another model")
    output.mkdir(parents=True, exist_ok=False)
    old = runpy.run_path(str(ROOT / "docs/evidence/FIX-005-2026-10-07/verify_real_voice.py"))
    source_script = (
        (ROOT / "src/siro/services/presentation/static/index.html")
        .read_text()
        .split("<script>", 1)[1]
        .split("</script>", 1)[0]
    )
    report: dict[str, Any] = {
        "status": "STARTING",
        "scope": "current UI/Gateway/Qwen; synthetic turns; manually operated browser",
        "human_listening": "NOT_RUN",
        "started_ms": old["now_ms"](),
        "source_hashes_start": hashes(),
        "main_ui_script_sha256": sha(source_script.encode()),
        "harness_sha256": sha(Path(__file__).read_bytes()),
        "turns": [],
        "jobs": [],
        "story_plan": plan_speech(old["STORY"]),
        "cancel_plan": plan_speech(old["CANCEL_TEXT"]),
        "browser_observation": "DOM-only #voice-verification; owner captures separately",
        "limits": [
            "EOS proves generation termination, not naturalness or semantic fidelity",
            "No automatic browser actions or automatic acceptance verdict",
            "Body is the explicit placeholder; this probe does not verify Live2D",
        ],
    }

    def save() -> None:
        pending = output / "report.pending.json"
        pending.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        pending.replace(output / "report.json")

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for name in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(name, stop.set)
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    listener.setblocking(False)
    port = listener.getsockname()[1]
    assert port not in (8000, 8026)
    origin = f"http://127.0.0.1:{port}"
    report["origin"] = origin
    tokens, hub, body = SessionTokens(), GatewayHub(), WebSocketBodyTransport()
    temporary = tempfile.TemporaryDirectory(prefix="siro-ui-qwen-cache-")

    class CUDAOnlyQwen(old["ObservedQwen"]):
        def _accept_ready(self, response):
            super()._accept_ready(response)
            if response.get("device") != "cuda:0":
                raise RuntimeError("expected CUDA; refusing CPU inference")

    speech = CUDAOnlyQwen(Path(temporary.name), output)
    speech.save_callback = save
    report["jobs"] = speech.jobs
    report["temporary_cache"] = temporary.name
    state = GatewayState()
    state.routes.update(
        model="synthetic:known-story", tts="qwen:ui-verification", body="placeholder"
    )

    async def on_turn(session_id, text, input_mode):
        del text, input_mode
        index = len(report["turns"])
        content = old["STORY"] if index == 0 else old["CANCEL_TEXT"]
        speech.case = "browser-story" if index == 0 else "cancel"
        speech.exchange_started.clear()
        report["turns"].append(
            {
                "index": index,
                "case": speech.case,
                "terminal_ms": old["now_ms"](),
                "content_sha256": sha(content.encode()),
            }
        )
        save()
        for event in (
            {"type": "assistant_started"},
            {"type": "assistant_delta", "text": content},
            {"type": "assistant_terminal", "state": "completed", "error": None},
        ):
            await hub.broadcast({**event, "session_id": session_id, "stream_id": f"probe-{index}"})

    app = create_app(
        allowed_origins={origin},
        state=state,
        hub=hub,
        tokens=tokens,
        body_transport=body,
        text_to_speech=speech,
        on_turn=on_turn,
        runtime_profile="candidate",
    )
    observer = (
        old["NATIVE_OBSERVER"]
        + r"""
addEventListener('DOMContentLoaded', () => {
  const target = document.querySelector('#voice-verification');
  window.__voiceProbe.cancel_clicks = [];
  document.querySelector('#cancel').addEventListener('click', () => {
    window.__voiceProbe.cancel_clicks.push({at_ms:Date.now()});
  }, {capture:true, passive:true});
  const update = () => { target.textContent = JSON.stringify(window.__voiceProbe); };
  update(); const timer = setInterval(update, 100);
  addEventListener('pagehide', () => clearInterval(timer), {once:true});
});
"""
    )

    class ObservedApp:
        async def __call__(self, scope, receive, send):
            if not (scope["type"] == "http" and scope["method"] == "GET" and scope["path"] == "/"):
                await app(scope, receive, send)
                return
            captured = []

            async def capture(message):
                captured.append(message)

            await app(scope, receive, capture)
            markup = b"".join(
                message.get("body", b"")
                for message in captured
                if message["type"] == "http.response.body"
            ).decode()
            assert source_script in markup
            markup = markup.replace(
                "<script>",
                '<pre id="voice-verification" aria-label="唯讀語音驗證資料" '
                'style="position:fixed;right:0;bottom:0;max-height:120px;max-width:440px;'
                "overflow:auto;background:white;color:black;font-size:9px;z-index:99;"
                'pointer-events:none"></pre>'
                "<script>" + observer + "</script>\n<script>",
                1,
            )
            assert source_script in markup
            content = markup.encode()
            start = next(
                message for message in captured if message["type"] == "http.response.start"
            )
            headers = [
                (key, value)
                for key, value in start["headers"]
                if key.lower() not in (b"content-length", b"cache-control")
            ]
            headers += [
                (b"content-length", str(len(content)).encode()),
                (b"cache-control", b"no-store"),
            ]
            await send({**start, "headers": headers})
            await send({"type": "http.response.body", "body": content})

    server = OwnedServer(uvicorn.Config(ObservedApp(), log_level="error", access_log=False))
    serving = asyncio.create_task(server.serve(sockets=[listener]))

    async def heartbeat():
        while True:
            process = speech._process
            report["runtime"] = {
                "sampled_ms": old["now_ms"](),
                "active": speech._active is not None,
                "pending": speech._pending,
                "worker_pid": process.pid if process is not None else None,
                "worker_returncode": process.returncode if process is not None else None,
                "exchange_started": speech.exchange_started.is_set(),
                "owned_pids": [item.pid for item in speech.processes],
                "owned_returncodes": [item.returncode for item in speech.processes],
            }
            save()
            await asyncio.sleep(0.1)

    recording = asyncio.create_task(heartbeat())
    stop_wait = asyncio.create_task(stop.wait())
    try:
        async with asyncio.timeout(10):
            while not server.started:
                if serving.done():
                    await serving
                    raise RuntimeError("server ended before startup")
                await asyncio.sleep(0.05)
        report["status"] = "READY_FOR_OWNER_BROWSER"
        save()
        print(
            json.dumps(
                {
                    "status": report["status"],
                    "origin": origin,
                    "report": str(output / "report.json"),
                }
            ),
            flush=True,
        )
        await asyncio.wait({serving, stop_wait}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        report["status"] = "CLEANING_UP"
        errors = []
        for operation in (speech.close, lambda: body.detach(reason="probe shutdown")):
            try:
                await asyncio.wait_for(operation(), 15)
            except BaseException as error:
                errors.append(type(error).__name__)
        server.should_exit = True
        try:
            await asyncio.wait_for(serving, 15)
        except BaseException as error:
            errors.append(type(error).__name__)
            serving.cancel()
            await asyncio.gather(serving, return_exceptions=True)
        recording.cancel()
        stop_wait.cancel()
        await asyncio.gather(recording, stop_wait, return_exceptions=True)
        await hub.shutdown()
        tokens._tokens.clear()
        listener.close()
        temporary.cleanup()
        report["cleanup"] = {
            "error_types": errors,
            "owned_worker_reaped": all(item.returncode is not None for item in speech.processes),
            "remaining_qwen_pids": qwen_pids(),
            "pending": speech._pending,
            "active_cleared": speech._active is None,
            "server_stopped": serving.done(),
            "listener_closed": listener.fileno() == -1,
            "temporary_cache_removed": not Path(temporary.name).exists(),
            "control_clients": hub.client_count,
        }
        report["source_hashes_end"] = hashes()
        report["source_unchanged"] = report["source_hashes_end"] == report["source_hashes_start"]
        report["status"] = "STOPPED_AWAITING_OWNER_VERDICT" if not errors else "FAILED_CLEANUP"
        save()
        for name in (signal.SIGINT, signal.SIGTERM):
            loop.remove_signal_handler(name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-real", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.run_real:
        print("NOT_RUN: explicit --run-real and exclusive GPU ownership required")
        return
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    asyncio.run(serve(args.output.resolve()))


if __name__ == "__main__":
    main()

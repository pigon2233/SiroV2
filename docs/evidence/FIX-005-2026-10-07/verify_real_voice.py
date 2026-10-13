#!/usr/bin/env python3
"""Isolated FIX-005 native-browser probe; GPU inference requires --run-real.

Run with the project .venv/bin/python. No service, private DB, env file, ASR,
cloud endpoint, original cache or original reference audio is copied or changed.
Native playing/ended proves browser playback lifecycle, not human listening or
semantic fidelity. Qwen EOS metadata proves generation termination only.
"""

# ruff: noqa: RUF001  # Mandarin punctuation is intentional synthetic input.

from __future__ import annotations

import argparse
import ast
import asyncio
import contextvars
import hashlib
import io
import json
import os
import socket
import tempfile
import time
import wave
from pathlib import Path
from typing import Any

import uvicorn
from playwright.async_api import async_playwright

from siro.adapters.body.web import WebSocketBodyTransport
from siro.services.audio.tts import QwenReferenceTTS, plan_speech, prepare_spoken_text
from siro.services.presentation.gateway import GatewayHub, GatewayState, SessionTokens, create_app

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
ARTIFACTS = ROOT / ".siro-data/verification/FIX-005-2026-10-08"
CHROME = "/opt/google/chrome/chrome"
SHORT = "今天的天空很晴朗，我們一起把小故事慢慢說完。"
STORY = (
    "星期六的清晨，小雨帶著一盞小燈，陪爺爺走進安靜的花園。"
    "昨夜的雨水還停在葉尖，一隻迷路的小鳥躲在木椅旁，輕輕叫著。"
    "小雨放下一碗清水，退到樹後耐心等待，爺爺則替牠搭了一處避風的小屋。"
    "太陽升高時，小鳥終於拍動翅膀，飛向遠處傳來歌聲的樹林。"
    "他們收好小燈，一起回家吃熱粥，窗邊也留下了一個溫柔的約定。"
    "故事到這裡，平安結束了。"
)
CANCEL_TEXT = (
    "這是一段專門驗證取消的全新合成文字。小船沿著安靜的河道緩緩前進，"
    "船上的孩子正在等待遠方的鐘聲，還沒有開始講述今天的冒險。"
)
JOB: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "voice_probe_job", default=None
)
COMPLETION_KEYS = (
    "status",
    "eos_observed",
    "cap_reached",
    "generated_tokens",
    "max_new_tokens",
    "observer_calls",
)


def now_ms() -> float:
    return round(time.time() * 1000, 3)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_hashes() -> dict[str, str]:
    paths = (
        "scripts/qwen_tts_worker.py",
        "src/siro/services/audio/tts.py",
        "src/siro/services/presentation/gateway.py",
        "src/siro/services/presentation/static/index.html",
    )
    return {path: sha((ROOT / path).read_bytes()) for path in paths}


def wav_duration(audio: bytes) -> float:
    with wave.open(io.BytesIO(audio), "rb") as source:
        return source.getnframes() / source.getframerate()


def gateway_reference_text() -> str:
    """Read only the existing constructor's source literal, never reference samples."""
    source = ROOT / "src/siro/services/presentation/gateway.py"
    candidates = [
        node
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8")))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "QwenReferenceTTS"
        and len(node.args) >= 5
    ]
    assert len(candidates) == 1, "Expected one Qwen constructor literal"
    literal = candidates[0].args[4]
    assert isinstance(literal, ast.Constant) and isinstance(literal.value, str)
    return literal.value


class Recorder:
    def __init__(self, output: Path) -> None:
        self.output = output
        self.case = "unassigned"
        self.jobs: list[dict[str, Any]] = []
        self.exchange_started = asyncio.Event()
        self.processes: list[asyncio.subprocess.Process] = []
        self.save_callback = lambda: None

    async def record_render(self, text: str, render) -> bytes:
        spoken = prepare_spoken_text(text)
        record: dict[str, Any] = {
            "index": len(self.jobs),
            "case": self.case,
            "chars": len(spoken),
            "text_sha256": sha(spoken.encode()),
            "started_ms": now_ms(),
            "worker_messages": [],
            "outcome": "pending",
        }
        self.jobs.append(record)
        token = JOB.set(record)
        started = time.monotonic()
        try:
            audio = await render()
            record.update(
                outcome="audio", ended_ms=now_ms(), audio_duration_seconds=wav_duration(audio)
            )
            filename = self.output / f"{record['index']:02d}-{self.case}.wav"
            filename.write_bytes(audio)
            record.update(audio_path=str(filename), audio_bytes=len(audio), audio_sha256=sha(audio))
            return audio
        except BaseException as error:
            record.update(outcome=type(error).__name__, ended_ms=now_ms())
            raise
        finally:
            record["elapsed_seconds"] = round(time.monotonic() - started, 6)
            if record["outcome"] == "audio":
                record["real_time_factor"] = round(
                    record["elapsed_seconds"] / record["audio_duration_seconds"], 6
                )
            JOB.reset(token)
            self.save_callback()


class ObservedQwen(QwenReferenceTTS, Recorder):
    def __init__(self, cache: Path, output: Path) -> None:
        Recorder.__init__(self, output)
        QwenReferenceTTS.__init__(
            self,
            ROOT / ".siro-data/qwen-tts-venv/bin/python",
            ROOT / "scripts/qwen_tts_worker.py",
            ROOT / ".siro-data/models/qwen3-tts-0.6b-base",
            ROOT / ".siro-data/qwen3-siro-anime-daughter-v1.wav",
            gateway_reference_text(),
            cache,
            lifecycle=True,
        )

    async def render(self, text: str, *, rate=1.0, pitch=0.0, energy=0.5) -> bytes:
        return await self.record_render(
            text,
            lambda: super(ObservedQwen, self).render(text, rate=rate, pitch=pitch, energy=energy),
        )

    async def _read_json(self, process, timeout):
        if process not in self.processes:
            self.processes.append(process)
        record = JOB.get()
        if record is not None and self._completion_protocol == 2:
            record["exchange_wait_started_ms"] = now_ms()
            if self.case == "cancel":
                self.exchange_started.set()  # stdin has been drained; awaiting inference response.
        response = await super()._read_json(process, timeout)
        safe = {
            key: response[key]
            for key in ("ready", "device", "completion_protocol", "cache_hit")
            if key in response
        }
        completion = response.get("completion")
        if isinstance(completion, dict):
            safe["completion"] = {key: completion.get(key) for key in COMPLETION_KEYS}
        safe.update(received_ms=now_ms(), audio_present=isinstance(response.get("audio"), str))
        if "error" in response:
            safe["worker_error_present"] = True
        if record is not None:
            record["worker_messages"].append(safe)
        self.save_callback()
        return response


class SyntheticSpeech(Recorder):
    """Only validates the probe's real-browser lifecycle; no Qwen evidence."""

    def __init__(self, output: Path) -> None:
        super().__init__(output)
        self.cache: dict[str, bytes] = {}
        self._pending = 0
        self._active = None
        self._process = None
        self._closed = False

    async def render(self, text: str, *, rate=1.0, pitch=0.0, energy=0.5) -> bytes:
        async def render():
            self._pending += 1
            self._active = asyncio.current_task()
            try:
                self.exchange_started.set()
                if self.case == "cancel":
                    await asyncio.sleep(60)
                spoken = prepare_spoken_text(text)
                hit = spoken in self.cache
                if not hit:
                    await asyncio.sleep(0.12)
                    target = io.BytesIO()
                    with wave.open(target, "wb") as audio:
                        audio.setnchannels(1)
                        audio.setsampwidth(2)
                        audio.setframerate(8000)
                        audio.writeframes(bytes(16000))  # Native one-second playback, rate=1.
                    self.cache[spoken] = target.getvalue()
                record = JOB.get()
                record["worker_messages"].append({"cache_hit": hit, "synthetic": True})
                return self.cache[spoken]
            finally:
                self._pending -= 1
                self._active = None

        return await self.record_render(text, render)

    async def close(self) -> None:
        self._closed = True
        if self._active is not None:
            self._active.cancel()
            await asyncio.gather(self._active, return_exceptions=True)


NATIVE_OBSERVER = r"""(() => {
  const NativeAudio = window.Audio;
  const probe = window.__voiceProbe = {audios: [], statuses: [], remoteRequests: []};
  const stamp = () => Date.now();
  window.Audio = function(...args) {
    const audio = new NativeAudio(...args);
    const record = {index: probe.audios.length, created_ms: stamp(), events: []};
    probe.audios.push(record);
    for (const event of ['play', 'playing', 'waiting', 'stalled', 'ended', 'error', 'pause']) {
      audio.addEventListener(event, () => record.events.push({type: event, at_ms: stamp(),
        current_time: audio.currentTime,
        duration: Number.isFinite(audio.duration) ? audio.duration : null,
        playback_rate: audio.playbackRate,
        status: document.querySelector('#tts-status')?.textContent}));
    }
    return audio;
  };
  window.Audio.prototype = NativeAudio.prototype;
  Object.setPrototypeOf(window.Audio, NativeAudio);
  addEventListener('DOMContentLoaded', () => {
    const status = document.querySelector('#tts-status');
    if (status) new MutationObserver(() =>
      probe.statuses.push({at_ms: stamp(), text: status.textContent}))
      .observe(status, {childList:true, subtree:true, characterData:true});
  });
})();"""


async def wait_until(predicate, timeout: float = 10) -> None:
    async with asyncio.timeout(timeout):
        while not predicate():
            await asyncio.sleep(0.05)


def response_metadata(job: dict[str, Any]) -> dict[str, Any]:
    return next(message for message in reversed(job["worker_messages"]) if "cache_hit" in message)


async def verify(args) -> None:
    mode = "real" if args.run_real else "synthetic"
    output = Path(args.output).resolve() if args.output else ARTIFACTS / mode
    output.mkdir(parents=True, exist_ok=True)
    result: dict[str, Any] = {
        "status": "STARTING",
        "mode": mode,
        "real_qwen_inference": "RUN" if args.run_real else "NOT_RUN",
        "human_listening": "NOT_RUN",
        "child_offline_policy": {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"},
        "started_ms": now_ms(),
        "scope": "Native Chromium Audio playing/ended, actual index.html and ephemeral Uvicorn",
        "limits": [
            "No human listening or semantic fidelity claim",
            "No ASR or cloud audio transfer",
            "EOS metadata is generation termination evidence only",
            "First speech waits for final text",
        ],
        "verification_script_sha256": sha(Path(__file__).read_bytes()),
        "source_sha256_start": source_hashes(),
        "story_chars": len(STORY),
        "story_final_sentence": "故事到這裡，平安結束了。",
        "checks": {},
        "jobs": [],
        "stage": "cold-short",
    }
    report = output / "result.json"

    def save():
        report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    checks = result["checks"]
    tokens, hub, body = SessionTokens(), GatewayHub(), WebSocketBodyTransport()
    browser = context = playwright = server = serving = listener = None
    passed = False
    page_errors: list[str] = []
    blocked_requests: list[str] = []
    cancel_task = None
    with tempfile.TemporaryDirectory(prefix="siro-fix005-cache-") as temporary:
        speech = ObservedQwen(Path(temporary), output) if args.run_real else SyntheticSpeech(output)
        speech.save_callback = save
        result["jobs"] = speech.jobs
        result["cache"] = {"temporary": True, "original_cache_untouched": True}
        save()
        try:
            speech.case = "cold-short"
            cold = await speech.render(SHORT)
            assert response_metadata(speech.jobs[-1])["cache_hit"] is False
            if args.run_real:
                assert speech.jobs[-1]["worker_messages"][0]["completion_protocol"] == 2
            checks["cold_short"] = "PASS"
            result["stage"] = "cache-hit"
            speech.case = "cache-hit"
            cached = await speech.render(SHORT)
            assert response_metadata(speech.jobs[-1])["cache_hit"] is True and cold == cached
            checks["cache_hit_separate_from_warm_generation"] = "PASS"
            save()

            listener = socket.socket()
            listener.bind(("127.0.0.1", 0))
            listener.listen(128)
            listener.setblocking(False)
            port = listener.getsockname()[1]
            assert port != 8026
            origin = f"http://127.0.0.1:{port}"
            state = GatewayState()
            state.routes.update(
                model="synthetic:known-story", tts=f"local:{mode}-verification", body="placeholder"
            )
            turns: list[dict[str, Any]] = []

            async def on_turn(session_id, text, input_mode):
                index = len(turns)
                content = STORY if index == 0 else CANCEL_TEXT
                turns.append(
                    {
                        "index": index,
                        "terminal_ms": now_ms(),
                        "content_sha256": sha(content.encode()),
                    }
                )
                stream = f"synthetic-voice-probe-{index}"
                for event in (
                    {"type": "assistant_started"},
                    {"type": "assistant_delta", "text": content},
                    {"type": "assistant_terminal", "state": "completed", "error": None},
                ):
                    await hub.broadcast({**event, "session_id": session_id, "stream_id": stream})

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
            server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
            serving = asyncio.create_task(server.serve(sockets=[listener]))
            await wait_until(lambda: server.started or serving.done())
            assert server.started
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(
                executable_path=args.chromium,
                headless=True,
                args=["--autoplay-policy=no-user-gesture-required"],
            )
            context = await browser.new_context(viewport={"width": 1440, "height": 1050})

            async def route_request(route):
                url = route.request.url
                if url.startswith(origin + "/"):
                    await route.continue_()
                else:
                    blocked_requests.append(url.split("?", 1)[0])
                    await route.abort()

            await context.route("**/*", route_request)
            await context.add_init_script(NATIVE_OBSERVER)
            page = await context.new_page()
            page.on("pageerror", lambda error: page_errors.append(type(error).__name__))
            await page.goto(origin, wait_until="networkidle")
            await page.wait_for_function(
                "document.querySelector('#connection').textContent === '已連線'"
            )
            await wait_until(lambda: body.connected)
            loaded = await page.locator("script").text_content()
            source = (ROOT / "src/siro/services/presentation/static/index.html").read_text(
                encoding="utf-8"
            )
            source_script = source.split("<script>", 1)[1].split("</script>", 1)[0]
            result["ui_script_sha256"] = sha(loaded.encode())
            assert sha(loaded.encode()) == sha(source_script.encode())
            await page.locator("#voice-output").check()
            result["stage"] = "browser-story"
            speech.case = "browser-story"
            plan = plan_speech(STORY)
            assert 150 <= len(STORY) <= 180 and len(plan["segments"]) > 1
            assert "".join(plan["segments"]) == plan["spoken_text"]
            result["story_plan"] = plan
            await page.locator("#text").fill("請說這篇合成驗收小故事。")
            await page.locator("#chat button[type=submit]").click()
            await page.wait_for_function(
                "document.querySelector('#tts-status').textContent.startsWith('全文朗讀完成')",
                timeout=args.timeout * 1000,
            )
            observed = await page.evaluate("window.__voiceProbe")
            jobs = [job for job in speech.jobs if job["case"] == "browser-story"]
            assert len(jobs) == len(plan["segments"]) == len(observed["audios"])
            assert all(
                job["outcome"] == "audio" and response_metadata(job)["cache_hit"] is False
                for job in jobs
            )
            assert [job["text_sha256"] for job in jobs] == [
                sha(prepare_spoken_text(segment).encode()) for segment in plan["segments"]
            ]
            playing, ended = [], []
            for audio in observed["audios"]:
                play_events = [event for event in audio["events"] if event["type"] == "playing"]
                end_events = [event for event in audio["events"] if event["type"] == "ended"]
                assert play_events and len(end_events) == 1
                assert not any(event["type"] == "error" for event in audio["events"])
                assert all(event["playback_rate"] == 1 for event in audio["events"])
                playing.append(play_events[0]["at_ms"])
                ended.append(end_events[0]["at_ms"])
            assert all(playing[index] >= ended[index - 1] for index in range(1, len(playing)))
            assert all(
                jobs[index]["started_ms"] >= ended[index - 2] for index in range(2, len(jobs))
            ), "More than one segment prefetched"
            assert all(
                jobs[index]["started_ms"] >= jobs[index - 1]["ended_ms"]
                for index in range(1, len(jobs))
            ), "Concurrent inference observed"
            generated_at_first_play = sum(
                next(
                    (
                        message["received_ms"]
                        for message in job["worker_messages"]
                        if message.get("audio_present")
                    ),
                    job["ended_ms"],
                )
                <= playing[0]
                for job in jobs
            )
            assert generated_at_first_play < len(jobs)
            complete = [
                status
                for status in observed["statuses"]
                if status["text"].startswith("全文朗讀完成")
            ]
            assert len(complete) == 1 and complete[0]["at_ms"] >= ended[-1]
            assert all(
                not str(event.get("status", "")).startswith("全文朗讀完成")
                for event in observed["audios"][-1]["events"]
                if event["type"] == "ended"
            )
            result["browser_story"] = {
                "native_audio": observed["audios"],
                "statuses": observed["statuses"],
                "first_play_wait_seconds": (playing[0] - turns[0]["terminal_ms"]) / 1000,
                "generated_segments_at_first_play": generated_at_first_play,
                "segment_gaps_seconds": [
                    (playing[index] - ended[index - 1]) / 1000 for index in range(1, len(playing))
                ],
                "completed_after_final_ended": True,
                "max_one_segment_prefetch": True,
                "warm_uncached_render_seconds": [job["elapsed_seconds"] for job in jobs],
            }
            checks["browser_ordered_complete_native_playback"] = "PASS"
            save()

            # Cancel a fresh request after its stdin drain, before any response/audio.
            result["stage"] = "cancel"
            speech.case = "cancel"
            speech.exchange_started.clear()
            cancel_plan = plan_speech(CANCEL_TEXT)
            fresh = sha(prepare_spoken_text(cancel_plan["segments"][0]).encode())
            assert fresh not in [job["text_sha256"] for job in speech.jobs]
            before_audio = len(observed["audios"])
            if args.run_real:
                await page.locator("#text").fill("請開始另一篇全新合成故事，接著測試停止。")
                await page.locator("#chat button[type=submit]").click()
                await asyncio.wait_for(speech.exchange_started.wait(), 30)
            else:
                # SyntheticSpeech has no owned-disconnect gateway path; directly
                # cancel its task while retaining real browser no-lateaudio check.
                cancel_task = asyncio.create_task(speech.render(cancel_plan["segments"][0]))
                await asyncio.wait_for(speech.exchange_started.wait(), 5)
            active_job = speech.jobs[-1]
            assert active_job["case"] == "cancel" and active_job["outcome"] == "pending"
            owned_process = speech._process
            await asyncio.sleep(0.25)
            assert active_job["outcome"] == "pending", (
                "Inference finished before cancellation; not a cancellation test"
            )
            cancel_at = now_ms()
            await page.locator("#cancel").click()
            if cancel_task is not None:
                cancel_task.cancel()
                await asyncio.gather(cancel_task, return_exceptions=True)
            await wait_until(
                lambda: speech._pending == 0 and speech._active is None and speech._process is None,
                15,
            )
            assert active_job["outcome"] == "CancelledError"
            assert owned_process is None or owned_process.returncode is not None
            await asyncio.sleep(1.0)
            after_cancel = await page.evaluate("window.__voiceProbe")
            assert len(after_cancel["audios"]) == before_audio
            assert not active_job.get("audio_path")
            result["cancellation"] = {
                "inference_wait_observed": True,
                "cancel_at_ms": cancel_at,
                "worker_reaped_before_close": owned_process is not None
                and owned_process.returncode is not None,
                "worker_returncode": owned_process.returncode
                if owned_process is not None
                else None,
                "no_audio_returned": True,
                "no_new_native_audio_after_cancel": True,
                "observation_after_cleanup_seconds": 1.0,
                "scope": "owned Qwen gateway disconnect"
                if args.run_real
                else "synthetic direct-task only",
            }
            checks["fresh_inflight_cancel"] = "PASS" if args.run_real else "SYNTHETIC_ONLY"
            assert not page_errors and not blocked_requests
            assert (
                sha(
                    (ROOT / "src/siro/services/presentation/static/index.html")
                    .read_text(encoding="utf-8")
                    .split("<script>", 1)[1]
                    .split("</script>", 1)[0]
                    .encode()
                )
                == result["ui_script_sha256"]
            )
            result["status"] = "CHECKS_PASSED_AWAITING_CLEANUP"
            passed = True
            save()
        except BaseException as error:
            result.update(
                status="FAILED", failure_type=type(error).__name__, failure_stage=result["stage"]
            )
            save()
            raise
        finally:
            result["stage"] = "cleanup"
            cleanup_errors: list[str] = []

            async def cleanup_call(awaitable):
                try:
                    await asyncio.wait_for(awaitable, 15)
                except BaseException as error:
                    cleanup_errors.append(type(error).__name__)

            if cancel_task is not None and not cancel_task.done():
                cancel_task.cancel()
                await cleanup_call(asyncio.gather(cancel_task, return_exceptions=True))
            if context is not None:
                await cleanup_call(context.close())
            if browser is not None:
                await cleanup_call(browser.close())
            if playwright is not None:
                await cleanup_call(playwright.stop())
            await cleanup_call(body.detach(reason="isolated voice verification cleanup"))
            if server is not None:
                server.should_exit = True
            if serving is not None:
                await cleanup_call(serving)
            if listener is not None:
                listener.close()
            await cleanup_call(speech.close())
            await cleanup_call(hub.shutdown())
            token_count = len(tokens._tokens)
            tokens._tokens.clear()
            result["cleanup"] = {
                "browser_closed": browser is None or not browser.is_connected(),
                "body_detached": not body.connected,
                "control_clients_remaining": hub.client_count,
                "server_stopped": serving is None or serving.done(),
                "listener_closed": listener is None or listener.fileno() == -1,
                "qwen_closed": speech._closed,
                "pending_renders": speech._pending,
                "active_render_cleared": speech._active is None,
                "owned_processes_reaped": all(
                    process.returncode is not None for process in speech.processes
                ),
                "owned_process_count": len(speech.processes),
                "temporary_tokens_disposed": token_count,
                "tokens_remaining": len(tokens._tokens),
                "cleanup_error_types": cleanup_errors,
            }
            cleaned = not cleanup_errors and all(
                (
                    result["cleanup"]["browser_closed"],
                    not body.connected,
                    hub.client_count == 0,
                    result["cleanup"]["server_stopped"],
                    result["cleanup"]["listener_closed"],
                    speech._closed,
                    speech._pending == 0,
                    speech._active is None,
                    result["cleanup"]["owned_processes_reaped"],
                    len(tokens._tokens) == 0,
                )
            )
            if not cleaned:
                result["status"] = "FAILED_CLEANUP"
            elif passed:
                result["status"] = "CHECKS_PASSED_AWAITING_TEMP_CACHE_CLEANUP"
            result["page_js_error_types"] = page_errors
            result["blocked_external_request_count"] = len(blocked_requests)
            save()
    result["cleanup"]["temporary_cache_removed"] = not Path(temporary).exists()
    if passed and result["status"] == "CHECKS_PASSED_AWAITING_TEMP_CACHE_CLEANUP":
        result["status"] = "PASS" if args.run_real else "SYNTHETIC_PROBE_PASS"
        result["stage"] = "finished"
    if not result["cleanup"]["temporary_cache_removed"]:
        result["status"] = "FAILED_CLEANUP"
    result["source_sha256_finish"] = source_hashes()
    if result["source_sha256_start"] != result["source_sha256_finish"]:
        result["status"] = "STALE_SOURCE"
    save()
    print(
        json.dumps(
            {"status": result["status"], "report": str(report), "checks": checks},
            ensure_ascii=False,
        ),
        flush=True,
    )
    assert result["status"] in {"PASS", "SYNTHETIC_PROBE_PASS"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument(
        "--run-real",
        action="store_true",
        help="Explicit opt-in: starts owned local Qwen GPU worker",
    )
    modes.add_argument(
        "--synthetic-only",
        action="store_true",
        help="Validate harness using synthetic one-second silent WAV",
    )
    parser.add_argument("--chromium", default=CHROME)
    parser.add_argument(
        "--output", help="Local generated WAV/JSON directory (default .siro-data/verification/...)"
    )
    parser.add_argument(
        "--timeout", type=int, default=1200, help="Browser whole-story wait in seconds"
    )
    args = parser.parse_args()
    # These process-local settings are inherited by the owned Qwen child only;
    # no original service environment is inspected, saved, or changed.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    asyncio.run(verify(args))


if __name__ == "__main__":
    main()

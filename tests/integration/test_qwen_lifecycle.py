from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

from siro.services.audio.tts import QwenReferenceTTS
from siro.services.presentation.gateway import create_app

WORKER = """
import base64,json,sys,time,os
from pathlib import Path
mode=Path(sys.argv[1]).name
Path(sys.argv[4]).mkdir(exist_ok=True)
with (Path(sys.argv[4])/'pids').open('a') as f:f.write(str(os.getpid())+'\\n')
if mode=='startup':time.sleep(100)
if mode=='invalid':print(json.dumps({'ready':False}),flush=True)
elif mode.startswith('metadata'):
 print(json.dumps({'ready':True,'completion_protocol':2}),flush=True)
elif mode=='unknown-protocol':print(json.dumps({'ready':True,'completion_protocol':3}),flush=True)
else:print(json.dumps({'ready':True}),flush=True)
for line in sys.stdin:
 r=json.loads(line)
 with (Path(sys.argv[4])/'requests').open('a') as f:f.write(json.dumps(r)+'\\n')
 r['text']=r['text'].rstrip('。')
 if r['text']=='delay':time.sleep(100)
 if r['text']=='eof':sys.exit(0)
 ident={k:r[k] for k in ('request_id','epoch') if k in r}
 if r['text']=='mismatch':ident['request_id']='old'
 if r['text']=='epoch':ident['epoch']=-1
 if r['text']=='error':out={'error':'synthetic'}
 else:out={'audio':base64.b64encode(r['text'].encode()).decode()}
 if mode.startswith('metadata') and mode!='metadata-missing':
  completion={'status':'complete','eos_observed':True,'cap_reached':False,
              'generated_tokens':20,'max_new_tokens':512,'observer_calls':1}
  if mode=='metadata-no-eos':completion['eos_observed']=False
  if mode=='metadata-cap':completion['cap_reached']=True
  if mode=='metadata-count':completion['generated_tokens']=512
  if mode=='metadata-status':completion['status']='unknown'
  if mode=='metadata-observers':completion['observer_calls']=2
  if mode=='metadata-bool-count':completion['generated_tokens']=True
  out['completion']=completion
 print(json.dumps({**ident,**out}),flush=True)
"""


def adapter(
    tmp_path: Path,
    *,
    mode: str = "normal",
    lifecycle: bool = True,
    timeout: float = 1,
    max_pending: int = 8,
) -> QwenReferenceTTS:
    worker = tmp_path / "worker.py"
    worker.write_text(WORKER)
    model = tmp_path / mode
    model.mkdir(exist_ok=True)
    reference = tmp_path / "ref.wav"
    reference.touch()
    return QwenReferenceTTS(
        Path(sys.executable),
        worker,
        model,
        reference,
        "synthetic",
        tmp_path / "cache",
        startup_timeout=0.15,
        render_timeout=timeout,
        lifecycle=lifecycle,
        max_pending=max_pending,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("lifecycle", [True, False])
@pytest.mark.parametrize(
    "mode",
    [
        "metadata-missing",
        "metadata-no-eos",
        "metadata-cap",
        "metadata-count",
        "metadata-status",
        "metadata-observers",
        "metadata-bool-count",
        "unknown-protocol",
    ],
)
async def test_advertised_completion_protocol_rejects_unverified_audio(
    tmp_path: Path, lifecycle: bool, mode: str
) -> None:
    tts = adapter(tmp_path, mode=mode, lifecycle=lifecycle)
    try:
        with pytest.raises(RuntimeError):
            await tts.render("synthetic")
        if lifecycle:
            assert tts._process is None
    finally:
        await tts.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("lifecycle", [True, False])
async def test_complete_protocol_audio_preserves_existing_bytes_caller(
    tmp_path: Path, lifecycle: bool
) -> None:
    tts = adapter(tmp_path, mode="metadata-ok", lifecycle=lifecycle)
    try:
        assert await tts.render("synthetic") == b"synthetic"
    finally:
        await tts.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text,error",
    [
        ("mismatch", RuntimeError),
        ("epoch", RuntimeError),
        ("eof", RuntimeError),
        ("error", RuntimeError),
        ("delay", TimeoutError),
    ],
)
async def test_failed_render_reaps_then_restarts(
    tmp_path: Path, text: str, error: type[Exception]
) -> None:
    tts = adapter(tmp_path, timeout=0.1)
    try:
        assert await tts.render("first") == b"first"
        old = tts._process
        assert old is not None
        with pytest.raises(error):
            await tts.render(text)
        assert old.returncode is not None
        assert tts._process is None
        assert await tts.render("second") == b"second"
        assert tts._process is not None and tts._process.pid != old.pid
    finally:
        await tts.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["startup", "invalid"])
async def test_startup_failure_has_no_owned_child(tmp_path: Path, mode: str) -> None:
    tts = adapter(tmp_path, mode=mode)
    with pytest.raises((TimeoutError, RuntimeError)):
        await tts.render("first")
    assert tts._process is None
    pids = (tmp_path / "cache" / "pids").read_text().splitlines()
    assert all(not Path("/proc", pid).exists() for pid in pids)
    await tts.close()


@pytest.mark.asyncio
async def test_cancel_active_queue_bound_and_close(tmp_path: Path) -> None:
    tts = adapter(tmp_path, max_pending=2)
    assert await tts.render("ready") == b"ready"
    old = tts._process
    active = asyncio.create_task(tts.render("delay"))
    await asyncio.sleep(0.02)
    queued = asyncio.create_task(tts.render("queued"))
    await asyncio.sleep(0.02)
    with pytest.raises(RuntimeError, match="queue is full"):
        await tts.render("overflow")
    queued.cancel()
    with pytest.raises(asyncio.CancelledError):
        await queued
    active.cancel()
    with pytest.raises(asyncio.CancelledError):
        await active
    assert old is not None and old.returncode is not None
    assert await tts.render("restart") == b"restart"
    last = tts._process
    active = asyncio.create_task(tts.render("delay"))
    await asyncio.sleep(0.02)
    async with create_app(text_to_speech=tts).router.lifespan_context(create_app()):
        pass
    with pytest.raises(asyncio.CancelledError):
        await active
    assert last is not None and last.returncode is not None
    with pytest.raises(RuntimeError, match="closed"):
        await tts.render("closed")
    await tts.close()


@pytest.mark.asyncio
async def test_legacy_text_only_worker_compatibility(tmp_path: Path) -> None:
    tts = adapter(tmp_path, lifecycle=False)
    try:
        assert await tts.render("legacy") == b"legacy"
        assert await tts.render("again") == b"again"
    finally:
        await tts.close()


@pytest.mark.asyncio
async def test_concurrent_calls_use_one_worker(tmp_path: Path) -> None:
    tts = adapter(tmp_path)
    try:
        results = await asyncio.gather(*(tts.render(str(i)) for i in range(8)))
        assert results == [str(i).encode() for i in range(8)]
        assert len((tmp_path / "cache" / "pids").read_text().splitlines()) == 1
    finally:
        await tts.close()


@pytest.mark.asyncio
async def test_cancel_during_startup(tmp_path: Path) -> None:
    tts = adapter(tmp_path, mode="startup")
    task = asyncio.create_task(tts.render("first"))
    try:
        for _ in range(100):
            if tts._process is not None:
                break
            await asyncio.sleep(0.001)
        process = tts._process
        assert process is not None
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert process.returncode is not None
        assert tts._process is None
    finally:
        await tts.close()


def test_main_freezes_candidate_qwen_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    import uvicorn

    from siro.services.presentation import gateway

    for key in list(os.environ):
        if key.startswith("SIRO_") or key == "GROQ_API_KEY":
            monkeypatch.delenv(key)
    monkeypatch.setenv("SIRO_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SIRO_RUNTIME_PROFILE", "candidate")
    (tmp_path / "qwen-tts-venv/bin").mkdir(parents=True)
    (tmp_path / "qwen-tts-venv/bin/python").symlink_to(sys.executable)
    (tmp_path / "models/qwen3-tts-0.6b-base").mkdir(parents=True)
    (tmp_path / "qwen3-siro-anime-daughter-v1.wav").touch()
    instances: list[QwenReferenceTTS] = []

    class CaptureQwen(QwenReferenceTTS):
        def __init__(self, *args: object, **kwargs: object) -> None:
            # Capture the production constructor without loading weights.
            assert kwargs["lifecycle"] is True
            instances.append(self)

    def run(*args: object, **kwargs: object) -> None:
        monkeypatch.setenv("SIRO_RUNTIME_PROFILE", "legacy")
        assert len(instances) == 1

    monkeypatch.setattr(gateway, "QwenReferenceTTS", CaptureQwen)
    monkeypatch.setattr(uvicorn, "run", run)
    gateway.main()
    assert len(instances) == 1


@pytest.mark.asyncio
async def test_real_http_disconnect_reaps_active_worker(tmp_path: Path) -> None:
    import json

    from starlette.types import Message, Scope

    from siro.services.presentation.gateway import SessionTokens

    tts = adapter(tmp_path)
    assert await tts.render("ready") == b"ready"
    old = tts._process
    tokens = SessionTokens()
    token, _ = tokens.issue()
    app = create_app(allowed_origins={"http://test"}, tokens=tokens, text_to_speech=tts)
    disconnect = asyncio.Event()
    initial = True
    sent: list[Message] = []

    async def receive() -> Message:
        nonlocal initial
        if initial:
            initial = False
            return {
                "type": "http.request",
                "body": json.dumps({"text": "delay"}).encode(),
                "more_body": False,
            }
        await disconnect.wait()
        return {"type": "http.disconnect"}

    async def send(message: Message) -> None:
        sent.append(message)

    scope: Scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "path": "/v1/audio/speech",
        "raw_path": b"/v1/audio/speech",
        "query_string": b"",
        "scheme": "http",
        "headers": [
            (b"origin", b"http://test"),
            (b"authorization", f"Bearer {token}".encode()),
            (b"content-type", b"application/json"),
        ],
        "server": ("test", 80),
        "client": ("test", 1),
    }
    task = asyncio.create_task(app(scope, receive, send))
    try:
        for _ in range(1000):
            if "delay" in (tmp_path / "cache" / "requests").read_text():
                break
            await asyncio.sleep(0.001)
        else:
            pytest.fail("HTTP render never entered worker")
        disconnect.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 2)
        assert old is not None and old.returncode is not None
        assert tts._process is None
        assert not sent
        assert await tts.render("restart") == b"restart"
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await tts.close()


@pytest.mark.asyncio
async def test_cleanup_failure_never_reuses_poisoned_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tts = adapter(tmp_path, timeout=0.1)
    assert await tts.render("first") == b"first"
    old = tts._process
    original = tts._retire

    async def fail_cleanup() -> None:
        raise RuntimeError("synthetic cleanup failure")

    monkeypatch.setattr(tts, "_retire", fail_cleanup)
    try:
        with pytest.raises(RuntimeError, match="cleanup failure"):
            await tts.render("mismatch")
        requests = (tmp_path / "cache" / "requests").read_text()
        with pytest.raises(RuntimeError, match="cleanup failure"):
            await tts.render("must not dispatch")
        assert (tmp_path / "cache" / "requests").read_text() == requests
        assert tts._process is old
    finally:
        monkeypatch.setattr(tts, "_retire", original)
        await tts.close()
    assert old is not None and old.returncode is not None

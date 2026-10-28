from __future__ import annotations

import sys
from pathlib import Path

import pytest

from siro.services.audio.tts import QwenReferenceTTS

WORKER = """
import base64,json,sys,io,wave
from pathlib import Path
mode=Path(sys.argv[1]).name
print(json.dumps({'ready':True,'completion_protocol':2}),flush=True)
good={'status':'complete','eos_observed':True,'cap_reached':False,
      'generated_tokens':20,'max_new_tokens':512,'observer_calls':1}
def chunk(i):return base64.b64encode(bytes([i,0,i,0])).decode()
for line in sys.stdin:
 r=json.loads(line)
 ident={k:r[k] for k in ('request_id','epoch')}
 if mode=='cachehit':
  b=io.BytesIO()
  w=wave.open(b,'wb');w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000)
  w.writeframes(bytes([1,0,2,0]));w.close()
  print(json.dumps({**ident,'audio':base64.b64encode(b.getvalue()).decode(),
                    'completion':good}),flush=True);continue
 print(json.dumps({**ident,'seq':0,'sample_rate':24000,'pcm':chunk(1)}),flush=True)
 if mode=='error':print(json.dumps({**ident,'error':'X'}),flush=True);continue
 if mode=='eof':sys.exit(0)
 seq=5 if mode=='order' else 1
 print(json.dumps({**ident,'seq':seq,'sample_rate':24000,'pcm':chunk(2)}),flush=True)
 comp=dict(good)
 if mode=='badproof':comp['eos_observed']=False
 n=1 if mode=='lost' else 2
 print(json.dumps({**ident,'done':True,'chunks':n,'completion':comp}),flush=True)
"""


def adapter(tmp_path: Path, mode: str) -> QwenReferenceTTS:
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
        startup_timeout=5,
        render_timeout=5,
        lifecycle=True,
    )


@pytest.mark.asyncio
async def test_stream_yields_chunks_then_next_request_reuses_worker(tmp_path: Path) -> None:
    tts = adapter(tmp_path, "normal")
    try:
        first = [item async for item in tts.render_stream("你好")]
        pid = tts._process.pid if tts._process else None
        second = [item async for item in tts.render_stream("再見")]
        assert first == [(b"\x01\x00\x01\x00", 24000), (b"\x02\x00\x02\x00", 24000)]
        assert second == first
        assert tts._process is not None and tts._process.pid == pid
    finally:
        await tts.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["error", "eof", "order", "badproof", "lost"])
async def test_incomplete_or_bad_stream_fails_and_worker_restarts(
    tmp_path: Path, mode: str
) -> None:
    tts = adapter(tmp_path, mode)
    try:
        with pytest.raises(RuntimeError):
            [item async for item in tts.render_stream("你好")]
        assert tts._process is None
    finally:
        await tts.close()


@pytest.mark.asyncio
async def test_early_close_retires_worker_so_stale_chunks_never_leak(tmp_path: Path) -> None:
    tts = adapter(tmp_path, "normal")
    try:
        stream = tts.render_stream("你好")
        assert await anext(stream) == (b"\x01\x00\x01\x00", 24000)
        await stream.aclose()
        assert tts._process is None
        again = [item async for item in tts.render_stream("再見")]
        assert len(again) == 2
    finally:
        await tts.close()


@pytest.mark.asyncio
async def test_cached_whole_sentence_reply_is_returned_as_one_pcm_chunk(tmp_path: Path) -> None:
    tts = adapter(tmp_path, "cachehit")
    try:
        chunks = [item async for item in tts.render_stream("你好")]
        assert chunks == [(bytes([1, 0, 2, 0]), 24000)]
    finally:
        await tts.close()


@pytest.mark.asyncio
async def test_stream_needs_owned_worker(tmp_path: Path) -> None:
    tts = adapter(tmp_path, "normal")
    tts._lifecycle = False
    with pytest.raises(RuntimeError):
        [item async for item in tts.render_stream("你好")]
